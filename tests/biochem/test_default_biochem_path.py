# -*- coding: utf-8 -*-
import os

import modelseedpy.biochem.modelseed_biochem as biochem


def test_environment_variable_wins(monkeypatch, tmp_path):
    monkeypatch.setenv("MODELSEED_DB_PATH", str(tmp_path))
    assert biochem.default_biochem_path() == str(tmp_path)


def test_configured_path_used_when_it_exists(monkeypatch, tmp_path):
    monkeypatch.delenv("MODELSEED_DB_PATH", raising=False)
    monkeypatch.setattr(biochem.config, "get", lambda section, key: str(tmp_path))
    assert biochem.default_biochem_path() == str(tmp_path)


def test_falls_back_to_checkout_beside_the_repository(monkeypatch):
    monkeypatch.delenv("MODELSEED_DB_PATH", raising=False)
    monkeypatch.setattr(
        biochem.config, "get", lambda section, key: "/nonexistent/ModelSEEDDatabase"
    )
    package_dir = os.path.dirname(os.path.dirname(os.path.abspath(biochem.__file__)))
    sibling = os.path.join(
        os.path.dirname(os.path.dirname(package_dir)), "ModelSEEDDatabase"
    )
    expected = sibling if os.path.isdir(sibling) else "/nonexistent/ModelSEEDDatabase"
    assert biochem.default_biochem_path() == expected
