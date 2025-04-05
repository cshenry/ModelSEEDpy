# -*- coding: utf-8 -*-

from __future__ import absolute_import

import logging
from optlang.symbolics import Zero, add
from modelseedpy.fbapkg.basefbapkg import BaseFBAPkg

logger = logging.getLogger(__name__)
logger.setLevel(
    logging.WARNING#INFO
)  # When debugging - set this to INFO then change needed messages below from DEBUG to INFO

# Base class for FBA packages
class ObjectivePkg(BaseFBAPkg):
    def __init__(self, model):
        BaseFBAPkg.__init__(self, model, "objective builder", {}, {})
        self.objective_cache = {}
        self.objective_string_cache = {}

    def build_package(self,objective_string,objective_name=None,cache_current_objective_name=None):
        #Saving unmodified objective string
        if objective_name == None:
            objective_name = objective_string
        #Caching objective and objective string
        self.objective_string_cache[objective_name] = objective_string
        #Caching the current objective if a name was specified
        if cache_current_objective_name != None:
            self.objective_cache[cache_current_objective_name] = self.model.objective
        #Creating empty objective - always max
        self.objective_cache[objective_name] = self.model.problem.Objective(Zero, direction="max")
        #Parsing objective string of form: MAX{(1)bio1|(1)rxn00001_c0}
        obj_coef = dict()
        #Checking if there is a directionality in the objective
        sign = 1
        if objective_string[0:3] == "MAX":
            objective_string = objective_string[4:-1]#Clearing out the directionality MAX{}
        elif objective_string[0:3] == "MIN":
            sign = -1
            objective_string = objective_string[4:-1]#Clearing out the directionality MIN{}
        #Building dictionary of variable names
        varnames = {}
        for variable in self.model.solver.variables:
            varnames[variable.name] = variable
        #Parsing the main body of the objective string
        terms = objective_string.split("|")
        for term in terms:
            coef = 1
            #Checking for coefficient
            if term[0:1] == "(":
                array = term.split(")")
                coef = float(array[0][1])
                term = array[1]
            #Applying the directionality sign
            coef = coef*sign
            #Checking for a +/- on term
            if term[0:1] == "+" or term[0:1] == "-":
                rxnid = term[1:]
                if rxnid not in self.model.reactions:
                    logger.warning(rxnid+" in objective strin not found in model.")
                else:
                    rxnobj = self.model.reactions.get_by_id(rxnid)
                    if term[0:1] == "+":
                        obj_coef[rxnobj.forward_variable] = coef
                    elif term[0:1] == "-":
                        obj_coef[rxnobj.reverse_variable] = coef
            #Checking if the term is just a reaction ID
            elif term in self.model.reactions:
                rxnobj = self.model.reactions.get_by_id(term)
                obj_coef[rxnobj.forward_variable] = coef
                obj_coef[rxnobj.reverse_variable] = -1*coef
            elif term in varnames:
                obj_coef[varnames[term]] = coef
        self.model.objective = self.objective_cache[objective_name]
        self.model.objective.set_linear_coefficients(obj_coef)
        print(self.model.objective)
    
    def restore_objective(self,name):
        if name in self.objective_cache:
            self.model.objective = self.objective_cache[name]
        else:
            logger.warning("Objective "+name+" not found in cache")