# -*- coding: utf-8 -*-
import logging

logger = logging.getLogger(__name__)
from cobra.core import Reaction, Metabolite
import re


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
    def edit_reaction(model, rxn_id, direction=None, gpr=None):
        # Direction: =>, <=, or <=>
        if direction is not None:
            lower_bound = model.reactions.get_by_id(rxn_id).lower_bound
            upper_bound = model.reactions.get_by_id(rxn_id).upper_bound

            if lower_bound < 0 and upper_bound > 0:  # rxn_id is reversible
                if direction == "=>":   model.reactions.get_by_id(rxn_id).lower_bound = 0
                elif direction == "<=": model.reactions.get_by_id(rxn_id).upper_bound = 0
            elif lower_bound == 0 and upper_bound > 0:  # rxn_id is forward only
                if direction == "<=":
                    model.reactions.get_by_id(rxn_id).lower_bound = -1 * upper_bound
                    model.reactions.get_by_id(rxn_id).upper_bound = 0
                elif direction == "<=>":  model.reactions.get_by_id(rxn_id).lower_bound = -1 * upper_bound
            elif lower_bound < 0 and upper_bound == 0:  # rxn_id is reverse only
                if direction == "=>":
                    model.reactions.get_by_id(rxn_id).lower_bound = 0
                    model.reactions.get_by_id(rxn_id).upper_bound = -1 * lower_bound
                elif direction == "<=>": model.reactions.get_by_id(rxn_id).upper_bound = -1 * lower_bound

        # Specify GPR as a string with boolean conditions (e.g. "(b0001 and b0002) or b1010").
        try:
            if gpr:
                model.reactions.get_by_id(rxn_id).gene_reaction_rule = gpr
        except:
            raise Exception(
                f'The gpr {gpr} is invalid. Perhaps check parentheses.'
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
            model.add_reaction(biomass_rxn)
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
    def add_custom_reaction(model, stoichiometry, direction=">", rxnID="rxn42", rxnName="",
                            subsystem="", lb=0, ub=1000, gpr=None):
        if direction == "<":  lb = -1000  ;  ub = 0
        elif direction == "<=>":   lb = -1000
        if isinstance(list(stoichiometry.keys())[0], str):
            stoichiometry = {model.metabolites.get_by_id(metID): stoich for metID, stoich in stoichiometry.items()}
        new_rxn = MSEquation(stoichiometry, direction, rxnID, rxnName, subsystem, lb, ub, gpr)
        model.add_reaction(new_rxn.rxn_obj)

    @staticmethod  
    def add_ms_reaction(model, rxn_id, modelseed, compartment_equivalents = {'0':'c0', '1':'e0'}, direction = '>'):#Andrew
        new_rxn = Reaction(rxn_id)
        modelseed_reaction = modelseed.get_seed_reaction(rxn_id)
        new_rxn.name = modelseed_reaction.data['name']
        reaction_stoich = modelseed_reaction.cstoichiometry
        metabolites_to_add = {Metabolite(metabolite[0], name=modelseed.get_seed_compound(metabolite[0]).data['name'],
                                          compartment=compartment_equivalents[metabolite[1]]): stoich
                              for metabolite, stoich in reaction_stoich.items()}

        new_rxn.add_metabolites(metabolites_to_add)
        new_rxn.lower_bound = 0 if direction != '=' else -1000   ;   new_rxn.upper_bound = 1000
        if direction == '<':  new_rxn.lower_bound = -1000  ;  new_rxn.upper_bound = 0
        model.add_reactions([new_rxn])

    @staticmethod
    def copy_model_reactions(model, source_model, rxn_id_list=[]):
        for rxnid in rxn_id_list:
            if rxnid in source_model.reactions:
                model.add_reactions([source_model.reactions.get_by_id(rxnid)])
            else:
                raise ValueError(f'The {rxnid} reaction ID is not in the source model, and thus cannot be added to the model.')

    @staticmethod
    def copy_all_model_reactions(model,source_model):  #new method that copies all reactions, may not be necessary
        model.add_reactions([source_model.reactions.get_by_id(rxn.id) for rxn in source_model.reactions if rxn not in model.reactions])

class MSEquation:
    def __init__(self, stoichiometry, direction=None, ID="rxn42", name="", subsystem="", lb=0, ub=1000, gpr=None):
        self.stoich = stoichiometry; self.direction = direction
        self.rxn_obj = Reaction(ID, name, subsystem, lb, ub)
        if gpr is not None:  self.rxn_obj.gene_reaction_rule = gpr
        if not isinstance(list(stoichiometry.keys())[0], str):  self.rxn_obj.add_metabolites(stoichiometry)

    @staticmethod
    def _get_coef(lst, return_dict, side, default_group):
        return_dict = return_dict or {}
        # for side variable, -1 is left side, 1 is right side, for coeficients
        for reagent in lst:
            coeficient = side
            identifier = default_group
            if '(' in reagent and ')' in reagent:
                number = ''
                position = 1
                while reagent[position] != ')':
                    number += reagent[position]
                    position += 1
                coeficient = side * float(number)
                reagent = reagent[position+1: ]
            elif '[' in reagent and ']' in reagent:
                s = ''
                position = -2
                while reagent[position] != '[':
                    s = reagent[position] + s
                    position -= 1
                identifier = s
                reagent = reagent[:position]
            elif any([x in reagent for x in ['(', ')', '[', ']']]):
                raise ValueError("A closing or opening parentheses or bracket is missing in the reaction string", reagent)
            return_dict[(reagent.strip(), identifier)] = coeficient
        return return_dict

    @staticmethod
    def build_from_palsson_string(equation_string, default_group='c', ID="rxn42", name="", subsystem="", lb=0, ub=1000, gpr=None):
        # check for the '=' character, throw exception otherwise
        if '=' not in equation_string: raise ValueError(f"Error: '=' is missing in the reaction {equation_string}.")
        if '<=>' in equation_string:   direction = '='
        elif '=>' in equation_string:  direction = '>'
        elif '<=' in equation_string:  direction = '<'
        else:  direction = '?'

        # get substrings for either side of the equation
        reactants_substring_list = equation_string[0:equation_string.find('=') - 1].split('+')
        products_substring_list = equation_string[equation_string.find('=') + 2:len(equation_string)].split('+')
        rxn_dict = MSEquation._get_coef([x.strip() for x in reactants_substring_list], None, -1, default_group)
        rxn_dict = MSEquation._get_coef([x.strip() for x in products_substring_list], rxn_dict, 1, default_group)
        return MSEquation(rxn_dict, direction, ID, name, subsystem, lb, ub, gpr)
