# -*- coding: utf-8 -*-

from __future__ import absolute_import
from modelseedpy.fbapkg.basefbapkg import BaseFBAPkg
import logging


class ElementUptakePkg(BaseFBAPkg):
    def __init__(self, model):
        BaseFBAPkg.__init__(
            self,
            model,
            "element uptake",
            {"elements": "string"},
            {"elements": "string"},
        )

    def build_package_simple(self, element_limits):
        for element, limit in element_limits.items():
            if element in self.variables["elements"]:
                continue
            # define the variable
            self.build_variable("elements", 0, limit, "continuous", element)
            # define the constraint
            coef = {self.variables["elements"][element]: -1}
            for exRXN in self.modelutl.exchange_list():
                ExNumAtoms = sum(
                    [
                        met.elements[element] * exRXN.metabolites[met]
                        for met in exRXN.metabolites
                        if element in met.elements
                    ]
                )
                if ExNumAtoms < 0:
                    coef[exRXN.reverse_variable] = abs(ExNumAtoms)
                elif ExNumAtoms > 0:
                    coef[exRXN.forward_variable] = ExNumAtoms
            self.build_constraint("elements", 0, 0, coef, element)

    def build_package(
        self, element_limits, exception_compounds=[], exception_reactions=[]
    ):
        # Converting exception compounds list into exception reaction list
        self.parameters = {
            "element_limits": element_limits,
            "exception_compounds": exception_compounds,
            "exception_reactions": exception_reactions,
        }
        exchange_hash = self.modelutl.exchange_hash()
        for met in exception_compounds:
            if met in exchange_hash:
                exception_reactions.append(exchange_hash[met])
        # Now building or rebuilding constraints
        for element in element_limits:
            if element not in self.variables["elements"]:
                self.build_variable(element, element_limits[element])
        for element in element_limits:
            # This call will first remove existing constraints then build the new constraint
            self.build_constraint(element, exception_reactions)

    def build_variable(self, element, limit):
        return BaseFBAPkg.build_variable(
            self, "elements", 0, limit, "continuous", element
        )

    def build_constraint(self, element, exception_reactions):
        coef = {self.variables["elements"][element]: -1}
        rxnlist = self.modelutl.exchange_list()
        for reaction in rxnlist:
            if reaction not in exception_reactions:
                total = 0
                for metabolite in reaction.metabolites:
                    elements = metabolite.elements
                    if element in elements:
                        total += elements[element] * reaction.metabolites[metabolite]
                if total < 0:
                    coef[reaction.reverse_variable] = -1 * total
                elif total > 0:
                    coef[reaction.forward_variable] = total
        return BaseFBAPkg.build_constraint(self, "elements", 0, 0, coef, element)
