# -*- coding: utf-8 -*-
import json
import os

import cobra
import pytest
from cobra.core.dictlist import DictList
from cobra.flux_analysis import flux_variability_analysis
from pandas import DataFrame, Series

from modelseedpy.core import report

TEST_DATA = os.path.join(os.path.dirname(__file__), "..", "test_data")
CPD_NAMES = os.path.join(report.package_dir, "data", "cpdNames.json")


@pytest.fixture
def e_coli_core():
    return cobra.io.load_json_model(os.path.join(TEST_DATA, "e_coli_core.json"))


def test_fba_report(e_coli_core, tmp_path):
    model = e_coli_core
    solution = model.optimize()
    fva = flux_variability_analysis(model, processes=1)
    essential = {model.genes.get_by_id("b2416")}
    path = tmp_path / "fba.html"

    html = report.fba_report(
        model, solution, fva, essential, "e_coli_core", "glucose_minimal", str(path)
    )

    assert path.read_text() == html
    # overview tab
    for value in ("e_coli_core", "glucose_minimal", "optimal", "Objective value"):
        assert value in html
    # summary tab: uptake, secretion and objective columns, one row per entry
    summary = report.model_summary(model, solution)
    assert all(len(row) == 6 for row in summary)
    uptake = {row[0] for row in summary}
    assert "D-Glucose\n(glc__D_e)" in uptake
    assert (
        summary[0][4]
        == "Biomass Objective Function with GAM\n(BIOMASS_Ecoli_core_w_GAM)"
    )
    assert summary[0][5] == pytest.approx(solution.objective_value, abs=1e-6)
    assert "(glc__D_e)" in html
    # ATP tab
    atp_rows, is_atp = report.atp_summary_formatter(model, solution)
    assert is_atp and {"PRODUCING", "CONSUMING"} == {row[0] for row in atp_rows}
    assert "ATPS4r" in html
    # reaction tabs are filled by DataTables from JSON; the HTML carries no
    # per-character rows rendered from the JSON string
    reactions = json.loads(report.reaction_formater(model, solution, fva, ex=False))
    exchanges = json.loads(report.reaction_formater(model, solution, fva, ex=True))
    assert {r["id"] for r in exchanges} == {r.id for r in model.exchanges}
    assert len(reactions) + len(exchanges) == len(model.reactions)
    assert '"id": "EX_glc__D_e"' in html and '"id": "PGI"' in html
    assert '<td style="text-align: center">[</td>' not in html
    # essential genes tab
    genes = json.loads(report.essential_genes_formatter(model, essential))
    assert {g["name"] for g in genes if g["essential"] == "Yes"} == {"b2416"}


def test_fba_report_without_fva_or_essential_genes(e_coli_core):
    html = report.fba_report(
        e_coli_core, e_coli_core.optimize(), None, None, "m", "media", None
    )
    assert "Select FVA setting and rerun to produce results." in html
    assert "Select simulate all single KO to produce results." in html


def test_atp_summary_without_atp():
    message, is_atp = report.atp_summary_formatter(cobra.Model("no_atp"))
    assert not is_atp and "atp_c" in message


def test_steadycom_report(tmp_path):
    members = ["iA", "iB"]
    flux_df = DataFrame(
        {"iA": [0.5, 0.0, 0.0, 0.0, 0.2], "iB": [0.0, 0.3, 0.1, 0.4, 0.0]},
        index=["cpd00027", "cpd00029", "zz_Environment", "zz_Species1", "zz_Species2"],
    )
    flux_df["Environment"] = [0.0, 0.0, 0.0, 0.1, 0.0]
    flux_df.index.name = "Metabolite/Donor ID"
    exMets_df = DataFrame(
        {"Environment": [" ", "Acetate", ""], "iA": ["Glucose", "", ""]},
        index=["Environment"] + members,
    )
    exMets_df["iB"] = ["", "", "Acetate"]
    path = tmp_path / "steadycom.html"

    html = report.steadycom_report(flux_df, exMets_df, str(path))

    assert path.read_text() == html
    assert "SteadyCom Results" in html
    assert "cpd00027" in html and "Species1" in html and "Glucose" in html
    assert "zz_" not in html
    assert list(flux_df.index)[-1] == "zz_Species2"  # the caller's frame is untouched


def _calculate_scores_row(model1, model2, mip1="2 (1)", mip2="0 (0)"):
    """A row as CommScores.calculate_scores builds it (cip_score=True, costless=True,
    no KBase genomes, so no FS)."""
    return Series(
        {
            "model1": model1,
            "model2": model2,
            "media": "media0",
            "model1 growth": 0.5,
            "model2 growth": 0.3,
            "community growth": 0.7,
            "coculture growth model0": 0.3,
            "coculture growth model1": 0.2,
            "MRO_model1": "50.000% (2/4)",
            "MRO_model2": "66.667% (2/3)",
            "CIP": 3,
            "MIP_model1 (costless)": mip1,
            "MIP_model2 (costless)": mip2,
            "BSS_model1": "25.0%",
            "BSS_model2": "0.0%",
            "PC_comm": 0.875,
            "PC_model1": 1.2,
            "PC_model2": 0.9,
            "BIT": "mutualism",
            "GYD1": 0.66667,
            "GYD2": 1.5,
        }
    )


@pytest.fixture
def commscores_output():
    df = DataFrame(
        [_calculate_scores_row("iA", "iB"), _calculate_scores_row("iA", "iC", "", "")]
    )
    mets = [
        {
            "MRO metabolites": ["cpd00027", "cpd00029"],
            "CIP metabolites": ["cpd00011", "cpd99999"],
            "MIP model1 metabolites": ["cpd00029"],
            "MIP model2 metabolites": [],
        },
        # MIP failed for this pair, and the CIP score was not requested
        {
            "MRO metabolites": ["cpd00027"],
            "MIP model1 metabolites": [None],
            "MIP model2 metabolites": [None],
        },
    ]
    return df, mets


def test_commscores_report(commscores_output, tmp_path):
    df, mets = commscores_output
    before = open(CPD_NAMES, "rb").read()
    path = tmp_path / "commscores.html"

    html = report.commscores_report(df, mets, str(path))

    assert path.read_text() == html
    assert open(CPD_NAMES, "rb").read() == before  # the package is never written
    assert "D-Glucose, Acetate" in html  # names from data/cpdNames.json
    assert "CO2, cpd99999" in html  # an unknown ID stands for itself
    assert "iA ++ iB in media0" in html and "iA ++ iC in media0" in html
    assert "mutualism" in html  # the full table keeps the BIT column
    assert df.index.name is None  # the caller's frame is untouched


def test_commscores_report_names_from_database(commscores_output, monkeypatch):
    import modelseedpy.biochem

    loaded = []

    class FakeDatabase:
        compounds = DictList([cobra.Metabolite("cpd99999", name="Testose")])

    def fake_from_local(path):
        loaded.append(path)
        return FakeDatabase()

    monkeypatch.setattr(modelseedpy.biochem, "from_local", fake_from_local)
    df, mets = commscores_output
    mets[1]["CIP metabolites"] = ["cpd99999", "cpd88888"]
    before = open(CPD_NAMES, "rb").read()

    html = report.commscores_report(df, mets, None, msdb_path="/db")

    assert loaded == ["/db"]  # loaded once, for the first unknown ID
    assert "CO2, Testose" in html and "Testose, cpd88888" in html
    assert open(CPD_NAMES, "rb").read() == before
