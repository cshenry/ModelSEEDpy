# -*- coding: utf-8 -*-
"""MSMinimalMedia on e_coli_core with ModelSEED ids for biomass, glucose and O2."""
import importlib
import sys

import pytest

from modelseedpy.core.exceptions import ObjectiveError
from modelseedpy.core.msminimalmedia import (
    MSMinimalMedia,
    bioFlux_check,
    minimizeFlux_withGrowth,
)
from modelseedpy.core.msmodelutl import MSModelUtil
from tests.test_data.mock_data import mock_model_ecoli_core

GLC, O2 = "EX_cpd00027_e0", "EX_cpd00007_e0"


def _model():
    model = mock_model_ecoli_core(seed=True)
    model.reactions.get_by_id("Biomass_Ecoli_core").id = "bio1"
    model.reactions.get_by_id("EX_glc__D_e").id = GLC
    model.reactions.get_by_id("EX_o2_e").id = O2
    model.repair()
    model.objective = "bio1"
    return model


def test_exported_from_modelseedpy_core():
    import modelseedpy
    import modelseedpy.core

    assert modelseedpy.core.MSMinimalMedia is MSMinimalMedia
    assert modelseedpy.core.bioFlux_check is bioFlux_check
    assert modelseedpy.core.minimizeFlux_withGrowth is minimizeFlux_withGrowth
    assert modelseedpy.MSMinimalMedia is MSMinimalMedia


def test_module_imports_without_deepdiff(monkeypatch):
    import modelseedpy.core

    # None in sys.modules makes "import deepdiff" raise; monkeypatch restores all
    monkeypatch.setitem(sys.modules, "deepdiff", None)
    monkeypatch.delitem(sys.modules, "modelseedpy.core.msminimalmedia")
    monkeypatch.setattr(modelseedpy.core, "msminimalmedia", None)
    module = importlib.import_module("modelseedpy.core.msminimalmedia")
    assert hasattr(module, "MSMinimalMedia")


def test_minimize_flux_leaves_the_callers_model_alone():
    model = _model()
    medium, n_cons = dict(model.medium), len(model.constraints)
    objective = str(model.objective.expression)
    env = dict(medium)
    env[GLC] = 5
    media, sol = MSMinimalMedia.minimize_flux(model, environment=env, printing=False)
    assert sol.status == "optimal"
    assert media[GLC] == pytest.approx(5)
    # every compound of the minimal medium is in the environment
    assert set(media) <= set(env)
    assert model.medium == medium
    assert len(model.constraints) == n_cons
    assert str(model.objective.expression) == objective


def test_minimize_flux_media_supports_the_growth():
    model = _model()
    max_growth = model.slim_optimize()
    media, _ = MSMinimalMedia.minimize_flux(model, printing=False)
    check = model.copy()
    check.medium = media
    assert check.slim_optimize() == pytest.approx(max_growth, rel=1e-3)


def test_minimize_flux_o2limit_caps_o2_and_keeps_an_anaerobic_medium_anaerobic():
    model = _model()
    media, _ = MSMinimalMedia.minimize_flux(model, o2limit=5, printing=False)
    assert media[O2] <= 5 + 1e-6
    anaerobic = {ex: v for ex, v in model.medium.items() if ex != O2}
    media, sol = MSMinimalMedia.minimize_flux(
        model, environment=anaerobic, climit=60, printing=False
    )
    assert sol.status == "optimal"
    assert O2 not in media


def test_minimize_flux_without_growth():
    model = _model()
    with pytest.raises(ObjectiveError):
        MSMinimalMedia.minimize_flux(model, environment={GLC: 10}, printing=False)
    assert MSMinimalMedia.minimize_flux(
        model, environment={GLC: 10}, errorOut=False, printing=False
    ) == ({}, None)


def test_determine_min_media_passes_its_arguments_through(monkeypatch):
    calls = []

    def fake_minimize_flux(*args, **kwargs):
        calls.append((args, kwargs))
        return {}, None

    monkeypatch.setattr(MSMinimalMedia, "minimize_flux", fake_minimize_flux)
    # CommScores' positional order: ..., interacting, pfba, printing, climit, o2limit
    MSMinimalMedia.determine_min_media(
        "model", "minFlux", 0.1, "env", True, False, False, 60, 20, errorOut=False
    )
    args, kwargs = calls[0]
    assert args == ("model", 0.1, "env", True)
    assert kwargs == {
        "printing": False,
        "pfba": False,
        "climit": 60,
        "o2limit": 20,
        "errorOut": False,
    }


def test_comm_media_est_passes_n_solutions_as_solution_limit(monkeypatch):
    calls = []

    def fake_determine_min_media(*args, **kwargs):
        calls.append(kwargs)
        return {}

    monkeypatch.setattr(MSMinimalMedia, "determine_min_media", fake_determine_min_media)
    model = _model()
    MSMinimalMedia.comm_media_est([model], model, "minFlux", 0.1, None, True, 7, False)
    assert calls == [{"printing": False, "solution_limit": 7}] * 2


def test_interacting_comm_media_passes_the_method_and_growth_by_name(monkeypatch):
    calls = []

    def fake_comm_media_est(*args, **kwargs):
        calls.append(kwargs)
        return {"community_media": {}, "members": {}}

    monkeypatch.setattr(MSMinimalMedia, "comm_media_est", fake_comm_media_est)
    MSMinimalMedia.interacting_comm_media([], None, "jenga", 0.2, printing=False)
    assert calls[0]["minimization_method"] == "jenga"
    assert calls[0]["min_growth"] == 0.2


def test_minimize_flux_with_growth_and_bio_flux_check():
    model = _model()
    util = MSModelUtil(model)
    growth = model.slim_optimize()
    glc = model.reactions.get_by_id(GLC)
    sol, sol_dict = minimizeFlux_withGrowth(util, 0.5 * growth, glc.reverse_variable)
    assert sol.status == "optimal"
    assert sol.fluxes["bio1"] >= 0.5 * growth * 0.9999
    assert model.constraints["min_growth"].lb == pytest.approx(0.5 * growth)
    # a solution dict alone is enough
    assert bioFlux_check(model, sol_dict=sol_dict, min_growth=0.5 * growth) is sol_dict
    with pytest.raises(ObjectiveError):
        bioFlux_check(model, sol, min_growth=2 * growth)
