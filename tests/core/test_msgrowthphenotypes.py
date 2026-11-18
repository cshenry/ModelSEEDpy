# -*- coding: utf-8 -*-
from modelseedpy.core.msgrowthphenotypes import MSGrowthPhenotype, MSGrowthPhenotypes
from modelseedpy.fbapkg.objectivepkg import ObjectiveData
from tests.core.test_msgapfill import get_model, media_glucose_aerobic  # noqa: F401


def _glucose_phenotypes(media):
    phenotypes = MSGrowthPhenotypes(
        base_media=media, base_uptake=0, base_excretion=1000
    )
    phenotypes.add_phenotypes(
        [
            MSGrowthPhenotype(
                "glucose_aerobic",
                base_media=media,
                experimental_value=1,
                experimental_value_is_binary=True,
                objective=ObjectiveData.from_string("MAX{bio1}"),
            )
        ]
    )
    return phenotypes


def test_simulate_phenotypes_runs_and_predicts_growth(get_model, media_glucose_aerobic):
    """simulate_phenotypes must run end to end (it raised NameError on undefined
    names such as full_media) and call growth for the complete E. coli core model
    on glucose aerobic a correct positive."""
    model = get_model([])
    # ModelSEED models name their biomass reaction bio1, which simulate() expects
    model.reactions.get_by_id("BIOMASS_Ecoli_core_w_GAM_c0").id = "bio1"
    model.repair()
    model.objective = "bio1"
    output = _glucose_phenotypes(media_glucose_aerobic).simulate_phenotypes(model)
    print(output["details"])
    assert output["data"]["summary"]["CP"] == 1
    assert output["data"]["summary"]["FN"] == 0
