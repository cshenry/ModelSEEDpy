from modelseedpy.core.optlanghelper import (
    OptlangHelper,
    Bounds,
    tupVariable,
    tupConstraint,
    tupObjective,
)
from modelseedpy.core.exceptions import FeasibilityError, ObjectAlreadyDefinedError
from modelseedpy.biochem import from_local
from collections import Counter
from time import process_time
from json import dump
import re


def counted_components(*ele_dics):
    ele_dic = {}
    for dic in ele_dics:
        # print(dic, ele_dics)
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


def _check_names(name, names):
    if name in names:
        raise ObjectAlreadyDefinedError(f"The {name} is already defined in the model.")
    names.append(name)
    return name


def combined_dic(dic):
    new_dic = {}
    for k, v in dic.items():
        k = re.sub(r"(\_\d+$)", "", k)
        if k not in new_dic:
            new_dic[k] = v
        else:
            new_dic[k] += v
    return new_dic


def optimized_reactions(msdb, met_freq, met_freq_threshold=10):
    # TODO select all reactions that contain a given metabolite,
    ##  either by updating the API to accept the attribute or through a custom function
    # reactions with undefined metabolites or metabolites that are in fewer than met_freq_threshold reactions
    rxns_to_optimize = set(
        [
            rxn
            for met in msdb.compound_tokens
            for rxn in met.reactions
            if met.elements == {}
            or (met.id in met_freq and met_freq[met.id] < met_freq_threshold)
        ]
    )  # [rxn for rxn in msdb.reactions if any([
    # reaction that are empty, mass imbalanced, or charge imbalanced
    rxns_to_optimize.update(
        [
            rxn
            for rxn in msdb.reactions
            if any(["MI" in rxn.status, "CI" in rxn.status, len(rxn.metabolites) == 0])
        ]
    )
    return rxns_to_optimize


def justifyDB(
    msdb_path: str,
    changes_path: str = "MSDB_corrections.json",
    mets_frequency_threshold=10,
):
    msdb = from_local(msdb_path)

    db_element_counts = counted_components(
        *[
            (met.elements, rxn.metabolites[met])
            for rxn in msdb.reactions
            for met in rxn.metabolites
        ]
    )
    stoich_vars, charge_vars, stoich_error, charge_error, protstoich = (
        {},
        {},
        {},
        {},
        {},
    )
    stoich_diff_pos, stoich_diff_neg, charge_diff_pos, charge_diff_neg = {}, {}, {}, {}
    stoich_constraints, charge_constraints = {}, {}
    variables, constraints, names = [], [], []
    objective = tupObjective("database_correction", [], "min")
    time1 = process_time()
    print("Defining variables and objective", end="\t")
    mets_frequency = combined_dic(
        counted_components(*[rxn.metabolites for rxn in msdb.reactions])
    )
    reactions_to_examine = optimized_reactions(
        msdb, mets_frequency, mets_frequency_threshold
    )
    mets_to_vary, mets_added = [], []
    for rxn in reactions_to_examine:
        for met in rxn.metabolites:
            metID = re.sub(r"(\_\d+$)", "", met.id)
            if metID not in mets_added:
                mets_to_vary.append(met)
                mets_added.append(metID)
    # print(mets_frequency)
    if "cpd00067" in mets_to_vary:
        mets_to_vary.remove("cpd00067")
    for met in mets_to_vary:
        metID = re.sub(r"(\_\d+$)", "", met.id)
        met_freq = mets_frequency[metID]
        # if met_freq > mets_frequency_threshold:  continue
        # mass balance
        stoich_diff_pos[metID], stoich_diff_neg[metID], stoich_error[metID] = {}, {}, {}
        met_elements = (
            met.elements if met.elements != {} else list(db_element_counts.keys())
        )
        for ele in met_elements:
            stoich_diff_pos[metID][ele] = tupVariable(f"{metID}~{ele}_diffpos")
            stoich_diff_neg[metID][ele] = tupVariable(f"{metID}~{ele}_diffneg")
            stoich_error[metID][ele] = tupVariable(f"{metID}~{ele}_error")
            objective.expr.extend(
                [
                    {
                        "elements": [
                            {
                                "elements": [
                                    stoich_diff_pos[metID][ele].name,
                                    met_freq,
                                ],
                                "operation": "Mul",
                            },
                            {
                                "elements": [
                                    stoich_diff_neg[metID][ele].name,
                                    met_freq,
                                ],
                                "operation": "Mul",
                            },
                        ],
                        "operation": "Add",
                    }
                ]
            )
        # charge balance
        charge_diff_pos[metID] = tupVariable(f"{metID}~charge_diffpos")
        charge_diff_neg[metID] = tupVariable(f"{metID}~charge_diffneg")
        charge_error[metID] = tupVariable(f"{metID}~charge_error")
        # define the objective expression and store the variables
        objective.expr.extend(
            [
                {
                    "elements": [
                        {
                            "elements": [charge_diff_pos[metID].name, met_freq],
                            "operation": "Mul",
                        },
                        {
                            "elements": [charge_diff_neg[metID].name, met_freq],
                            "operation": "Mul",
                        },
                    ],
                    "operation": "Add",
                }
            ]
        )
        variables.extend(
            [
                *stoich_diff_pos[metID].values(),
                *stoich_diff_neg[metID].values(),
                *stoich_error[metID].values(),
                charge_diff_pos[metID],
                charge_diff_neg[metID],
                charge_error[metID],
            ]
        )
    time2 = process_time()
    print(f"Done after {(time2-time1)/60} minutes")
    print("Defining constraints", end="\t")
    # print(len(constraints))
    empty_reactions = []
    proton_met = msdb.compounds.get_by_id("cpd00067")
    for rxn in reactions_to_examine:
        rxn_element_counts = counted_components(
            *[(met.elements, rxn.metabolites[met]) for met in rxn.metabolites]
        )
        if proton_met in rxn.metabolites:
            rxn.subtract_metabolites({proton_met: rxn.metabolites[proton_met]})
        if rxn_element_counts == {}:
            empty_reactions.append(rxn.id)
        protstoich[rxn.id] = tupVariable(f"{rxn.id}~protstoich")
        variables.append(protstoich[rxn.id])
        # sum_m^M( (-diffpos_{m} + diffneg_{m}) * n_{met,rxn} ) = sum_m^M( charge_{m} * n_{met,rxn} ) , per reaction rxn
        charge_constraints[rxn.id] = tupConstraint(
            name=f"{rxn.id}_charge",
            expr={
                "elements": [
                    protstoich[rxn.id].name,
                    sum(
                        [
                            (
                                met.charge * rxn.metabolites[met]
                                if hasattr(met, "charge")
                                else 0
                            )
                            for met in rxn.metabolites
                        ]
                    ),
                ],
                "operation": "Add",
            },
        )
        for met in rxn.metabolites:
            metID = re.sub(r"(\_\d+$)", "", met.id)
            if metID == "cpd00067":
                continue
            charge_constraints[rxn.id].expr["elements"].extend(
                [
                    {
                        "elements": [
                            charge_diff_pos[metID].name,
                            -rxn.metabolites[met],
                        ],
                        "operation": "Mul",
                    },
                    {
                        "elements": [charge_diff_neg[metID].name, rxn.metabolites[met]],
                        "operation": "Mul",
                    },
                    charge_error[metID].name,
                ]
            )
        # sum_{m,e}^{M,E}( (-diffpos_{m,e} + diffneg_{m,e}) * n_{met,rxn} )
        ##  = {m,e}^{M,E}( stoich_{m,e} * n_{met,rxn} ) , per reaction rxn
        stoich_constraints[rxn.id] = {}
        # TODO the reaction elemental count is based on the presence of protons, so the protstoich
        ## value will just fill the vacancy when the cpd00067 variable is removed and offer no new information
        for ele, count in rxn_element_counts.items():
            stoich_constraints[rxn.id][ele] = tupConstraint(
                name=f"{rxn.id}_{ele}",
                expr={
                    "elements": [
                        protstoich[rxn.id].name,
                        sum(
                            [
                                (
                                    met.elements[ele] * rxn.metabolites[met]
                                    if hasattr(met, "elements") and ele in met.elements
                                    else 0
                                )
                                for met in rxn.metabolites
                            ]
                        ),
                    ],
                    "operation": "Add",
                },
            )
            for met in rxn.metabolites:
                if ele not in met.elements:
                    continue
                metID = re.sub(r"(\_\d+$)", "", met.id)
                if metID == "cpd00067":
                    continue
                stoich_constraints[rxn.id][ele].expr["elements"].extend(
                    [
                        {
                            "elements": [
                                stoich_diff_pos[metID][ele].name,
                                -rxn.metabolites[met],
                            ],
                            "operation": "Mul",
                        },
                        {
                            "elements": [
                                stoich_diff_neg[metID][ele].name,
                                rxn.metabolites[met],
                            ],
                            "operation": "Mul",
                        },
                        stoich_error[metID][ele].name,
                    ]
                )
        constraints.extend(
            [*stoich_constraints[rxn.id].values(), charge_constraints[rxn.id]]
        )
    if empty_reactions:
        print(
            f"The {empty_reactions} reactions lack any metabolites with "
            f"defined formula, and thus are not constrained.",
            end="\t",
        )
    time3 = process_time()
    print(f"Done after {(time3-time2)/60} minutes")

    # construct the model
    print("Constructing the model", end="\t")
    print(
        list(
            map(
                len,
                [
                    variables,
                    constraints,
                    stoich_constraints,
                    charge_constraints,
                    objective.expr,
                ],
            )
        ),
        end="\t",
    )
    optlang_model = OptlangHelper.define_model(
        "Correct_MSDB", variables, constraints, objective, True
    )
    with open("Correct_MSDB.lp", "w") as lp:
        lp.write(optlang_model.to_lp())
    with open("Correct_MSDB.json", "w") as jsonOut:
        dump(optlang_model.to_json(), jsonOut, indent=3)
    print(f"Done after {(process_time()-time3)/60} minutes")

    # acquire the optimized minimum from the model
    print("Starting optimization.", end="\t")
    before = process_time()
    solution = optlang_model.optimize()
    after = process_time()
    print(f"Done after \t{(after-before)/60} minutes")
    if solution != "optimal":
        FeasibilityError(f"The optimization is {solution}.")
    return optlang_model
    print("Exporting primals", end="\t")
    # export the changes
    if changes_path is not None:
        # evaluate proposed changes from the optimization
        proposed_changes, undefined = {}, {}
        for varName, val in optlang_model.primal_values.items():
            if "_" in varName:
                content, diffName = varName.split("_")
            elif "cpd" not in varName and not isclose(float(val), 0, abs_tol=1e-6):
                proposed_changes[varName] = val
                continue
            metID, context = content.split("~")
            met = msdb.compounds.get_by_id(metID)
            missing_formula = False
            if context == "charge":
                original_val = met.charge
            elif context in met.elements:
                original_val = met.elements[context]
            elif context not in met.elements:
                missing_formula = True
                original_val = None
                if metID not in undefined:
                    undefined[metID] = [context]
                else:
                    undefined[metID].append(context)
            if val != 0 or missing_formula:
                val = -val if "neg" in diffName else val
                if metID not in proposed_changes:
                    proposed_changes[metID] = {}
                if context in proposed_changes[metID]:
                    proposed_changes[metID][context]["proposed"] += val
                else:
                    proposed_changes[metID][context] = {
                        "original": original_val,
                        "proposed": (
                            val + original_val if original_val is not None else val
                        ),
                    }
        # export the proposed changes
        print(
            f"The {list(undefined.keys())} metabolites are mis-categorized with the {list(undefined.values())} "
            f"elements, or possibly the formula and < elements > metabolite attribute are not defined."
        )
        with open(changes_path, "w") as out:
            dump(proposed_changes, out, indent=3)
        print(f"Done after {(process_time()-after)/60} minutes")
        return optlang_model, proposed_changes
    print(f"Done after {(process_time()-after)/60} minutes")
    return optlang_model


# if __name__ == "__main__":
#     # accept the command-line arguments
#     from argparse import ArgumentParser
#     from pathlib import Path
#
#     parser = ArgumentParser()
#     parser.add_argument("--msdb_path", type=Path, default=".")
#     parser.add_argument("--changes_path", type=Path, default="MSDB_corrections.json")
#     args = parser.parse_args()
#     justifyDB(args.msdb_path, args.changes_path)
