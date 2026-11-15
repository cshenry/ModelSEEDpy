# -*- coding: utf-8 -*-
"""Offline role matching and draft-build regression tests (no optimization)."""
import json
from pathlib import Path

import pytest
from cobra import Configuration

from modelseedpy.core.msbuilder import MSBuilder
from modelseedpy.core.msgenome import MSFeature, MSGenome, normalize_role
from modelseedpy.core.mstemplate import (
    MSTemplate,
    MSTemplateBuilder,
    MSTemplateCompartment,
    MSTemplateMetabolite,
    MSTemplateSpecies,
    MSTemplateReaction,
    NewModelTemplateRole,
    NewModelTemplateComplex,
)


@pytest.fixture(autouse=True)
def glpk_models():
    config = Configuration()
    previous = config.solver
    config.solver = "glpk"
    yield
    config.solver = previous


def genome_with(*functions):
    genome = MSGenome()
    features = []
    for i, function in enumerate(functions):
        feature = MSFeature(feature_id=f"g{i}", sequence="M")
        feature.add_ontology_term(ontology_term="RAST", value=function)
        features.append(feature)
    genome.add_features(feature_list=features)
    return genome


def small_template():
    template = MSTemplate(template_id="alias_test")
    template.compartments.append(MSTemplateCompartment("c", "Cytosol", 3))
    template.add_compounds([MSTemplateMetabolite("cpd_test", "C", "test")])
    species = MSTemplateSpecies("cpd_test_c", 0, "c", "cpd_test")
    template.add_comp_compounds([species])
    roles = [
        NewModelTemplateRole(
            "r1", "First enzyme", aliases=["Shared alias", "alias two"]
        ),
        NewModelTemplateRole("r2", "Second enzyme", aliases=["Shared alias"]),
    ]
    template.add_roles(roles)
    complex_ = NewModelTemplateComplex("cpx_test", "test")
    for role in roles:
        complex_.add_role(role=role, triggering=True, optional=False)
    template.add_complexes([complex_])
    reaction = MSTemplateReaction("rxn_test_c", "rxn_test", "test", "", 0, 1000)
    reaction.add_metabolites({species: -1})
    reaction.add_complexes([complex_])
    template.add_reactions([reaction])
    return template


def draft(template, genome, **options):
    return MSBuilder(genome=genome, template=template).build_base_model(
        model_or_id="test", annotate_with_rast=False, **options
    )


def test_alias_only_and_shared_alias():
    template = small_template()
    genome = genome_with("SHARED ALIAS")
    assert "rxn_test_c0" not in draft(template, genome).reactions
    model = draft(
        template, genome, match_role_aliases=True, allow_incomplete_complexes=False
    )
    assert {gene.id for gene in model.reactions.rxn_test_c0.genes} == {"g0"}
    builder = MSBuilder(genome=genome, template=template)
    matches = builder._get_template_reaction_complexes(
        template_reaction=template.reactions[0], match_role_aliases=True
    )["cpx_test"]
    assert matches["r1"][3] == matches["r2"][3] == {"g0"}


def test_name_and_multiple_aliases_union_genes():
    model = draft(
        small_template(),
        genome_with("First enzyme", "Shared alias", "alias two"),
        match_role_aliases=True,
    )
    assert {gene.id for gene in model.reactions.rxn_test_c0.genes} == {"g0", "g1", "g2"}


def test_incomplete_required_triggering_subunit():
    template, genome = small_template(), genome_with("First enzyme")
    assert (
        "rxn_test_c0"
        in draft(template, genome, allow_incomplete_complexes=True).reactions
    )
    assert (
        "rxn_test_c0"
        not in draft(template, genome, allow_incomplete_complexes=False).reactions
    )


def legacy_name_matching(self, template_reaction, **unused):
    """Name-only matcher copied from the pre-change builder."""
    result = {}
    for complex_ in template_reaction.get_complexes():
        result[complex_.id] = {}
        for role, (triggering, optional) in complex_.roles.items():
            name = normalize_role(role.name)
            result[complex_.id][role.id] = [
                name,
                triggering,
                optional,
                set(self.search_name_to_genes.get(name, set())),
            ]
    return result


def signature(model):
    # Canonicalize GPRs: set iteration can change textual operand ordering.
    from cobra.core.gene import GPR
    from sympy import srepr

    return {
        reaction.id: srepr(GPR.from_string(reaction.gene_reaction_rule).as_symbolic())
        for reaction in model.reactions
    }


@pytest.mark.parametrize("core", [False, True], ids=["in_code", "core_template"])
def test_defaults_match_unpatched_name_only_builder(core, monkeypatch):
    if core:
        path = (
            Path(__file__).parents[2] / "modelseedpy/data/templates/template_core.json"
        )
        template = MSTemplateBuilder.from_dict(json.loads(path.read_text())).build()
        assert any(role.aliases for role in template.roles)
    else:
        template = small_template()
    # Exercise names, aliases and unmatched roles together.
    functions = [role.name for role in template.roles[::3]]
    functions += [alias for role in template.roles for alias in role.aliases]
    genome = genome_with(*functions)
    actual = signature(draft(template, genome))
    explicit = signature(
        draft(
            template, genome, match_role_aliases=False, allow_incomplete_complexes=True
        )
    )
    monkeypatch.setattr(
        MSBuilder, "_get_template_reaction_complexes", legacy_name_matching
    )
    expected = signature(draft(template, genome))
    assert actual == explicit == expected
    assert actual
