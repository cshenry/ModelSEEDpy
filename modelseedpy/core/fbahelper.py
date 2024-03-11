# -*- coding: utf-8 -*-
from __future__ import absolute_import
import logging
from chemicals import periodic_table
import re
from cobra.core import (
    Gene,
    Metabolite,
    Model,
    Reaction,
)  # !!! Gene and Model are never used
from cobra.util import solver as sutil  # !!! sutil is never used
from scipy.odr import Output  # !!! Output is never used
from typing import Iterable
import time
from chemw import ChemMW
from warnings import warn

# from Carbon.Aliases import false

logger = logging.getLogger(__name__)


class FBAHelper:
    @staticmethod
    def add_autodrain_reactions_to_community_model(
        model, auto_sink=["cpd02701", "cpd15302"]
    ):
        # Adding missing drains in the base model
        drain_reactions = []
        for metabolite in model.metabolites:
            msid = FBAHelper.modelseed_id_from_cobra_metabolite(metabolite)
            if msid in auto_sink:
                if metabolite.compartment == "c0":
                    met_id = metabolite.id
                    if all(
                        [
                            rxn not in model.reactions
                            for rxn in [f"EX_{met_id}", f"DM_{met_id}", f"SK_{met_id}"]
                        ]
                    ):
                        drain_reaction = FBAHelper.add_drain_from_metabolite_id(
                            model, metabolite.id, 0, 100, "DM_"
                        )
                        if not drain_reaction:
                            logger.info("Adding " + met_id + " DM")
                            drain_reactions.append(drain_reaction)
        model.add_reactions(drain_reactions)

    @staticmethod
    def add_drain_from_metabolite_id(
        model, cpd_id, uptake, excretion, prefix="EX_", prefix_name="Exchange for "
    ):
        """
        :param model:
        :param cpd_id:
        :param uptake:
        :param excretion:
        :param prefix:
        :param prefix_name:
        :return:
        """
        if cpd_id in model.metabolites:
            cobra_metabolite = model.metabolites.get_by_id(cpd_id)
            drain_reaction = Reaction(
                id=f"{prefix}{cpd_id}",
                name=prefix_name + cobra_metabolite.name,
                lower_bound=-uptake,
                upper_bound=excretion,
            )
            drain_reaction.add_metabolites({cobra_metabolite: -1})
            drain_reaction.annotation["sbo"] = "SBO:0000627"
            # model.add_reactions([drain_reaction])
            return drain_reaction
        return None

    @staticmethod
    def set_reaction_bounds_from_direction(reaction, direction, add=False):
        if direction == "<":
            reaction.lower_bound = -100
            if not add:
                reaction.upper_bound = 0
        if direction == ">":
            reaction.upper_bound = 100
            if not add:
                reaction.lower_bound = 0
        reaction.update_variable_bounds()

    @staticmethod
    def modelseed_id_from_cobra_metabolite(metabolite):
        if re.search("^(cpd\d+)", metabolite.id):
            m = re.search("^(cpd\d+)", metabolite.id)
            return m[1]
        # TODO: should check to see if ModelSEED ID is in the annotations for the compound
        return None

    @staticmethod
    def modelseed_id_from_cobra_reaction(reaction):
        if re.search("^(rxn\d+)", reaction.id):
            m = re.search("^(rxn\d+)", reaction.id)
            return m[1]
        # TODO: should check to see if ModelSEED ID is in the annotations for the compound
        else:
            return None

    @staticmethod
    def metabolite_mw(metabolite):
        fixed_masses = {"cpd11416": 1, "cpd17041": 0, "cpd17042": 0, "cpd17043": 0}
        msid = FBAHelper.modelseed_id_from_cobra_metabolite(metabolite)
        if msid in fixed_masses:
            return fixed_masses[msid]
        if not metabolite.formula:
            return 0
        formula = re.sub("R\d*", "", metabolite.formula)
        try:
            chem_mw = ChemMW(printing=False)
            chem_mw.mass(formula)
            return chem_mw.raw_mw
        except:
            warn(
                f"The compound {metabolite.id} possesses an unconventional "
                f"formula {metabolite.formula}; hence, the MW cannot be computed."
            )
            return 0

    @staticmethod
    def elemental_mass():
        return {element.symbol: element.MW for element in periodic_table}

    @staticmethod
    def get_modelseed_db_api(modelseed_path):
        from modelseedpy.biochem import from_local

        return from_local(modelseed_path)

    @staticmethod
    def is_ex(reaction):
        # TODO: check for SBO
        if len(reaction.id) > 3 and reaction.id[0:3] in ["EX_", "DM_", "SK_"]:
            return True
        return False

    @staticmethod
    def is_biomass(reaction):
        # TODO: check for SBO
        return reaction.id[0:3] == "bio"

    @staticmethod
    def isnumber(string):
        if str(string) in ["nan", "inf"]:
            return False
        try:
            float(string)
            return True
        except:
            return False

    @staticmethod
    def rxn_mets_list(rxn):
        return [met for met in rxn.reactants + rxn.products]

    @staticmethod
    def sum_dict(d1, d2):
        for key, value in d1.items():
            if key in d2:
                d2[key] += value
            else:
                d2[key] = value
        return d2

    @staticmethod
    def rxn_compartment(reaction):
        compartments = list(reaction.compartments)
        if len(compartments) == 1:
            return compartments[0]
        for comp in compartments:
            if comp[0:1] != "e":
                return comp
            elif comp[0:1] == "e":
                extracellular = comp
        return extracellular

    @staticmethod
    def remove_compartment(objID):
        return re.sub(r"(\_\w\d+)", "", objID)

    @staticmethod
    def compartment_index(string):
        return int(re.search(r"(?<=\_|\w)(\d+)(?=$)", string).group())

    @staticmethod
    def id_from_ref(ref):
        array = ref.split("/")
        return array[-1]

    @staticmethod
    def mediaName(media):
        if media == None:
            return "Complete"
        return media.id

    @staticmethod
    def validate_dictionary(dictionary, required_keys, optional_keys={}):
        for item in required_keys:
            if item not in dictionary:
                raise ValueError("Required key " + item + " is missing!")
        for key in optional_keys:
            if key not in dictionary:
                dictionary[key] = optional_keys[key]
        return dictionary

    @staticmethod
    def parse_media(media):
        return [cpd.id for cpd in media.data["mediacompounds"]]

    @staticmethod
    def get_reframed_model(kbase_model):
        from reframed import from_cobrapy

        reframed_model = from_cobrapy(kbase_model)
        if hasattr(kbase_model, "id"):
            reframed_model.id = kbase_model.id
        for comp in reframed_model.compartments:
            if "e" in comp:
                reframed_model.compartments[comp].external = True

        return reframed_model

    @staticmethod
    def filter_cobra_set(cobra_set):
        unique_ids = set(obj.id for obj in cobra_set)
        unique_objs = set()
        for obj in cobra_set:
            if obj.id in unique_ids:
                unique_objs.add(obj)
                unique_ids.remove(obj.id)
        return unique_objs

    @staticmethod
    def parse_df(df, float_values=True):
        if isinstance(df, tuple):
            return df
        from collections import namedtuple

        dataframe = namedtuple("DataFrame", ("index", "columns", "values"))
        df.dropna(inplace=True)
        values = df.to_numpy()
        if float_values:
            values = values.astype("float64")
        return dataframe(list(df.index), list(df.columns), values)

    @staticmethod
    def solution_to_dict(solution):
        return {key: flux for key, flux in solution.fluxes.items()}

    @staticmethod
    def solution_to_rxns_dict(solution, model):
        return {
            model.reactions.get_by_id(key): flux
            for key, flux in solution.fluxes.items()
        }

    @staticmethod
    def solution_to_variables_dict(solution, model):
        return {model.variables.get(key): flux for key, flux in solution.fluxes.items()}

    @staticmethod
    def remove_media_compounds(media_dict, compounds, printing=True):
        edited_dic = media_dict.copy()
        for cpd in compounds:
            if cpd in edited_dic:
                edited_dic.pop(cpd)
                if printing:
                    print(f"{cpd} removed")
            else:
                print(f"ERROR: The {cpd} is not located in the media.")
        return edited_dic

    @staticmethod
    def IDRxnMets(rxn):
        if not isinstance(rxn, dict):
            return {met.id: stoich for met, stoich in rxn.metabolites.items()}
        else:
            return {met.id: stoich for met, stoich in rxn.items()}

    @staticmethod
    def convert_kbase_media(kbase_media, uniform_uptake=None):
        if uniform_uptake is None:
            return {
                "EX_" + exID: -bound[0]
                for exID, bound in kbase_media.get_media_constraints().items()
            }
        return {
            "EX_" + exID: uniform_uptake
            for exID in kbase_media.get_media_constraints().keys()
        }
