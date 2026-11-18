# -*- coding: utf-8 -*-
import math

import cobra
from cobra.core.dictlist import DictList

from modelseedpy.biochem.modelseed_biochem import ModelSEEDBiochem
from modelseedpy.biochem.modelseed_compound import ModelSEEDCompound2
from modelseedpy.fbapkg.fullthermopkg import FullThermoPkg


class _FakeBiochem:
    def __init__(self, compounds):
        self.compounds = DictList(compounds)


def _model():
    """cpd99002_c0 takes its energy from the database; cpd99005_c0 is not in it."""
    model = cobra.Model("db_energies")
    from_db = cobra.Metabolite("cpd99002_c0", compartment="c0", charge=0, formula="C")
    unknown = cobra.Metabolite("cpd99005_c0", compartment="c0", charge=0, formula="C")
    ext = cobra.Metabolite("cpd99003_e0", compartment="e0", charge=0, formula="C")
    ext.notes = {"deltag": -50.0}
    rxn = cobra.Reaction("rxn_test_c0", lower_bound=0, upper_bound=1000)
    rxn.add_metabolites({ext: -1, from_db: 1, unknown: 1})
    ex = cobra.Reaction("EX_cpd99003_e0", lower_bound=-1000, upper_bound=1000)
    ex.add_metabolites({ext: -1})
    sinks = []
    for met in (from_db, unknown):
        sink = cobra.Reaction(f"DM_{met.id}", lower_bound=0, upper_bound=1000)
        sink.add_metabolites({met: -1})
        sinks.append(sink)
    model.add_reactions([rxn, ex] + sinks)
    model.objective = "DM_cpd99002_c0"
    return model


def test_formation_energy_is_read_from_the_database(monkeypatch):
    fake = _FakeBiochem([ModelSEEDCompound2("cpd99002", delta_g=-100.0)])
    monkeypatch.setattr(ModelSEEDBiochem, "get", staticmethod(lambda *a, **k: fake))
    pkg = FullThermoPkg(_model())
    pkg.build_package({})
    potc = pkg.constraints["potc"]
    # deltaG from the database, kcal/mol -> kJ/mol; uncharged, so no membrane term
    assert math.isclose(potc["cpd99002_c0"].lb, -100.0 * 4.184, rel_tol=1e-9)
    # a compound missing from the database is left without a constraint
    assert "cpd99005_c0" not in potc
