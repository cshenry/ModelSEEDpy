# -*- coding: utf-8 -*-
"""The MSModelUtil API that MSCommunity, CommScores and MSMinimalMedia call."""
import pytest
from cobra import Metabolite, Model, Reaction
from optlang.symbolics import Zero

from modelseedpy.core.exceptions import ModelError
from modelseedpy.core.msmedia import MSMedia
from modelseedpy.core.msmodelutl import MSModelUtil
from tests.test_data.mock_data import mock_model_ecoli_core


def _model():
    model = mock_model_ecoli_core(seed=True)
    model.reactions.get_by_id("EX_glc__D_e").id = "EX_cpd00027_e0"
    model.reactions.get_by_id("EX_o2_e").id = "EX_cpd00007_e0"
    model.repair()
    return model


# ---------------------------------------------------------------- constructor
def test_default_constructor_changes_nothing():
    model = _model()
    medium, n_cons = dict(model.medium), len(model.constraints)
    util = MSModelUtil(model)
    assert util.model is model
    assert util.id == model.id
    assert util.climit is None and util.o2limit is None
    assert model.medium == medium and len(model.constraints) == n_cons
    assert util.biomass_objective == "Biomass_Ecoli_core"


def test_copy_leaves_the_original_untouched():
    model = _model()
    medium, n_cons = dict(model.medium), len(model.constraints)
    media = MSMedia.from_dict({"cpd00027": 5, "cpd00007": 20})
    util = MSModelUtil(model, copy=True, environment=media, climit=60)
    assert util.model is not model
    assert util.model.medium["EX_cpd00027_e0"] == 5
    assert "C_elements" in util.model.constraints
    # the environment and the limits went to the copy only
    assert model.medium == medium
    assert len(model.constraints) == n_cons


def test_copy_raises_when_the_objective_value_changes(monkeypatch):
    model = _model()
    original_copy = Model.copy

    def corrupting_copy(self):
        copied = original_copy(self)
        copied.reactions.get_by_id("EX_cpd00027_e0").lower_bound = -1
        return copied

    monkeypatch.setattr(Model, "copy", corrupting_copy)
    with pytest.raises(ModelError):
        MSModelUtil(model, copy=True)


@pytest.mark.parametrize(
    "climit, o2limit, expected",
    [(60, None, (60, 20)), (None, 10, (30, 10)), (90, 15, (90, 15))],
)
def test_uptake_limits(climit, o2limit, expected):
    model = _model()
    util = MSModelUtil(model, climit=climit, o2limit=o2limit)
    assert (util.climit, util.o2limit) == expected
    assert "C_elements" in model.constraints
    assert model.reactions.get_by_id("EX_cpd00007_e0").lower_bound == -expected[1]


@pytest.mark.parametrize(
    "climit, o2limit", [(None, None), (False, False), (False, None), (None, False)]
)
def test_no_uptake_limits(climit, o2limit):
    model = _model()
    util = MSModelUtil(model, climit=climit, o2limit=o2limit)
    assert util.climit is None and util.o2limit is None
    assert "C_elements" not in model.constraints
    assert model.reactions.get_by_id("EX_cpd00007_e0").lower_bound == -1000


def test_o2limit_does_not_open_an_anaerobic_medium():
    model = _model()
    model.reactions.get_by_id("EX_cpd00007_e0").lower_bound = 0
    MSModelUtil(model, climit=60)
    assert model.reactions.get_by_id("EX_cpd00007_e0").lower_bound == 0


# ---------------------------------------------------------------- reaction lists
def _toy_model():
    model = Model("toy")
    glc_e = Metabolite("cpd00027_e0", formula="C6H12O6", compartment="e0")
    glc_c = Metabolite("cpd00027_c0", formula="C6H12O6", compartment="c0")
    h2o_e = Metabolite("cpd00001_e0", formula="H2O", compartment="e0")
    unk_e = Metabolite("cpd99999_e0", compartment="e0")
    bio_c = Metabolite("cpd11416_c0", compartment="c0")
    bio_c1 = Metabolite("cpd11416_c1", compartment="c1")
    bio_c2 = Metabolite("cpd11416_c2", compartment="c2")
    reactions = {
        "EX_cpd00027_e0": {glc_e: -1},
        "EX_cpd00001_e0": {h2o_e: -1},
        "EX_cpd99999_e0": {unk_e: -1},
        "rxn05573_c0": {glc_e: -1, glc_c: 1},
        "rxn00001_c0": {glc_c: -1, h2o_e: 1},
        "bio1": {glc_c: -1, bio_c: 1},
        # cpd11416 on both sides looks like a transport, but is biomass
        "bio2": {bio_c: -1, bio_c1: 1},
        "bio3": {bio_c1: -1, bio_c2: 1},
    }
    for rxn_id, stoich in reactions.items():
        rxn = Reaction(rxn_id, lower_bound=-1000, upper_bound=1000)
        rxn.add_metabolites(stoich)
        model.add_reactions([rxn])
    return model


def test_transport_internal_and_exchange_lists():
    util = MSModelUtil(_toy_model())
    # both biomass reactions are excluded, also when they follow one another
    assert [r.id for r in util.transport_list()] == ["rxn05573_c0"]
    assert [r.id for r in util.internal_list()] == [
        "rxn00001_c0",
        "bio1",
        "bio2",
        "bio3",
    ]
    assert {m.id for m in util.exchange_mets_list()} == {
        "cpd00027_e0",
        "cpd00001_e0",
        "cpd99999_e0",
    }


def test_carbon_exchanges():
    util = MSModelUtil(_toy_model())
    assert [r.id for r in util.carbon_exchange_list()] == [
        "EX_cpd00027_e0",
        "EX_cpd99999_e0",
    ]
    assert [r.id for r in util.carbon_exchange_list(include_unknown=False)] == [
        "EX_cpd00027_e0"
    ]
    assert {m.id for m in util.carbon_exchange_mets_list(False)} == {"cpd00027_e0"}


def test_metabolites_set_of_no_reactions_is_empty():
    util = MSModelUtil(_toy_model())
    assert util.metabolites_set([]) == set()
    assert util.metabolites_set(ids=True) == {m.id for m in util.model.metabolites}


def test_standard_exchanges():
    model = _toy_model()
    MSModelUtil(model).standard_exchanges()
    ex = model.reactions.get_by_id("EX_cpd00027_e0")
    ex.add_metabolites({model.metabolites.get_by_id("cpd00027_c0"): 1})
    with pytest.raises(ModelError, match="EX_cpd00027_e0"):
        MSModelUtil(model).standard_exchanges()


# ---------------------------------------------------------------- constraints and objectives
def test_constraint_helpers():
    model = _model()
    util = MSModelUtil(model)
    glc = model.reactions.get_by_id("EX_cpd00027_e0")
    for name in ("a_regularization", "b_regularization", "other"):
        util.create_constraint(
            model.problem.Constraint(Zero, lb=-5, ub=None, name=name),
            coef={glc.forward_variable: 1, glc.reverse_variable: -1},
        )
    cons = model.constraints["a_regularization"]
    assert cons.get_linear_coefficients([glc.forward_variable]) == {
        glc.forward_variable: 1
    }
    # every constraint whose name contains the text is removed
    util.remove_constraint("_regularization")
    assert "a_regularization" not in model.constraints
    assert "b_regularization" not in model.constraints
    assert "other" in model.constraints
    util.remove_cons_vars([model.constraints["other"]])
    assert "other" not in model.constraints
    var = model.problem.Variable("extra", lb=0, ub=1)
    util.add_cons_vars([var])
    assert "extra" in model.variables


def test_objective_helpers():
    model = _model()
    util = MSModelUtil(model)
    growth = model.slim_optimize()
    util.add_minimal_objective_cons(0.5 * growth)
    assert model.constraints["min_value"].lb == pytest.approx(0.5 * growth)
    util.add_minimal_objective_cons(0.6 * growth)
    assert model.constraints["min_value"].lb == pytest.approx(0.6 * growth)
    glc = model.reactions.get_by_id("EX_cpd00027_e0")
    util.add_objective(Zero, "min", {glc.reverse_variable: 1})
    assert model.objective.direction == "min"
    # the least glucose that still gives 60% of the growth
    assert 0 < model.slim_optimize() < 10
    util.add_objective(glc.flux_expression, "max")
    assert model.objective.direction == "max"


def test_run_fba():
    model = _model()
    util = MSModelUtil(model)
    fba = util.run_fba()
    pfba = util.run_fba(pfba=True)
    assert pfba.fluxes["Biomass_Ecoli_core"] == pytest.approx(fba.objective_value)
    fva = util.run_fba(fva_reactions=["EX_cpd00027_e0"])
    assert list(fva.index) == ["EX_cpd00027_e0"]


def test_add_timeout():
    model = _model()
    MSModelUtil(model).add_timeout(7)
    assert model.solver.configuration.timeout == 7


@pytest.mark.parametrize("pfba", [False, True])
def test_costless_excreta_leaves_the_model_as_it_was(pfba):
    model = _model()
    objective = str(model.objective.expression)
    n_cons = len(model.constraints)
    excreta = MSModelUtil(model).costless_excreta(pfba=pfba)
    assert "co2_e" in excreta and "h2o_e" in excreta
    assert all(not ex.startswith("EX_") for ex in excreta)
    assert str(model.objective.expression) == objective
    assert model.objective.direction == "max"
    assert len(model.constraints) == n_cons
