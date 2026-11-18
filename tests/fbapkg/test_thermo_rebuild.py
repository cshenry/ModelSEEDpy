# -*- coding: utf-8 -*-
"""A second build_package must leave FullThermoPkg/SimpleThermoPkg variables with the bounds
of that build's parameters, as a fresh build would.

BaseFBAPkg.build_variable returns an existing variable unchanged, so the logconc, pdgerr,
ndgerr, potential and dgp variables kept the bounds of the first build. Toy models with
energies in notes['deltag'] and ids that are not ModelSEED ids: no database is needed.
"""
import math

import cobra
import pytest

from modelseedpy.fbapkg.mspackagemanager import MSPackageManager


def _model(deltag_glc=-100.0, deltag_pyr=-110.0):
    """glucose -> 2 pyruvate, formation energies (kcal/mol) in notes['deltag']."""
    m = cobra.Model("rebuild")
    m.solver = "glpk"
    glc = cobra.Metabolite("glc_c0", compartment="c0", formula="C6H12O6", charge=0)
    pyr = cobra.Metabolite("pyr_c0", compartment="c0", formula="C3H3O3", charge=-1)
    glc.notes = {"deltag": deltag_glc}
    pyr.notes = {"deltag": deltag_pyr}
    m.add_metabolites([glc, pyr])
    r = cobra.Reaction("R1", lower_bound=-1000, upper_bound=1000)
    r.add_metabolites({glc: -1, pyr: 2})
    ex = cobra.Reaction("EX_glc_e0", lower_bound=-10, upper_bound=1000)
    ex.add_metabolites({glc: -1})
    dm = cobra.Reaction("DM_pyr_c0", lower_bound=0, upper_bound=1000)
    dm.add_metabolites({pyr: -1})
    m.add_reactions([r, ex, dm])
    m.objective = "DM_pyr_c0"
    return m


def test_rebuild_resets_concentration_and_error_bounds():
    m = _model()
    pkg = MSPackageManager.get_pkg_mgr(m).getpkg("FullThermoPkg")
    pkg.build_package({})
    pkg.build_package(
        {
            "custom_concentrations": {"glc_c0": [0.05, 0.1]},
            "default_max_error": 20,
            "custom_deltaG_error": {"pyr_c0": 2},
        }
    )
    glc = pkg.variables["logconc"]["glc_c0"]
    assert (glc.lb, glc.ub) == pytest.approx((math.log(0.05), math.log(0.1)))
    for kind in ("pdgerr", "ndgerr"):
        assert pkg.variables[kind]["glc_c0"].ub == 20
        assert pkg.variables[kind]["pyr_c0"].ub == 2
    # and back to the defaults
    pkg.build_package({})
    assert (glc.lb, glc.ub) == pytest.approx((math.log(1e-6), math.log(0.02)))
    for kind in ("pdgerr", "ndgerr"):
        assert pkg.variables[kind]["glc_c0"].ub == 5
        assert pkg.variables[kind]["pyr_c0"].ub == 5


def test_full_build_after_a_simple_build_takes_its_own_potential_bounds():
    # glucose at -3000 kcal/mol = -12552 kJ/mol fits a FullThermoPkg max_potential of 100000
    # (the old fixed bound; the default is now 10000), but a SimpleThermoPkg built first at
    # its default max_potential of 10000 left the potentials at +/-10000, and the model was
    # infeasible where a fresh FullThermoPkg build is not
    m = _model(deltag_glc=-3000.0, deltag_pyr=-1501.0)
    pkgmgr = MSPackageManager.get_pkg_mgr(m)
    simple = pkgmgr.getpkg("SimpleThermoPkg")
    simple.build_package({})
    pkgmgr.getpkg("FullThermoPkg").build_package({"max_potential": 100000})
    assert m.slim_optimize() == pytest.approx(20)
    for kind in ("potential", "dgp"):
        for var in simple.variables[kind].values():
            assert (var.lb, var.ub) == (-100000, 100000)
