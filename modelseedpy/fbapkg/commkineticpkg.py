# -*- coding: utf-8 -*-

from __future__ import absolute_import

import logging
from modelseedpy.fbapkg.basefbapkg import BaseFBAPkg
from modelseedpy.core.fbahelper import FBAHelper

# Base class for FBA packages
class CommKineticPkg(BaseFBAPkg):
    def __init__(self, model):
        BaseFBAPkg.__init__(self, model, "community kinetics", {}, {"commKin": "string"})

    def build_package(self, kinetic_coef, community_model, probs={}):
        self.validate_parameters({}, [], {"kinetic_coef": kinetic_coef, "community": community_model})
        for species in self.parameters["community"].members:
            if species.id+"_commKin" in self.model.constraints:
                print(f"Removing {species.id+'_commKin'} from {self.model.id}")
                self.model.remove_cons_vars(self.model.constraints[species.id+"_commKin"])
            self.build_constraint(species, probs)

    def build_constraint(self, species, probs):
        coef = {species.primary_biomass.forward_variable: -self.parameters["kinetic_coef"],
                species.primary_biomass.reverse_variable: self.parameters["kinetic_coef"]}
        for rxn in self.model.reactions:
            rxnIndex = int(FBAHelper.rxn_compartment(rxn)[1:])
            if (rxnIndex == species.index and rxn != species.primary_biomass):
                coef[rxn.forward_variable] = coef[rxn.reverse_variable] = probs.get(rxn.id, 1)
        return BaseFBAPkg.build_constraint(self, "commKin", None, 0, coef, species.id)
