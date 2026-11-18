# -*- coding: utf-8 -*-
"""Propose corrections to the formulas and charges of ModelSEED compounds.

``justifyDB`` builds a linear program over the database reactions that are
mass or charge imbalanced, that have no metabolites, or that involve a
compound without a formula or used in fewer than ``mets_frequency_threshold``
reactions. For every compound in those reactions, each element count and the
charge get a pair of non-negative variables, ``<cpd>~<element>_diffpos`` and
``<cpd>~<element>_diffneg``, so that the corrected value is
``original + diffpos - diffneg``. The protons (cpd00067) of each reaction are
replaced by a free variable ``<rxn>~protstoich``, the reaction's net proton
coefficient, which enters its hydrogen and charge balances. Every examined
reaction must balance in every element and in charge, and the objective
minimises the total change, each compound's changes weighted by how often the
compound occurs in the database, so that widely used compounds are the last to
change.

Compounds without a formula get only charge variables: their formulas are not
proposed.
"""
import logging
import os
import re
from json import dump
from math import isclose

from modelseedpy.core.exceptions import FeasibilityError
from modelseedpy.core.optlanghelper import (
    OptlangHelper,
    Bounds,
    tupVariable,
    tupConstraint,
    tupObjective,
)

logger = logging.getLogger(__name__)

PROTON = "cpd00067"
_COMPARTMENT_INDEX = re.compile(r"(\_\d+$)")


def _base_id(met_id):
    """cpd00001_0 -> cpd00001"""
    return _COMPARTMENT_INDEX.sub("", met_id)


def _elements(met):
    """A compound's element counts; {} when its formula is missing or, as for
    formulas with parentheses, cobra cannot parse it."""
    return met.elements or {}


def counted_components(*ele_dics):
    ele_dic = {}
    for dic in ele_dics:
        coef = 1
        if isinstance(dic, tuple):
            dic, coef = dic
        for ele, count in dic.items():
            if not isinstance(ele, str):
                ele = ele.id
            if ele in ele_dic:
                ele_dic[ele] += abs(count) * coef
            else:
                ele_dic[ele] = abs(count) * coef
    return dict(sorted(ele_dic.items(), key=lambda x: x[1], reverse=True))


def combined_dic(dic):
    new_dic = {}
    for k, v in dic.items():
        k = _base_id(k)
        if k not in new_dic:
            new_dic[k] = v
        else:
            new_dic[k] += v
    return new_dic


def optimized_reactions(msdb, met_freq, met_freq_threshold=10):
    """The reactions the correction LP examines, sorted by ID: those with a
    formula-less compound or a compound in fewer than ``met_freq_threshold``
    reactions (``met_freq`` is keyed by compound ID), and those that are
    mass imbalanced (MI), charge imbalanced (CI) or empty."""
    rxns_to_optimize = set(
        rxn
        for met in msdb.compound_tokens
        for rxn in met.reactions
        if _elements(met) == {}
        or met_freq.get(_base_id(met.id), 0) < met_freq_threshold
    )
    rxns_to_optimize.update(
        rxn
        for rxn in msdb.reactions
        if "MI" in (rxn.status or "")
        or "CI" in (rxn.status or "")
        or len(rxn.metabolites) == 0
    )
    return sorted(rxns_to_optimize, key=lambda rxn: rxn.id)


def _difference_terms(pos_name, neg_name, coef):
    return [
        {"elements": [pos_name, coef], "operation": "Mul"},
        {"elements": [neg_name, -coef], "operation": "Mul"},
    ]


def build_correction_model(msdb, mets_frequency_threshold=10):
    """The optlang LP that ``justifyDB`` solves, built from a loaded
    ModelSEED database without changing it."""
    mets_frequency = combined_dic(
        counted_components(*[rxn.metabolites for rxn in msdb.reactions])
    )
    reactions = optimized_reactions(msdb, mets_frequency, mets_frequency_threshold)

    # one set of difference variables per compound, shared by its compartments
    mets_to_vary = {}
    for rxn in reactions:
        for met in rxn.metabolites:
            metID = _base_id(met.id)
            if metID != PROTON and metID not in mets_to_vary:
                mets_to_vary[metID] = met
    variables, objective = [], tupObjective("database_correction", [], "min")
    formulaless = []
    for metID, met in mets_to_vary.items():
        if _elements(met) == {}:
            formulaless.append(metID)
        for prop in [*_elements(met), "charge"]:
            pos, neg = f"{metID}~{prop}_diffpos", f"{metID}~{prop}_diffneg"
            variables.extend([tupVariable(pos), tupVariable(neg)])
            weight = mets_frequency[metID]
            objective.expr.append(
                {
                    "elements": [
                        {"elements": [pos, weight], "operation": "Mul"},
                        {"elements": [neg, weight], "operation": "Mul"},
                    ],
                    "operation": "Add",
                }
            )
    if formulaless:
        logger.info(
            "%d compounds have no formula and get only charge variables: %s",
            len(formulaless),
            formulaless,
        )

    constraints, empty_reactions = [], []
    for rxn in reactions:
        stoich = {
            met: coef
            for met, coef in rxn.metabolites.items()
            if _base_id(met.id) != PROTON
        }
        protstoich = f"{rxn.id}~protstoich"
        variables.append(tupVariable(protstoich, Bounds(-1000, 1000)))
        # every reaction balances hydrogen, so that protons cannot stand in
        # for a charge imbalance in a reaction without hydrogen
        elements = sorted(set(ele for met in stoich for ele in _elements(met)) | {"H"})
        if all(_elements(met) == {} for met in stoich):
            empty_reactions.append(rxn.id)
        for prop in [*elements, "charge"]:
            # sum_m( (original_m + diffpos_m - diffneg_m) * n_m ) [+ protstoich] = 0
            expr = {"elements": [], "operation": "Add"}
            if prop in ("H", "charge"):
                expr["elements"].append(protstoich)
            for met, coef in stoich.items():
                if prop == "charge":
                    original = met.charge or 0
                elif prop in _elements(met):
                    original = _elements(met)[prop]
                else:
                    continue
                metID = _base_id(met.id)
                expr["elements"].append(original * coef)
                expr["elements"].extend(
                    _difference_terms(
                        f"{metID}~{prop}_diffpos", f"{metID}~{prop}_diffneg", coef
                    )
                )
            constraints.append(tupConstraint(f"{rxn.id}_{prop}", Bounds(0, 0), expr))
    if empty_reactions:
        logger.info(
            "The %s reactions lack any metabolites with a defined formula, "
            "and thus only their charges and protons are constrained.",
            empty_reactions,
        )
    logger.info(
        "%d variables and %d constraints over %d reactions",
        len(variables),
        len(constraints),
        len(reactions),
    )
    return OptlangHelper.define_model(
        "Correct_MSDB", variables, constraints, objective, True
    )


def proposed_changes_from(optlang_model, msdb, tolerance=1e-6):
    """``{compound ID: {element or "charge": {"original", "proposed"}}}`` from
    the difference variables of a solved model, plus
    ``{reaction ID: {"protons": {"original", "proposed"}}}`` for the reactions
    whose net proton coefficient changed."""
    differences = {}
    proposed_changes = {}
    for name, value in optlang_model.primal_values.items():
        entity, variable = name.split("~", 1)
        if variable == "protstoich":
            rxn = msdb.reactions.get_by_id(entity)
            original = sum(
                coef
                for met, coef in rxn.metabolites.items()
                if _base_id(met.id) == PROTON
            )
            if not isclose(value, original, abs_tol=tolerance):
                proposed_changes[entity] = {
                    "protons": {"original": original, "proposed": value}
                }
            continue
        if isclose(value, 0, abs_tol=tolerance):
            continue
        prop, direction = variable.rsplit("_", 1)
        sign = 1 if direction == "diffpos" else -1
        differences.setdefault(entity, {}).setdefault(prop, 0)
        differences[entity][prop] += sign * value
    for metID, props in differences.items():
        met = msdb.compounds.get_by_id(metID)
        for prop, difference in props.items():
            if isclose(difference, 0, abs_tol=tolerance):
                continue
            original = (met.charge or 0) if prop == "charge" else _elements(met)[prop]
            proposed_changes.setdefault(metID, {})[prop] = {
                "original": original,
                "proposed": original + difference,
            }
    return proposed_changes


def justifyDB(
    msdb_path,
    changes_path: str = None,
    mets_frequency_threshold=10,
    model_path: str = None,
):
    """Solve the database correction LP and return the changes it proposes.

    Parameters
    ----------
    msdb_path : str or ModelSEEDDatabase
        A ModelSEEDDatabase checkout, as ``from_local`` takes, or a database
        that is already loaded.
    changes_path : str, optional
        Where to write the proposed changes as JSON; None writes nothing.
    mets_frequency_threshold : int
        Reactions with a compound in fewer than this many reactions are
        examined (see ``optimized_reactions``).
    model_path : str, optional
        Where to write the LP, e.g. ``"Correct_MSDB.lp"``; the optlang JSON of
        the model is written beside it with a ``.json`` suffix. None writes
        neither.

    Returns
    -------
    (optlang.Model, dict)
        The solved model and the proposed changes (see ``proposed_changes_from``).

    Raises
    ------
    FeasibilityError
        If the LP is not solved to optimality.
    """
    if isinstance(msdb_path, (str, os.PathLike)):
        from modelseedpy.biochem.modelseed_biochem import from_local

        msdb = from_local(msdb_path)
    else:
        msdb = msdb_path
    optlang_model = build_correction_model(msdb, mets_frequency_threshold)

    if model_path is not None:
        directory = os.path.dirname(os.path.abspath(model_path))
        os.makedirs(directory, exist_ok=True)
        if hasattr(optlang_model, "to_lp"):
            with open(model_path, "w") as lp:
                lp.write(optlang_model.to_lp())
        else:
            logger.warning(
                "The %s solver interface cannot write LP files; only the JSON "
                "is exported.",
                optlang_model.interface.__name__,
            )
        with open(os.path.splitext(model_path)[0] + ".json", "w") as jsonOut:
            dump(optlang_model.to_json(), jsonOut, indent=3)

    status = optlang_model.optimize()
    if status != "optimal":
        raise FeasibilityError(f"The database correction LP is {status}.")
    proposed_changes = proposed_changes_from(optlang_model, msdb)
    if changes_path is not None:
        with open(changes_path, "w") as out:
            dump(proposed_changes, out, indent=3)
    return optlang_model, proposed_changes
