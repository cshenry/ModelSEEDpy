# -*- coding: utf-8 -*-
"""Compound energies and pKas from the current ModelSEEDDatabase schema and the old one.

Since 2026-09-11 the database keeps formation energies in a per-source "thermodynamics" block
and pKas in a per-source "pkas" block, with no top-level deltag/deltagerr/pka/pkb. The old
schema (top-level fields) must load exactly as before.
"""
import json
import os

import pytest

from modelseedpy.biochem.modelseed_biochem import (
    DELTA_G_SOURCES,
    _load_metabolites,
    _pkas,
    _thermodynamics,
)


def _write_db(tmp_path, records):
    biochem = tmp_path / "Biochemistry"
    biochem.mkdir()
    (biochem / "compound_00.json").write_text(json.dumps(records))
    return _load_metabolites(str(tmp_path))


# a current-schema record, as cpd00027 (D-Glucose) is stored today
GLUCOSE = {
    "id": "cpd00027",
    "abbreviation": "glc-D",
    "charge": 0,
    "formula": "C6H12O6",
    "is_core": 1,
    "is_obsolete": 0,
    "mass": 180.0,
    "name": "D-Glucose",
    "source": "Primary Database",
    "pkas": {
        "Marvin": {
            "kind": "microscopic",
            "pKa": "1:11.30;1:12.69",
            "pKb": "1:-2.98;1:-3.65",
        },
        "MolGpKa": {"kind": "microscopic", "pKa": "1:12.03", "pKb": ""},
    },
    "thermodynamics": {
        "Group contribution": [-218.28, 3.09],
        "dGPredictor": [-101.26, 1.51, 1.0],
        "eQuilibrator": [-101.58, 0.18],
    },
}


def test_current_schema_takes_the_preferred_source(tmp_path):
    records = [
        GLUCOSE,
        # no eQuilibrator entry: dGPredictor's
        {
            "id": "cpd90001",
            "thermodynamics": {"dGPredictor": [-40.0, 5.0]},
            "pkas": {"MolGpKa": {"kind": "microscopic", "pKa": "1:4.2", "pKb": ""}},
        },
        # eQuilibrator's "no estimate" marker: unknown, not dGPredictor's
        {
            "id": "cpd90002",
            "thermodynamics": {
                "eQuilibrator": [132.52, 23901.43],
                "dGPredictor": [67.83, 8.41, 0.76],
            },
        },
        # Group contribution only (not pH-7 transformed), here with ModelSEED's 1e7 marker
        {
            "id": "cpd90003",
            "thermodynamics": {"Group contribution": [10000000, 10000000]},
            "pkas": {},
        },
        # a pathways list is carried onto the compound
        {"id": "cpd90004", "pathways": ["glycolysis"]},
    ]
    cpds = _write_db(tmp_path, records)

    glc = cpds["cpd00027"]
    assert (glc.delta_g, glc.delta_g_error) == (-101.58, 0.18)
    assert glc.delta_g_source == "eQuilibrator"
    assert (glc.pka, glc.pkb) == ("1:11.30;1:12.69", "1:-2.98;1:-3.65")
    assert glc.pathways == []

    only_dgp = cpds["cpd90001"]
    assert (only_dgp.delta_g, only_dgp.delta_g_error) == (-40.0, 5.0)
    assert only_dgp.delta_g_source == "dGPredictor"
    assert (only_dgp.pka, only_dgp.pkb) == ("1:4.2", None)

    for cpd_id in ("cpd90002", "cpd90003"):
        cpd = cpds[cpd_id]
        assert (cpd.delta_g, cpd.delta_g_error, cpd.delta_g_source) == (
            None,
            None,
            None,
        )
        assert (cpd.pka, cpd.pkb) == (None, None)

    assert cpds["cpd90004"].pathways == ["glycolysis"]


OLD_RECORDS = [
    {
        "id": "cpd00001",
        "abbreviation": "h2o",
        "charge": 0,
        "formula": "H2O",
        "name": "H2O",
        "mass": 18.0,
        "is_core": 1,
        "is_obsolete": 0,
        "source": "Primary Database",
        "deltag": -56.687,
        "deltagerr": 0.5,
        "pka": "1:1:15.70",
        "pkb": "1:1:-1.80",
    },
    # ModelSEED's unknown marker is passed through as it always was
    {"id": "cpd00002", "deltag": 10000000, "deltagerr": 10000000},
    # no energy, but an error and a pKb only
    {"id": "cpd00003", "deltag": None, "deltagerr": 2.0, "pkb": "1:3:-2.0"},
    # no thermodynamic fields at all
    {"id": "cpd00004"},
]


def test_old_schema_loads_as_before(tmp_path):
    cpds = _write_db(tmp_path, OLD_RECORDS)
    for record in OLD_RECORDS:
        cpd = cpds[record["id"]]
        # what _load_metabolites always passed: the top-level fields, unchanged
        assert cpd.delta_g == record.get("deltag")
        assert cpd.delta_g_error == record.get("deltagerr")
        assert cpd.pka == record.get("pka")
        assert cpd.pkb == record.get("pkb")
        assert cpd.pathways == []
    assert cpds["cpd00001"].delta_g_source == "deltag"
    assert cpds["cpd00002"].delta_g_source == "deltag"
    assert cpds["cpd00003"].delta_g_source is None
    assert cpds["cpd00004"].delta_g_source is None


def test_top_level_fields_win_over_the_per_source_blocks():
    # the database carried both for a while before the top-level fields were retired
    record = dict(GLUCOSE, deltag=-102.12, deltagerr=0.16, pka="1:11:11.30", pkb=None)
    assert _thermodynamics(record) == (-102.12, 0.16, "deltag")
    assert _pkas(record) == ("1:11:11.30", None)


def test_no_estimate_markers_leave_the_energy_unknown():
    # eQuilibrator's marker: the energy is unknown, NOT dGPredictor's, which is on another scale
    sam = {
        "thermodynamics": {
            "eQuilibrator": [132.52, 23901.43],
            "dGPredictor": [67.83, 8.41, 0.76],
        }
    }
    assert _thermodynamics(sam) == (None, None, None)
    co2 = {
        "thermodynamics": {
            "eQuilibrator": [-92.26, 0.76],
            "dGPredictor": [-91.91, 2.09],
        }
    }
    assert _thermodynamics(co2) == (-92.26, 0.76, "eQuilibrator")
    unknown = {
        "thermodynamics": {
            "eQuilibrator": [27.8, 12482.4],
            "Group contribution": [1e7, 1e7],
        }
    }
    assert _thermodynamics(unknown) == (None, None, None)
    # dGPredictor has no marker: a large genuine error is kept
    wide = {"thermodynamics": {"dGPredictor": [-500.0, 911.43]}}
    assert _thermodynamics(wide) == (-500.0, 911.43, "dGPredictor")
    # an entry without an error
    bare = {"thermodynamics": {"eQuilibrator": [-10.0]}}
    assert _thermodynamics(bare) == (-10.0, None, "eQuilibrator")


DATABASE = os.path.expanduser("~/Documents/ModelSEEDDatabase")


@pytest.mark.skipif(
    not os.path.isdir(os.path.join(DATABASE, "Biochemistry")),
    reason="no ModelSEEDDatabase checkout at ~/Documents/ModelSEEDDatabase",
)
def test_real_database_compounds_get_energies():
    cpds = _load_metabolites(DATABASE)
    glc = cpds["cpd00027"]
    assert glc.delta_g is not None
    assert glc.delta_g_error is not None
    assert glc.delta_g_source in DELTA_G_SOURCES + ("deltag",)
    # reading only the top-level fields, none of the current database's compounds get one
    with_energy = sum(1 for cpd in cpds.values() if cpd.delta_g is not None)
    assert with_energy > 10000
