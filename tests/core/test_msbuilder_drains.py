# -*- coding: utf-8 -*-
from cobra import Metabolite

from modelseedpy.core.msbuilder import MSBuilder


class _TemplateSpecies:
    def __init__(self, species_id):
        self.id = species_id


class _Template:
    def __init__(self, drains):
        self.drains = drains


def _builder_with_drains(drains):
    """An MSBuilder holding only what build_sinks/build_demands read."""
    builder = MSBuilder.__new__(MSBuilder)
    builder.template = _Template(
        {_TemplateSpecies(cpd_id): bounds for cpd_id, bounds in drains.items()}
    )
    builder.template_species_to_model_species = {
        cpd_id: Metabolite(f"{cpd_id}0", name=cpd_id, compartment="c0")
        for cpd_id in drains
    }
    return builder


def test_build_demands_only_for_drains_that_allow_uptake():
    builder = _builder_with_drains({"cpd11416_c": (0, 1000), "cpd00001_c": (-50, 1000)})
    demands = builder.build_demands()
    assert [r.id for r in demands] == ["DM_cpd00001_c0"]
    assert demands[0].bounds == (-50, 0)


def test_consumption_only_drain_gets_an_outlet_and_no_source():
    builder = _builder_with_drains({"cpd11416_c": (0, 1000)})
    assert builder.build_demands() == []
    sinks = builder.build_sinks()
    assert [r.id for r in sinks] == ["SK_cpd11416_c0"]
    assert sinks[0].bounds == (0, 1000)
    # the sink consumes the biomass token: it is the outlet bio1 needs
    assert (
        sinks[0].metabolites[builder.template_species_to_model_species["cpd11416_c"]]
        == -1
    )
