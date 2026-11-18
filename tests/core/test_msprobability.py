# -*- coding: utf-8 -*-
"""MSProbability without MSCommunity or cobrakbase, megaModel, and its biomass objective.

The numerics of prFBA are tested in test_msprobability_prfba.py. These tests do not need
MSCommunity: its absence is simulated where it matters.
"""
import importlib
import json
import sys

import pytest

import cobra
from cobra.io import read_sbml_model, write_sbml_model
from modelseedpy.core.msprobability import MSProbability, add_biomass_objective


def _member(mid, extra=False):
    """Glucose uptake, a "rxn" transport, biomass (bio1) and a biomass sink; with extra, a
    second route to biomass (rxn00001_c0) that only this member has."""
    glc_e = cobra.Metabolite("cpd00027_e0", compartment="e0", formula="C6H12O6")
    glc_c = cobra.Metabolite("cpd00027_c0", compartment="c0", formula="C6H12O6")
    bio_c = cobra.Metabolite("cpd11416_c0", compartment="c0", formula="R")
    ex = cobra.Reaction("EX_cpd00027_e0", lower_bound=-10, upper_bound=1000)
    ex.add_metabolites({glc_e: -1})
    tr = cobra.Reaction("rxn05573_c0", lower_bound=0, upper_bound=1000)
    tr.add_metabolites({glc_e: -1, glc_c: 1})
    tr.notes["probability"] = "0.5"
    bio = cobra.Reaction("bio1", name="biomass", lower_bound=0, upper_bound=1000)
    bio.add_metabolites({glc_c: -1, bio_c: 1})
    sink = cobra.Reaction("SK_cpd11416_c0", lower_bound=0, upper_bound=1000)
    sink.add_metabolites({bio_c: -1})
    reactions = [ex, tr, bio, sink]
    if extra:
        alt = cobra.Reaction("rxn00001_c0", lower_bound=0, upper_bound=1000)
        alt.add_metabolites({glc_c: -1, bio_c: 1})
        alt.notes["probability"] = "0.5"
        reactions.append(alt)
    model = cobra.Model(mid)
    model.add_reactions(reactions)
    model.objective = "bio1"
    return model


# ------------------------------------------------- without MSCommunity or cobrakbase
@pytest.fixture
def msprobability_without_mscommunity(monkeypatch):
    """modelseedpy.core.msprobability imported afresh while neither MSCommunity nor
    cobrakbase can be imported (neither is in install_requires). None in sys.modules
    makes an import raise ModuleNotFoundError; monkeypatch restores every entry
    afterwards."""
    for package in ("mscommunity", "cobrakbase"):
        for name in list(sys.modules):
            if name == package or name.startswith(package + "."):
                monkeypatch.setitem(sys.modules, name, None)
        monkeypatch.setitem(sys.modules, package, None)
    monkeypatch.delitem(sys.modules, "modelseedpy.core.msprobability", raising=False)
    import modelseedpy.core

    monkeypatch.setattr(modelseedpy.core, "msprobability", None, raising=False)
    return importlib.import_module("modelseedpy.core.msprobability")


def test_module_imports_without_mscommunity(msprobability_without_mscommunity):
    """Module-level imports of modelseedpy.community and cobrakbase made the module
    unimportable without them."""
    with pytest.raises(ModuleNotFoundError):
        import mscommunity  # noqa: F401
    with pytest.raises(ModuleNotFoundError):
        import cobrakbase  # noqa: F401
    assert hasattr(msprobability_without_mscommunity.MSProbability, "prFBA")


def test_prfba_single_model_runs_without_mscommunity(msprobability_without_mscommunity):
    MSP = msprobability_without_mscommunity.MSProbability
    sol = MSP.prFBA(_member("solo", extra=True))
    assert sol.status == "optimal"
    assert sol.fluxes["bio1"] > 0


def test_prfba_community_path_needs_mscommunity(msprobability_without_mscommunity):
    MSP = msprobability_without_mscommunity.MSProbability
    with pytest.raises(ModuleNotFoundError, match="mscommunity"):
        MSP.prFBA([_member("memA"), _member("memB")])


# ---------------------------------------------------------------- megaModel output path
def _write_members(directory):
    paths = []
    for mid, extra in (("m1", True), ("m2", False)):
        path = str(directory / f"{mid}.xml")
        write_sbml_model(_member(mid, extra), path)
        paths.append(path)
    return paths


def test_megaModel_computes_the_counts_and_writes_the_model(tmp_path, monkeypatch):
    pytest.importorskip("cobrakbase")
    paths = _write_members(tmp_path)
    monkeypatch.chdir(tmp_path)
    mega = MSProbability.megaModel({"cladeA": paths})
    with open(tmp_path / "reaction_counts" / "cladeA_reactions.json") as fh:
        counts = json.load(fh)
    assert counts["numMembers"] == 2
    assert counts["rxn00001_c0"] == 0.5 and counts["rxn05573_c0"] == 1.0
    assert mega.reactions.get_by_id("rxn00001_c0").notes["probability"] == 0.5
    written = read_sbml_model(str(tmp_path / "cladeA.xml"))
    assert float(written.reactions.get_by_id("rxn00001_c0").notes["probability"]) == 0.5
    assert len(written.reactions) == 5
    # the objective is the biomass reaction, not the first reaction of the model
    assert written.reactions.get_by_id("bio1").objective_coefficient == 1
    assert {r.id for r in written.reactions if r.objective_coefficient} == {"bio1"}


def test_megaModel_reads_supplied_counts(tmp_path, monkeypatch):
    pytest.importorskip("cobrakbase")
    paths = _write_members(tmp_path)
    counts_dir = tmp_path / "counts"
    counts_dir.mkdir()
    counts = {
        "EX_cpd00027_e0": 1.0,
        "rxn05573_c0": 1.0,
        "bio1": 1.0,
        "SK_cpd11416_c0": 1.0,
        "rxn00001_c0": 0.5,
        "numMembers": 2,
    }
    with open(counts_dir / "cladeA.json", "w") as fh:
        json.dump(counts, fh)
    monkeypatch.chdir(tmp_path)
    mega = MSProbability.megaModel(
        {"cladeA": paths}, reaction_counts_path=str(counts_dir)
    )
    assert mega.reactions.get_by_id("rxn00001_c0").notes["probability"] == 0.5
    assert not (tmp_path / "reaction_counts").exists()
    assert (tmp_path / "cladeA.xml").exists()


# ---------------------------------------------------------------- add_biomass_objective
def test_add_biomass_objective_takes_the_most_frequent_biomass():
    model = _member("mega")
    model.reactions.get_by_id("rxn05573_c0").objective_coefficient = 1
    glc_c = model.metabolites.get_by_id("cpd00027_c0")
    bio_c = model.metabolites.get_by_id("cpd11416_c0")
    # two biomass reactions share an equation; a third differs
    for rxn_id, stoich in (
        ("bio2", {glc_c: -1, bio_c: 1}),
        ("biomass_alt", {glc_c: -2, bio_c: 1}),
    ):
        rxn = cobra.Reaction(rxn_id, name="biomass", upper_bound=1000)
        rxn.add_metabolites(stoich)
        model.add_reactions([rxn])
    add_biomass_objective(model, captured_rxnIDs={"anything"})
    objective = {r.id for r in model.reactions if r.objective_coefficient}
    assert objective in ({"bio1"}, {"bio2"})


def test_add_biomass_objective_without_biomass_raises():
    model = _member("nobiomass")
    model.remove_reactions(["bio1"])
    with pytest.raises(ValueError, match="biomass"):
        add_biomass_objective(model)
