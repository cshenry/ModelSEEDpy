# -*- coding: utf-8 -*-

from __future__ import absolute_import

import logging
from modelseedpy.fbapkg.basefbapkg import BaseFBAPkg
from modelseedpy.core.fbahelper import FBAHelper


# Base class for FBA packages
class CommKineticPkg(BaseFBAPkg):
    def __init__(self, model):
        BaseFBAPkg.__init__(
            self, model, "community kinetics", {}, {"commkin": "string"}
        )

    def build_package(self, kinetic_coef, community_model):
        self.validate_parameters(
            {}, [], {"kinetic_coef": kinetic_coef, "community": community_model}
        )
        for member in self.parameters["community"].members:
            self.build_constraint(member)

    def build_constraint(self, member):
        bioRXN = member.primary_biomass
        coef = {
            bioRXN.forward_variable: -self.parameters["kinetic_coef"],
            bioRXN.reverse_variable: self.parameters["kinetic_coef"],
        }
        for reaction in member.reactions:
            if (
                int(FBAHelper.rxn_compartment(reaction)[1:]) == member.index
                and reaction != bioRXN
            ):
                coef[reaction.forward_variable] = coef[reaction.reverse_variable] = 1
        return BaseFBAPkg.build_constraint(
            self, "commkin", None, 0, coef, "Species" + str(member.index)
        )
