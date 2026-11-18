# -*- coding: utf-8 -*-
"""The FBAHelper helpers that MSCommunity, CommScores and MSMinimalMedia call."""
import pandas as pd
import pytest

from modelseedpy.core.fbahelper import FBAHelper
from modelseedpy.core.msmedia import MSMedia
from tests.test_data.mock_data import mock_model_ecoli_core


@pytest.mark.parametrize(
    "value, expected",
    [
        (1, True),
        (2.5, True),
        ("3", True),
        ("-4.5e2", True),
        (None, False),
        (True, False),
        (False, False),
        ("abc", False),
        (float("nan"), False),
        (float("inf"), False),
        ([1], False),
    ],
)
def test_isnumber(value, expected):
    assert FBAHelper.isnumber(value) is expected


def test_media_name():
    media = MSMedia.from_dict({"cpd00027": 10})
    media.id = "glucose"
    assert FBAHelper.mediaName(media) == FBAHelper.medianame(media) == "glucose"
    assert FBAHelper.mediaName(None) == "Complete"


def test_convert_kbase_media():
    media = MSMedia.from_dict({"cpd00027": 10, "cpd00007": 20})
    assert FBAHelper.convert_kbase_media(media) == {
        "EX_cpd00027_e0": 1000,
        "EX_cpd00007_e0": 1000,
    }
    assert FBAHelper.convert_kbase_media(media, None) == {
        "EX_cpd00027_e0": 10,
        "EX_cpd00007_e0": 20,
    }
    assert FBAHelper.convert_kbase_media(media, 5) == {
        "EX_cpd00027_e0": 5,
        "EX_cpd00007_e0": 5,
    }


def test_clean_fluxes():
    assert FBAHelper.clean_fluxes({"a": 1e-9, "b": -2.0, "c": 0}) == {"b": -2.0}
    series = FBAHelper.clean_fluxes(pd.Series({"a": 1e-9, "b": -2.0}))
    assert series.to_dict() == {"a": 0, "b": -2.0}


def test_compartment_helpers():
    assert FBAHelper.remove_compartment("cpd00027_e0") == "cpd00027"
    assert FBAHelper.remove_compartment("EX_cpd00027_e0") == "EX_cpd00027"
    assert FBAHelper.compartment_index("cpd00027_c1") == 1
    assert FBAHelper.compartment_index("cpd00027_e0") == 0
    assert FBAHelper.compartment_index("rxn00001_c12") == 12


def test_dict_helpers():
    assert FBAHelper.sum_dict({"a": 1, "b": 2}, {"b": 3, "c": 4}) == {
        "a": 1,
        "b": 5,
        "c": 4,
    }
    media = {"EX_a": 1, "EX_b": 2}
    assert FBAHelper.remove_media_compounds(media, ["EX_a", "EX_z"], False) == {
        "EX_b": 2
    }
    assert media == {"EX_a": 1, "EX_b": 2}


def test_solution_and_reaction_helpers():
    model = mock_model_ecoli_core(seed=True)
    sol = model.optimize()
    by_id = FBAHelper.solution_to_dict(sol)
    by_rxn = FBAHelper.solution_to_rxns_dict(sol, model)
    by_var = FBAHelper.solution_to_variables_dict(sol, model)
    biomass = model.reactions.get_by_id("Biomass_Ecoli_core")
    assert by_id["Biomass_Ecoli_core"] == pytest.approx(sol.objective_value)
    assert by_rxn[biomass] == by_id["Biomass_Ecoli_core"]
    assert by_var[biomass.forward_variable] == by_id["Biomass_Ecoli_core"]
    assert len(by_id) == len(by_rxn) == len(by_var) == len(model.reactions)
    rxn = model.reactions[0]
    assert rxn.reactants and rxn.products
    assert FBAHelper.rxn_mets_list(rxn) == rxn.reactants + rxn.products
