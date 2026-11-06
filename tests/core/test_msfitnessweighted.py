# -*- coding: utf-8 -*-
import copy
import json
import math
import os

import cobra
import pytest

from modelseedpy import MSFitnessWeightedAnalysis, MSMedia
from modelseedpy.core import msfitnessweighted as fw
from modelseedpy.core.mstemplate import MSTemplateBuilder
from modelseedpy.fbapkg.fitnessweightedfluxpkg import (
    FitnessWeightedFluxPkg,
    validate_penalties,
)

BIOMASS = "BIOMASS_Ecoli_core_w_GAM_c0"
DATA = os.path.join(os.path.dirname(__file__), "..", "test_data")


def _template_dict():
    with open(os.path.join(DATA, "template_core_bigg.json")) as fh:
        return json.load(fh)


@pytest.fixture
def template():
    return MSTemplateBuilder.from_dict(_template_dict()).build()


def _model(ko=None, extra=None):
    """e_coli_core with ModelSEED-style compartment suffixes (as in test_msgapfill.py)."""
    with open(os.path.join(DATA, "e_coli_core.json")) as fh:
        model_json = json.load(fh)
    model_json["compartments"] = {
        k + "0": v for (k, v) in model_json["compartments"].items()
    }
    metabolites = {}
    for m in model_json["metabolites"]:
        m["id"] += "0"
        m["compartment"] += "0"
        metabolites[m["id"]] = m
    for r in model_json["reactions"]:
        r["metabolites"] = {i + "0": v for (i, v) in r["metabolites"].items()}
        compartments = set(
            [metabolites[k]["compartment"] for k in r["metabolites"].keys()]
        )
        if r["id"].endswith("_e"):
            r["id"] += "0"
        elif len(compartments) == 1:
            r["id"] += "_" + list(compartments)[0]
        else:
            r["id"] += "_c0"
    model_json["reactions"] = [
        x for x in model_json["reactions"] if x["id"] not in (ko or [])
    ]
    model = cobra.io.from_json(json.dumps(model_json))
    if extra:
        extra(model)
    return model


@pytest.fixture
def glucose():
    return MSMedia.from_dict(
        {
            "glc__D": (-10, 1000),
            "o2": (-1000, 1000),
            "h": (-1000, 1000),
            "h2o": (-1000, 1000),
            "pi": (-1000, 1000),
            "co2": (-1000, 1000),
            "nh4": (-1000, 1000),
        }
    )


def _duplicate_pgi(model):
    """Add PGI2_c0: an exact copy of PGI_c0 catalysed by a made-up gene g_pgi2."""
    pgi = model.reactions.get_by_id("PGI_c0")
    dup = cobra.Reaction(
        "PGI2_c0", lower_bound=pgi.lower_bound, upper_bound=pgi.upper_bound
    )
    dup.add_metabolites(pgi.metabolites)
    model.add_reactions([dup])
    dup.gene_reaction_rule = "g_pgi2"


# ---------------------------------------------------------------- pure helpers
def test_fitness_penalty_tiers():
    assert fw.fitness_penalty(0.0) == pytest.approx(1.0)
    assert fw.fitness_penalty(2.0) == pytest.approx(1.0 - 0.9 * math.tanh(1.0))
    assert fw.fitness_penalty(100.0) == pytest.approx(0.1, abs=1e-6)
    assert fw.fitness_penalty(5.0) > 0.1  # approached, not reached, for finite fitness


def test_normalize_fitness_shapes():
    rows = [
        {"gene": "a", "fitness": -3.0, "t_score": -5.0},
        {"gene": "b", "fitness": 1.0},
    ]
    assert fw.normalize_fitness(rows) == {"a": (-3.0, -5.0), "b": (1.0, None)}
    assert fw.normalize_fitness({"a": (-3.0, -5.0)}) == {"a": (-3.0, -5.0)}
    assert fw.normalize_fitness({"a": {"fitness": -3.0, "t_score": -5.0}}) == {
        "a": (-3.0, -5.0)
    }
    assert fw.normalize_fitness({"a": float("nan")}) == {}


def test_classify_commitment():
    assert fw.classify_commitment(1.0, 2.0, 1.5) == fw.ESSENTIAL
    assert fw.classify_commitment(-2.0, -1.0, 0.0) == fw.ESSENTIAL
    assert fw.classify_commitment(0.0, 2.0, 1.0) == fw.ACTIVE
    assert fw.classify_commitment(0.0, 0.0, 0.0) == fw.BLOCKED
    assert fw.classify_commitment(-1.0, 2.0, 0.0) == fw.UNUSED


def test_classify_impact_and_score_edge():
    assert fw.classify_impact(-3.0, -5.0) == (True, 1.0, "tier1")
    assert fw.classify_impact(-1.0, -5.0) == (True, 0.5, "tier2")
    assert fw.classify_impact(-3.0, -3.9) == (False, 0.0, None)  # |t| < 4
    assert fw.classify_impact(-3.0, None) == (
        False,
        0.0,
        None,
    )  # missing t never significant
    assert fw.classify_impact(3.0, 9.0) == (
        False,
        0.0,
        None,
    )  # positive fitness: no impact
    assert fw.classify_impact(None, None, is_essential=True) == (
        True,
        1.0,
        "essentiality",
    )
    tier1 = fw.classify_impact(-3.0, -5.0)
    none = fw.classify_impact(0.1, 0.2)
    assert fw.score_edge(fw.ESSENTIAL, tier1) == (fw.STRONG_POS, 1.0)
    assert fw.score_edge(fw.ESSENTIAL, none, ko_ratio=0.0) == (fw.STRONG_NEG, -1.0)
    assert fw.score_edge(fw.ESSENTIAL, none, ko_ratio=0.9) == (
        fw.NEUTRAL,
        0.0,
    )  # isozyme gate
    assert fw.score_edge(fw.ACTIVE, fw.classify_impact(-1.0, -5.0)) == (fw.POS, 0.25)
    assert fw.score_edge(fw.ACTIVE, none) == (fw.MILD_NEG, -0.5)
    assert fw.score_edge(fw.UNUSED, tier1) == (fw.UNEXPLAINED, 0.0)
    assert fw.score_edge(fw.BLOCKED, none) == (fw.NEUTRAL, 0.0)
    assert fw.score_edge(fw.ESSENTIAL, tier1, is_gapfill=True) == (fw.NEUTRAL, 0.0)
    assert (
        fw.dominant_verdict([fw.POS, fw.MILD_NEG]) == fw.MILD_NEG
    )  # tie, same rank: alphabetical
    assert (
        fw.dominant_verdict([fw.POS, fw.STRONG_NEG]) == fw.STRONG_NEG
    )  # tie: stronger class wins


def test_flux_pkg_coefficients():
    model = _model()
    pkg = FitnessWeightedFluxPkg(model)
    pkg.build_package({"PGI_c0": 2.0, "PFK_c0": {">": 3.0, "<": 5.0}})
    coef = model.objective.get_linear_coefficients(model.objective.variables)
    pgi, pfk = model.reactions.PGI_c0, model.reactions.PFK_c0
    assert model.objective.direction == "min"
    assert coef[pgi.forward_variable] == 2.0 and coef[pgi.reverse_variable] == 2.0
    assert coef[pfk.forward_variable] == 3.0 and coef[pfk.reverse_variable] == 5.0
    with pytest.raises(ValueError):
        validate_penalties({"PGI_c0": 0.0})
    with pytest.raises(ValueError):
        validate_penalties({"PGI_c0": {">": 1.0}})


# ---------------------------------------------------------------- the analysis
def test_penalty_tiers_on_model(template):
    # without these reactions the template has candidates to offer
    ko = ["GLCpts_c0", "CYTBD_c0", "NADH16_c0", "O2t_c0"]
    fwa = MSFitnessWeightedAnalysis(
        _model(ko=ko), template, biomass=BIOMASS, atp_safe=False
    )
    fwa.build_superset()
    # pgi b4025: significant, PFK b3916: not significant (|t| < 4), PGK b2926: positive
    fit = fw.normalize_fitness(
        {"b4025": (-4.0, -6.0), "b3916": (-4.0, -3.0), "b2926": (2.0, 9.0)}
    )
    pen = fwa.reaction_penalties(fit)
    assert pen["PGI_c0"][">"] == pytest.approx(fw.fitness_penalty(4.0))
    assert pen["PFK_c0"][">"] == pytest.approx(1.0)
    assert pen["PGK_c0"][">"] == pytest.approx(1.0)
    # a reaction without genes costs p_base; exchanges and biomass are not priced
    assert pen["ATPM_c0"][">"] == pytest.approx(1.0)
    assert "EX_glc__D_e0" not in pen and BIOMASS not in pen
    # candidates cost candidate_scale * candidate_factor * their gap-fill penalty
    assert fwa.candidates
    rid = sorted(fwa.candidates & set(pen))[0]
    gp = fwa.gapfilling_penalties[rid]
    if "forward" in gp:
        assert pen[rid][">"] == pytest.approx(20.0 * gp["forward"])
    # mass-imbalanced model reactions cost p_mass_imbalanced
    fwa2 = MSFitnessWeightedAnalysis(
        _model(), template, biomass=BIOMASS, atp_safe=False, mass_imbalanced=["PGI"]
    )
    fwa2.build_superset()
    assert fwa2.reaction_penalties({})["PGI_c0"] == {">": 1000.0, "<": 1000.0}


def test_flux_follows_fitness(template, glucose):
    """Two identical parallel reactions: the one whose gene has a strong fitness defect wins."""
    fwa = MSFitnessWeightedAnalysis(
        _model(extra=_duplicate_pgi),
        template,
        biomass=BIOMASS,
        atp_safe=False,
        loopless=False,
    )
    fwa.build_superset()
    r1 = fwa.analyze_condition("glc", glucose, {"b4025": (-3.0, -8.0)})
    assert r1["status"] == "done"
    assert abs(r1["fluxes"].get("PGI_c0", 0.0)) > 1e-6
    assert abs(r1["fluxes"].get("PGI2_c0", 0.0)) < 1e-9
    r2 = fwa.analyze_condition("glc", glucose, {"g_pgi2": (-3.0, -8.0)})
    assert abs(r2["fluxes"].get("PGI2_c0", 0.0)) > 1e-6
    assert abs(r2["fluxes"].get("PGI_c0", 0.0)) < 1e-9
    # biomass is fixed at frac * optimum
    assert r1["fluxes"][BIOMASS] == pytest.approx(r1["biomass_fixed"], rel=1e-6)
    assert r1["biomass_fixed"] == pytest.approx(r1["growth_superset"], rel=1e-9)
    # the model grows on its own: nothing gap-filled
    assert r1["distance_to_growth"] == 0 and not r1["annotation_gap"]
    calls = r1["reaction_calls"]
    assert calls["PGI_c0"][0] == fw.ACTIVE
    assert calls["PGI2_c0"][0] == fw.UNUSED  # can carry flux, does not in this solution
    ev = {(e["gene"], e["reaction"]): e for e in r1["edge_evidence"]}
    assert ev[("b4025", "PGI_c0")]["verdict"] == fw.POS
    # an essential reaction whose gene has no significant fitness: strong_neg (single-gene KO kills growth)
    assert calls["ENO_c0"][0] == fw.ESSENTIAL
    assert ev[("b2779", "ENO_c0")]["verdict"] == fw.STRONG_NEG
    assert ev[("b2779", "ENO_c0")]["ko_ratio"] == pytest.approx(0.0)


def test_gapfill_distance_and_template(template, glucose):
    """No glucose transporter in the model: the superset solve gap-fills it from the template;
    a template without it cannot grow."""
    model = _model(ko=["GLCpts_c0"])
    fwa = MSFitnessWeightedAnalysis(
        model, template, biomass=BIOMASS, atp_safe=False, loopless=False
    )
    res = fwa.analyze_condition("glc", glucose, {"b4025": (-3.0, -8.0)})
    assert res["status"] == "done"
    assert res["gapfilled"].get("GLCpts_c0") == ">"
    assert res["distance_to_growth"] == len(res["gapfilled"]) >= 1
    assert res["annotation_gap"]
    assert res["growth_model"] is None or res["growth_model"] < 1e-6
    assert "GLCpts_c0" not in model.reactions  # the input model is not changed
    tdict = _template_dict()
    tdict["reactions"] = [r for r in tdict["reactions"] if r["id"] != "GLCpts_c"]
    small = MSTemplateBuilder.from_dict(tdict).build()
    fwa2 = MSFitnessWeightedAnalysis(
        _model(ko=["GLCpts_c0"]), small, biomass=BIOMASS, atp_safe=False, loopless=False
    )
    res2 = fwa2.analyze_condition("glc", glucose, {})
    assert "GLCpts_c0" not in fwa2.superset.reactions
    assert res2["status"] == "no_growth"


def _template_with_free_atp():
    """Template plus a candidate that makes ATP from ADP and phosphate with no energy input."""
    tdict = _template_dict()
    atps = [r for r in tdict["reactions"] if r["id"] == "ATPS4r_c"][0]
    free = copy.deepcopy(atps)
    free["id"] = "FREEATP_c"
    free["name"] = "ATP from nothing"
    free["templateReactionReagents"] = [
        x
        for x in free["templateReactionReagents"]
        if not x["templatecompcompound_ref"].endswith(("h_e", "h_c"))
    ]
    free["templateReactionReagents"].append(
        {"coefficient": 1.0, "templatecompcompound_ref": "~/compcompounds/id/h_c"}
    )
    free["direction"] = free["GapfillDirection"] = ">"
    free["lower_bound"] = 0.0
    tdict["reactions"].append(free)
    return MSTemplateBuilder.from_dict(tdict).build()


def _free_atp_possible(fwa):
    sup = fwa.superset.copy()
    from modelseedpy import MSModelUtil

    MSModelUtil.get(sup).pkgmgr.getpkg("KBaseMediaPkg").build_package(
        MSMedia.from_dict({})
    )
    sup.objective = "ATPM_c0"
    return sup.slim_optimize(error_value=0.0)


def test_atp_safe_filter_removes_free_atp_candidate():
    tpl = _template_with_free_atp()
    unsafe = MSFitnessWeightedAnalysis(_model(), tpl, biomass=BIOMASS, atp_safe=False)
    unsafe.build_superset()
    assert "FREEATP_c0" in unsafe.candidates
    assert _free_atp_possible(unsafe) > 1.0
    safe = MSFitnessWeightedAnalysis(_model(), tpl, biomass=BIOMASS, atp_safe=True)
    safe.build_superset()
    assert safe.filtered.get("FREEATP_c0") == ">"
    assert _free_atp_possible(safe) <= 1e-5


def test_loopless_fallback(template, glucose, monkeypatch):
    """If the loopless MILP fails the plain LP is used and the result says so."""

    def boom(model, *a, **k):
        raise RuntimeError("no loopless here")

    monkeypatch.setattr(cobra.flux_analysis.loopless, "add_loopless", boom)
    fwa = MSFitnessWeightedAnalysis(
        _model(), template, biomass=BIOMASS, atp_safe=False, loopless=True
    )
    res = fwa.analyze_condition("glc", glucose, {"b4025": (-3.0, -8.0)})
    assert res["status"] == "done" and res["loopless"] is False


def test_reversal_priced_as_candidate(template, glucose):
    """A model reaction made one-way while the template has it two-way: the opened direction is a
    gap-fill candidate (price_reversals=True) or priced like the model reaction (False, as GAA)."""

    def one_way(model):
        model.reactions.get_by_id("PGI_c0").lower_bound = 0

    fwa = MSFitnessWeightedAnalysis(
        _model(extra=one_way), template, biomass=BIOMASS, atp_safe=False
    )
    fwa.build_superset()
    if "PGI_c0" not in fwa.reversals:
        pytest.skip("template does not open the PGI reverse direction")
    on = fwa.reaction_penalties({})
    assert on["PGI_c0"]["<"] > on["PGI_c0"][">"]
    fwa.params["price_reversals"] = False
    off = fwa.reaction_penalties({})
    assert off["PGI_c0"]["<"] == off["PGI_c0"][">"] == 1.0


def test_run_and_rollup(template, glucose):
    fwa = MSFitnessWeightedAnalysis(
        _model(), template, biomass=BIOMASS, atp_safe=False, loopless=False
    )
    out = fwa.run(
        {
            "glc1": {"media": glucose, "fitness": {"b4025": (-3.0, -8.0)}},
            "glc2": {"media": glucose, "fitness": {"b4025": (-3.0, -8.0)}},
            "none": {"media": glucose, "fitness": {}},
        }
    )
    assert out["conditions"]["none"]["status"] == "no_fitness"
    roll = {(r["gene"], r["reaction"]): r for r in out["annotation_evidence"]}
    row = roll[("b4025", "PGI_c0")]
    # PGI is FVA-essential in e_coli_core at full growth, and pgi has a tier-1 defect
    assert (
        row["n_conditions"] == 2
        and row["n_strong_pos"] == 2
        and row["dominant_verdict"] == fw.STRONG_POS
    )
    assert row["net_score"] == pytest.approx(2.0)
    assert out["superset"]["n_candidates"] == len(fwa.candidates)


def test_loopless_solution(template, glucose):
    """On a small model the loopless MILP finishes and gives the same weighted objective as the LP
    (all penalties are positive, so the LP optimum has no loop flux to remove)."""
    fwa = MSFitnessWeightedAnalysis(
        _model(), template, biomass=BIOMASS, atp_safe=False, loopless=True
    )
    res = fwa.analyze_condition("glc", glucose, {"b4025": (-3.0, -8.0)})
    assert res["status"] == "done" and res["loopless"] is True
    fwa.params["loopless"] = False
    lp = fwa.analyze_condition("glc", glucose, {"b4025": (-3.0, -8.0)})
    assert lp["loopless"] is False
    assert res["objective"] == pytest.approx(lp["objective"], rel=1e-6)
    fwa.params["loopless"] = "auto"
    auto = fwa.analyze_condition("glc", glucose, {"b4025": (-3.0, -8.0)})
    assert auto["loopless"] == "implied"
    assert auto["objective"] == pytest.approx(res["objective"], rel=1e-6)


def test_nonpositive_template_penalty(template):
    """A gap-fill penalty <= 0 is floored at 1e-9 (GAA) or replaced by 1.0 before scaling."""
    fwa = MSFitnessWeightedAnalysis(
        _model(ko=["GLCpts_c0"]), template, biomass=BIOMASS, atp_safe=False
    )
    fwa.build_superset()
    assert fwa._candidate_price({"reverse": -3.0}, "reverse", 20.0) == 1e-9
    assert (
        fwa._candidate_price({}, "reverse", 20.0) == 10.0
    )  # direction not offered: p_gapfill
    fwa.params["nonpositive_penalty"] = "one"
    assert fwa._candidate_price({"reverse": -3.0}, "reverse", 20.0) == 20.0
    assert fwa._candidate_price({"forward": 4.0}, "forward", 20.0) == 80.0


def test_biomass_reference_model(template, glucose):
    """biomass_reference='model': a model that grows on its own is not pushed to the superset optimum."""
    model = _model(
        ko=["PGI_c0"]
    )  # grows (pentose phosphate bypass) but slower than with PGI
    fwa = MSFitnessWeightedAnalysis(model, template, biomass=BIOMASS, atp_safe=False)
    sup = fwa.analyze_condition("glc", glucose, {"b4025": (-3.0, -8.0)})
    assert sup["growth_model"] < sup["growth_superset"] - 1e-6
    assert sup["gapfilled"].get(
        "PGI_c0"
    )  # reaching the superset optimum needs PGI back
    fwa.params["biomass_reference"] = "model"
    mod = fwa.analyze_condition("glc", glucose, {"b4025": (-3.0, -8.0)})
    assert mod["biomass_fixed"] == pytest.approx(mod["growth_model"], rel=1e-9)
    assert mod["distance_to_growth"] == 0


def test_atp_tests_from_correction(template):
    """Tests come from MSATPCorrection on a copy: the input model is not changed, the empty medium comes first,
    and the tests can be passed to the analysis."""
    model = _model()
    n = len(model.reactions)
    tests = MSFitnessWeightedAnalysis.atp_tests_from_correction(
        model, template, atp_hydrolysis_id="ATPM_c0"
    )
    assert len(model.reactions) == n
    assert tests and tests[0]["media"].id == "empty"
    assert all(
        {"media", "threshold", "objective", "is_max_threshold"} <= set(t) for t in tests
    )
    fwa = MSFitnessWeightedAnalysis(
        _model(), template, biomass=BIOMASS, atp_tests=tests
    )
    fwa.build_superset()
    assert fwa.superset is not None
