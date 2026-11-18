# -*- coding: utf-8 -*-
"""Energy audit of a metabolic model: what it makes from nothing.

A model with an energy-generating cycle makes ATP, or grows, with every uptake closed: a
set of reactions that runs in a loop and charges ATP (or another nucleotide) on the way
round. The functions here test for such cycles, name one, look for one inside a flux
distribution, and give the ATP yield of a substrate net of what the model makes without
it.

    energy_from_nothing     ATP, growth and electrons made with every uptake closed
    electrons_from_nothing  electrons exported in reduced products, only CO2, H2O, H+ in
    net_atp_yield           ATP per substrate, net of the ATP made without the substrate
    find_energy_cycle       the smallest-flux cycle that makes a given ATP flux
    conformal_cycle         the cycle inside a given flux distribution, if any (one LP)

Namespace. Metabolites are matched by ModelSEED compound id: cpd00002_c0 is ATP in c0.
ATP (and, with pins, other nucleotide) hydrolysis is tested in every cytosol -- a
compartment named c, c0, c1, ... -- that holds all of the hydrolysis' metabolites;
`compartments` narrows that. The extracellular compartment is `extracellular` ("e0" by
default).

Units. Fluxes are in mmol/gDW/h: ATP made is the flux of the ATP hydrolysis test
reactions (mmol ATP/gDW/h), growth the flux of the biomass reaction (1/h for a biomass
normalised to 1 g), electrons mmol e-/gDW/h. Yields are mmol ATP per mmol substrate. dG
values are in kcal/mol (the ModelSEED database's units), concentrations in mol/L. A
result of None means the LP had no optimal solution (it was infeasible), which is not
the same as 0.

Sealing (`closure`):
    "lax"     every boundary reaction (exchange, sink, demand) may only remove matter:
              nothing comes in, anything may leave. The default.
    "strict"  every boundary reaction is closed both ways, except, with
              biomass_outlet=True, the outlets of the biomass pseudo-metabolite
              (cpd11416), so that growth can still be measured. With
              biomass_outlet=False strict is literal, and growth from nothing is 0 by
              construction.
    The two differ only where reactions make matter from nothing, which "lax" lets out
    and "strict" does not. "Remove matter" follows each boundary reaction's own
    direction: the direction in which its metabolite is consumed.

Floors (`release_floors`). A forced flux -- a positive lower bound such as an ATP
maintenance floor, or a measured rate fixed as an equality -- cannot run on nothing, so
with it in place the sealed LP is infeasible (None) rather than 0, and the test says
nothing about cycles. True (the default) first lets every non-boundary reaction stop: a
lower bound above 0 goes to 0, an upper bound below 0 goes to 0 (release_forced_fluxes);
the report lists what was released. False keeps the bounds as they are.

Lifted rows (`lift_rows`). Extra constraint rows can hold every flux at 0 when nothing
comes in -- a row that caps a flux at a multiple of growth, say -- and so hide a cycle
that still runs whenever the model grows. lift_rows names rows to lift (bounds to
+-1e30) for the test only: None (the default) lifts nothing; a string lifts every row
whose name ends with it; an iterable lifts the rows of those names; a callable lifts
each row it returns True for. The bounds come back afterwards (`with model:` does not
track row bounds, so lifted_rows restores them).

Pins (`pins`). None or "atp" tests ATP hydrolysis only (ATP + H2O -> ADP + Pi + H+).
"ntp" also tests GTP, CTP and UTP hydrolysis and pyrophosphate hydrolysis (PPi + H2O ->
2 Pi + H+): a cycle that charges GTP and hands it straight to biomass makes no ATP and
is invisible to the ATP test alone. A list of (triphosphate, diphosphate-or-None)
compound ids gives the pins directly.

Boundary ions. The sealed tests close every uptake, so they cannot see a route that
draws free energy from a boundary ion: protons taken in and sent out again, or phosphate
and protons taken in and pyrophosphate sent out. energy_from_nothing(boundary_ions=True)
adds arms that reopen H+ and H+ with phosphate, and net_atp_yield gives a substrate's
yield net of what the same test makes without it.

Every test runs inside `with model:` and leaves the model as it found it.
"""
import glob
import json
import logging
import os
import re
from contextlib import contextmanager
from math import isnan
from math import log as ln

from cobra import Reaction
from optlang.symbolics import Zero

logger = logging.getLogger(__name__)

RT = 0.0019872 * 298.15  # kcal/mol at 25 C, the units of the ModelSEED dG values

# phosphoanhydride hydrolysis pins: (triphosphate, diphosphate); diphosphate None is
# pyrophosphate (PPi + H2O -> 2 Pi + H+); every other pin is NTP + H2O -> NDP + Pi + H+
ATP, ADP, PI, PPI = "cpd00002", "cpd00008", "cpd00009", "cpd00012"
H2O, PROTON = "cpd00001", "cpd00067"
ATP_PINS = ((ATP, ADP),)
NTP_PINS = (
    (ATP, ADP),
    ("cpd00038", "cpd00031"),  # GTP/GDP
    ("cpd00052", "cpd00096"),  # CTP/CDP
    ("cpd00062", "cpd00014"),  # UTP/UDP
    (PPI, None),  # pyrophosphate
)
TEST_PREFIXES = ("ATPtest_", "NTPtest_")
BIOMASS_CPD = "cpd11416"

# electrons each reduced product carries, relative to CO2, H2O and H+:
# H2, methane, formate, ethanol, L-lactate, D-lactate, succinate
REDUCED_PRODUCTS = {
    "cpd11640": 2,
    "cpd01024": 8,
    "cpd00047": 2,
    "cpd00363": 12,
    "cpd00159": 12,
    "cpd00221": 12,
    "cpd00036": 14,
}
ELECTRON_TEST_INPUTS = ("cpd00011", "cpd00001", "cpd00067")  # CO2, H2O, H+

# the boundary-ion arms of energy_from_nothing; the yield test's background uptakes
BOUNDARY_ION_ARMS = (("H+", (PROTON,)), ("H+,Pi", (PROTON, PI)))
YIELD_OPEN = (H2O, PROTON, PI, "cpd00011")  # H2O, H+, Pi, CO2
# left out of the "medium" ion arm: electron acceptors (a donor-free test cannot use
# them, and they are not ions in the sense meant here) and inorganic electron donors
# (H2 + CO2 is a real energy source for methanogens and acetogens)
ELECTRON_ACCEPTORS = {
    "cpd00007",
    "cpd00209",
    "cpd00075",
    "cpd00048",
    "cpd00106",
    "cpd00659",
    "cpd10516",
    "cpd00268",
}
INORGANIC_DONORS = {"cpd11640", "cpd00239", "cpd10515"}  # H2, H2S, Fe2+
INORGANIC_CARBON = {"cpd00011", "cpd00242"}  # CO2, HCO3-

# the thermodynamic gate of find_energy_cycle
NOT_IN_CONCENTRATION_TERM = {H2O, PROTON}  # fixed by the pH of dG'0
THERMO_SOURCES = ("eQuilibrator", "dGPredictor", "Group contribution")

_CYTOSOL = re.compile(r"^c\d*$")
_MSID = re.compile(r"^(rxn\d{5})")


# ---------------------------------------------------------------- pins and tests
def resolve_pins(pins=None, pin_atp=True):
    """The pins as a tuple of (triphosphate, diphosphate-or-None) compound ids.

    pins: None (ATP_PINS, or no pins with pin_atp=False), "atp", "ntp" (NTP_PINS), or an
    iterable of (triphosphate, diphosphate-or-None) pairs."""
    if pins is None:
        return ATP_PINS if pin_atp else ()
    if isinstance(pins, str):
        if pins.lower() == "ntp":
            return NTP_PINS
        if pins.lower() == "atp":
            return ATP_PINS
        raise ValueError(
            f"pins must be None, 'atp', 'ntp' or a list of pairs, not {pins!r}"
        )
    return tuple((tri, di) for tri, di in pins)


def hydrolysis_stoichiometry(tri, di):
    """{compound: coefficient} of tri + H2O -> di + Pi + H+, or with di None of
    PPi + H2O -> 2 Pi + H+."""
    if di is None:
        return {tri: -1, H2O: -1, PI: 2, PROTON: 1}
    return {tri: -1, H2O: -1, di: 1, PI: 1, PROTON: 1}


def _cpd(met):
    return met.id.split("_")[0]


def _selected(compartments, tri, comp):
    if compartments is None:
        return True
    if callable(compartments):
        return bool(compartments(tri, comp))
    return comp in compartments


def hydrolysis_sites(model, pins=ATP_PINS, compartments=None):
    """[(triphosphate, compartment, {metabolite id: coefficient})]: every cytosol (c,
    c0, c1, ...) that holds all the metabolites of a pin's hydrolysis, in pin order,
    then model order.

    pins as in resolve_pins. compartments: None (every such cytosol), an iterable of
    compartment ids, or a callable (triphosphate, compartment) -> bool."""
    mets = {m.id for m in model.metabolites}
    out = []
    for tri, di in resolve_pins(pins):
        st = hydrolysis_stoichiometry(tri, di)
        for met in model.metabolites:
            comp = met.compartment or ""
            if _cpd(met) != tri or not _CYTOSOL.match(comp):
                continue
            if not _selected(compartments, tri, comp):
                continue
            if all(f"{c}_{comp}" in mets for c in st):
                out.append((tri, comp, {f"{c}_{comp}": n for c, n in st.items()}))
    return out


def add_hydrolysis_tests(model, pins=None, compartments=None):
    """Add one hydrolysis test reaction per pin and site (hydrolysis_sites), each
    irreversible with an upper bound of 1000 mmol/gDW/h: ATP + H2O -> ADP + Pi + H+ with
    id ATPtest_<comp>, and, for the other pins, NTPtest_<compound>_<comp>. Call inside
    `with model:` so they go again. Returns {compartment: reaction} for ATP and
    {(compound, compartment): reaction} for the other pins.

    Maximising the sum of their fluxes with every uptake closed gives the ATP (and
    nucleotide) a model makes from nothing; a GTP loop that feeds biomass is invisible
    to the ATP tests alone, hence pins="ntp". With no site at all (metabolite ids not in
    the ModelSEED namespace, say) nothing is added and a warning is logged: every test
    built on these would then read 0 whatever the model makes."""
    mets = {met.id: met for met in model.metabolites}
    tests = {}
    for tri, comp, st in hydrolysis_sites(model, resolve_pins(pins), compartments):
        if tri == ATP:
            rid, label, key = f"ATPtest_{comp}", "ATP", comp
        else:
            rid, label, key = f"NTPtest_{tri}_{comp}", tri, (tri, comp)
        rxn = Reaction(
            rid,
            name=f"{label} hydrolysis test {comp}",
            lower_bound=0,
            upper_bound=1000,
        )
        rxn.add_metabolites({mets[mid]: n for mid, n in st.items()})
        tests[key] = rxn
    if not tests:
        logger.warning(
            "%s: no cytosol holds all the metabolites of a pinned hydrolysis "
            "(ModelSEED ids such as cpd00002_c0); the energy tests measure nothing",
            model.id,
        )
    model.add_reactions(list(tests.values()))
    return tests


def _summary_by_test(tests, tol):
    """{compartment: flux} of the ATP tests and {"<compound>_<comp>": flux} of the
    others, each above tol."""
    atp, ntp = {}, {}
    for key, rxn in tests.items():
        if rxn.flux <= tol:
            continue
        if isinstance(key, tuple):
            ntp[f"{key[0]}_{key[1]}"] = rxn.flux
        else:
            atp[key] = rxn.flux
    return atp, ntp


# ---------------------------------------------------------------- sealing
def _rows_to_lift(model, rows):
    if rows is None or rows is False:
        return []
    if isinstance(rows, str):
        return [c for c in model.constraints if c.name.endswith(rows)]
    if callable(rows):
        return [c for c in model.constraints if rows(c)]
    names = set(rows)
    missing = names - {c.name for c in model.constraints}
    if missing:
        raise ValueError(f"no constraint rows named {sorted(missing)}")
    return [c for c in model.constraints if c.name in names]


@contextmanager
def lifted_rows(model, rows=None):
    """Lift constraint rows for the duration of the block and restore them on exit.

    rows: None (the default: lift nothing), a string (every row whose name ends with
    it), an iterable of row names, or a callable taking an optlang constraint and
    returning a bool. A finite bound goes to +-1e30, not None (optlang's Gurobi
    interface refuses a free row). `with model:` does not track row bounds, so this
    restores them itself. Yields the lifted rows' names."""
    selected = _rows_to_lift(model, rows)
    saved = [(c, c.lb, c.ub) for c in selected]
    try:
        for c in selected:
            if c.ub is not None:
                c.ub = 1e30
            if c.lb is not None:
                c.lb = -1e30
        yield [c.name for c in selected]
    finally:
        for c, lb, ub in saved:  # only the bounds changed above (not None) go back
            if ub is not None:
                c.ub = ub
            if lb is not None:
                c.lb = lb


def release_forced_fluxes(model):
    """Let every non-boundary reaction stop: a positive lower bound (a maintenance-ATP
    floor, a measured rate fixed as an equality) goes to 0, and so does a negative upper
    bound.

    A test of what a model makes from nothing has to do this first: a forced flux cannot
    run with every uptake closed, so with it in place the sealed LP is infeasible rather
    than 0. Call inside `with model:`. Returns {reaction id: (old lower bound, old upper
    bound)} of the reactions released (mmol/gDW/h)."""
    released = {}
    for rxn in model.reactions:
        if rxn.boundary:
            continue
        lb, ub = rxn.bounds
        if lb > 0 or ub < 0:
            released[rxn.id] = (lb, ub)
            rxn.bounds = (min(lb, 0), max(ub, 0))
    return released


def close_uptakes(
    model,
    open_cpds=(),
    strict=False,
    biomass_outlet=True,
    extracellular="e0",
    biomass_cpd=BIOMASS_CPD,
):
    """Let every boundary reaction (exchange, sink, demand) only remove matter, except
    the exchanges of `open_cpds` in the `extracellular` compartment, which may also
    supply up to 1000 mmol/gDW/h. Call inside `with model:`.

    strict=True closes removal as well: every boundary reaction gets (0, 0), except
    `open_cpds` and, with biomass_outlet, the outlets of the biomass pseudo-metabolite
    (`biomass_cpd`), so that a growth test can still measure something. With
    biomass_outlet=False strict is literal and any growth from nothing is 0 by
    construction.

    "Remove" follows each reaction's own direction: forward for one written as
    consumption (met <=>, the cobra convention), reverse for one written as production
    (<=> met)."""
    for rxn in model.boundary:
        met = next(iter(rxn.metabolites))
        consumes = rxn.metabolites[met] < 0
        lb, ub = rxn.lower_bound, rxn.upper_bound
        if open_cpds and _cpd(met) in open_cpds and met.compartment == extracellular:
            rxn.bounds = (-1000, max(ub, 0)) if consumes else (min(lb, 0), 1000)
        elif strict and not (biomass_outlet and _cpd(met) == biomass_cpd):
            rxn.bounds = (0, 0)
        else:
            rxn.bounds = (0, max(ub, 0)) if consumes else (min(lb, 0), 0)


def seal(
    model,
    closure="lax",
    release_floors=True,
    open_cpds=(),
    biomass_outlet=True,
    extracellular="e0",
    biomass_cpd=BIOMASS_CPD,
):
    """release_forced_fluxes (if release_floors) and close_uptakes with the given
    closure: "lax", boundary reactions may only remove matter; "strict", every boundary
    reaction closed (but the biomass outlets, with biomass_outlet). Call inside `with
    model:`. Returns the released bounds {reaction id: (old lower bound, old upper
    bound)}."""
    if closure not in ("lax", "strict"):
        raise ValueError(f"closure must be 'lax' or 'strict', not {closure!r}")
    released = release_forced_fluxes(model) if release_floors else {}
    close_uptakes(
        model,
        open_cpds=open_cpds,
        strict=closure == "strict",
        biomass_outlet=biomass_outlet,
        extracellular=extracellular,
        biomass_cpd=biomass_cpd,
    )
    return released


def _value(model):
    v = model.slim_optimize(error_value=float("nan"))
    return None if isnan(v) else v


def _maximise_tests(model, tests):
    made = sum(r.flux_expression for r in tests.values())
    model.objective = model.problem.Objective(made, direction="max")
    return _value(model)


def medium_inorganic_uptakes(model, formulas=None, exclude=None, extracellular="e0"):
    """The `extracellular` compounds the model's current medium lets in that are
    inorganic -- no carbon in the formula, or CO2 / HCO3- -- other than electron
    acceptors and inorganic electron donors (ELECTRON_ACCEPTORS, INORGANIC_DONORS;
    `exclude` replaces both).

    formulas: {compound: formula}, e.g. from the ModelSEED database, for metabolites
    that carry none. Returns (compounds, compounds with no formula), each sorted."""
    if exclude is None:
        exclude = ELECTRON_ACCEPTORS | INORGANIC_DONORS
    exclude = set(exclude)
    formulas = formulas or {}
    ions, unknown = set(), set()
    for rxn in model.boundary:
        met = next(iter(rxn.metabolites))
        if met.compartment != extracellular:
            continue
        if rxn.metabolites[met] < 0:
            uptake = rxn.lower_bound < 0
        else:
            uptake = rxn.upper_bound > 0
        cpd = _cpd(met)
        if not uptake or cpd in exclude:
            continue
        formula = formulas.get(cpd) or met.formula or ""
        if not formula:
            unknown.add(cpd)
            continue
        if re.search(r"C(?![a-z])", formula) and cpd not in INORGANIC_CARBON:
            continue
        ions.add(cpd)
    return sorted(ions), sorted(unknown)


# ---------------------------------------------------------------- the tests
def _boundary_ion_arms(model, arms, release_floors, pins, tol, compartments, extra):
    """ATP made (summed tests) with every uptake closed except each arm's compounds
    (lax)."""
    out = {}
    for label, cpds in arms:
        with model:
            seal(model, "lax", release_floors, open_cpds=tuple(cpds), **extra)
            tests = add_hydrolysis_tests(model, pins, compartments)
            v = _maximise_tests(model, tests)
            rec = {"open": list(cpds), "atp": v}
            if v is not None and v > tol:
                rec["atp_by_compartment"], ntp = _summary_by_test(tests, tol)
                if ntp:
                    rec["ntp_by_test"] = ntp
                fluxes = {r.id: r.flux for r in model.boundary}
                rec["boundary"] = {k: v for k, v in fluxes.items() if abs(v) > tol}
        out[label] = rec
    return out


def energy_from_nothing(
    model,
    biomass="bio1",
    electrons=True,
    tol=1e-6,
    release_floors=True,
    closure="lax",
    biomass_outlet=True,
    lift_rows=None,
    boundary_ions=False,
    pins=None,
    formulas=None,
    compartments=None,
    extracellular="e0",
    biomass_cpd=BIOMASS_CPD,
):
    """What the model makes from nothing. All values in mmol/gDW/h (growth: the biomass
    reaction's flux); each is 0 for a model without energy-generating cycles, and None
    means the LP failed (infeasible).

    atp_from_nothing        max total ATP hydrolysis over the tests
                            (add_hydrolysis_tests) with every uptake closed; with
                            pins="ntp", ATP, GTP, CTP, UTP and PPi hydrolysis summed
    atp_by_compartment      {compartment: ATP test flux} at that optimum, above `tol`
    ntp_by_test             {"<compound>_<comp>": flux}, the other hydrolysis tests
                            (only when pins are not ATP alone)
    n_atp_tests             the number of ATP test reactions
    growth_from_nothing     max `biomass` flux with every uptake closed (skipped if
                            biomass is None or not in the model)
    electrons_from_nothing  max electrons exported in REDUCED_PRODUCTS with only CO2,
                            H2O and H+ coming in (electrons=True;
                            electrons_from_nothing)
    released                {reaction id: old bounds} of the forced fluxes released
    rows_lifted             names of the constraint rows lifted for the tests

    closure         "lax" (default) or "strict"; see the module docstring
    release_floors  True (default): release forced fluxes first (release_forced_fluxes),
                    else a floor such as ATP maintenance makes the test infeasible
                    (None), not 0
    biomass_outlet  with "strict", keep the biomass outlets able to remove biomass;
                    False makes growth_from_nothing 0 by construction (the electron test
                    keeps its own closure: CO2, H2O and H+ in, anything out)
    lift_rows       constraint rows to lift for the tests (lifted_rows); None lifts
                    nothing
    boundary_ions   False (default); True adds arms that reopen H+ ("H+") and H+ with
                    phosphate ("H+,Pi") and report, per arm, the ATP made, the boundary
                    fluxes at that optimum and, as atp_from_boundary_ions, the largest.
                    A clean model makes none: taking in Pi and H+ and sending out, say,
                    pyrophosphate is uphill. "medium" adds an arm "ions" with the
                    medium's inorganic uptakes too (medium_inorganic_uptakes, with
                    `formulas` for metabolites that carry none); a list of compounds
                    adds that arm with those compounds.
    pins            None (ATP tests only), "ntp", or a list of pairs (resolve_pins)
    compartments    where to test (hydrolysis_sites); None: every cytosol"""
    out = {"closure": closure}
    pins = resolve_pins(pins)
    extra = {"extracellular": extracellular, "biomass_cpd": biomass_cpd}
    arms = []
    if boundary_ions is not False and boundary_ions is not None:
        arms = list(BOUNDARY_ION_ARMS)
        ions = []
        if isinstance(boundary_ions, str):
            if boundary_ions != "medium":
                raise ValueError(
                    "boundary_ions must be True, 'medium' or a list of compounds, "
                    f"not {boundary_ions!r}"
                )
            ions, unknown = medium_inorganic_uptakes(
                model, formulas, extracellular=extracellular
            )
            out["ions_without_formula"] = unknown
        elif boundary_ions is not True:
            ions = list(boundary_ions)
        if ions:
            arms.append(("ions", tuple(dict.fromkeys((PROTON, PI) + tuple(ions)))))
    with lifted_rows(model, lift_rows) as lifted:
        out["rows_lifted"] = lifted
        with model:
            released = seal(
                model, closure, release_floors, biomass_outlet=biomass_outlet, **extra
            )
            out["released"] = released
            tests = add_hydrolysis_tests(model, pins, compartments)
            out["atp_from_nothing"] = _maximise_tests(model, tests)
            if out["atp_from_nothing"] is not None:
                atp, ntp = _summary_by_test(tests, tol)
            else:
                atp, ntp = {}, {}
            out["atp_by_compartment"] = atp
            if pins != ATP_PINS:
                out["ntp_by_test"] = ntp
            out["n_atp_tests"] = sum(1 for k in tests if not isinstance(k, tuple))
            if biomass is not None and biomass in model.reactions:
                model.objective = biomass
                out["growth_from_nothing"] = _value(model)
        if arms:
            by_arm = _boundary_ion_arms(
                model, arms, release_floors, pins, tol, compartments, extra
            )
            out["boundary_ions"] = by_arm
            vals = [a["atp"] for a in by_arm.values()]
            vals = [v for v in vals if v is not None]
            out["atp_from_boundary_ions"] = max(vals) if vals else None
        if electrons:
            e = electrons_from_nothing(
                model, release_floors=release_floors, extracellular=extracellular
            )
            e.pop("rows_lifted", None)
            out.update(e)
    return out


def electrons_from_nothing(
    model, release_floors=True, lift_rows=None, extracellular="e0"
):
    """Max electrons exported in REDUCED_PRODUCTS (mmol e-/gDW/h) with only CO2, H2O and
    H+ coming in (lax closure otherwise), and the reduced products carrying them
    ({compound: export flux, mmol/gDW/h}). A clean model makes none, since reducing CO2
    with electrons from water needs an energy source. Electrons made by reactions that
    do not conserve charge are a curation problem, not a cycle; this reports them,
    nothing here removes them. release_floors and lift_rows as in
    energy_from_nothing."""
    with lifted_rows(model, lift_rows) as lifted, model:
        seal(
            model,
            "lax",
            release_floors,
            open_cpds=ELECTRON_TEST_INPUTS,
            extracellular=extracellular,
        )
        coefs, exports = {}, {}
        for rxn in model.exchanges:
            met = next(iter(rxn.metabolites))
            if met.compartment == extracellular and _cpd(met) in REDUCED_PRODUCTS:
                # an exchange written as consumption exports with forward flux
                w = REDUCED_PRODUCTS[_cpd(met)] * -rxn.metabolites[met]
                coefs[rxn.forward_variable], coefs[rxn.reverse_variable] = w, -w
                exports[_cpd(met)] = rxn
        if not coefs:
            return {
                "electrons_from_nothing": 0.0,
                "electron_carriers": {},
                "rows_lifted": lifted,
            }
        model.objective = model.problem.Objective(Zero, direction="max")
        model.objective.set_linear_coefficients(coefs)
        v = _value(model)
        carriers = {}
        if v is not None:
            carriers = {c: r.flux for c, r in exports.items() if abs(r.flux) > 1e-9}
    return {
        "electrons_from_nothing": v,
        "electron_carriers": carriers,
        "rows_lifted": lifted,
    }


def net_atp_yield(
    model,
    substrate,
    acceptor="cpd00007",
    open_cpds=YIELD_OPEN,
    rate=1.0,
    release_floors=True,
    lift_rows=None,
    pins=None,
    compartments=None,
    extracellular="e0",
):
    """The ATP yield of `substrate` (a compound id) net of what the same test makes
    without it.

    The test: every uptake closed except `open_cpds` (default H2O, H+, Pi, CO2), the
    `acceptor` (a compound, a list, or None) and the substrate at up to `rate`
    (mmol/gDW/h); forced fluxes released (release_floors), `lift_rows` lifted, the ATP
    tests summed and maximised. gross is that maximum per mmol of the allowed substrate;
    substrate_closed the same test with the substrate shut, per the same mmol; net =
    gross - substrate_closed. A model that makes ATP from H+ and Pi alone (a boundary
    route the sealed test cannot see) counts it in the gross yield; the net yield does
    not. A cycle-free model can still be too efficient, which only the net yield shows
    against the biochemistry (about 24 per glucose aerobically, say).

    Returns {substrate, rate, open, rows_lifted, atp_with_substrate, atp_without (mmol
    ATP/gDW/h), substrate_uptake (mmol/gDW/h), gross, substrate_closed, net (mmol ATP
    per mmol substrate)}."""
    acc = (acceptor,) if isinstance(acceptor, str) else tuple(acceptor or ())
    opened = tuple(dict.fromkeys(tuple(open_cpds) + acc))
    sid = f"{substrate}_{extracellular}"
    exs = [r for r in model.boundary if any(m.id == sid for m in r.metabolites)]
    if not exs:
        raise ValueError(f"no boundary reaction for {sid}")

    def run(with_substrate):
        with model:
            seal(
                model,
                "lax",
                release_floors,
                open_cpds=opened,
                extracellular=extracellular,
            )
            met = model.metabolites.get_by_id(sid)
            for ex in exs:
                coef = ex.metabolites[met]
                lb, ub = ex.lower_bound, ex.upper_bound
                # uptake of up to `rate`, whichever way the reaction is written
                if with_substrate:
                    ex.bounds = (-rate, max(ub, 0)) if coef < 0 else (min(lb, 0), rate)
                else:
                    ex.bounds = (0, max(ub, 0)) if coef < 0 else (min(lb, 0), 0)
            tests = add_hydrolysis_tests(model, pins, compartments)
            v = _maximise_tests(model, tests)
            up = None
            if v is not None:
                up = sum(ex.flux * ex.metabolites[met] for ex in exs)
        return v, up

    with lifted_rows(model, lift_rows) as lifted:
        g, up = run(True)
        c, _ = run(False)
    out = {
        "substrate": substrate,
        "rate": rate,
        "open": list(opened),
        "rows_lifted": lifted,
        "atp_with_substrate": g,
        "atp_without": c,
        "substrate_uptake": up,
        "gross": None if g is None else g / rate,
        "substrate_closed": None if c is None else c / rate,
    }
    out["net"] = None if g is None or c is None else (g - c) / rate
    return out


# ---------------------------------------------------------------- the cycle
def msid(rxn):
    """The ModelSEED reaction id behind a model reaction id (rxn00571_c0 -> rxn00571),
    or None."""
    m = _MSID.match(rxn.id)
    return m.group(1) if m else None


def load_msdb_thermo(msdb_path):
    """{reaction id: {reversibility, dg, err, source, name}} from a ModelSEEDDatabase
    checkout (Biochemistry/reaction_*.json). dg/err are dG'0 and its standard error in
    kcal/mol from the first of THERMO_SOURCES with a value (None if none has one)."""
    pattern = os.path.join(msdb_path, "Biochemistry", "reaction_*.json")
    files = sorted(glob.glob(pattern))
    if not files:
        raise FileNotFoundError(f"no Biochemistry/reaction_*.json under {msdb_path}")
    db = {}
    for f in files:
        with open(f) as fh:
            reactions = json.load(fh)
        for r in reactions:
            entry = {
                "reversibility": r.get("reversibility"),
                "name": r.get("name"),
                "dg": None,
                "err": None,
                "source": None,
            }
            thermo = r.get("thermodynamics") or {}
            for src in THERMO_SOURCES:
                val = thermo.get(src) or []
                if len(val) < 2:
                    continue
                if not all(isinstance(x, (int, float)) for x in val[:2]):
                    continue
                if abs(val[0]) < 1e6 and abs(val[1]) < 1e6:
                    entry.update(dg=float(val[0]), err=float(val[1]), source=src)
                    break
            db[r["id"]] = entry
    return db


def direction_thermo(rxn, direction, entry, c_min=1e-6, c_max=0.02, n_sigma=2.0):
    """dG'0 and dG'min (kcal/mol) of `rxn` run forward (direction > 0) or in reverse,
    and whether thermodynamics rules that direction out. None where there is no dG'0 or
    the reaction crosses a membrane (its dG then depends on the membrane potential).

    A direction is ruled out only when no concentrations in [c_min, c_max] (mol/L)
    could make it run, that is when dG'min - n_sigma * err > 0, where

        dG'min = dG'0 + RT * (sum_products n ln c_min - sum_substrates n ln c_max)

    with water and protons left out of the sums. entry is a load_msdb_thermo value.
    """
    if not entry or entry.get("dg") is None or len(rxn.compartments) > 1:
        return None
    sign = 1 if direction > 0 else -1
    dg0 = sign * entry["dg"]
    conc = 0.0
    for met, coef in rxn.metabolites.items():
        if _cpd(met) in NOT_IN_CONCENTRATION_TERM:
            continue
        n = sign * coef  # > 0: a product in the running direction
        conc += n * ln(c_min) if n > 0 else n * ln(c_max)
    dg_min = dg0 + RT * conc
    return {
        "dg0": dg0,
        "dg_min": dg_min,
        "err": entry["err"],
        "source": entry["source"],
        "infeasible": dg_min - n_sigma * entry["err"] > 0,
    }


def _cycle_row(rxn, v, thermo, gapfilled, gate):
    base = msid(rxn)
    entry = thermo.get(base) if base else None
    rev = entry.get("reversibility") if entry else None
    row = {
        "reaction": rxn.id,
        "msid": base,
        "flux": v,
        "bounds": list(rxn.bounds),
        "db_reversibility": rev,
        "name": (entry or {}).get("name") or rxn.name,
        "against_db": bool((rev == ">" and v < 0) or (rev == "<" and v > 0)),
    }
    td = direction_thermo(rxn, v, entry, **gate)
    if td:
        row.update(
            dg0=td["dg0"],
            dg_min=td["dg_min"],
            dg_err=td["err"],
            dg_source=td["source"],
            infeasible=td["infeasible"],
        )
    else:
        row.update(dg0=None, dg_min=None, dg_err=None, dg_source=None, infeasible=False)
    row["gapfilled"] = bool(base and base in gapfilled)
    return row


def find_energy_cycle(
    model,
    flux=1.0,
    compartment=None,
    thermo=None,
    gapfilled=None,
    tol=1e-7,
    release_floors=True,
    lift_rows=None,
    pins=None,
    compartments=None,
    extracellular="e0",
    **gate,
):
    """The smallest-total-flux cycle that makes `flux` mmol ATP/gDW/h with every uptake
    closed (lax closure, forced fluxes released with release_floors, `lift_rows`
    lifted).

    compartment  make the ATP in this compartment's test; default the sum over all tests
    thermo       load_msdb_thermo() output: each reaction's database direction and dG
    gapfilled    a set of ModelSEED reaction ids gapfilled into the model
    pins         None (ATP tests) or "ntp" (the other hydrolysis tests count too)
    gate         c_min, c_max, n_sigma for direction_thermo

    Returns {status, reactions, fluxes, rows_lifted}. status is "cycle"; "no cycle" when
    the model cannot make the ATP; or "infeasible" when the sealed model cannot run at
    all (a forced flux kept with release_floors=False, say), which says nothing about
    cycles. reactions has one row per reaction in the cycle (the test reactions left
    out): reaction, msid, flux, bounds (during the test), db_reversibility, name,
    against_db (runs against the database direction), dg0, dg_min, dg_err, dg_source,
    infeasible (direction_thermo), gapfilled. fluxes is {reaction id: flux} of every
    reaction above tol, tests included."""
    gapfilled, thermo = set(gapfilled or ()), thermo or {}
    with lifted_rows(model, lift_rows) as lifted:
        out = _find_energy_cycle(
            model,
            flux,
            compartment,
            thermo,
            gapfilled,
            tol,
            release_floors,
            resolve_pins(pins),
            compartments,
            extracellular,
            gate,
        )
    out["rows_lifted"] = lifted
    return out


def _find_energy_cycle(
    model,
    flux,
    compartment,
    thermo,
    gapfilled,
    tol,
    release_floors,
    pins,
    compartments,
    extracellular,
    gate,
):
    with model:
        seal(model, "lax", release_floors, extracellular=extracellular)
        tests = add_hydrolysis_tests(model, pins, compartments)
        if compartment is not None:
            made = tests[compartment].flux_expression
        else:
            made = sum(r.flux_expression for r in tests.values())
        con = model.problem.Constraint(made, lb=flux, ub=flux, name="energy_cycle_atp")
        model.add_cons_vars(con)
        model.objective = model.problem.Objective(Zero, direction="min")
        model.objective.set_linear_coefficients(
            {
                v: 1
                for r in model.reactions
                for v in (r.forward_variable, r.reverse_variable)
            }
        )
        if _value(model) is None:
            con.lb, con.ub = 0, 0
            status = "no cycle" if _value(model) is not None else "infeasible"
            return {"status": status, "reactions": [], "fluxes": {}}
        fluxes = {r.id: r.flux for r in model.reactions if abs(r.flux) > tol}
        rows = []
        for rid, v in fluxes.items():
            if rid.startswith(TEST_PREFIXES):
                continue
            rxn = model.reactions.get_by_id(rid)
            rows.append(_cycle_row(rxn, v, thermo, gapfilled, gate))
    return {"status": "cycle", "reactions": rows, "fluxes": fluxes}


def conformal_cycle(
    model, fluxes, tol=1e-7, pin_atp=True, lp="auto", threads=None, pins=None
):
    """The internal reactions of a cycle inside a flux distribution, or [] if it holds
    none.

    A cycle here is a steady-state flux u through internal reactions only, each run the
    way `fluxes` ({reaction id: flux}) runs it (support and signs within the flux's
    own), plus, with pin_atp, any amount of ATP hydrolysis in each cytosol: exactly what
    makes `fluxes` violate the loop law with ATP hydrolysis pinned downhill (no
    potentials can make every step of u downhill). One LP over the active reactions; the
    support of its solution is returned. pins="ntp" allows hydrolysis of every pinned
    nucleotide and PPi as well, so a GTP loop that feeds biomass is a cycle here too.

    lp: "gurobi" (gurobipy), "highs" (scipy's HiGHS) or "auto" (gurobi when gurobipy
    imports, else highs); threads goes to the Gurobi environment (None: gurobi.env or
    Gurobi's default). Neither solver is a dependency of this module until this function
    is called."""
    import numpy as np
    import scipy.sparse as sp
    from scipy.optimize import linprog

    boundary = {r.id for r in model.boundary}
    active = [
        model.reactions.get_by_id(rid)
        for rid, v in fluxes.items()
        if abs(v) > tol and rid not in boundary and rid in model.reactions
    ]
    cols, signs = [], []
    for r in active:
        cols.append({m.id: c for m, c in r.metabolites.items()})
        signs.append(1.0 if fluxes[r.id] > 0 else -1.0)
    n_active = len(cols)
    for _, _, st in hydrolysis_sites(model, resolve_pins(pins, pin_atp)):
        cols.append(dict(st))
        signs.append(1.0)
    if not n_active:
        return []
    index = {}
    rows, cidx, vals = [], [], []
    for j, col in enumerate(cols):
        for mid, c in col.items():
            i = index.setdefault(mid, len(index))
            rows.append(i)
            cidx.append(j)
            vals.append(c * signs[j])
    A = sp.csr_matrix((vals, (rows, cidx)), shape=(len(index), len(cols)))
    # w_j = sign_j * u_j in [0, 1]; maximise the flux through the active reactions
    # only, so a pin alone (ATP hydrolysis with nothing making the ATP) is not a cycle
    c = np.concatenate([-np.ones(n_active), np.zeros(len(cols) - n_active)])
    if lp == "auto":
        try:
            import gurobipy  # noqa: F401

            lp = "gurobi"
        except ImportError:
            lp = "highs"
    if lp == "gurobi":
        import gurobipy as gp

        params = {"OutputFlag": 0}
        if threads:
            params["Threads"] = int(threads)
        env = gp.Env(params=params)
        g = gp.Model(env=env)
        w = g.addMVar(len(cols), lb=0, ub=1, obj=c)
        g.addMConstr(A, w, "=", np.zeros(len(index)))
        g.optimize()
        ok = g.Status == gp.GRB.OPTIMAL
        value = -g.ObjVal if g.SolCount else 0.0
        x = w.X.copy() if g.SolCount else None
        g.dispose()
        env.dispose()
    else:
        res = linprog(
            c,
            A_eq=A,
            b_eq=np.zeros(len(index)),
            bounds=[(0, 1)] * len(cols),
            method="highs",
        )
        ok = res.status == 0
        value = -res.fun if ok else 0.0
        x = res.x
    if not ok or value <= tol:
        return []
    return [active[j].id for j in range(n_active) if x[j] > tol]
