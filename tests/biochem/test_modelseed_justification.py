# -*- coding: utf-8 -*-
import json

import pytest

import modelseedpy.core.optlanghelper as optlanghelper
from modelseedpy.biochem.modelseed_biochem import ModelSEEDDatabase
from modelseedpy.biochem.modelseed_compound import ModelSEEDCompound2
from modelseedpy.biochem.modelseed_justification import (
    build_correction_model,
    justifyDB,
)
from modelseedpy.biochem.modelseed_reaction import ModelSEEDReaction2
from modelseedpy.core.exceptions import FeasibilityError
from modelseedpy.core.report import msdb_justification_report

# id: (formula, charge)
COMPOUNDS = {
    "cpd00067": ("H", 1),  # proton
    "cpdA": ("C2", 0),
    "cpdB": ("C3", 0),  # should be C2
    "cpdC": ("C4", 0),
    "cpdD": ("O3", 0),
    "cpdE": ("O2", 0),  # should be O3
    "cpdG": ("O6", 0),
    "cpdN": ("S", 0),
    "cpdP": ("S", 2),  # should be neutral
    "cpdQ": ("S", 0),
    "cpdJ": ("C2H2", 0),
    "cpdK": ("C2H", -1),
    "cpdL": ("C3H4", 0),
    "cpdM": ("C3H3", -1),
    "cpdR": ("C4H3", -1),
    "cpdT": ("C4H4", 0),
}
# id: stoichiometry; the frequent compounds A, D and N are the ones to keep
REACTIONS = {
    "rxn1": {"cpdA": -1, "cpdB": 1},  # carbon gained
    "rxn2": {"cpdA": -2, "cpdC": 1},
    "rxn3": {"cpdD": -1, "cpdE": 1},  # oxygen lost
    "rxn4": {"cpdD": -2, "cpdG": 1},
    "rxn5": {"cpdJ": -1, "cpdK": 1, "cpd00067": 1},  # balanced with its proton
    "rxn6": {"cpdL": -1, "cpdM": 1},  # releases a proton it does not list
    "rxn7": {"cpdN": -1, "cpdP": 1},  # charge gained
    "rxn8": {"cpdN": -1, "cpdQ": 1},
    "rxn9": {"cpdR": -1, "cpdT": 1},  # takes up a proton it does not list
}
EXPECTED_CHANGES = {
    "cpdB": {"C": (3, 2)},
    "cpdE": {"O": (2, 3)},
    "cpdP": {"charge": (2, 0)},
    "rxn6": {"protons": (0, 1)},
    "rxn9": {"protons": (0, -1)},
}


@pytest.fixture
def msdb():
    """A ModelSEEDDatabase shaped as from_local builds it: reactions hold
    compartment tokens (cpdA_0) of the database compounds (cpdA)."""
    compounds = {
        cpd_id: ModelSEEDCompound2(cpd_id, formula, cpd_id, charge)
        for cpd_id, (formula, charge) in COMPOUNDS.items()
    }
    tokens, reactions = {}, []
    for rxn_id, stoichiometry in REACTIONS.items():
        metabolites = {}
        for cpd_id, coef in stoichiometry.items():
            if cpd_id not in tokens:
                token = compounds[cpd_id].copy()
                token.id, token.compartment = f"{cpd_id}_0", "0"
                tokens[cpd_id] = token
            metabolites[tokens[cpd_id]] = coef
        rxn = ModelSEEDReaction2(rxn_id, status="OK")
        rxn.add_metabolites(metabolites)
        reactions.append(rxn)
    return ModelSEEDDatabase(compounds.values(), reactions, tokens.values())


def test_build_correction_model(msdb):
    model = build_correction_model(msdb)

    names = set(model.variables.keys())
    assert {"cpdB~C_diffpos", "cpdB~C_diffneg", "cpdP~charge_diffneg"} <= names
    assert not any(name.endswith("_error") for name in names)
    assert not any(name.startswith("cpd00067~") for name in names)
    protons = model.variables["rxn5~protstoich"]
    assert (protons.lb, protons.ub) == (-1000, 1000)
    constraints = set(model.constraints.keys())
    assert {"rxn1_C", "rxn1_H", "rxn1_charge", "rxn5_H", "rxn7_charge"} <= constraints
    # the frequent compound costs more to change
    coefficients = model.objective.get_linear_coefficients(
        [model.variables["cpdA~C_diffpos"], model.variables["cpdB~C_diffpos"]]
    )
    assert list(coefficients.values()) == [3, 1]
    # the database is not modified: rxn5 keeps its proton
    assert "cpd00067_0" in [met.id for met in msdb.reactions.rxn5.metabolites]


def test_justifyDB_proposed_changes(msdb, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    model, changes = justifyDB(msdb)

    assert model.status == "optimal"
    assert list(tmp_path.iterdir()) == []  # nothing is written by default
    assert set(changes) == set(EXPECTED_CHANGES)
    for entity, props in EXPECTED_CHANGES.items():
        assert set(changes[entity]) == set(props)
        for prop, (original, proposed) in props.items():
            assert changes[entity][prop]["original"] == original
            assert changes[entity][prop]["proposed"] == pytest.approx(proposed)


def test_justifyDB_exports(msdb, tmp_path, monkeypatch):
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    model_path = tmp_path / "out" / "Correct_MSDB.lp"
    changes_path = tmp_path / "corrections.json"

    model, changes = justifyDB(
        msdb, changes_path=str(changes_path), model_path=str(model_path)
    )

    assert list(cwd.iterdir()) == []
    assert "rxn1_C" in model_path.read_text()
    exported = json.loads((tmp_path / "out" / "Correct_MSDB.json").read_text())
    assert exported["name"] == "Correct_MSDB"
    assert json.loads(changes_path.read_text()) == changes


def test_justifyDB_raises_when_not_optimal(msdb, monkeypatch):
    monkeypatch.setattr(optlanghelper.Model, "optimize", lambda self: "infeasible")
    with pytest.raises(FeasibilityError, match="infeasible"):
        justifyDB(msdb)


def test_msdb_justification_report(msdb, tmp_path):
    _, changes = justifyDB(msdb)
    path = tmp_path / "msdb.html"

    html = msdb_justification_report(changes, str(path))

    assert path.read_text() == html
    assert "Correction optimization of MSDB" in html
    for entity in EXPECTED_CHANGES:
        assert entity in html
    assert "protons" in html and "charge" in html
    assert "No changes were proposed." in msdb_justification_report({}, None)
