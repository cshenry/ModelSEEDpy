# -*- coding: utf-8 -*-
"""The packaged genome classifier (data/ml) and templates (data/templates), MSPredict,
and MSBuilder.auto_select_template on top of them."""
import os

import pytest

import modelseedpy
import modelseedpy.helpers
from modelseedpy.core import msbuilder, mspredict
from modelseedpy.core.msbuilder import MSBuilder, MSGenomeClass
from modelseedpy.core.mspredict import MSPredict, DEFAULT_CLASSIFIER
from tests.test_data.mock_data import mock_genome_ecoli_rast

DATA = os.path.join(os.path.dirname(modelseedpy.__file__), "data")


@pytest.fixture(scope="module")
def ecoli_genome():
    return mock_genome_ecoli_rast()


@pytest.fixture(scope="module")
def predictor():
    return MSPredict()


@pytest.fixture
def no_download(monkeypatch):
    """Fail the test if a data file would be downloaded rather than read from the
    package."""

    def fail(*args, **kwargs):
        raise AssertionError(f"tried to download {args}")

    monkeypatch.setattr(modelseedpy.helpers.requests, "get", fail)


def test_classifier_and_templates_ship_in_the_package():
    for path in [
        f"ml/{DEFAULT_CLASSIFIER}.pickle",
        f"ml/{DEFAULT_CLASSIFIER}_features.json",
        "templates/template_core.json",
        "templates/template_gram_neg.json",
        "templates/template_gram_pos.json",
    ]:
        assert os.path.isfile(os.path.join(DATA, path)), path


def test_classifier_loads_and_matches_its_features(no_download):
    classifier = modelseedpy.helpers.get_classifier(DEFAULT_CLASSIFIER)
    assert len(classifier.features) == 1411
    assert classifier.model.n_features_in_ == len(classifier.features)
    assert list(classifier.model.classes_) == ["A", "C", "N", "P"]


def test_genome_class_enum_is_the_msbuilder_one():
    assert mspredict.MSGenomeClass is msbuilder.MSGenomeClass


def test_predict_ecoli_is_gram_negative(predictor, ecoli_genome):
    assert predictor.predict(ecoli_genome) is MSGenomeClass.N


def test_predict_rejects_an_unknown_class(predictor, ecoli_genome, monkeypatch):
    monkeypatch.setattr(predictor.genome_classifier, "classify", lambda genome: "X")
    with pytest.raises(ValueError):
        predictor.predict(ecoli_genome)


def test_auto_select_template_gram_positive(no_download):
    template_core, template_genome_scale = MSPredict.auto_select_template(
        MSGenomeClass.P
    )
    assert template_core.id == "CoreModelTemplateV2"
    assert template_genome_scale.id == "GramPositive.modeltemplate"
    assert "bio1" in template_genome_scale.biomasses


def test_auto_select_template_rejects_an_unknown_class():
    with pytest.raises(ValueError):
        MSPredict.auto_select_template("N")


def test_msbuilder_auto_select_template_still_returns_the_class_string(
    ecoli_genome, no_download
):
    builder = MSBuilder(ecoli_genome)
    genome_class = builder.auto_select_template()
    assert isinstance(genome_class, str) and genome_class == "N"
    assert builder.genome_class == "N"
    assert builder.template.id == "GramNegative.modeltemplate"
