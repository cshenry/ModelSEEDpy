# -*- coding: utf-8 -*-

from __future__ import absolute_import
import logging
from modelseedpy.fbapkg.basefbapkg import BaseFBAPkg
from optlang.symbolics import Zero


# Base class for FBA packages
class SimpleThermoPkg(BaseFBAPkg):
    def __init__(self, model):
        BaseFBAPkg.__init__(
            self,
            model,
            "simple thermo",
            {"potential": "metabolite", "dgbinF": "reaction", "dgbinR": "reaction"},
            {"thermo": "reaction"},
        )
        self.pkgmgr.addpkgs(["RevBinPkg"])

    def build_package(self, parameters):
        self.validate_parameters(
            parameters,
            [],
            {
                "filter": None,
                "min_potential": 0,
                "max_potential": 1000,
                "dgbin": False,
                "reduced_constraints": False,
            },
        )
        self.pkgmgr.getpkg("RevBinPkg").build_package(self.parameters["filter"])
        for metabolite in self.model.metabolites:
            self.build_variable(metabolite)
        for reaction in self.model.reactions:
            if reaction.id[:3] not in ["EX_", "SK_", "DM_"]:
                # determine the range of Delta_rG values
                objective_coefficient = {}
                for metabolite in reaction.metabolites:
                    objective_coefficient[
                        self.variables["potential"][metabolite.id]
                    ] = reaction.metabolites[metabolite]

                # define the minimum and maximum progressions
                self.modelutl.add_objective(Zero, "min", objective_coefficient)
                min_value = self.modelutl.model.slim_optimize()
                self.modelutl.add_objective(Zero, "max", objective_coefficient)
                max_value = self.modelutl.model.slim_optimize()

                # build constraints for the filtered reactions
                if (
                    self.parameters["filter"] is None
                    or reaction.id in self.parameters["filter"]
                ):
                    self.build_constraint(reaction, min_value, max_value)

        if self.parameters["dgbin"]:
            # define the model objective as the sum of the dgbin variables
            self.optimize_dgbin()

    def build_variable(self, obj):
        return BaseFBAPkg.build_variable(
            self,
            "potential",
            self.parameters["min_potential"],
            self.parameters["max_potential"],
            "continuous",
            obj,
        )

    def build_constraint(self, obj, min_energy, max_energy):
        # Gibbs: dg = Sum(n_(i,j)*\Delta G_(j))
        # 0 <= max_abs_energy*revbin(i) - |min_energy|*dgbinR + max_energy*dgbinF + dg <= max_abs_energy

        coef = {
            self.variables["potential"][metabolite.id]: obj.metabolites[metabolite]
            for metabolite in obj.metabolites
        }
        max_abs_energy = max([abs(min_energy), abs(max_energy)])
        built_constraint = None
        if not self.parameters["reduced_constraints"]:
            coef[self.pkgmgr.getpkg("RevBinPkg").variables["revbin"][obj.id]] = (
                max_abs_energy
            )
            if self.parameters["dgbin"]:
                # build the dgbin variables
                BaseFBAPkg.build_variable(self, "dgbinF", 0, 1, "binary", obj)
                BaseFBAPkg.build_variable(self, "dgbinR", 0, 1, "binary", obj)
                # define the dgbin coefficients
                coef[self.variables["dgbinF"][obj.id]] = max_energy
                coef[self.variables["dgbinR"][obj.id]] = abs(min_energy)
            # build the constraint
            built_constraint = BaseFBAPkg.build_constraint(
                self, "thermo", 0, max_abs_energy, coef, obj
            )

        return built_constraint

    def optimize_dgbin(self):
        dgbin_vars = [
            self.variables["dgbinF"][reaction] for reaction in self.variables["dgbinF"]
        ] + [
            self.variables["dgbinR"][reaction] for reaction in self.variables["dgbinR"]
        ]
        self.modelutl.add_objective(dgbin_vars, "max")
