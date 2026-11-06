# -*- coding: utf-8 -*-
"""Fitness-weighted, per-condition gap-fill and flux analysis.

Port of the fitness-weighted evidence method in Chris Henry's GenomeAnnotationAggregator
(``fitness_simulation.simulate_model_conditions``, ``penalty.build_superset_penalties``,
``fitness_weighted_fba.solve`` and ``evidence.score_edge``), written against the ModelSEEDpy
dev API so it works with any MSTemplate.

Method, per model:

1. Gap-fill superset, built once. MSGapfill extends a copy of the model with every
   candidate reaction of the template and prices the candidates (GapfillingPkg
   gapfilling_penalties). With ``atp_safe`` the candidate database is filtered with
   ATP tests (by default one test: no ATP from an empty medium), so no candidate that
   makes ATP from nothing can be used.
2. Per condition, fitness-weighted FBA on the superset. Biomass is fixed at
   ``frac`` times its optimum and the flux distribution that minimises
   sum(penalty * |flux|) is found. A model reaction with genes costs
   ``p_base - (p_base - p_min) * tanh(fit_best / k)``, where fit_best is the largest
   |fitness| among its genes' significant negative fitness values (fitness < 0 and
   |t| >= t_sig). A model reaction without genes costs ``p_base``. A candidate costs
   ``candidate_scale * candidate_factor * gap-fill penalty``. Mass-imbalanced reactions
   cost ``p_mass_imbalanced``. The solve is loopless when the MILP finishes within
   ``loopless_timeout`` seconds, otherwise a plain LP. Candidates that carry flux are the
   condition's gap-fill solution; their number is the distance to growth.
3. Per condition, restricted FVA on the model reactions with genes (inactive candidates
   closed, biomass at least ``frac`` of the optimum of that network), a commitment class
   per reaction (essential, active, blocked, unused), and a signed evidence score per
   (gene, reaction) edge from the gene's fitness in that condition.

Use only training conditions: the fitness data choose the fluxes.
"""
from __future__ import absolute_import

import logging
import math
import time
from collections import Counter, defaultdict

import cobra
from optlang.interface import OPTIMAL

from modelseedpy.core.msgapfill import MSGapfill
from modelseedpy.core.msmedia import MSMedia
from modelseedpy.core.msmodelutl import MSModelUtil
from modelseedpy.fbapkg.mspackagemanager import MSPackageManager

logger = logging.getLogger(__name__)

# Defaults (GenomeAnnotationAggregator penalty.py, recon_batch.py, evidence.py, config.py)
P_BASE = 1.0
P_MIN = 0.1
K = 2.0
P_GAPFILL = 10.0
P_MASS_IMBALANCED = 1000.0
CANDIDATE_SCALE = 10.0
CANDIDATE_FACTOR = 2.0
T_SIG = 4.0
FIT_IMPORTANT = -2.0
KO_IMPORTANT = 0.5
W_ESSENTIAL = 1.0
W_ACTIVE = 0.5
FRAC = 1.0
LOOPLESS_TIMEOUT = 30.0
FLUX_TOL = 1e-9
MIN_GROWTH = 0.01

ESSENTIAL, ACTIVE, BLOCKED, UNUSED = "essential", "active", "blocked", "unused"
STRONG_POS, STRONG_NEG, POS, MILD_NEG = "strong_pos", "strong_neg", "pos", "mild_neg"
UNEXPLAINED, NEUTRAL = "unexplained", "neutral"
_VERDICT_RANK = {STRONG_POS: 2, STRONG_NEG: 2, POS: 1, MILD_NEG: 1, UNEXPLAINED: 0, NEUTRAL: -1}


def fitness_penalty(fit_best, p_base=P_BASE, p_min=P_MIN, k=K):
    """Penalty of a gene-associated reaction: p_base - (p_base - p_min) * tanh(fit_best / k)."""
    return p_base - (p_base - p_min) * math.tanh(fit_best / k)


def normalize_fitness(fitness):
    """Return {gene: (fitness, t_score)} from any of the accepted input shapes.

    Accepted: {gene: (fitness, t)}, {gene: {"fitness": f, "t_score": t}}, or an iterable of
    rows {"gene": g, "fitness": f, "t_score": t}. A missing t_score is kept as None (never
    significant). Several rows for one gene keep the most negative significant value first,
    then the most negative value.
    """
    out = {}
    if fitness is None:
        return out
    if isinstance(fitness, dict):
        items = []
        for gene, value in fitness.items():
            if isinstance(value, dict):
                items.append((gene, value.get("fitness"), value.get("t_score")))
            elif isinstance(value, (tuple, list)):
                items.append((gene, value[0], value[1] if len(value) > 1 else None))
            else:
                items.append((gene, value, None))
    else:
        items = [(row["gene"], row.get("fitness"), row.get("t_score")) for row in fitness]
    for gene, fit, t in items:
        if fit is None or (isinstance(fit, float) and math.isnan(fit)):
            continue
        if t is not None and isinstance(t, float) and math.isnan(t):
            t = None
        if gene in out:
            old = out[gene]
            if _significant_negative(fit, t, T_SIG) and (
                not _significant_negative(old[0], old[1], T_SIG) or fit < old[0]
            ):
                out[gene] = (fit, t)
            continue
        out[gene] = (fit, t)
    return out


def _significant_negative(fit, t, t_sig):
    return fit is not None and t is not None and fit < 0 and abs(t) >= t_sig


def classify_commitment(fva_min, fva_max, flux, flux_tol=FLUX_TOL):
    """Commitment class: essential (FVA min and max same nonzero sign), else active (carries
    flux in the weighted solution), else blocked (FVA min and max zero), else unused.

    Zero tolerance eps = max(1e-9, 1e-6 * max(|min|, |max|)) as in GAA model_build/outputs.py.
    """
    eps = max(1e-9, 1e-6 * max(abs(fva_min), abs(fva_max)))
    if (fva_min > eps and fva_max > eps) or (fva_min < -eps and fva_max < -eps):
        return ESSENTIAL
    if flux is not None and abs(flux) > flux_tol:
        return ACTIVE
    if abs(fva_min) < eps and abs(fva_max) < eps:
        return BLOCKED
    return UNUSED


def classify_impact(fit, t, is_essential=False, t_sig=T_SIG, fit_important=FIT_IMPORTANT):
    """(is_impactful, weight, tier) for a gene's fitness in one condition.

    tier1: fitness < fit_important and |t| >= t_sig (weight 1). tier2: fit_important <= fitness
    < 0 and |t| >= t_sig (weight |fitness| / |fit_important|, at most 1). essentiality: gene
    essential (weight 1). Anything else, including a missing t, is no impact.
    """
    if is_essential:
        return True, 1.0, "essentiality"
    if fit is None or t is None or abs(t) < t_sig:
        return False, 0.0, None
    if fit < fit_important:
        return True, 1.0, "tier1"
    if fit < 0:
        return True, min(abs(fit) / abs(fit_important), 1.0), "tier2"
    return False, 0.0, None


def score_edge(
    commitment,
    impact,
    ko_ratio=1.0,
    is_gapfill=False,
    ko_important=KO_IMPORTANT,
    w_essential=W_ESSENTIAL,
    w_active=W_ACTIVE,
):
    """Signed evidence for one (gene, reaction) edge in one condition. Returns (verdict, score).

    essential + impact -> strong_pos (+w_essential * weight); essential + no impact ->
    strong_neg (-w_essential) if the gene's knockout ratio < ko_important, else neutral
    (an isozyme covers it); active + impact -> pos (+w_active * weight); active + no impact
    -> mild_neg (-w_active); blocked/unused + impact -> unexplained (0); otherwise neutral.
    Reactions without genes (is_gapfill) are never credited.
    """
    if is_gapfill:
        return NEUTRAL, 0.0
    impactful, weight, _tier = impact
    if commitment == ESSENTIAL:
        if impactful:
            return STRONG_POS, w_essential * weight
        if ko_ratio is not None and ko_ratio < ko_important:
            return STRONG_NEG, -w_essential
        return NEUTRAL, 0.0
    if commitment == ACTIVE:
        if impactful:
            return POS, w_active * weight
        return MILD_NEG, -w_active
    if impactful:
        return UNEXPLAINED, 0.0
    return NEUTRAL, 0.0


def dominant_verdict(verdicts):
    """Most frequent verdict; ties go to the stronger class, then alphabetical order."""
    counts = Counter(verdicts)
    top = max(counts.values())
    cands = [v for v, c in counts.items() if c == top]
    best = max(_VERDICT_RANK.get(v, 0) for v in cands)
    return sorted(v for v in cands if _VERDICT_RANK.get(v, 0) == best)[0]


def _media_from(media):
    if media is None or isinstance(media, MSMedia):
        return media
    if isinstance(media, dict):
        return MSMedia.from_dict({k: tuple(v) if isinstance(v, (list, tuple)) else v for k, v in media.items()})
    raise TypeError("media must be an MSMedia, a {cpd: (lb, ub)} dict or None")


def _release(model):
    MSModelUtil.mdlutls.pop(model, None)
    MSPackageManager.pkgmgrs.pop(model, None)


class MSFitnessWeightedAnalysis:
    """Fitness-weighted per-condition gap-fill and flux analysis for one model.

    Parameters
    ----------
    model_or_mdlutl : cobra.Model or MSModelUtil
        The model. It is not changed (MSGapfill works on a copy).
    template : MSTemplate
        Any ModelSEED template; its reactions are the gap-fill candidates.
    biomass : str
        Biomass reaction id.
    atp_safe : bool
        Filter candidates that break the ATP tests before any solve.
    atp_tests : list or None
        Tests as MSATPCorrection.build_tests returns them ({"media", "is_max_threshold",
        "threshold", "objective"}). None means one test: ATP hydrolysis at most 1e-5 on an
        empty medium (the first test MSATPCorrection.build_tests makes).
    blacklist : list
        Template reaction ids never added as candidates.
    gene_reactions : dict or None
        {reaction_id: [gene, ...]} or {reaction_id: {gene: [source, ...]}} edges to score.
        None takes the edges from the model's gene rules (source "model").
    mass_imbalanced : iterable or None
        Bare ModelSEED ids (rxnNNNNN) of mass-imbalanced reactions: candidates among them
        are closed, model reactions among them cost p_mass_imbalanced.
    price_reversals : bool
        If a model reaction's direction is opened only by the gap-fill superset (the model
        has it one-way, the template two-way), price that direction as a candidate and
        report it as gap-filled. GAA prices it like the model reaction and never reports it
        (False reproduces that).
    biomass_reference : str
        "superset": fix biomass at frac times the optimum of the model plus all candidates
        (GAA). "model": if the model alone grows, frac times the model's own optimum, else
        as "superset". With "superset", a model that grows can still need candidates to
        reach the higher superset optimum.
    """

    def __init__(
        self,
        model_or_mdlutl,
        template,
        biomass="bio1",
        atp_safe=True,
        atp_tests=None,
        blacklist=None,
        gene_reactions=None,
        mass_imbalanced=None,
        p_base=P_BASE,
        p_min=P_MIN,
        k=K,
        p_gapfill=P_GAPFILL,
        p_mass_imbalanced=P_MASS_IMBALANCED,
        candidate_scale=CANDIDATE_SCALE,
        candidate_factor=CANDIDATE_FACTOR,
        t_sig=T_SIG,
        fit_important=FIT_IMPORTANT,
        ko_important=KO_IMPORTANT,
        w_essential=W_ESSENTIAL,
        w_active=W_ACTIVE,
        frac=FRAC,
        loopless=True,
        loopless_timeout=LOOPLESS_TIMEOUT,
        flux_tol=FLUX_TOL,
        min_growth=MIN_GROWTH,
        price_reversals=True,
        biomass_reference="superset",
        compartment="c0",
    ):
        if isinstance(model_or_mdlutl, MSModelUtil):
            self.mdlutl = model_or_mdlutl
        else:
            self.mdlutl = MSModelUtil.get(model_or_mdlutl)
        self.model = self.mdlutl.model
        self.template = template
        self.biomass = biomass
        if biomass not in self.model.reactions:
            raise ValueError("biomass reaction " + biomass + " not in model")
        if not 0 < p_min <= p_base:
            raise ValueError("need 0 < p_min <= p_base")
        if biomass_reference not in ("superset", "model"):
            raise ValueError("biomass_reference must be 'superset' or 'model'")
        self.atp_safe = atp_safe
        self.atp_tests = atp_tests
        self.blacklist = list(blacklist or [])
        self.mass_imbalanced = set(mass_imbalanced or [])
        self.params = dict(
            p_base=p_base, p_min=p_min, k=k, p_gapfill=p_gapfill, p_mass_imbalanced=p_mass_imbalanced,
            candidate_scale=candidate_scale, candidate_factor=candidate_factor, t_sig=t_sig,
            fit_important=fit_important, ko_important=ko_important, w_essential=w_essential,
            w_active=w_active, frac=frac, loopless=loopless, loopless_timeout=loopless_timeout,
            flux_tol=flux_tol, min_growth=min_growth, price_reversals=price_reversals,
            biomass_reference=biomass_reference,
        )
        self.compartment = compartment
        self.draft_reactions = {r.id for r in self.model.reactions}
        self.edges = self._edges(gene_reactions)
        self.gapfiller = None
        self.superset = None
        self.timing = {}

    # ------------------------------------------------------------------ inputs
    def _edges(self, gene_reactions):
        """{reaction_id: {gene: [sources]}} restricted to model reactions."""
        edges = {}
        if gene_reactions is None:
            for rxn in self.model.reactions:
                if rxn.genes:
                    edges[rxn.id] = {g.id: ["model"] for g in rxn.genes}
            return edges
        for rid, genes in gene_reactions.items():
            if rid not in self.draft_reactions:
                continue
            if isinstance(genes, dict):
                edges[rid] = {g: list(src) if src else ["model"] for g, src in genes.items()}
            else:
                edges[rid] = {g: ["model"] for g in genes}
        return edges

    # ------------------------------------------------------------------ stage 1
    def build_superset(self):
        """Build the gap-fill superset once (model plus all template candidates) and, with
        atp_safe, filter the candidates with the ATP tests. Returns the superset model."""
        t0 = time.time()
        self.gapfiller = MSGapfill(
            self.mdlutl,
            default_gapfill_templates=[self.template],
            default_target=self.biomass,
            minimum_obj=self.params["min_growth"],
            test_conditions=[],
            reaction_scores={},
            blacklist=self.blacklist,
        )
        # MSGapfill registers itself as the model's gap-filler; undo that side effect
        if getattr(self.mdlutl, "gfutl", None) is self.gapfiller:
            self.mdlutl.gfutl = None
        self.superset = self.gapfiller.gfmodelutl.model
        gfpkg = self.gapfiller.gfpkgmgr.getpkg("GapfillingPkg")
        self.gapfilling_penalties = {k: dict(v) for k, v in gfpkg.gapfilling_penalties.items()}
        self.superset_bounds_before_filter = {r.id: r.bounds for r in self.superset.reactions}
        self.timing["superset"] = time.time() - t0
        self.atp_reaction = None
        self._added_atp_reaction = False
        self.filtered = {}
        if self.atp_safe:
            t1 = time.time()
            tests = self.atp_tests
            if tests is None:
                tests = [self._empty_atp_test()]
            gfpkg.filter_database_based_on_tests(tests)
            for rxn in self.superset.reactions:
                lb0, ub0 = self.superset_bounds_before_filter.get(rxn.id, rxn.bounds)
                dirs = ""
                if ub0 > 0 and rxn.upper_bound <= 0:
                    dirs += ">"
                if lb0 < 0 and rxn.lower_bound >= 0:
                    dirs += "<"
                if dirs:
                    self.filtered[rxn.id] = dirs
            self.timing["atp_filter"] = time.time() - t1
        # the gap-fill objective constraint (biomass >= minimum_obj) is not part of this
        # method: growth is checked explicitly against min_growth
        objconst = self.gapfiller.gfpkgmgr.getpkg("ObjConstPkg", False)
        if objconst is not None:
            cons = list(objconst.constraints.get("objc", {}).values())
            if cons:
                self.superset.remove_cons_vars(cons)
            objconst.constraints["objc"] = {}
        if self._added_atp_reaction:
            self.superset.reactions.get_by_id(self.atp_reaction).bounds = (0, 0)
        self._classify_superset()
        return self.superset

    def _empty_atp_test(self):
        """ATP hydrolysis at most 1e-5 on an empty medium."""
        found = None
        for rxn in self.superset.reactions:
            if rxn.id.startswith("rxn00062_") or rxn.id.startswith("ATPM"):
                if rxn.id in self.draft_reactions:
                    found = rxn.id
                    break
        if found is None:
            output = self.gapfiller.gfmodelutl.add_atp_hydrolysis(self.compartment)
            if output is None:
                raise ValueError("no ATP hydrolysis reaction and none can be added")
            found = output["reaction"].id
            self._added_atp_reaction = output.get("new", False)
        self.atp_reaction = found
        empty = MSMedia.from_dict({})
        empty.id = empty.name = "empty"
        return {"media": empty, "is_max_threshold": True, "threshold": 0.00001, "objective": found}

    def _classify_superset(self):
        sup = self.superset
        self.candidates = {r.id for r in sup.reactions if r.id not in self.draft_reactions}
        # directions of model reactions that only the superset opens
        self.reversals = {}
        for rid, pen in self.gapfilling_penalties.items():
            if rid in self.draft_reactions and rid in sup.reactions:
                orig = self.model.reactions.get_by_id(rid)
                dirs = ""
                if "forward" in pen and orig.upper_bound <= 0:
                    dirs += ">"
                if "reverse" in pen and orig.lower_bound >= 0:
                    dirs += "<"
                if dirs:
                    self.reversals[rid] = dirs
        self.mass_imbalanced_ids = set()
        if self.mass_imbalanced:
            for rxn in sup.reactions:
                if rxn.id.split("_")[0] in self.mass_imbalanced:
                    self.mass_imbalanced_ids.add(rxn.id)
                    if rxn.id not in self.draft_reactions:
                        rxn.bounds = (0, 0)
        self.priced = [
            r.id for r in sup.reactions if not r.boundary and r.id != self.biomass
        ]

    # ------------------------------------------------------------------ penalties
    def gene_fit_best(self, fitness):
        """{gene: largest |fitness| among significant negative values}."""
        t_sig = self.params["t_sig"]
        out = {}
        for gene, (fit, t) in fitness.items():
            if _significant_negative(fit, t, t_sig):
                out[gene] = abs(fit)
        return out

    def reaction_penalties(self, fitness):
        """Directional penalties {rxn: {">": p, "<": p}} for every priced superset reaction."""
        if self.superset is None:
            self.build_superset()
        P = self.params
        fit_best = self.gene_fit_best(fitness)
        cand_mult = P["candidate_scale"] * P["candidate_factor"]
        out = {}
        for rid in self.priced:
            if rid in self.mass_imbalanced_ids:
                out[rid] = {">": P["p_mass_imbalanced"], "<": P["p_mass_imbalanced"]}
                continue
            if rid not in self.draft_reactions:
                pen = self.gapfilling_penalties.get(rid) or {}
                out[rid] = {
                    ">": max(cand_mult * float(pen.get("forward", P["p_gapfill"] / cand_mult) or 1.0), 1e-9),
                    "<": max(cand_mult * float(pen.get("reverse", P["p_gapfill"] / cand_mult) or 1.0), 1e-9),
                }
                continue
            genes = self.edges.get(rid)
            if not genes:
                p = P["p_base"]
            else:
                best = max((fit_best.get(g, 0.0) for g in genes), default=0.0)
                p = fitness_penalty(best, P["p_base"], P["p_min"], P["k"])
            pen = {">": p, "<": p}
            if P["price_reversals"] and rid in self.reversals:
                gp = self.gapfilling_penalties.get(rid) or {}
                if ">" in self.reversals[rid]:
                    pen[">"] = cand_mult * float(gp.get("forward", 1.0) or 1.0)
                if "<" in self.reversals[rid]:
                    pen["<"] = cand_mult * float(gp.get("reverse", 1.0) or 1.0)
            out[rid] = pen
        return out

    # ------------------------------------------------------------------ helpers
    def _condition_model(self, media):
        model = self.superset.copy()
        mdlutl = MSModelUtil.get(model)
        if media is not None:
            mdlutl.pkgmgr.getpkg("KBaseMediaPkg").build_package(media)
        return model

    def _optimum(self, model):
        with model:
            model.objective = self.biomass
            model.objective_direction = "max"
            value = model.slim_optimize(error_value=float("nan"))
        return None if value is None or math.isnan(value) else value

    def _close(self, model, reactions):
        for rid in reactions:
            if rid in model.reactions:
                model.reactions.get_by_id(rid).bounds = (0, 0)

    def _close_reversal_directions(self, model, fluxes=None):
        """Close superset-opened directions of model reactions (unless used in fluxes)."""
        for rid, dirs in self.reversals.items():
            rxn = model.reactions.get_by_id(rid)
            v = 0.0 if fluxes is None else fluxes.get(rid, 0.0)
            if ">" in dirs and not v > self.params["flux_tol"]:
                rxn.upper_bound = 0
            if "<" in dirs and not v < -self.params["flux_tol"]:
                rxn.lower_bound = 0

    def _weighted_solve(self, model, penalties, target):
        """Fix biomass at target and minimise sum(penalty * |flux|). Returns (fluxes, loopless)."""
        attempts = [True, False] if self.params["loopless"] else [False]
        for loopless in attempts:
            work = model.copy()
            try:
                bio = work.reactions.get_by_id(self.biomass)
                bio.bounds = (target, target)
                if loopless:
                    cobra.flux_analysis.loopless.add_loopless(work)
                work.solver.configuration.timeout = (
                    self.params["loopless_timeout"] if loopless else model.solver.configuration.timeout
                )
                pkg = MSPackageManager.get_pkg_mgr(work).getpkg("FitnessWeightedFluxPkg")
                pkg.build_package(penalties)
                status = work.solver.optimize()
                if status == OPTIMAL:
                    return (
                        {r.id: float(r.forward_variable.primal - r.reverse_variable.primal) for r in work.reactions},
                        loopless,
                    )
                logger.info("weighted solve status %s (loopless=%s)", status, loopless)
            except Exception as exc:  # noqa: BLE001 - any loopless failure falls back to the LP
                if not loopless:
                    raise
                logger.warning("loopless solve failed (%s); using the LP", exc)
            finally:
                _release(work)
        return None, False

    def _fva(self, model, reaction_ids, frac):
        """Restricted FVA: biomass >= frac * optimum, min and max of each listed reaction."""
        out = {}
        with model:
            opt = self._optimum(model)
            if opt is None:
                return out, None
            model.reactions.get_by_id(self.biomass).lower_bound = frac * opt * (1 - 1e-9)
            for rid in reaction_ids:
                if rid not in model.reactions:
                    continue
                rxn = model.reactions.get_by_id(rid)
                model.objective = rxn
                model.objective_direction = "max"
                vmax = model.slim_optimize(error_value=float("nan"))
                model.objective_direction = "min"
                vmin = model.slim_optimize(error_value=float("nan"))
                if math.isnan(vmax) or math.isnan(vmin):
                    continue
                out[rid] = (vmin, vmax)
        return out, opt

    def _ko_ratios(self, model, genes, wild_type):
        """{gene: knockout growth / wild-type growth} on the condition network."""
        out = {}
        for gene in genes:
            if gene not in model.genes:
                continue
            with model:
                model.genes.get_by_id(gene).knock_out()
                g = self._optimum(model)
            out[gene] = 0.0 if g is None or wild_type <= 0 else max(g, 0.0) / wild_type
        return out

    # ------------------------------------------------------------------ per condition
    def analyze_condition(self, condition_id, media, fitness, essential_genes=None, fluxes_out=True):
        """Run stages 2 and 3 for one condition.

        Parameters
        ----------
        condition_id : str
        media : MSMedia, {cpd: (lb, ub)} dict or None (model bounds as they are)
        fitness : fitness data in any shape normalize_fitness accepts; only this condition
        essential_genes : genes counted as essentiality impact (for a rich-medium condition)
        fluxes_out : include the nonzero flux distribution in the result

        Returns
        -------
        dict with status, growth, gap-fill solution, distance to growth, annotation gap,
        reaction calls {rxn: [class, flux]} for model reactions with genes, and edge evidence.
        """
        if self.superset is None:
            self.build_superset()
        P = self.params
        tol = P["flux_tol"]
        fit = normalize_fitness(fitness)
        essential_genes = set(essential_genes or [])
        res = {"condition": condition_id, "status": None}
        t0 = time.time()
        media = _media_from(media)
        model = self._condition_model(media)
        try:
            opt_superset = self._optimum(model)
            res["growth_superset"] = opt_superset
            if opt_superset is None or opt_superset <= tol or opt_superset < P["min_growth"]:
                res["status"] = "no_growth"
                res["time_s"] = time.time() - t0
                return res
            if not fit and not essential_genes:
                res["status"] = "no_fitness"
                res["time_s"] = time.time() - t0
                return res
            with model:
                self._close(model, self.candidates)
                self._close_reversal_directions(model)
                opt_model = self._optimum(model)
            res["growth_model"] = opt_model
            target = P["frac"] * opt_superset
            if P["biomass_reference"] == "model" and opt_model is not None and opt_model >= P["min_growth"]:
                target = P["frac"] * opt_model
            res["biomass_fixed"] = target
            penalties = self.reaction_penalties(fit)
            t1 = time.time()
            fluxes, loopless = self._weighted_solve(model, penalties, target)
            res["time_solve_s"] = time.time() - t1
            if fluxes is None:
                res["status"] = "solver_failed"
                res["time_s"] = time.time() - t0
                return res
            res["loopless"] = loopless
            res["objective"] = sum(
                (penalties[r][">"] * v if v > 0 else -penalties[r]["<"] * v)
                for r, v in fluxes.items() if r in penalties and abs(v) > tol
            )
            gapfilled = {}
            for rid in self.candidates:
                v = fluxes.get(rid, 0.0)
                if abs(v) > tol:
                    gapfilled[rid] = ">" if v > 0 else "<"
            reversed_used = {}
            for rid, dirs in self.reversals.items():
                v = fluxes.get(rid, 0.0)
                if (">" in dirs and v > tol) or ("<" in dirs and v < -tol):
                    reversed_used[rid] = ">" if v > 0 else "<"
            res["gapfilled"] = gapfilled
            res["reversals_used"] = reversed_used
            res["distance_to_growth"] = len(gapfilled) + (len(reversed_used) if P["price_reversals"] else 0)
            res["annotation_gap"] = res["distance_to_growth"] > 0
            if fluxes_out:
                res["fluxes"] = {r: v for r, v in fluxes.items() if abs(v) > tol}
            # restricted FVA on the network the solution uses
            t2 = time.time()
            with model:
                self._close(model, [r for r in self.candidates if r not in gapfilled])
                self._close_reversal_directions(model, fluxes)
                fva, opt_net = self._fva(model, list(self.edges), P["frac"])
                res["growth_network"] = opt_net
                calls = {}
                for rid in self.edges:
                    if rid not in fva:
                        continue
                    vmin, vmax = fva[rid]
                    v = fluxes.get(rid, 0.0)
                    calls[rid] = [classify_commitment(vmin, vmax, v, tol), v, vmin, vmax]
                res["reaction_calls"] = calls
                # knockout ratios only where they decide a verdict (essential, no impact)
                need = set()
                for rid, call in calls.items():
                    if call[0] != ESSENTIAL:
                        continue
                    for gene in self.edges[rid]:
                        f, t = fit.get(gene, (None, None))
                        if not classify_impact(f, t, gene in essential_genes, P["t_sig"], P["fit_important"])[0]:
                            need.add(gene)
                kos = self._ko_ratios(model, sorted(need), opt_net or 0.0) if need else {}
            res["time_fva_s"] = time.time() - t2
            res["edge_evidence"] = self.score_condition_edges(calls, fit, kos, essential_genes)
            res["status"] = "done"
            res["time_s"] = time.time() - t0
            return res
        finally:
            _release(model)

    def score_condition_edges(self, calls, fitness, ko_ratios=None, essential_genes=None):
        """Edge evidence rows for one condition: one row per (gene, reaction, source) whose
        verdict is not neutral."""
        P = self.params
        ko_ratios = ko_ratios or {}
        essential_genes = essential_genes or set()
        rows = []
        for rid, call in calls.items():
            commitment = call[0]
            for gene, sources in self.edges.get(rid, {}).items():
                f, t = fitness.get(gene, (None, None))
                impact = classify_impact(f, t, gene in essential_genes, P["t_sig"], P["fit_important"])
                ko = ko_ratios.get(gene, 1.0)
                verdict, score = score_edge(
                    commitment, impact, ko, False, P["ko_important"], P["w_essential"], P["w_active"]
                )
                if verdict == NEUTRAL:
                    continue
                for source in sources:
                    rows.append({
                        "gene": gene, "reaction": rid, "source": source, "verdict": verdict, "score": score,
                        "commitment": commitment, "fitness": f, "t_score": t, "tier": impact[2], "ko_ratio": ko,
                    })
        return rows

    # ------------------------------------------------------------------ many conditions
    def run(self, conditions, fluxes_out=True):
        """Analyse several conditions.

        Parameters
        ----------
        conditions : dict
            {condition_id: {"media": media, "fitness": fitness, "essential_genes": [...]}}

        Returns
        -------
        dict with per-condition results, the annotation evidence rollup and timing.
        """
        if self.superset is None:
            self.build_superset()
        results = {}
        for cid, spec in conditions.items():
            results[cid] = self.analyze_condition(
                cid, spec.get("media"), spec.get("fitness"), spec.get("essential_genes"), fluxes_out
            )
        return {
            "conditions": results,
            "annotation_evidence": self.aggregate_evidence(results),
            "superset": self.summary(),
        }

    @staticmethod
    def aggregate_evidence(results):
        """Roll edge evidence up to one row per (gene, reaction, source) over conditions."""
        groups = defaultdict(list)
        for cid, res in results.items():
            for row in res.get("edge_evidence", []):
                groups[(row["gene"], row["reaction"], row["source"])].append(dict(row, condition=cid))
        out = []
        for (gene, rid, source), rows in sorted(groups.items()):
            counts = Counter(r["verdict"] for r in rows)
            out.append({
                "gene": gene, "reaction": rid, "source": source,
                "net_score": sum(r["score"] for r in rows),
                "n_strong_pos": counts.get(STRONG_POS, 0), "n_pos": counts.get(POS, 0),
                "n_mild_neg": counts.get(MILD_NEG, 0), "n_strong_neg": counts.get(STRONG_NEG, 0),
                "n_unexplained": counts.get(UNEXPLAINED, 0),
                "n_conditions": len({r["condition"] for r in rows}),
                "dominant_verdict": dominant_verdict([r["verdict"] for r in rows]),
            })
        return out

    def summary(self):
        if self.superset is None:
            return {}
        return {
            "n_model_reactions": len(self.draft_reactions),
            "n_superset_reactions": len(self.superset.reactions),
            "n_candidates": len(self.candidates),
            "n_reversal_candidates": len(self.reversals),
            "n_filtered_directions": len(self.filtered),
            "atp_reaction": self.atp_reaction,
            "timing": dict(self.timing),
            "params": dict(self.params),
        }
