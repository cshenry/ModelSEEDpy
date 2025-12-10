# -*- coding: utf-8 -*-
import logging
from typing import Optional, Union, TYPE_CHECKING

#from numpy._core.numeric import True_
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

def compute_gene_score(expr, values, default, datatype):
    # Handle tuple return from parse_gpr() in newer COBRApy versions
    if isinstance(expr, tuple) and len(expr) == 2:
        expr = expr[0]  # Extract GPR object from (GPR, frozenset) tuple

    if isinstance(expr, (Expression, GPR)):
        return compute_gene_score(expr.body, values, default, datatype)
    elif isinstance(expr, Name):
        if expr.id in values:
            return values[expr.id]
        else:
            return default
    elif isinstance(expr, BoolOp):
        op = expr.op
        if isinstance(op, Or):
            best = None
            total = None
            for subexpr in expr.values:
                value = compute_gene_score(subexpr, values, default, datatype)
                if value != None:
                    if datatype == "NormalizedRatios":
                        diff = abs(value - 1)
                        if best == None or diff > best:
                            best = diff
                            total = value
                    elif datatype == "RelativeAbundance" or datatype == "FPKM" or datatype == "TPM" or datatype == "AbsoluteAbundance":
                        if total == None:
                            total = 0
                        total += value
            return total
        elif isinstance(op, And):
            best = None
            best_value = None
            for subexpr in expr.values:
                value = compute_gene_score(subexpr, values, default, datatype)
                if value != None:
                    if datatype == "NormalizedRatios":
                        diff = abs(value - 1)
                        if best == None or diff > best:
                            best = diff
                            best_value = value
                    elif datatype == "RelativeAbundance" or datatype == "FPKM" or datatype == "TPM" or datatype == "AbsoluteAbundance":
                        if best == None or value < best:
                            best = value
                            best_value = value
            return best_value
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
        genome_or_model: Union['MSGenome', 'Model'],
        create_missing_features: bool = False,
        ignore_columns: list = None,
        description_column: Optional[str] = None,
        id_column: Optional[str] = None,
        id_translation: Optional[dict] = None,
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
        if genome_or_model is None:
            expression.object = MSGenome()
            create_missing_features = True
        else:
            expression.object = genome_or_model

        # Identify columns
        headers = list(df.columns)
        if id_column is None:
            id_column = headers[0]
        print(id_column)
        print(headers)

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
            gene_id = row[id_column]
            if id_translation is not None and gene_id in id_translation:
                gene_id = id_translation[gene_id]
            description = None
            if description_present:
                description = row[description_column]
            protfeature = expression.add_feature(
                gene_id, create_missing_features, description=description
            )
            if protfeature is not None:
                valid_feature_ids.append(protfeature.id)

        # Bulk load data into DataFrame
        if len(valid_feature_ids) > 0 and len(conditions) > 0:
            # Apply ID translation to the dataframe's ID column if provided
            if id_translation is not None:
                # Create a translated version of the ID column for filtering and indexing
                df_translated = df.copy()
                df_translated['_translated_id'] = df_translated[id_column].map(
                    lambda x: id_translation.get(x, x)
                )
                # Filter using translated IDs
                data_df = df_translated[df_translated['_translated_id'].isin(valid_feature_ids)].copy()
                # Set index using translated IDs
                data_df = data_df.set_index('_translated_id')
            else:
                # Extract numeric data columns without translation
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
        genome_or_model: Union['MSGenome', 'Model'] = None,
        create_missing_features: bool = True,
        id_translation: Optional[dict] = None,
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
            genome_or_model=genome_or_model,
            create_missing_features=create_missing_features,
            ignore_columns=ignore_columns,
            description_column=description_column,
            id_column=id_column,
            id_translation=id_translation,
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

    @staticmethod
    def load_from_dict(
        data_dict: dict,
        genome_or_model: Union['MSGenome', 'Model'],
        value_type: str,
        create_missing_features: bool = False
    ) -> 'MSExpression':
        """Create an MSExpression object from a dictionary.

        The dictionary should have feature IDs as keys and nested dictionaries
        mapping condition IDs to expression values as values.

        Example:
            data = {
                "gene1": {
                    "condition1": 10.5,
                    "condition2": 20.3
                },
                "gene2": {
                    "condition1": 8.2,
                    "condition2": 15.7
                }
            }
            expr = MSExpression.load_from_dict(
                data,
                genome_or_model=genome,
                value_type="Log2"
            )

        Args:
            data_dict: Dictionary with feature IDs as keys and condition-value
                dictionaries as values
            genome_or_model: MSGenome object (for gene expression) or Model
                object (for reaction expression). Required.
            value_type: Expression data type (RelativeAbundance, AbsoluteAbundance,
                FPKM, TPM, Log2, NormalizedRatios). Required.
            create_missing_features: If True, create features not in genome/model

        Returns:
            MSExpression object with data loaded from dictionary
        """
        # Create expression object
        expression = MSExpression(value_type)
        expression.object = genome_or_model

        # Convert dictionary to DataFrame
        # The dictionary format is: {feature_id: {condition_id: value, ...}, ...}
        if not data_dict:
            return expression

        # Convert to DataFrame with feature IDs as index and conditions as columns
        data_df = pd.DataFrame.from_dict(data_dict, orient='index').T

        if 'Feature ID' not in data_df.columns:
            # If 'Feature ID' is the index, reset it
            data_df = data_df.reset_index()
            if 'index' in data_df.columns:
                data_df = data_df.rename(columns={'index': 'Feature ID'})

        return MSExpression.from_dataframe(
            df=data_df,
            genome_or_model=genome_or_model,
            create_missing_features=create_missing_features,
            type=value_type,
            id_column='Feature ID'
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
            elif hasattr(self.object.model, 'reactions') and id in self.object.model.reactions:
                feature = self.object.model.reactions.get_by_id(id)
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
            # First, try to find the gene directly in expression features
            # This handles cases where expression was loaded without a genome
            if gene.id in self.features:
                feature = self.features.get_by_id(gene.id)
            else:
                # Fallback: search through the genome object (supports aliases)
                feature = self.object.search_for_gene(gene.id)
                if feature is None:
                    logger.debug(
                        "Model gene " + gene.id + " not found in genome or expression"
                    )
                    continue
                if feature.id not in self.features:
                    logger.debug(
                        "Model gene " + gene.id + " in genome but not in expression"
                    )
                    continue
                feature = self.features.get_by_id(feature.id)

            # Extract expression values for this feature
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
                    condition, compute_gene_score(tree, values[condition.id], default, self.type)
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
            denominator = None
            for feature in self.features:
                value = feature.get_value(condition)
                if value is not None:
                    if self.type == "AbsoluteAbundance" or self.type == "FPKM" or self.type == "TPM":
                        if target_type == "RelativeAbundance":
                            if condition.sum_value() > 0.01:
                                transformed_value = value / condition.sum_value()
                            else:
                                transformed_value = 0
                        elif target_type == "NormalizedRatios":
                            if condition.highest_value() > 0.01:
                                transformed_value = value / condition.highest_value()
                            else:
                                transformed_value = 0
                        else:
                            raise ValueError(
                                f"Translation from {self.type} to {target_type} not supported"
                            )
                        new_expression._data.loc[feature.id, condition.id] = transformed_value
                    elif self.type == "Log2":
                        if target_type == "RelativeAbundance":
                            if denominator is None:
                                denominator = 0
                                for ftr in self.features:
                                    denominator += 2 ** ftr.get_value(condition)
                            numerator = 2 ** value
                            if denominator > 0.01:
                                transformed_value = numerator / denominator
                            else:
                                transformed_value = 0
                        else:
                            raise ValueError(
                                f"Translation from {self.type} to {target_type} not supported"
                            )                            
                        new_expression._data.loc[feature.id, condition.id] = transformed_value
                    else:
                        raise ValueError(
                            f"Translation from {self.type} to {target_type} not supported"
                        )
                    
        return new_expression

    def average_expression_replicates(self, strain_list: list) -> 'MSExpression':
        """Average expression replicates for each strain.

        Takes an MSExpression object with replicate columns (e.g., ACN2586_1, ACN2586_2, ...)
        and averages them to create single columns per strain (e.g., ACN2586).

        Args:
            strain_list: List of strain names (e.g., ["ACN2586", "ACN2821", ...])

        Returns:
            New MSExpression object with averaged data per strain

        Raises:
            ValueError: If no data found for any strain in the list
        """
        try:
            # Access the underlying DataFrame
            expression_df = self._data.copy()

            # Create new DataFrame for averaged data
            averaged_data = {}

            # Keep the index (gene/protein IDs)
            averaged_data['index'] = expression_df.index

            # For each strain, find and average its replicates
            for strain in strain_list:
                # Find columns that match this strain pattern (e.g., ACN2586_1, ACN2586_2, ...)
                replicate_cols = [col for col in expression_df.columns if col.startswith(f"{strain}_")]

                if replicate_cols:
                    # Average the replicates
                    averaged_data[strain] = expression_df[replicate_cols].mean(axis=1)
                    logger.info(f"Averaged {len(replicate_cols)} replicates for strain {strain}")
                else:
                    # No replicates found - check if strain column exists as-is
                    if strain in expression_df.columns:
                        averaged_data[strain] = expression_df[strain]
                        logger.info(f"No replicates found for {strain}, using existing column")
                    else:
                        logger.warning(f"No data found for strain {strain}")

            # Create new DataFrame from averaged data
            averaged_df = pd.DataFrame(averaged_data)
            averaged_df.set_index('index', inplace=True)

            # Create a deep copy of the expression object
            averaged_expression = copy.deepcopy(self)

            # Replace the data with averaged data
            averaged_expression._data = averaged_df

            # Update conditions list to match new columns
            # Clear and rebuild conditions using proper MSCondition class
            averaged_expression.conditions = DictList()
            for strain in strain_list:
                if strain in averaged_df.columns:
                    condition = MSCondition(strain, averaged_expression)
                    averaged_expression.conditions.append(condition)

            logger.info(f"Created averaged expression data with {len(averaged_expression.conditions)} conditions")

            return averaged_expression

        except Exception as e:
            logger.error(f"Error averaging expression replicates: {str(e)}")
            raise

    def fit_model_expression_to_data(
        self,
        model: 'MSModelUtil',
        condition: str,
        default_coef: float = 0.00001,
        activation_threshold: float = None,  # cshenry 10/16/2026: Changed default for activation to None so activation will be off by default
        deactivation_threshold: float = 0.000001,
        on_coef_override: float = None,
        off_coef_override: float = None,
        analyze_solution_essentiality: bool = False
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
        logger.info(f"Fitting model flux to expression or fitness data for condition: {condition}")

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
            expr_rxns = set(self.object.model.reactions.list_attr('id'))
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
            raise ValueError(
                f"Reaction expression must be in terms of relative abundance or normalized ratios"
            )

        # Initialize empty dictionaries
        on_hash = {}
        off_hash = {}

        # Iterate through reactions and build dictionaries
        for rxn in model.model.reactions:
            expr_value = rxn_expression.get_value(rxn.id, condition)
            if expr_value is None:
                continue
            if rxn_expression.type == "NormalizedRatios":
                if activation_threshold is not None and abs(1 - expr_value) >= activation_threshold:
                    on_hash[rxn.id] = 10 * (1 - expr_value)
                elif abs(1-expr_value) <= deactivation_threshold:
                    off_hash[rxn.id] = 10*(1 - expr_value)
            else:
                if activation_threshold is not None and expr_value > activation_threshold:
                    if activation_threshold != 0:
                        on_hash[rxn.id] = (expr_value - activation_threshold)/activation_threshold
                    else:
                        on_hash[rxn.id] = expr_value+1
                elif expr_value < deactivation_threshold:
                    if deactivation_threshold != 0:
                        off_hash[rxn.id] = (deactivation_threshold - expr_value)/deactivation_threshold
                    else:
                        off_hash[rxn.id] = expr_value+1

        print("On:", on_hash)
        print("Off:", off_hash)

        # Log dictionary sizes
        logger.info(f"Identified {len(on_hash)} reactions for activation (above threshold {activation_threshold})")
        logger.info(f"Identified {len(off_hash)} reactions for deactivation (below threshold {deactivation_threshold})")

        # Access package manager
        pkgmgr = model.pkgmgr

        # Get ExpressionActivationPkg
        expr_pkg = pkgmgr.getpkg("ExpressionActivationPkg")

        # Use context manager for transient modifications
        output = {"on_on":[],"on_off":[], "off_on":[], "off_off":[],"none_on":[],"none_off":[],"on_on_reduced":[],"off_on_reduced":[],"none_on_reduced":[],"solution":None}
        original_objective = model.model.objective
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
                elif rxn.id in off_hash:
                    if abs(output["solution"].fluxes[rxn.id]) > 1e-6:
                        output["off_on"].append(rxn.id)
                    else:
                        output["off_off"].append(rxn.id)
                else:
                    if abs(output["solution"].fluxes[rxn.id]) > 1e-6:
                        output["none_on"].append(rxn.id)
                    else:
                        output["none_off"].append(rxn.id)

            # Task 4.6: Validate solution status
            if output["solution"].status != "optimal":
                raise RuntimeError(
                    f"Optimization failed with status: {output['solution'].status}. "
                    f"The model may be infeasible with the given expression constraints."
                )

            # Task 4.7: Log optimization result
            logger.info(f"Optimization completed with objective value: {output['solution'].objective_value}")

        # Categorize reactions by flux
        zero_flux_rxns = []
        active_rxns = []
        
        for rxn_id, flux in output["solution"].fluxes.items():
            if rxn_id not in [r.id for r in model.model.reactions]:
                continue
            if abs(flux) <= 1e-9:
                zero_flux_rxns.append(rxn_id)
            else:
                active_rxns.append((rxn_id, flux))
        
        print(f"  Zero-flux reactions: {len(zero_flux_rxns)}")
        print(f"  Active reactions: {len(active_rxns)}")
        
        with model.model:
            #model.model.objective = original_objective
            # Set zero-flux reactions to have zero bounds
            for rxn_id in zero_flux_rxns:
                rxn = model.model.reactions.get_by_id(rxn_id)
                rxn.lower_bound = 0
                rxn.upper_bound = 0
            
            # Get baseline growth with constrained model
            output["baseline_growth"] = model.model.optimize().objective_value
            
            # Test each active reaction knockout
            essentiality_results = {}
            essential_count = 0
            reduced_count = 0
            
            for rxn_id, original_flux in active_rxns:
                rxn = model.model.reactions.get_by_id(rxn_id)
                
                # Save original bounds
                orig_lb = rxn.lower_bound
                orig_ub = rxn.upper_bound
                
                # Knock out the reaction
                rxn.lower_bound = 0
                rxn.upper_bound = 0
                
                # Optimize
                ko_solution = model.model.optimize()
                
                if ko_solution.status == 'optimal':
                    ko_growth = ko_solution.objective_value
                    growth_ratio = ko_growth / baseline_growth if baseline_growth > 0 else 0
                else:
                    ko_growth = 0
                    growth_ratio = 0
                
                # Categorize impact
                if growth_ratio < 0.01:
                    impact = "essential"
                    essential_count += 1
                elif growth_ratio < 0.95:
                    impact = "reduced"
                    reduced_count += 1
                else:
                    impact = "dispensable"
                
                essentiality_results[rxn_id] = {
                    "expression_data_status":"none",
                    "original_flux": original_flux,
                    "ko_growth": ko_growth,
                    "growth_ratio": growth_ratio,
                    "impact": impact
                }
                if rxn_id in on_hash:
                    essentiality_results[rxn_id]["expression_data_status"] = "on"
                    if growth_ratio < 0.95:
                        output["on_on_reduced"].append(rxn_id)
                elif rxn_id in off_hash:
                    essentiality_results[rxn_id]["expression_data_status"] = "off"
                    if growth_ratio < 0.95:
                        output["off_on_reduced"].append(rxn_id)
                else:
                    essentiality_results[rxn_id]["expression_data_status"] = "none"
                    if growth_ratio < 0.95:
                        output["none_on_reduced"].append(rxn_id)

                # Restore original bounds
                rxn.lower_bound = orig_lb
                rxn.upper_bound = orig_ub
        
        print(f"  Essential reactions: {essential_count}")
        print(f"  Reduced growth reactions: {reduced_count}")
        print(f"  Dispensable reactions: {len(active_rxns) - essential_count - reduced_count}")
        
        output["baseline_growth"] = baseline_growth
        output["zero_flux_count"] = len(zero_flux_rxns)
        output["active_count"] = len(active_rxns)
        output["essential_count"] = essential_count
        output["reduced_count"] = reduced_count
        output["reactions"] = essentiality_results

        # Task 4.8: Return solution
        return output


    def fit_flux_to_mutant_growth_rate_data(
        self,
        model: 'MSModelUtil',
        condition: str,
        default_coef: float = 0.00001,
        activation_threshold: float = 0.90,
        deactivation_threshold: float = 0.95,
        on_coef_override: float = None,
        off_coef_override: float = None
    ) -> Solution:
        """Fit metabolic model fluxes to mutant growth rate data using threshold-based constraints
        """
        if not isinstance(model, MSModelUtil):
            model = MSModelUtil(model)
        
        logger.info(f"Fitting model flux to mutant growth rate data for condition: {condition}")

        if activation_threshold >= deactivation_threshold:
            raise ValueError(
                f"activation_threshold ({activation_threshold}) must be less than "
                f"deactivation_threshold ({deactivation_threshold})"
            )

        if condition not in self.conditions:
            available_conditions = [c.id for c in self.conditions]
            raise ValueError(
                f"Condition '{condition}' not found in expression data. "
                f"Available conditions: {available_conditions}"
            )

        if self.type != "NormalizedRatios":
            raise ValueError(
                f"Expression must be in terms of normalized ratios"
            )

        # Initialize empty dictionaries
        on_hash = {}
        off_hash = {}

        # Iterate through reactions and build dictionaries
        for rxn in model.model.reactions:
            # Check if the reaction ID is in the expression data
            if rxn.id in self.features:
                expr_value = self.get_value(rxn.id, condition)
            else:
                lowest_value = None
                for gene_id in rxn.genes:
                    if gene_id in self.features:
                        expr_value = self.get_value(gene_id, condition)
                        if lowest_value is None or expr_value < lowest_value:
                            lowest_value = expr_value
                if lowest_value is None:
                    expr_value = None
                else:
                    expr_value = lowest_value
            if expr_value is None:
                continue
            if expr_value <= activation_threshold:
                on_hash[rxn.id] = 1 + 10 * (activation_threshold - expr_value)
            elif expr_value >= deactivation_threshold:
                off_hash[rxn.id] = 1 + 10 * (expr_value-deactivation_threshold)
            
        print("On:", on_hash)
        print("Off:", off_hash)

        # Log dictionary sizes
        logger.info(f"Identified {len(on_hash)} reactions for activation (above threshold {activation_threshold})")
        logger.info(f"Identified {len(off_hash)} reactions for deactivation (below threshold {deactivation_threshold})")

        # Get ExpressionActivationPkg
        expr_pkg = model.pkgmgr.getpkg("ExpressionActivationPkg")

        # Use context manager for transient modifications
        output = {"on_on":[],"on_off":[], "off_on":[], "off_off":[],"none_on":[],"none_off":[],"on_on_reduced":[],"off_on_reduced":[],"none_on_reduced":[],"solution":None}
        original_objective = model.model.objective
        with model.model:
            expr_pkg.build_package(on_hash, off_hash, other_coef=default_coef, on_coeff=on_coef_override, off_coeff=off_coef_override)
            output["solution"] = model.model.optimize()
            for rxn in model.model.reactions:
                if rxn.id in on_hash:
                    if abs(output["solution"].fluxes[rxn.id]) > 1e-6:
                        output["on_on"].append(rxn.id)
                    else:
                        output["on_off"].append(rxn.id)
                elif rxn.id in off_hash:
                    if abs(output["solution"].fluxes[rxn.id]) > 1e-6:
                        output["off_on"].append(rxn.id)
                    else:
                        output["off_off"].append(rxn.id)
                else:
                    if abs(output["solution"].fluxes[rxn.id]) > 1e-6:
                        output["none_on"].append(rxn.id)
                    else:
                        output["none_off"].append(rxn.id)

            if output["solution"].status != "optimal":
                raise RuntimeError(
                    f"Optimization failed with status: {output['solution'].status}. "
                    f"The model may be infeasible with the given expression constraints."
                )

            logger.info(f"Optimization completed with objective value: {output['solution'].objective_value}")

        # Categorize reactions by flux
        zero_flux_rxns = []
        active_rxns = []
        
        for rxn_id, flux in output["solution"].fluxes.items():
            if rxn_id not in [r.id for r in model.model.reactions]:
                continue
            if abs(flux) <= 1e-9:
                zero_flux_rxns.append(rxn_id)
            else:
                active_rxns.append((rxn_id, flux))
        
        print(f"  Zero-flux reactions: {len(zero_flux_rxns)}")
        print(f"  Active reactions: {len(active_rxns)}")
        
        with model.model:
            #model.model.objective = original_objective
            # Set zero-flux reactions to have zero bounds
            for rxn_id in zero_flux_rxns:
                rxn = model.model.reactions.get_by_id(rxn_id)
                rxn.lower_bound = 0
                rxn.upper_bound = 0
            
            # Get baseline growth with constrained model
            output["baseline_growth"] = model.model.optimize().objective_value
            
            # Test each active reaction knockout
            essentiality_results = {}
            essential_count = 0
            reduced_count = 0
            
            for rxn_id, original_flux in active_rxns:
                rxn = model.model.reactions.get_by_id(rxn_id)
                
                # Save original bounds
                orig_lb = rxn.lower_bound
                orig_ub = rxn.upper_bound
                
                # Knock out the reaction
                rxn.lower_bound = 0
                rxn.upper_bound = 0
                
                # Optimize
                ko_solution = model.model.optimize()
                
                if ko_solution.status == 'optimal':
                    ko_growth = ko_solution.objective_value
                    growth_ratio = ko_growth / baseline_growth if baseline_growth > 0 else 0
                else:
                    ko_growth = 0
                    growth_ratio = 0
                
                # Categorize impact
                if growth_ratio < 0.01:
                    impact = "essential"
                    essential_count += 1
                elif growth_ratio < 0.95:
                    impact = "reduced"
                    reduced_count += 1
                else:
                    impact = "dispensable"
                
                essentiality_results[rxn_id] = {
                    "expression_data_status":"none",
                    "original_flux": original_flux,
                    "ko_growth": ko_growth,
                    "growth_ratio": growth_ratio,
                    "impact": impact
                }
                if rxn_id in on_hash:
                    essentiality_results[rxn_id]["expression_data_status"] = "on"
                    if growth_ratio < 0.95:
                        output["on_on_reduced"].append(rxn_id)
                elif rxn_id in off_hash:
                    essentiality_results[rxn_id]["expression_data_status"] = "off"
                    if growth_ratio < 0.95:
                        output["off_on_reduced"].append(rxn_id)
                else:
                    essentiality_results[rxn_id]["expression_data_status"] = "none"
                    if growth_ratio < 0.95:
                        output["none_on_reduced"].append(rxn_id)

                # Restore original bounds
                rxn.lower_bound = orig_lb
                rxn.upper_bound = orig_ub
        
        print(f"  Essential reactions: {essential_count}")
        print(f"  Reduced growth reactions: {reduced_count}")
        print(f"  Dispensable reactions: {len(active_rxns) - essential_count - reduced_count}")
        
        output["baseline_growth"] = baseline_growth
        output["zero_flux_count"] = len(zero_flux_rxns)
        output["active_count"] = len(active_rxns)
        output["essential_count"] = essential_count
        output["reduced_count"] = reduced_count
        output["reactions"] = essentiality_results

        # Task 4.8: Return solution
        return output
