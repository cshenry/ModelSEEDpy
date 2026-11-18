# -*- coding: utf-8 -*-
"""MSBuilder.build_base_model / build, add_atpm, integrate_gapfill_solution,
build_and_gapfill, and msatpcorrection.load_default_medias."""
import inspect
import os

import cobra
import pytest

import modelseedpy
import modelseedpy.core.msatpcorrection as msatpcorrection
from modelseedpy.core.exceptions import GapfillingError
from modelseedpy.core.msatpcorrection import load_default_medias
from modelseedpy.core.msbuilder import MSBuilder
from modelseedpy.core.msgenome import MSGenome, normalize_role
from modelseedpy.core.msmedia import MSMedia
from modelseedpy.core.mstemplate import MSTemplateBuilder
from modelseedpy.fbapkg.mspackagemanager import MSPackageManager
from modelseedpy.helpers import config, get_template
from tests.test_data.mock_data import mock_genome_ecoli_rast

ATPM_COMPOUNDS = ["cpd00001", "cpd00002", "cpd00008", "cpd00009", "cpd00067"]


@pytest.fixture(scope="module")
def template_core():
    return MSTemplateBuilder.from_dict(get_template("template_core")).build()


def stub_pipeline(monkeypatch, base, gapfill_result):
    """Replace the base model build, ATP correction and gapfilling, so that
    build_and_gapfill only does its own bookkeeping."""

    class StubATPCorrection:
        def __init__(self, *args, **kwargs):
            self.args, self.kwargs = args, kwargs

        def evaluate_growth_media(self):
            return {}

        def determine_growth_media(self):
            pass

        def apply_growth_media_gapfilling(self):
            pass

        def expand_model_to_genome_scale(self):
            pass

        def build_tests(self):
            return []

    class StubGapfill:
        def __init__(self, *args, **kwargs):
            pass

        def run_gapfilling(self, media):
            return gapfill_result

    monkeypatch.setattr(MSBuilder, "build_base_model", lambda self, *a, **k: base)
    monkeypatch.setattr(msatpcorrection, "load_default_medias", lambda: [])
    monkeypatch.setattr(modelseedpy, "MSATPCorrection", StubATPCorrection)
    monkeypatch.setattr(modelseedpy, "MSGapfill", StubGapfill)


def model_with_atp_compounds(index):
    model = cobra.Model("m")
    model.add_metabolites(
        [
            cobra.Metabolite(f"{c}_c{index}", compartment=f"c{index}")
            for c in ATPM_COMPOUNDS
        ]
    )
    return model


def test_build_keeps_its_signature_and_returns_build_base_model(monkeypatch):
    assert list(inspect.signature(MSBuilder.build).parameters) == [
        "self",
        "model_or_id",
        "index",
        "allow_all_non_grp_reactions",
        "annotate_with_rast",
        "biomass_classic",
        "biomass_gc",
        "add_reaction_from_rast_annotation",
    ]
    calls = []

    def fake(self, *args):
        calls.append(args)
        return "model"

    monkeypatch.setattr(MSBuilder, "build_base_model", fake)
    builder = MSBuilder(MSGenome())
    assert builder.build("m", "1", True, False, True, 0.6, False) == "model"
    assert calls == [("m", "1", True, False, True, 0.6, False)]
    assert builder.build("m") == "model"
    assert calls[-1] == ("m", "0", False, True, False, 0.5, True)


def test_template_core_is_optional(template_core):
    assert MSBuilder(MSGenome()).template_core is None
    builder = MSBuilder(MSGenome(), template_core=template_core)
    assert builder.template_core is template_core


@pytest.mark.parametrize("index", ["0", "1"])
def test_add_atpm_uses_the_index(index):
    model = model_with_atp_compounds(index)
    assert MSBuilder.add_atpm(model, index) == f"ATPM_c{index}"
    assert MSBuilder.add_atpm(model, index) == f"ATPM_c{index}"  # added once
    assert len(model.reactions) == 1
    atpm = model.reactions.get_by_id(f"ATPM_c{index}")
    assert atpm.bounds == (0, 1000)
    assert {m.id: v for m, v in atpm.metabolites.items()} == {
        f"cpd00001_c{index}": -1,
        f"cpd00002_c{index}": -1,
        f"cpd00008_c{index}": 1,
        f"cpd00009_c{index}": 1,
        f"cpd00067_c{index}": 1,
    }


def test_integrate_gapfill_solution_uses_the_index(template_core):
    model = cobra.Model("m")
    added, exchanges = MSBuilder.integrate_gapfill_solution(
        template_core, model, {"rxn05467_c": (-1000, 0)}, "1"
    )
    # CO2 diffusion: cytosol takes the index, the extracellular compound stays e0
    assert [r.id for r in added] == ["rxn05467_c1"]
    rxn = model.reactions.rxn05467_c1
    assert rxn.bounds == (-1000, 0)
    assert {m.id for m in rxn.metabolites} == {"cpd00011_c1", "cpd00011_e0"}
    assert [r.id for r in exchanges] == ["EX_cpd00011_e0"]


@pytest.mark.parametrize("index", ["0", "1", "10"])
def test_build_and_gapfill_maps_new_reactions_to_the_template(
    monkeypatch, template_core, index
):
    """The gapfiller names model reactions (template id + index, whatever the
    index's length); the solution keeps template reactions only."""
    new = {
        f"rxn00256_c{index}": "<",
        f"rxn05467_c{index}": "=",
        "rxn99999_c0": ">",  # not in the template
    }
    stub_pipeline(monkeypatch, cobra.Model("base"), {"new": new, "reversed": {}})
    builder = MSBuilder(MSGenome(), template_core)

    model, _atpc, _tests, gap_sol = builder.build_and_gapfill(
        "m", None, index=index, add_maintenance_atp_reaction=False
    )

    assert gap_sol == {"rxn00256_c": (-1000, 0), "rxn05467_c": (-1000, 1000)}
    assert model.reactions.get_by_id(f"rxn00256_c{index}").bounds == (-1000, 0)
    assert f"rxn05467_c{index}" in model.reactions


def test_build_and_gapfill_passes_index_medias_and_core_template(
    monkeypatch, template_core
):
    base = model_with_atp_compounds("1")
    stub_pipeline(monkeypatch, base, {"new": {}, "reversed": {}})
    medias = [["media", 1]]
    monkeypatch.setattr(msatpcorrection, "load_default_medias", lambda: medias)
    builder = MSBuilder(MSGenome(), template_core, template_core=template_core)

    model, atpc, tests, gap_sol = builder.build_and_gapfill("m", None, index="1")

    assert "ATPM_c1" in model.reactions and "ATPM_c1" in base.reactions
    assert atpc.args == (base, template_core, medias)
    assert atpc.kwargs == {
        "compartment": "c1",
        "atp_hydrolysis_id": "ATPM_c1",
        "load_default_medias": False,
    }
    assert model is not base and gap_sol == {} and tests == []


def test_build_and_gapfill_raises_when_gapfilling_finds_nothing(
    monkeypatch, template_core
):
    stub_pipeline(monkeypatch, cobra.Model("base"), None)
    media = MSMedia.from_dict({"cpd00027": 10})
    media.id = "Glc"
    builder = MSBuilder(MSGenome(), template_core)
    with pytest.raises(GapfillingError, match="Glc"):
        builder.build_and_gapfill("m", media, add_maintenance_atp_reaction=False)


def test_load_default_medias(tmp_path):
    medias = {media.id: (media, min_obj) for media, min_obj in load_default_medias()}
    assert len(medias) == 54
    glc_o2, min_obj = medias["Glc.O2"]
    assert min_obj == 5  # min_gap
    assert medias["Glc"][1] == 0.01  # default
    assert {c.id: c.upper_bound for c in glc_o2.mediacompounds} == {
        "cpd00027": 1000,
        "cpd00007": 1000,
        "cpd00001": 1000,
        "cpd00067": 1000,
    }

    path = tmp_path / "medias.tsv"
    path.write_text("seed\tA\tname\nEX_cpd00027_e0\t1\tglucose\n")
    ((media, min_obj),) = load_default_medias(str(path), default_min_obj=0.5)
    assert media.id == "A" and min_obj == 0.5
    assert {c.id for c in media.mediacompounds} == {"cpd00027", "cpd00001", "cpd00067"}


DATABASE = os.path.join(config.get("biochem", "path"), "Biochemistry")


@pytest.mark.skipif(
    not os.path.isdir(DATABASE),
    reason="ATP correction reads the ModelSEED database (config.cfg [biochem] path)",
)
@pytest.mark.parametrize(
    "index, pass_template_core", [("0", False), ("1", True)], ids=["c0", "c1"]
)
def test_build_and_gapfill_end_to_end(template_core, index, pass_template_core):
    """E. coli K-12 without citrate synthase, on the core template: the base model
    cannot grow on glucose; build_and_gapfill runs the real ATP correction and
    gapfilling and returns a model that grows."""
    genome = mock_genome_ecoli_rast()
    knockout = {
        normalize_role(role.name)
        for cpx in template_core.reactions.rxn00256_c.get_complexes()
        for role in cpx.roles
    }
    for feature in genome.features:
        if "RAST" in feature.ontology_terms:
            feature.ontology_terms["RAST"] = [
                r
                for r in feature.ontology_terms["RAST"]
                if normalize_role(r) not in knockout
            ]
    media = {m.id: m for m, _ in load_default_medias()}["Glc.O2"]

    def growth(model):
        model = model.copy()
        MSPackageManager.get_pkg_mgr(model).getpkg("KBaseMediaPkg").build_package(media)
        model.objective = "bio1"
        return model.slim_optimize(error_value=0)

    builder = MSBuilder(
        genome,
        template_core,
        template_core=template_core if pass_template_core else None,
    )
    model, atp_correction, tests, gap_sol = builder.build_and_gapfill(
        "ecoli", media, index=index, annotate_with_rast=False
    )

    base = builder.base_model
    assert f"rxn00256_c{index}" not in base.reactions
    assert growth(base) < 1e-6
    assert "rxn00256_c" in gap_sol
    for rxn_id, bounds in gap_sol.items():
        assert model.reactions.get_by_id(f"{rxn_id}{index}").bounds == bounds
    assert f"ATPM_c{index}" in model.reactions
    assert growth(model) > 1
    # the default medias passed in were kept (the TSV has its own "empty" media)
    assert set(atp_correction.media_hash) == {m.id for m, _ in load_default_medias()}
    assert len(tests) > 0
