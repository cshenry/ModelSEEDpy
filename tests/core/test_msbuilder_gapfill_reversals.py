# -*- coding: utf-8 -*-
"""MSBuilder.build_and_gapfill must apply the gapfiller's reversals, not only its new
reactions (MSBuilder.apply_gapfill_reversals)."""
import cobra
import pytest

import modelseedpy
import modelseedpy.core.msatpcorrection as msatpcorrection
from modelseedpy.core.msbuilder import MSBuilder


def small_model(bounds):
    model = cobra.Model("m")
    a, b = cobra.Metabolite("A_c0", compartment="c0"), cobra.Metabolite(
        "B_c0", compartment="c0"
    )
    for rxn_id, (lb, ub) in bounds.items():
        rxn = cobra.Reaction(rxn_id, lower_bound=lb, upper_bound=ub)
        rxn.add_metabolites({a: -1, b: 1})
        model.add_reactions([rxn])
    return model


def test_reverse_direction_is_opened():
    model = small_model({"rxn00001_c0": (0, 1000)})
    assert MSBuilder.apply_gapfill_reversals(model, {"rxn00001_c0": "<"}) == [
        "rxn00001_c0"
    ]
    assert model.reactions.rxn00001_c0.bounds == (-1000, 1000)


def test_forward_direction_is_opened():
    model = small_model({"rxn00001_c0": (-1000, 0)})
    MSBuilder.apply_gapfill_reversals(model, {"rxn00001_c0": ">"})
    assert model.reactions.rxn00001_c0.bounds == (-1000, 1000)


def test_only_the_reversed_side_changes_and_wider_bounds_are_kept():
    model = small_model({"rxn00001_c0": (-5, 0), "rxn00002_c0": (0, 5000)})
    MSBuilder.apply_gapfill_reversals(model, {"rxn00001_c0": ">", "rxn00002_c0": ">"})
    assert model.reactions.rxn00001_c0.bounds == (-5, 1000)
    assert model.reactions.rxn00002_c0.bounds == (0, 5000)


def test_absent_reaction_and_empty_input_are_ignored():
    model = small_model({"rxn00001_c0": (0, 1000)})
    assert MSBuilder.apply_gapfill_reversals(model, {"rxn99999_c0": "<"}) == []
    assert MSBuilder.apply_gapfill_reversals(model, None) == []
    assert model.reactions.rxn00001_c0.bounds == (0, 1000)


def test_build_and_gapfill_applies_the_reversed_set(monkeypatch):
    """Wiring: with ATP correction and gapfilling stubbed, a reversed reaction in the
    gapfill result must come back open in the returned model, and the base model must
    stay untouched."""
    base = small_model({"rxn00001_c0": (0, 1000), "rxn00002_c0": (-1000, 0)})

    class StubATPCorrection:
        def __init__(self, *args, **kwargs):
            pass

        def evaluate_growth_media(self):
            return {}

        def determine_growth_media(self):
            pass

        def apply_growth_media_gapfilling(self):
            pass

        def expand_model_to_genome_scale(self):
            pass

        def build_tests(self):
            return []

    class StubGapfill:
        def __init__(self, *args, **kwargs):
            pass

        def run_gapfilling(self, media):
            return {"new": {}, "reversed": {"rxn00001_c0": "<", "rxn00002_c0": ">"}}

    monkeypatch.setattr(MSBuilder, "build_base_model", lambda self, *a, **k: base)
    monkeypatch.setattr(msatpcorrection, "load_default_medias", lambda: [])
    monkeypatch.setattr(modelseedpy, "MSATPCorrection", StubATPCorrection)
    monkeypatch.setattr(modelseedpy, "MSGapfill", StubGapfill)
    builder = MSBuilder.__new__(MSBuilder)
    builder.template = cobra.Model("template")
    builder.template_core = None

    model, _atpc, tests, gap_sol = builder.build_and_gapfill(
        "m", gapfill_media=None, add_maintenance_atp_reaction=False
    )

    assert model.reactions.rxn00001_c0.bounds == (-1000, 1000)
    assert model.reactions.rxn00002_c0.bounds == (-1000, 1000)
    assert base.reactions.rxn00001_c0.bounds == (0, 1000)  # the base model is a copy
    assert gap_sol == {} and tests == []
