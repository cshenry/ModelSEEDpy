# -*- coding: utf-8 -*-
from modelseedpy.core.msminimalmedia import MSMinimalMedia
from modelseedpy.core.msmodelutl import MSModelUtil
from modelseedpy.fbapkg.mspackagemanager import MSPackageManager
from tests.test_data.mock_data import mock_model_ecoli_core


def _seed_core_model():
    model = mock_model_ecoli_core(seed=True)
    # minimal media reads growth from the bio<N> reaction, the ModelSEED name
    model.reactions.get_by_id("Biomass_Ecoli_core").id = "bio1"
    model.repair()
    model.objective = "bio1"
    return model


def test_minimize_flux_releases_its_model_copies():
    """Each minimize_flux call works on a model copy; the copy must not stay
    pinned in the class-level registries, or media sweeps leak one model per
    call until they run out of memory."""
    model = _seed_core_model()
    packages_before = len(MSPackageManager.pkgmgrs)
    utils_before = len(MSModelUtil.mdlutls)
    for _ in range(3):
        MSMinimalMedia.minimize_flux(model, climit=60, printing=False)
    assert len(MSPackageManager.pkgmgrs) == packages_before
    assert len(MSModelUtil.mdlutls) == utils_before
