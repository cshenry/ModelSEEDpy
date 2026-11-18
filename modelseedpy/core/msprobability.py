# -*- coding: utf-8 -*-
# cobrakbase (megaModel's FBAModel) and MSCommunity (prFBA with several models) are
# optional packages, not in install_requires: each is imported where it is used, so
# that this module imports without them
from cobra.io import write_sbml_model, read_sbml_model
from collections import Counter
from optlang import Objective
from json import load, dump
from os import path, mkdir
from cobra import Model
import re


def add_biomass_objective(megaModel, captured_rxnIDs=None):
    """Sets the objective to the biomass reaction (named "biomass", or "bio1" in its id)
    whose equation is the most frequent. captured_rxnIDs is unused and kept for
    compatibility."""
    biomasses = [
        rxn
        for rxn in megaModel.reactions
        if ("biomass" in rxn.name or "bio1" in rxn.id) and not "EX_" in rxn.id
    ]
    if not biomasses:
        raise ValueError(
            f"{megaModel.id} has no biomass reaction (named 'biomass', or with 'bio1'"
            " in its id) to set as the objective."
        )
    biomass_name_reaction_dic = {rxn.reaction: rxn for rxn in biomasses}
    biomass_rxn_counts = Counter([rxn.reaction for rxn in biomasses])
    max_biomass_freq = max(biomass_rxn_counts.values())
    most_frequent_biomass = dict(
        zip(list(biomass_rxn_counts.values()), list(biomass_rxn_counts.keys()))
    )[max_biomass_freq]
    megaModel.objective = Objective(
        biomass_name_reaction_dic[most_frequent_biomass].flux_expression,
        direction="max",
    )
    megaModel.solver.update()
    return megaModel


class MSProbability:

    # TODO - add the parallelization code with an argument flag
    @staticmethod
    def megaModel(
        clades_paths,
        kbase_api=None,
        reaction_counts_path=None,
        numTotal="numMembers",
        copy_genes=True,
    ):
        from cobrakbase.core.kbasefba.fbamodel import FBAModel

        # compute the reaction frequency of the models in a given clade
        broken_models, megaModels = [], []
        # models_paths = glob(f"{models_path}/*.xml")
        for clade, paths in clades_paths.items():
            if not reaction_counts_path:
                if not path.exists("reaction_counts"):
                    mkdir("reaction_counts")
                reaction_counts = {}
                for index, model_path in enumerate(paths):
                    print(
                        f"{model_path}\tindex {index}\t\t\t\t\t\t\t\t\t\t\t\t", end="\r"
                    )
                    try:
                        model = (
                            read_sbml_model(model_path)
                            if not kbase_api
                            else kbase_api.get_from_ws(model_path)
                        )
                    except Exception as e:
                        print("broken", e, model_path)
                        broken_models.append(model_path)
                        continue
                    # print(f"\n{len(model.reactions)} reactions", )
                    for rxn in model.reactions:
                        if rxn.id in reaction_counts:
                            reaction_counts[rxn.id] += 1
                        else:
                            reaction_counts[rxn.id] = 1
                        # TODO storing a list of the rxn objects will save computational effort in the subsequent step
                reaction_counts.update({numTotal: len(paths) - len(broken_models)})
                reaction_counts.update(
                    {
                        rxnID: (count / reaction_counts[numTotal])
                        for rxnID, count in reaction_counts.items()
                        if rxnID != numTotal
                    }
                )
                with open(f"reaction_counts/{clade}_reactions.json", "w") as jsonOut:
                    dump(reaction_counts, jsonOut, indent=3)
            else:
                try:
                    with open(f"{reaction_counts_path}/{clade}.json", "r") as jsonIn:
                        reaction_counts = load(jsonIn)
                except:
                    print(f"broken model: {clade}")
                    continue

            # constructing the probabilistic clade model
            megaModel = FBAModel(
                {
                    "id": clade,
                    "name": f"MegaModel for {clade} from {reaction_counts[numTotal]} members",
                }
            )
            # megaModel = CobraModelConverter(Model(clade, name=f"MegaModel for {clade} from {reaction_counts[numTotal]} members")).build()
            remaining_rxnIDs = set(list(reaction_counts.keys()))
            captured_reactions, captured_rxnIDs = [], set()

            print("\n", clade)  # , end="\t")
            found_rxn_hash = {}
            for model_path in paths:
                print(f"{model_path}\t\t\t\t\t\t\t\t\t\t\t\t", end="\r")
                try:
                    model = (
                        read_sbml_model(model_path)
                        if not kbase_api
                        else kbase_api.get_from_ws(model_path)
                    )
                except Exception as e:
                    print("broken", e, model_path)
                    broken_models.append(model_path)
                    continue
                for rxn in model.reactions:
                    if rxn.id not in found_rxn_hash:
                        found_rxn_hash[rxn.id] = {"genes": {}, "rxn": rxn}
                        captured_reactions.append(rxn)
                    elif copy_genes:
                        for gene in rxn.genes:
                            if gene.id not in found_rxn_hash[rxn.id]:
                                found_rxn_hash[rxn.id]["genes"][gene.id] = 1
                                if (
                                    len(
                                        found_rxn_hash[rxn.id]["rxn"].gene_reaction_rule
                                    )
                                    > 0
                                ):
                                    found_rxn_hash[rxn.id][
                                        "rxn"
                                    ].gene_reaction_rule += f" or {gene.id}"
                                else:
                                    found_rxn_hash[rxn.id][
                                        "rxn"
                                    ].gene_reaction_rule = gene.id
            if captured_reactions == []:
                print(f"\tNo models for {clade} are defined.")
                continue
            ## add reactions
            megaModel.add_reactions(list(captured_reactions))
            for rxn in megaModel.reactions:
                rxn.notes["probability"] = reaction_counts[rxn.id]
            ## add objective
            megaModel = add_biomass_objective(megaModel)
            ## evaluate the model and export
            missingRxns = (
                set([rxnID for rxnID in reaction_counts])
                - set([rxn.id for rxn in megaModel.reactions])
                - {numTotal}
            )
            if missingRxns != set():
                print("\nmissing reactions: ", missingRxns)
            write_sbml_model(megaModel, clade + ".xml")
            megaModels.append(megaModel)
            print("\tfinished")
        return megaModels if len(clades_paths) > 1 else megaModels[0]

    @staticmethod
    def apply_threshold(model, threshold=0.5):
        for rxn in model.reactions:
            if rxn.notes["probability"] < threshold:
                rxn.lower_bound = rxn.upper_bound = 0
        return model

    # "MS2 - Probabilistic modeling" would create a probabilstic model and optionally an ensemble model from the probabilistic model

    # TODO - develop a separate App from

    # TODO - Construct another code to aggregate functions from all genomes into a single model, where the genes themselves would be mapped with a probability
    ## only count genomes with SSOs
    ## this would accelerate the construction of making a megaModel
    ## specify an ANI cut-off and a closeness to the top-hitting genome
    ## yield two models:  augmented MAG model with only conserved functions and the probabilistic model with all functions
    ## create the KBase module + GitHub repository, after Chris settles on a name

    # TODO - integrate the ensembleFBA modules + repositories

    # TODO - update the CommunityFBA update to run probabilistic models

    @staticmethod
    def prFBA(
        model_s_,
        environment=None,
        abundances=None,
        min_prob=0.01,
        prob_exp=1,
        ex_weight=100,
        commkinetics=None,
        kinetics_coef=1000,
        printLP=False,
        expression=None,
        missing_probability=None,
        biomass_id=None,
        min_growth=1e-6,
    ):
        """Probabilistic FBA: hold the objective at 95% of its maximum, then minimize

            sum_r max(min_prob, 1 - p_r**prob_exp) * |v_r|  +  sum_ex ex_weight * |v_ex|

        over the "rxn"-prefixed reactions r (p_r = float(rxn.notes["probability"])) and the
        "EX_" exchanges, with total carbon uptake capped at 100 (ElementUptakePkg). |v| is
        the forward plus the reverse variable. Other reactions (biomass, ATPM, sinks) have
        coefficient 0.

        Parameters
        ----------
        model_s_ : cobra.Model, or a list of cobra.Model
            One model, bare or as a one-element list, is simulated itself. It is modified
            in place: the medium, the carbon-uptake package, the "min_value" floor and the
            objective are set on it, so pass ``model.copy()`` to keep the original. A second
            call on the same object raises PackageError (ElementUptakePkg is already
            registered). Two or more models are merged with
            mscommunity.commhelper.build_from_species_models; only this path needs the
            MSCommunity package.
        environment : dict, MSMedia or None
            None (default) keeps the model's own exchange bounds. A dict goes through
            MSModelUtil.add_medium: keys are compound ids (mapped to ``EX_<id>_e0``) or,
            when any key contains "EX_", exchange ids; it becomes ``model.medium`` (keys
            without an exchange in the model are dropped), so every uptake not listed is
            closed. An MSMedia also goes through MSModelUtil.add_medium, which gives
            each compound the media's own uptake bound.
        min_prob, prob_exp, ex_weight : float
            The terms of the objective above.
        printLP : bool
            Print the constraint names and write the LP to ./prFBA.lp. Silent otherwise.
        missing_probability : float or None
            The probability used for a "rxn" reaction that carries no notes["probability"].
            None (default) raises KeyError naming those reactions, before the model is
            changed. Reactions added after the probabilities were annotated carry no note:
            gapfilled reactions, for example. Pass 0.0 to weight them like reactions
            without genetic evidence: coefficient max(min_prob, 1 - 0) = 1, the same as a
            reaction annotated with probability 0 (the usual value for a reaction without
            genes when p(reaction) = max over its genes).
        biomass_id : str or None
            The reaction whose maximum sets the 95% floor. None (default) keeps whatever
            objective the model carries on entry, as before. Check it: MSATPCorrection.
            build_tests sets the model's objective to ATP hydrolysis (ATPM_c0), so a model
            built through ATP correction and gapfilling can carry ATPM_c0, and the floor then
            holds ATP maintenance, not growth. Pass the biomass id (e.g. "bio1") then.
        min_growth : float or None
            The smallest maximum of the floored objective that is accepted (default 1e-6).
            Below it the 95% floor is (near) 0 and the weighted minimization returns the
            all-zero flux vector with status "optimal"; an infeasible model would instead
            reach the solver as a NaN bound. Both raise ValueError. By then the medium and
            the carbon-uptake package are already on the model. None disables the check.

        Returns
        -------
        cobra.Solution of the weighted minimization.
        """
        from modelseedpy.core.msmodelutl import MSModelUtil
        from modelseedpy.fbapkg.elementuptakepkg import ElementUptakePkg
        from optlang.symbolics import Zero

        # commkinetics = commkinetics if commkinetics is not None else len(model_s_) > 1
        # one model may be passed bare or as a one-element list; MSModelUtil takes the model
        # itself (a cobra Model has no len(), and the list has no .id)
        if not isinstance(model_s_, (list, tuple)):
            model_s_ = [model_s_]
        if len(model_s_) == 0:
            raise ValueError("prFBA needs at least one model.")
        if len(model_s_) == 1:
            mdlUtil = MSModelUtil(model_s_[0])
        else:
            # community modeling lives in the standalone MSCommunity package, which only
            # this path needs
            from mscommunity.commhelper import build_from_species_models

            mdlUtil = MSModelUtil(
                build_from_species_models(
                    model_s_, abundances=abundances, commkinetics=commkinetics
                )
            )
        # every rxn reaction needs a probability; check before the model is changed
        missing = [
            rxn.id
            for rxn in mdlUtil.model.reactions
            if "rxn" == rxn.id[0:3] and "probability" not in rxn.notes
        ]
        if missing and missing_probability is None:
            raise KeyError(
                f"{len(missing)} rxn reactions of {mdlUtil.model.id} have no "
                f"notes['probability'] (first: {missing[:5]}). Annotate them, or pass "
                f"missing_probability (e.g. 0.0 for reactions without genetic evidence)."
            )
        if biomass_id is not None:
            mdlUtil.model.objective = biomass_id
        # environment=None keeps the model's own exchange bounds, as MSModelUtil(environment=None) does
        if environment is not None:
            mdlUtil.add_medium(environment)
        # constrain carbon consumption and community composition
        elepkg = ElementUptakePkg(mdlUtil.model)
        elepkg.build_package({"C": 100})
        ## the total flux through the members proportional to their relative abundances
        if not commkinetics and len(model_s_) > 1:
            from mscommunity.mscommsim import MSCommunity

            # the MSCommunity constructor installs the community kinetic rows
            MSCommObj = MSCommunity(
                mdlUtil.model, model_s_, kinetic_coeff=kinetics_coef
            )
        # (the carbon constraint is built once, above: a second ElementUptakePkg on the same
        # model raises PackageError "Package with name ElementUptakePkg already in model!")

        # constrain the model to 95% of the optimum growth
        maxBioSol = mdlUtil.model.slim_optimize()
        if min_growth is not None:
            objective = str(mdlUtil.model.objective.expression)[:80]
            if maxBioSol is None or maxBioSol != maxBioSol:  # NaN: no feasible solution
                raise ValueError(
                    f"{mdlUtil.model.id}: the model is infeasible under this "
                    f"medium and the carbon cap (solver status "
                    f"{mdlUtil.model.solver.status}); objective {objective}."
                )
            if maxBioSol < min_growth:
                raise ValueError(
                    f"{mdlUtil.model.id}: the objective's maximum is {maxBioSol:g} "
                    f"(< min_growth {min_growth:g}), so the 95% floor would be "
                    f"~0 and the weighted minimization would return the all-zero "
                    f"flux vector. Pass an environment on which the model grows, or "
                    f"check biomass_id; objective {objective}."
                )
        mdlUtil.add_minimal_objective_cons(maxBioSol * 0.95)

        # weight internal reactions based on their probabilities
        ## minimize:   sum_r^R max(min_prob, 1-probability_r^prob_exp)*flux_r + sum_ex^EX(ex_weight*EX)
        coef = {}
        # TODO experiment with reducing or eliminating the exchange limitation
        for rxn in mdlUtil.model.reactions:
            if "rxn" == rxn.id[0:3]:
                prob = float(rxn.notes.get("probability", missing_probability))
                coef.update(
                    {rxn.forward_variable: max(min_prob, (1 - prob**prob_exp))}
                )
                coef.update(
                    {rxn.reverse_variable: max(min_prob, (1 - prob**prob_exp))}
                )
            elif "EX_" == rxn.id[0:3]:
                coef.update({rxn.forward_variable: ex_weight})
                coef.update({rxn.reverse_variable: ex_weight})
        mdlUtil.add_objective(Zero, "min", coef)

        if printLP:
            print([cons.name for cons in mdlUtil.model.constraints])
            with open("prFBA.lp", "w") as out:
                out.write(str(mdlUtil.model.solver))

        # simulate the probabilistic model with the respective probabilities
        return mdlUtil.model.optimize()

    @staticmethod
    def iterative_simulation(time_iterative_data):
        pass

    def expressionData(data):
        # iterate over the reactions, genes, and keep the highest expression score
        # turn off reactions that are below a threshold, ensure that the growth is unchanged, otherwise restore the reaction.
        pass
