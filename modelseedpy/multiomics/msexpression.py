# -*- coding: utf-8 -*-
import logging
from typing import Optional, Union, TYPE_CHECKING

import pandas as pd
import numpy as np
import re
import copy
from cobra.core.dictlist import DictList
from cobra.core.gene import Gene, ast2str, eval_gpr, parse_gpr, GPR
from cobra import Solution
from ast import And, BitAnd, BitOr, BoolOp, Expression, Name, NodeTransformer, Or
from modelseedpy.core.msgenome import MSGenome, MSFeature
from modelseedpy.core.msmodelutl import MSModelUtil

logger = logging.getLogger(__name__)

def compute_gene_score(expr, values, default):
    # Handle tuple return from parse_gpr() in newer COBRApy versions
    if isinstance(expr, tuple) and len(expr) == 2:
        expr = expr[0]  # Extract GPR object from (GPR, frozenset) tuple

    if isinstance(expr, (Expression, GPR)):
        return compute_gene_score(expr.body, values, default)
    elif isinstance(expr, Name):
        if expr.id in values:
            return values[expr.id]
        else:
            return default
    elif isinstance(expr, BoolOp):
        op = expr.op
        if isinstance(op, Or):
            total = None
            for subexpr in expr.values:
                value = compute_gene_score(subexpr, values, default)
                if value != None:
                    if total == None:
                        total = 0
                    total += value
            return total
        elif isinstance(op, And):
            least = None
            for subexpr in expr.values:
                value = compute_gene_score(subexpr, values, default)
                if value != None:
                    if least == None or value < least:
                        least = value
            return least
        else:
            raise TypeError("unsupported operation " + op.__class__.__name__)
    elif expr is None:
        return default
    else:
        raise TypeError("unsupported operation  " + repr(expr))

class MSCondition:
    def __init__(self, id, parent):
        self.id = id
        self.parent = parent

    def value_at_zscore(self, zscore: float) -> Optional[float]:
        """Calculate the value at a given z-score for this condition.

        Args:
            zscore: The z-score threshold

        Returns:
            The value at the specified z-score, or None if no data
        """
        if self.id not in self.parent._data.columns:
            return None

        values = self.parent._data[self.id].dropna()
        if len(values) == 0:
            return None

        mean = values.mean()
        std_dev = values.std()
        return mean + (zscore * std_dev)

    def lowest_value(self) -> Optional[float]:
        """Get the minimum value for this condition.

        Returns:
            The minimum value, or None if no data
        """
        if self.id not in self.parent._data.columns:
            return None

        values = self.parent._data[self.id].dropna()
        if len(values) == 0:
            return None

        return float(values.min())

    def highest_value(self) -> Optional[float]:
        """Get the maximum value for this condition.

        Returns:
            The maximum value, or None if no data
        """
        if self.id not in self.parent._data.columns:
            return None

        values = self.parent._data[self.id].dropna()
        if len(values) == 0:
            return None

        return float(values.max())

    def average_value(self) -> Optional[float]:
        """Get the mean value for this condition.

        Returns:
            The mean value, or None if no data
        """
        if self.id not in self.parent._data.columns:
            return None

        values = self.parent._data[self.id].dropna()
        if len(values) == 0:
            return None

        return float(values.mean())

    def sum_value(self) -> float:
        """Get the sum of all values for this condition.

        Returns:
            The sum of all values (0.0 if no data)
        """
        if self.id not in self.parent._data.columns:
            return 0.0

        return float(self.parent._data[self.id].sum(skipna=True))

class MSExpressionFeature:
    def __init__(self, feature, parent):
        self.id = feature.id
        self.feature = feature
        self.parent = parent

    def add_value(self, condition: Union[str, 'MSCondition'], value: float) -> None:
        """Add a value for a specific condition.

        Args:
            condition: MSCondition object or condition ID string
            value: The expression value to store
        """
        # Resolve condition to condition_id
        if isinstance(condition, str):
            condition_id = condition
        else:
            condition_id = condition.id

        # Ensure feature row exists in parent DataFrame
        if self.id not in self.parent._data.index:
            self.parent._data.loc[self.id, :] = np.nan

        # Ensure condition column exists in parent DataFrame
        if condition_id not in self.parent._data.columns:
            self.parent._data[condition_id] = np.nan

        # Set the value
        self.parent._data.loc[self.id, condition_id] = value

    def get_value(self, condition: Union[str, 'MSCondition'], convert_to_relative_abundance: bool = False) -> Optional[float]:
        """Get the expression value for a specific condition.

        Args:
            condition: MSCondition object or condition ID string
            convert_to_relative_abundance: If True, convert value to relative abundance

        Returns:
            The expression value, or None if not found
        """
        # Resolve condition to condition_id and condition object
        if isinstance(condition, str):
            if condition not in self.parent.conditions:
                logger.warning(
                    "Condition " + condition + " not found in expression object!"
                )
                return None
            condition_id = condition
            condition_obj = self.parent.conditions.get_by_id(condition)
        else:
            condition_id = condition.id
            condition_obj = condition

        # Check if value exists in DataFrame
        if self.id not in self.parent._data.index or condition_id not in self.parent._data.columns:
            logger.info(
                "Condition " + condition_id + " has no value in " + self.feature.id
            )
            return None

        # Get value from DataFrame and convert NaN to None
        value = self.parent._data.loc[self.id, condition_id]

        # Handle duplicate indices - if loc returns a Series, take the last value
        if isinstance(value, pd.Series):
            value = value.iloc[-1]

        if pd.isna(value):
            logger.info(
                "Condition " + condition_id + " has no value in " + self.feature.id
            )
            return None

        # Apply relative abundance conversion if requested
        if convert_to_relative_abundance:
            if self.parent.type == "AbsoluteAbundance":
                value = value / condition_obj.column_sum
            elif self.parent.type == "FPKM":
                value = value / condition_obj.column_sum
            elif self.parent.type == "TPM":
                value = value / condition_obj.column_sum
            elif self.parent.type == "Log2":
                value = 2 ** (value - condition_obj.lowest_value()) / 2 ** (condition_obj.column_sum - self.parent.features.len() * condition_obj.lowest_value())

        return value

class MSExpression:
    def __init__(self, type):
        self.type = type  # RelativeAbundance, AbsoluteAbundance, FPKM, TPM, Log2, NormalizedRatios
        self.object = None
        self.features = DictList()
        self.conditions = DictList()
        self._data = pd.DataFrame()
        self._data.index.name = 'feature_id'

    @staticmethod
    def from_msexpression(msexpression: 'MSExpression') -> 'MSExpression':
        """Create a copy of an existing MSExpression object.

        Args:
            msexpression: The MSExpression object to copy

        Returns:
            A new MSExpression object with the same data
        """
        new_expression = MSExpression(msexpression.type)
        new_expression.object = msexpression.object
        # Copy features
        for feature in msexpression.features:
            new_expression.features.append(MSExpressionFeature(feature.feature, new_expression))
        # Copy conditions
        for condition in msexpression.conditions:
            new_expression.conditions.append(MSCondition(condition.id, new_expression))
        # Copy data DataFrame
        new_expression._data = msexpression._data.copy()
        return new_expression
    
    def from_dataframe(
        df: pd.DataFrame,
        genome: Optional['MSGenome'] = None,
        create_missing_features: bool = False,
        ignore_columns: list = None,
        description_column: Optional[str] = None,
        id_column: Optional[str] = None,
        type: str = "RelativeAbundance"
    ) -> 'MSExpression':
        """Create an MSExpression object from a pandas DataFrame.

        Args:
            df: DataFrame with feature IDs and condition values
            genome: MSGenome object (optional)
            create_missing_features: If True, create features not in genome
            ignore_columns: List of column names to ignore
            description_column: Name of column containing descriptions
            id_column: Name of column containing feature IDs (default: first column)
            type: Expression data type (RelativeAbundance, AbsoluteAbundance, FPKM, TPM, Log2)

        Returns:
            MSExpression object with data loaded from DataFrame
        """
        if ignore_columns is None:
            ignore_columns = []

        expression = MSExpression(type)
        if genome is None:
            expression.object = MSGenome()
            create_missing_features = True
        else:
            expression.object = genome

        # Identify columns
        headers = list(df.columns)
        if id_column is None:
            id_column = headers[0]

        # Identify condition columns
        conditions = []
        description_present = description_column is not None and description_column in headers

        for header in headers:
            if header == id_column:
                continue
            elif header == description_column:
                continue
            elif header not in ignore_columns:
                conditions.append(header)
                if header not in expression.conditions:
                    expression.conditions.append(MSCondition(header, expression))
                # Initialize metadata attributes
                expression.conditions.get_by_id(header).column_sum = 0
                expression.conditions.get_by_id(header).feature_count = 0

        # Add features to the expression object
        valid_feature_ids = []
        for index, row in df.iterrows():
            description = None
            if description_present:
                description = row[description_column]
            protfeature = expression.add_feature(
                row[id_column], create_missing_features, description=description
            )
            if protfeature is not None:
                valid_feature_ids.append(protfeature.id)

        # Bulk load data into DataFrame
        if len(valid_feature_ids) > 0 and len(conditions) > 0:
            # Extract numeric data columns
            data_df = df[df[id_column].isin(valid_feature_ids)].copy()
            data_df = data_df.set_index(id_column)
            data_df = data_df[conditions]

            # Convert to numeric, coercing errors to NaN
            for col in conditions:
                data_df[col] = pd.to_numeric(data_df[col], errors='coerce')

            # Assign to expression._data
            expression._data = data_df
            expression._data.index.name = 'feature_id'

        return expression
    
    @staticmethod
    def from_spreadsheet(
        filename: str,
        sheet_name: Union[str, int] = 0,
        skiprows: int = 0,
        genome: Optional['MSGenome'] = None,
        create_missing_features: bool = False,
        ignore_columns: list = None,
        description_column: Optional[str] = None,
        id_column: Optional[str] = None,
        type: str = "RelativeAbundance"
    ) -> 'MSExpression':
        """Create an MSExpression object from an Excel spreadsheet.

        Args:
            filename: Path to Excel file
            sheet_name: Sheet name or index (default: 0)
            skiprows: Number of rows to skip at start
            genome: MSGenome object (optional)
            create_missing_features: If True, create features not in genome
            ignore_columns: List of column names to ignore
            description_column: Name of column containing descriptions
            id_column: Name of column containing feature IDs (default: first column)
            type: Expression data type (RelativeAbundance, AbsoluteAbundance, FPKM, TPM, Log2)

        Returns:
            MSExpression object with data loaded from spreadsheet
        """
        df = pd.read_excel(filename, sheet_name=sheet_name, skiprows=skiprows)
        return MSExpression.from_dataframe(
            df,
            genome=genome,
            create_missing_features=create_missing_features,
            ignore_columns=ignore_columns,
            description_column=description_column,
            id_column=id_column,
            type=type
        )

    @staticmethod
    def from_gene_feature_file(
        filename: str,
        genome: Optional['MSGenome'] = None,
        create_missing_features: bool = False,
        ignore_columns: list = None,
        description_column: Optional[str] = None,
        sep: str = "\t",
        id_column: Optional[str] = None,
        type: str = "RelativeAbundance"
    ) -> 'MSExpression':
        """Create an MSExpression object from a delimited text file.

        Args:
            filename: Path to delimited file
            genome: MSGenome object (optional)
            create_missing_features: If True, create features not in genome
            ignore_columns: List of column names to ignore
            description_column: Name of column containing descriptions
            sep: Field delimiter (default: tab)
            id_column: Name of column containing feature IDs (default: first column)
            type: Expression data type (RelativeAbundance, AbsoluteAbundance, FPKM, TPM, Log2)

        Returns:
            MSExpression object with data loaded from file
        """
        df = pd.read_csv(filename, sep=sep)
        return MSExpression.from_dataframe(
            df,
            genome=genome,
            create_missing_features=create_missing_features,
            ignore_columns=ignore_columns,
            description_column=description_column,
            id_column=id_column,
            type=type
        )

    def add_feature(
        self,
        id: str,
        create_gene_if_missing: bool = False,
        description: Optional[str] = None
    ) -> Optional['MSExpressionFeature']:
        """Add a feature to the expression object.

        Args:
            id: Feature ID
            create_gene_if_missing: If True, create the gene in genome if missing
            description: Optional feature description

        Returns:
            MSExpressionFeature object, or None if feature not found
        """
        if id in self.features:
            return self.features.get_by_id(id)
        feature = None
        # Check if object is MSGenome (gene expression) or Model (reaction expression)
        if isinstance(self.object, MSGenome):
            if self.object.search_for_gene(id) is None:
                if create_gene_if_missing:
                    self.object.features.append(MSFeature(id, ""))
            feature = self.object.search_for_gene(id)
        else:
            # Assume it's a COBRApy Model with reactions
            if hasattr(self.object, 'reactions') and id in self.object.reactions:
                feature = self.object.reactions.get_by_id(id)
        if feature is None:
            logger.warning(
                "Feature referred by expression " + id + " not found in genome object!"
            )
            return None
        if feature.id in self.features:
            return self.features.get_by_id(feature.id)
        protfeature = MSExpressionFeature(feature, self)
        self.features.append(protfeature)
        return protfeature

    def get_value(
        self,
        feature: Union[str, 'MSExpressionFeature'],
        condition: Union[str, 'MSCondition']
    ) -> Optional[float]:
        """Get expression value for a feature and condition.

        Args:
            feature: MSExpressionFeature object or feature ID string
            condition: MSCondition object or condition ID string

        Returns:
            The expression value, or None if not found
        """
        if isinstance(feature, str):
            if feature not in self.features:
                logger.warning(
                    "Feature " + feature + " not found in expression object!"
                )
                return None
            feature = self.features.get_by_id(feature)
        return feature.get_value(condition)

    def build_reaction_expression(self, model, default: Optional[float] = None) -> 'MSExpression':
        """Build reaction-level expression from gene-level expression using GPR rules.

        Args:
            model: COBRApy Model object
            default: Default value for missing genes

        Returns:
            MSExpression object with reaction-level expression data
        """
        # Creating the expression and features
        rxnexpression = MSExpression(self.type)
        rxnexpression.object = model
        for rxn in model.reactions:
            if len(rxn.genes) > 0:
                rxnexpression.add_feature(rxn.id)
        for condition in self.conditions:
            newcondition = MSCondition(condition.id, rxnexpression)
            rxnexpression.conditions.append(newcondition)

        # Pulling the gene values from the current expression using DataFrame
        values = {}
        for gene in model.genes:
            feature = self.object.search_for_gene(gene.id)
            if feature is None:
                logger.debug(
                    "Model gene " + gene.id + " not found in genome or expression"
                )
            elif feature.id not in self.features:
                logger.debug(
                    "Model gene " + gene.id + " in genome but not in expression"
                )
            else:
                feature = self.features.get_by_id(feature.id)
                for condition in self.conditions:
                    if condition.id not in values:
                        values[condition.id] = {}
                    # Get value from DataFrame instead of feature.values dictionary
                    if feature.id in self._data.index and condition.id in self._data.columns:
                        value = self._data.loc[feature.id, condition.id]
                        if not pd.isna(value):
                            values[condition.id][gene.id] = value

        # Computing the reaction level values
        for condition in rxnexpression.conditions:
            for feature in rxnexpression.features:
                tree = GPR().from_string(str(feature.feature.gene_reaction_rule))
                feature.add_value(
                    condition, compute_gene_score(tree, values[condition.id], default)
                )
        return rxnexpression
    
    def get_dataframe(self, reset_index: bool = False) -> pd.DataFrame:
        """Get a DataFrame with expression data.

        Args:
            reset_index: If True, move feature_id from index to column (default: False)

        Returns:
            DataFrame with feature IDs as index (or column if reset_index=True)
            and conditions as columns
        """
        if reset_index:
            return self._data.reset_index()
        else:
            return self._data.copy()
    
    def translate_data(self, target_type: str) -> 'MSExpression':
        """Translate expression data to a different type.

        Args:
            target_type: Target expression type (RelativeAbundance, AbsoluteAbundance, FPKM, TPM, Log2)

        Returns:
            New MSExpression object with translated data
        """
        # Create a copy of the current expression object
        new_expression = MSExpression.from_msexpression(self)
        new_expression.type = target_type
        # Perform translation based on source and target types
        for condition in self.conditions:
            for feature in self.features:
                value = feature.get_value(condition)
                if value is not None:
                    if self.type == "AbsoluteAbundance":
                        if target_type == "RelativeAbundance":
                            value = value / condition.sum_value()
                        elif target_type == "NormalizedRatios":
                            value = value / condition.highest_value()
                        else:
                            raise ValueError(
                                f"Translation from {self.type} to {target_type} not supported"
                            )
                    else:
                        raise ValueError(
                            f"Translation from {self.type} to {target_type} not supported"
                        )
                    new_expression._data.loc[feature.id, condition.id] = value
        return new_expression
    
    def fit_model_flux_to_data(
        self,
        model: 'MSModelUtil',
        condition: str,
        default_coef: float = 0.00001,
        activation_threshold: float = None,  # cshenry 10/16/2026: Changed default for activation to None so activation will be off by default
        deactivation_threshold: float = 0.000001,
        on_coef_override: float = None,
        off_coef_override: float = None
    ) -> Solution:
        """Fit metabolic model fluxes to expression data using threshold-based constraints.

        This function integrates gene or reaction expression data with a metabolic model
        to predict fluxes that are consistent with observed expression patterns. Reactions
        with high expression are encouraged (activated), while reactions with low expression
        are discouraged (deactivated).

        The function automatically handles:
        - Conversion from gene-level to reaction-level expression (if needed)
        - Transformation of expression data types to RelativeAbundance
        - Construction of activation/deactivation dictionaries
        - Integration with ExpressionActivationPkg for constrained optimization

        Parameters
        ----------
        model : MSModelUtil
            The metabolic model to fit to expression data. Must contain the same reactions
            as the expression model (if expression is already at reaction level).
        condition : str
            The condition ID whose expression values will be used for fitting. Must exist
            in the expression data conditions.
        activation_threshold : float, optional
            Minimum relative abundance value for a reaction to be considered "active".
            Reactions with expression above this threshold will be encouraged in the
            optimization. Default: 0.002 (0.2% relative abundance).
        deactivation_threshold : float, optional
            Maximum relative abundance value for a reaction to be considered "inactive".
            Reactions with expression below this threshold will be discouraged in the
            optimization. Default: 0.000001 (0.0001% relative abundance).

        Returns
        -------
        cobra.Solution
            The optimized FBA solution with expression-based flux constraints. Contains:
            - objective_value: The optimized objective value
            - fluxes: pandas Series of reaction fluxes
            - status: Optimization status ('optimal', 'infeasible', etc.)

        Raises
        ------
        ValueError
            If the expression model does not match the input model (when expression is
            already at reaction level).
        ValueError
            If the specified condition does not exist in the expression data.
        ValueError
            If activation_threshold is less than or equal to deactivation_threshold.
        ValueError
            If no reactions have expression values above the activation threshold.
        RuntimeError
            If the optimization fails or produces an infeasible solution.

        Notes
        -----
        - This function does NOT modify the original expression data or model
        - All model modifications occur within a context manager and are reverted
        - Reactions without expression data or reactions between the specified thresholds are deactivated base on the default_coef argument
        - The function uses ExpressionActivationPkg internally for constraint building

        See Also
        --------
        MSExpression.build_reaction_expression : Convert gene to reaction expression
        ExpressionActivationPkg.build_package : Build expression-based constraints
        MSModelUtil.test_single_condition : Run FBA on a single condition

        References
        ----------
        .. [1] Becker, S. A., & Palsson, B. O. (2008). Context-specific metabolic networks
           are consistent with experiments. PLoS computational biology, 4(5), e1000082.
        """
        # cshenry 10/16/2026: Checking that model is MSModelUtil and converting if not
        if not isinstance(model, MSModelUtil):
            model = MSModelUtil(model)
        
        # Task 1.6: Initial logging
        logger.info(f"Fitting model flux to expression data for condition: {condition}")

        # Task 1.4: Threshold validation
        if activation_threshold is not None and activation_threshold <= deactivation_threshold:
            raise ValueError(
                f"activation_threshold ({activation_threshold}) must be greater than "
                f"deactivation_threshold ({deactivation_threshold})"
            )

        # Task 1.5: Condition validation
        if condition not in self.conditions:
            available_conditions = [c.id for c in self.conditions]
            raise ValueError(
                f"Condition '{condition}' not found in expression data. "
                f"Available conditions: {available_conditions}"
            )

        # Task 2.1-2.4: Genome vs model detection and conversion
        if isinstance(self.object, MSGenome):
            # Task 2.2: Genome-level expression - convert to reaction-level
            rxn_expression = self.build_reaction_expression(model.model)
        else:
            # Task 2.3: Model-level expression - validate model match
            expr_rxns = set(self.object.reactions.list_attr('id'))
            model_rxns = set(model.model.reactions.list_attr('id'))

            if expr_rxns != model_rxns:
                # Task 2.4: Model mismatch error
                missing_in_expr = list(model_rxns - expr_rxns)[:10]
                missing_in_model = list(expr_rxns - model_rxns)[:10]
                raise ValueError(
                    f"Models must match when fitting flux to data. "
                    f"Expression model has {len(expr_rxns)} reactions, "
                    f"input model has {len(model_rxns)} reactions. "
                    f"Missing in expression: {missing_in_expr}. "
                    f"Missing in model: {missing_in_model}"
                )

            rxn_expression = self

        # Task 2.5-2.13: Expression type transformation
        if rxn_expression.type != "RelativeAbundance" and rxn_expression.type != "NormalizedRatios":
            # Task 2.10: Log transformation
            logger.info(f"Transforming expression data from {rxn_expression.type} to RelativeAbundance")

            # Task 2.11: Warning for Log2
            if rxn_expression.type == "Log2":
                logger.warning("Converting from Log2 scale - ensure this is scientifically appropriate for your analysis")

            # Task 2.12: Create new MSExpression with RelativeAbundance type
            transformed_expr = MSExpression("RelativeAbundance")
            transformed_expr.object = rxn_expression.object

            # Copy conditions
            for cond in rxn_expression.conditions:
                new_cond = MSCondition(cond.id, transformed_expr)
                transformed_expr.conditions.append(new_cond)

            # Copy features
            for feat in rxn_expression.features:
                transformed_expr.add_feature(feat.id)

            # Transform values based on type
            cond_obj = rxn_expression.conditions.get_by_id(condition)

            for feat in rxn_expression.features:
                for cond in rxn_expression.conditions:
                    value = rxn_expression.get_value(feat.id, cond.id)
                    if value is not None:
                        # Task 2.6-2.9: Apply transformation formulas
                        if rxn_expression.type == "AbsoluteAbundance":
                            transformed_value = value / cond.sum_value()
                        elif rxn_expression.type == "FPKM":
                            transformed_value = value / cond.sum_value()
                        elif rxn_expression.type == "TPM":
                            transformed_value = value / cond.sum_value()
                        elif rxn_expression.type == "Log2":
                            ave_val = cond.average_value()
                            col_sum = cond.sum_value()
                            n_features = len(rxn_expression.features)
                            transformed_value = (2 ** (value - ave_val)) / (2 ** (col_sum - n_features * ave_val))
                        else:
                            transformed_value = value

                        transformed_expr.features.get_by_id(feat.id).add_value(cond.id, transformed_value)

            # Task 2.13: Use transformed expression
            rxn_expression = transformed_expr

        # Task 3.1: Initialize empty dictionaries
        on_hash = {}
        off_hash = {}

        # Task 3.2-3.6: Iterate through reactions and build dictionaries
        for rxn in model.model.reactions:
            # Task 3.3: Get expression value
            expr_value = rxn_expression.get_value(rxn.id, condition)

            # Task 3.4: Handle None values
            if expr_value is None:
                continue

            # Task 3.5: Check for activation
            if rxn_expression.type != "NormalizedRatios":
                if activation_threshold is not None and 1 - expr_value > activation_threshold:
                    on_hash[rxn.id] = 10 * (1 - expr_value)
                elif 1-expr_value < deactivation_threshold:
                    off_hash[rxn.id] = 10*(1 - expr_value)
            else:
                if activation_threshold is not None and expr_value > activation_threshold:
                    if activation_threshold != 0:
                        on_hash[rxn.id] = (expr_value - activation_threshold)/activation_threshold
                    else:
                        on_hash[rxn.id] = expr_value+1

                # Task 3.6: Check for deactivation
                if expr_value < deactivation_threshold:
                    if activation_threshold != 0:
                        off_hash[rxn.id] = (deactivation_threshold - expr_value)/deactivation_threshold
                    else:
                        off_hash[rxn.id] = expr_value+1

        print("On:", on_hash)
        print("Off:", off_hash)

        # Task 3.8-3.9: Log dictionary sizes
        logger.info(f"Identified {len(on_hash)} reactions for activation (above threshold {activation_threshold})")
        logger.info(f"Identified {len(off_hash)} reactions for deactivation (below threshold {deactivation_threshold})")

        # Task 4.1: Access package manager
        pkgmgr = model.pkgmgr

        # Task 4.2: Get ExpressionActivationPkg
        expr_pkg = pkgmgr.getpkg("ExpressionActivationPkg")

        # Task 4.3: Use context manager for transient modifications
        output = {"on_on":[],"on_off":[], "off_on":[], "off_off":[],"solution":None}
        with model.model:
            # Task 4.4: Build package with dictionaries
            expr_pkg.build_package(on_hash, off_hash, other_coef=default_coef, on_coeff=on_coef_override, off_coeff=off_coef_override)
            # Task 4.5: Execute optimization
            output["objective"] = model.model.objective
            output["solution"] = model.model.optimize()
            for rxn in model.model.reactions:
                if rxn.id in on_hash:
                    if abs(output["solution"].fluxes[rxn.id]) > 1e-6:
                        output["on_on"].append(rxn.id)
                    else:
                        output["on_off"].append(rxn.id)
                if rxn.id in off_hash:
                    if abs(output["solution"].fluxes[rxn.id]) > 1e-6:
                        output["off_on"].append(rxn.id)
                    else:
                        output["off_off"].append(rxn.id)

            # Task 4.6: Validate solution status
            if output["solution"].status != "optimal":
                raise RuntimeError(
                    f"Optimization failed with status: {output['solution'].status}. "
                    f"The model may be infeasible with the given expression constraints."
                )

            # Task 4.7: Log optimization result
            logger.info(f"Optimization completed with objective value: {output['solution'].objective_value}")

        # Task 4.8: Return solution
        return output
