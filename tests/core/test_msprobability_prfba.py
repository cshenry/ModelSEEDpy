# -*- coding: utf-8 -*-
"""MSProbability.prFBA on a single model.

The model is e_coli_core (tests/test_data) with compartment suffixes, as in
test_msgapfill.py, and every internal reaction renamed to a "rxn"-prefixed id carrying
notes["probability"]: prFBA weights only "rxn" reactions and "EX_" exchanges. Biomass
(BIOMASS_Ecoli_core_w_GAM_c0) and ATPM_c0 keep their ids, so their coefficient is 0.
"""
import json
import math
import os

import cobra
import pytest

from modelseedpy.core.msprobability import MSProbability
from modelseedpy.fbapkg.elementuptakepkg import ElementUptakePkg

BIOMASS = "BIOMASS_Ecoli_core_w_GAM_c0"
PROBS = (0.0, 0.25, 0.5, 0.75, 1.0)


def _build():
    path = os.path.join(
        os.path.dirname(__file__), "..", "test_data", "e_coli_core.json"
    )
    with open(path) as fh:
        model_json = json.load(fh)
    model_json["compartments"] = {
        k + "0": v for k, v in model_json["compartments"].items()
    }
    metabolites = {}
    for m in model_json["metabolites"]:
        m["id"] += "0"
        m["compartment"] += "0"
        metabolites[m["id"]] = m
    index = 0
    for r in model_json["reactions"]:
        r["metabolites"] = {i + "0": v for i, v in r["metabolites"].items()}
        comps = {metabolites[k]["compartment"] for k in r["metabolites"]}
        if r["id"].startswith("EX_"):
            r["id"] += "0"
        elif r["id"] in ("BIOMASS_Ecoli_core_w_GAM", "ATPM"):
            r["id"] += "_" + (list(comps)[0] if len(comps) == 1 else "c0")
        else:
            r["id"] = "rxn{:05d}_c0".format(index)
            r["notes"] = {"probability": str(PROBS[index % len(PROBS)])}
            index += 1
    return cobra.io.from_json(json.dumps(model_json))


@pytest.fixture(scope="module")
def base_model():
    return _build()


@pytest.fixture
def model(base_model):
    # prFBA changes the model it is given, and a second call on the same object would
    # find its ElementUptakePkg already registered: every call gets a fresh copy
    return base_model.copy()


def _rel(a, b):
    return abs(a - b) / max(1.0, abs(a), abs(b))


def _max_objective_under_carbon_cap(model):
    """The released code's floor: max of the model's objective under C uptake <= 100."""
    ref = model.copy()
    ElementUptakePkg(ref).build_package({"C": 100})
    return ref.slim_optimize()


# ---------------------------------------------------------------- released signature
def test_bare_model_and_one_item_list_agree(base_model):
    """The released code raised TypeError (len of a Model) on the bare model and
    AttributeError (MSModelUtil of a list) on the list."""
    sol_bare = MSProbability.prFBA(base_model.copy())
    sol_list = MSProbability.prFBA([base_model.copy()])
    assert sol_bare.status == "optimal"
    assert sol_list.status == "optimal"
    assert sol_bare.objective_value > 0
    assert _rel(sol_bare.objective_value, sol_list.objective_value) < 1e-9


def test_dict_environment_of_the_models_own_medium_matches_none(base_model):
    """environment=None keeps the model's bounds (the released code called
    add_medium(None) and raised); a dict environment still goes through add_medium."""
    m_none, m_env = base_model.copy(), base_model.copy()
    sol_none = MSProbability.prFBA(m_none, environment=None)
    sol_env = MSProbability.prFBA(m_env, environment=dict(base_model.medium))
    assert sol_env.status == "optimal"
    assert _rel(sol_none.objective_value, sol_env.objective_value) < 1e-9
    # a smaller glucose uptake lowers the floor
    m_low = base_model.copy()
    env = dict(base_model.medium)
    env["EX_glc__D_e0"] = 5.0
    MSProbability.prFBA(m_low, environment=env)
    assert m_low.constraints["min_value"].lb < m_env.constraints["min_value"].lb - 1e-6


def test_biomass_is_held_at_95_percent_of_its_maximum(model):
    expected_max = _max_objective_under_carbon_cap(model)
    assert expected_max > 0.1
    sol = MSProbability.prFBA(model)
    assert sol.status == "optimal"
    floor = model.constraints["min_value"]
    assert math.isclose(floor.lb, 0.95 * expected_max, rel_tol=1e-9)
    # the floor is on the biomass reaction (the objective on entry)
    bio = model.reactions.get_by_id(BIOMASS)
    floor_vars = {v.name for v in floor.variables}
    assert floor_vars == {bio.forward_variable.name, bio.reverse_variable.name}
    # minimizing positive costs puts biomass on its floor
    assert math.isclose(sol.fluxes[BIOMASS], 0.95 * expected_max, rel_tol=1e-6)


def test_objective_coefficients(model):
    min_prob, prob_exp, ex_weight = 0.05, 2, 7.0
    sol = MSProbability.prFBA(
        model, min_prob=min_prob, prob_exp=prob_exp, ex_weight=ex_weight
    )
    assert sol.status == "optimal"
    assert model.objective.direction == "min"
    variables = [
        v for r in model.reactions for v in (r.forward_variable, r.reverse_variable)
    ]
    coefs = model.objective.get_linear_coefficients(variables)
    n_rxn = 0
    for r in model.reactions:
        if r.id.startswith("rxn"):
            p = float(r.notes["probability"])
            expected = max(min_prob, 1 - p**prob_exp)
            n_rxn += 1
        elif r.id.startswith("EX_"):
            expected = ex_weight
        else:
            expected = 0
        assert math.isclose(coefs[r.forward_variable], expected, abs_tol=1e-12), r.id
        assert math.isclose(coefs[r.reverse_variable], expected, abs_tol=1e-12), r.id
    assert n_rxn > 50
    # every probability level and the floor are exercised: p = 1 -> min_prob
    assert {
        float(r.notes["probability"]) for r in model.reactions if r.id.startswith("rxn")
    } == set(PROBS)
    # the solver's objective is the priced flux
    priced = sum(coefs[v] * v.primal for v in variables)
    assert _rel(priced, sol.objective_value) < 1e-7


def test_silent_unless_printLP(base_model, capsys, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    # copy before clearing the capture: some solver interfaces (gurobi) report the LP
    # read that cobra's Model.copy performs, and that is not prFBA's output
    m_quiet, m_loud = base_model.copy(), base_model.copy()
    capsys.readouterr()
    MSProbability.prFBA(m_quiet)
    assert capsys.readouterr().out == ""
    assert not (tmp_path / "prFBA.lp").exists()
    MSProbability.prFBA(m_loud, printLP=True)
    out = capsys.readouterr().out
    assert "min_value" in out and "C_elements" in out
    assert (tmp_path / "prFBA.lp").exists()


# ---------------------------------------------------------------- reactions without a note
def _strip_note(model):
    rxn = next(
        r
        for r in model.reactions
        if r.id.startswith("rxn") and r.notes.get("probability") == "0.5"
    )
    del rxn.notes["probability"]
    return rxn


def test_missing_probability_raises_by_default_before_changing_the_model(model):
    rxn = _strip_note(model)
    objective_before = str(model.objective.expression)
    with pytest.raises(KeyError, match=rxn.id):
        MSProbability.prFBA(model)
    assert "min_value" not in model.constraints
    assert "C_elements" not in model.constraints
    assert str(model.objective.expression) == objective_before


def test_missing_probability_keyword_sets_the_value(base_model):
    m_missing = base_model.copy()
    rxn = _strip_note(m_missing)
    sol_missing = MSProbability.prFBA(m_missing, missing_probability=0.0)
    coef = m_missing.objective.get_linear_coefficients(
        [m_missing.reactions.get_by_id(rxn.id).forward_variable]
    )
    assert list(coef.values()) == [1.0]  # max(min_prob, 1 - 0)
    m_zero = base_model.copy()
    m_zero.reactions.get_by_id(rxn.id).notes["probability"] = "0"
    sol_zero = MSProbability.prFBA(m_zero)
    assert _rel(sol_missing.objective_value, sol_zero.objective_value) < 1e-9


# ---------------------------------------------------------------- the objective on entry
def test_floor_follows_the_objective_on_entry_unless_biomass_id(base_model):
    sol_bio = MSProbability.prFBA(base_model.copy())
    # ATPM as the objective on entry: the floor holds ATP maintenance, not growth
    m_atpm = base_model.copy()
    m_atpm.objective = "ATPM_c0"
    MSProbability.prFBA(m_atpm)
    atpm = m_atpm.reactions.get_by_id("ATPM_c0")
    assert {v.name for v in m_atpm.constraints["min_value"].variables} == {
        atpm.forward_variable.name,
        atpm.reverse_variable.name,
    }
    # biomass_id moves the floor back onto biomass and reproduces the biomass run
    m_fix = base_model.copy()
    m_fix.objective = "ATPM_c0"
    sol_fix = MSProbability.prFBA(m_fix, biomass_id=BIOMASS)
    assert _rel(sol_fix.objective_value, sol_bio.objective_value) < 1e-9
    assert math.isclose(sol_fix.fluxes[BIOMASS], sol_bio.fluxes[BIOMASS], rel_tol=1e-6)


# ---------------------------------------------------------------- the community path
def _member(mid, carbon, uptake):
    """A three-reaction member (uptake, rxn transport, biomass) with formulas for the
    carbon cap; the fixture of MSCommunity's tests/test_f_biomass_drains.py."""
    form = {
        carbon: "C6H12O6",
        "cpd00002": "C10H13N5O13P3",
        "cpd00001": "H2O",
        "cpd00008": "C10H13N5O10P2",
        "cpd00009": "HO4P",
        "cpd00067": "H",
        "cpd11416": "R",
    }
    m = cobra.Model(mid)
    # the ATP-hydrolysis metabolites are needed by the community build, which adds rxn00062
    mets = {
        k: cobra.Metabolite(k, name=k, compartment=k[-2:], formula=form[k[:-3]])
        for k in (
            f"{carbon}_e0",
            f"{carbon}_c0",
            "cpd00002_c0",
            "cpd00001_c0",
            "cpd00008_c0",
            "cpd00009_c0",
            "cpd00067_c0",
            "cpd11416_c0",
        )
    }
    m.add_metabolites(list(mets.values()))
    ex = cobra.Reaction(f"EX_{carbon}_e0", lower_bound=-float(uptake), upper_bound=1000)
    ex.add_metabolites({mets[f"{carbon}_e0"]: -1})
    tr = cobra.Reaction("rxn10000_c0", lower_bound=0, upper_bound=1000)
    tr.add_metabolites({mets[f"{carbon}_e0"]: -1, mets[f"{carbon}_c0"]: 1})
    tr.notes["probability"] = "0.5"
    bio = cobra.Reaction("bio1", lower_bound=0, upper_bound=1000)
    bio.add_metabolites({mets[f"{carbon}_c0"]: -1, mets["cpd11416_c0"]: 1})
    sink = cobra.Reaction("SK_cpd11416_c0", lower_bound=0, upper_bound=1000)
    sink.add_metabolites({mets["cpd11416_c0"]: -1})
    m.add_reactions([ex, tr, bio, sink])
    m.objective = "bio1"
    return m


def test_community_path_builds_the_carbon_cap_once():
    """Two models: the released code raised PackageError on the second ElementUptakePkg
    (it sat outside the community condition). Only that is checked here; what the
    community rows do is MSCommunity's business."""
    # only this path needs the MSCommunity package
    pytest.importorskip("mscommunity")
    models = [_member("memA", "cpd00027", 10), _member("memB", "cpd00082", 4)]
    sol = MSProbability.prFBA(models, environment={"cpd00027": 10, "cpd00082": 4})
    assert sol.status == "optimal"


# ---------------------------------------------------------------- no growth, infeasible
def test_no_growth_raises_instead_of_an_all_zero_solution(base_model):
    """environment={} closes every uptake; with ATP maintenance released the model is
    feasible but cannot grow, so the floor would be 0 and the minimization would return the
    all-zero vector as 'optimal'."""
    m = base_model.copy()
    m.reactions.get_by_id("ATPM_c0").lower_bound = 0
    with pytest.raises(ValueError, match="all-zero"):
        MSProbability.prFBA(m, environment={}, biomass_id=BIOMASS)


def test_infeasible_medium_raises_a_clear_error(base_model):
    """With ATP maintenance at its lower bound and no uptake the model is infeasible; the
    released code handed the solver a NaN bound (opaque solver error)."""
    m = base_model.copy()
    assert m.reactions.get_by_id("ATPM_c0").lower_bound > 0
    with pytest.raises(ValueError, match="infeasible"):
        MSProbability.prFBA(m, environment={}, biomass_id=BIOMASS)


def test_min_growth_none_keeps_the_unchecked_behaviour(base_model):
    m = base_model.copy()
    m.reactions.get_by_id("ATPM_c0").lower_bound = 0
    sol = MSProbability.prFBA(m, environment={}, biomass_id=BIOMASS, min_growth=None)
    assert sol.status == "optimal"
    assert abs(sol.objective_value) < 1e-9
    assert all(abs(v) < 1e-9 for v in sol.fluxes)
