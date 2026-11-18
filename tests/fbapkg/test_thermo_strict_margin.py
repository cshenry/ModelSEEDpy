# -*- coding: utf-8 -*-
"""The loop-law margin in SimpleThermoPkg, and the units of FullThermoPkg's database errors.

Toy models only -- no database or solver licence beyond the default MILP solver is needed.
"""
import cobra
import pytest

from modelseedpy.fbapkg.mspackagemanager import MSPackageManager


def _model(with_loop=True, with_pump=False):
    """A -> B -> C plus exchanges; optionally an internal cycle B <-> C <-> D <-> B, or a
    two-reaction 'pump' P + Q -> X + R, R -> P + Q... that nets nothing -> X."""
    m = cobra.Model("toy")
    mets = {k: cobra.Metabolite(f"{k}_c0", compartment="c0") for k in "ABCDXPQR"}
    m.add_metabolites(list(mets.values()))

    def rxn(rid, stoich, lb=-1000, ub=1000):
        r = cobra.Reaction(rid, lower_bound=lb, upper_bound=ub)
        r.add_metabolites({mets[k]: v for k, v in stoich.items()})
        m.add_reactions([r])
        return r

    rxn("EX_A_e0", {"A": -1}, lb=-10, ub=0)  # A in
    rxn("EX_C_e0", {"C": -1}, lb=0, ub=1000)  # C out
    rxn("R1", {"A": -1, "B": 1})
    rxn("R2", {"B": -1, "C": 1})
    if with_loop:  # a cycle with no net conversion
        rxn("L1", {"C": -1, "D": 1})
        rxn("L2", {"D": -1, "B": 1})
    if with_pump:  # nothing -> X, through P/Q/R
        rxn("P1", {"P": -1, "Q": -1, "X": 1, "R": 1})
        rxn("P2", {"R": -1, "P": 1, "Q": 1})
        rxn("EX_X_e0", {"X": -1}, lb=0, ub=1000)
    return m


def _max(m, rid, **params):
    MSPackageManager.get_pkg_mgr(m).getpkg("SimpleThermoPkg").build_package(params)
    m.objective = rid
    return m.slim_optimize()


@pytest.mark.parametrize("coupling", ["revbin", "tmfa"])
def test_margin_blocks_internal_cycle(coupling):
    plain = _model()
    plain.objective = "L1"
    assert plain.slim_optimize() == pytest.approx(1000)  # the cycle runs freely
    # eps = 0 is the old behaviour: all-zero potentials satisfy every row
    assert _max(_model(), "L1", dg_margin=0.0, coupling=coupling) == pytest.approx(1000)
    # any eps > 0 forbids the cycle; L1 may only carry flux the network actually needs (none)
    assert _max(_model(), "L1", dg_margin=1.0, coupling=coupling) == pytest.approx(
        0, abs=1e-6
    )


@pytest.mark.parametrize("coupling", ["revbin", "tmfa"])
def test_margin_keeps_real_pathways(coupling):
    # A -> B -> C -> out is downhill all the way; the margin must not cost it any flux
    assert _max(
        _model(with_loop=False), "EX_C_e0", dg_margin=1.0, coupling=coupling
    ) == pytest.approx(10)


@pytest.mark.parametrize("coupling", ["revbin", "tmfa"])
def test_margin_cannot_stop_mass_creation(coupling):
    # P1 + P2 net: nothing -> X. It is not a cycle (X leaves), so no loop law excludes it.
    # Documented limitation: this needs mass balance, not thermodynamics.
    m = _model(with_loop=False, with_pump=True)
    assert _max(m, "EX_X_e0", dg_margin=1.0, coupling=coupling) == pytest.approx(1000)


def test_tmfa_leaves_idle_reactions_unconstrained():
    m = _model()
    pkg = MSPackageManager.get_pkg_mgr(m).getpkg("SimpleThermoPkg")
    pkg.build_package({"dg_margin": 1.0, "coupling": "tmfa"})
    # pin R1's dgp at exactly 0: under tmfa R1 can then carry no flux, but the model stays
    # feasible; under revbin the same pin is infeasible because every reaction needs |dgp|>=eps
    pkg.variables["dgp"]["R1"].lb = pkg.variables["dgp"]["R1"].ub = 0
    m.objective = "EX_C_e0"
    assert m.slim_optimize() == pytest.approx(0, abs=1e-6)
    r = _model()
    rp = MSPackageManager.get_pkg_mgr(r).getpkg("SimpleThermoPkg")
    rp.build_package({"dg_margin": 1.0, "coupling": "revbin"})
    rp.variables["dgp"]["R1"].lb = rp.variables["dgp"]["R1"].ub = 0
    r.objective = "EX_C_e0"
    r.slim_optimize()  # nan, not an exception
    assert r.solver.status == "infeasible"


def test_build_package_without_arguments():
    # MetaboFBAPkg calls build_package() with no parameters
    m = _model()
    MSPackageManager.get_pkg_mgr(m).getpkg("SimpleThermoPkg").build_package()
    m.objective = "L1"
    assert m.slim_optimize() == pytest.approx(0, abs=1e-6)


def test_build_package_with_only_a_margin():
    # MSCommunity's energy-cycles pilot calls build_package({"dg_margin": 1.0})
    m = _model()
    pkg = MSPackageManager.get_pkg_mgr(m).getpkg("SimpleThermoPkg")
    pkg.build_package({"dg_margin": 1.0})
    assert pkg.parameters["coupling"] == "revbin"
    m.objective = "L1"
    assert m.slim_optimize() == pytest.approx(0, abs=1e-6)
    m.objective = "EX_C_e0"
    assert m.slim_optimize() == pytest.approx(10)


def test_thermo_row_bounds():
    # revbin: eps <= dgp + (M + eps) revbin <= M, where it was 0 <= dgp + (M + 1) revbin <= M + 1
    m = _model(with_loop=False)
    pkg = MSPackageManager.get_pkg_mgr(m).getpkg("SimpleThermoPkg")
    pkg.build_package({"dg_margin": 2.0, "max_potential": 500})
    row = pkg.constraints["thermo"]["R1"]
    assert (row.lb, row.ub) == (2.0, 500)
    revbin = pkg.pkgmgr.getpkg("RevBinPkg").variables["revbin"]["R1"]
    assert row.get_linear_coefficients([revbin])[revbin] == 502.0
    assert sorted(pkg.constraints["thermo"]) == ["R1", "R2"]


def test_rebuild_with_another_coupling_replaces_the_rows():
    m = _model()
    pkg = MSPackageManager.get_pkg_mgr(m).getpkg("SimpleThermoPkg")
    pkg.build_package({"dg_margin": 1.0, "coupling": "revbin"})
    m.objective = "L1"
    assert m.slim_optimize() == pytest.approx(0, abs=1e-6)
    # eps = 0 under tmfa must behave as eps = 0, not keep revbin's eps = 1 rows
    pkg.build_package({"dg_margin": 0.0, "coupling": "tmfa"})
    assert not pkg.constraints["thermo"]
    assert m.slim_optimize() == pytest.approx(1000)
    pkg.build_package({"dg_margin": 1.0, "coupling": "tmfa"})
    assert m.slim_optimize() == pytest.approx(0, abs=1e-6)


@pytest.mark.parametrize(
    "params",
    [
        {"dg_margin": 10000.0},
        {"dg_margin": -1.0},
        {"coupling": "tmfa", "flux_big_m": 0},
        {"coupling": "tmfa", "flux_big_m": float("inf")},
    ],
)
def test_bad_parameters_are_rejected(params):
    pkg = MSPackageManager.get_pkg_mgr(_model()).getpkg("SimpleThermoPkg")
    with pytest.raises(ValueError):
        pkg.build_package(params)


def test_tmfa_rejects_an_infinite_bound():
    m = _model()
    m.reactions.R1.upper_bound = float("inf")
    with pytest.raises(ValueError, match="R1"):
        MSPackageManager.get_pkg_mgr(m).getpkg("SimpleThermoPkg").build_package(
            {"coupling": "tmfa"}
        )


@pytest.mark.parametrize("coupling", ["revbin", "tmfa"])
def test_empty_reaction_is_skipped(coupling):
    # a reaction with no metabolites has dgp = 0; under revbin it made the model infeasible
    m = _model(with_loop=False)
    m.add_reactions([cobra.Reaction("EMPTY", lower_bound=-1000, upper_bound=1000)])
    assert _max(m, "EX_C_e0", dg_margin=1.0, coupling=coupling) == pytest.approx(10)


def test_database_error_is_converted_to_kj(monkeypatch):
    from modelseedpy.fbapkg import fullthermopkg as ft

    class Cpd:
        def __init__(self, err):
            self.delta_g_error = err

    class Compounds(dict):
        def get_by_id(self, k):
            return self[k]

    class DB:
        compounds = Compounds(cpd1=Cpd(2.0), cpd2=Cpd(23901.43), cpd3=Cpd(None))

    monkeypatch.setattr(
        "modelseedpy.biochem.modelseed_biochem.ModelSEEDBiochem.get",
        staticmethod(lambda path=None: DB()),
    )
    pkg = ft.FullThermoPkg.__new__(ft.FullThermoPkg)
    pkg.parameters = {"modelseed_db_path": None}
    assert pkg.database_error("cpd1") == pytest.approx(2.0 * 4.184)  # kcal -> kJ
    assert pkg.database_error("cpd2") is None  # no-estimate marker
    assert pkg.database_error("cpd3") is None
    assert pkg.database_error("cpdX") is None


def _pinned_model(deltag_a=-100.0, deltag_b=-110.0):
    """glucose -> 2 pyruvate with both formation energies (kcal/mol) in notes['deltag'],
    so FullThermoPkg needs the database for nothing but the error bounds."""
    m = cobra.Model("pinned")
    a = cobra.Metabolite("cpd00027_c0", compartment="c0", formula="C6H12O6", charge=0)
    b = cobra.Metabolite("cpd00020_c0", compartment="c0", formula="C3H3O3", charge=-1)
    a.notes = {"deltag": deltag_a}
    b.notes = {"deltag": deltag_b}
    m.add_metabolites([a, b])
    r = cobra.Reaction("R1", lower_bound=-1000, upper_bound=1000)
    r.add_metabolites({a: -1, b: 2})
    ex = cobra.Reaction("EX_cpd00027_e0", lower_bound=-10, upper_bound=1000)
    ex.add_metabolites({a: -1})
    dm = cobra.Reaction("DM_cpd00020_c0", lower_bound=0, upper_bound=1000)
    dm.add_metabolites({b: -1})
    m.add_reactions([r, ex, dm])
    m.objective = "DM_cpd00020_c0"
    return m


def test_unreadable_database_falls_back_to_default_error(monkeypatch, caplog, tmp_path):
    # use_database_error=True is the default; a missing database must not raise
    # FileNotFoundError out of build_package when no energy comes from it
    from modelseedpy.biochem.modelseed_biochem import ModelSEEDBiochem

    monkeypatch.setattr(ModelSEEDBiochem, "default_biochemistry", None)
    m = _pinned_model()
    pkg = MSPackageManager.get_pkg_mgr(m).getpkg("FullThermoPkg")
    with caplog.at_level("WARNING", logger="modelseedpy.fbapkg.fullthermopkg"):
        pkg.build_package({"modelseed_db_path": str(tmp_path / "no_database")})
    warnings = [r for r in caplog.records if "ModelSEED database" in r.message]
    assert len(warnings) == 1  # one per build, not one per compound
    for kind in ("pdgerr", "ndgerr"):
        for var in pkg.variables[kind].values():
            assert var.ub == pytest.approx(5)  # default_max_error
    assert sorted(pkg.constraints["potc"]) == ["cpd00020_c0", "cpd00027_c0"]
    assert m.slim_optimize() == pytest.approx(20)


def test_rebuild_with_another_max_potential_matches_a_fresh_build():
    # glucose at -3000 kcal/mol = -12552 kJ/mol: free under max_potential 10000, pinned
    # under 100000. A rebuild kept the potentials' old bounds of +/-10000, so the pinned
    # compound could not reach its energy and the model was infeasible; a rebuild back
    # down kept the row that pinned it beyond the new bounds.
    m = _pinned_model(deltag_a=-3000.0, deltag_b=-1501.0)
    pkg = MSPackageManager.get_pkg_mgr(m).getpkg("FullThermoPkg")
    simple = pkg.pkgmgr.getpkg("SimpleThermoPkg")
    for max_potential, pinned in [
        (10000, ["cpd00020_c0"]),
        (100000, ["cpd00020_c0", "cpd00027_c0"]),
        (10000, ["cpd00020_c0"]),
    ]:
        pkg.build_package({"use_database_error": False, "max_potential": max_potential})
        assert m.slim_optimize() == pytest.approx(20)  # as a fresh build; nan if stale
        assert sorted(pkg.constraints["potc"]) == pinned
        assert sorted(c.name for c in m.constraints if c.name.endswith("_potc")) == [
            f"{mid}_potc" for mid in pinned
        ]
        for kind in ("potential", "dgp"):
            for var in simple.variables[kind].values():
                assert (var.lb, var.ub) == (-max_potential, max_potential)


def test_rebuild_resets_concentration_and_error_bounds():
    import math

    m = _pinned_model()
    pkg = MSPackageManager.get_pkg_mgr(m).getpkg("FullThermoPkg")
    pkg.build_package({"use_database_error": False})
    pkg.build_package(
        {
            "use_database_error": False,
            "custom_concentrations": {"cpd00027_c0": [0.05, 0.1]},
            "default_max_error": 20,
            "custom_deltaG_error": {"cpd00020": 2},
        }
    )
    glc = pkg.variables["logconc"]["cpd00027_c0"]
    assert (glc.lb, glc.ub) == pytest.approx((math.log(0.05), math.log(0.1)))
    pyr = pkg.variables["logconc"]["cpd00020_c0"]
    assert (pyr.lb, pyr.ub) == pytest.approx((math.log(1e-6), math.log(0.02)))
    for kind in ("pdgerr", "ndgerr"):
        assert pkg.variables[kind]["cpd00027_c0"].ub == 20
        assert pkg.variables[kind]["cpd00020_c0"].ub == 2
    # and back to the defaults
    pkg.build_package({"use_database_error": False})
    assert (glc.lb, glc.ub) == pytest.approx((math.log(1e-6), math.log(0.02)))
    for kind in ("pdgerr", "ndgerr"):
        assert pkg.variables[kind]["cpd00020_c0"].ub == 5


def test_database_error_widens_the_default_bound(monkeypatch):
    class Cpd:
        def __init__(self, err):
            self.delta_g_error = err

    class Compounds(dict):
        def get_by_id(self, k):
            return self[k]

    class DB:
        # kcal/mol: 3.0 -> 12.552 kJ/mol, wider than the default 5; 0.2 -> 0.837, narrower
        compounds = Compounds(cpd00027=Cpd(3.0), cpd00020=Cpd(0.2))

    monkeypatch.setattr(
        "modelseedpy.biochem.modelseed_biochem.ModelSEEDBiochem.get",
        staticmethod(lambda *a, **k: DB()),
    )
    m = _pinned_model()
    pkg = MSPackageManager.get_pkg_mgr(m).getpkg("FullThermoPkg")
    pkg.build_package({})
    for kind in ("pdgerr", "ndgerr"):
        assert pkg.variables[kind]["cpd00027_c0"].ub == pytest.approx(3.0 * 4.184)
        assert pkg.variables[kind]["cpd00020_c0"].ub == pytest.approx(5)
    pkg.build_package({"use_database_error": False})
    for kind in ("pdgerr", "ndgerr"):
        assert pkg.variables[kind]["cpd00027_c0"].ub == pytest.approx(5)


def test_unknown_marker_and_out_of_range_energies_leave_the_potential_free():
    # 10000000 is ModelSEED's "unknown"; -3000 kcal/mol = -12552 kJ/mol is beyond the
    # default max_potential of 10000 kJ/mol. Both used to be pinned, making the model
    # infeasible.
    for deltag in (10000000, -3000.0):
        m = _pinned_model(deltag_a=deltag, deltag_b=-110.0)
        pkg = MSPackageManager.get_pkg_mgr(m).getpkg("FullThermoPkg")
        pkg.build_package({"use_database_error": False})
        assert sorted(pkg.constraints["potc"]) == ["cpd00020_c0"]
        assert m.slim_optimize() == pytest.approx(20)


def test_fullthermo_defaults_to_tmfa_with_a_margin():
    m = _pinned_model()
    pkg = MSPackageManager.get_pkg_mgr(m).getpkg("FullThermoPkg")
    pkg.build_package({"use_database_error": False})
    simple = pkg.pkgmgr.getpkg("SimpleThermoPkg")
    assert simple.parameters["coupling"] == "tmfa"
    assert simple.parameters["dg_margin"] == 1.0
    assert simple.parameters["max_potential"] == 10000
    assert sorted(simple.variables["zf"]) == ["R1"]
    assert sorted(simple.variables["zr"]) == ["R1"]
    assert not simple.constraints["thermo"]


def test_fullthermo_tmfa_rejects_an_infinite_bound():
    m = _pinned_model()
    m.reactions.R1.lower_bound = -float("inf")
    pkg = MSPackageManager.get_pkg_mgr(m).getpkg("FullThermoPkg")
    with pytest.raises(ValueError, match="R1"):
        pkg.build_package({"use_database_error": False})
    # revbin, the old coupling, still builds
    pkg.build_package({"use_database_error": False, "coupling": "revbin"})
    assert m.slim_optimize() == pytest.approx(20)


def test_filter_limits_the_rows_to_the_filtered_reactions():
    # the revbin rows index RevBinPkg's binaries, which exist only for the filtered
    # reactions: building every reaction's row raised KeyError
    for coupling in ("revbin", "tmfa"):
        # the whole cycle B -> C -> D -> B is constrained: it cannot run
        m = _model()
        pkg = MSPackageManager.get_pkg_mgr(m).getpkg("SimpleThermoPkg")
        pkg.build_package({"filter": {"R2", "L1", "L2"}, "coupling": coupling})
        assert sorted(pkg.variables["dgp"]) == ["L1", "L2", "R2"]
        m.objective = "L1"
        assert m.slim_optimize() == pytest.approx(0, abs=1e-6)
        # R2 left out: nothing ties the cycle's dgp together, so it runs
        m = _model()
        pkg = MSPackageManager.get_pkg_mgr(m).getpkg("SimpleThermoPkg")
        pkg.build_package({"filter": {"L1", "L2"}, "coupling": coupling})
        assert sorted(pkg.variables["dgp"]) == ["L1", "L2"]
        m.objective = "L1"
        assert m.slim_optimize() == pytest.approx(1000)


def test_flux_big_m_caps_tmfa_flux():
    m = _model(with_loop=False)
    assert _max(m, "EX_C_e0", coupling="tmfa", flux_big_m=4) == pytest.approx(4)


def test_tolerance_warnings(caplog):
    m = _model()
    pkg = MSPackageManager.get_pkg_mgr(m).getpkg("SimpleThermoPkg")
    with caplog.at_level("WARNING", logger="modelseedpy.fbapkg.simplethermopkg"):
        pkg.build_package({"dg_margin": 0.0})
    assert any("exclude nothing" in r.message for r in caplog.records)
    caplog.clear()
    m.solver.configuration.tolerances.integrality = 1e-4
    with caplog.at_level("WARNING", logger="modelseedpy.fbapkg.simplethermopkg"):
        pkg.build_package({"dg_margin": 1.0})
    messages = [r.message for r in caplog.records]
    assert any("lets dgp slip" in msg for msg in messages)
    assert any("trickle" in msg for msg in messages)


def test_min_error_objective_has_unit_coefficients():
    m = _pinned_model()
    pkg = MSPackageManager.get_pkg_mgr(m).getpkg("FullThermoPkg")
    pkg.build_package({"use_database_error": False, "set_min_error_objective": True})
    errs = list(pkg.variables["pdgerr"].values()) + list(
        pkg.variables["ndgerr"].values()
    )
    coefs = m.objective.get_linear_coefficients(errs)
    assert m.objective.direction == "min"
    assert all(coef == 1 for coef in coefs.values())
    assert m.slim_optimize() == pytest.approx(0, abs=1e-9)


def test_compartment_potential_warning_uses_the_module_logger(caplog):
    m = _pinned_model()
    pkg = MSPackageManager.get_pkg_mgr(m).getpkg("FullThermoPkg")
    with caplog.at_level("WARNING", logger="modelseedpy.fbapkg.fullthermopkg"):
        pkg.build_package(
            {"use_database_error": False, "compartment_potential": {"c0": 400}}
        )
    records = [r for r in caplog.records if "compartment_potential" in r.message]
    assert records
    assert {r.name for r in records} == {"modelseedpy.fbapkg.fullthermopkg"}
