# -*- coding: utf-8 -*-
"""ElementClosurePkg -- the network may not create chemical elements.

For each element E one linear row, over the reactions that cross the system boundary:

    sum over boundary and biomass reactions r of  -imb_E(r) * v_r   <=  0

where imb_E(r) is the net number of E atoms reaction r produces per unit flux. An exchange
that exports a compound "destroys" its atoms (imb < 0), so the row reads: E leaving through
exchanges, sinks and demands, plus E retained in biomass, may not exceed E entering.

Why the boundary is enough. At steady state S v = 0, so for ANY assignment a of atom counts to
metabolites, a^T S v = 0: the net creation of E by internal reactions equals minus its net
creation by boundary and biomass reactions. Forbidding net creation at the boundary therefore
forbids it inside, whatever the internal mechanism -- including reactions whose own balance
cannot even be computed because a reactant carries an R group or a placeholder formula. One row
per element, no binaries.

What it catches and what it does not.
  - Mass-imbalanced reactions or combinations that create atoms -- e.g. two versions of one
    enzymatic step that differ by a CO2, which together emit CO2 from nothing. Thermodynamic
    (loop-law) constraints cannot catch these: such a pathway is not a cycle, and creating CO2
    "from nothing" looks downhill to every formation-energy model.
  - NOT charge-only imbalances that create electrons with no atoms (e.g. carrier pairs that
    differ in how many ferredoxins they reduce). Set charge=True to add a charge row; expect it
    to expose every charge-imbalanced reaction a model relies on.
  - It forbids net creation, not every imbalance: a reaction that creates an element may run if
    another destroys as much (the net is what reaches the boundary). imbalanced_reactions()
    lists the culprits so they can be curated.

Biomass. Biomass is a sink that keeps atoms. Its content is computed from its components; the
biomass token (cpd11416, which every biomass reaction emits and sinks remove) carries none, so
nothing is counted twice and member-level biomass sinks in a community are covered. Macromolecule
pseudo-compounds -- Protein, DNA, RNA, ACP -- have placeholder formulas (C4H5N2O3R2 for Protein),
so each is given the content of the reaction that synthesises it from formulated precursors (a
reversible reaction written the other way round counts). A carrier with no producer (apo-ACP,
which biomass releases as it consumes ACP) is zero, which makes the pair count only the moiety
actually incorporated.

Atom assignment (one, used everywhere): biomass token -> 0; formula without R -> its atoms;
biomass pseudo-compound -> content of its synthesis reaction; any other formula with R -> its
explicit atoms (R taken as the same unspecified moiety on both sides of a reaction); no formula
(empty, "null", "noformula", or the "*" KBase models carry) -> 0, tagged "zero: no formula" in
`how` (summary() lists it with the pseudo-compounds, and a warning names any that sit on the
boundary: their exchanges count no atoms, so what they bring in is closed as if it were nothing).

Parameters (build_package):
    elements          which elements get a row. Default "all": every element the boundary and
                      biomass compounds contain, metals included (about 20 rows; on 403 member
                      models it costs ~7 ms more to build than C, H, O and no measurable solve
                      time). Also accepted: a string of symbols ("C,H,O" or "C H O N"), or any
                      iterable of symbols.
                      Unknown symbols raise ValueError. See parse_elements.
    charge            also close charge. Default False.
    sense             "le" (default): no net creation, destruction allowed -- biomass may keep
                      atoms, and so may sinks. "eq": neither.
    exempt_reactions  {reaction id: reason} -- reactions whose own imbalance is allowed (e.g. a
                      known stoichiometric error awaiting curation that growth depends on). Every
                      other reaction stays closed. Their metabolites must have formulas.
                      Boundary and biomass reactions are not closed, so exempting one changes
                      nothing; a warning says so.
    biomass_reactions ids; default: every reaction that produces a biomass token, with a
                      warning if none does (e.g. a BiGG model): biomass then goes uncounted.
    biomass_tokens    ModelSEED ids of biomass tokens. Default ("cpd11416",).
"""
from __future__ import absolute_import

import logging
import re

from modelseedpy.fbapkg.basefbapkg import BaseFBAPkg

logger = logging.getLogger(__name__)

DEFAULT_ELEMENTS = "all"
ELEMENT_SYMBOLS = frozenset(
    """
    H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn Ga Ge As Se
    Br Kr Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb
    Dy Ho Er Tm Yb Lu Hf Ta W Re Os Ir Pt Au Hg Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U Np Pu Am Cm
    Bk Cf Es Fm Md No Lr Rf Db Sg Bh Hs Mt Ds Rg Cn Nh Fl Mc Lv Ts Og""".split()
)
_ATOM = re.compile(r"([A-Z][a-z]?)(\d+(?:\.\d+)?)?")
_RGROUP = re.compile(r"R(?![a-z])(\d+(?:\.\d+)?)?")  # R, not Rb/Re/Rh/Ru/Rn/Ra/Rf/Rg
_R_DROPPED = "explicit atoms (R dropped)"


def parse_elements(spec=None):
    """The `elements` parameter, normalised: DEFAULT_ELEMENTS for None, "all" for "all" (any
    case), otherwise a tuple of element symbols in the order given, duplicates dropped.

    Accepts a string ("C,H,O,N", "C H O", "all") -- the form an environment variable or a
    command-line option arrives in -- or an iterable of symbols (each item may itself be such a
    string). An empty iterable gives () -- no element rows, for a charge-only closure -- but an
    empty or blank string is an error, since it is usually an unset variable. Unknown symbols, and
    "all" mixed with symbols, raise ValueError.
    """
    if spec is None:
        return DEFAULT_ELEMENTS
    if isinstance(spec, (bytes, bytearray)):
        raise ValueError(
            f"elements must be a string or an iterable of symbols, not {type(spec).__name__}"
        )
    split = lambda s: [x for x in re.split(r"[\s,;]+", s.strip()) if x]
    if isinstance(spec, str):
        items = split(spec)
        if not items:
            raise ValueError("no elements given (empty string); pass symbols or 'all'")
    else:
        try:
            raw = list(spec)
        except TypeError:
            raise ValueError(
                f"elements must be a string or an iterable of symbols, not "
                f"{type(spec).__name__}"
            ) from None
        items = []
        for s in raw:
            if not isinstance(s, str):
                raise ValueError(f"element symbols must be strings, not {s!r}")
            items.extend(split(s))
    if any(s.lower() == "all" for s in items):
        if len(items) > 1:
            raise ValueError("'all' cannot be combined with other symbols")
        return "all"
    out = []
    for s in items:
        if s not in ELEMENT_SYMBOLS:
            raise ValueError(
                f"not an element symbol: {s!r} (symbols are case-sensitive, "
                f"e.g. 'Co' not 'CO'; or use 'all')"
            )
        if s not in out:
            out.append(s)
    return tuple(out)


def formula_atoms(formula, strip_r=False):
    """Atom counts of a formula. None if there is none, or if it carries an R group and
    strip_r is False; with strip_r the R groups are dropped and the explicit atoms counted."""
    if not formula or formula in ("null", "noformula", "*"):
        return None
    if _RGROUP.search(formula):
        if not strip_r:
            return None
        formula = _RGROUP.sub("", formula)
    out = {}
    for el, n in _ATOM.findall(formula):
        out[el] = out.get(el, 0.0) + (float(n) if n else 1.0)
    return out


def _base_id(met):
    return met.id.rsplit("_", 1)[0] if "_" in met.id else met.id


class ElementClosurePkg(BaseFBAPkg):
    def __init__(self, model):
        BaseFBAPkg.__init__(self, model, "element closure", {}, {"closure": "string"})
        self.content = {}  # met id -> (atoms dict, charge)
        self.how = {}  # met id -> how its content was assigned
        self.biomass = []
        self.boundary = []
        self.terms = {}  # element -> {reaction id: -imb (coefficient on net flux)}

    # ------------------------------------------------------------------ atom assignment ------
    def _parsed(self, met):
        atoms = formula_atoms(met.formula)
        if atoms is not None:
            return atoms, float(met.charge or 0)
        return None

    def build_contents(self):
        p = self.parameters
        self.content, self.how = {}, {}  # recomputed each build (parameters may differ)
        tokens = set(p["biomass_tokens"])
        for met in self.model.metabolites:
            if _base_id(met) in tokens:
                self.content[met.id], self.how[met.id] = ({}, 0.0), "biomass token"
        if p["biomass_reactions"] is None:
            self.biomass = [
                r
                for r in self.model.reactions
                if any(_base_id(m) in tokens for m in r.products)
            ]
            if not self.biomass:
                logger.warning(
                    f"ElementClosurePkg: no reaction produces a biomass token "
                    f"{sorted(tokens)}, so no biomass reaction is counted and atoms "
                    f"kept in biomass escape the closure; pass biomass_reactions"
                )
        else:
            self.biomass = [
                self.model.reactions.get_by_id(r) for r in p["biomass_reactions"]
            ]
        bio_ids = {r.id for r in self.biomass}

        def known(met):
            if met.id in self.content:
                return self.content[met.id]
            v = self._parsed(met)
            if v is not None:
                self.content[met.id], self.how[met.id] = v, "formula"
            return v

        def makes(r, u, reverse=True):
            # r produces u: u is written as a product, or (reverse) r is reversible and u is
            # written as a reactant, so running r backwards produces it
            if r.id in bio_ids or r.boundary:
                return False
            c = r.metabolites[u]
            return c > 0 or (reverse and c < 0 and r.lower_bound < 0)

        # biomass components with placeholder formulas: give each the content of the reaction
        # that synthesises it; carriers with no producer are zero; repeat until nothing moves
        unknown = {m for b in self.biomass for m in b.metabolites if known(m) is None}
        for _ in range(50):
            moved = False
            for u in sorted(unknown, key=lambda m: m.id):
                # by id: u.reactions is a set, and when several reactions make u the one
                # taken must not depend on the run
                for r in sorted(u.reactions, key=lambda r: r.id):
                    if not makes(r, u):
                        continue
                    others = [m for m in r.metabolites if m is not u]
                    vals = [known(m) for m in others]
                    if any(v is None for v in vals):
                        continue
                    s = r.metabolites[u]  # either sign: u's content balances r
                    atoms, q = {}, 0.0
                    for m, (a, c) in zip(others, vals):
                        for el, n in a.items():
                            atoms[el] = atoms.get(el, 0.0) + r.metabolites[m] * n
                        q += r.metabolites[m] * c
                    self.content[u.id] = (
                        {el: -n / s for el, n in atoms.items() if abs(n) > 1e-12},
                        -q / s,
                    )
                    self.how[u.id] = f"synthesis {r.id}"
                    unknown.discard(u)
                    moved = True
                    break
            if moved:
                continue
            # zero what nothing produces; failing that, carriers produced only by running a
            # reversible reaction backwards (apo-ACP, when ACP loading is reversible), so the
            # pair still counts the moiety incorporated
            dead = [u for u in unknown if not any(makes(r, u) for r in u.reactions)]
            if not dead:
                dead = [
                    u
                    for u in unknown
                    if not any(makes(r, u, reverse=False) for r in u.reactions)
                ]
            for u in dead or list(unknown):
                self.content[u.id] = ({}, 0.0)
                self.how[u.id] = (
                    "zero: carrier with no producer"
                    if dead
                    else "zero: unresolved biomass component"
                )
                unknown.discard(u)
                if not dead:
                    logger.warning(
                        f"ElementClosurePkg: biomass component {u.id} has no "
                        f"resolvable content; counted as zero"
                    )
            if not unknown:
                break

    def atoms_of(self, met):
        """Content of a metabolite under this package's single assignment."""
        if met.id in self.content:
            return self.content[met.id]
        v = self._parsed(met)
        if v is not None:
            how = "formula"
        else:
            a = formula_atoms(met.formula, strip_r=True)
            v, how = (
                ((a, float(met.charge or 0)), _R_DROPPED)
                if a is not None
                else (({}, float(met.charge or 0)), "zero: no formula")
            )
        self.content[met.id], self.how[met.id] = v, how
        return v

    def imbalance(self, rxn, key):
        """Net atoms of `key` (an element, or 'charge') the reaction produces per unit flux."""
        tot = 0.0
        for met, c in rxn.metabolites.items():
            atoms, q = self.atoms_of(met)
            tot += c * (q if key == "charge" else atoms.get(key, 0.0))
        return tot

    # ------------------------------------------------------------------ constraints ----------
    def _state(self):
        """What a build sets and the reports read, so it can be put back."""
        return (
            dict(self.parameters),
            self.content,
            self.how,
            self.biomass,
            self.boundary,
        )

    def _restore(self, state):
        params, self.content, self.how, self.biomass, self.boundary = state
        self.parameters.clear()
        self.parameters.update(params)

    def build_package(self, parameters=None):
        # validate and compute first: a bad parameter must leave the existing rows, and what
        # the reports read, in place
        saved = self._state()
        try:
            terms = self._closure_terms(parameters)
        except Exception:
            self._restore(saved)
            raise
        p = self.parameters
        # then replace the rows -- otherwise rebuilding with fewer elements (say "all", then
        # C,H,O) would leave the dropped elements' rows in the model
        self.clear()
        for key, row in terms.items():
            coef = {}
            for rid, c in row.items():
                r = self.model.reactions.get_by_id(rid)
                coef[r.forward_variable] = coef.get(r.forward_variable, 0.0) + c
                coef[r.reverse_variable] = coef.get(r.reverse_variable, 0.0) - c
            self.build_constraint(
                "closure", 0 if p["sense"] == "eq" else None, 0, coef, key
            )
        self.terms = terms  # what summary/creation/imbalanced_reactions report
        return self.summary()

    def clear(self):
        """Remove this package's closure rows. Only rows still in the solver are removed (a row
        built inside a `with model:` block is gone once the block exits), and only rows named
        for an element or charge -- the package adopts any existing constraint ending in
        '_closure' when it is created, and one that is not a closure row is left alone."""
        rows = self.constraints.get("closure", {})
        mine = {k: c for k, c in rows.items() if k in ELEMENT_SYMBOLS or k == "charge"}
        live = [c for c in mine.values() if c.name in self.model.constraints]
        if live:
            self.model.remove_cons_vars(live)
        self.constraints["closure"] = {k: c for k, c in rows.items() if k not in mine}
        self.terms = {}

    def closure_terms(self, parameters=None):
        """The closure rows without building them: {element: {reaction id: coefficient}}, each
        row reading sum(coefficient * net flux) <= 0 (== 0 with sense "eq").

        For solvers driven outside optlang -- e.g. a model too large to load into an optlang
        interface, solved from its stoichiometric matrix -- add these rows directly.
        build_package builds exactly these. This call changes nothing on the package: not the
        built rows, not its parameters, not what summary(), creation() and
        imbalanced_reactions() report.

        A requested element that no boundary or biomass reaction exchanges gets no row (it would
        read 0 <= 0); a warning names it. With "all" such an element -- present only in
        compounds whose atoms balance in each of those reactions -- is skipped quietly.
        """
        saved = self._state()
        try:
            return self._closure_terms(parameters)
        finally:
            self._restore(saved)

    def _closure_terms(self, parameters):
        # closure_terms, setting parameters, content, how, biomass and boundary as it goes
        self.validate_parameters(
            parameters or {},
            [],
            {
                "elements": DEFAULT_ELEMENTS,
                "charge": False,
                "sense": "le",
                "exempt_reactions": {},
                "biomass_reactions": None,
                "biomass_tokens": ("cpd11416",),
            },
        )
        p = self.parameters
        if p["sense"] not in ("le", "eq"):
            raise ValueError("sense must be 'le' or 'eq'")
        exempt = p["exempt_reactions"]
        if not isinstance(exempt, dict):
            exempt = {r: "" for r in exempt}
        self.build_contents()
        bio_ids = {r.id for r in self.biomass}
        self.boundary = [
            r
            for r in self.model.reactions
            if r.id not in bio_ids
            and (r.boundary or r.id.startswith(("EX_", "SK_", "DM_")))
        ]
        rows = list(self.boundary) + list(self.biomass)
        elements = parse_elements(p["elements"])
        named = elements != "all"
        if elements == "all":
            found, odd = set(), {}
            for r in rows:
                for met in r.metabolites:
                    for sym in self.atoms_of(met)[0]:
                        if sym in ELEMENT_SYMBOLS:
                            found.add(sym)
                        else:
                            odd.setdefault(sym, met.id)
            if odd:
                logger.warning(
                    f"ElementClosurePkg: 'all' skips formula tokens that are not "
                    f"elements: {odd}"
                )
            elements = sorted(found)
        keys = list(elements) + (["charge"] if p["charge"] else [])
        if not keys:
            raise ValueError("no rows to build: give elements, or charge=True")
        exempt_rxns = []
        row_ids = {r.id for r in rows}
        for rid, why in exempt.items():
            if rid not in self.model.reactions:
                continue
            if rid in row_ids:
                # its term already stands for its own exchange of atoms; adding it again
                # would count that exchange twice
                logger.warning(
                    f"ElementClosurePkg: {rid} is a boundary or biomass reaction, which "
                    f"the closure does not constrain; exempting it changes nothing"
                )
                continue
            r = self.model.reactions.get_by_id(rid)
            # biomass tokens and pseudo-compounds were given a content above; anything else
            # without a parseable formula leaves the reaction's own balance undefined (whether
            # or not "all" has already cached it as zero or as its explicit atoms)
            bad = [
                m.id
                for m in r.metabolites
                if self._parsed(m) is None
                and self.how.get(m.id) in (None, "zero: no formula", _R_DROPPED)
            ]
            if bad:
                raise ValueError(
                    f"exempt reaction {rid} has metabolites without a formula: {bad}"
                )
            exempt_rxns.append(r)
            logger.info(f"ElementClosurePkg: {rid} exempt ({why})")
        out = {}
        for key in keys:
            terms = {}
            for r in rows:
                b = self.imbalance(r, key)
                if abs(b) > 1e-12:
                    terms[r.id] = -b
            for r in exempt_rxns:  # allow this reaction's own creation of `key`
                b = self.imbalance(r, key)
                if abs(b) > 1e-12:
                    terms[r.id] = -b
            if not terms:
                if named or key == "charge":
                    logger.warning(
                        f"ElementClosurePkg: no boundary or biomass reaction exchanges "
                        f"{key} (no compound there contains {key}, or it balances in "
                        f"each); no row built for it"
                    )
                continue
            out[key] = terms
        blank = sorted(
            {
                m.id
                for r in self.boundary
                for m in r.metabolites
                if self.how.get(m.id) == "zero: no formula"
            }
        )
        if blank:
            logger.warning(
                f"ElementClosurePkg: {len(blank)} boundary compound(s) have no formula, so "
                f"their exchanges count no atoms and the closure treats what they bring in "
                f"as nothing (give them formulas): {blank[:10]}"
                + (" ..." if len(blank) > 10 else "")
            )
        return out

    # ------------------------------------------------------------------ reporting ------------
    def summary(self):
        how = {}
        for v in self.how.values():
            k = v.split(" ")[0] if v.startswith("synthesis") else v
            how[k] = how.get(k, 0) + 1
        return {
            "rows": sorted(self.terms),
            "boundary_reactions": len(self.boundary),
            "biomass_reactions": len(self.biomass),
            "pseudo_compounds": {
                m: h for m, h in self.how.items() if h.startswith(("synthesis", "zero"))
            },
            "assignment_counts": how,
        }

    def creation(self, fluxes):
        """Net creation of each closed quantity by internal reactions outside the exemptions,
        from a flux mapping (reaction id -> flux). This is the left-hand side of the row:
        positive means the solution creates it, and the row keeps it <= 0. By a^T S v = 0 it
        equals the sum over internal reactions of imbalance x flux."""
        out = {}
        for key, terms in self.terms.items():
            out[key] = sum(
                c * float(fluxes[rid]) for rid, c in terms.items() if rid in fluxes
            )
        return out

    def imbalanced_reactions(self, keys=None, tol=1e-9):
        """Internal reactions that create or destroy a closed quantity, under formulas alone
        (reactions involving an R-group or unformulated metabolite are left out: their balance
        is not defined). These are the curation targets. `keys` defaults to the rows built --
        every element present by default -- or pass keys=[...]. Like closure_terms, it leaves
        what summary() reports unchanged."""
        keys = keys or list(self.terms)
        bio_ids = {r.id for r in self.biomass}
        bnd = {r.id for r in self.boundary}
        # imbalance() caches each metabolite it reads into content/how; work on copies so the
        # assignment counts summary() reports stay those of the build
        content, how = self.content, self.how
        self.content, self.how = dict(content), dict(how)
        try:
            out = {}
            for r in self.model.reactions:
                if r.id in bio_ids or r.id in bnd:
                    continue
                if any(
                    self._parsed(m) is None
                    and not str(self.how.get(m.id, "")).startswith(
                        ("synthesis", "biomass token")
                    )
                    for m in r.metabolites
                ):
                    continue
                imb = {k: self.imbalance(r, k) for k in keys}
                imb = {k: v for k, v in imb.items() if abs(v) > tol}
                if imb:
                    out[r.id] = imb
            return out
        finally:
            self.content, self.how = content, how
