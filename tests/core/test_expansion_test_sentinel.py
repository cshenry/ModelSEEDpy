# -*- coding: utf-8 -*-
import logging

import pytest

from modelseedpy.core.msatpcorrection import MSATPCorrection
from modelseedpy.core.msgapfill import MSGapfill
from tests.core.test_msgapfill import (  # noqa: F401
    get_model,
    media_glucose_aerobic,
    template,
)


def _never_passes(*args, **kwargs):
    # reaction_expansion_test's sentinel: no subset of reactions passes a test
    return None


def _gapfilling_pkg(template, get_model):
    gap_fill = MSGapfill(get_model(["GLCpts_c0"]), [template])
    gap_fill.gfmodel.optimize()
    return gap_fill.gfpkgmgr.getpkg("GapfillingPkg")


def test_run_test_conditions_returns_none(template, get_model, monkeypatch):
    gfpkg = _gapfilling_pkg(template, get_model)
    monkeypatch.setattr(gfpkg.modelutl, "reaction_expansion_test", _never_passes)
    assert gfpkg.run_test_conditions([{}], {"new": {}, "reversed": {}}) is None


def test_filter_database_raises_a_clear_error(template, get_model, monkeypatch):
    gfpkg = _gapfilling_pkg(template, get_model)
    monkeypatch.setattr(gfpkg.modelutl, "reaction_expansion_test", _never_passes)
    with pytest.raises(ValueError, match="test conditions fail"):
        gfpkg.filter_database_based_on_tests([{}])


def test_expand_model_warns_and_keeps_going(
    template, get_model, media_glucose_aerobic, monkeypatch, caplog
):
    atp = MSATPCorrection(
        get_model([]),
        template,
        [media_glucose_aerobic],
        atp_hydrolysis_id="ATPM_c0",
        load_default_medias=False,
    )
    monkeypatch.setattr(atp, "build_tests", lambda *a, **k: [])
    monkeypatch.setattr(atp.modelutl, "reaction_expansion_test", _never_passes)
    with caplog.at_level(logging.WARNING):
        atp.expand_model_to_genome_scale()
    assert atp.filtered_noncore == []
    assert any("no passing solution" in r.getMessage() for r in caplog.records)
