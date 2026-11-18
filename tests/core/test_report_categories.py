# -*- coding: utf-8 -*-
import subprocess
import sys

from modelseedpy.core import report


def test_import_does_not_load_category_data():
    """Importing the package must not read the ~60 MB category tables, and must
    not leak report.py's module names (numpy's load, ...) into modelseedpy.core."""
    code = (
        "import modelseedpy, modelseedpy.core, modelseedpy.core.report as r;"
        "print(r._category_names is None, hasattr(modelseedpy.core, 'load'))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    ).stdout.split()
    assert out[-2:] == ["True", "False"]


def test_categorize_mets_reads_the_tables_on_first_use():
    sugars, amino_acids, vitamins, minerals, energy, other = report.categorize_mets(
        ["cpd00027", "not_a_compound"]
    )
    assert sugars == ["D-Glucose (cpd00027)"]
    assert other == ["not_a_compound"]
