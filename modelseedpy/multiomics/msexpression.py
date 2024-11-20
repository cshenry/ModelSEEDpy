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
        self.column_sum = None
        self.feature_count = None
        self.lowest = None
        self.parent = parent
    
    def value_at_zscore(self,zscore,normalization=None):
        array = []
        for feature in self.parent.features:
            value  = feature.get_value(self,normalization)
            if value != None:
                array.append(value)
        mean = sum(array) / len(array)
        std_dev = (sum([(x - mean) ** 2 for x in array]) / len(array)) ** 0.5
        return mean + (zscore * std_dev)

class MSExpressionFeature:
    def __init__(self, feature, parent):
        self.id = feature.id
        self.feature = feature
        self.values = {}
        self.parent = parent

    def add_value(self, condition, value,collision_policy="add"):#Could also choose overwrit
        if condition in self.values:
            if self.values[condition] != None:
                condition.column_sum += -1 * self.values[condition]
            if collision_policy == "add":
                if self.values[condition] == None:
                    if value != None:
                        self.values[condition] = value
                elif value != None:
                    self.values[condition] += value
            else:
                self.values[condition] = self.values[condition]
            logger.warning(
                collision_policy+" value "
                + str(self.values[condition])
                + " to "
                + str(value)
                + " in feature "
                + self.feature.id) 
        else:
            condition.feature_count += 1
            self.values[condition] = value
        if self.values[condition] != None:
            condition.column_sum += self.values[condition]
            if condition.lowest is None or condition.lowest > self.values[condition]:
                condition.lowest = self.values[condition]

    def get_value(self, condition, normalization=None):
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
        if normalization == "column_norm" and self.values[condition] != None:
            return self.values[condition] / condition.column_sum
        return self.values[condition]


class MSExpression:
    def __init__(self, type):
        self.type = type
        self.object = None
        self.features = DictList()
        self.conditions = DictList()

    @staticmethod
    def from_gene_feature_file(filename, genome=None, create_missing_features=False,ignore_columns=[],description_column=None,sep="\t"):
        expression = MSExpression("genome")
        if genome == None:
            expression.object = MSGenome()
            create_missing_features = True
        else:
            expression.object = genome
        data = ""
        with open(filename, "r") as file:
            data = file.read()
        lines = data.split("\n")
        conditions = None
        description_index = None
        cond_indeces = []
        for line in lines:
            if conditions == None:
                conditions = []
                headers = line.split("\t")
                for i in range(1, len(headers)):
                    if headers[i] == description_column:
                        description_index = i
                        print("Description column:",description_index)
                    elif headers[i] not in ignore_columns:
                        conditions.append(headers[i])
                        cond_indeces.append(i)
                        if headers[i] not in expression.conditions:
                            expression.conditions.append(MSCondition(headers[i],expression))
                        else:
                            conditions.append(self.conditions.get_by_id(headers[i])) 
                        expression.conditions.get_by_id(headers[i]).column_sum = 0
                        expression.conditions.get_by_id(headers[i]).feature_count = 0 
            else:
                array = line.split("\t")
                description = None
                if description_index != None:
                    description = array[description_index]
                protfeature = expression.add_feature(array[0], create_missing_features,description=description)
                if protfeature != None:
                    for cond_index in cond_indeces:
                        protfeature.add_value(expression.conditions.get_by_id(headers[cond_index]), float(array[cond_index]))
        return expression

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

    def get_value(self, feature, condition, normalization=None):
        if isinstance(feature, str):
            if feature not in self.features:
                logger.warning(
                    "Feature " + feature + " not found in expression object!"
                )
                return None
            feature = self.features.get_by_id(feature)
        return feature.get_value(condition, normalization)

    def build_reaction_expression(self, model, default):
        if self.type == "model":
            logger.critical(
                "Cannot build a reaction expression from a model-based expression object!"
            )
        # Creating the expression and features
        rxnexpression = MSExpression("model")
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
    
    def get_dataframe(self, normalization=None):
        records = []
        for feature in self.features:
            record = {"ftr_id":feature.id}
            for condition in self.conditions:
                record[condition.id] = feature.get_value(condition, normalization)
            records.append(record)
        return pd.DataFrame.from_records(records)
