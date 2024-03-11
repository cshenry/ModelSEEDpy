# -*- coding: utf-8 -*-

from __future__ import absolute_import

import logging
import sys
import re
import json
from optlang.symbolics import Zero, add
from cobra import Model, Reaction, Metabolite
from cobra.io import (
    load_json_model,
    save_json_model,
    load_matlab_model,
    save_matlab_model,
    read_sbml_model,
    write_sbml_model,
)
from modelseedpy.fbapkg.basefbapkg import BaseFBAPkg
from modelseedpy.core.fbahelper import FBAHelper

logger = logging.getLogger(__name__)
logger.setLevel(
    logging.WARNING
)  # When debugging - set this to INFO then change needed messages below from DEBUG to INFO

base_blacklist = {}
zero_threshold = 1e-8


class GapfillingPkg(BaseFBAPkg):
    """ """

    def __init__(self, model):
        BaseFBAPkg.__init__(
            self,
            model,
            "gapfilling",
            {"rmaxf": "reaction", "fmaxf": "reaction"},
            {"rmaxfc": "reaction", "fmaxfc": "reaction"},
        )
        self.gapfilling_penalties = None
        self.maxflux_variables = {}

    def build(self, template, minimum_objective=0.01):
        parameters = {
            "default_gapfill_templates": [template],
            "gapfill_all_indecies_with_default_templates": 1,
            "minimum_obj": minimum_objective,
            "set_objective": 1,
        }
        self.build_package(parameters)

    def get_model_index_hash(self):
        """
        Determine all indices that should be gap filled
        :return:
        """
        index_hash = {"none": 0}
        for metabolite in self.model.metabolites:
            if re.search("_[a-z]\d+$", metabolite.id) is not None:
                m = re.search("_([a-z])(\d+)$", metabolite.id)
                if m[1] != "e":
                    if m[2] not in index_hash:
                        index_hash[m[2]] = 0
                    index_hash[m[2]] += 1
            else:
                index_hash["none":0]
                # Iterating over all indecies with more than 10 intracellular compounds:
        return index_hash

    def build_package(self, parameters):
        self.validate_parameters(
            parameters,
            [],
            {
                "auto_sink": ["cpd02701", "cpd11416", "cpd15302", "cpd03091"],
                "extend_with_template": 1,
                "model_penalty": 1,
                "default_gapfill_models": [],
                "default_gapfill_templates": [],
                "gapfill_templates_by_index": {},
                "gapfill_models_by_index": {},
                "reaction_scores": {},
                "gapfill_all_indecies_with_default_templates": 1,
                "gapfill_all_indecies_with_default_models": 1,
                "default_excretion": 100,
                "default_uptake": 100,
                "minimum_obj": 0.01,
                "minimize_exchanges": False,
                "blacklist": [],
            },
        )

        # Adding model reactions to original reaction list
        self.parameters["original_reactions"] = []
        for rxn in self.model.reactions:
            if FBAHelper.is_ex(rxn):
                continue
            if FBAHelper.is_biomass(rxn):
                continue
            if rxn.lower_bound < 0:
                self.parameters["original_reactions"].append([rxn, "<"])
            if rxn.upper_bound > 0:
                self.parameters["original_reactions"].append([rxn, ">"])

        # Adding constraint for target reaction
        self.parameters["origobj"] = self.model.objective
        self.pkgmgr.getpkg("ObjConstPkg").build_package(
            self.parameters["minimum_obj"], None
        )

        # Computing gapfilling penalties
        self.compute_gapfilling_penalties()

        # Creating the gapfilling objective function and saving it under self.parameters["gfobj"]
        self.build_gapfilling_objective_function()

    def compute_gapfilling_penalties(
        self, exclusion_solution=None, reaction_scores=None
    ):
        """Builds gapfilling objective function for model
        Parameters
        ----------
        exclusion_solution : [string rxn_id,string direction]
            Solution with reaction directions that should be removed from the gapfilling objective function
        """
        # Determine all indecies that should be gapfilled
        indexhash = self.get_model_index_hash()
        # Iterating over all indecies with more than 10 intracellular compounds:
        self.gapfilling_penalties = dict()
        for index, val in indexhash.items():
            if val > 10:
                if index == "none":
                    for template in self.parameters["default_gapfill_templates"]:
                        self.gapfilling_penalties.update(
                            self.extend_model_with_template_for_gapfilling(
                                template, index
                            )
                        )
                    for gfmdl in self.parameters["default_gapfill_models"]:
                        self.gapfilling_penalties.update(
                            self.extend_model_with_model_for_gapfilling(gfmdl, index)
                        )
                if index in self.parameters["gapfill_templates_by_index"]:
                    for template in self.parameters["gapfill_templates_by_index"][
                        index
                    ]:
                        self.gapfilling_penalties.update(
                            self.extend_model_with_template_for_gapfilling(
                                template, index
                            )
                        )
                if index in self.parameters["gapfill_models_by_index"]:
                    for gfmdl in self.parameters["gapfill_models_by_index"]:
                        self.gapfilling_penalties.update(
                            self.extend_model_with_model_for_gapfilling(gfmdl, index)
                        )
                if self.parameters["gapfill_all_indecies_with_default_templates"]:
                    for template in self.parameters["default_gapfill_templates"]:
                        self.gapfilling_penalties.update(
                            self.extend_model_with_template_for_gapfilling(
                                template, index
                            )
                        )
                if self.parameters["gapfill_all_indecies_with_default_models"]:
                    for gfmdl in self.parameters["default_gapfill_models"]:
                        self.gapfilling_penalties.update(
                            self.extend_model_with_model_for_gapfilling(gfmdl, index)
                        )
        # Removing exclusion solution reactions from penalties dictionary
        if exclusion_solution:
            for item in exclusion_solution:
                if item[0] in self.gapfilling_penalties:
                    if (
                        item[1] == ">"
                        and "forward" in self.gapfilling_penalties[item[0]]
                    ):
                        del self.gapfilling_penalties[item[0]]["forward"]
                    elif (
                        item[1] == "<"
                        and "reverse" in self.gapfilling_penalties[item[0]]
                    ):
                        del self.gapfilling_penalties[item[0]]["reverse"]
        # Rescaling penalties by reaction scores and saving genes
        if not reaction_scores:
            reaction_scores = self.parameters["reaction_scores"]
        for reaction in self.gapfilling_penalties:
            rxnid = reaction.split("_")[0]
            if rxnid in reaction_scores:
                highest_score = 0
                for gene in reaction_scores[rxnid]:
                    if highest_score < reaction_scores[rxnid][gene]:
                        highest_score = reaction_scores[rxnid][gene]
                factor = 0.1
                if "reverse" in self.gapfilling_penalties[reaction]:
                    self.gapfilling_penalties[reaction]["reverse"] = (
                        factor * self.gapfilling_penalties[reaction]["reverse"]
                    )
                if "forward" in self.gapfilling_penalties[reaction]:
                    self.gapfilling_penalties[reaction]["forward"] = (
                        factor * self.gapfilling_penalties[reaction]["forward"]
                    )

    def build_gapfilling_objective_function(self):
        """Builds gapfilling objective function for model"""
        reaction_objective = self.model.problem.Objective(Zero, direction="min")
        obj_coef = dict()
        for reaction in self.model.reactions:
            if reaction.id in self.gapfilling_penalties:
                if self.parameters["minimize_exchanges"] or reaction.id[0:3] != "EX_":
                    # Minimizing gapfilled reactions
                    if "reverse" in self.gapfilling_penalties[reaction.id]:
                        obj_coef[reaction.reverse_variable] = abs(
                            self.gapfilling_penalties[reaction.id]["reverse"]
                        )
                    if "forward" in self.gapfilling_penalties[reaction.id]:
                        obj_coef[reaction.forward_variable] = abs(
                            self.gapfilling_penalties[reaction.id]["forward"]
                        )
            else:
                obj_coef[reaction.forward_variable] = 0
                obj_coef[reaction.reverse_variable] = 0
        self.model.objective = reaction_objective
        reaction_objective.set_linear_coefficients(obj_coef)
        self.parameters["gfobj"] = self.model.objective

    def create_max_flux_variables(self):
        """Creates max flux variables needed for the global gapfilling formulation
        Parameters
        ----------
        """
        for reaction in self.model.reactions:
            if reaction.id in self.gapfilling_penalties:
                if "reverse" in self.gapfilling_penalties[reaction.id]:
                    self.maxflux_variables[reaction.id]["reverse"] = (
                        self.build_variable("rmaxf", 0, 1000, "continuous", reaction)
                    )
                    self.build_constraint(
                        "rmaxfc",
                        0,
                        None,
                        {
                            reaction.reverse_variable: -1,
                            self.maxflux_variables[reaction.id]["reverse"]: 1,
                        },
                        reaction,
                    )
                if "forward" in self.gapfilling_penalties[reaction.id]:
                    self.maxflux_variables[reaction.id]["forward"] = (
                        self.build_variable("fmaxf", 0, 1000, "continuous", reaction)
                    )
                    self.build_constraint(
                        "fmaxfc",
                        0,
                        None,
                        {
                            reaction.forward_variable: -1,
                            self.maxflux_variables[reaction.id]["forward"]: 1,
                        },
                        reaction,
                    )

    def reset_original_objective(self):
        self.parameters["origobj"] = self.model.objective

    def get_model_index_hash(self):
        """Determine all indices that should be gap filled"""
        index_hash = {"none": 0}
        for metabolite in self.model.metabolites:
            if re.search("_[a-z]\d+$", metabolite.id) is not None:
                m = re.search("_([a-z])(\d+)$", metabolite.id)
                if m[1] != "e":
                    if m[2] not in index_hash:
                        index_hash[m[2]] = 0
                    index_hash[m[2]] += 1
            else:
                index_hash["none":0]
                # Iterating over all indecies with more than 10 intracellular compounds:
        return index_hash

    def extend_model_with_model_for_gapfilling(self, source_model, index):
        self.new_metabolites, self.new_reactions, local_remap, new_penalties = (
            {},
            {},
            {},
            {},
        )
        new_exchange, new_demand = [], []
        # Adding metabolites from source model to gapfill model
        for cobra_met in source_model.metabolites:
            original_id = cobra_met.id
            if re.search("(.+)_([a-z])\d+$", cobra_met.id):
                m = re.search("(.+)_([a-z])\d+$", cobra_met.id)
                if m[2] == "e":
                    cobra_met.compartment = "e0"
                    cobra_met.id = m[1] + "_e0"
                else:
                    cobra_met.compartment = m[2] + index
                    cobra_met.id = m[1] + "_" + m[2] + index
                if (
                    cobra_met.id not in self.model.metabolites
                    and cobra_met.id not in self.new_metabolites
                ):
                    self.new_metabolites[cobra_met.id] = cobra_met
                    local_remap[original_id] = cobra_met
                    if m[1] + "_" + m[2] in self.parameters["auto_sink"]:
                        new_demand.append(cobra_met)
                    if m[2] == "e":
                        new_exchange.append(cobra_met)
        # Adding all metabolites to model prior to adding reactions
        self.model.add_metabolites(self.new_metabolites.values())
        # Adding reactions from source model to gapfill model
        for modelreaction in source_model.reactions:
            if re.search("(.+)_([a-z])\d+$", modelreaction.id):
                m = re.search("(.+)_([a-z])\d+$", modelreaction.id)
                if m[1] not in self.parameters["blacklist"]:
                    cobra_rxn = modelreaction.copy()
                    if m[1] in base_blacklist:
                        if base_blacklist[m[1]] == ">" or base_blacklist[m[1]] == "=":
                            cobra_rxn.upper_bound = 0
                        if base_blacklist[m[1]] == "<" or base_blacklist[m[1]] == "=":
                            cobra_rxn.lower_bound = 0
                    cobra_rxn.id = m[1] + "_" + m[2] + index
                    if (
                        cobra_rxn.id not in self.model.reactions
                        and cobra_rxn.id not in self.new_reactions
                    ):
                        self.new_reactions[cobra_rxn.id] = cobra_rxn
                        new_penalties[cobra_rxn.id] = dict()
                        new_penalties[cobra_rxn.id]["added"] = 1
                        if cobra_rxn.lower_bound < 0:
                            new_penalties[cobra_rxn.id]["reverse"] = self.parameters[
                                "model_penalty"
                            ]
                        if cobra_rxn.upper_bound > 0:
                            new_penalties[cobra_rxn.id]["forward"] = self.parameters[
                                "model_penalty"
                            ]
                        # Updating metabolites in reaction to new model
                        new_stoichiometry = {}
                        for met in cobra_rxn.metabolites:
                            # Adding new coefficient:
                            new_stoichiometry[local_remap[met.id]] = (
                                cobra_rxn.metabolites[met]
                            )
                            # Zeroing out current coefficients
                            if local_remap[met.id] != met:
                                new_stoichiometry[met] = 0
                        cobra_rxn.add_metabolites(new_stoichiometry, combine=False)
                    elif (
                        cobra_rxn.lower_bound < 0
                        and self.model.reactions.get_by_id(cobra_rxn.id).lower_bound
                        == 0
                    ):
                        self.model.reactions.get_by_id(cobra_rxn.id).lower_bound = (
                            cobra_rxn.lower_bound
                        )
                        self.model.reactions.get_by_id(
                            cobra_rxn.id
                        ).update_variable_bounds()
                        new_penalties[cobra_rxn.id]["reverse"] = self.parameters[
                            "model_penalty"
                        ]
                        new_penalties[cobra_rxn.id]["reversed"] = True
                    elif (
                        cobra_rxn.upper_bound > 0
                        and self.model.reactions.get_by_id(cobra_rxn.id).upper_bound
                        == 0
                    ):
                        self.model.reactions.get_by_id(cobra_rxn.id).upper_bound = (
                            cobra_rxn.upper_bound
                        )
                        self.model.reactions.get_by_id(
                            cobra_rxn.id
                        ).update_variable_bounds()
                        new_penalties[cobra_rxn.id]["forward"] = self.parameters[
                            "model_penalty"
                        ]
                        new_penalties[cobra_rxn.id]["reversed"] = True

        # Only run this on new exchanges so we don't readd for all exchanges
        self.modelutl.add_exchanges_for_metabolites(
            new_exchange,
            self.parameters["default_uptake"],
            self.parameters["default_excretion"],
        )
        # Only run this on new demands so we don't readd for all exchanges
        self.modelutl.add_exchanges_for_metabolites(
            new_demand,
            self.parameters["default_uptake"],
            self.parameters["default_excretion"],
            "DM_",
        )
        # Adding all new reactions to the model at once (much faster than one at a time)
        self.model.add_reactions(self.new_reactions.values())
        return new_penalties

    def extend_model_with_template_metabolites(self, template, index="0"):
        """
        Add all missing template compartment compounds to the model
        :param template:
        :param index:
        :return:
        """
        self.new_metabolites = {}
        new_exchange, new_demand = [], []
        for template_compound in template.compcompounds:
            compartment = template_compound.compartment
            compartment_index = "0" if compartment == "e" else index
            cobra_met = self.convert_template_compound(
                template_compound, compartment_index, template
            )  # TODO: move function out
            if (
                cobra_met.id not in self.model.metabolites
                and cobra_met.id not in self.new_metabolites
            ):
                self.new_metabolites[cobra_met.id] = cobra_met
                # self.model.add_metabolites([cobra_met])
                msid = FBAHelper.modelseed_id_from_cobra_metabolite(cobra_met)
                if msid in self.parameters["auto_sink"]:
                    if msid != "cpd11416" or cobra_met.compartment == "c0":
                        new_demand.append(cobra_met.id)
                if compartment == "e":
                    new_exchange.append(cobra_met)
        # Adding all metabolites to model prior to adding reactions
        self.model.add_metabolites(self.new_metabolites.values())

        return new_exchange, new_demand

    # Possible new function to add to the KBaseFBAModelToCobraBuilder to extend a model with a template for gapfilling for a specific index
    def extend_model_with_template_for_gapfilling(self, template, index):
        logger.debug(f"extend model with template: {template}, index: {index}")

        self.new_reactions = {}
        new_penalties = dict()

        # Adding all metabolites to model prior to adding reactions
        new_exchange, new_demand = self.extend_model_with_template_metabolites(
            template, index
        )

        for template_reaction in template.reactions:
            if template_reaction.reference_id in self.parameters["blacklist"]:
                continue
            cobra_rxn = self.convert_template_reaction(
                template_reaction, index, template, 1
            )  # TODO: move function out
            if template_reaction.reference_id in base_blacklist:
                if (
                    base_blacklist[template_reaction.reference_id] == ">"
                    or base_blacklist[template_reaction.reference_id] == "="
                ):
                    cobra_reaction.upper_bound = 0
                if (
                    base_blacklist[template_reaction.reference_id] == "<"
                    or base_blacklist[template_reaction.reference_id] == "="
                ):
                    cobra_reaction.lower_bound = 0
            new_penalties[cobra_reaction.id] = dict()
            if (
                cobra_rxn.id not in self.model.reactions
                and cobra_rxn.id not in self.new_reactions
            ):
                # Adding any template reactions missing from the present model
                self.new_reactions[cobra_rxn.id] = cobra_rxn
                if cobra_rxn.lower_bound < 0:
                    new_penalties[cobra_rxn.id]["reverse"] = (
                        template_reaction.base_cost + template_reaction.reverse_penalty
                    )
                if cobra_rxn.upper_bound > 0:
                    new_penalties[cobra_rxn.id]["forward"] = (
                        template_reaction.base_cost + template_reaction.forward_penalty
                    )
                new_penalties[cobra_rxn.id]["added"] = 1
            elif template_reaction.GapfillDirection == "=":
                # Adjusting directionality as needed for existing reactions
                model_reaction = self.model.reactions.get_by_id(cobra_rxn.id)
                new_penalties[cobra_rxn.id]["reversed"] = True
                if model_reaction.lower_bound == 0:
                    model_reaction.lower_bound = template_reaction.lower_bound
                    model_reaction.update_variable_bounds()
                    new_penalties[cobra_rxn.id]["reverse"] = (
                        template_reaction.base_cost + template_reaction.reverse_penalty
                    )
                if model_reaction.upper_bound == 0:
                    model_reaction.upper_bound = template_reaction.upper_bound
                    model_reaction.update_variable_bounds()
                    new_penalties[cobra_rxn.id]["forward"] = (
                        template_reaction.base_cost + template_reaction.forward_penalty
                    )
        # Only run this on new exchanges so we don't read for all exchanges
        exchanges = self.modelutl.add_exchanges_for_metabolites(
            new_exchange,
            self.parameters["default_uptake"],
            self.parameters["default_excretion"],
        )
        for ex in exchanges:
            new_penalties[ex.id] = {"added": 1, "reverse": 1, "forward": 1}

        # Only run this on new demands so we don't readd for all exchanges
        exchanges = self.modelutl.add_exchanges_for_metabolites(
            new_demand,
            self.parameters["default_uptake"],
            self.parameters["default_excretion"],
            "DM_",
        )
        for ex in exchanges:
            new_penalties[ex.id] = {"added": 1, "reverse": 1, "forward": 1}

        # Adding all new reactions to the model at once (much faster than one at a time)
        self.model.add_reactions(self.new_reactions.values())
        return new_penalties

    def convert_template_compound(self, template_compound, index, template):
        base_id = template_compound.id.split("_")[0]
        base_compound = template.compounds.get_by_id(base_id)
        new_id = template_compound.id + str(index)
        compartment = template_compound.compartment + str(index)

        met = Metabolite(
            new_id,
            formula=base_compound.formula,
            name=base_compound.name,
            charge=template_compound.charge,
            compartment=compartment,
        )

        met.annotation["sbo"] = (
            "SBO:0000247"  # simple chemical - Simple, non-repetitive chemical entity.
        )
        met.annotation["seed.compound"] = base_id
        return met

    def convert_template_reaction(
        self, template_reaction, index, template, for_gapfilling=1
    ):
        base_id = template_reaction.id.split("_")[0]
        new_id = template_reaction.id + str(index)

        lower_bound = template_reaction.lower_bound
        upper_bound = template_reaction.upper_bound
        direction = template_reaction.GapfillDirection
        if for_gapfilling == 0:
            direction = template_reaction.direction
        if direction == ">":
            lower_bound = 0
        elif direction == "<":
            upper_bound = 0

        object_stoichiometry = {}
        for m, value in template_reaction.metabolites.items():
            metabolite_id = m.id
            template_compound = template.compcompounds.get_by_id(m.id)
            compartment = template_compound.compartment
            if compartment == "e":
                metabolite_id = m.id + "0"
            else:
                metabolite_id = m.id + str(index)
            metabolite = self.model.metabolites.get_by_id(metabolite_id)
            object_stoichiometry[metabolite] = value

        cobra_rxn = Reaction(
            new_id,
            name=template_reaction.name,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
        )
        cobra_rxn.add_metabolites(object_stoichiometry)
        cobra_rxn.annotation["sbo"] = "SBO:0000176"  # biochemical reaction
        cobra_rxn.annotation["seed.reaction"] = template_reaction.reference_id
        return cobra_rxn

    def binary_check_gapfilling_solution(self, solution=None, flux_values=None):
        solution = solution or self.compute_gapfilled_solution(flux_values)
        flux_values = flux_values or FBAHelper.compute_flux_values_from_variables(
            self.model
        )
        rxn_filter = {
            rxn_id: solution["reversed"][rxn_id] for rxn_id in solution["reversed"]
        }
        rxn_filter.update(
            {rxn_id: solution["new"][rxn_id] for rxn_id in solution["new"]}
        )
        self.pkgmgr.getpkg("ReactionUsePkg").build_package(rxn_filter)
        objcoef = {}
        for rxnid in rxn_filter:
            if rxn_filter[rxnid] == ">":
                objcoef[self.pkgmgr.getpkg("ReactionUsePkg").variables["fu"][rxnid]] = 1
            if rxn_filter[rxnid] == "<":
                objcoef[self.pkgmgr.getpkg("ReactionUsePkg").variables["ru"][rxnid]] = 1
        new_solution = {}
        with self.model:  # to prevent the model for permanently assuming the zeroed reactions
            # Setting all gapfilled reactions not in the solution to zero
            self.knockout_gf_reactions_outside_solution(solution, flux_values)
            # Setting the objective to the minimum sum of binary variables
            self.model.objective = self.model.problem.Objective(Zero, direction="min")
            self.model.objective.set_linear_coefficients(objcoef)
            self.model.optimize()
            new_solution = self.compute_gapfilled_solution(flux_values)
        return new_solution

    def knockout_gf_reactions_outside_solution(self, solution=None, flux_values=None):
        """
        This function is designed to KO all gap filled reactions not included in the solution
        """
        if solution == None:
            solution = self.compute_gapfilled_solution(flux_values)
        if flux_values == None:
            flux_values = self.modelutl.compute_flux_values_from_variables()
        for rxnobj in self.model.reactions:
            if rxnobj.id in self.gapfilling_penalties:
                if (
                    "reverse" in self.gapfilling_penalties[rxnobj.id]
                    and flux_values[rxnobj.id]["reverse"] <= zero_threshold
                ):
                    rxnobj.lower_bound = 0
                if (
                    "forward" in self.gapfilling_penalties[rxnobj.id]
                    and flux_values[rxnobj.id]["forward"] <= zero_threshold
                ):
                    rxnobj.upper_bound = 0
                rxnobj.update_variable_bounds()

    def run_test_conditions(self, condition_list, solution=None, max_iterations=10):
        reaction_list, filtered_list = [], []
        if solution == None:
            solution = self.compute_gapfilled_solution()
        for rxnid in solution["reversed"]:
            reaction_list.append(
                [self.model.reactions.get_by_id(rxnid), solution["reversed"][rxnid]]
            )
        for rxnid in solution["new"]:
            reaction_list.append(
                [self.model.reactions.get_by_id(rxnid), solution["new"][rxnid]]
            )
        filtered_list = []
        with self.model:
            # Setting all gapfilled reactions not in the solution to zero
            self.knockout_gf_reactions_outside_solution(solution)
            self.pkgmgr.getpkg("ObjConstPkg").constraints["objc"]["1"].lb = 0
            for condition in condition_list:
                condition["change"] = True
            filtered_list = self.modelutl.reaction_expansion_test(
                reaction_list, condition_list
            )
            for condition in condition_list:
                condition["change"] = False
        if len(filtered_list) > 0:
            if max_iterations > 0:
                logger.warning("Gapfilling test failed " + str(11 - max_iterations))
                # Forcing filtered reactions to zero
                for item in filtered_list:
                    if item[1] == ">":
                        self.model.reactions.get_by_id(item[0].id).upper_bound = 0
                    else:
                        self.model.reactions.get_by_id(item[0].id).lower_bound = 0
                # Restoring lower bound on biomass constraint
                self.pkgmgr.getpkg("ObjConstPkg").constraints["objc"]["1"].lb = (
                    self.parameters["minimum_obj"]
                )
                # Reoptimizing
                self.model.optimize()
                return self.run_test_conditions(
                    condition_list, None, max_iterations - 1
                )
            return None
        return solution

    def test_gapfill_database(self):
        self.pkgmgr.getpkg("ObjConstPkg").constraints["objc"]["1"].lb = 0
        self.model.objective = self.parameters["origobj"]
        solution = self.model.optimize()
        logger.debug(
            "Objective with gapfill database:"
            + str(solution.objective_value)
            + "; min objective:"
            + str(self.parameters["minimum_obj"])
        )
        self.pkgmgr.getpkg("ObjConstPkg").constraints["objc"]["1"].lb = self.parameters[
            "minimum_obj"
        ]
        self.model.objective = self.parameters["gfobj"]
        if solution.objective_value < self.parameters["minimum_obj"]:
            return False
        return True

    def set_min_objective(self, min_objective):
        self.parameters["minimum_obj"] = min_objective
        self.pkgmgr.getpkg("ObjConstPkg").constraints["objc"]["1"].lb = self.parameters[
            "minimum_obj"
        ]

    def filter_database_based_on_tests(self, test_conditions):
        # Setting the minimal growth constraint to zero
        self.pkgmgr.getpkg("ObjConstPkg").constraints["objc"]["1"].lb = 0
        # Filtering the database of any reactions that violate the specified tests
        filetered_list = []
        with self.model:
            rxnlist = []
            for reaction in self.model.reactions:
                if reaction.id in self.gapfilling_penalties:
                    if "reverse" in self.gapfilling_penalties[reaction.id]:
                        rxnlist.append([reaction, "<"])
                    if "forward" in self.gapfilling_penalties[reaction.id]:
                        rxnlist.append([reaction, ">"])

            filtered_list = self.modelutl.reaction_expansion_test(
                rxnlist, test_conditions
            )
        # Now constraining filtered reactions to zero
        for item in filtered_list:
            logger.debug("Filtering:" + item[0].id + item[1])
            if item[1] == ">":
                self.model.reactions.get_by_id(item[0].id).upper_bound = 0
            else:
                self.model.reactions.get_by_id(item[0].id).lower_bound = 0
        # Now testing if the gapfilling minimum objective can still be achieved
        if not self.test_gapfill_database():
            # Now we need to restore a minimal set of filtered reactions such that we permit the minimum objective to be reached
            # Restoring the minimum objective constraint
            self.pkgmgr.getpkg("ObjConstPkg").constraints["objc"]["1"].lb = (
                self.parameters["minimum_obj"]
            )
            new_objective = self.model.problem.Objective(Zero, direction="min")
            filterobjcoef = dict()
            for item in filtered_list:
                rxn = self.model.reactions.get_by_id(item[0].id)
                if item[1] == ">":
                    filterobjcoef[rxn.forward_variable] = item[3]
                    rxn.upper_bound = item[2]
                else:
                    filterobjcoef[rxn.reverse_variable] = item[3]
                    rxn.lower_bound = item[2]
            self.model.objective = new_objective
            new_objective.set_linear_coefficients(filterobjcoef)
            solution = self.model.optimize()
            count = len(filtered_list)
            for item in filtered_list:
                rxn = self.model.reactions.get_by_id(item[0].id)
                if solution.fluxes[rxn.id] > 0.0000001:
                    if item[1] == "<":
                        count += -1
                        rxn.lower_bound = 0
                elif solution.fluxes[rxn.id] < -0.0000001:
                    if item[1] == ">":
                        count += -1
                        rxn.upper_bound = 0
                else:
                    if item[1] == ">":
                        count += -1
                        rxn.upper_bound = 0
                    else:
                        count += -1
                        rxn.lower_bound = 0
            logger.debug("Reactions unfiltered:" + str(count))
            # Checking for model reactions that can be removed to enable all tests to pass
            self.pkgmgr.getpkg("ObjConstPkg").constraints["objc"]["1"].lb = 0
            filtered_list = self.modelutl.reaction_expansion_test(
                self.parameters["original_reactions"], test_conditions
            )
            for item in filtered_list:
                logger.debug("Filtering:" + item[0].id + item[1])
                if item[1] == ">":
                    self.model.reactions.get_by_id(item[0].id).upper_bound = 0
                else:
                    self.model.reactions.get_by_id(item[0].id).lower_bound = 0
        # Restoring gapfilling objective function and minimal objective constraint
        self.pkgmgr.getpkg("ObjConstPkg").constraints["objc"]["1"].lb = self.parameters[
            "minimum_obj"
        ]
        self.model.objective = self.parameters["gfobj"]
        return True

    def compute_gapfilled_solution(self, flux_values=None):
        if flux_values is None:
            flux_values = self.modelutl.compute_flux_values_from_variables()
        output = {"reversed": {}, "new": {}}
        for reaction in self.model.reactions:
            if reaction.id in self.gapfilling_penalties:
                if (
                    flux_values[reaction.id]["forward"] > zero_threshold
                    and "forward" in self.gapfilling_penalties[reaction.id]
                ):
                    if "added" in self.gapfilling_penalties[reaction.id]:
                        logger.debug(f"New gapfilled reaction: {reaction.id} >")
                        output["new"][reaction.id] = ">"
                    else:
                        logger.debug(f"Reversed gapfilled reaction: {reaction.id} >")
                        output["reversed"][reaction.id] = ">"
                elif (
                    flux_values[reaction.id]["reverse"] > zero_threshold
                    and "reverse" in self.gapfilling_penalties[reaction.id]
                ):
                    if "added" in self.gapfilling_penalties[reaction.id]:
                        logger.debug(f"New gapfilled reaction: {reaction.id} <")
                        output["new"][reaction.id] = "<"
                    else:
                        logger.debug(f"Reversed gapfilled reaction: {reaction.id} <")
                        output["reversed"][reaction.id] = "<"
        return output
