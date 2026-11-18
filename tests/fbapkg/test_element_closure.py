# -*- coding: utf-8 -*-
"""ElementClosurePkg on toy models: a CO2 pump, the biomass loophole, exemptions."""
import cobra
import pytest

from modelseedpy.fbapkg.mspackagemanager import MSPackageManager
from modelseedpy.fbapkg.elementclosurepkg import formula_atoms


def _toy(pump=True, biomass=True):
    """S (C1) can be taken up at 1. Two reactions form a pump: r1 A -> B + S balances, r2 B -> A
    does not (creates one C), so together they make S from nothing. Biomass consumes a
    placeholder-formula polymer P (formula 'R') made from 2 S."""
    m = cobra.Model("toy")
    M = lambda i, f, q=0: cobra.Metabolite(i, formula=f, charge=q, compartment="c0")
    mets = {
        "S": M("S_c0", "CO2"),
        "A": M("A_c0", "C2H4O2"),
        "B": M("B_c0", "CH4"),
        "P": M("P_c0", "R"),
        "T": M("cpd11416_c0", ""),
    }
    # make B + S = A in atoms so r1 balances: B = C2H4O2 - CO2 = CH4 (hydrogen differs; give A
    # C2H4O2 and B CH4O0 -> pick A = C2H4O2, B = CH4 means r1 balances C and H but not O:
    # set B = C1H4 and S = CO2, A = C2H4O2 -> r1: C2H4O2 -> CH4 + CO2 : C2 H4 O2 -> C2 H4 O2 ok
    m.add_metabolites(list(mets.values()))

    def rxn(rid, st, lb=0, ub=1000):
        r = cobra.Reaction(rid, lower_bound=lb, upper_bound=ub)
        r.add_metabolites({mets[k]: v for k, v in st.items()})
        m.add_reactions([r])

    rxn("EX_S_e0", {"S": -1}, lb=-1, ub=1000)
    if pump:
        rxn("r1", {"A": -1, "B": 1, "S": 1})  # balanced
        rxn("r2", {"B": -1, "A": 1})  # creates CO2 worth of atoms
    if biomass:
        rxn("Psyn", {"S": -2, "P": 1})  # P's content = 2 CO2
        rxn("bio1", {"P": -1, "T": 1})
        rxn("SK_cpd11416_c0", {"T": -1})
    return m


def _close(m, **params):
    return (
        MSPackageManager.get_pkg_mgr(m)
        .getpkg("ElementClosurePkg")
        .build_package(params)
    )


def _max(m, rid):
    m.objective = rid
    v = m.slim_optimize()
    return 0.0 if v != v else v


def test_formula_parsing():
    assert formula_atoms("C4H5N2O3R2") is None
    assert formula_atoms("C4H5N2O3R2", strip_r=True) == {"C": 4, "H": 5, "N": 2, "O": 3}
    assert formula_atoms("C62H90CoN13O14PR", strip_r=True)["Co"] == 1
    assert formula_atoms("RbCl") == {"Rb": 1, "Cl": 1}  # Rb is not an R group
    assert formula_atoms("") is None


def test_pump_exports_carbon_without_closure_and_not_with_it():
    m = _toy(biomass=False)
    assert _max(m, "EX_S_e0") == pytest.approx(1000)  # carbon out of nothing
    m = _toy(biomass=False)
    _close(m)
    assert _max(m, "EX_S_e0") == pytest.approx(0, abs=1e-7)


def test_biomass_loophole_is_closed():
    # without closure the pump feeds biomass without limit
    assert _max(_toy(), "bio1") == pytest.approx(500.5)  # (1000 pump + 1 uptake) / 2
    # exchange-only closure (biomass not counted) still lets pump carbon into biomass
    m = _toy()
    _close(m, biomass_reactions=[])
    assert _max(m, "bio1") == pytest.approx(500.5)
    # with biomass counted (P resolved to 2 CO2 through Psyn): one S in supports 0.5 biomass
    m = _toy()
    info = _close(m)
    assert info["pseudo_compounds"]["P_c0"] == "synthesis Psyn"
    assert _max(m, "bio1") == pytest.approx(0.5)


def test_real_pathway_is_untouched():
    m = _toy(pump=False)
    _close(m)
    assert _max(m, "bio1") == pytest.approx(0.5)  # same as with no closure
    m2 = _toy(pump=False)
    assert _max(m2, "bio1") == pytest.approx(0.5)


def test_exempt_reaction_may_create():
    m = _toy(biomass=False)
    _close(m, exempt_reactions={"r2": "known error, pending curation"})
    assert _max(m, "EX_S_e0") == pytest.approx(1000)


def test_creation_report_and_curation_targets():
    m = _toy(biomass=False)
    pkg = MSPackageManager.get_pkg_mgr(m).getpkg("ElementClosurePkg")
    pkg.build_package({"elements": ("C", "O")})
    m.remove_cons_vars(
        [pkg.constraints["closure"][k] for k in list(pkg.constraints["closure"])]
    )
    m.objective = "EX_S_e0"
    sol = m.optimize()
    made = pkg.creation(sol.fluxes)
    assert made["C"] == pytest.approx(1000) and made["O"] == pytest.approx(2000)
    assert set(pkg.imbalanced_reactions()) == {"r2"}


def test_all_elements_and_charge_rows():
    m = _toy()
    m.metabolites.S_c0.charge = -1  # give the boundary a charge to close
    info = _close(m, elements="all", charge=True)
    assert set(info["rows"]) == {"C", "O", "charge"}


def test_closure_terms_match_built_rows():
    # closure_terms() returns exactly what build_package() turns into constraints
    m = _toy()
    pkg = MSPackageManager.get_pkg_mgr(m).getpkg("ElementClosurePkg")
    terms = pkg.closure_terms({})
    pkg2 = MSPackageManager.get_pkg_mgr(_toy()).getpkg("ElementClosurePkg")
    pkg2.build_package({})
    assert terms == pkg2.terms
    for key, row in terms.items():
        con = pkg2.constraints["closure"][key]
        lin = con.get_linear_coefficients(
            [
                v
                for rid in row
                for v in (
                    pkg2.model.reactions.get_by_id(rid).forward_variable,
                    pkg2.model.reactions.get_by_id(rid).reverse_variable,
                )
            ]
        )
        for rid, c in row.items():
            r = pkg2.model.reactions.get_by_id(rid)
            assert lin[r.forward_variable] == pytest.approx(c)
            assert lin[r.reverse_variable] == pytest.approx(-c)


def test_default_closes_every_element_present(caplog):
    from modelseedpy.fbapkg.elementclosurepkg import DEFAULT_ELEMENTS

    assert DEFAULT_ELEMENTS == "all"
    assert set(_close(_toy())["rows"]) == {"C", "O"}  # all the toy's boundary holds
    # an explicit element the boundary lacks gets no row, and a warning says so
    assert set(_close(_toy(), elements="C,H,O")["rows"]) == {"C", "O"}
    assert any("contains H" in r.message for r in caplog.records)


def test_parse_elements():
    from modelseedpy.fbapkg.elementclosurepkg import parse_elements, DEFAULT_ELEMENTS

    assert parse_elements(None) == DEFAULT_ELEMENTS
    assert parse_elements("all") == "all" and parse_elements(" ALL ") == "all"
    assert parse_elements(["all"]) == "all"
    assert parse_elements("C,H,O,N") == ("C", "H", "O", "N")
    assert parse_elements("C H  O;N") == ("C", "H", "O", "N")
    assert parse_elements(("Co", "Fe", "Co")) == ("Co", "Fe")  # duplicates dropped
    for bad in ("CO", "Xx", "c", "", ",", ["C", "Q"]):
        with pytest.raises(ValueError):
            parse_elements(bad)


@pytest.mark.parametrize("spec", ["C,O", "C O", ("C", "O"), "all", "ALL", ["all"]])
def test_element_specs_build_the_same_rows_on_the_toy(spec):
    # the toy's boundary and biomass hold only C and O, so "all" finds exactly those
    assert set(_close(_toy(), elements=spec)["rows"]) == {"C", "O"}


def _nitrogen_maker():
    """X (CH) can be taken up at 1; r makes Y (CHN) from X, creating one N; Y is exported."""
    m = cobra.Model("n")
    X = cobra.Metabolite("X_c0", formula="CH", compartment="c0")
    Y = cobra.Metabolite("Y_c0", formula="CHN", compartment="c0")
    for rid, st, lb, ub in (
        ("EX_X_e0", {X: -1}, -1, 1000),
        ("r", {X: -1, Y: 1}, 0, 1000),
        ("EX_Y_e0", {Y: -1}, 0, 1000),
    ):
        r = cobra.Reaction(rid, lower_bound=lb, upper_bound=ub)
        r.add_metabolites(st)
        m.add_reactions([r])
    return m


def test_carbon_hydrogen_oxygen_leave_nitrogen_open_the_default_closes_it():
    m = _nitrogen_maker()
    _close(m, elements="C,H,O")
    assert _max(m, "EX_Y_e0") == pytest.approx(1)  # N made from nothing passes
    for spec in ("C,H,O,N", "all", None):
        m = _nitrogen_maker()
        _close(m, elements=spec)
        assert _max(m, "EX_Y_e0") == pytest.approx(0, abs=1e-9)


def test_rebuild_with_fewer_elements_replaces_the_rows():
    m = _nitrogen_maker()
    pkg = MSPackageManager.get_pkg_mgr(m).getpkg("ElementClosurePkg")
    pkg.build_package({"elements": "all"})
    assert set(pkg.constraints["closure"]) == {"C", "H", "N"}
    assert _max(m, "EX_Y_e0") == pytest.approx(0, abs=1e-9)
    info = pkg.build_package({"elements": "C,H,O"})  # C, H, O (no O here)
    assert set(info["rows"]) == {"C", "H"}
    assert set(pkg.constraints["closure"]) == {"C", "H"}
    names = {c.name for c in m.constraints if c.name.endswith("_closure")}
    assert names == {"C_closure", "H_closure"}  # the N row is gone from the model
    assert _max(m, "EX_Y_e0") == pytest.approx(1)  # so N may be created again


def test_closure_terms_twice_on_one_model():
    m = _toy()
    pkg = MSPackageManager.get_pkg_mgr(m).getpkg("ElementClosurePkg")
    a = pkg.closure_terms({"elements": "all"})
    b = pkg.closure_terms({})
    assert set(a) == {"C", "O"} and set(b) == {"C", "O"}
    assert pkg.terms == {}  # closure_terms alone changes nothing reported
    pkg.build_package({"elements": "all"})
    pkg.closure_terms({"elements": ["C"]})
    assert set(pkg.terms) == {"C", "O"}  # still what is built


def test_failed_rebuild_keeps_the_rows():
    m = _nitrogen_maker()
    pkg = MSPackageManager.get_pkg_mgr(m).getpkg("ElementClosurePkg")
    pkg.build_package({"elements": "all"})
    with pytest.raises(ValueError):
        pkg.build_package({"elements": "all", "sense": "bogus"})
    assert set(pkg.constraints["closure"]) == {"C", "H", "N"}
    assert _max(m, "EX_Y_e0") == pytest.approx(0, abs=1e-9)


def test_rebuild_after_rows_left_with_block():
    m = _nitrogen_maker()
    pkg = MSPackageManager.get_pkg_mgr(m).getpkg("ElementClosurePkg")
    with m:
        pkg.build_package({"elements": "all"})
    pkg.build_package({"elements": "C,H,N"})  # used to raise LookupError
    assert {c.name for c in m.constraints if c.name.endswith("_closure")} == {
        "C_closure",
        "H_closure",
        "N_closure",
    }


def test_foreign_closure_named_constraint_survives():
    m = _toy()
    m.add_cons_vars(
        [
            m.problem.Constraint(
                m.reactions.EX_S_e0.flux_expression, lb=-10, name="uptake_closure"
            )
        ]
    )
    pkg = MSPackageManager.get_pkg_mgr(m).getpkg("ElementClosurePkg")
    pkg.build_package({})
    pkg.build_package({"elements": "C"})
    assert "uptake_closure" in m.constraints


def test_charge_only_closure():
    m = _toy()
    m.metabolites.S_c0.charge = -1
    info = _close(m, elements=[], charge=True)
    assert info["rows"] == ["charge"]
    with pytest.raises(ValueError):
        _close(_toy(), elements=[])  # nothing to build


def test_parse_elements_edge_cases():
    from modelseedpy.fbapkg.elementclosurepkg import parse_elements

    assert parse_elements([]) == ()
    assert parse_elements(["C, H", "O"]) == ("C", "H", "O")
    for bad in (5, 1.5, b"CHO", "all,C", ["all", "C"], "   "):
        with pytest.raises(ValueError):
            parse_elements(bad)


def test_all_skips_tokens_that_are_not_elements(caplog):
    m = _toy()
    X = cobra.Metabolite("X_c0", formula="CH4X", compartment="c0")
    r = cobra.Reaction("EX_X_e0", lower_bound=0, upper_bound=0)
    r.add_metabolites({X: -1})
    m.add_reactions([r])
    info = _close(m, elements="all")
    assert "X" not in info["rows"] and "H" in info["rows"]
    assert any("not elements" in rec.message for rec in caplog.records)


def _reverse(rxn):
    """Write a reaction the other way round, reversible: same chemistry, opposite signs."""
    st = {m: -2 * c for m, c in rxn.metabolites.items()}
    rxn.add_metabolites(st)  # adds -2c to each coefficient c, leaving -c
    rxn.bounds = (-1000, 1000)


def test_reversible_synthesis_written_backwards_still_resolves():
    m = _toy()
    _reverse(m.reactions.Psyn)  # P <=> 2 S
    assert _max(m, "bio1") == pytest.approx(500.5)  # the pump still feeds biomass
    info = _close(m)
    assert info["pseudo_compounds"]["P_c0"] == "synthesis Psyn"
    pkg = MSPackageManager.get_pkg_mgr(m).getpkg("ElementClosurePkg")
    assert pkg.content["P_c0"][0] == {"C": 2, "O": 4}  # signs handled: 2 CO2, not -2
    assert _max(m, "bio1") == pytest.approx(0.5)  # was 500.5: P zeroed as a carrier


def test_irreversible_reaction_written_backwards_does_not_produce():
    m = _toy()
    _reverse(m.reactions.Psyn)
    m.reactions.Psyn.lower_bound = 0  # P -> 2 S only: nothing makes P
    info = _close(m)
    assert info["pseudo_compounds"]["P_c0"] == "zero: carrier with no producer"


def _carrier_toy():
    """Biomass consumes a loaded carrier ACP and releases apo-ACP; the reversible loading
    reaction apo-ACP + D <=> ACP + E moves a CH2 moiety from D onto the carrier."""
    m = cobra.Model("carrier")
    M = lambda i, f: cobra.Metabolite(i, formula=f, charge=0, compartment="c0")
    apo, acp, d, e, t = (
        M("apoACP_c0", "R"),
        M("ACP_c0", "CH2R"),
        M("D_c0", "C3H6"),
        M("E_c0", "C2H4"),
        M("cpd11416_c0", ""),
    )
    for rid, st, lb in (
        ("EX_D_e0", {d: -1}, -1),
        ("EX_E_e0", {e: -1}, 0),
        ("ACPS", {apo: -1, d: -1, acp: 1, e: 1}, -1000),
        ("bio1", {acp: -1, apo: 1, t: 1}, 0),
        ("SK_cpd11416_c0", {t: -1}, 0),
    ):
        r = cobra.Reaction(rid, lower_bound=lb, upper_bound=1000)
        r.add_metabolites(st)
        m.add_reactions([r])
    return m


def test_reversible_carrier_loading_keeps_the_carrier_zero():
    # apo-ACP is made only by running the loading reaction backwards; it stays the zero
    # carrier, and ACP gets the moiety -- not both zeroed as unresolved
    m = _carrier_toy()
    pkg = MSPackageManager.get_pkg_mgr(m).getpkg("ElementClosurePkg")
    info = pkg.build_package({})
    assert info["pseudo_compounds"] == {
        "apoACP_c0": "zero: carrier with no producer",
        "ACP_c0": "synthesis ACPS",
    }
    assert pkg.content["ACP_c0"][0] == {"C": 1, "H": 2}


def test_exempting_a_boundary_reaction_changes_nothing(caplog):
    m = _toy(biomass=False)
    pkg = MSPackageManager.get_pkg_mgr(m).getpkg("ElementClosurePkg")
    pkg.build_package({})
    plain = pkg.terms
    assert plain["C"]["EX_S_e0"] == pytest.approx(1)
    pkg.build_package({"exempt_reactions": {"EX_S_e0": "x"}})
    assert pkg.terms == plain  # was doubled: {C: 2, O: 4}
    assert any("exempting it changes nothing" in r.message for r in caplog.records)
    # with biomass: the doubled uptake term let one S in support 1.0 biomass
    m = _toy()
    _close(m, exempt_reactions={"EX_S_e0": "x"})
    assert _max(m, "bio1") == pytest.approx(0.5)
    m = _toy()
    _close(m, exempt_reactions={"bio1": "y"})  # a doubled biomass term allowed none
    assert _max(m, "bio1") == pytest.approx(0.5)


def _bigg_style():
    """The toy with a biomass reaction that emits no cpd11416 token: 2 S -> Z, Z exported."""
    m = _toy(biomass=False)
    S, Z = m.metabolites.S_c0, cobra.Metabolite("Z_c0", formula="", compartment="c0")
    for rid, st in (("BIOMASS_toy", {S: -2, Z: 1}), ("EX_Z_e0", {Z: -1})):
        r = cobra.Reaction(rid, lower_bound=0, upper_bound=1000)
        r.add_metabolites(st)
        m.add_reactions([r])
    return m


def test_no_biomass_token_warns(caplog):
    m = _bigg_style()
    info = _close(m)
    assert info["biomass_reactions"] == 0
    assert any(
        "no reaction produces a biomass token" in r.message for r in caplog.records
    )
    assert _max(m, "BIOMASS_toy") == pytest.approx(500.5)  # what goes uncounted
    caplog.clear()
    m = _bigg_style()
    info = _close(m, biomass_reactions=["BIOMASS_toy"])
    assert info["biomass_reactions"] == 1
    assert not any("biomass token" in r.message for r in caplog.records)
    assert _max(m, "BIOMASS_toy") == pytest.approx(0.5)
    caplog.clear()
    _close(
        _toy(), biomass_reactions=[]
    )  # an explicit empty set is a choice: no warning
    assert not any("biomass token" in r.message for r in caplog.records)


def test_closure_terms_leaves_the_package_state_alone():
    m = _toy()
    pkg = MSPackageManager.get_pkg_mgr(m).getpkg("ElementClosurePkg")
    built = pkg.build_package({})
    params = dict(pkg.parameters)
    other = pkg.closure_terms({"biomass_reactions": [], "sense": "eq"})
    assert "bio1" not in other["C"]  # the call did compute without biomass
    assert pkg.summary() == built  # was: 0 biomass reactions, no pseudo-compounds
    assert pkg.parameters == params and pkg.parameters["sense"] == "le"
    assert _max(m, "bio1") == pytest.approx(0.5)


def test_failed_rebuild_keeps_what_is_reported():
    m = _toy()
    pkg = MSPackageManager.get_pkg_mgr(m).getpkg("ElementClosurePkg")
    built = pkg.build_package({})
    params = dict(pkg.parameters)
    with pytest.raises(ValueError):
        pkg.build_package({"biomass_reactions": [], "sense": "bogus"})
    with pytest.raises(ValueError):  # fails after the contents are recomputed
        pkg.build_package({"biomass_reactions": [], "elements": []})
    assert pkg.summary() == built
    assert pkg.parameters == params


def test_unformulated_compound_is_tagged_in_how():
    m = _toy()
    X = cobra.Metabolite("X_c0", formula="", compartment="c0")
    r = cobra.Reaction("EX_X_e0", lower_bound=0, upper_bound=0)
    r.add_metabolites({X: -1})
    m.add_reactions([r])
    pkg = MSPackageManager.get_pkg_mgr(m).getpkg("ElementClosurePkg")
    info = pkg.build_package({})
    assert pkg.how["X_c0"] == "zero: no formula"
    assert info["pseudo_compounds"]["X_c0"] == "zero: no formula"
    assert not hasattr(pkg, "unformulated")


def test_star_formula_is_no_formula(caplog):
    # KBase models write "*" for an unknown formula (340 of iSB1139's 1196 metabolites); it
    # is no formula, not a formula with no atoms
    assert formula_atoms("*") is None and formula_atoms("*", strip_r=True) is None
    m = _toy()
    X = cobra.Metabolite("X_c0", formula="*", compartment="c0")
    r = cobra.Reaction("EX_X_e0", lower_bound=-1, upper_bound=0)
    r.add_metabolites({X: -1})
    m.add_reactions([r])
    r = cobra.Reaction("rX", lower_bound=0, upper_bound=1000)
    r.add_metabolites({X: -1, m.metabolites.S_c0: 1})  # balance undefined
    m.add_reactions([r])
    pkg = MSPackageManager.get_pkg_mgr(m).getpkg("ElementClosurePkg")
    info = pkg.build_package({})
    assert pkg.how["X_c0"] == "zero: no formula"
    assert info["pseudo_compounds"]["X_c0"] == "zero: no formula"
    assert any(
        "have no formula" in rec.message and "X_c0" in rec.message
        for rec in caplog.records
    )
    assert "rX" not in pkg.imbalanced_reactions()
    assert set(pkg.imbalanced_reactions()) == {"r2"}
    for spec in ("all", "C,O"):  # an exempt reaction's balance must be defined
        with pytest.raises(ValueError):
            pkg.build_package({"elements": spec, "exempt_reactions": {"rX": "x"}})


def test_star_biomass_component_resolves_through_synthesis():
    m = _toy()
    m.metabolites.P_c0.formula = "*"  # was "R": same placeholder role
    info = _close(m)
    assert info["pseudo_compounds"]["P_c0"] == "synthesis Psyn"
    assert _max(m, "bio1") == pytest.approx(0.5)


def test_imbalanced_reactions_leaves_the_summary_alone():
    m = _toy()
    pkg = MSPackageManager.get_pkg_mgr(m).getpkg("ElementClosurePkg")
    built = pkg.build_package({})
    assert set(pkg.imbalanced_reactions()) == {"r2"}
    assert pkg.summary() == built


def test_synthesis_choice_does_not_depend_on_set_order():
    # two reactions make P with different contents; the first by id is taken, every run
    m = _toy()
    r = cobra.Reaction("Asyn", lower_bound=0, upper_bound=1000)
    r.add_metabolites({m.metabolites.S_c0: -3, m.metabolites.P_c0: 1})
    m.add_reactions([r])
    pkg = MSPackageManager.get_pkg_mgr(m).getpkg("ElementClosurePkg")
    info = pkg.build_package({})
    assert info["pseudo_compounds"]["P_c0"] == "synthesis Asyn"
    assert pkg.content["P_c0"][0] == {"C": 3, "O": 6}


def test_element_that_balances_everywhere(caplog):
    # biomass consumes a loaded carrier and releases it unloaded, as BiGG biomass does
    # accoa -> coa: N sits in biomass compounds, but no boundary or biomass reaction
    # exchanges any
    m = _toy()
    Qa = cobra.Metabolite("Qa_c0", formula="C2NO2", compartment="c0")
    Qb = cobra.Metabolite("Qb_c0", formula="CN", compartment="c0")
    r = cobra.Reaction("Qload", lower_bound=0, upper_bound=1000)
    r.add_metabolites({Qb: -1, m.metabolites.S_c0: -1, Qa: 1})
    m.add_reactions([r])
    m.reactions.bio1.add_metabolites({Qa: -1, Qb: 1})
    caplog.clear()
    assert set(_close(m)["rows"]) == {"C", "O"}  # "all": N skipped quietly
    assert not any("exchanges N" in rec.message for rec in caplog.records)
    # named: N still gets no row (it would read 0 <= 0), but a warning says why
    assert set(_close(m, elements="C,N")["rows"]) == {"C"}
    assert any("exchanges N" in rec.message for rec in caplog.records)


def test_modelseed_core_model_is_untouched():
    # his ModelSEED-id E. coli core fixture: a balanced model keeps its growth under the
    # default closure, and nothing is reported for curation
    from tests.test_data.mock_data import mock_model_ecoli_core

    m = mock_model_ecoli_core(True)
    free = m.slim_optimize()
    pkg = MSPackageManager.get_pkg_mgr(m).getpkg("ElementClosurePkg")
    info = pkg.build_package({"biomass_reactions": ["Biomass_Ecoli_core"]})
    assert set(info["rows"]) == {"C", "H", "N", "O", "P"}
    assert info["boundary_reactions"] == 20 and info["biomass_reactions"] == 1
    assert m.slim_optimize() == pytest.approx(free)
    assert pkg.imbalanced_reactions() == {}
    sol = m.optimize()
    assert all(v <= 1e-6 for v in pkg.creation(sol.fluxes).values())
