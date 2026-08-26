from cobrakbase.core.kbasefba.fbamodel_from_cobra import CobraModelConverter
# from modelseedpy.fbapkg.mspackagemanager import MSPackageManager
from mscommunity import MSCommunity
from cobrakbase.core.kbasefba.fbamodel import FBAModel
from cobra.io import write_sbml_model, read_sbml_model
from collections import Counter
from optlang import Objective
from json import load, dump
from os import path, mkdir
from cobra import Model
import re

# def add_biomass_objective(megaModel, captured_rxnIDs):
#     if "bio1" in captured_rxnIDs:
#         megaModel.objective = Objective(megaModel.reactions.bio1.flux_expression, direction="max")
#     else:
#         # select the most conserved biomass composition
#         for rxn in megaModel.reactions:
#             if "biomass" and not "EX_" in rxn.id:   # randomly the first biomass reaction is pulled from the ASV set
#                 megaModel.objective = Objective(rxn.flux_expression, direction="max")
#                 break
#     megaModel.solver.update()
#     return megaModel

def add_biomass_objective(megaModel):#, captured_rxnIDs):
    # if "bio1" in captured_rxnIDs:
    #     megaModel.objective = Objective(megaModel.reactions.bio1.flux_expression, direction="max")
    # else:
    biomasses = [rxn for rxn in megaModel.reactions if ("biomass" in rxn.name or "bio1" in rxn.id) and not "EX_" in rxn.id]
    # print("\n", [rxn.reaction for rxn in biomasses])
    biomass_name_reaction_dic = {rxn.reaction:rxn for rxn in biomasses}
    biomass_rxn_counts = Counter([rxn.reaction for rxn in biomasses])
    max_biomass_freq = max(biomass_rxn_counts.values())
    most_frequent_biomass = dict(zip(list(biomass_rxn_counts.values()), list(biomass_rxn_counts.keys())))[max_biomass_freq]
    # print("\n", most_frequent_biomass)
    megaModel.objective = Objective(biomass_name_reaction_dic[most_frequent_biomass].flux_expression, direction="max")
    megaModel.solver.update()
    return megaModel


class MSProbability:
        
    # TODO - add the parallelization code with an argument flag
    @staticmethod
    def megaModel(clades_paths, kbase_api=None, reaction_counts_path=None, numTotal="numMembers"):
        # compute the reaction frequency of the models in a given clade
        broken_models, megaModels = [], []
        # models_paths = glob(f"{models_path}/*.xml")
        for clade, paths in clades_paths.items():
            if not reaction_counts_path:
                if not path.exists("reaction_counts"):  mkdir("reaction_counts")
                reaction_counts = {}
                for index, model_path in enumerate(paths):
                    print(f"{model_path}\tindex {index}\t\t\t\t\t\t\t\t\t\t\t\t", end="\r")
                    try:  model = read_sbml_model(model_path) if not kbase_api else kbase_api.get_from_ws(model_path)
                    except Exception as e:
                            print("broken", e, model_path)
                            broken_models.append(model_path)
                            continue
                    # print(f"\n{len(model.reactions)} reactions", )
                    for rxn in model.reactions:
                        if rxn.id in reaction_counts:  reaction_counts[rxn.id] += 1
                        else:  reaction_counts[rxn.id] = 1
                        # TODO storing a list of the rxn objects will save computational effort in the subsequent step
                reaction_counts.update({numTotal: len(paths)-len(broken_models)})
                reaction_counts.update({rxnID:(count/reaction_counts[numTotal]) for rxnID,count in reaction_counts.items() if rxnID != numTotal})
                with open(f"reaction_counts/{clade}_reactions.json", "w") as jsonOut:   dump(reaction_counts, jsonOut, indent=3)
            else:
                try:
                    with open(f"{reaction_counts_path}/{clade}.json", "r") as jsonIn:   reaction_counts = load(jsonIn)
                except:  print(f"broken model: {clade}")  ;  continue

            # constructing the probabilistic clade model
            megaModel = FBAModel({"id":clade, "name":f"MegaModel for {clade} from {reaction_counts[numTotal]} members"})
            # megaModel = CobraModelConverter(Model(clade, name=f"MegaModel for {clade} from {reaction_counts[numTotal]} members")).build()
            remaining_rxnIDs = set(list(reaction_counts.keys()))
            captured_reactions, captured_rxnIDs = [], set()
            print("\n", clade)#, end="\t")
            for model_path in paths:
                print(f"{model_path}\t\t\t\t\t\t\t\t\t\t\t\t", end="\r")
                try:   model = read_sbml_model(model_path) if not kbase_api else kbase_api.get_from_ws(model_path)
                except Exception as e:
                    print("broken", e, model_path)
                    broken_models.append(model_path)
                    continue
                # captured_reactions.extend([rxn for rxn in model.reactions if rxn.id not in captured_rxnIDs])
                # captured_rxnIDs.update([rxn.id for rxn in model.reactions])
                # remaining_rxnIDs -= captured_rxnIDs
                # if remaining_rxnIDs == set():   break
            # if captured_reactions == []:    print(f"\tNo models for {clade} are defined.")  ;  continue
                for rxn in model.reactions:
                    if rxn.id not in found_rxn_hash:
                        found_rxn_hash[rxn.id] = {"genes":{},"rxn":rxn}
                        captured_reactions.append(rxn)
                    elif copy_genes:
                        for gene in rxn.genes:
                            if gene.id not in found_rxn_hash[rxn.id]:
                                found_rxn_hash[rxn.id]["genes"][gene.id] = 1
                                if len(found_rxn_hash[rxn.id]["rxn"].gene_reaction_rule) > 0:
                                    found_rxn_hash[rxn.id]["rxn"].gene_reaction_rule += f" or {gene.id}"
                                else:
                                    found_rxn_hash[rxn.id]["rxn"].gene_reaction_rule = gene.id
            if captured_reactions == []:
                print(f"\tNo models for {clade} are defined.")
                continue
            ## add reactions
            megaModel.add_reactions(list(captured_reactions))
            for rxn in megaModel.reactions:
                rxn.notes["probability"] = reaction_counts[rxn.id]
            ## add objective
            megaModel = add_biomass_objective(megaModel)#, captured_rxnIDs)
            ## evaluate the model and export
            missingRxns = set([rxnID for rxnID in reaction_counts]) - set([rxn.id for rxn in megaModel.reactions]) - {numTotal}
            if missingRxns != set():  print("\nmissing reactions: ", missingRxns)
            export_name = path.join(reaction_counts_path, f"{clade}.xml")  # if re.search(f"[0-9]+\/[0-9]+\/[0-9]+", model_path) else f"{path.join(path.dirname(model_path), clade)}.xml"
            write_sbml_model(megaModel, export_name)
            megaModels.append(megaModel)
            print("\tfinished")
        return megaModels if len(clades_paths) > 1 else megaModels[0]

    @staticmethod
    def megaModel_parallel():
        from multiprocess import Pool
        pool = Pool(24)
        args = [(asv, [model_gcf_mapping[k] for k in set(set(gcfs) - broken_models)]) for asv, gcfs in unique_asv_mappings.items()]
        print(args[0])
        pool.map(rxnFreq, args)

    @staticmethod
    def apply_threshold(model, threshold=0.5):
        for rxn in model.reactions:
            if rxn.notes["probability"] < threshold:   rxn.lower_bound = rxn.upper_bound = 0
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
    def prFBA(model_s_, environment=None, abundances=None, min_prob=0.01, prob_exp=1, ex_weight=100,
              commkinetics=None, kinetics_coef=1000, printLP=False, expression=None):
        from modelseedpy.community.commhelper import build_from_species_models
        from modelseedpy.core.msmodelutl import MSModelUtil
        from modelseedpy.fbapkg.elementuptakepkg import ElementUptakePkg
        from optlang.symbolics import Zero

        # commkinetics = commkinetics if commkinetics is not None else len(model_s_) > 1
        mdlUtil = MSModelUtil(model_s_ if len(model_s_) == 1 else build_from_species_models(model_s_, abundances=abundances, commkinetics=commkinetics))
        mdlUtil.add_medium(environment)
        # constrain carbon consumption and community composition
        elepkg = ElementUptakePkg(mdlUtil.model)  ;  elepkg.build_package({"C": 100})
        ## the total flux through the members proportional to their relative abundances
        if not commkinetics and len(model_s_) > 1:
            # pkgmgr = MSPackageManager.get_pkg_mgr(mdlUtil.model)
            MSCommObj = MSCommunity(mdlUtil.model, model_s_)
            # pkgmgr.getpkg("CommKineticPkg").build_package(kinetics_coef, MSCommObj)
        # constrain carbon consumption
        elepkg = ElementUptakePkg(mdlUtil.model)  ;  elepkg.build_package({"C": 100})
        # evaluate the metabolomics data over time

        # constrain the model to 95% of the optimum growth
        maxBioSol = mdlUtil.model.slim_optimize()
        mdlUtil.add_minimal_objective_cons(maxBioSol*.95)

        # weight internal reactions based on their probabilities
        ## minimize:   sum_r^R ((1-probabilities^prob_exp_r)*flux_r + min_prob) + sum_ex^EX(ex_weight*EX)
        coef = {}
        # TODO experiment with reducing or eliminating the exchange limitation
        for rxn in mdlUtil.model.reactions:
            if "rxn" == rxn.id[0:3]:
                coef.update({rxn.forward_variable: max(min_prob, (1-float(rxn.notes["probability"])**prob_exp))})
                coef.update({rxn.reverse_variable: max(min_prob, (1-float(rxn.notes["probability"])**prob_exp))})
            elif "EX_" == rxn.id[0:3]:
                coef.update({rxn.forward_variable: ex_weight})
                coef.update({rxn.reverse_variable: ex_weight})
        mdlUtil.add_objective(Zero, "min", coef)

        print([cons.name for cons in mdlUtil.model.constraints])

        if printLP:
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
