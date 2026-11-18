# -*- coding: utf-8 -*-
from modelseedpy.core.rast_client import RastClient


def test_annotate_protein_sequences_sends_every_sequence():
    client = RastClient.__new__(RastClient)  # no RPC connection needed
    sent = []
    client.f = lambda p_features: sent.append(p_features) or "result"
    assert client.annotate_protein_sequences({"p1": "MKV", "p2": "MAA"}) == "result"
    assert sent == [
        [
            {"id": "p1", "protein_translation": "MKV"},
            {"id": "p2", "protein_translation": "MAA"},
        ]
    ]
