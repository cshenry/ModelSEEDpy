# -*- coding: utf-8 -*-
import math

import cobra

from modelseedpy.core.msmedia import MSMedia
from modelseedpy.fbapkg.mspackagemanager import MSPackageManager


def _thermo_model():
    model = cobra.Model("media_thermo")
    ext = cobra.Metabolite("cpd99003_e0", compartment="e0", charge=0, formula="C")
    ext.notes = {"deltag": -50.0}
    cyt = cobra.Metabolite("cpd99002_c0", compartment="c0", charge=0, formula="C")
    cyt.notes = {"deltag": -100.0}
    uptake = cobra.Reaction("rxn_up_c0", lower_bound=0, upper_bound=1000)
    uptake.add_metabolites({ext: -1, cyt: 1})
    ex = cobra.Reaction("EX_cpd99003_e0", lower_bound=-1000, upper_bound=1000)
    ex.add_metabolites({ext: -1})
    sink = cobra.Reaction("DM_cpd99002_c0", lower_bound=0, upper_bound=1000)
    sink.add_metabolites({cyt: -1})
    model.add_reactions([uptake, ex, sink])
    model.objective = "DM_cpd99002_c0"
    return model


def test_media_concentration_pins_the_thermo_concentration():
    """With FullThermoPkg built, a media compound's concentration fixes the
    log-concentration of its extracellular metabolite. This raised KeyError:
    the variables were looked up on KBaseMediaPkg, which has none."""
    model = _thermo_model()
    pkgmgr = MSPackageManager.get_pkg_mgr(model)
    pkgmgr.getpkg("FullThermoPkg").build_package({})
    media = MSMedia.from_dict(
        {"cpd99003": {"lower_bound": -10, "upper_bound": 100, "concentration": 0.01}}
    )
    pkgmgr.getpkg("KBaseMediaPkg").build_package(media)
    var = pkgmgr.getpkg("FullThermoPkg").variables["logconc"]["cpd99003_e0"]
    assert math.isclose(var.lb, math.log(0.01))
    assert math.isclose(var.ub, math.log(0.01))
    assert model.slim_optimize() > 0


def test_media_without_concentration_leaves_the_bounds():
    model = _thermo_model()
    pkgmgr = MSPackageManager.get_pkg_mgr(model)
    pkgmgr.getpkg("FullThermoPkg").build_package({})
    var = pkgmgr.getpkg("FullThermoPkg").variables["logconc"]["cpd99003_e0"]
    before = (var.lb, var.ub)
    pkgmgr.getpkg("KBaseMediaPkg").build_package(MSMedia.from_dict({"cpd99003": 10}))
    assert (var.lb, var.ub) == before
