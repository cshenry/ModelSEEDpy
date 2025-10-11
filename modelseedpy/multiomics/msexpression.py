# -*- coding: utf-8 -*-
import logging

import pandas as pd
import re
import copy
from cobra.core.dictlist import DictList
from cobra.core.gene import Gene, ast2str, eval_gpr, parse_gpr, GPR
from ast import And, BitAnd, BitOr, BoolOp, Expression, Name, NodeTransformer, Or
from modelseedpy.core.msgenome import MSGenome, MSFeature

logger = logging.getLogger(__name__)

def compute_gene_score(expr, values, default):
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
    def __init__(self, id,parent):
        self.id = id
        self.parent = parent
    
    def value_at_zscore(self,zscore):
        array = []
        for feature in self.parent.features:
            value  = feature.get_value(self)
            if value != None:
                array.append(value)
        mean = sum(array) / len(array)
        std_dev = (sum([(x - mean) ** 2 for x in array]) / len(array)) ** 0.5
        return mean + (zscore * std_dev)
    
    def lowest_value(self):
        lowest = None
        for feature in self.parent.features:
            value  = feature.get_value(self)
            if value != None:
                if lowest == None or value < lowest:
                    lowest = value
        return lowest

    def highest_value(self):
        highest = None
        for feature in self.parent.features:
            value  = feature.get_value(self)
            if value != None:
                if highest == None or value > highest:
                    highest = value
        return highest
    
    def average_value(self):
        array = []
        for feature in self.parent.features:
            value  = feature.get_value(self)
            if value != None:
                array.append(value)
        if len(array) == 0:
            return None
        return sum(array) / len(array)
    
    def sum_value(self):
        total = 0
        for feature in self.parent.features:
            value  = feature.get_value(self)
            if value != None:
                total += value
        return total

class MSExpressionFeature:
    def __init__(self, feature, parent):
        self.id = feature.id
        self.feature = feature
        self.values = {}
        self.parent = parent

    def add_value(self, condition, value):
        self.values[condition] = value

    def get_value(self, condition, convert_to_relative_abundance=False):
        if isinstance(condition, str):
            if condition not in self.parent.conditions:
                logger.warning(
                    "Condition " + condition + " not found in expression object!"
                )
                return None
            condition = self.parent.conditions.get_by_id(condition)
        if condition not in self.values:
            logger.info(
                "Condition " + condition.id + " has no value in " + self.feature.id
            )
            return None
        value = self.values[condition]
        if convert_to_relative_abundance:
            if self.parent.type == "AbsoluteAbundance":
                value = value / condition.column_sum
            elif self.parent.type == "FPKM":
                value = value / condition.column_sum
            elif self.parent.type == "TPM":
                value = value / condition.column_sum
            elif self.parent.type == "Log2":
                value = 2 ** (value - condition.lowest_value()) / 2 ** (condition.column_sum - self.parent.features.len() * condition.lowest_value())
        return self.values[condition]

class MSExpression:
    def __init__(self, type):
        self.type = type#RelativeAbundance,AbsoluteAbundance,FPKM,TPM,Log2
        self.object = None
        self.features = DictList()
        self.conditions = DictList()

    @staticmethod
    def from_dataframe(df, genome=None, create_missing_features=False,ignore_columns=[],description_column=None,id_column=None,type="RelativeAbundance"):
        expression = MSExpression(type)
        if genome == None:
            expression.object = MSGenome()
            create_missing_features = True
        else:
            expression.object = genome
        conditions = []
        description_present = False
        headers = list(df.columns)
        if id_column is None:
            id_column = headers[0]
        for i in range(1, len(headers)):
            if headers[i] == description_column:
                description_present = True
            elif headers[i] not in ignore_columns:
                conditions.append(headers[i])
                if headers[i] not in expression.conditions:
                    expression.conditions.append(MSCondition(headers[i],expression))
                expression.conditions.get_by_id(headers[i]).column_sum = 0
                expression.conditions.get_by_id(headers[i]).feature_count = 0 
        for index, row in df.iterrows():
            description = None
            if description_present:
                description = row[description_column]
            protfeature = expression.add_feature(row[id_column], create_missing_features,description=description)
            if protfeature != None:
                for condition in conditions:
                    protfeature.add_value(expression.conditions.get_by_id(condition), float(row[condition]))
        return expression
    
    def from_spreadsheet(filename, sheet_name=0, skiprows=0, genome=None, create_missing_features=False,ignore_columns=[],description_column=None,id_column=None,type="RelativeAbundance"):
        df = pd.read_excel(filename, sheet_name=sheet_name, skiprows=skiprows)
        return MSExpression.from_dataframe(df, genome=genome, create_missing_features=create_missing_features, ignore_columns=ignore_columns, description_column=description_column, id_column=id_column)

    def from_gene_feature_file(filename, genome=None, create_missing_features=False,ignore_columns=[],description_column=None,sep="\t",id_column=None,type="RelativeAbundance"):
        df = pd.read_csv(filename, sep=sep)
        return MSExpression.from_dataframe(df, genome=genome, create_missing_features=create_missing_features, ignore_columns=ignore_columns, description_column=description_column, id_column=id_column)

    def add_feature(self, id, create_gene_if_missing=False,description=None):
        if id in self.features:
            return self.features.get_by_id(id)
        feature = None
        if self.type == "genome":
            if self.object.search_for_gene(id) == None:
                if create_gene_if_missing:
                    self.object.features.append(MSFeature(id, ""))
            feature = self.object.search_for_gene(id)
        else:
            if id in self.object.reactions:
                feature = self.object.reactions.get_by_id(id)
        if feature == None:
            logger.warning(
                "Feature referred by expression " + id + " not found in genome object!"
            )
            return None
        if feature.id in self.features:
            return self.features.get_by_id(feature.id)
        protfeature = MSExpressionFeature(feature, self)
        self.features.append(protfeature)
        return protfeature

    def get_value(self, feature, condition):
        if isinstance(feature, str):
            if feature not in self.features:
                logger.warning(
                    "Feature " + feature + " not found in expression object!"
                )
                return None
            feature = self.features.get_by_id(feature)
        return feature.get_value(condition)

    def build_reaction_expression(self, model, default):
        # Creating the expression and features
        rxnexpression = MSExpression(self.type)
        rxnexpression.object = model
        for rxn in model.reactions:
            if len(rxn.genes) > 0:
                rxnexpression.add_feature(rxn.id)
        for condition in self.conditions:
            newcondition = MSCondition(condition.id,rxnexpression)
            rxnexpression.conditions.append(condition)
        # Pulling the gene values from the current expression
        values = {}
        for gene in model.genes:
            feature = self.object.search_for_gene(gene.id)
            if feature == None:
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
                    if condition in feature.values:
                        values[condition.id][gene.id] = feature.values[condition]
        # Computing the reaction level values
        for condition in rxnexpression.conditions:
            for feature in rxnexpression.features:
                tree = GPR().from_string(str(feature.feature.gene_reaction_rule))
                feature.add_value(
                    condition, compute_gene_score(tree, values[condition.id], default)
                )
        return rxnexpression
    
    def get_dataframe(self):
        records = []
        for feature in self.features:
            record = {"ftr_id":feature.id}
            for condition in self.conditions:
                record[condition.id] = feature.get_value(condition)
            records.append(record)
        return pd.DataFrame.from_records(records)
