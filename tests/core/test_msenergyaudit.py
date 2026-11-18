# -*- coding: utf-8 -*-
"""Energy audit (modelseedpy.core.msenergyaudit) on toy single models.

Each toy model has ATP, ADP, Pi, PPi, H2O, H+, GTP and GDP in c0, a biomass reaction
that spends ATP, and exchanges in e0 that are closed for uptake. A test adds the
reactions that make (or do not make) energy from nothing.
"""
import pytest
from cobra import Metabolite, Model, Reaction

from modelseedpy.core import msenergyaudit as ea

ATP, ADP, PI, PPI, H2O, H = (
    "cpd00002_c0",
    "cpd00008_c0",
    "cpd00009_c0",
    "cpd00012_c0",
    "cpd00001_c0",
    "cpd00067_c0",
)
GTP, GDP = "cpd00038_c0", "cpd00031_c0"
X, Y, Z = "cpd90001_c0", "cpd90002_c0", "cpd90003_c0"
GLC, LAC = "cpd00027_c0", "cpd00159_c0"
CYTOSOL = ("cpd00002", "cpd00008", "cpd00009", "cpd00012", "cpd00001", "cpd00067")
CYTOSOL += ("cpd00038", "cpd00031", "cpd90001", "cpd90002", "cpd90003")
CYTOSOL += ("cpd00027", "cpd00159", "cpd11416")
FORMULAS = {
    "cpd00027": "C6H12O6",
    "cpd00159": "C3H5O3",
    "cpd00067": "H",
    "cpd00001": "H2O",
    "cpd00009": "HO4P",
    "cpd00011": "CO2",
    "cpd00007": "O2",
    "cpd90003": "",
}

# an ATP cycle: X -> Y, then Y back to X making ATP
PLANTED = (
    ("rxn90001_c0", {X: -1, Y: 1}),
    ("rxn90002_c0", {Y: -1, ADP: -1, PI: -1, H: -1, X: 1, ATP: 1, H2O: 1}),
)
# the same cycle charging GTP; nothing links GTP to ATP
GTP_LOOP = (
    ("rxn90001_c0", {X: -1, Y: 1}),
    ("rxn90004_c0", {Y: -1, GDP: -1, PI: -1, H: -1, X: 1, GTP: 1, H2O: 1}),
)
# makes ATP and a by-product Z from nothing; Z can only leave through its exchange
LEAK = (
    ("rxn90005_c0", {ADP: -1, PI: -1, H: -1, ATP: 1, H2O: 1, Z: 1}),
    ("rxn90006_c0", {Z: -1, "cpd90003_e0": 1}),
)
# ATP from extracellular protons; the cytosolic proton leaves through a demand
ION = (
    ("rxn90007_c0", {ADP: -1, PI: -1, "cpd00067_e0": -2, ATP: 1, H2O: 1, H: 1}),
    ("DM_cpd00067_c0", {H: -1}),
)
# 2 ATP per glucose, lactate out, protons through a reversible transport
GLYCOLYSIS = (
    ("rxn90008_c0", {"cpd00027_e0": -1, GLC: 1}),
    ("rxn90009_c0", {GLC: -1, ADP: -2, PI: -2, ATP: 2, LAC: 2, H2O: 2}),
    ("rxn90010_c0", {LAC: -1, "cpd00159_e0": 1}),
    ("rxn90011_c0", {H: -1, "cpd00067_e0": 1}, -1000, 1000),
)


def _model(*reactions):
    """The toy model with `reactions`: (id, {metabolite id: coefficient}[, lb, ub]);
    the default bounds are (0, 1000)."""
    model = Model("toy")
    mets = {}
    for cpd in CYTOSOL:
        mets[f"{cpd}_c0"] = Metabolite(f"{cpd}_c0", compartment="c0")
    for cpd, formula in FORMULAS.items():
        mets[f"{cpd}_e0"] = Metabolite(f"{cpd}_e0", formula=formula, compartment="e0")
    model.add_metabolites(list(mets.values()))
    rxns = []
    for cpd in FORMULAS:
        ex = Reaction(f"EX_{cpd}_e0", lower_bound=0, upper_bound=1000)
        ex.add_metabolites({mets[f"{cpd}_e0"]: -1})
        rxns.append(ex)
    bio = Reaction("bio1", lower_bound=0, upper_bound=1000)
    spend = {ATP: -10, H2O: -10, ADP: 10, PI: 10, H: 10, "cpd11416_c0": 1}
    bio.add_metabolites({mets[m]: n for m, n in spend.items()})
    outlet = Reaction("SK_cpd11416_c0", lower_bound=0, upper_bound=1000)
    outlet.add_metabolites({mets["cpd11416_c0"]: -1})
    rxns += [bio, outlet]
    for rid, st, *bounds in reactions:
        lb, ub = bounds or (0, 1000)
        rxn = Reaction(rid, lower_bound=lb, upper_bound=ub)
        rxn.add_metabolites({mets[m]: n for m, n in st.items()})
        rxns.append(rxn)
    model.add_reactions(rxns)
    model.objective = "bio1"
    return model


def _state(model):
    bounds = {r.id: r.bounds for r in model.reactions}
    rows = {c.name: (c.lb, c.ub) for c in model.constraints}
    return bounds, rows, str(model.objective.expression)


def test_a_planted_atp_cycle_is_detected():
    model = _model(*PLANTED)
    before = _state(model)
    out = ea.energy_from_nothing(model)
    assert out["atp_from_nothing"] == pytest.approx(1000)
    assert out["atp_by_compartment"] == {"c0": pytest.approx(1000)}
    assert out["n_atp_tests"] == 1
    assert out["growth_from_nothing"] > 0
    assert out["electrons_from_nothing"] == pytest.approx(0)
    assert "ntp_by_test" not in out
    assert _state(model) == before  # the model is left as it was found


def test_a_cycle_free_model_makes_nothing():
    out = ea.energy_from_nothing(_model(*GLYCOLYSIS))
    assert out["atp_from_nothing"] == pytest.approx(0)
    assert out["atp_by_compartment"] == {}
    assert out["growth_from_nothing"] == pytest.approx(0)
    assert out["electrons_from_nothing"] == pytest.approx(0)
    assert out["released"] == {}


def test_a_floor_is_released_else_the_test_is_infeasible():
    atpm = ("rxn00062_c0", {ATP: -1, H2O: -1, ADP: 1, PI: 1, H: 1}, 5, 1000)
    model = _model(*GLYCOLYSIS, atpm)
    kept = ea.energy_from_nothing(model, release_floors=False, electrons=False)
    assert kept["atp_from_nothing"] is None
    assert kept["released"] == {}
    released = ea.energy_from_nothing(model, electrons=False)
    assert released["atp_from_nothing"] == pytest.approx(0)
    assert released["released"] == {"rxn00062_c0": (5, 1000)}
    assert model.reactions.rxn00062_c0.bounds == (5, 1000)
    cycle = ea.find_energy_cycle(model, release_floors=False)
    assert cycle["status"] == "infeasible"
    assert ea.find_energy_cycle(model)["status"] == "no cycle"


def test_strict_closes_what_lax_lets_out():
    model = _model(*LEAK)
    lax = ea.energy_from_nothing(model, electrons=False)
    strict = ea.energy_from_nothing(model, closure="strict", electrons=False)
    assert lax["atp_from_nothing"] == pytest.approx(1000)
    assert strict["atp_from_nothing"] == pytest.approx(0)
    assert strict["closure"] == "strict"
    with pytest.raises(ValueError):
        ea.energy_from_nothing(model, closure="sealed")


def test_strict_keeps_the_biomass_outlet_unless_told_not_to():
    model = _model(*PLANTED)
    kept = ea.energy_from_nothing(model, closure="strict", electrons=False)
    literal = ea.energy_from_nothing(
        model, closure="strict", biomass_outlet=False, electrons=False
    )
    assert kept["growth_from_nothing"] > 0
    assert literal["growth_from_nothing"] == pytest.approx(0)


def test_the_ntp_pins_catch_a_gtp_loop_the_atp_test_misses():
    model = _model(*GTP_LOOP)
    atp_only = ea.energy_from_nothing(model, electrons=False)
    ntp = ea.energy_from_nothing(model, pins="ntp", electrons=False)
    assert atp_only["atp_from_nothing"] == pytest.approx(0)
    assert ntp["atp_from_nothing"] == pytest.approx(1000)
    assert ntp["ntp_by_test"] == {"cpd00038_c0": pytest.approx(1000)}
    assert ntp["atp_by_compartment"] == {}
    assert ntp["n_atp_tests"] == 1
    tests = [r.id for r in ea.add_hydrolysis_tests(model.copy(), pins="ntp").values()]
    assert tests == ["ATPtest_c0", "NTPtest_cpd00038_c0", "NTPtest_cpd00012_c0"]


def test_a_boundary_ion_arm_reveals_a_proton_route_the_sealed_test_misses():
    model = _model(*ION)
    out = ea.energy_from_nothing(model, boundary_ions=True, electrons=False)
    assert out["atp_from_nothing"] == pytest.approx(0)
    arm = out["boundary_ions"]["H+"]
    assert arm["open"] == ["cpd00067"]
    assert arm["atp"] == pytest.approx(500)  # two protons per ATP
    assert arm["boundary"]["EX_cpd00067_e0"] == pytest.approx(-1000)
    assert out["boundary_ions"]["H+,Pi"]["atp"] == pytest.approx(500)
    assert out["atp_from_boundary_ions"] == pytest.approx(500)
    clean = ea.energy_from_nothing(
        _model(*GLYCOLYSIS), boundary_ions=True, electrons=False
    )
    assert clean["atp_from_boundary_ions"] == pytest.approx(0)


def test_the_medium_arm_opens_the_inorganic_uptakes():
    model = _model(*ION)
    for cpd in ("cpd00027", "cpd00067", "cpd00009", "cpd00011", "cpd00007", "cpd90003"):
        model.reactions.get_by_id(f"EX_{cpd}_e0").lower_bound = -10
    ions, unknown = ea.medium_inorganic_uptakes(model)
    assert ions == ["cpd00009", "cpd00011", "cpd00067"]
    assert unknown == ["cpd90003"]
    ions, unknown = ea.medium_inorganic_uptakes(model, formulas={"cpd90003": "Fe"})
    assert "cpd90003" in ions and unknown == []
    out = ea.energy_from_nothing(model, boundary_ions="medium", electrons=False)
    assert out["boundary_ions"]["ions"]["open"] == [
        "cpd00067",
        "cpd00009",
        "cpd00011",
    ]
    assert out["ions_without_formula"] == ["cpd90003"]


def test_net_atp_yield_subtracts_what_the_model_makes_without_the_substrate():
    clean = ea.net_atp_yield(_model(*GLYCOLYSIS), "cpd00027", acceptor=None)
    assert clean["gross"] == pytest.approx(2)
    assert clean["substrate_closed"] == pytest.approx(0)
    assert clean["net"] == pytest.approx(2)
    assert clean["substrate_uptake"] == pytest.approx(1)
    capped = [(rid, st, 0, 5) for rid, st in PLANTED]
    leaky = ea.net_atp_yield(_model(*GLYCOLYSIS, *capped), "cpd00027", acceptor=None)
    assert leaky["atp_without"] == pytest.approx(5)
    assert leaky["gross"] == pytest.approx(7)
    assert leaky["net"] == pytest.approx(2)
    with pytest.raises(ValueError):
        ea.net_atp_yield(_model(*GLYCOLYSIS), "cpd99999")


def test_lifted_rows_uncover_a_cycle_a_row_hides():
    model = _model(*PLANTED)
    rxn = model.reactions.rxn90001_c0
    row = model.problem.Constraint(rxn.flux_expression, ub=0, name="rxn90001_c0_cap")
    model.add_cons_vars(row)
    hidden = ea.energy_from_nothing(model, electrons=False)
    assert hidden["atp_from_nothing"] == pytest.approx(0)
    assert hidden["rows_lifted"] == []
    by_name = lambda c: c.name.startswith("rxn90001")  # noqa: E731
    for rows in ("_cap", ["rxn90001_c0_cap"], by_name):
        out = ea.energy_from_nothing(model, lift_rows=rows, electrons=False)
        assert out["atp_from_nothing"] == pytest.approx(1000)
        assert out["rows_lifted"] == ["rxn90001_c0_cap"]
        assert model.constraints["rxn90001_c0_cap"].ub == 0  # back after the test
    with pytest.raises(ValueError):
        ea.energy_from_nothing(model, lift_rows=["no_such_row"])


def test_find_energy_cycle_names_the_cycle_and_its_uphill_step():
    thermo = {
        "rxn90002": {"dg": 30.0, "err": 1.0, "source": "test", "reversibility": "="}
    }
    cycle = ea.find_energy_cycle(_model(*PLANTED), thermo=thermo)
    assert cycle["status"] == "cycle"
    rows = {r["reaction"]: r for r in cycle["reactions"]}
    assert set(rows) == {"rxn90001_c0", "rxn90002_c0"}
    assert rows["rxn90002_c0"]["flux"] == pytest.approx(1)
    assert rows["rxn90002_c0"]["msid"] == "rxn90002"
    assert rows["rxn90002_c0"]["infeasible"] is True
    assert rows["rxn90001_c0"]["dg0"] is None
    assert cycle["fluxes"]["ATPtest_c0"] == pytest.approx(1)
    one = ea.find_energy_cycle(_model(*PLANTED), compartment="c0", flux=2.0)
    assert one["fluxes"]["rxn90001_c0"] == pytest.approx(2)
    assert ea.find_energy_cycle(_model(*GLYCOLYSIS))["status"] == "no cycle"


def test_conformal_cycle_finds_the_cycle_inside_a_flux():
    model = _model(*PLANTED, *GLYCOLYSIS)
    looped = {"rxn90001_c0": 3.0, "rxn90002_c0": 3.0, "rxn90009_c0": 1.0}
    assert sorted(ea.conformal_cycle(model, looped, lp="highs")) == [
        "rxn90001_c0",
        "rxn90002_c0",
    ]
    clean = {"rxn90008_c0": 1.0, "rxn90009_c0": 1.0, "rxn90010_c0": 2.0}
    assert ea.conformal_cycle(model, clean, lp="highs") == []
    gtp = _model(*GTP_LOOP)
    loop = {"rxn90001_c0": 1.0, "rxn90004_c0": 1.0}
    assert ea.conformal_cycle(gtp, loop, lp="highs") == []
    assert len(ea.conformal_cycle(gtp, loop, lp="highs", pins="ntp")) == 2


def test_electrons_from_nothing_reports_a_reduced_product_made_from_co2():
    fix = ("rxn90012_c0", {"cpd00011_e0": -3, "cpd00001_e0": -3, "cpd00159_e0": 1})
    out = ea.electrons_from_nothing(_model(fix + (0, 2)))
    assert out["electrons_from_nothing"] == pytest.approx(24)
    assert out["electron_carriers"] == {"cpd00159": pytest.approx(2)}


def test_hydrolysis_sites_and_the_compartment_filter():
    model = _model()
    sites = ea.hydrolysis_sites(model, "ntp")
    assert [(tri, comp) for tri, comp, _ in sites] == [
        ("cpd00002", "c0"),
        ("cpd00038", "c0"),
        ("cpd00012", "c0"),
    ]
    assert sites[0][2] == {ATP: -1, H2O: -1, ADP: 1, PI: 1, H: 1}
    assert ea.hydrolysis_sites(model, compartments=[]) == []
    only_atp = ea.hydrolysis_sites(model, "ntp", lambda tri, c: tri == "cpd00002")
    assert len(only_atp) == 1
    with pytest.raises(ValueError):
        ea.resolve_pins("gtp")


def test_close_uptakes_follows_the_direction_of_each_boundary_reaction():
    model = _model(("SK_cpd90002_c0", {Y: 1}, -1000, 1000))
    with model:
        ea.close_uptakes(model)
        assert model.reactions.SK_cpd90002_c0.bounds == (-1000, 0)
        assert model.reactions.EX_cpd00027_e0.bounds == (0, 1000)
    with model:
        ea.close_uptakes(model, open_cpds=("cpd00027",), strict=True)
        assert model.reactions.EX_cpd00027_e0.bounds == (-1000, 1000)
        assert model.reactions.EX_cpd00159_e0.bounds == (0, 0)
        assert model.reactions.SK_cpd11416_c0.bounds == (0, 1000)
    assert model.reactions.SK_cpd90002_c0.bounds == (-1000, 1000)


def test_a_model_without_the_atp_metabolites_warns_rather_than_reads_clean(caplog):
    model = _model(*PLANTED)
    model.remove_metabolites([model.metabolites.get_by_id(PI)])
    with caplog.at_level("WARNING", logger="modelseedpy.core.msenergyaudit"):
        out = ea.energy_from_nothing(model, electrons=False)
    assert out["n_atp_tests"] == 0
    assert "no cytosol holds" in caplog.text
