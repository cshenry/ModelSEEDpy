import os

from modelseedpy.community.mscompatibility import MSCompatibility
from modelseedpy.core.msminimalmedia import MSMinimalMedia
from modelseedpy.community.commhelper import build_from_species_models
from modelseedpy.community.mscommunity import MSCommunity
from modelseedpy.core.fbahelper import FBAHelper
from modelseedpy.core.msgapfill import MSGapfill
from itertools import combinations, permutations, chain
from optlang import Variable, Constraint, Objective
from modelseedpy.core.exceptions import ObjectiveError, ParameterError
from numpy import array, unique, ndarray, where, sort, array_split, nan
from modelseedpy.core.msmodelutl import MSModelUtil
from collections import Counter
from deepdiff import DeepDiff  # (old, new)
from typing import Iterable, Union
from pprint import pprint
from numpy.random import shuffle
from multiprocess import current_process
from icecream import ic
import re
# from math import prod

# silence deprecation warnings from DeepDiff parsing the
import warnings
warnings.simplefilter("ignore", category=DeprecationWarning)


def _compatibilize(member_models: Iterable, printing=False):
    # return member_models
    models = MSCompatibility.standardize(member_models, conflicts_file_name='exchanges_conflicts.json', printing=printing)
    if not isinstance(member_models, (set, list, tuple)):
        return models[0]
    return models

def _load_models(member_models: Iterable, com_model=None, compatibilize=True, printing=False):
    # ic(member_models, com_model, compatibilize)
    if not com_model and member_models:
        model = build_from_species_models(member_models, name="SMETANA_pair", cobra_model=True)
        return member_models, model  # (model, names=names, abundances=abundances)
    # models = PARSING_FUNCTION(community_model) # TODO the individual models of a community model can be parsed
    if compatibilize:
        # return _compatibilize(member_models, printing), MSCommunity(_compatibilize([com_model], printing)[0])
        return _compatibilize(member_models, printing), _compatibilize([com_model], printing)[0]
    return member_models, com_model  # MSCommunity(com_model)

def _get_media(media=None, com_model=None, model_s_=None, min_growth=None, environment=None,
               interacting=True, printing=False, minimization_method="minFlux"):
    # ic(media, com_model, model_s_)
    if com_model is None and model_s_ is None:  raise TypeError("< com_model > or < model_s_ > must be parameterized.")
    if media is not None:
        if model_s_ is not None and not isinstance(model_s_, (list,set,tuple)):
            return media["members"][model_s_.id]["media"]
        elif com_model is not None:  return media["community_media"]
        return media
    # model_s_ is either a singular model or a list of models
    if com_model is not None:  com_media = MSMinimalMedia.determine_min_media(
        com_model, minimization_method, min_growth, None, interacting, 5, printing)
    if model_s_ is not None:
        if not isinstance(model_s_, (list,set,tuple,ndarray)):  return MSMinimalMedia.determine_min_media(
            model_s_, minimization_method, min_growth, environment, interacting, printing)
        members_media = {}
        for model in model_s_:
            members_media[model.id] = {"media":MSMinimalMedia.determine_min_media(
                model, minimization_method, min_growth, environment, interacting, printing)}
        # print(members_media)
        if com_model is None:  return members_media
    else:  return com_media
    return {"community_media":com_media, "members":members_media}


class MSCommScores:
    def __init__(self, member_models, min_growth=0.1, n_solutions=100, environment=None,
                 abstol=1e-3, media_dict=None, printing=True, raw_content=False, antismash_json_path:str=None,
                 antismash_zip_path:str=None, minimal_media_method="minFlux"):
        self.min_growth = min_growth ; self.abstol = abstol ; self.n_solutions = n_solutions
        self.printing = printing ; self.raw_content = raw_content
        self.antismash_json_path = antismash_json_path ; self.antismash_zip_path = antismash_zip_path

        # process the models
        self.models = _compatibilize(member_models)
        self.community = MSModelUtil(build_from_species_models(self.models, cobra_model=True))
        ## define the environment
        if environment:
            if hasattr(environment, "get_media_constraints"):
                ### standardize modelseed media into COBRApy media
                environment = {"EX_" + exID: -bound[0] for exID, bound in environment.get_media_constraints().items()}
            self.community.add_medium(environment)
        self.environment = environment
        ## test growth
        for model in self.models:
            if model.slim_optimize() == 0:
                raise ObjectiveError(f"The model {model.id} possesses an objective value of 0 in complete media, "
                                     "which is incompatible with minimal media computations and hence SMETANA.")
        if self.community.model.slim_optimize() == 0:
            raise ObjectiveError(f"The community model {self.community.model.id} possesses an objective "
                                 "value of 0 in complete media, which is incompatible with minimal "
                                 "media computations and hence SMETANA.")
        ## determine the minimal media for each model, including the community
        self.media = media_dict if media_dict else MSMinimalMedia.comm_media_est(
            member_models, self.community.model, minimal_media_method,
            min_growth, self.environment, True, n_solutions, printing)

    def all_scores(self, mp_score=True, kbase_obj=None, cobrakbase_path:str=None,
                   kbase_token_path:str=None, RAST_genomes:dict=None):
        mro = self.mro_score()
        mip = self.mip_score(interacting_media=self.media)
        mp = None if not mp_score else self.mp_score()
        mu = None # self.mu_score()
        sc = None # self.sc_score()
        smetana = None # self.smetana_score()
        gyd = self.gyd_score()
        rfc = self.rfc_score() if any([kbase_obj is not None, RAST_genomes != [], cobrakbase_path is not None
                                       and kbase_token_path is not None]) else None
        return {"mro": mro, "mip": mip, "mp": mp, "mu": mu, "sc": sc, "smetana": smetana,
                "gyd":gyd, "rfc":rfc}

    def mro_score(self):
        self.mro_val = MSCommScores.mro(self.models, self.media["members"], self.min_growth,
                                        self.media, self.raw_content, self.environment, self.printing, True)
        if not self.printing:  return self.mro_val
        if self.raw_content:
            for pair, (interaction, media) in self.mro_val.items():
                newcomer, established = pair.split('---')
                print(f"\n(MRO) The {newcomer} media {media} possesses {interaction} shared "
                      f"requirements with the {established} established member.")
                return self.mro_val
        for pair, mro in self.mro_val.items():
            newcomer, established = pair.split('---')
            print(f"\nThe {newcomer} on {established} MRO score: {mro[0]} ({mro[0]*100:.2f}%). "
                  f"This is the percent of nutritional requirements in {newcomer} "
                  f"that overlap with {established} ({mro[1]}/{mro[2]}).")
        return self.mro_val

    def mip_score(self, interacting_media:dict=None, noninteracting_media:dict=None):
        interacting_media = interacting_media or self.media or None
        diff, self.mip_val = MSCommScores.mip(self.community.model, self.models, self.min_growth, interacting_media,
                                              noninteracting_media, self.environment, self.printing, True)
        if not self.printing:  return self.mip_val
        print(f"\nMIP score: {self.mip_val}\t\t\t{self.mip_val} required compound(s) can be sourced via syntrophy:")
        if self.raw_content:  pprint(diff)
        return self.mip_val

    def gyd_score(self, coculture_growth=False):
        self.gyd_val = MSCommScores.gyd(self.models, environment=self.environment, coculture_growth=coculture_growth)
        if not self.printing:  return self.gyd
        growth_type = "monocultural" if not coculture_growth else "cocultural"
        for pair, score in self.gyd_val.items():
            print(f"\nGYD score: The {growth_type} growth difference between the {pair} member models"
                  f" is {score} times greater than the growth of the slower member.")
        return self.gyd

    def rfc_score(self, kbase_obj=None, cobrakbase_path:str=None, kbase_token_path:str=None, RAST_genomes:dict=None):
        self.rfc_val = MSCommScores.rfc(self.models, kbase_obj, cobrakbase_path, kbase_token_path, RAST_genomes)
        if not self.printing:  return self.rfc
        for pair, score in self.rfc_val.items():
            print(f"\nRFC Score: The similarity of RAST functional SSO ontology "
                  f"terms between the {pair} members is {score}.")
        return self.rfc

    def mp_score(self):
        print("executing MP")
        self.mp_val = MSCommScores.mp(self.models, self.environment, self.community.model, None, self.abstol, self.printing)
        if not self.printing:  return self.mp_val
        if self.raw_content:
            print("\n(MP) The possible contributions of each member in the member media include:\n")
            pprint(self.mp_val)
        else:
            print("\nMP score:\t\t\tEach member can possibly contribute the following to the community:\n")
            for member, contributions in self.mp_val.items():
                print(member, "\t", len(contributions))
        return self.mp_val

    def mu_score(self):
        member_excreta = self.mp_score() if not hasattr(self, "mp_val") else self.mp_val
        self.mu_val = MSCommScores.mu(self.models, self.environment, member_excreta, self.n_solutions,
                                      self.abstol, True, self.printing)
        if not self.printing:  return self.mu_val
        print("\nMU score:\t\t\tThe fraction of solutions in which each member is the "
              "syntrophic receiver that contain a respective metabolite:\n")
        pprint(self.mu_val)
        return self.mu_val

    def sc_score(self):
        self.sc_val = MSCommScores.sc(self.models, self.community.model, self.min_growth,
                                      self.n_solutions, self.abstol, True, self.printing)
        if not self.printing:  return self.sc_val
        print("\nSC score:\t\t\tThe fraction of community members who syntrophically contribute to each species:\n")
        pprint(self.sc_val)
        return self.sc_val

    def smetana_score(self):
        if not hasattr(self, "sc_val"):  self.sc_val = self.sc_score()
        sc_coupling = all(array(list(self.sc.values())) is not None)
        if not hasattr(self, "mu_val"):  self.mu_val = self.mu_score()
        if not hasattr(self, "mp_val"):  self.mp_val = self.mp_score()

        self.smetana = MSCommScores.smetana(
            self.models, self.community.model, self.min_growth, self.n_solutions, self.abstol,
            (self.sc_val, self.mu_val, self.mp_val), True, sc_coupling, self.printing)
        if self.printing:  print("\nsmetana score:\n")  ;  pprint(self.smetana)
        return self.smetana

    def antiSMASH_scores(self, antismash_json_path=None):
        self.antismash = MSCommScores.antiSMASH(antismash_json_path or self.antismash_json_path)
        if not self.printing:  return self.antismash
        if self.raw_content:
            print("\n(antismash) The biosynthetic_areas, BGCs, protein_annotations, clusterBlast, and "
                  "num_clusterBlast from the provided antiSMASH results:\n")
            print("The 'areas' that antiSMASH determines produce biosynthetic products:")
            pprint(self.antismash[0])
            print("The set of biosynthetic gene clusters:")
            pprint(self.antismash[1])
            print("The set of clusterblast protein annotations:")
            pprint(self.antismash[2])
            print("Resistance information from clusterblast")
            pprint(self.antismash[3])
            print("The number of proteins associated with resistance")
            pprint(self.antismash[4])
            return self.antismash
        print("\nantiSMASH scores:\n")
        print("The community exhibited:"
              f"- {len(self.antismash[0])}'areas' that antiSMASH determines produce biosynthetic products."
              f"- {len(self.antismash[1])} biosynthetic gene clusters."
              f"- {len(self.antismash[2])} clusterblast protein annotations."
              f"- {len(self.antismash[3])} parcels of resistance information from clusterblast."
              f"- {self.antismash[4]} proteins associated with resistance.")
        return list(map(len, self.antismash[:4]))+[self.antismash[4]]


    ###### STATIC METHODS OF THE SMETANA SCORES, WHICH ARE APPLIED IN THE ABOVE CLASS OBJECT ######

    @staticmethod
    def _check_model(model_util, media, model_str):
        default_media = model_util.model.medium
        model_util.add_medium(media)
        obj_val = model_util.model.slim_optimize()
        if obj_val == 0 or not FBAHelper.isnumber(obj_val):
            print(f"The {model_str} model input does not yield an operational model, and will therefore be gapfilled.")
            return MSGapfill.gapfill(model_util.model, media)
        model_util.add_medium(default_media)
        return model_util.model

    @staticmethod
    def _load(model, kbase_obj):
        model_str = model
        if len(model) == 2:  model = kbase_obj.get_from_ws(*model)
        else:  model = kbase_obj.get_from_ws(model)
        return model, model_str

    @staticmethod
    def calculate_scores(pairs, models_media=None, environments=None, RAST_genomes=None, lazy_load=False,
                         kbase_obj=None, cip_score=True, costless=True, pc=True):
        from pandas import Series

        if isinstance(pairs, list):
            pairs, models_media, environments, RAST_genomes, kbase_obj, lazy_load = pairs  ;  pairs = dict([pairs])
        series, mets = [], []
        environments = [environments] if not isinstance(environments, (list, set, tuple)) else environments
        pid = current_process().name
        model_utils = {}
        count = 0
        for model1, models in pairs.items():
            if lazy_load:  model1, model1_str = MSCommScores._load(model1, kbase_obj)
            else:  model1_str = str(list(pairs.keys()).index(model1))
            if model1.id not in models_media: models_media[model1.id] = {"media": _get_media(model_s_=model1)}
            if model1.id not in model_utils:  model_utils[model1.id] = MSModelUtil(model1)
            # print(pid, model1)
            for model_index, model2 in enumerate(models):
                # print(model2)
                if lazy_load:  model2, model2_str = MSCommScores._load(model2, kbase_obj)
                else:  model2_str = f"{model1_str}_{model_index}"
                if model2.id not in models_media: models_media[model2.id] = {"media": _get_media(model_s_=model2)}
                if model2.id not in model_utils:  model_utils[model2.id] = MSModelUtil(model2)
                # print(model2)
                grouping = [model1, model2]
                modelIDs = [model.id for model in grouping]
                print(f"{pid}~~{count}\t{modelIDs}")
                for envIndex, environ in enumerate(environments):
                    print(f"\tEnvironment{envIndex}: {environ}", end="\t")
                    model1 = MSCommScores._check_model(model_utils[model1.id], environ, model1_str)
                    model2 = MSCommScores._check_model(model_utils[model2.id], environ, model1_str)
                    # initiate the KBase output
                    kbase_dic = {f"model{index+1}": modelID for index, modelID in enumerate(modelIDs)}
                    kbase_dic["media"] = f"{environ}{envIndex}" if not hasattr(environ, "name") else environ.name
                    # define the MRO content
                    mro_values = MSCommScores.mro(grouping, models_media, raw_content=True, environment=environ)
                    kbase_dic.update({f"mro_model{modelIDs.index(models_string.split('--')[0])+1}":
                                      f"{len(intersection)/len(memMedia):.5f} ({len(intersection)}/{len(memMedia)})"
                                      for models_string, (intersection, memMedia) in mro_values.items()})
                    mets.append({"mro_mets": list(mro_values.values())})
                    print("MRO done", end="\t")
                    # define the CIP content
                    if cip_score:
                        cip_values = MSCommScores.cip(modelutils=[model_utils[mem.id] for mem in grouping])
                        kbase_dic.update({"cip": cip_values[1]})
                        print("CIP done", end="\t")
                    # define the MIP content
                    multi_output = bool(costless or pc)
                    # print(multi_output)
                    mip_values = MSCommScores.mip(None, grouping, environment=environ, compatibilized=True,
                                                  costless=costless, pc=pc, multi_output=multi_output)
                    if multi_output:
                        if costless and not pc:
                            kbase_dic.update({"mip": mip_values[0][1], "costless_mip": mip_values[1][1]})
                        elif pc and not costless:
                            kbase_dic.update({"mip": mip_values[0][1], "pc": mip_values[1]})
                        else:  kbase_dic.update({"mip": mip_values[0][1], "costless_mip": mip_values[1][1],
                                                 "pc": mip_values[2]})  ;  print("PC  done", end="\t")
                        mets.append({"mip_mets": [re.search(r"(cpd[0-9]{5})", cpd).group() for cpd in mip_values[0][0]]})
                    else:
                        kbase_dic.update({"mip": mip_values[1]})
                        mets.append({"mip_mets": [re.search(r"(cpd[0-9]{5})", cpd).group() for cpd in mip_values[0]]})

                    print("MIP done", end="\t")
                    # determine the growth diff content
                    kbase_dic.update({"gyd": list(MSCommScores.gyd(grouping, environment=environ).values())[0]})
                    print("GYD done\t\t", end="\t" if RAST_genomes else "\n")
                    # determine the RAST Functional Complementarity content
                    if kbase_obj is not None and RAST_genomes:
                        kbase_dic.update({"RFC": list(MSCommScores.rfc(
                            grouping, kbase_obj, RAST_genomes=RAST_genomes).values())[0]})
                        print("RFC done\t\t")

                    # return a pandas Series, which can be easily aggregated with other results into a DataFrame
                    series.append(Series(kbase_dic))
                count += 1
        return series, mets

    @staticmethod
    def kbase_output(all_models:iter=None, pairs:dict=None, mem_media:dict=None, pair_limit:int=None,
                     exclude_pairs:list=None, kbase_obj=None,
                     RAST_genomes:dict=True,  # True triggers internal acquisition of the genomes, where None
                     see_media=True, environments:iter=None,  # a collection of environment dicts or KBase media objects
                     pool_size:int=None, cip_score=True, costless=True, pc=True):
        from pandas import concat
        if pairs:  model_pairs = unique([{model1, model2} for model1, models in pairs.items() for model2 in models])
        elif all_models is not None:
            model_pairs = array(list(combinations(all_models, 2)))
            if pair_limit is not None:
                shuffle(model_pairs)
                new_pairs = []
                for index, pair in enumerate(model_pairs):
                    if set(pair) not in exclude_pairs and index < pair_limit:  new_pairs.append(pair)
                    elif index >= pair_limit:  break
                model_pairs = array(new_pairs)
            if isinstance(model_pairs[0], str):  model_pairs = unique(sort(model_pairs, axis=1))
            pairs = {first: model_pairs[where(model_pairs[:, 0] == first)][:, 1] for first in model_pairs[:, 0]}
        else:  raise ValueError("Either < all_models > or < pairs > must be defined to simulate interactions.")
        if not all_models:  all_models = list(chain(*[list(values) for values in pairs.values()])) + list(pairs.keys())
        lazy_load = isinstance(all_models[0], (list,set,tuple))
        if lazy_load and not kbase_obj:  ValueError("The < kbase_obj > argument must be provided to lazy load models.")
        if not mem_media:  models_media = _get_media(model_s_=all_models)
        else:
            models_media = mem_media.copy()
            missing_models = set()
            missing_modelID = []
            for model in all_models:
                if model is not None and model.id not in models_media:
                    missing_models.add(model)
                    missing_modelID.append(model if not hasattr(model, "id") else model.id)
            if missing_models != set():
                print(f"Media of the {missing_modelID} models are not defined, and will be calculated separately.")
                models_media.update(_get_media(model_s_=missing_models))
        if see_media and not mem_media:  print(f"The minimal media of all members:\n{models_media}")
        print(f"\nExamining the {len(list(model_pairs))} model pairs")
        if pool_size is not None:
            from datetime import datetime  ;  from multiprocess import Pool
            print(f"Loading {int(pool_size)} workers and computing the scores", datetime.now())
            pool = Pool(int(pool_size))#.map(calculate_scores, [{k: v} for k,v in pairs.items()])
            args = [[pair, models_media, environments, RAST_genomes, kbase_obj, lazy_load]
                    for pair in list(pairs.items())]
            output = pool.map(MSCommScores.calculate_scores, args)
            series = chain.from_iterable([ele[0] for ele in output])
            mets = chain.from_iterable([ele[1] for ele in output])
        else:  series, mets = MSCommScores.calculate_scores(pairs, models_media, environments, RAST_genomes, lazy_load,
                                                            kbase_obj, cip_score, costless, pc)
        return concat(series, axis=1).T, mets

    @staticmethod
    def mro(member_models:Iterable=None, mem_media:dict=None, min_growth=0.1, media_dict=None,
            raw_content=False, environment=None, printing=False, compatibilized=False):
        """Determine the overlap of nutritional requirements (minimal media) between member organisms."""
        # determine the member minimal media if they are not parameterized
        if not mem_media:
            if not member_models:
                raise ParameterError("The either member_models or minimal_media parameter must be defined.")
            member_models = _compatibilize(member_models, printing)
            mem_media = _get_media(media_dict, None, member_models, min_growth, environment, printing=printing)
            if "community_media" in mem_media:  mem_media = mem_media["members"]
        # MROs = array(list(map(len, pairs.values()))) / array(list(map(len, mem_media.values())))
        mro_values = {}
        for model1, model2 in permutations(member_models, 2):
            intersection = set(mem_media[model1.id]["media"].keys()) & set(mem_media[model2.id]["media"].keys())
            member_media = mem_media[model1.id]["media"]
            if raw_content:  mro_values[f"{model1.id}---{model2.id})"] = (intersection, member_media)
            else:  mro_values[f"{model1.id}---{model2.id})"] = (
                len(intersection)/len(member_media), len(intersection), len(member_media))
        return mro_values
        # return mean(list(map(len, pairs.values()))) / mean(list(map(len, mem_media.values())))

    @staticmethod
    def mip(com_model=None, member_models:Iterable=None, min_growth=0.1, interacting_media_dict=None,
            noninteracting_media_dict=None, environment=None, printing=True, compatibilized=False,
            costless=False, pc=False, multi_output=False):
        """Determine the quantity of nutrients that can be potentially sourced through syntrophy"""
        member_models, community = _load_models(member_models, com_model, not compatibilized, printing=printing)
        # determine the interacting and non-interacting media for the specified community  .util.model
        noninteracting_medium = _get_media(noninteracting_media_dict, community, None, min_growth, environment, False)
        if "community_media" in noninteracting_medium:  noninteracting_medium = noninteracting_medium["community_media"]
        interacting_medium = _get_media(interacting_media_dict, community, None, min_growth, environment, True)
        if "community_media" in interacting_medium:  interacting_medium = interacting_medium["community_media"]
        # differentiate the community media
        interact_diff = DeepDiff(noninteracting_medium, interacting_medium)
        if "dictionary_item_removed" in interact_diff:
            cross_fed_exIDs = [re.sub("(root\['|'\])", "", x) for x in interact_diff["dictionary_item_removed"]]
            outputs = [(cross_fed_exIDs, len(cross_fed_exIDs))]
            if costless:
                costless_mets, numMets = MSCommScores.cip(member_models=member_models)
                costless_cross_fed = [exID for exID in cross_fed_exIDs if exID in costless_mets]
                if not multi_output:  return costless_cross_fed, len(costless_cross_fed)
                outputs.append((costless_cross_fed, len(costless_cross_fed)))
            if pc:  outputs.append((MSCommScores.pc(member_models, community)))
            return outputs
        return None, 0

    @staticmethod
    def cip(modelutils=None, member_models=None):  # costless interaction potential
        if not modelutils:  modelutils = {MSModelUtil(model) for model in member_models}
        costless_mets = set(chain.from_iterable([modelutil.costless_excreta() for modelutil in modelutils]))
        return costless_mets, len(costless_mets)

    @staticmethod
    def contributions(org_possible_contributions, scores, model_util, abstol):
        # identify and log excreta from the solution
        model_util.add_objective(sum(ex_rxn.flux_expression for ex_rxn in org_possible_contributions))
        sol = model_util.model.optimize()
        if sol.status != "optimal":
            # exit the while loop by returning the original possible_contributions,
            ## hence DeepDiff == {} and the while loop terminates
            return scores, org_possible_contributions
        # identify and log excreta from the solution
        possible_contributions = org_possible_contributions[:]
        for ex in org_possible_contributions:
            if ex.id in sol.fluxes.keys() and sol.fluxes[ex.id] >= abstol:
                possible_contributions.remove(ex)
                scores[model_util.model.id].update([met.id for met in ex.metabolites])
        return scores, possible_contributions

    @staticmethod
    def mp(member_models:Iterable, environment, com_model=None, minimal_media=None, abstol=1e-3, printing=False):
        """Discover the metabolites that each species can contribute to a community"""
        community = _compatibilize(com_model) if com_model else build_from_species_models(
            member_models, cobra_model=True, standardize=True)
        # TODO support parsing the individual members through the MSCommunity object
        community.medium = minimal_media or MSMinimalMedia.minimize_flux(community)
        scores = {}
        for org_model in member_models:
            model_util = MSModelUtil(org_model)
            model_util.compatibilize(printing=printing)
            if environment:
                model_util.add_medium(environment)
            # TODO leverage extant minimal media as the default instead of the community complete media
            scores[model_util.model.id] = set()
            # determines possible member contributions in the community environment, where the excretion of media compounds is irrelevant
            org_possible_contributions = [ex_rxn for ex_rxn in model_util.exchange_list()
                                          if (ex_rxn.id not in community.medium and ex_rxn.upper_bound > 0)]
            # ic(org_possible_contributions, len(model_util.exchange_list()), len(community.medium))
            scores, possible_contributions = MSCommScores.contributions(
                org_possible_contributions, scores, model_util, abstol)
            while DeepDiff(org_possible_contributions, possible_contributions):
                print("remaining possible_contributions", len(possible_contributions), end="\r")
                ## optimize the sum of the remaining exchanges that have not surpassed the abstol
                org_possible_contributions = possible_contributions[:]
                scores, possible_contributions = MSCommScores.contributions(
                    org_possible_contributions, scores, model_util, abstol)

            ## individually checks the remaining possible contributions
            for ex_rxn in possible_contributions:
                model_util.model.objective = Objective(ex_rxn.flux_expression)
                sol = model_util.model.optimize()
                if sol.status == 'optimal' or sol.objective_value > abstol:
                    for met in ex_rxn.metabolites:
                        if met.id in scores[model_util.model.id]:
                            print("removing", met.id)
                            scores[model_util.model.id].remove(met.id)
        return scores

    @staticmethod
    def mu(member_models:Iterable, environment=None, member_excreta=None, n_solutions=100, abstol=1e-3,
           compatibilized=False, printing=True):
        """the fractional frequency of each received metabolite amongst all possible alternative syntrophic solutions"""
        # member_solutions = member_solutions if member_solutions else {model.id: model.optimize() for model in member_models}
        scores = {}
        member_models = member_models if compatibilized else _compatibilize(member_models, printing)
        if member_excreta:
            missing_members = [model for model in member_models if model.id not in member_excreta]
            if missing_members:
                print(f"The {','.join(missing_members)} members are missing from the defined "
                      f"excreta list and will therefore be determined through an additional MP simulation.")
                member_excreta.update(MSCommScores.mp(missing_members, environment))
        else:
            member_excreta = MSCommScores.mp(member_models, environment, None, abstol, printing)
        for org_model in member_models:
            other_excreta = set(chain.from_iterable([excreta for model, excreta in member_excreta.items()
                                                     if model != org_model.id]))
            print(f"\n{org_model.id}\tOther Excreta", other_excreta)
            model_util = MSModelUtil(org_model, True)
            if environment:
                model_util.add_medium(environment)
            ex_rxns = {ex_rxn: list(ex_rxn.metabolites)[0] for ex_rxn in model_util.exchange_list()}
            print(f"\n{org_model.id}\tExtracellular reactions", ex_rxns)
            variables = {ex_rxn.id: Variable('___'.join([model_util.model.id, ex_rxn.id]),
                                             lb=0, ub=1, type="binary") for ex_rxn in ex_rxns}
            model_util.add_cons_vars(list(variables.values()))
            media, solutions = [], []
            sol = model_util.model.optimize()
            while sol.status == "optimal" and len(solutions) < n_solutions:
                solutions.append(sol)
                medium = set([ex for ex in ex_rxns if sol.fluxes[ex.id] < -abstol and ex in other_excreta])
                model_util.create_constraint(Constraint(sum([variables[ex.id] for ex in medium]),
                                                        ub=len(medium)-1, name=f"iteration_{len(solutions)}"))
                media.append(medium)
                sol = model_util.model.optimize()
            counter = Counter(chain(*media))
            scores[model_util.model.id] = {met.id: counter[ex] / len(media)
                                           for ex, met in ex_rxns.items() if counter[ex] > 0}
        return scores

    @staticmethod
    def sc(member_models:Iterable=None, com_model=None, min_growth=0.1, n_solutions=100,
           abstol=1e-6, compatibilized=True, printing=False):
        """Calculate the frequency of interspecies dependency in a community"""
        member_models, community = _load_models(
            member_models, com_model, not compatibilized, printing=printing)
        for rxn in com_model.reactions:
            rxn.lower_bound = 0 if 'bio' in rxn.id else rxn.lower_bound

        # c_{rxn.id}_lb: rxn < 1000*y_{species_id}
        # c_{rxn.id}_ub: rxn > -1000*y_{species_id}
        variables = {}
        constraints = []
        # TODO this can be converted to an MSCommunity object by looping through each index
        # leverage CommKinetics
        for org_model in member_models:
            model_util = MSModelUtil(org_model, True)
            variables[model_util.model.id] = Variable(name=f'y_{model_util.model.id}', lb=0, ub=1, type='binary')
            model_util.add_cons_vars([variables[model_util.model.id]])
            for rxn in model_util.model.reactions:
                if "bio" not in rxn.id:
                    # print(rxn.flux_expression)
                    lb = Constraint(rxn.flux_expression + 1000*variables[model_util.model.id],
                                    name="_".join(["c", model_util.model.id, rxn.id, "lb"]), lb=0)
                    ub = Constraint(rxn.flux_expression - 1000*variables[model_util.model.id],
                                    name="_".join(["c", model_util.model.id, rxn.id, "ub"]), ub=0)
                    constraints.extend([lb, ub])

        # calculate the SCS
        scores = {}
        for model in member_models:
            com_model_util = MSModelUtil(com_model)
            com_model_util.add_cons_vars(constraints, sloppy=True)
            # model growth is guaranteed while minimizing the growing members of the community
            ## SMETANA_Biomass: {biomass_reactions} > {min_growth}
            com_model_util.create_constraint(Constraint(sum(rxn.flux_expression for rxn in model.reactions
                                                            if "bio" in rxn.id), name='SMETANA_Biomass', lb=min_growth)) # sloppy = True)
            other_members = [other for other in member_models if other.id != model.id]
            com_model_util.add_objective(sum([variables[other.id] for other in other_members]), "min")
            previous_constraints, donors_list = [], []
            for i in range(n_solutions):
                sol = com_model.optimize()  # FIXME The solution is not optimal
                if sol.status != 'optimal':
                    scores[model.id] = None
                    break
                donors = [o for o in other_members if com_model.solver.primal_values[f"y_{o.id}"] > abstol]
                donors_list.append(donors)
                previous_con = f'iteration_{i}'
                previous_constraints.append(previous_con)
                com_model_util.add_cons_vars([Constraint(sum(variables[o.id] for o in donors), name=previous_con,
                                                         ub=len(previous_constraints)-1)], sloppy=True)
            if i != 0:
                donors_counter = Counter(chain(*donors_list))
                scores[model.id] = {o.id: donors_counter[o] / len(donors_list) for o in other_members}
        return scores

    @staticmethod
    def gyd(member_models:Iterable=None, model_utils:Iterable=None, environment=None, coculture_growth=False):
        diffs = {}
        for combination in combinations(model_utils or member_models, 2):
            if model_utils is None:
                model1_util = MSModelUtil(combination[0], True) ; model2_util = MSModelUtil(combination[1], True)
                if environment:  model1_util.add_medium(environment); model2_util.add_medium(environment)
            else:  model1_util = combination[0] ; model2_util = combination[1]
            if not coculture_growth:
                G_m1, G_m2 = model1_util.model.slim_optimize(), model2_util.model.slim_optimize()
                G_m1 = G_m1 if FBAHelper.isnumber(str(G_m1)) else 0
                G_m2 = G_m2 if FBAHelper.isnumber(str(G_m2)) else 0
            else:
                mscom = MSCommunity(models=[model1_util.model, model2_util.model],
                                    names=[mem.id for mem in member_models])
                sol = mscom.run_fba()
                # TODO parse the community FBA solution for the individual member growths.
                ## This may require converting the biomasses into growth fluxes.
            if G_m2 <= 0 and G_m1 <= 0: diffs[f"{model1_util.model.id} ++ {model2_util.model.id}"] = None  ;  continue
            if G_m2 <= 0 or G_m1 <= 0: diffs[f"{model1_util.model.id} ++ {model2_util.model.id}"] = 1e5  ;  continue
            diffs[f"{model1_util.model.id} ++ {model2_util.model.id}"] = abs(G_m1-G_m2) / min([G_m1, G_m2])
        return diffs

    @staticmethod
    def pc(member_models, com_model=None, printing=True, compatibilized=False):
        # TODO the ratio of community growth to the sum of member growths, where >1 indicates synergism
        if com_model: community = com_model
        else:  member_models, community = _load_models(member_models, com_model, not compatibilized, printing=printing)
        return (community.slim_optimize()/sum([model.slim_optimize() for model in member_models]))

    @staticmethod
    def _calculate_jaccard_score(set1, set2):
        if set1 == set2:  print(f"The sets are identical, with a length of {len(set1)}.")
        return len(set1.intersection(set2)) / len(set1.union(set2))

    @staticmethod
    def get_all_genomes_from_ws(ws_id, kbase_object=None, cobrakbase_repo_path:str=None, kbase_token_path:str=None):
        def get_genome(genome_name):
            return kbase_object.ws_client.get_objects2(
                {'objects': [{'ref': f"{ws_id}/{genome_name}"}]})["data"][0]['data']
        # load the kbase client instance
        if not kbase_object:
            import os
            os.environ["HOME"] = cobrakbase_repo_path
            import cobrakbase
            with open(kbase_token_path) as token_file:  kbase_object = cobrakbase.KBaseAPI(token_file.readline())

        # calculate the complementarity
        genome_list = kbase_object.ws_client.list_objects(
            {"ids": [ws_id], "type": 'KBaseGenomes.Genome', 'minObjectID': 0, 'maxObjectID': 10000})
        genome_names = [g[1] for g in genome_list if g[1].endswith("RAST")]
        return {genome_name: set([sso for j in get_genome(genome_name)['cdss']
                                  for sso in j['ontology_terms']['SSO'].keys()])
                for genome_name in genome_names}

    @staticmethod
    def rfc(models:Iterable=None, kbase_object=None, cobrakbase_repo_path:str=None,  # RAST Functional Complementarity
            kbase_token_path:str=None, RAST_genomes:dict=None, printing=False):
        if not isinstance(RAST_genomes, dict):
            if not kbase_object:
                import os ; os.environ["HOME"] = cobrakbase_repo_path ; import cobrakbase
                with open(kbase_token_path) as token_file:  kbase_object = cobrakbase.KBaseAPI(token_file.readline())
            RAST_genomes = {model.id: kbase_object.get_from_ws(model.genome_ref) for model in models}
        elif not isinstance(RAST_genomes, dict):  RAST_genomes = dict(zip([model.id for model in models], RAST_genomes))
        elif models is not None:
            RAST_genomes = {k:v for k,v in RAST_genomes.items() if k in [model.id for model in models]}
        genome_combinations = list(combinations(RAST_genomes.keys(), 2))
        if printing: print(f"The RAST Functionality Score (RFC) will be calculated for {len(genome_combinations)} pairs.")
        if not isinstance(list(RAST_genomes.values())[0], dict):
            genome1_set, genome2_set = set(), set()
            distances = {}
            for genome1, genome2 in genome_combinations:
                for j in RAST_genomes[genome1].features:
                    for key, val in j.ontology_terms.items():
                        if key == 'SSO':  genome1_set.update(val)
                for j in RAST_genomes[genome2].features:
                    for key, val in j.ontology_terms.items():
                        if key == 'SSO':  genome2_set.update(val)
                distances[f"{genome1} ++ {genome2}"] = MSCommScores._calculate_jaccard_score(genome1_set, genome2_set)
        else:
            distances = {f"{genome1} ++ {genome2}": MSCommScores._calculate_jaccard_score(
                set(list(content["SSO"].keys())[0] for dic in RAST_genomes[genome1]["cdss"]
                    for x, content in dic.items() if x == "ontology_terms" and len(content["SSO"].keys()) > 0),
                set(list(content["SSO"].keys())[0] for dic in RAST_genomes[genome2]["cdss"]
                    for x, content in dic.items() if x == "ontology_terms" and len(content["SSO"].keys()) > 0))
                for genome1, genome2 in combinations(RAST_genomes.keys(), 2)}
        return distances

    @staticmethod
    def smetana(member_models: Iterable, environment, com_model=None, min_growth=0.1, n_solutions=100,
                abstol=1e-6, prior_values=None, compatibilized=False, sc_coupling=False, printing=False):
        """Quantifies the extent of syntrophy as the sum of all exchanges in a given nutritional environment"""
        member_models, community = _load_models(
            member_models, com_model, compatibilized==False, printing=printing)
        sc = None
        if not prior_values:
            mp = MSCommScores.mp(member_models, environment, com_model, abstol)
            mu = MSCommScores.mu(member_models, environment, mp, n_solutions, abstol, compatibilized)
            if sc_coupling:
                sc = MSCommScores.sc(member_models, com_model, min_growth, n_solutions, abstol, compatibilized)
        elif len(prior_values) == 3:  sc, mu, mp = prior_values
        else:  mu, mp = prior_values

        smetana_scores = {}
        for pairs in combinations(member_models, 2):
            for model1, model2 in permutations(pairs):
                if model1.id not in smetana_scores:
                    smetana_scores[model1.id] = {}
                if not any([not mu[model1.id], not mp[model1.id]]):
                    sc_score = 1 if not sc_coupling else sc[model1.id][model2.id]
                    models_mets = list(model1.metabolites)+list(model2.metabolites)
                    unique_mets = set([met.id for met in models_mets])
                    smetana_scores[model1.id][model2.id] = 0
                    for met in models_mets:
                        if met.id in unique_mets:
                            mp_score = 0 if met.id not in mp[model1.id] else 1
                            smetana_scores[model1.id][model2.id] += mu[model1.id].get(met.id,0)*sc_score*mp_score
        return smetana_scores

    @staticmethod
    def antiSMASH(json_path=None, zip_path=None):
        # TODO Scores 2, 4, and 5 are being explored for relevance to community formation and reveal specific member interactions/targets
        # load the antiSMASH report from either the JSON or the raw ZIP, or both
        from os import mkdir, listdir, path
        from zipfile import ZipFile
        from json import load
        if json_path:
            cwd_files = listdir()
            if json_path not in cwd_files and zip_path:
                with ZipFile(zip_path, "r") as zip_file:
                    zip_file.extract(json_path)
            with open(json_path, "r") as json_file:
                data = load(json_file)
        elif zip_path:
            mkdir("extracted_antiSMASH")
            with ZipFile(zip_path, "r") as zip_file:
                zip_file.extractall("extracted_antiSMASH")
            json_files = [x for x in listdir("extracted_antiSMASH") if x.endswith("json")]
            if len(json_files) > 1:
                print(f"The antiSMASH report describes {len(json_files)} JSON files, the first of which is selected "
                      f"{json_files[0]} for analysis, otherwise explicitly identify the desired JSON file in the json_path parameter.")
            with open(path.join("extracted_antiSMASH", json_files[0]), "r") as json_file:
                data = load(json_file)
        else:
            raise ParameterError("Either the json_path or zip_path from the antiSMASH analysis must be provided,"
                                 " for these scores to be determined.")
        # Parse data and scores from the antiSMASH report
        biosynthetic_areas = data["records"][0]['areas']
        BGCs = set(numpy.array([data["records"][0]['areas'][i]['products'] for i in range(biosynthetic_areas)]).flatten())
        len_proteins = len(data["records"][0]['modules']['antismash.modules.clusterblast']['knowncluster']['proteins'])
        protein_annotations = [data["records"][0]['modules']['antismash.modules.clusterblast']['knowncluster']['proteins'][i]['annotations']
                           for i in range(len_proteins)]
        clusterBlast = [s for s in protein_annotations if "resistance" in s]
        num_clusterBlast = sum([item.count("resistance") for item in protein_annotations])

        return biosynthetic_areas, BGCs, protein_annotations, clusterBlast, num_clusterBlast