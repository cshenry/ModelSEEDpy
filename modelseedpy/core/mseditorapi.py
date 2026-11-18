# -*- coding: utf-8 -*-
import logging

logger = logging.getLogger(__name__)
from cobra.core import Reaction, Metabolite
import re

# Every accepted spelling of a reaction direction, mapped to the ">", "<" or "="
# that MSEquation.build_from_palsson_string emits
_DIRECTIONS = {
    ">": ">",
    "=>": ">",
    "forward": ">",
    "<": "<",
    "<=": "<",
    "backward": "<",
    "=": "=",
    "<=>": "=",
    "reversible": "=",
}


def _check_direction(direction):
    if direction not in _DIRECTIONS:
        raise ValueError(
            f"The reaction direction {direction!r} is not one of {list(_DIRECTIONS)}."
        )
    return _DIRECTIONS[direction]


def _is_equation(obj):
    # An MSEquation, or any object with the same direction and stoichiometry
    # attributes (older code reads the stoichiometry as .equation)
    return hasattr(obj, "direction") and (
        hasattr(obj, "stoich") or hasattr(obj, "equation")
    )


class MSEditorAPI:
    @staticmethod
    def remove_reactions(model, rxn_id_list=[]):
        model_reactions = " ".join(
            [rxn.id for rxn in model.reactions]
        )  # removed from loop for greater efficiency
        for rxn_id in rxn_id_list:
            if not model.reactions.has_id(rxn_id):
                compartment = re.search(f"(?<={rxn_id})(\_\w\d)", model_reactions)
                if not compartment:
                    raise Exception("Reaction", rxn_id, "is not in the model.")
                else:
                    rxn_id += compartment.group()
            model.remove_reactions([rxn_id])

    # edit reaction progam
    # ASSUMPTIONS:
    # an arrow will exist in the program, either =>, <=>, or <=
    @staticmethod
    def edit_reaction(model, rxn_id, direction=None, gpr=None, genome=None):
        # genome is unused, and is kept so that existing calls that pass it still work
        # Direction: =>, <=, or <=>
        if direction is not None:
            lower_bound = model.reactions.get_by_id(rxn_id).lower_bound
            upper_bound = model.reactions.get_by_id(rxn_id).upper_bound

            if lower_bound < 0 and upper_bound > 0:  # rxn_id is reversible
                if direction == "=>":
                    model.reactions.get_by_id(rxn_id).lower_bound = 0
                elif direction == "<=":
                    model.reactions.get_by_id(rxn_id).upper_bound = 0
            elif lower_bound == 0 and upper_bound > 0:  # rxn_id is forward only
                if direction == "<=":
                    model.reactions.get_by_id(rxn_id).lower_bound = -1 * upper_bound
                    model.reactions.get_by_id(rxn_id).upper_bound = 0
                elif direction == "<=>":
                    model.reactions.get_by_id(rxn_id).lower_bound = -1 * upper_bound
            elif lower_bound < 0 and upper_bound == 0:  # rxn_id is reverse only
                if direction == "=>":
                    model.reactions.get_by_id(rxn_id).lower_bound = 0
                    model.reactions.get_by_id(rxn_id).upper_bound = -1 * lower_bound
                elif direction == "<=>":
                    model.reactions.get_by_id(rxn_id).upper_bound = -1 * lower_bound

        # Specify GPR as a string with boolean conditions (e.g. "(b0001 and b0002) or b1010").
        # An empty string clears the GPR; None leaves it unchanged.
        try:
            if gpr is not None:
                model.reactions.get_by_id(rxn_id).gene_reaction_rule = gpr
        except:
            raise Exception(
                f"The gpr {gpr} is invalid. Perhaps check parentheses."
            )  # not working, unsure exactly why

    @staticmethod
    def edit_biomass_compound(model, biomass_id, cpd_id, new_coef, rescale=1):
        if biomass_id in model.reactions:
            if cpd_id in model.metabolites:
                model.reactions.get_by_id(biomass_id).add_metabolites(
                    {model.metabolites.get_by_id(cpd_id): new_coef}, combine=False
                )
            else:
                raise Exception("Metabolite", cpd_id, " is not in the model.")
        else:  # if there is no biomass reaction
            biomass_rxn = Reaction(biomass_id)
            model.add_reactions([biomass_rxn])
            if cpd_id in model.metabolites:
                biomass_rxn.add_metabolites(
                    {model.metabolites.get_by_id(cpd_id): new_coef}
                )
            else:
                raise Exception("Metabolite ", cpd_id, " is not in the model.")

    @staticmethod
    def compute_molecular_weight(model, metabolite_id):
        if metabolite_id not in model.metabolites:
            raise Exception(
                "Error, metabolite", metabolite_id, "not found in the model"
            )
        return model.metabolites.get_by_id(metabolite_id).formula_weight

    @staticmethod
    def add_custom_reaction(
        model,
        stoichiometry=None,
        direction=">",
        rxnID=None,
        rxnName="",
        subsystem="",
        lb=0,
        ub=1000,
        gpr=None,
        genome=None,
        rxn_id=None,
        MSEquation=None,
    ):
        """Add a reaction to the model.

        stoichiometry maps metabolites, metabolite ids, or the (compound, compartment)
        tuples of a parsed MSEquation to their coefficients. direction is ">", "<", "=",
        "=>", "<=", "<=>", "forward", "backward" or "reversible"; anything else raises
        ValueError. "<" sets the bounds to (-1000, 0) and "=" sets lb to -1000.
        rxnID defaults to "rxn42".

        The older call add_custom_reaction(model, rxn_id, MSEquation, gpr, genome) still
        works, positionally or with the rxn_id= and MSEquation= keywords. genome is unused.
        """
        # MSEquation is the older keyword, so the MSEquation class is hidden here
        equation = MSEquation
        if equation is None and _is_equation(direction):
            # the older positional call puts the MSEquation in direction, and its
            # gpr and genome in rxnID and rxnName
            equation = direction
            if rxnID is not None:
                gpr = rxnID
            rxnID, rxnName = None, ""
        if equation is not None:
            rxnID = rxn_id if rxn_id is not None else stoichiometry
            if hasattr(equation, "stoich"):
                stoichiometry = equation.stoich
            else:
                stoichiometry = equation.equation
            direction = equation.direction
        if rxnID is None:
            rxnID = rxn_id if rxn_id is not None else "rxn42"
        if stoichiometry is None:
            raise TypeError("add_custom_reaction needs a stoichiometry or MSEquation.")
        direction = _check_direction(direction)
        if direction == "<":
            lb = -1000
            ub = 0
        elif direction == "=":
            lb = -1000
        # Keys may be metabolites, metabolite ids, or the (compound, compartment)
        # tuples of a parsed MSEquation, which name the metabolite compound_compartment
        metabolites = {}
        for met, stoich in stoichiometry.items():
            if isinstance(met, tuple):
                met = f"{met[0]}_{met[1]}"
            if not isinstance(met, Metabolite):
                if met not in model.metabolites:
                    raise ValueError(f"The metabolite {met} is not in the model.")
                met = model.metabolites.get_by_id(met)
            metabolites[met] = stoich
        new_rxn = Reaction(rxnID, rxnName, subsystem, lb, ub)
        new_rxn.add_metabolites(metabolites)
        if gpr is not None:
            new_rxn.gene_reaction_rule = gpr
        model.add_reactions([new_rxn])

    @staticmethod
    def add_ms_reaction(
        model,
        rxn_id,
        modelseed,
        compartment_equivalents={"0": "c0", "1": "e0"},
        direction="forward",
    ):  # Andrew
        """Add a reaction with ModelSEED parameters to the FBA simulation
        "model" (COBRA object): The metabolic model that is defined by COBRApy
        "rxn_id" (Python object, string): The ModelSEED reaction id that will be added to the model
        "Compartment_equivalents" (Python object, dictionary): The compartment codes that are used in formating the passed reactions
        "direction" (Python object, string): The direction of the defined reaction: ">", "<", "=", "=>", "<=", "<=>", "forward", "backward" or "reversible". Anything else raises ValueError.
        "modelseed" (ModelSEED object): The ModelSEED database that describes the reaction and metabolites of the argument, with get_seed_reaction and get_seed_compound methods (e.g. ModelSEEDBiochem)
        """
        direction = _check_direction(direction)
        new_rxn = Reaction(rxn_id)
        modelseed_reaction = modelseed.get_seed_reaction(rxn_id)
        new_rxn.name = modelseed_reaction.data["name"]
        reaction_stoich = modelseed_reaction.cstoichiometry
        metabolites_to_add = {
            Metabolite(
                metabolite[0],
                name=modelseed.get_seed_compound(metabolite[0]).data["name"],
                compartment=compartment_equivalents[metabolite[1]],
            ): stoich
            for metabolite, stoich in reaction_stoich.items()
        }

        new_rxn.add_metabolites(metabolites_to_add)
        new_rxn.lower_bound = 0 if direction == ">" else -1000
        new_rxn.upper_bound = 0 if direction == "<" else 1000
        model.add_reactions([new_rxn])

    @staticmethod
    def copy_model_reactions(model, source_model, rxn_id_list=[]):
        for rxnid in rxn_id_list:
            if rxnid in source_model.reactions:
                model.add_reactions([source_model.reactions.get_by_id(rxnid)])
            else:
                raise ValueError(
                    f"The {rxnid} reaction ID is not in the source model, and thus cannot be added to the model."
                )

    @staticmethod
    def copy_all_model_reactions(
        model, source_model
    ):  # new method that copies all reactions, may not be necessary
        model.add_reactions(
            [
                source_model.reactions.get_by_id(rxn.id)
                for rxn in source_model.reactions
                if rxn not in model.reactions
            ]
        )


class MSEquation:
    def __init__(
        self,
        stoichiometry,
        d=None,
        ID="rxn42",
        name="",
        subsystem="",
        lb=0,
        ub=1000,
        gpr=None,
        direction=None,
    ):
        # d is the original name of the direction argument; direction is its
        # documented name. Either may be given, not both.
        if d is not None and direction is not None:
            raise TypeError(
                "Give the MSEquation direction as d or direction, not both."
            )
        self.stoich = stoichiometry
        self.direction = d if d is not None else direction
        self.rxn_obj = Reaction(ID, name, subsystem, lb, ub)
        if gpr is not None:
            self.rxn_obj.gene_reaction_rule = gpr
        # Only cobra Metabolite keys can be added to a reaction: the parser below
        # returns (compound id, compartment) tuples, which cobra cannot take
        if stoichiometry and isinstance(list(stoichiometry.keys())[0], Metabolite):
            self.rxn_obj.add_metabolites(stoichiometry)

    @property
    def equation(self):
        # the original name of the stoichiometry attribute
        return self.stoich

    @equation.setter
    def equation(self, stoichiometry):
        self.stoich = stoichiometry

    @staticmethod
    def _get_coef(lst, return_dict, side, default_group):
        return_dict = return_dict or {}
        # for side variable, -1 is left side, 1 is right side, for coeficients
        for reagent in lst:
            coeficient = side
            identifier = default_group
            if "(" in reagent and ")" in reagent:
                number = ""
                position = 1
                while reagent[position] != ")":
                    number += reagent[position]
                    position += 1
                coeficient = side * float(number)
                reagent = reagent[position + 1 :]
            # a separate test, not an elif: a reagent can carry both a
            # coefficient and a compartment, e.g. (2)cpd00003[e]
            if "[" in reagent and "]" in reagent:
                s = ""
                position = -2
                while reagent[position] != "[":
                    s = reagent[position] + s
                    position -= 1
                identifier = s
                reagent = reagent[:position]
            # an unmatched parenthesis or bracket is left over in the reagent
            if any([x in reagent for x in ["(", ")", "[", "]"]]):
                raise ValueError(
                    "A closing or opening parentheses or bracket is missing in the reaction string",
                    reagent,
                )
            return_dict[(reagent.strip(), identifier)] = coeficient
        return return_dict

    @staticmethod
    def build_from_palsson_string(
        equation_string,
        default_group="c",
        ID="rxn42",
        name="",
        subsystem="",
        lb=0,
        ub=1000,
        gpr=None,
    ):
        # check for the '=' character, throw exception otherwise
        if "=" not in equation_string:
            raise ValueError(
                f"Error: '=' is missing in the reaction {equation_string}."
            )
        if "<=>" in equation_string:
            direction = "="
        elif "=>" in equation_string:
            direction = ">"
        elif "<=" in equation_string:
            direction = "<"
        else:
            direction = "?"

        # get substrings for either side of the equation
        reactants_substring_list = equation_string[
            0 : equation_string.find("=") - 1
        ].split("+")
        products_substring_list = equation_string[
            equation_string.find("=") + 2 : len(equation_string)
        ].split("+")
        rxn_dict = MSEquation._get_coef(
            [x.strip() for x in reactants_substring_list], None, -1, default_group
        )
        rxn_dict = MSEquation._get_coef(
            [x.strip() for x in products_substring_list], rxn_dict, 1, default_group
        )
        return MSEquation(rxn_dict, direction, ID, name, subsystem, lb, ub, gpr)
