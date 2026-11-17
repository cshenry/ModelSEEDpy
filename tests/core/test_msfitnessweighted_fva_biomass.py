# -*- coding: utf-8 -*-
"""The restricted FVA must hold biomass at the value the weighted solve used.

Re-maximising biomass on the restricted network can give a higher optimum than the
weighted solve's target: with ``biomass_reference='model'`` the target is the model's own
optimum, while the restricted network also carries the candidates the solve gap-filled and
so grows faster. An FVA bounded below by that higher optimum excludes the very flux
distribution it is classifying, and every reaction on the cheaper route is then reported
with a flux outside its own interval.
"""
import json
import os

import cobra
import pytest

from modelseedpy import MSFitnessWeightedAnalysis, MSMedia, MSModelUtil
from modelseedpy.core.mstemplate import MSTemplateBuilder

BIOMASS = "BIOMASS_Ecoli_core_w_GAM_c0"
DATA = os.path.join(os.path.dirname(__file__), "..", "test_data")
# the pentose phosphate route that carries G6P -> F6P when PGI is missing
BYPASS = ["G6PDH2r", "PGL", "GND"]
TOL = 1e-6


def _template():
    with open(os.path.join(DATA, "template_core_bigg.json")) as fh:
        return MSTemplateBuilder.from_dict(json.load(fh)).build()


def _model(ko=None):
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
    return cobra.io.from_json(json.dumps(model_json))


def _glucose():
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


@pytest.fixture(scope="module")
def exceeding():
    """A condition whose restricted network grows faster than the weighted target.

    PGI is missing, so the model grows through the pentose phosphate bypass; pricing that
    bypass as mass-imbalanced at 1e6 makes the template's PGI candidate the cheaper route,
    so the weighted solve gap-fills it. With ``biomass_reference='model'`` the target stays
    the model's own optimum, which the gap-filled network beats.
    """
    fwa = MSFitnessWeightedAnalysis(
        _model(ko=["PGI_c0"]),
        _template(),
        biomass=BIOMASS,
        atp_safe=False,
        loopless=False,
        biomass_reference="model",
        mass_imbalanced=BYPASS,
        p_mass_imbalanced=1e6,
    )
    return fwa.analyze_condition("glc", _glucose(), {"b4025": (-3.0, -8.0)})


def test_toy_restricted_network_outgrows_the_target(exceeding):
    """The toy is only a test of the fix if the restricted network really does grow faster."""
    assert exceeding["status"] == "done"
    assert exceeding["gapfilled"].get("PGI_c0") == ">"
    assert exceeding["biomass_fixed"] == pytest.approx(
        exceeding["growth_model"], rel=1e-9
    )
    assert exceeding["growth_network"] > exceeding["biomass_fixed"] * (1 + TOL)


def test_every_reported_flux_lies_in_its_own_fva_interval(exceeding):
    calls = exceeding["reaction_calls"]
    assert calls
    outside = {
        rid: call
        for rid, call in calls.items()
        if not call[2] - TOL <= call[1] <= call[3] + TOL
    }
    assert outside == {}


def test_reported_biomass_equals_biomass_fixed(exceeding):
    assert exceeding["fluxes"][BIOMASS] == pytest.approx(
        exceeding["biomass_fixed"], rel=1e-9
    )


def test_fva_fixes_biomass_instead_of_re_maximising_it():
    """_fva pins biomass to the value it is given and still reports the network optimum."""
    fwa = MSFitnessWeightedAnalysis(
        _model(), _template(), biomass=BIOMASS, atp_safe=False
    )
    fwa.build_superset()
    model = fwa.superset.copy()
    MSModelUtil.get(model).pkgmgr.getpkg("KBaseMediaPkg").build_package(_glucose())
    opt = fwa._optimum(model)
    target = 0.5 * opt  # deliberately below what the network can reach
    fva, opt_net = fwa._fva(model, [BIOMASS], target)
    assert opt_net == pytest.approx(opt, rel=1e-9)
    vmin, vmax = fva[BIOMASS]
    assert vmin == pytest.approx(target, rel=1e-9)
    assert vmax == pytest.approx(target, rel=1e-9)
