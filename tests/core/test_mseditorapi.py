# -*- coding: utf-8 -*-
from modelseedpy.core.mseditorapi import MSEditorAPI, MSEquation
from tests.test_data.mock_data import mock_model_ecoli_core
import pytest


@pytest.fixture
def editor():
    return MSEditorAPI()


@pytest.fixture
def example_model():
    return mock_model_ecoli_core()


@pytest.fixture
def example_model2():
    return mock_model_ecoli_core()


def test_remove_reactions1(editor, example_model):
    """
    testing for remove_reaction()
    """
    # remove valid reactions
    total_reactions = len(example_model.reactions)
    lst = ["rxn00171", "rxn00248"]
    editor.remove_reactions(example_model, lst)
    assert len(example_model.reactions) == total_reactions - len(lst)


def test_remove_reactions2(editor, example_model):
    """
    remove invalid reactions
    """
    lst = ["C"]
    with pytest.raises(Exception):
        editor.remove_reactions(example_model, lst)


def test_edit_reaction1(editor, example_model):
    """
    testing for edit_reaction()
    change a reversible reaction to a forward reaction and change the gpr
    """
    rxn = "rxn00198_c0"
    editor.edit_reaction(example_model, rxn, "=>", "(b0001 and b0002) or b1010")
    reaction = example_model.reactions.get_by_id(rxn)
    assert reaction.reversibility is False
    assert reaction.lower_bound == 0
    assert reaction.upper_bound == 1000
    assert len(reaction.genes) == 3


def test_edit_reaction2(editor, example_model):
    """
    testing for edit_reaction()
    change a forward reaction to a reversible reaction
    """
    rxn = "rxn19316_c0"
    editor.edit_reaction(example_model, rxn, "<=>")
    reaction = example_model.reactions.get_by_id(rxn)
    assert reaction.reversibility is True
    assert reaction.lower_bound == -1000
    assert reaction.upper_bound == 1000


def test_edit_reaction3(editor, example_model):
    """
    testing for edit_reaction()
    change a forward reaction to a reverse reaction
    """
    rxn = "rxn08288_c0"
    editor.edit_reaction(example_model, rxn, "<=")
    reaction = example_model.reactions.get_by_id(rxn)
    assert reaction.reversibility is False
    assert reaction.lower_bound == -1000
    assert reaction.upper_bound == 0


def test_copy_model_reactions1(editor, example_model, example_model2):
    """
    testing for copy_model_reaction()
    copying reactions from one list to another
    """
    lst = ["rxn00198_c0", "rxn08288_c0"]
    editor.remove_reactions(example_model2, lst)
    assert len(example_model2.reactions) == 95 - len(lst)
    editor.copy_model_reactions(example_model2, example_model, lst)
    assert len(example_model2.reactions) == 95


def test_copy_model_reactions2(editor, example_model, example_model2):
    """
    testing for copy_model_reaction()
    copying a reaction that already in the original model
    """
    lst = ["rxn00198_c0", "rxn08288_c0"]
    editor.copy_model_reactions(example_model2, example_model, lst)
    assert len(example_model2.reactions) == 95


def test_copy_model_reactions3(editor, example_model, example_model2):
    """
    testing for copy_model_reaction()
    copying a reaction that doesn't exist in the original model
    """
    lst = ["C", "rxn00198"]
    with pytest.raises(Exception):
        editor.copy_model_reactions(example_model2, example_model, lst)
    assert len(example_model2.reactions) == 95


def test_copy_all_model_reactions1(editor, example_model, example_model2):
    pass
    """
    testing for copy_all_model_reactions()
    copying all reactions from a source model that don't already exist in the receiving model
    """
    lst = ["rxn00198"]
    editor.remove_reactions(example_model2, lst)
    editor.copy_all_model_reactions(example_model2, example_model)
    assert len(example_model2.reactions) == 95


def test_build_from_palsson_string_1():
    """
    test for building a modelseed equaiton form a string
    """
    eq = MSEquation.build_from_palsson_string(
        "cpd00001 + cpd00002[e] <= (2)cpd00003 + cpd00004"
    )
    # assert(test.equation == "{('cpd00001', 'c'): -1, ('cpd00002', 'e'): -1, ('cpd00003', 'c'): 2, ('cpd00004', 'c'): 1}")
    assert eq.direction == "<"


def test_build_from_palsson_string_2():
    eq = MSEquation.build_from_palsson_string(
        "cpd00001 + cpd00002[e] <=> (2)cpd00003 + cpd00004"
    )
    # assert(test.equation == "{('cpd00001', 'c'): -1, ('cpd00002', 'e'): -1, ('cpd00003', 'c'): 2, ('cpd00004', 'c'): 1}")
    assert eq.direction == "="


def test_build_from_palsson_string_3():
    eq = MSEquation.build_from_palsson_string(
        "cpd00001 + cpd00002[e] => (2)cpd00003 + cpd00004"
    )
    # assert(test.equation == "{('cpd00001', 'c'): -1, ('cpd00002', 'e'): -1, ('cpd00003', 'c'): 2, ('cpd00004', 'c'): 1}")
    assert eq.direction == ">"


def test_build_from_palsson_string_4(editor):
    eq = MSEquation.build_from_palsson_string(
        "cpd00001 + cpd00002[e] = (2)cpd00003 + cpd00004"
    )
    # assert(test.equation == "{('cpd00001', 'c'): -1, ('cpd00002', 'e'): -1, ('cpd00003', 'c'): 2, ('cpd00004', 'c'): 1}")
    assert eq.direction == "?"


def _stoich_by_id(reaction):
    return {met.id: coef for met, coef in reaction.metabolites.items()}


def test_add_custom_reaction(editor, example_model):
    """
    testing for add_custom_reaction()
    add a reaction parsed from a string, with metabolites already in the model
    """
    equation = MSEquation.build_from_palsson_string(
        "cpd00002 + cpd00001 => cpd00008 + cpd00009 + cpd00067", "c0"
    )
    editor.add_custom_reaction(example_model, "bio2", equation)
    reaction = example_model.reactions.get_by_id("bio2")
    assert _stoich_by_id(reaction) == {
        "cpd00002_c0": -1,
        "cpd00001_c0": -1,
        "cpd00008_c0": 1,
        "cpd00009_c0": 1,
        "cpd00067_c0": 1,
    }
    assert reaction.bounds == (0, 1000)


def test_edit_biomass_compound_new_reaction(editor, example_model):
    """
    testing for edit_biomass_compound()
    a biomass reaction absent from the model is created
    """
    editor.edit_biomass_compound(example_model, "bio9", "cpd00001_c0", -1)
    biomass = example_model.reactions.get_by_id("bio9")
    assert _stoich_by_id(biomass) == {"cpd00001_c0": -1}
    editor.edit_biomass_compound(example_model, "bio9", "cpd00001_c0", -2)
    assert _stoich_by_id(biomass) == {"cpd00001_c0": -2}


ATP_HYDROLYSIS = "cpd00002 + cpd00001 {} cpd00008 + cpd00009 + cpd00067"
ATP_HYDROLYSIS_STOICH = {
    "cpd00002_c0": -1,
    "cpd00001_c0": -1,
    "cpd00008_c0": 1,
    "cpd00009_c0": 1,
    "cpd00067_c0": 1,
}


def test_add_custom_reaction_metabolite_ids(editor, example_model):
    """
    the documented signature: a stoichiometry keyed by metabolite ids
    """
    editor.add_custom_reaction(
        example_model, ATP_HYDROLYSIS_STOICH, ">", "rxn90001", gpr="b0001"
    )
    reaction = example_model.reactions.get_by_id("rxn90001")
    assert _stoich_by_id(reaction) == ATP_HYDROLYSIS_STOICH
    assert reaction.bounds == (0, 1000)
    assert reaction.gene_reaction_rule == "b0001"
    assert "b0001" in example_model.genes
    assert reaction.model is example_model


def test_add_custom_reaction_msequation_call(editor, example_model):
    """
    the older call add_custom_reaction(model, rxn_id, MSEquation) still works
    """
    equation = MSEquation.build_from_palsson_string(ATP_HYDROLYSIS.format("=>"), "c0")
    editor.add_custom_reaction(example_model, "bio2", equation)
    reaction = example_model.reactions.get_by_id("bio2")
    assert _stoich_by_id(reaction) == ATP_HYDROLYSIS_STOICH
    assert reaction.bounds == (0, 1000)

    # its fourth positional argument is the gpr, and genome is accepted
    editor.add_custom_reaction(example_model, "bio3", equation, "b0001", None)
    assert example_model.reactions.bio3.gene_reaction_rule == "b0001"
    editor.add_custom_reaction(example_model, "bio4", equation, genome=None)
    assert "bio4" in example_model.reactions


def test_add_custom_reaction_parsed_stoichiometry(editor, example_model):
    """
    the (compound, compartment) keys of a parsed MSEquation become metabolites
    """
    equation = MSEquation.build_from_palsson_string(ATP_HYDROLYSIS.format("=>"), "c0")
    editor.add_custom_reaction(example_model, equation.stoich, ">", "rxn90002")
    reaction = example_model.reactions.get_by_id("rxn90002")
    assert _stoich_by_id(reaction) == ATP_HYDROLYSIS_STOICH


@pytest.mark.parametrize(
    "arrow, bounds",
    [("=>", (0, 1000)), ("<=", (-1000, 0)), ("<=>", (-1000, 1000))],
)
def test_add_custom_reaction_parsed_direction(editor, example_model, arrow, bounds):
    """
    the direction emitted by build_from_palsson_string sets the bounds
    """
    equation = MSEquation.build_from_palsson_string(ATP_HYDROLYSIS.format(arrow), "c0")
    editor.add_custom_reaction(example_model, "bio2", equation)
    assert example_model.reactions.bio2.bounds == bounds
    editor.add_custom_reaction(
        example_model, equation.stoich, equation.direction, "rxn90003"
    )
    assert example_model.reactions.rxn90003.bounds == bounds


def test_add_custom_reaction_rejects_bad_input(editor, example_model):
    """
    an unknown direction or a metabolite absent from the model raises
    """
    reaction_count = len(example_model.reactions)
    with pytest.raises(ValueError):
        editor.add_custom_reaction(
            example_model, ATP_HYDROLYSIS_STOICH, "sideways", "rxn90004"
        )
    # "=" without an arrow is parsed as the unknown direction "?"
    equation = MSEquation.build_from_palsson_string(ATP_HYDROLYSIS.format("="), "c0")
    with pytest.raises(ValueError):
        editor.add_custom_reaction(example_model, "bio2", equation)
    # the default compartment "c" names cpd00001_c, which the model lacks
    equation = MSEquation.build_from_palsson_string(ATP_HYDROLYSIS.format("=>"))
    with pytest.raises(ValueError):
        editor.add_custom_reaction(example_model, "bio2", equation)
    assert len(example_model.reactions) == reaction_count


@pytest.fixture
def biochem():
    from modelseedpy.biochem.modelseed_biochem import ModelSEEDBiochem

    return ModelSEEDBiochem(
        {"cpd00001": {"name": "H2O"}, "cpd00067": {"name": "H+"}},
        {
            "rxn90001": {
                "name": "test reaction",
                "stoichiometry": '-1:cpd00001:0:0:"H2O";1:cpd00067:1:0:"H+"',
            }
        },
    )


@pytest.mark.parametrize(
    "direction, bounds",
    [
        (">", (0, 1000)),
        ("=>", (0, 1000)),
        ("forward", (0, 1000)),
        ("<", (-1000, 0)),
        ("<=", (-1000, 0)),
        ("backward", (-1000, 0)),
        ("=", (-1000, 1000)),
        ("<=>", (-1000, 1000)),
        ("reversible", (-1000, 1000)),
    ],
)
def test_add_ms_reaction_direction(editor, example_model, biochem, direction, bounds):
    """
    add_ms_reaction accepts both direction vocabularies
    """
    editor.add_ms_reaction(example_model, "rxn90001", biochem, direction=direction)
    reaction = example_model.reactions.get_by_id("rxn90001")
    assert reaction.bounds == bounds
    assert len(reaction.metabolites) == 2


@pytest.mark.parametrize("direction", ["<=>>", "reverse"])
def test_add_ms_reaction_unknown_direction(editor, example_model, biochem, direction):
    """
    an unknown direction raises instead of prompting for another with input()
    """
    with pytest.raises(ValueError):
        editor.add_ms_reaction(example_model, "rxn90001", biochem, direction=direction)
    assert "rxn90001" not in example_model.reactions


def test_edit_reaction_clears_gpr(editor, example_model):
    """
    an empty gpr clears the reaction's gpr; None leaves it alone
    """
    rxn = "rxn00198_c0"
    editor.edit_reaction(example_model, rxn, gpr="b0001")
    editor.edit_reaction(example_model, rxn, gpr=None)
    assert example_model.reactions.get_by_id(rxn).gene_reaction_rule == "b0001"
    editor.edit_reaction(example_model, rxn, gpr="")
    reaction = example_model.reactions.get_by_id(rxn)
    assert reaction.gene_reaction_rule == ""
    assert len(reaction.genes) == 0


def test_edit_reaction_accepts_genome(editor, example_model):
    """
    the genome argument is still accepted
    """
    rxn = "rxn00198_c0"
    editor.edit_reaction(example_model, rxn, "=>", "b0001", genome=None)
    editor.edit_reaction(example_model, rxn, "=>", "b0001", None)
    assert example_model.reactions.get_by_id(rxn).lower_bound == 0


# The call styles below are the ones cshenry/main's docs, notebooks and tests use


def test_add_ms_reaction_keyword_call(editor, example_model, biochem):
    """
    the keyword call of examples/Model Reconstruction/add_ms_reaction.ipynb, and
    the default direction, forward
    """
    editor.add_ms_reaction(
        example_model,
        rxn_id="rxn90001",
        modelseed=biochem,
        compartment_equivalents={"0": "c0", "1": "e0"},
        direction="backward",
    )
    assert example_model.reactions.rxn90001.bounds == (-1000, 0)
    example_model.reactions.rxn90001.remove_from_model()
    editor.add_ms_reaction(example_model, "rxn90001", biochem)
    reaction = example_model.reactions.rxn90001
    assert reaction.bounds == (0, 1000)
    assert reaction.name == "test reaction"
    assert {met.compartment for met in reaction.metabolites} == {"c0", "e0"}


def test_add_custom_reaction_older_keywords(editor, example_model):
    """
    the documented add_custom_reaction(model, rxn_id, MSEquation, gpr=None),
    with its parameters given by keyword
    """
    equation = MSEquation.build_from_palsson_string(ATP_HYDROLYSIS.format("=>"), "c0")
    editor.add_custom_reaction(
        model=example_model, rxn_id="bio2", MSEquation=equation, gpr="b0001"
    )
    reaction = example_model.reactions.bio2
    assert _stoich_by_id(reaction) == ATP_HYDROLYSIS_STOICH
    assert reaction.bounds == (0, 1000)
    assert reaction.gene_reaction_rule == "b0001"
    editor.add_custom_reaction(example_model, "bio3", MSEquation=equation, genome=None)
    assert _stoich_by_id(example_model.reactions.bio3) == ATP_HYDROLYSIS_STOICH


def test_add_custom_reaction_equation_attribute(editor, example_model):
    """
    an object with the original .equation and .direction attributes, such as the
    MSEquation of examples/Flux Analysis/FBA Model functions.ipynb, is accepted
    """

    class OlderEquation:
        def __init__(self, stoichiometry, d):
            self.equation = stoichiometry
            self.direction = d

    stoich = MSEquation.build_from_palsson_string(
        ATP_HYDROLYSIS.format("<=>"), "c0"
    ).equation
    editor.add_custom_reaction(example_model, "bio2", OlderEquation(stoich, "="))
    reaction = example_model.reactions.bio2
    assert _stoich_by_id(reaction) == ATP_HYDROLYSIS_STOICH
    assert reaction.bounds == (-1000, 1000)


@pytest.mark.parametrize("direction", ["left", "reversable", "?"])
def test_add_custom_reaction_older_direction_words_raise(
    editor, example_model, direction
):
    """
    the "left" and "reversable" directions that the older add_custom_reaction read
    are not in the direction table, and raise like any other unknown direction
    """
    equation = MSEquation(
        MSEquation.build_from_palsson_string(ATP_HYDROLYSIS.format("=>"), "c0").stoich,
        direction,
    )
    with pytest.raises(ValueError):
        editor.add_custom_reaction(example_model, "bio2", equation)
    assert "bio2" not in example_model.reactions


def test_add_custom_reaction_needs_stoichiometry(editor, example_model):
    with pytest.raises(TypeError):
        editor.add_custom_reaction(example_model, direction=">", rxnID="rxn90005")


def test_msequation_original_arguments():
    """
    MSEquation(stoichiometry, d) and its .equation attribute still work
    """
    stoich = {("cpd00001", "c0"): -1, ("cpd00067", "c0"): 1}
    for equation in [
        MSEquation(stoich, ">"),
        MSEquation(stoich, d=">"),
        MSEquation(stoich, direction=">"),
    ]:
        assert equation.direction == ">"
        assert equation.equation is stoich
        assert equation.stoich is stoich
    equation.equation = {("cpd00001", "c0"): -2}
    assert equation.stoich == {("cpd00001", "c0"): -2}
    with pytest.raises(TypeError):
        MSEquation(stoich, ">", direction=">")


def test_build_from_palsson_string_stoichiometry():
    """
    the stoichiometry that the commented assertions of the tests above expect
    """
    eq = MSEquation.build_from_palsson_string(
        "cpd00001 + cpd00002[e] <= (2)cpd00003 + cpd00004", default_group="c"
    )
    assert eq.equation == {
        ("cpd00001", "c"): -1,
        ("cpd00002", "e"): -1,
        ("cpd00003", "c"): 2,
        ("cpd00004", "c"): 1,
    }
    eq = MSEquation.build_from_palsson_string(
        "octapb + cysi__L[e] => (2)dhap[c0] + prbatp", "c0"
    )
    assert eq.equation == {
        ("octapb", "c0"): -1,
        ("cysi__L", "e"): -1,
        ("dhap", "c0"): 2,
        ("prbatp", "c0"): 1,
    }


@pytest.mark.parametrize(
    "equation_string",
    [
        "cpd00001 + cpd00002[e]  (2)cpd00003 + cpd00004",
        "cpd00001 + cpd00002[e => (2)cpd00003 + cpd00004",
        "cpd00001 + cpd00002e] => (2)cpd00003 + cpd00004",
        "cpd00001 + cpd00002[e] => (2cpd00003 + cpd00004",
        "cpd00001 + cpd00002[e] => 2)cpd00003 + cpd00004",
        "cpd00001 + cpd00002[e] => (2cpd00003[e] + cpd00004",
    ],
)
def test_build_from_palsson_string_malformed(equation_string):
    """
    the malformed strings of examples/Flux Analysis/FBA Model functions.ipynb raise
    """
    with pytest.raises(ValueError):
        MSEquation.build_from_palsson_string(equation_string)


def test_edit_reaction_keyword_call(editor, example_model):
    """
    the documented edit_reaction(model, rxn_id, direction=None, gpr=None)
    """
    rxn = "rxn19316_c0"
    editor.edit_reaction(example_model, rxn_id=rxn, direction="<=>", gpr="b0001")
    reaction = example_model.reactions.get_by_id(rxn)
    assert reaction.bounds == (-1000, 1000)
    assert reaction.gene_reaction_rule == "b0001"
