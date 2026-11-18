# -*- coding: utf-8 -*-
import json

from modelseedpy.biochem.modelseed_biochem import _load_metabolites


def test_compound_fields_land_in_the_right_attributes(tmp_path):
    biochem = tmp_path / "Biochemistry"
    biochem.mkdir()
    record = {
        "id": "cpd00001",
        "formula": "H2O",
        "name": "water",
        "charge": 0,
        "abbreviation": "h2o",
        "mass": 18,
        "deltag": -56.7,
        "deltagerr": 0.5,
        "is_core": 1,
        "is_obsolete": 0,
        "pka": "1:15.7",
        "pkb": "1:-1.7",
        "source": "Primary Database",
    }
    (biochem / "compound_00.json").write_text(json.dumps([record]))
    cpd = _load_metabolites(str(tmp_path))["cpd00001"]
    assert cpd.pka == "1:15.7"
    assert cpd.pkb == "1:-1.7"
    assert cpd.source == "Primary Database"
    assert not cpd.is_abstract
