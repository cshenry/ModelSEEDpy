# -*- coding: utf-8 -*-
import logging
import copy
import math
from enum import Enum
import pandas as pd
import numpy as np
from cobra.core import Metabolite, Reaction
from cobra.core.dictlist import DictList
from cobra.util import format_long_string
from modelseedpy.core.fbahelper import FBAHelper
from modelseedpy.core.msmodel import (
    get_direction_from_constraints,
    get_reaction_constraints_from_direction,
    get_cmp_token,
)
from cobra.core.dictlist import DictList
from typing import TYPE_CHECKING, Dict, Iterable, List, Optional, Tuple, Union

# from gevent.libev.corecext import self

# from cobrakbase.kbase_object_info import KBaseObjectInfo

logger = logging.getLogger(__name__)

SBO_ANNOTATION = "sbo"


class AttrDict(dict):
    """
    Base object to use for subobjects in KBase objects
    """

    def __init__(self, *args, **kwargs):
        super(AttrDict, self).__init__(*args, **kwargs)
        self.__dict__ = self


class TemplateReactionType(Enum):
    CONDITIONAL = "conditional"
    UNIVERSAL = "universal"
    SPONTANEOUS = "spontaneous"
    GAPFILLING = "gapfilling"


class TemplateBiomassCoefficientType(Enum):
    MOLFRACTION = "MOLFRACTION"
    MOLSPLIT = "MOLSPLIT"
    MULTIPLIER = "MULTIPLIER"
    EXACT = "EXACT"


class MSTemplateMetabolite:
    def __init__(
        self,
        cpd_id,
        formula=None,
        name="",
        default_charge=None,
        mass=None,
        delta_g=None,
        delta_g_error=None,
        is_cofactor=False,
        abbreviation="",
        aliases=None,
    ):
        self.id = cpd_id
        self.formula = formula
        self.name = name
        self.abbreviation = abbreviation
        self.default_charge = default_charge
        self.mass = mass
        self.delta_g = delta_g
        self.delta_g_error = delta_g_error
        self.is_cofactor = is_cofactor
        self.aliases = []
        if aliases:
            self.aliases = aliases
        self.species = set()
        self._template = None

    @staticmethod
    def from_dict(d):
        return MSTemplateMetabolite(
            d["id"],
            d["formula"],
            d["name"],
            d["defaultCharge"],
            d["mass"],
            d["deltaG"],
            d["deltaGErr"],
            d["isCofactor"] == 1,
            d["abbreviation"],
            d["aliases"],
        )

    def get_data(self):
        return {
            "id": self.id,
            "name": self.name,
            "abbreviation": self.abbreviation if self.abbreviation else "",
            "aliases": [],
            "defaultCharge": self.default_charge if self.default_charge else 0,
            "deltaG": self.delta_g if self.delta_g else 10000000,
            "deltaGErr": self.delta_g_error if self.delta_g_error else 10000000,
            "formula": self.formula if self.formula else "R",
            "isCofactor": 1 if self.is_cofactor else 0,
            "mass": self.mass if self.mass else 0,
        }

    def __repr__(self):
        return "<%s %s at 0x%x>" % (self.__class__.__name__, self.id, id(self))

    def __str__(self):
        return "{}:{}".format(self.id, self.name)

    def _repr_html_(self):
        return """
        <table>
            <tr>
                <td><strong>Compound identifier</strong></td><td>{id}</td>
            </tr><tr>
                <td><strong>Name</strong></td><td>{name}</td>
            </tr><tr>
                <td><strong>Memory address</strong></td>
                <td>{address}</td>
            </tr><tr>
                <td><strong>Formula</strong></td><td>{formula}</td>
            </tr><tr>
                <td><strong>In {n_species} species</strong></td><td>
                    {species}</td>
            </tr>
        </table>""".format(
            id=self.id,
            name=format_long_string(self.name),
            formula=self.formula,
            address="0x0%x" % id(self),
            n_species=len(self.species),
            species=format_long_string(", ".join(r.id for r in self.species), 200),
        )


class MSTemplateSpecies(Metabolite):
    def __init__(
        self,
        comp_cpd_id: str,
        charge: float,
        compartment: str,
        cpd_id,
        max_uptake=0,
        template=None,
    ):
        self._template_compound = None
        super().__init__(comp_cpd_id, "", "", charge, compartment)
        self._template = template
        self.cpd_id = cpd_id
        self.max_uptake = max_uptake
        if self._template:
            if self.cpd_id in self._template.compounds:
                self._template_compound = self._template.compounds.get_by_id(
                    self.cpd_id
                )

    def to_metabolite(self, index="0", force=False):
        """
        Create cobra.core.Metabolite instance
        :param index: compartment index
        :@param force: force index
        :return: cobra.core.Metabolite
        """
        if index is None:
            index = ""
        index = str(index)

        if self.compartment == "e" and index.isnumeric():
            if force:
                logger.warning(
                    f"Forcing numeric index [{index}] to extra cellular compartment not advised"
                )
            else:
                index = "0"

        cpd_id = f"{self.id}{index}"
        compartment = f"{self.compartment}{index}"
        if self.compound == None:
            logger.critical(
                f"Compound objective associated with [{cpd_id}] is missing from template"
            )
        name = f"{self.compound.name} [{compartment}]"
        metabolite = Metabolite(cpd_id, self.formula, name, self.charge, compartment)
        metabolite.notes["modelseed_template_id"] = self.id
        return metabolite

    @property
    def compound(self):
        return self._template_compound

    @property
    def name(self):
        if self._template_compound:
            return f"{self._template_compound.name} [{self.compartment}]"
        return f"{self.id} [{self.compartment}]"

    @name.setter
    def name(self, value):
        if self._template_compound:
            self._template_compound.name = value

    @property
    def formula(self):
        if self._template_compound:
            return self._template_compound.formula
        return ""

    @formula.setter
    def formula(self, value):
        if self._template_compound:
            self._template_compound.formula = value

    @staticmethod
    def from_dict(d, template=None):
        return MSTemplateSpecies(
            d["id"],
            d["charge"],
            d["templatecompartment_ref"].split("/")[-1],
            d["templatecompound_ref"].split("/")[-1],
            d["maxuptake"],
            template,
        )

    def get_data(self):
        return {
            "charge": self.charge,
            "id": self.id,
            "maxuptake": self.max_uptake,
            "templatecompartment_ref": "~/compartments/id/" + self.compartment,
            "templatecompound_ref": "~/compounds/id/" + self.cpd_id,
        }


class MSTemplateReaction(Reaction):
    def __init__(
        self,
        rxn_id: str,
        reference_id: str,
        name="",
        subsystem="",
        lower_bound=0.0,
        upper_bound=None,
        reaction_type=TemplateReactionType.CONDITIONAL,
        gapfill_direction="=",
        base_cost=1000,
        reverse_penalty=1000,
        forward_penalty=1000,
        status="OK",
        reference_reaction_id=None,
    ):
        """

        :param rxn_id:
        :param reference_id:
        :param name:
        :param subsystem:
        :param lower_bound:
        :param upper_bound:
        :param reaction_type:
        :param gapfill_direction:
        :param base_cost:
        :param reverse_penalty:
        :param forward_penalty:
        :param status:
        :param reference_reaction_id: DO NOT USE THIS duplicate of reference_id
        :param template:
        """
        super().__init__(rxn_id, name, subsystem, lower_bound, upper_bound)
        self.reference_id = reference_id
        self.GapfillDirection = gapfill_direction
        self.base_cost = base_cost
        self.reverse_penalty = reverse_penalty
        self.forward_penalty = forward_penalty
        self.status = status
        self.type = (
            reaction_type.value
            if type(reaction_type) == TemplateReactionType
            else reaction_type
        )
        self.reference_reaction_id = reference_reaction_id  # TODO: to be removed
        self.complexes = DictList()
        self.templateReactionReagents = {}
        self._template = None

    @property
    def gene_reaction_rule(self):
        return " or ".join(map(lambda x: x.id, self.complexes))

    @gene_reaction_rule.setter
    def gene_reaction_rule(self, gpr):
        pass

    @property
    def compartment(self):
        """

        :return:
        """
        return get_cmp_token(self.compartments)

    def to_reaction(self, model=None, index="0"):
        if index is None:
            index = ""
        index = str(index)
        rxn_id = f"{self.id}{index}"
        compartment = f"{self.compartment}{index}"
        name = f"{self.name}"
        metabolites = {}
        for m, v in self.metabolites.items():
            _metabolite = m.to_metabolite(index)
            if _metabolite.id in model.metabolites:
                metabolites[model.metabolites.get_by_id(_metabolite.id)] = v
            else:
                metabolites[_metabolite] = v

        if len(str(index)) > 0:
            name = f"{self.name} [{compartment}]"
        reaction = Reaction(
            rxn_id, name, self.subsystem, self.lower_bound, self.upper_bound
        )
        reaction.add_metabolites(metabolites)
        reaction.annotation["seed.reaction"] = self.reference_id
        return reaction

    @staticmethod
    def from_dict(d, template):
        metabolites = {}
        complexes = set()
        for o in d["templateReactionReagents"]:
            comp_compound = template.compcompounds.get_by_id(
                o["templatecompcompound_ref"].split("/")[-1]
            )
            metabolites[comp_compound] = o["coefficient"]
        for o in d["templatecomplex_refs"]:
            protein_complex = template.complexes.get_by_id(o.split("/")[-1])
            complexes.add(protein_complex)
        lower_bound, upper_bound = get_reaction_constraints_from_direction(
            d["direction"]
        )
        if "lower_bound" in d and "upper_bound" in d:
            lower_bound = d["lower_bound"]
            upper_bound = d["upper_bound"]
        reaction = MSTemplateReaction(
            d["id"],
            d["reaction_ref"].split("/")[-1],
            d["name"],
            "",
            lower_bound,
            upper_bound,
            d["type"],
            d["GapfillDirection"],
            d["base_cost"],
            d["reverse_penalty"],
            d["forward_penalty"],
            d["status"] if "status" in d else None,
            d["reaction_ref"].split("/")[-1],
        )
        reaction.add_metabolites(metabolites)
        reaction.add_complexes(complexes)
        return reaction

    def add_complexes(self, complex_list):
        self.complexes += complex_list

    @property
    def cstoichiometry(self):
        return dict(
            ((met.id, met.compartment), coefficient)
            for (met, coefficient) in self.metabolites.items()
        )

    def remove_role(self, role_id):
        pass

    def remove_complex(self, complex_id):
        pass

    def get_roles(self):
        """

        :return:
        """
        roles = set()
        for cpx in self.complexes:
            for role in cpx.roles:
                roles.add(role)
        return roles

    def get_complexes(self):
        return self.complexes

    def get_complex_roles(self):
        res = {}
        for complexes in self.data["templatecomplex_refs"]:
            complex_id = complexes.split("/")[-1]
            res[complex_id] = set()
            if self._template:
                cpx = self._template.get_complex(complex_id)

                if cpx:
                    for complex_role in cpx["complexroles"]:
                        role_id = complex_role["templaterole_ref"].split("/")[-1]
                        res[complex_id].add(role_id)
                else:
                    print("!!")
        return res

    def get_data(self):
        template_reaction_reagents = list(
            map(
                lambda x: {
                    "coefficient": x[1],
                    "templatecompcompound_ref": "~/compcompounds/id/" + x[0].id,
                },
                self.metabolites.items(),
            )
        )
        return {
            "id": self.id,
            "name": self.name,
            "GapfillDirection": self.GapfillDirection,
            "base_cost": self.base_cost,
            "reverse_penalty": self.reverse_penalty,
            "forward_penalty": self.forward_penalty,
            "upper_bound": self.upper_bound,
            "lower_bound": self.lower_bound,
            "direction": get_direction_from_constraints(
                self.lower_bound, self.upper_bound
            ),
            "maxforflux": self.upper_bound,
            "maxrevflux": 0 if self.lower_bound > 0 else math.fabs(self.lower_bound),
            "reaction_ref": "kbase/default/reactions/id/" + self.reference_id,
            "templateReactionReagents": template_reaction_reagents,
            "templatecompartment_ref": "~/compartments/id/" + self.compartment,
            "templatecomplex_refs": list(
                map(lambda x: "~/complexes/id/" + x.id, self.complexes)
            ),
            # 'status': self.status,
            "type": self.type if type(self.type) is str else self.type.value,
        }

    # def build_reaction_string(self, use_metabolite_names=False, use_compartment_names=None):
    #    cpd_name_replace = {}
    #    if use_metabolite_names:
    #        if self._template:
    #            for cpd_id in set(map(lambda x: x[0], self.cstoichiometry)):
    #                name = cpd_id
    #                if cpd_id in self._template.compcompounds:
    #                    ccpd = self._template.compcompounds.get_by_id(cpd_id)
    #                    cpd = self._template.compounds.get_by_id(ccpd['templatecompound_ref'].split('/')[-1])
    #                    name = cpd.name
    #                cpd_name_replace[cpd_id] = name
    #        else:
    #            return self.data['definition']
    #    return to_str2(self, use_compartment_names, cpd_name_replace)

    # def __str__(self):
    #    return "{id}: {stoichiometry}".format(
    #        id=self.id, stoichiometry=self.build_reaction_string())


class MSTemplateBiomassComponent:
    def __init__(
        self,
        metabolite,
        comp_class: str,
        coefficient: float,
        coefficient_type: str,
        linked_metabolites,
    ):
        """
        :param metabolite:MSTemplateMetabolite
        :param comp_class:string
        :param coefficient:float
        :param coefficient_type:string
        :param linked_metabolites:{MSTemplateMetabolite:float}
        """
        self.id = metabolite.id + "_" + comp_class
        self.metabolite = metabolite
        self.comp_class = comp_class
        self.coefficient = coefficient
        self.coefficient_type = coefficient_type
        self.linked_metabolites = linked_metabolites

    @staticmethod
    def from_dict(d, template):
        met_id = d["templatecompcompound_ref"].split("/").pop()
        metabolite = template.compcompounds.get_by_id(met_id)
        linked_metabolites = {}
        for count, item in enumerate(d["linked_compound_refs"]):
            l_met_id = item.split("/").pop()
            l_metabolite = template.compcompounds.get_by_id(l_met_id)
            linked_metabolites[l_metabolite] = d["link_coefficients"][count]
        self = MSTemplateBiomassComponent(
            metabolite,
            d["class"],
            d["coefficient"],
            d["coefficient_type"],
            linked_metabolites,
        )
        return self

    def get_data(self):
        data = {
            "templatecompcompound_ref": "~/compcompounds/id/" + self.metabolite.id,
            "class": self.comp_class,
            "coefficient": self.coefficient,
            "coefficient_type": self.coefficient_type,
            "linked_compound_refs": [],
            "link_coefficients": [],
        }
        for met in self.linked_metabolites:
            data["linked_compound_refs"].append("~/compcompounds/id/" + met.id)
            data["link_coefficients"].append(self.linked_metabolites[met])
        return data


class MSTemplateBiomass:
    def __init__(
        self,
        biomass_id: str,
        name: str,
        type: str,
        dna: float = 0,
        rna: float = 0,
        protein: float = 0,
        lipid: float = 0,
        cellwall: float = 0,
        cofactor: float = 0,
        pigment: float = 0,
        carbohydrate: float = 0,
        energy: float = 0,
        other: float = 0
    ):
        """

        :param biomass_id:string
        :param name:string
        :param type:string
        :param dna:float
        :param rna:float
        :param protein:float
        :param lipid:float
        :param cellwall:float
        :param cofactor:float
        :param pigment:float
        :param carbohydrate:float
        :param energy:float
        :param other:float
        """
        self.id = biomass_id
        self.name = name
        self.type = type
        self.dna = dna
        self.rna = rna
        self.protein = protein
        self.lipid = lipid
        self.cellwall = cellwall
        self.cofactor = cofactor
        self.pigment = pigment
        self.carbohydrate = carbohydrate
        self.energy = energy
        self.other = other
        self.templateBiomassComponents = DictList()
        self._template = None

    @staticmethod
    def from_table(
        filename_or_df,
        template,
        bio_id,
        name,
        type,
        dna,
        rna,
        protein,
        lipid,
        cellwall,
        cofactor,
        pigment,
        carbohydrate,
        energy,
        other,
    ):
        self = MSTemplateBiomass(
            bio_id,
            name,
            type,
            dna,
            rna,
            protein,
            lipid,
            cellwall,
            cofactor,
            pigment,
            carbohydrate,
            energy,
            other,
        )
        if isinstance(filename_or_df, str):
            filename_or_df = pd.read_table(filename_or_df)
        for index, row in filename_or_df.iterrows():
            if "biomass_id" not in row:
                row["biomass_id"] = "bio1"
            if row["biomass_id"] == bio_id:
                if "compartment" not in row:
                    row["compartment"] = "c"
                metabolite = template.compcompounds.get_by_id(
                    f'{row["id"]}_{row["compartment"].lower()}'
                )
                linked_mets = {}
                if (
                    isinstance(row["linked_compounds"], str)
                    and len(row["linked_compounds"]) > 0
                ):
                    array = row["linked_compounds"].split("|")
                    for item in array:
                        sub_array = item.split(":")
                        l_met = template.compcompounds.get_by_id(
                            f'{sub_array[0]}_{row["compartment"].lower()}'
                        )
                        linked_mets[l_met] = float(sub_array[1])
                self.add_biomass_component(
                    metabolite,
                    row["class"].lower(),
                    float(row["coefficient"]),
                    row["coefficient_type"].upper(),
                    linked_mets,
                )
        return self

    @staticmethod
    def from_dict(d, template):
        self = MSTemplateBiomass(
            d["id"],
            d["name"],
            d["type"],
            d.get("dna", 0),
            d.get("rna", 0),
            d.get("protein", 0),
            d.get("lipid", 0),
            d.get("cellwall", 0),
            d.get("cofactor", 0),
            d.get("pigment", 0),
            d.get("carbohydrate", 0),
            d.get("energy", 0),
            d.get("other", 0)
        )
        for item in d["templateBiomassComponents"]:
            biocomp = MSTemplateBiomassComponent.from_dict(item, template)
            self.templateBiomassComponents.add(biocomp)
        self._template = template
        return self

    def add_biomass_component(
        self, metabolite, comp_class, coefficient, coefficient_type, linked_mets={}
    ):
        biocomp = MSTemplateBiomassComponent(
            metabolite, comp_class, coefficient, coefficient_type, linked_mets
        )
        self.templateBiomassComponents.add(biocomp)

    def get_or_create_metabolite(self, model, baseid, compartment=None, index=None):
        fullid = baseid
        if compartment:
            fullid += "_" + compartment
        tempid = fullid
        if index:
            fullid += index
        if fullid in model.metabolites:
            return model.metabolites.get_by_id(fullid)
        if tempid in self._template.compcompounds:
            met = self._template.compcompounds.get_by_id(tempid).to_metabolite(index)
            model.add_metabolites([met])
            return met
        logger.error(
            "Could not find biomass metabolite [%s] in model or template!",
            fullid,
        )

    def get_or_create_reaction(self, model, baseid, compartment=None, index=None):
        logger.debug(f"{baseid}, {compartment}, {index}")
        fullid = baseid
        if compartment:
            fullid += "_" + compartment
        tempid = fullid
        if index:
            fullid += index
        if fullid in model.reactions:
            return model.reactions.get_by_id(fullid)
        if tempid in self._template.reactions:
            rxn = self._template.reactions.get_by_id(tempid).to_reaction(model, index)
            model.add_reactions([rxn])
            return rxn
        newrxn = Reaction(fullid, fullid, "biomasses", 0, 1000)
        model.add_reactions(newrxn)
        return newrxn

    def build_biomass(self, model, index="0", classic=False, GC=0.5, add_to_model=True):
        types = [
            "cofactor",
            "pigment",
            "carbohydrate",
            "lipid",
            "cellwall",
            "protein",
            "dna",
            "rna",
            "energy",
            "other",
            "pigment",
            "carbohydrate"
        ]
        type_abundances = {
            "cofactor": self.cofactor,
            "pigment": self.pigment,
            "carbohydrate": self.carbohydrate,
            "lipid": self.lipid,
            "cellwall": self.cellwall,
            "protein": self.protein,
            "dna": self.dna,
            "rna": self.rna,
            "energy": self.energy,
            "pigment": self.pigment,
            "carbohydrate": self.carbohydrate,
        }
        # Creating biomass reaction object
        metabolites = {}
        biorxn = Reaction(self.id, self.name, "biomasses", 0, 1000)
        # Adding standard compounds for DNA, RNA, protein, and biomass
        specific_reactions = {"dna": None, "rna": None, "protein": None}
        exclusions = {"cpd17041_c": 1, "cpd17042_c": 1, "cpd17043_c": 1}
        if not classic and self.dna > 0:
            met = self.get_or_create_metabolite(model, "cpd11461", "c", index)
            specific_reactions["dna"] = self.get_or_create_reaction(
                model, "rxn05294", "c", index
            )
            specific_reactions["dna"].name = "DNA synthesis"
            if "rxn13783_c" + index in model.reactions:
                specific_reactions[
                    "dna"
                ].gene_reaction_rule = model.reactions.get_by_id(
                    "rxn13783_c" + index
                ).gene_reaction_rule
                specific_reactions["dna"].notes[
                    "modelseed_complex"
                ] = model.reactions.get_by_id("rxn13783_c" + index).notes[
                    "modelseed_complex"
                ]
                model.remove_reactions(
                    [model.reactions.get_by_id("rxn13783_c" + index)]
                )
            specific_reactions["dna"].subtract_metabolites(
                specific_reactions["dna"].metabolites
            )
            specific_reactions["dna"].add_metabolites({met: 1})
            metabolites[met] = 1
            metabolites[met] = -1 * self.dna
        if not classic and self.protein > 0:
            met = self.get_or_create_metabolite(model, "cpd11463", "c", index)
            specific_reactions["protein"] = self.get_or_create_reaction(
                model, "rxn05296", "c", index
            )
            specific_reactions["protein"].name = "Protein synthesis"
            if "rxn13782_c" + index in model.reactions:
                specific_reactions[
                    "protein"
                ].gene_reaction_rule = model.reactions.get_by_id(
                    "rxn13782_c" + index
                ).gene_reaction_rule
                specific_reactions["protein"].notes[
                    "modelseed_complex"
                ] = model.reactions.get_by_id("rxn13782_c" + index).notes[
                    "modelseed_complex"
                ]
                model.remove_reactions(
                    [model.reactions.get_by_id("rxn13782_c" + index)]
                )
            specific_reactions["protein"].subtract_metabolites(
                specific_reactions["protein"].metabolites
            )
            specific_reactions["protein"].add_metabolites({met: 1})
            metabolites[met] = -1 * self.protein
        if not classic and self.rna > 0:
            met = self.get_or_create_metabolite(model, "cpd11462", "c", index)
            specific_reactions["rna"] = self.get_or_create_reaction(
                model, "rxn05295", "c", index
            )
            specific_reactions["rna"].name = "mRNA synthesis"
            if "rxn13784_c" + index in model.reactions:
                specific_reactions[
                    "rna"
                ].gene_reaction_rule = model.reactions.get_by_id(
                    "rxn13784_c" + index
                ).gene_reaction_rule
                specific_reactions["rna"].notes[
                    "modelseed_complex"
                ] = model.reactions.get_by_id("rxn13784_c" + index).notes[
                    "modelseed_complex"
                ]
                model.remove_reactions(
                    [model.reactions.get_by_id("rxn13784_c" + index)]
                )
            specific_reactions["rna"].subtract_metabolites(
                specific_reactions["rna"].metabolites
            )
            specific_reactions["rna"].add_metabolites({met: 1})
            metabolites[met] = -1 * self.rna
        bio_type_hash = {}
        for type in types:
            for comp in self.templateBiomassComponents:
                if comp.metabolite.id in exclusions and not classic:
                    pass
                elif type == comp.comp_class:
                    met = self.get_or_create_metabolite(
                        model, comp.metabolite.id, None, index
                    )
                    if type not in bio_type_hash:
                        bio_type_hash[type] = {"items": [], "total_mw": 0}
                    if FBAHelper.metabolite_mw(met):
                        bio_type_hash[type]["total_mw"] += (
                            -1 * FBAHelper.metabolite_mw(met) * comp.coefficient / 1000
                        )
                    bio_type_hash[type]["items"].append(comp)
        for type in bio_type_hash:
            for comp in bio_type_hash[type]["items"]:
                coef = None
                if (
                    comp.coefficient_type == "MOLFRACTION"
                    or comp.coefficient_type == "MOLSPLIT"
                ):
                    coef = (
                        type_abundances[type] / bio_type_hash[type]["total_mw"]
                    ) * comp.coefficient
                elif comp.coefficient_type == "MULTIPLIER":
                    coef = type_abundances[type] * comp.coefficient
                elif comp.coefficient_type == "EXACT":
                    coef = comp.coefficient
                elif comp.coefficient_type == "AT":
                    coef = (
                        2
                        * comp.coefficient
                        * (1 - GC)
                        * (type_abundances[type] / bio_type_hash[type]["total_mw"])
                    )
                elif comp.coefficient_type == "GC":
                    coef = (
                        2
                        * comp.coefficient
                        * GC
                        * (type_abundances[type] / bio_type_hash[type]["total_mw"])
                    )
                if coef:
                    met = model.metabolites.get_by_id(comp.metabolite.id + index)
                    if type not in ("dna", "protein", "rna") or classic:
                        if met in metabolites:
                            metabolites[met] += coef
                        else:
                            metabolites[met] = coef
                    elif not classic:
                        coef = coef / type_abundances[type]
                        specific_reactions[type].add_metabolites({met: coef})
                    for l_met in comp.linked_metabolites:
                        met = self.get_or_create_metabolite(
                            model, l_met.id, None, index
                        )
                        if type not in ("dna", "protein", "rna") or classic:
                            if met in metabolites:
                                metabolites[met] += (
                                    coef * comp.linked_metabolites[l_met]
                                )
                            else:
                                metabolites[met] = coef * comp.linked_metabolites[l_met]
                        elif not classic:
                            specific_reactions[type].add_metabolites(
                                {met: coef * comp.linked_metabolites[l_met]}
                            )
        biorxn.annotation[SBO_ANNOTATION] = "SBO:0000629"
        biorxn.add_metabolites(metabolites)
        if add_to_model:
            if biorxn.id in model.reactions:
                model.remove_reactions([biorxn.id])
            model.add_reactions([biorxn])
        return biorxn

    def get_data(self):
        data = {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "dna": self.dna,
            "rna": self.rna,
            "protein": self.protein,
            "lipid": self.lipid,
            "cellwall": self.cellwall,
            "cofactor": self.cofactor,
            "pigment": self.pigment,
            "carbohydrate": self.carbohydrate,
            "energy": self.energy,
            "other": self.other,
            "templateBiomassComponents": [],
        }
        for comp in self.templateBiomassComponents:
            data["templateBiomassComponents"].append(comp.get_data())

        return data


class NewModelTemplateRole:
    def __init__(self, role_id, name, features=None, source="", aliases=None):
        """

        :param role_id:
        :param name:
        :param features:
        :param source:
        :param aliases:
        """
        self.id = role_id
        self.name = name
        self.source = source
        self.features = [] if features is None else features
        self.aliases = [] if aliases is None else aliases
        self._complexes = set()
        self._template = None

    @staticmethod
    def from_dict(d):
        return NewModelTemplateRole(
            d["id"], d["name"], d["features"], d["source"], d["aliases"]
        )

    def get_data(self):
        return {
            "id": self.id,
            "name": self.name,
            "aliases": self.aliases,
            "features": self.features,
            "source": self.source,
        }

    def __repr__(self):
        return "<%s %s at 0x%x>" % (self.__class__.__name__, self.id, id(self))

    def __str__(self):
        return "{}:{}".format(self.id, self.name)

    def _repr_html_(self):
        return """
        <table>
            <tr>
                <td><strong>Role identifier</strong></td><td>{id}</td>
            </tr><tr>
                <td><strong>Function</strong></td><td>{name}</td>
            </tr><tr>
                <td><strong>Memory address</strong></td>
                <td>{address}</td>
            </tr><tr>
                <td><strong>In {n_complexes} complexes</strong></td><td>
                    {complexes}</td>
            </tr>
        </table>""".format(
            id=self.id,
            name=format_long_string(self.name),
            address="0x0%x" % id(self),
            n_complexes=len(self._complexes),
            complexes=format_long_string(", ".join(r.id for r in self._complexes), 200),
        )


class NewModelTemplateComplex:
    def __init__(
        self, complex_id, name, source="", reference="", confidence=0, template=None
    ):
        """

        :param complex_id:
        :param name:
        :param source:
        :param reference:
        :param confidence:
        :param template:
        """
        self.id = complex_id
        self.name = name
        self.source = source
        self.reference = reference
        self.confidence = confidence
        self.roles = {}
        self._template = template

    @staticmethod
    def from_dict(d, template):
        protein_complex = NewModelTemplateComplex(
            d["id"], d["name"], d["source"], d["reference"], d["confidence"], template
        )
        for o in d["complexroles"]:
            role = template.roles.get_by_id(o["templaterole_ref"].split("/")[-1])
            protein_complex.add_role(
                role, o["triggering"] == 1, o["optional_role"] == 1
            )
        return protein_complex

    def add_role(self, role: NewModelTemplateRole, triggering=True, optional=False):
        """
        Add role (function) to the complex
        :param role:
        :param triggering:
        :param optional:
        :return:
        """
        self.roles[role] = (triggering, optional)

    def get_data(self):
        complex_roles = []
        for role in self.roles:
            triggering, optional = self.roles[role]
            complex_roles.append(
                {
                    "triggering": 1 if triggering else 0,
                    "optional_role": 1 if optional else 0,
                    "templaterole_ref": "~/roles/id/" + role.id,
                }
            )
        return {
            "id": self.id,
            "name": self.name,
            "reference": self.reference,
            "confidence": self.confidence,
            "source": self.source,
            "complexroles": complex_roles,
        }

    def __str__(self):
        return " and ".join(
            map(
                lambda x: "{}{}{}".format(
                    x[0].id, ":trig" if x[1][0] else "", ":optional" if x[1][1] else ""
                ),
                self.roles.items(),
            )
        )

    def __repr__(self):
        return "<%s %s at 0x%x>" % (self.__class__.__name__, self.id, id(self))

    def _repr_html_(self):

        return """
        <table>
            <tr>
                <td><strong>Complex identifier</strong></td><td>{id}</td>
            </tr><tr>
                <td><strong>Name</strong></td><td>{name}</td>
            </tr><tr>
                <td><strong>Memory address</strong></td>
                <td>{address}</td>
            </tr><tr>
                <td><strong>Contains {n_complexes} role(s)</strong></td><td>
                    {complexes}</td>
            </tr>
        </table>""".format(
            id=self.id,
            name=format_long_string(self.name),
            address="0x0%x" % id(self),
            n_complexes=len(self.roles),
            complexes=format_long_string(
                ", ".join(
                    "{}:{}:{}:{}".format(r[0].id, r[0].name, r[1][0], r[1][1])
                    for r in self.roles.items()
                ),
                200,
            ),
        )


class MSTemplateCompartment:
    def __init__(
        self, compartment_id: str, name: str, ph: float, hierarchy=0, aliases=None
    ):
        self.id = compartment_id
        self.name = name
        self.ph = ph
        self.hierarchy = hierarchy
        self.aliases = [] if aliases is None else list(aliases)
        self._template = None

    @staticmethod
    def from_dict(d):
        return MSTemplateCompartment(
            d["id"], d["name"], d["pH"], d["hierarchy"], d["aliases"]
        )

    def get_data(self):
        return {
            "id": self.id,
            "name": self.name,
            "pH": self.ph,
            "aliases": self.aliases,
            "hierarchy": self.hierarchy,
        }


class MSTemplate:
    def __init__(
        self,
        template_id,
        name="",
        domain="",
        template_type="",
        version=1,
        info=None,
        args=None,
    ):
        self.id = template_id
        self.name = name
        self.domain = domain
        self.template_type = template_type
        self.__VERSION__ = version
        self.biochemistry_ref = ""
        self.compartments = DictList()
        self.biomasses = DictList()
        self.reactions = DictList()
        self.compounds = DictList()
        self.compcompounds = DictList()
        self.roles = DictList()
        self.complexes = DictList()
        self.pathways = DictList()
        self.subsystems = DictList()
        self.drains = None

    ################# Replaces biomass reactions from an input TSV table ############################
    def overwrite_biomass_from_table(
        self,
        filename_or_df,
        bio_id,
        name,
        type,
        dna,
        rna,
        protein,
        lipid,
        cellwall,
        cofactor,
        pigment,
        carbohydrate,
        energy,
        other,
    ):
        if isinstance(filename_or_df, str):
            filename_or_df = pd.read_table(filename_or_df)
        newbio = MSTemplateBiomass.from_table(
            filename_or_df,
            self,
            bio_id,
            name,
            type,
            dna,
            rna,
            protein,
            lipid,
            cellwall,
            cofactor,
            pigment,
            carbohydrate,
            energy,
            other,
        )
        if newbio.id in self.biomasses:
            self.biomasses.remove(newbio.id)
        self.biomasses.add(newbio)

    def add_drain(self, compound_id, lower_bound, upper_bound):
        if compound_id not in self.compcompounds:
            raise ValueError(f"{compound_id} not in template")
        if lower_bound > upper_bound:
            raise ValueError(
                f"lower_bound: {lower_bound} must not be > than upper_bound: {upper_bound}"
            )
        if self.drains is None:
            self.drains = {}
        self.drains[self.compcompounds.get_by_id(compound_id)] = (
            lower_bound,
            upper_bound,
        )

    def add_sink(self, compound_id, default_upper_bound=1000):
        self.add_drain(compound_id, 0, default_upper_bound)

    def add_demand(self, compound_id, default_lower_bound=-1000):
        self.add_drain(compound_id, default_lower_bound, 0)

    def add_compartments(self, compartments: list):
        """

        :param compartments:
        :return:
        """
        duplicates = list(filter(lambda x: x.id in self.compartments, compartments))
        if len(duplicates) > 0:
            logger.error(
                "unable to add compartments [%s] already present in the template",
                duplicates,
            )
            return None

        for x in compartments:
            x._template = self
        self.compartments += compartments

    def add_roles(self, roles: list):
        """

        :param roles:
        :return:
        """
        duplicates = list(filter(lambda x: x.id in self.roles, roles))
        if len(duplicates) > 0:
            logger.error(
                "unable to add roles [%s] already present in the template", duplicates
            )
            return None

        for x in roles:
            x._template = self
        self.roles += roles

    def add_complexes(self, complexes: list):
        """

        :param complexes:
        :return:
        """
        duplicates = list(filter(lambda x: x.id in self.complexes, complexes))
        if len(duplicates) > 0:
            logger.error(
                "unable to add comp compounds [%s] already present in the template",
                duplicates,
            )
            return None

        roles_to_add = []
        for x in complexes:
            x._template = self
            roles_rep = {}
            for role in x.roles:
                r = role
                if role.id not in self.roles:
                    roles_to_add.append(role)
                else:
                    r = self.roles.get_by_id(role.id)
                roles_rep[r] = x.roles[role]
                r._complexes.add(x)
            x.roles = roles_rep

        self.roles += roles_to_add
        self.complexes += complexes

    def add_compounds(self, compounds: list):
        """

        :param compounds:
        :return:
        """
        duplicates = list(filter(lambda x: x.id in self.compounds, compounds))
        if len(duplicates) > 0:
            logger.error(
                "unable to add compounds [%s] already present in the template",
                duplicates,
            )
            return None

        for x in compounds:
            x._template = self
        self.compounds += compounds

    def add_comp_compounds(self, comp_compounds: list):
        """
        Add a compartment compounds (i.e., species) to the template
        :param comp_compounds:
        :return:
        """
        duplicates = list(filter(lambda x: x.id in self.compcompounds, comp_compounds))
        if len(duplicates) > 0:
            logger.error(
                "unable to add comp compounds [%s] already present in the template",
                duplicates,
            )
            return None

        for x in comp_compounds:
            x._template = self
            if x.cpd_id in self.compounds:
                x._template_compound = self.compounds.get_by_id(x.cpd_id)
                x._template_compound.species.add(x)
        self.compcompounds += comp_compounds

    def add_biomasses(self, biomasses: list):
        """
        Add biomasses to the template
        :param biomasses:
        :return:
        """
        duplicates = list(filter(lambda x: x.id in self.biomasses, biomasses))
        if len(duplicates) > 0:
            logger.error(
                "unable to add biomasses [%s] already present in the template",
                duplicates,
            )
            return None

        for x in biomasses:
            x._template = self
        self.biomasses += biomasses

    def add_reactions(self, reaction_list: list):
        """

        :param reaction_list:
        :return:
        """
        duplicates = list(filter(lambda x: x.id in self.reactions, reaction_list))
        if len(duplicates) > 0:
            logger.error(
                "unable to add reactions [%s] already present in the template",
                duplicates,
            )
            return None

        for x in reaction_list:
            metabolites_replace = {}
            complex_replace = set()
            x._template = self
            for comp_cpd, coefficient in x.metabolites.items():
                if comp_cpd.id not in self.compcompounds:
                    self.add_comp_compounds([comp_cpd])
                metabolites_replace[
                    self.compcompounds.get_by_id(comp_cpd.id)
                ] = coefficient
            for cpx in x.complexes:
                if cpx.id not in self.complexes:
                    self.add_complexes([cpx])
                complex_replace.add(self.complexes.get_by_id(cpx.id))

            x._metabolites = metabolites_replace
            x._update_awareness()
            x.complexes = complex_replace

        self.reactions += reaction_list

    def get_role_sources(self):
        pass

    def get_complex_sources(self):
        pass

    def get_complex_from_role(self, roles):
        cpx_role_str = ";".join(sorted(roles))
        if cpx_role_str in self.role_set_to_cpx:
            return self.role_set_to_cpx[cpx_role_str]
        return None

    @staticmethod
    def get_last_id_value(object_list, s):
        last_id = 0
        for o in object_list:
            if o.id.startswith(s):
                number_part = id[len(s) :]
                if len(number_part) == 5:
                    if int(number_part) > last_id:
                        last_id = int(number_part)
        return last_id

    def get_complex(self, id):
        return self.complexes.get_by_id(id)

    def get_reaction(self, id):
        return self.reactions.get_by_id(id)

    def get_role(self, id):
        return self.roles.get_by_id(id)

    # def _to_object(self, key, data):
    #    if key == 'compounds':
    #        return NewModelTemplateCompound.from_dict(data, self)
    #    if key == 'compcompounds':
    #        return NewModelTemplateCompCompound.from_dict(data, self)
    #    #if key == 'reactions':
    #    #    return NewModelTemplateReaction.from_dict(data, self)
    #    if key == 'roles':
    #        return NewModelTemplateRole.from_dict(data, self)
    #    if key == 'subsystems':
    #        return NewModelTemplateComplex.from_dict(data, self)
    #    return super()._to_object(key, data)

    def get_data(self):
        """
        typedef structure {
            modeltemplate_id id;
            string name;
            string type;
            string domain;
            Biochemistry_ref biochemistry_ref;
            list < TemplateRole > roles;
            list < TemplateComplex > complexes;
            list < TemplateCompound > compounds;
            list < TemplateCompCompound > compcompounds;
            list < TemplateCompartment > compartments;
            list < NewTemplateReaction > reactions;
            list < NewTemplateBiomass > biomasses;
            list < TemplatePathway > pathways;
        } NewModelTemplate;
        """

        d = {
            "__VERSION__": self.__VERSION__,
            "id": self.id,
            "name": self.name,
            "domain": self.domain,
            "biochemistry_ref": self.biochemistry_ref,
            "type": "Test",
            "compartments": list(map(lambda x: x.get_data(), self.compartments)),
            "compcompounds": list(map(lambda x: x.get_data(), self.compcompounds)),
            "compounds": list(map(lambda x: x.get_data(), self.compounds)),
            "roles": list(map(lambda x: x.get_data(), self.roles)),
            "complexes": list(map(lambda x: x.get_data(), self.complexes)),
            "reactions": list(map(lambda x: x.get_data(), self.reactions)),
            "biomasses": list(map(lambda x: x.get_data(), self.biomasses)),
            "pathways": [],
            "subsystems": [],
        }

        if self.drains is not None:
            d["drain_list"] = {c.id: t for c, t in self.drains.items()}

        return d

    def _repr_html_(self):
        """
        taken from cobra.core.Model :)
        :return:
        """
        return """
        <table>
            <tr>
                <td><strong>ID</strong></td>
                <td>{id}</td>
            </tr><tr>
                <td><strong>Memory address</strong></td>
                <td>{address}</td>
            </tr><tr>
                <td><strong>Number of metabolites</strong></td>
                <td>{num_metabolites}</td>
            </tr><tr>
                <td><strong>Number of species</strong></td>
                <td>{num_species}</td>
            </tr><tr>
                <td><strong>Number of reactions</strong></td>
                <td>{num_reactions}</td>
            </tr><tr>
                <td><strong>Number of biomasses</strong></td>
                <td>{num_bio}</td>
            </tr><tr>
                <td><strong>Number of roles</strong></td>
                <td>{num_roles}</td>
            </tr><tr>
                <td><strong>Number of complexes</strong></td>
                <td>{num_complexes}</td>
            </tr>
          </table>""".format(
            id=self.id,
            address="0x0%x" % id(self),
            num_metabolites=len(self.compounds),
            num_species=len(self.compcompounds),
            num_reactions=len(self.reactions),
            num_bio=len(self.biomasses),
            num_roles=len(self.roles),
            num_complexes=len(self.complexes),
        )
    
    def remove_reactions(
        self,
        reactions: Union[str, Reaction, List[Union[str, Reaction]]],
        remove_orphans: bool = False,
    ) -> None:
        """Remove reactions from the template.

        The change is reverted upon exit when using the model as a context.

        Parameters
        ----------
        reactions : list or reaction or str
            A list with reactions (`cobra.Reaction`), or their id's, to remove.
            Reaction will be placed in a list. Str will be placed in a list and used to
            find the reaction in the model.
        remove_orphans : bool, optional
            Remove orphaned genes and metabolites from the model as
            well (default False).
        """
        if isinstance(reactions, str) or hasattr(reactions, "id"):
            warn("need to pass in a list")
            reactions = [reactions]

        for reaction in reactions:
            # Make sure the reaction is in the model
            try:
                reaction = self.reactions[self.reactions.index(reaction)]
            except ValueError:
                warn(f"{reaction} not in {self}")

            else:
                self.reactions.remove(reaction)
                
                """ for met in reaction._metabolites:
                    if reaction in met._reaction:
                        met._reaction.remove(reaction)
                        if context:
                            context(partial(met._reaction.add, reaction))
                        if remove_orphans and len(met._reaction) == 0:
                            self.remove_metabolites(met)

                for gene in reaction._genes:
                    if reaction in gene._reaction:
                        gene._reaction.remove(reaction)
                        if context:
                            context(partial(gene._reaction.add, reaction))

                        if remove_orphans and len(gene._reaction) == 0:
                            self.genes.remove(gene)
                            if context:
                                context(partial(self.genes.add, gene))

                # remove reference to the reaction in all groups
                associated_groups = self.get_associated_groups(reaction)
                for group in associated_groups:
                    group.remove_members(reaction) """
    
    #*************************Curation Functions*************************
    def auto_fix_protons(self):
        for rxn in self.reactions:
            mb = rxn.check_mass_balance()
            if 'charge' in mb and mb.get('H') == mb.get('charge'):
                print(f'auto fix charge for {rxn.id}')
                rxn.add_metabolites({
                    self.compcompounds.cpd00067_c: -1 * mb['charge']
                })

class MSTemplateBuilder:
    def __init__(
        self,
        template_id,
        name="",
        domain="",
        template_type="",
        version=1,
        info=None,
        biochemistry=None,
        biomasses=None,
        pathways=None,
        subsystems=None,
    ):
        self.id = template_id
        self.version = version
        self.name = name
        self.domain = domain
        self.template_type = template_type
        self.compartments = []
        self.biomasses = []
        self.roles = []
        self.complexes = []
        self.compounds = []
        self.compartment_compounds = []
        self.reactions = []
        self.info = info
        self.biochemistry_ref = None
        self.drains = {}

    @staticmethod
    def from_dict(d, info=None, args=None):
        """

        :param d:
        :param info:
        :param args:
        :return:
        """
        builder = MSTemplateBuilder(
            d["id"], d["name"], d["domain"], d["type"], d["__VERSION__"], None
        )
        builder.compartments = d["compartments"]
        builder.roles = d["roles"]
        builder.complexes = d["complexes"]
        builder.compounds = d["compounds"]
        builder.compartment_compounds = d["compcompounds"]
        builder.reactions = d["reactions"]
        builder.biochemistry_ref = d["biochemistry_ref"]
        builder.biomasses = d["biomasses"]

        return builder

    @staticmethod
    def from_template(template):
        b = MSTemplateBuilder()
        for o in template.compartments:
            b.compartments.append(copy.deepcopy(o))

        return b

    def with_compound_modelseed(self, seed_id, modelseed):
        pass

    def with_role(self, template_rxn, role_ids, auto_complex=False):
        # TODO: copy from template curation
        complex_roles = template_rxn.get_complex_roles()
        role_match = {}
        for o in role_ids:
            role_match[o] = False
        for complex_id in complex_roles:
            for o in role_match:
                if o in complex_roles[complex_id]:
                    role_match[o] = True
        all_roles_present = True
        for o in role_match:
            all_roles_present &= role_match[o]
        if all_roles_present:
            logger.debug("ignore %s all present in atleast 1 complex", role_ids)
            return None
        complex_id = self.template.get_complex_from_role(role_ids)
        if complex_id is None:
            logger.warning("unable to find complex for %s", role_ids)
            if auto_complex:
                role_names = set()
                for role_id in role_ids:
                    role = self.template.get_role(role_id)
                    role_names.add(role["name"])
                logger.warning("build complex for %s", role_names)
                complex_id = self.template.add_complex_from_role_names(role_names)
            else:
                return None
        complex_ref = "~/complexes/id/" + complex_id
        if complex_ref in template_rxn.data["templatecomplex_refs"]:
            logger.debug("already contains complex %s, role %s", role_ids, complex_ref)
            return None
        return complex_ref

    def with_compound(self):
        pass

    def with_compound_compartment(self):
        pass

    def with_compartment(self, cmp_id, name, ph=7, index="0"):
        res = list(filter(lambda x: x["id"] == cmp_id, self.compartments))
        if len(res) > 0:
            return res[0]

        self.compartments.append(
            {
                "id": cmp_id,
                "name": name,
                "aliases": [],
                "hierarchy": 3,  # TODO: what is this?
                "index": index,
                "pH": ph,
            }
        )

        return self

    def build(self):
        template = MSTemplate(
            self.id, self.name, self.domain, self.template_type, self.version
        )
        template.add_compartments(
            list(map(lambda x: MSTemplateCompartment.from_dict(x), self.compartments))
        )
        template.add_compounds(
            list(map(lambda x: MSTemplateMetabolite.from_dict(x), self.compounds))
        )
        template.add_comp_compounds(
            list(
                map(
                    lambda x: MSTemplateSpecies.from_dict(x), self.compartment_compounds
                )
            )
        )
        template.add_roles(
            list(map(lambda x: NewModelTemplateRole.from_dict(x), self.roles))
        )
        template.add_complexes(
            list(
                map(
                    lambda x: NewModelTemplateComplex.from_dict(x, template),
                    self.complexes,
                )
            )
        )
        template.add_reactions(
            list(
                map(lambda x: MSTemplateReaction.from_dict(x, template), self.reactions)
            )
        )
        template.biomasses += list(
            list(
                map(lambda x: MSTemplateBiomass.from_dict(x, template), self.biomasses)
            )
        )

        for compound_id, (lb, ub) in self.drains.items():
            template.add_drain(compound_id, lb, ub)

        return template
