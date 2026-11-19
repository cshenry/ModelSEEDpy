# -*- coding: utf-8 -*-
"""Candidates GapfillingPkg offers to MSModelUtil.reaction_expansion_test

reaction_expansion_test blocks a direction of any candidate whose removal lets
a test condition pass. Blocking the reaction an ATP test maximizes always lets
it pass, so the ATP test objective must never be a candidate; nor may biomass
or exchange, demand and sink reactions.
"""
import pytest

from modelseedpy import MSGapfill, MSMedia
from modelseedpy.core.fbahelper import FBAHelper
from modelseedpy.core.msmodelutl import MSModelUtil
from tests.core.test_msatpcorreption import (  # noqa: F401
    get_model,
    media_genome_scale_glucose_aerobic,
    media_glucose_aerobic,
    template_genome_scale,
)

ATPM = "ATPM_c0"
BIOMASS = "BIOMASS_Ecoli_core_w_GAM_c0"
KNOCKOUTS = ["GLCpts_c0", "GLUSy_c0", "GLUDy_c0"]
# Template K+ transports that form an ATP-yielding cycle in the gapfilling model
LOOP = {"Kt2r_c0", "Ktex_c0"}


@pytest.fixture
def atp_tests(get_model, media_glucose_aerobic):
    """ATP tests as MSATPCorrection.build_tests makes them: none on the empty
    medium, at most 1.2x the core yield on glucose"""
    empty = MSMedia.from_dict({})
    empty.id = "empty"
    reference = get_model()
    reference.objective = ATPM
    MSModelUtil.get(reference).pkgmgr.getpkg("KBaseMediaPkg").build_package(
        media_glucose_aerobic
    )
    core_atp = reference.slim_optimize()
    assert core_atp > 0
    return [
        {
            "media": empty,
            "is_max_threshold": True,
            "threshold": 0.00001,
            "objective": ATPM,
        },
        {
            "media": media_glucose_aerobic,
            "is_max_threshold": True,
            "threshold": 1.2 * core_atp,
            "objective": ATPM,
        },
    ]


def _growth_conditions(media):
    return [
        {
            "media": media,
            "is_max_threshold": False,
            "threshold": 0.1,
            "objective": BIOMASS,
        }
    ]


def _gapfill(get_model, template_genome_scale, atp_tests, media):
    gap_fill = MSGapfill(get_model(KNOCKOUTS), [template_genome_scale], [], atp_tests)
    gfpkg = gap_fill.gfpkgmgr.getpkg("GapfillingPkg")
    gfpkg.set_base_objective(BIOMASS, 0.1)
    gfpkg.set_media(media)
    return gap_fill, gfpkg


def _empty_medium_filter(gap_fill):
    return set(gap_fill.gfmodelutl.get_attributes("gf_filter")["empty"][ATPM][0.00001])


def _assert_no_excluded(candidates):
    ids = {rxn_id for rxn_id, _ in candidates}
    assert ATPM not in ids
    assert BIOMASS not in ids
    assert not [rxn_id for rxn_id in ids if rxn_id[0:3] in ("EX_", "DM_", "SK_")]


def test_expansion_test_candidates(
    get_model, template_genome_scale, atp_tests, media_genome_scale_glucose_aerobic
):
    gap_fill, gfpkg = _gapfill(
        get_model, template_genome_scale, atp_tests, media_genome_scale_glucose_aerobic
    )
    reactions = gap_fill.gfmodel.reactions
    items = [
        [reactions.get_by_id(rxn_id), direction]
        for rxn_id, direction in [
            (ATPM, ">"),
            (BIOMASS, ">"),
            ("EX_glc__D_e0", "<"),
            ("GLCpts_c0", ">"),
            ("PGK_c0", "<"),
            ("PGK_c0", ">"),
        ]
    ]
    kept = gfpkg.expansion_test_candidates(
        items, atp_tests, _growth_conditions(media_genome_scale_glucose_aerobic)
    )
    # The same item objects, in order: reaction_expansion_test appends to them
    assert kept == items[3:]
    assert all(a is b for a, b in zip(kept, items[3:]))
    # A condition objective may be given as a reaction rather than its ID
    pgk = reactions.get_by_id("PGK_c0")
    assert gfpkg.expansion_test_candidates(items[3:], [{"objective": pgk}]) == [
        items[3]
    ]
    # No condition lists: biomass and drains are still excluded, ATPM is not
    assert [i[0].id for i in gfpkg.expansion_test_candidates(items)] == [
        ATPM,
        "GLCpts_c0",
        "PGK_c0",
        "PGK_c0",
    ]


def test_expansion_test_never_offered_objective_biomass_or_drains(
    get_model,
    template_genome_scale,
    atp_tests,
    media_genome_scale_glucose_aerobic,
    monkeypatch,
):
    """Every candidate list at all three reaction_expansion_test call sites"""
    gap_fill, gfpkg = _gapfill(
        get_model, template_genome_scale, atp_tests, media_genome_scale_glucose_aerobic
    )
    calls = []

    def record(self, reaction_list, condition_list, *args, **kwargs):
        calls.append([(item[0].id, item[1]) for item in reaction_list])
        return []

    monkeypatch.setattr(MSModelUtil, "reaction_expansion_test", record)
    # Failing the database test sends filter_database_based_on_tests on to its
    # second reaction_expansion_test call, over the model's original reactions
    monkeypatch.setattr(gfpkg, "test_gapfill_database", lambda *a, **k: False)
    gfpkg.filter_database_based_on_tests(
        atp_tests,
        growth_conditions=_growth_conditions(media_genome_scale_glucose_aerobic),
    )
    # run_test_conditions reads gapfilled fluxes from a solved model
    gap_fill.gfmodel.optimize()
    solution = {
        "reversed": {},
        "new": {"GLCpts_c0": ">", "EX_k_e0": ">", ATPM: ">", BIOMASS: ">"},
    }
    assert gfpkg.run_test_conditions(atp_tests, solution) is solution

    assert len(calls) == 3
    database, original, solution_candidates = calls
    for candidates in calls:
        _assert_no_excluded(candidates)
    # The lists still hold what should be tested
    assert LOOP <= {rxn_id for rxn_id, _ in database}
    assert ("PGK_c0", ">") in original
    assert solution_candidates == [("GLCpts_c0", ">")]
    # Without the exclusion all three of these would have been offered
    offered = {(item[0].id, item[1]) for item in gfpkg.parameters["original_reactions"]}
    assert (ATPM, ">") in offered
    assert not gfpkg.modelutl.is_core(ATPM)
    assert not gfpkg.modelutl.is_core(BIOMASS)
    assert FBAHelper.is_ex(gap_fill.gfmodel.reactions.EX_glc__D_e0)


def test_prefilter_does_not_block_the_atp_test_objective(
    get_model, template_genome_scale, atp_tests, media_genome_scale_glucose_aerobic
):
    """Regression: with ATPM_c0 ">" sorted after the cycle reactions, the old
    candidate list let the bisection block ATPM_c0 itself; nothing else was
    filtered and both ATP tests read 0 for the rest of gapfilling."""
    gap_fill, gfpkg = _gapfill(
        get_model, template_genome_scale, atp_tests, media_genome_scale_glucose_aerobic
    )
    # Raise ATPM_c0 ">" from reliability score 300 to 3300, after the K+ cycle (1000)
    gap_fill.prefilter(
        growth_conditions=_growth_conditions(media_genome_scale_glucose_aerobic),
        active_reaction_sets=[[[ATPM, ">"]] * 100],
    )
    assert gap_fill.gfmodel.reactions.get_by_id(ATPM).bounds == (0, 1000)
    filtered = _empty_medium_filter(gap_fill)
    assert ATPM not in filtered
    assert filtered and filtered <= LOOP
    # The ATP tests can still measure ATP, and both pass after filtering
    with gap_fill.gfmodel:
        gfpkg.reset_objective_minimum(0, False)
        for test in atp_tests:
            gap_fill.gfmodelutl.apply_test_condition(test)
            atp = gap_fill.gfmodel.slim_optimize()
            assert atp < test["threshold"]
            if test["media"].id != "empty":
                assert atp > 0


def test_gapfilling_with_atp_tests_unchanged(
    get_model, template_genome_scale, atp_tests, media_genome_scale_glucose_aerobic
):
    """Default ordering, where the old code already filtered the cycle: the
    filter and the gapfilling solution are what they were"""
    gap_fill = MSGapfill(get_model(KNOCKOUTS), [template_genome_scale], [], atp_tests)
    result = gap_fill.run_gapfilling(
        media_genome_scale_glucose_aerobic, BIOMASS, minimum_obj=0.1
    )
    assert result
    assert result["reversed"] == {}
    assert len(result["new"]) == 2
    assert result["new"]["GLCpts_c0"] == ">"
    assert "GLUSy_c0" in result["new"] or "GLUDy_c0" in result["new"]
    assert _empty_medium_filter(gap_fill) == {"Ktex_c0"}
    assert gap_fill.gfmodel.reactions.get_by_id(ATPM).bounds == (0, 1000)
