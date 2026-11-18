# -*- coding: utf-8 -*-
### test examples for the rast_client.py file

import logging

import pytest

from modelseedpy.core.rast_client import RastClient, split_annotation


def test_somefunction():

    pass


def _stub_client(results):
    """A RastClient whose RPC call returns the given results in turn, recording each request."""
    client = RastClient.__new__(RastClient)  # no RPC connection needed
    client.sent = []
    results = iter(results)

    def f(p_features):
        client.sent.append(p_features)
        return next(results)

    client.f = f
    return client


def _rast_result(*features):
    return [{"features": list(features), "analysis_events": []}]


def test_annotate_protein_batch_chunks():
    """
    chunk_size proteins go to each RAST call, and the functions are merged
    """
    proteins = {"p1": "MA", "p2": "MB", "p3": "MC", "p4": "MD", "p5": "ME"}
    client = _stub_client(
        [
            _rast_result(
                {"id": "p1", "function": "Role A"}, {"id": "p2", "function": "Role B"}
            ),
            _rast_result({"id": "p3", "function": "Role C"}, {"id": "p4"}),
            _rast_result({"id": "p5", "function": "Role D / Role E"}),
        ]
    )
    annotations = client.annotate_protein_batch(proteins, chunk_size=2)
    assert annotations == {
        "p1": "Role A",
        "p2": "Role B",
        "p3": "Role C",
        "p5": "Role D / Role E",
    }
    assert client.sent == [
        [
            {"id": "p1", "protein_translation": "MA"},
            {"id": "p2", "protein_translation": "MB"},
        ],
        [
            {"id": "p3", "protein_translation": "MC"},
            {"id": "p4", "protein_translation": "MD"},
        ],
        [{"id": "p5", "protein_translation": "ME"}],
    ]


def test_annotate_protein_batch_one_call_by_default():
    client = _stub_client([_rast_result({"id": "p1", "function": "Role A"})])
    assert client.annotate_protein_batch({"p1": "MA", "p2": "MB"}) == {"p1": "Role A"}
    assert len(client.sent) == 1


def test_annotate_protein_batch_empty_result(caplog):
    """
    a call that returns an empty result adds nothing, and the other calls still count
    """
    client = _stub_client([None, _rast_result({"id": "p2", "function": "Role B"})])
    with caplog.at_level(logging.WARNING, logger="modelseedpy.core.rast_client"):
        annotations = client.annotate_protein_batch(
            {"p1": "MA", "p2": "MB"}, chunk_size=1
        )
    assert annotations == {"p2": "Role B"}
    assert "starting at p1" in caplog.text


def test_annotate_protein_batch_no_proteins():
    client = _stub_client([])
    assert client.annotate_protein_batch({}) == {}
    assert client.sent == []


@pytest.mark.parametrize("chunk_size", [0, -1])
def test_annotate_protein_batch_rejects_chunk_size(chunk_size):
    client = _stub_client([])
    with pytest.raises(ValueError):
        client.annotate_protein_batch({"p1": "MA"}, chunk_size=chunk_size)
    assert client.sent == []


@pytest.mark.parametrize(
    "annotation, roles",
    [
        (None, []),
        ("", []),
        ("Role A", ["Role A"]),
        ("Role A; Role B", ["Role A", "Role B"]),
        ("Role A / Role B", ["Role A", "Role B"]),
        ("Role A @ Role B", ["Role A", "Role B"]),
        ("Role A; Role B / Role C @ Role D", ["Role A", "Role B", "Role C", "Role D"]),
    ],
)
def test_split_annotation(annotation, roles):
    assert split_annotation(annotation) == roles
