# -*- coding: utf-8 -*-

from __future__ import absolute_import

import logging
from scipy.constants import physical_constants, calorie, kilo, R
from optlang.symbolics import Zero, add
import numpy as np
from numpy import log as ln
from modelseedpy.fbapkg.basefbapkg import BaseFBAPkg
from modelseedpy.core.fbahelper import FBAHelper
from modelseedpy.biochem.modelseed_biochem import UNKNOWN_DELTAG, NO_ESTIMATE_ERROR

logger = logging.getLogger(__name__)

# Units. The database (and a metabolite's notes['deltag']) give formation energies and their
# errors in kcal/mol. Everything inside this package -- potentials, dgp, the error variables,
# default_max_error, custom_deltaG_error, max_potential, dg_margin -- is kJ/mol. Every value read
# from the database is converted with KCAL_TO_KJ on the way in.
KCAL_TO_KJ = 4.184

# Base class for FBA packages
class FullThermoPkg(BaseFBAPkg):
    @staticmethod
    def default_concentration():
        return {
            "cpd00067_c0": [0.0000001, 0.0000001],  # M H+ - equivalent to pHint = 7
            "cpd00007_c0": [1e-07, 8.2e-06],  # M O2 instracellular
            "cpd00011_c0": [1e-08, 0.0014],  # M CO2 instracellular
            "cpd00067_e0": [
                3.16228e-08,
                3.16228e-07,
            ],  # M H+ - equivalent to pHext = 6.5
            "cpd00009_e0": [
                0.056,
                0.056,
            ],  # Extracellular phosphate - overridden by media when media concentration is given
            "cpd00048_e0": [
                0.0030,
                0.0030,
            ],  # Extracellular sulfate - overridden by media when media concentration is given
            "cpd00013_e0": [
                0.019,
                0.019,
            ],  # Extracellular ammonia - overridden by media when media concentration is given
            "cpd00971_e0": [
                0.16,
                0.16,
            ],  # Extracellular sodium - overridden by media when media concentration is given
            "cpd00205_e0": [
                0.022,
                0.022,
            ],  # Extracellular potassium - overridden by media when media concentration is given
            "cpd10515_e0": [
                0.062,
                0.062,
            ],  # Extracellular Fe2+ - overridden by media when media concentration is given
            "cpd00011_e0": [
                0.00010,
                0.00010,
            ],  # Extracellular CO2 - overridden by media when media concentration is given
            "cpd00007_e0": [
                8.2e-06,
                8.2e-06,
            ],  # Extracellular O2 - overridden by media when media concentration is given
            "cpd00027_e0": [
                0.020,
                0.020,
            ],  # Extracellular glucose - overridden by media when media concentration is given
        }

    def __init__(self, model):
        BaseFBAPkg.__init__(
            self,
            model,
            "full thermo",
            {
                "logconc": "metabolite",
                "pdgerr": "metabolite",
                "ndgerr": "metabolite",
                "pconcfit": "metabolite",
                "nconcfit": "metabolite",
            },
            {"potc": "metabolite", "concfit": "metabolite"},
        )
        self.pkgmgr.addpkgs(["SimpleThermoPkg"])

    def build_package(self, parameters, verbose=True):
        self.validate_parameters(
            parameters,
            [],
            {
                "default_max_conc": 0.02,  # M
                "default_min_conc": 0.000001,  # M
                "default_max_error": 5,  # kJ/mol
                "custom_concentrations": {},
                "custom_deltaG_error": {"cpd00067": 0},
                "compartment_potential": {
                    "e0": 0,  # mV — extracellular MUST be the zero reference for compartment electrochemical potential (so community modeling works)
                    "c0": -160,  # mV = 0.33*(pHint - pHext) - 143.33 where pHint=7, pHext=6.5
                },
                "temperature": 298,  # K
                "filter": None,
                "infeasible_model": False,
                "dgbin": False,
                "modelseed_db_path": None,
                "exclude_reactions": [],
                "set_min_error_objective": False,
                "set_concfit_objective": False,
                # The bound on a compound's chemical potential, which is also the
                # big-M of the direction rows of SimpleThermoPkg. At the old
                # 100000 those rows are badly scaled against the kJ/mol of the
                # energies, and the solver returns different "optimal" answers as
                # the integrality tolerance moves; it only has to exceed the
                # largest potential the model can reach.
                "max_potential": 10000,  # kJ/mol
                # the loop-law margin, kJ/mol: a reaction carrying flux must be at least this
                # far below equilibrium. 0 makes the direction rows vacuous -- all-zero
                # potentials satisfy them -- so near-equilibrium internal cycles are not
                # excluded (see SimpleThermoPkg).
                "dg_margin": 1.0,
                # "tmfa": the margin applies only to reactions that carry flux, so a reaction
                # whose pinned dG cannot leave (-dg_margin, dg_margin) is idle rather than
                # making the model infeasible. "revbin" applies it to every reaction (loopless
                # FBA). SimpleThermoPkg on its own defaults to "revbin". Either way a reaction
                # whose dG cannot fit within +/-max_potential (large polymers) is infeasible.
                "coupling": "tmfa",
                # take each compound's error bound from the database's own
                # estimate where it is larger than default_max_error
                "use_database_error": True,
                "concfit_objective_type": "l1",
                "concfit_weights": None,
            },
        )
        simple_thermo_parameters = {
            "filter": self.parameters["filter"],
            "dg_margin": self.parameters["dg_margin"],
            "coupling": self.parameters["coupling"],
            "min_potential": -self.parameters["max_potential"],
            "max_potential": self.parameters["max_potential"],
            "dgbin": self.parameters["dgbin"],
            "exclude_reactions": self.parameters["exclude_reactions"],
        }
        if self.parameters["infeasible_model"]:
            simple_thermo_parameters["dgbin"] = True
        self.pkgmgr.getpkg("SimpleThermoPkg").build_package(simple_thermo_parameters)
        # database_error() sets this when the database cannot be loaded; each build tries again
        self._database_unavailable = False

        self.parameters[
            "combined_custom_concentrations"
        ] = FullThermoPkg.default_concentration()
        for cpd in self.parameters["custom_concentrations"]:
            self.parameters["combined_custom_concentrations"][cpd] = self.parameters[
                "custom_concentrations"
            ][cpd]
        msid_hash = {}
        for metabolite in self.model.metabolites:
            msid = FBAHelper.modelseed_id_from_cobra_metabolite(metabolite)
            if msid != None:
                if msid not in msid_hash:
                    msid_hash[msid] = {}
                msid_hash[msid][metabolite.id] = metabolite
            # Build concentration variable
            self.build_logconc_variable(metabolite)
            # Build error variable
            self.build_dgerr_variables(metabolite)
            # Build the potential constraint
            self.build_gibbs_constraint(metabolite)
        if self.parameters["set_min_error_objective"]:
            self.build_min_error_objective()
        if self.parameters["set_concfit_objective"]:
            if "target_concentrations" not in self.parameters:
                raise ValueError(
                    "build_package: 'target_concentrations' is required in parameters "
                    "when 'set_concfit_objective' is True."
                )
            target_concentrations = self.parameters["target_concentrations"]
            concfit_weights = self.parameters["concfit_weights"]
            objective_type = self.parameters["concfit_objective_type"]
            if objective_type == "l2":
                self.build_concfit_objective_l2(target_concentrations, concfit_weights)
            elif objective_type == "l1":
                self.build_concfit_objective(target_concentrations, concfit_weights)
            else:
                raise ValueError(
                    f"build_package: 'concfit_objective_type' must be 'l1' or 'l2', got {objective_type!r}."
                )

    def build_min_error_objective(self):
        objvars = []
        for metabolite in self.model.metabolites:
            if metabolite.id in self.variables["pdgerr"]:
                objvars.append(self.variables["pdgerr"][metabolite.id])
            if metabolite.id in self.variables["ndgerr"]:
                objvars.append(self.variables["ndgerr"][metabolite.id])
        self._set_min_objective(objvars)

    @staticmethod
    def _validate_concfit_weights(weights):
        """Validate a metabolite-id -> weight dict: every weight must be a
        finite number >= 0. Raises ValueError otherwise. A weight of 0 is
        valid (it drops that metabolite's term from the objective)."""
        for metabolite_id, weight in weights.items():
            if weight is None or not np.isfinite(weight):
                raise ValueError(
                    f"Weight for metabolite '{metabolite_id}' must be a finite number; got {weight!r}."
                )
            if weight < 0:
                raise ValueError(
                    f"Weight for metabolite '{metabolite_id}' must be >= 0; got {weight!r}."
                )

    def _is_qp_capable_solver(self):
        """Detect whether self.model is currently attached to a QP-capable
        optlang backend (gurobi or cplex), by module identity of the solver
        interface. GLPK, SCIPY, and the hybrid interface are not QP-capable
        (see build_concfit_objective_l2 for why this matters)."""
        interface_name = getattr(self.model.solver.interface, "__name__", "")
        return interface_name.startswith(
            "optlang.gurobi_interface"
        ) or interface_name.startswith("optlang.cplex_interface")

    def _require_qp_capable_solver(self):
        if not self._is_qp_capable_solver():
            raise NotImplementedError(
                "L2 concentration-fit objective requires a QP-capable solver backend "
                "(gurobi/cplex) - set model.solver before calling build_package"
            )

    def build_concfit_objective(self, target_concentrations, weights=None):
        weights = weights or {}
        self._validate_concfit_weights(weights)
        # Removing all existing concfit constraints, from the model and from
        # self.constraints: build_constraint removes a row it still finds there, and a
        # row already gone from the solver raises LookupError on a second fit
        for metabolite in self.model.metabolites:
            if metabolite.id in self.constraints["concfit"]:
                self.model.remove_cons_vars(self.constraints["concfit"][metabolite.id])
                del self.constraints["concfit"][metabolite.id]
        objcoefs = {}
        for metabolite in self.model.metabolites:
            if metabolite.id in target_concentrations:
                w = weights.get(metabolite.id, 1.0)
                if metabolite.id not in self.variables["pconcfit"]:
                    self.build_variable("pconcfit", 0, 100, "continuous", metabolite)
                if metabolite.id not in self.variables["nconcfit"]:
                    self.build_variable("nconcfit", 0, 100, "continuous", metabolite)
                self.build_constraint(
                    "concfit",
                    target_concentrations[metabolite.id],
                    target_concentrations[metabolite.id],
                    {
                        self.variables["pconcfit"][metabolite.id]: 1,
                        self.variables["nconcfit"][metabolite.id]: -1,
                        self.variables["logconc"][metabolite.id]: 1,
                    },
                    metabolite,
                )
                objcoefs[self.variables["pconcfit"][metabolite.id]] = w
                objcoefs[self.variables["nconcfit"][metabolite.id]] = w
        self._set_min_objective(objcoefs)

    def _set_min_objective(self, objvars):
        # The coefficients are set on the objective rather than built into an
        # expression: optlang cannot parse the sum of bare variables that
        # `add([1 * var, ...])` collapses to when symengine backs it.
        # `objvars` is {variable: coefficient}, or a list of variables that all
        # get coefficient 1.
        if not isinstance(objvars, dict):
            objvars = {var: 1 for var in objvars}
        self.model.objective = self.model.problem.Objective(
            Zero, direction="min", sloppy=True
        )
        self.model.objective.set_linear_coefficients(objvars)

    def build_concfit_objective_l2(self, target_concentrations, weights=None):
        """Weighted least-squares concentration-fit objective:
        minimize sum_i w_i * (logconc_i - target_i)^2 over the fitted set
        (metabolites present in target_concentrations). Unlike
        build_concfit_objective, this uses no pconcfit/nconcfit slack
        variables — the squared term is expressible directly against the
        logconc variable — so any slacks/constraints left over from a prior
        L1 build for the fitted set are removed first.

        Requires a QP-capable optlang backend (gurobi/cplex); raises
        NotImplementedError early otherwise, since GLPK cannot hold a
        quadratic objective at all.
        """
        weights = weights or {}
        self._require_qp_capable_solver()
        self._validate_concfit_weights(weights)

        # Remove any pre-existing concfit constraints (mirrors build_concfit_objective).
        for metabolite in self.model.metabolites:
            if metabolite.id in self.constraints["concfit"]:
                self.model.remove_cons_vars(self.constraints["concfit"][metabolite.id])
                del self.constraints["concfit"][metabolite.id]

        # Remove any pre-existing pconcfit/nconcfit slack variables for the fitted set —
        # an L2 build after an L1 build must leave no stale slacks behind.
        stale_vars = []
        for metabolite_id in target_concentrations:
            if metabolite_id in self.variables["pconcfit"]:
                stale_vars.append(self.variables["pconcfit"].pop(metabolite_id))
            if metabolite_id in self.variables["nconcfit"]:
                stale_vars.append(self.variables["nconcfit"].pop(metabolite_id))
        if stale_vars:
            self.model.remove_cons_vars(stale_vars)

        objvars = []
        for metabolite in self.model.metabolites:
            if (
                metabolite.id in target_concentrations
                and metabolite.id in self.variables["logconc"]
            ):
                w = weights.get(metabolite.id, 1.0)
                target = target_concentrations[metabolite.id]
                objvars.append(
                    w * (self.variables["logconc"][metabolite.id] - target) ** 2
                )
        self.model.objective = self.model.problem.Objective(
            add(objvars), direction="min", sloppy=True
        )

    def build_logconc_variable(self, object):
        msid = self.modelutl.metabolite_msid(object)
        if msid == "cpd00001":
            return None
        lb = ln(self.parameters["default_min_conc"])
        ub = ln(self.parameters["default_max_conc"])
        if object.id in self.parameters["combined_custom_concentrations"]:
            lb = ln(self.parameters["combined_custom_concentrations"][object.id][0])
            ub = ln(self.parameters["combined_custom_concentrations"][object.id][1])
        if msid in self.parameters["combined_custom_concentrations"]:
            lb = ln(self.parameters["combined_custom_concentrations"][msid][0])
            ub = ln(self.parameters["combined_custom_concentrations"][msid][1])
        variable = self.build_variable("logconc", lb, ub, "continuous", object)
        # build_variable returns an earlier build's variable unchanged, so a rebuild with
        # other concentrations would keep the old bounds
        variable.set_bounds(lb, ub)
        return variable

    def build_dgerr_variables(self, object):
        msid = self.modelutl.metabolite_msid(object)
        ub = self.parameters["default_max_error"]
        if self.parameters["use_database_error"]:
            # The database's error for each compound's estimate, converted to kJ/mol.
            # The larger of it and the flat default is taken, so no compound is held
            # tighter than the default and a poorly determined one is not held as
            # tightly as a well determined one. (This was compared and applied in
            # kcal/mol until it was converted, holding every such compound 4.184x too
            # tightly.) eQuilibrator's "no estimate" marker -- an error of 12,482 to
            # 407,722 kcal/mol, e.g. SAM 132.52 +/- 23,901 kcal/mol -- is not an error
            # bound: the loader leaves such compounds without an energy, and
            # database_error ignores errors from NO_ESTIMATE_ERROR up.
            reported = self.database_error(msid)
            if reported is not None:
                ub = max(ub, reported)
        if msid in self.parameters["custom_deltaG_error"]:
            ub = self.parameters["custom_deltaG_error"][msid]
        elif object.id in self.parameters["custom_deltaG_error"]:
            ub = self.parameters["custom_deltaG_error"][object.id]
        # set_bounds: a variable of an earlier build comes back with its old bounds
        self.build_variable("pdgerr", 0, ub, "continuous", object).set_bounds(0, ub)
        self.build_variable("ndgerr", 0, ub, "continuous", object).set_bounds(0, ub)

    def database_error(self, msid):
        """The error the database reports for a compound's formation energy.

        The database only widens the default error bound here, and the energies may all
        come from notes['deltag'], so a database that cannot be read is not fatal: the
        first failure logs one warning, and this returns None (the default bound) for
        every compound until the next build_package tries again."""
        if msid is None or getattr(self, "_database_unavailable", False):
            return None
        from modelseedpy.biochem.modelseed_biochem import ModelSEEDBiochem

        try:
            if self.parameters["modelseed_db_path"] is not None:
                biochem_db = ModelSEEDBiochem.get(
                    path=self.parameters["modelseed_db_path"]
                )
            else:
                biochem_db = ModelSEEDBiochem.get()
        except OSError as ex:
            self._database_unavailable = True
            logger.warning(
                f"FullThermoPkg: cannot load the ModelSEED database ({ex}); the error "
                f"bounds use default_max_error ({self.parameters['default_max_error']} "
                f"kJ/mol) without the database's own estimates. Set "
                f"use_database_error=False to skip the database."
            )
            return None
        if msid not in biochem_db.compounds:
            return None
        error = getattr(biochem_db.compounds.get_by_id(msid), "delta_g_error", None)
        if error is None or abs(error) >= NO_ESTIMATE_ERROR:
            return None
        return abs(error) * KCAL_TO_KJ  # kcal/mol in the database, kJ/mol here

    def build_concfit_variables(self, object):
        self.build_variable("pconcfit", 0, 100, "continuous", object)
        self.build_variable("nconcfit", 0, 100, "continuous", object)

    def build_gibbs_constraint(self, object):
        msid = self.modelutl.metabolite_msid(object)
        # An earlier build's row goes first: a compound left free this time (no energy, or
        # beyond max_potential) must not stay pinned by it
        if object.id in self.constraints["potc"]:
            self.model.remove_cons_vars(self.constraints["potc"].pop(object.id))

        # potential(i) (kJ/mol) = deltaG(i) (kJ/mol) + R*T(K)*lnconc(i)
        #                         + charge(i) * Faraday(kC/mol) * compartment_potential(mV) / 1000
        # compartment_potential is in mV throughout (build_package default: e0=0 mV, c0=-160 mV).
        # Dividing by 1000 converts mV -> V so that kC/mol * V = kJ/mol.
        if (
            object.id
            not in self.pkgmgr.getpkg("SimpleThermoPkg").variables["potential"]
        ):
            return None

        pos_deltagerr_variable = self.variables["pdgerr"][object.id]
        neg_deltagerr_variable = self.variables["ndgerr"][object.id]
        potential_variable = self.pkgmgr.getpkg("SimpleThermoPkg").variables[
            "potential"
        ][object.id]

        # First check if compound has a deltaG value in the model
        deltag = None
        if object.notes and "deltag" in object.notes:
            deltag = object.notes["deltag"]
        elif msid is not None:
            from modelseedpy.biochem.modelseed_biochem import ModelSEEDBiochem

            if self.parameters["modelseed_db_path"] is not None:
                biochem_db = ModelSEEDBiochem.get(
                    path=self.parameters["modelseed_db_path"]
                )
            else:
                biochem_db = ModelSEEDBiochem.get()
            # a compound the database does not have gets no Gibbs constraint
            mscpd = None
            if msid in biochem_db.compounds:
                mscpd = biochem_db.compounds.get_by_id(msid)
            if mscpd is not None:
                if hasattr(mscpd, "deltag") and mscpd.deltag is not None:
                    deltag = mscpd.deltag
                elif hasattr(mscpd, "delta_g") and mscpd.delta_g is not None:
                    deltag = mscpd.delta_g
        RValue = 0.008314  # kJ/mol/K
        if deltag is not None and abs(deltag) >= UNKNOWN_DELTAG:
            # ModelSEED marks an unknown formation energy with 10000000 rather
            # than a null. Taken literally it puts the compound's potential far
            # outside the bounds of SimpleThermoPkg and the model is infeasible,
            # so it is treated as no data: the potential stays free.
            deltag = None
        if deltag is None:
            return None
        if abs(deltag) * KCAL_TO_KJ >= self.parameters["max_potential"]:
            # e.g. the mycobacterial arabinogalactans, to -15,565 kJ/mol: pinning one outside
            # the potential bounds makes the model infeasible, so it is left free instead
            logger.debug(
                f"FullThermoPkg: {object.id} formation energy {deltag} kcal/mol is "
                f"beyond max_potential; its potential is left free"
            )
            return None
        if msid == "cpd00067":
            # pH-7-transformed energies: add RT ln(1e-7) back for H+ so its concentration term
            # cancels at pH 7. RT is kJ/mol and deltag is still kcal/mol here, hence the division.
            deltag += (
                -1
                * RValue
                * self.parameters["temperature"]
                * np.log(0.0000001)
                / KCAL_TO_KJ
            )
        Faraday = 96.485  # kC/mol
        compartment_potential = 0  # mV
        if object.compartment in self.parameters["compartment_potential"]:
            compartment_potential = self.parameters["compartment_potential"][
                object.compartment
            ]
        # Sanity-check: compartment_potential is expected in mV.
        # Typical biological membrane potentials are well under 300 mV in magnitude.
        # Values above 300 mV are suspicious (possible volts/mV unit slip; e.g. 0.16 V
        # mis-entered as 160 would not trigger this, but -160 mV correctly does not).
        # Values above 1000 mV are egregiously non-physical.
        abs_cp = abs(compartment_potential)
        if abs_cp > 1000:
            logger.warning(
                "compartment_potential for '%s' is %.1f mV, which is egregiously "
                "non-physical (|V| > 1000 mV). Verify units — expected mV.",
                object.compartment,
                compartment_potential,
            )
        elif abs_cp > 300:
            logger.warning(
                "compartment_potential for '%s' is %.1f mV, which is unusually large "
                "(|V| > 300 mV). Typical biological membrane potentials sit well under "
                "300 mV; verify that mV (not V) was supplied.",
                object.compartment,
                compartment_potential,
            )
        # Divide compartment_potential by 1000 to convert mV -> V.
        # Faraday (kC/mol) * V = kJ/mol, matching the kJ/mol scale of deltaG.
        constant = (
            deltag * KCAL_TO_KJ + object.charge * Faraday * compartment_potential / 1000
        )
        coef = {
            potential_variable: 1,
            pos_deltagerr_variable: -1,
            neg_deltagerr_variable: 1,
        }
        if msid != "cpd00001":  # Water concentration should not contribute to potential
            coef[self.variables["logconc"][object.id]] = (
                -1 * RValue * self.parameters["temperature"]
            )
        return self.build_constraint("potc", constant, constant, coef, object)
