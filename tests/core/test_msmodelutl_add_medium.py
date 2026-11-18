# -*- coding: utf-8 -*-
from modelseedpy.core.msmedia import MSMedia
from modelseedpy.core.msmodelutl import MSModelUtil
from tests.test_data.mock_data import mock_model_ecoli_core


def _model_with_seed_exchanges():
    model = mock_model_ecoli_core(seed=True)
    model.reactions.get_by_id("EX_glc__D_e").id = "EX_cpd00027_e0"
    model.reactions.get_by_id("EX_o2_e").id = "EX_cpd00007_e0"
    model.repair()
    return model


def test_add_medium_keeps_the_media_bounds():
    model = _model_with_seed_exchanges()
    media = MSMedia.from_dict({"cpd00027": 10, "cpd00007": 20})
    medium = MSModelUtil(model).add_medium(media)
    assert medium["EX_cpd00027_e0"] == 10
    assert medium["EX_cpd00007_e0"] == 20


def test_add_medium_uniform_uptake_still_overrides():
    model = _model_with_seed_exchanges()
    media = MSMedia.from_dict({"cpd00027": 10, "cpd00007": 20})
    medium = MSModelUtil(model).add_medium(media, uniform_uptake=5)
    assert medium["EX_cpd00027_e0"] == 5
    assert medium["EX_cpd00007_e0"] == 5


def test_add_medium_dict_of_compounds_or_exchanges():
    model = _model_with_seed_exchanges()
    util = MSModelUtil(model)
    # compound ids are read as EX_<id>_e0; ids without an exchange are skipped
    medium = util.add_medium({"cpd00027": 10, "cpd00007": 20, "cpd99999": 5})
    assert medium == {"EX_cpd00027_e0": 10, "EX_cpd00007_e0": 20}
    # exchange ids are used as given, and every uptake not listed is closed
    medium = util.add_medium({"EX_cpd00027_e0": 4})
    assert medium == {"EX_cpd00027_e0": 4}
    assert model.reactions.get_by_id("EX_cpd00007_e0").lower_bound == 0


def test_add_medium_none_leaves_the_medium():
    model = _model_with_seed_exchanges()
    before = dict(model.medium)
    assert MSModelUtil(model).add_medium(None) == before
    assert model.medium == before


def test_add_medium_reapplies_the_o2_cap_without_raising_uptake():
    model = _model_with_seed_exchanges()
    util = MSModelUtil(model, o2limit=10)
    o2 = model.reactions.get_by_id("EX_cpd00007_e0")
    # setting the medium would raise the O2 uptake to 20: the cap holds it at 10
    util.add_medium({"cpd00027": 10, "cpd00007": 20})
    assert o2.lower_bound == -10
    # a medium with less O2 than the cap, or none, keeps it
    util.add_medium({"cpd00027": 10, "cpd00007": 4})
    assert o2.lower_bound == -4
    util.add_medium({"cpd00027": 10})
    assert o2.lower_bound == 0
