# -*- coding: utf-8 -*-

from __future__ import absolute_import
import logging
from modelseedpy.fbapkg.basefbapkg import BaseFBAPkg
from optlang.symbolics import Zero
import re

logger = logging.getLogger(__name__)

# Base class for FBA packages
class SimpleThermoPkg(BaseFBAPkg):
    """Loop-law constraints: flux may only run down a potential gradient.

    Each metabolite gets a potential p_m and each internal reaction a dgp_r = sum_m S_mr p_m (the
    'dgpc' row). The sign of dgp_r is then tied to the direction of the reaction's flux. Here the
    potentials are free; FullThermoPkg pins those of metabolites with a known formation energy.

    The coupling has to be STRICT, with a margin eps > 0:

        forward flux  ->  dgp_r <= -eps        reverse flux  ->  dgp_r >= +eps

    With eps = 0 -- this package's behaviour before the `dg_margin` parameter existed -- the rows
    read dgp <= 0 / dgp >= 0, and setting every potential to zero makes every dgp zero and
    satisfies all of them whatever the fluxes are. The constraints then exclude nothing: not
    even an internal cycle with no net conversion, which is the one thing loop-law constraints
    are for. A cycle is excluded because the dgp of its reactions must sum to zero around it,
    and they cannot if each one carrying flux must be at least eps below zero.

    Two ways to tie the margin to flux are offered (`coupling`):

    "revbin"  One binary per reaction (RevBinPkg): b = 1 allows forward flux and forces
              dgp <= -eps; b = 0 allows reverse flux and forces dgp >= +eps. Every internal
              reaction must then sit at least eps from equilibrium, including reactions that
              carry no flux. This is loopless FBA (Schellenberger, Lewis & Palsson 2011). With
              free potentials that costs nothing; with pinned potentials (FullThermoPkg) a
              reaction whose attainable dG lies entirely inside (-eps, eps) makes the model
              infeasible even if it never carries flux.

    "tmfa"    Two binaries per reaction, forward-active zf and reverse-active zr, at most one
              of them on: zf = 1 forces dgp <= -eps, zr = 1 forces dgp >= +eps, and with both
              off the reaction carries no flux and its dgp is unconstrained. The margin applies
              only to reactions that carry flux (TMFA, Henry, Broadbelt & Hatzimanikatis 2007).
              It excludes the same cycles, and an idle reaction whose dG cannot leave (-eps, eps)
              does not make the model infeasible. Every dgp is still bounded by max_potential,
              though, so a reaction whose attainable dG lies beyond +/-max_potential makes the
              model infeasible under either coupling (e.g. teichoic acid synthesis with 30
              UDP-sugars, when potentials are pinned).

    Both big-M terms must stay above what the solver can resolve. A binary is accepted as
    integral within the solver's integrality tolerance tau, so the dgp side can slip by
    tau * (max_potential + eps), which must stay well below eps. The package warns when the slip
    reaches a tenth of eps: with max_potential 10000 and eps 1 that is tau >= 1e-5, which is
    Gurobi's own default; cobra sets 1e-7, a slip of 0.001. On the flux side an "off" direction
    can still carry tau * big-M -- big-M is RevBinPkg's fixed 1000 under "revbin" and the
    reaction's largest bound under "tmfa" -- so a loop can trickle through nominally off
    binaries, each leg uphill. The package warns when that reaches 0.01; tighten tau or set the
    solver's IntegralityFocus if it matters. Proving that no loop exists is slow: objectives
    that maximise loop flux need a time limit.

    Defaults differ: this package uses "revbin"; FullThermoPkg, which pins potentials, uses
    "tmfa".

    Build after the final reaction bounds are set. "tmfa" reads them at build time: it gives a
    direction a binary only if the bounds allow flux that way, and caps that flux at the big-M.
    A reaction blocked at build and reopened later has no thermo rows in that direction, and a
    bound widened later is capped at the old one. "revbin" relies on RevBinPkg, whose flux big-M
    is a fixed 1000. Building again replaces this package's coupling rows, so a rebuild with
    another coupling, margin or filter does not leave the previous one's thermo rows behind.
    RevBinPkg's own rows (one direction at a time, flux capped at 1000) stay after a switch from
    "revbin" to "tmfa": RevBinPkg may be shared with other packages on the model, so this
    package does not remove them.

    Parameters (build_package):
        dg_margin      eps, in the units of the potentials -- kJ/mol under FullThermoPkg,
                       arbitrary here. Default 1. 0 restores the old, vacuous behaviour.
        coupling       "revbin" (default) or "tmfa", as above.
        max_potential  bound on each potential and dgp, and the big-M of the dgp side.
        flux_big_m     big-M of the flux side for "tmfa"; None (default) uses each reaction's
                       own largest bound magnitude.
        filter         if given, only these reactions get thermo rows.
        exclude_reactions  reactions to leave unconstrained.
    Exchange (EX_), sink (SK_) and demand (DM_) reactions are never constrained: they cross the
    system boundary, so a potential difference across them has no meaning here. Nor are
    reactions with no metabolites, whose dgp is 0 and so can never clear the margin.
    """

    def __init__(self, model):
        BaseFBAPkg.__init__(
            self,
            model,
            "simple thermo",
            {
                "potential": "metabolite",
                "dgp": "reaction",
                "zf": "reaction",
                "zr": "reaction",
            },
            {
                "thermo": "reaction",
                "dgpc": "reaction",
                "thermof": "reaction",
                "thermor": "reaction",
                "zfc": "reaction",
                "zrc": "reaction",
                "zexcl": "reaction",
            },
        )
        self.pkgmgr.addpkgs(["RevBinPkg"])

    def build_package(self, parameters=None):
        self.validate_parameters(
            parameters or {},
            [],
            {
                "filter": None,
                "max_potential": 10000,
                "exclude_reactions": [],
                "dg_margin": 1.0,
                "coupling": "revbin",
                "flux_big_m": None,
            },
        )
        if self.parameters["coupling"] not in ("revbin", "tmfa"):
            raise ValueError(
                f"coupling must be 'revbin' or 'tmfa', "
                f"not {self.parameters['coupling']!r}"
            )
        eps, M = self.parameters["dg_margin"], self.parameters["max_potential"]
        if not 0 <= eps < M:
            raise ValueError(
                f"dg_margin must satisfy 0 <= dg_margin < max_potential "
                f"({M}), not {eps}"
            )
        big = self.parameters["flux_big_m"]
        if big is not None and not (0 < big < float("inf")):
            raise ValueError(f"flux_big_m must be positive and finite, not {big}")
        self.clear_coupling()
        if self.parameters["coupling"] == "revbin":
            self.pkgmgr.getpkg("RevBinPkg").build_package(self.parameters["filter"])
        for metabolite in self.model.metabolites:
            self.build_potential_variable(metabolite)
        flt = self.parameters["filter"]
        for reaction in self.model.reactions:
            if reaction.id[:3] in ("EX_", "SK_", "DM_"):
                continue
            if reaction.id in self.parameters["exclude_reactions"]:
                continue
            # the thermo rows of "revbin" index RevBinPkg's binaries, which exist only for the
            # filtered reactions -- so the filter has to apply here too
            if flt is not None and reaction.id not in flt:
                continue
            if not reaction.metabolites:
                continue
            self.build_dgp_variable(reaction)
            self.build_dgp_constraint(reaction)
            if self.parameters["coupling"] == "revbin":
                self.build_fluxcoupling_constraint(reaction)
            else:
                self.build_tmfa_coupling(reaction)
        self.check_tolerance()

    def clear_coupling(self):
        """Remove the coupling rows and binaries of an earlier build, of either coupling. The
        potentials and dgp variables are kept, with this build's bounds: build_variable reuses
        them, and other packages (FullThermoPkg) hold rows on the potentials. RevBinPkg's own rows are left alone."""
        objs = []
        for kind in ("thermo", "thermof", "thermor", "zfc", "zrc", "zexcl"):
            objs.extend(self.constraints[kind].values())
            self.constraints[kind] = {}
        for kind in ("zf", "zr"):
            objs.extend(self.variables[kind].values())
            self.variables[kind] = {}
        if objs:
            self.model.remove_cons_vars(objs)

    def build_potential_variable(self, object):
        M = self.parameters["max_potential"]
        variable = self.build_variable("potential", -M, M, "continuous", object)
        # build_variable returns an earlier build's variable unchanged, so a rebuild with
        # another max_potential would keep the old bounds
        variable.set_bounds(-M, M)
        return variable

    def build_dgp_variable(self, object):
        M = self.parameters["max_potential"]
        variable = self.build_variable("dgp", -M, M, "continuous", object)
        # build_variable returns an earlier build's variable unchanged, so a rebuild with
        # another max_potential would keep the old bounds
        variable.set_bounds(-M, M)
        return variable

    def build_dgp_constraint(self, object):
        # Gibbs: dg = Sum(st(i,j)*p(j))
        # 0 <= (-1) dgp(i) + Sum(st(i,j)*p(j)) <= 0
        coef = {}
        for metabolite in object.metabolites:
            coef[self.variables["potential"][metabolite.id]] = object.metabolites[
                metabolite
            ]
        coef[self.variables["dgp"][object.id]] = -1

        return self.build_constraint("dgpc", 0, 0, coef, object)

    def build_fluxcoupling_constraint(self, object):
        """revbin coupling:  eps <= dgp + (M + eps) * revbin <= M

        revbin = 1 (forward allowed):  -M   <= dgp <= -eps
        revbin = 0 (reverse allowed):   eps <= dgp <=  M
        With eps = 0 this is exactly the original row 0 <= dgp + (M+1) revbin <= M+1, whose
        feasible set is the same within the dgp bounds of +/-M.
        """
        M, eps = self.parameters["max_potential"], self.parameters["dg_margin"]
        coef = {
            self.variables["dgp"][object.id]: 1,
            self.pkgmgr.getpkg("RevBinPkg").variables["revbin"][object.id]: M + eps,
        }
        return self.build_constraint("thermo", eps, M, coef, object)

    def build_tmfa_coupling(self, object):
        """tmfa coupling, per direction the reaction's bounds allow.

        forward:  v_fwd - V zf <= 0          dgp + (M + eps) zf <= M     (zf=1 -> dgp <= -eps)
        reverse:  v_rev - V zr <= 0          dgp - (M + eps) zr >= -M    (zr=1 -> dgp >= +eps)
        both:     zf + zr <= 1
        """
        M, eps = self.parameters["max_potential"], self.parameters["dg_margin"]
        big = self.parameters["flux_big_m"]
        if big is None:
            big = max(abs(object.lower_bound), abs(object.upper_bound))
            if big == float("inf"):
                raise ValueError(
                    f"{object.id} has an infinite bound; set finite bounds or "
                    f"pass flux_big_m"
                )
        dgp = self.variables["dgp"][object.id]
        has_f, has_r = object.upper_bound > 0, object.lower_bound < 0
        if has_f:
            zf = self.build_variable("zf", 0, 1, "binary", object)
            self.build_constraint(
                "zfc", None, 0, {object.forward_variable: 1, zf: -big}, object
            )
            self.build_constraint("thermof", None, M, {dgp: 1, zf: M + eps}, object)
        if has_r:
            zr = self.build_variable("zr", 0, 1, "binary", object)
            self.build_constraint(
                "zrc", None, 0, {object.reverse_variable: 1, zr: -big}, object
            )
            self.build_constraint("thermor", -M, None, {dgp: 1, zr: -(M + eps)}, object)
        if has_f and has_r:
            self.build_constraint(
                "zexcl",
                None,
                1,
                {
                    self.variables["zf"][object.id]: 1,
                    self.variables["zr"][object.id]: 1,
                },
                object,
            )

    def check_tolerance(self):
        """Warn when the solver cannot tell the margin apart from zero."""
        eps = self.parameters["dg_margin"]
        if eps <= 0:
            logger.warning(
                "SimpleThermoPkg: dg_margin is 0, so the loop-law rows exclude "
                "nothing (all-zero potentials satisfy them)"
            )
            return
        try:
            tau = self.model.solver.configuration.tolerances.integrality
        except Exception:
            return
        slip = tau * (self.parameters["max_potential"] + eps)
        if slip >= 0.1 * eps:
            logger.warning(
                f"SimpleThermoPkg: integrality tolerance {tau:g} lets dgp slip by {slip:g}, "
                f"not small against dg_margin {eps:g}; tighten the tolerance or lower "
                f"max_potential"
            )
        if self.parameters["coupling"] == "revbin":
            big = 1000.0  # RevBinPkg's fixed flux big-M
        else:
            big = self.parameters["flux_big_m"]
            if big is None:
                big = max(
                    (
                        max(abs(r.lower_bound), abs(r.upper_bound))
                        for r in self.model.reactions
                        if r.id in self.variables["zf"] or r.id in self.variables["zr"]
                    ),
                    default=0.0,
                )
        if tau * big >= 0.01:
            logger.warning(
                f"SimpleThermoPkg: integrality tolerance {tau:g} lets an 'off' direction carry "
                f"up to {tau * big:g} flux (big-M {big:g}); a loop can trickle through it. "
                f"Tighten the tolerance or set IntegralityFocus"
            )
