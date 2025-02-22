# -*- coding: utf-8 -*-
import pandas as pd
import logging
import cobra
from cobra.core.dictlist import DictList
from modelseedpy.core.msmedia import MSMedia
from modelseedpy.fbapkg.mspackagemanager import MSPackageManager
from modelseedpy.core.msmodelutl import MSModelUtil
from modelseedpy.core.msgapfill import MSGapfill

logger = logging.getLogger(__name__)
logger.setLevel(
    logging.INFO
)  # When debugging - set this to INFO then change needed messages below from DEBUG to INFO

zero_threshold = 0.0000001

class MSGrowthPhenotype:
    def __init__(
        self,
        id,
        media=None,
        experimental_value=None,
        gene_ko=[],
        additional_compounds=[],
        parent=None,
        name=None,
        type="growth"
    ):
        self.id = id
        self.name = name
        if name == None:
            self.name = self.id
        self.experimental_value = experimental_value
        self.media = media
        self.gene_ko = gene_ko
        self.gapfilling = None
        self.additional_compounds = additional_compounds
        self.parent = parent
        self.type = type

    def build_media(self, include_base_media=True):
        """Builds media object to use when simulating the phenotype
        Parameters
        ----------
        include_base_media : bool
            Indicates whether to include the base media for the phenotype set in the formulation
        """
        cpd_hash = {}
        for cpd in self.additional_compounds:
            cpd_hash[cpd] = 100
        full_media = MSMedia.from_dict(cpd_hash)
        if self.media:
            full_media.merge(self.media, overwrite_overlap=False)
        if include_base_media:
            if self.parent and self.parent.base_media:
                full_media.merge(self.parent.base_media, overwrite_overlap=False)
        return full_media

    def simulate(
        self,
        model_or_mdlutl,
        multiplier=3,
        add_missing_exchanges=False,
        save_fluxes=False,
        save_reaction_list=False,
        ignore_experimental_data=False,
        baseline_objective=0.01,
        flux_coefficients=None,
    ):
        """Simulates a single phenotype
        Parameters
        ----------
        model_or_modelutl : Model | MSModelUtl
            Model to use to run the simulations
        add_missing_exchanges : bool
            Boolean indicating if exchanges for compounds mentioned explicitly in phenotype media should be added to the model automatically
        multiplier : double
            Indicates a multiplier to use for positive growth above the growth on baseline media
        save_fluxes : bool
            Indicates if the fluxes should be saved and returned with the results
        pfba : bool
            Runs pFBA to compute fluxes after initially solving for growth
        ignore_experimental_data : bool
            Indicates if existing growth data in the phenotype should be ignored when computing the class of the simulated phenotype
        """
        modelutl = model_or_mdlutl
        if not isinstance(model_or_mdlutl, MSModelUtil):
            modelutl = MSModelUtil.get(model_or_mdlutl)

        #Setting the objective from the phenotype type - this will add missing exchanges for the primary compound for uptake and excretion phenotypes
        missing_transporters = []
        objstring = modelutl.set_objective_from_phenotype(self,missing_transporters)

        #Creating output datastructure and returning if the objective cannot be created
        output = {
            "objective_value": 0,
            "class": "N",
            "missing_transports": missing_transporters,
            "baseline_objective": 0,
            "objective":objstring,
            "baseline_objective":baseline_objective
        }
        if objstring == None:
            return output

        # Building full media and adding missing exchanges
        full_media = self.build_media()

        #Adding missing exchanges
        if add_missing_exchanges:
            output["missing_transports"].extend(modelutl.add_missing_exchanges(full_media))
        
        # Getting basline growth
        if objstring != None and output["baseline_objective"] == None and self.parent:
            output["baseline_objective"] = self.parent.baseline_objective(modelutl, objstring)
        if output["baseline_objective"] < 1e-5:
            output["baseline_objective"] = 0.01

        # Building specific media and setting compound exception list
        if self.parent and self.parent.atom_limits and len(self.parent.atom_limits) > 0:
            reaction_exceptions = []
            specific_media = self.build_media(False)
            for mediacpd in specific_media.mediacompounds:
                ex_hash = mediacpd.get_mdl_exchange_hash(modelutl)
                for mdlcpd in ex_hash:
                    reaction_exceptions.append(ex_hash[mdlcpd])
            modelutl.pkgmgr.getpkg("ElementUptakePkg").build_package(
                self.parent.atom_limits, exception_reactions=reaction_exceptions
            )

        # Applying media
        if self.parent:
            modelutl.pkgmgr.getpkg("KBaseMediaPkg").build_package(
                full_media, self.parent.base_uptake, self.parent.base_excretion
            )
        else:
            modelutl.pkgmgr.getpkg("KBaseMediaPkg").build_package(full_media, 0, 1000)

        with modelutl.model:
            # Applying gene knockouts
            for gene in self.gene_ko:
                if gene in modelutl.model.genes:
                    geneobj = modelutl.model.genes.get_by_id(gene)
                    geneobj.knock_out()

            # Optimizing model
            if '1_objc' in modelutl.model.constraints:
                constraint = modelutl.model.constraints['1_objc']
                modelutl.model.remove_cons_vars([constraint])
            solution = modelutl.model.optimize()
            output["objective_value"] = solution.objective_value
            if solution.objective_value != None and solution.objective_value > 0:
                if flux_coefficients == None:
                    solution = cobra.flux_analysis.pfba(modelutl.model)
                else:
                    #modelutl.printlp(lpfilename="lpfiles/gapfill.lp")
                    modelutl.pkgmgr.getpkg("ObjConstPkg").build_package(
                        0.1, None
                    )
                    coefobj = modelutl.model.problem.Objective(0, direction="min")
                    modelutl.model.objective = coefobj
                    obj_coef = {}
                    for rxn in flux_coefficients:
                        rxnid = rxn
                        direction = "="
                        if rxn[0:1] == ">" or rxn[0:1] == "<":
                            direction = rxn[0:1]
                            rxnid = rxn[1:]
                        if rxnid in modelutl.model.reactions:
                            rxnobj = modelutl.model.reactions.get_by_id(rxnid)
                            if direction == ">" or direction == "=":
                                obj_coef[rxnobj.forward_variable] = flux_coefficients[rxn]
                            if direction == "<" or direction == "=":
                                obj_coef[rxnobj.reverse_variable] = flux_coefficients[rxn]
                    coefobj.set_linear_coefficients(obj_coef)
                    solution = modelutl.model.optimize()
                    modelutl.pkgmgr.getpkg("ObjConstPkg").clear()
                if save_reaction_list:
                    output["reactions"] = []
                if save_fluxes:
                    output["fluxes"] = solution.fluxes
                output["gapfill_count"] = 0
                output["reaction_count"] = 0
                for reaction in modelutl.model.reactions:
                    if reaction.id in solution.fluxes:
                        flux = solution.fluxes[reaction.id]
                        if abs(flux) > zero_threshold:
                            output["reaction_count"] += 1
                            if reaction.id[0:3] != "bio" and reaction.id[0:3] != "EX_" and reaction.id[0:3] != "DM_" and len(reaction.genes) == 0:
                                output["gapfill_count"] += 1
                            if save_reaction_list and flux > zero_threshold:
                                output["reactions"].append(">"+reaction.id)
                            elif save_reaction_list:
                                output["reactions"].append("<"+reaction.id)

        # Determining phenotype class
        if output["objective_value"] != None and output["objective_value"] >= output["baseline_objective"] * multiplier:
            output["postive"] = True
            if not self.experimental_value or ignore_experimental_data:
                output["class"] = "P"
            elif self.experimental_value > 0:
                output["class"] = "CP"
            elif self.experimental_value == 0:
                output["class"] = "FP"
        else:
            output["postive"] = False
            if self.experimental_value == None or ignore_experimental_data:
                output["class"] = "N"
            elif self.experimental_value > 0:
                output["class"] = "FN"
            elif self.experimental_value == 0:
                output["class"] = "CN"
        return output

    def gapfill_model_for_phenotype(
        self,
        msgapfill,
        test_conditions,
        multiplier=10,
        add_missing_exchanges=False,
    ):
        """Gapfills the model to permit this single phenotype to be positive
        Parameters
        ----------
        msgapfill : MSGapfill
            Fully configured gapfilling object
        add_missing_exchanges : bool
            Boolean indicating if exchanges for compounds mentioned explicitly in phenotype media should be added to the model automatically
        multiplier : double
            Indicates a multiplier to use for positive growth above the growth on baseline media
        objective : string
            Expression for objective to be activated by gapfilling
        """
        # First simulate model without gapfilling to assess ungapfilled growth
        output = self.simulate(
            msgapfill.mdlutl,multiplier, add_missing_exchanges
        )
        if output["objective_value"] >= output["baseline_objective"] * multiplier:
            # No gapfilling needed - original model grows without gapfilling
            return {
                "reversed": {},
                "new": {},
                "media": self.build_media(),
                "target": output["objective"],
                "minobjective": output["baseline_objective"] * multiplier,
                "binary_check": False,
            }

        # Now pulling the gapfilling configured model from MSGapfill
        gfmodelutl = MSModelUtil.get(msgapfill.gfmodel)
        # Saving the gapfill objective because this will be replaced when the simulation runs
        gfobj = gfmodelutl.model.objective
        # Running simulate on gapfill model to add missing exchanges and set proper media and uptake limit constraints
        output = self.simulate(
            gfmodelutl, multiplier=multiplier, add_missing_exchanges=add_missing_exchanges
        )
        # If the gapfilling model fails to achieve the minimum growth, then no solution exists
        if output["objective_value"] < output["baseline_objective"] * multiplier:
            logger.warning(
                "Gapfilling failed with the specified model, media, and target reaction."
            )
            return None

        # Running the gapfilling itself
        full_media = self.build_media()
        with gfmodelutl.model:
            # Applying gene knockouts
            for gene in self.gene_ko:
                if gene in gfmodelutl.model.genes:
                    geneobj = gfmodelutl.model.genes.get_by_id(gene)
                    geneobj.knock_out()

            gfresults = self.gapfilling.run_gapfilling(
                full_media, None, minimum_obj=output["baseline_objective"] * multiplier
            )
            if gfresults is None:
                logger.warning(
                    "Gapfilling failed with the specified model, media, and target reaction."
                )

        return gfresults

class MSGrowthPhenotypes:
    def __init__(
        self, base_media=None, base_uptake=0, base_excretion=1000, global_atom_limits={}, id=None, name=None, source=None, source_id=None, type=None
    ):
        self.id = id
        self.name = name
        self.source = source
        self.source_id = source_id
        self.type = type
        self.base_media = base_media
        self.phenotypes = DictList()
        self.base_uptake = base_uptake
        self.base_excretion = base_excretion
        self.atom_limits = global_atom_limits
        self.baseline_objective_data = {}
        self.cached_based_growth = {}

    @staticmethod
    def from_compound_hash(
        compounds,
        base_media=None,
        base_uptake=0,
        base_excretion=1000,
        global_atom_limits={},
        type="growth"
    ):
        growthpheno = MSGrowthPhenotypes(
            base_media=base_media, base_uptake=base_uptake, base_excretion=base_excretion, global_atom_limits=global_atom_limits, id=None, name=None, source=None, source_id=None, type=None
        )
        new_phenos = []
        for cpd in compounds:
            newpheno = MSGrowthPhenotype(cpd,media=None,experimental_value=compounds[cpd],gene_ko=[],additional_compounds=[cpd],type=type)            
            new_phenos.append(newpheno)
        growthpheno.add_phenotypes(new_phenos)
        return growthpheno

    @staticmethod
    def from_kbase_object(
        data,
        kbase_api,
        base_media=None,
        base_uptake=0,
        base_excretion=1000,
        global_atom_limits={},
    ):
        growthpheno = MSGrowthPhenotypes(
            base_media=base_media, base_uptake=base_uptake, base_excretion=base_excretion, global_atom_limits=global_atom_limits, id=data["id"], name=data["name"], source=data["source"], source_id=data["source_id"], type=data["type"]
        )
        new_phenos = []
        for pheno in data["phenotypes"]:
            media = kbase_api.get_from_ws(pheno["media_ref"], None)
            geneko = []
            for gene in pheno["geneko_refs"]:
                geneko.append(added_cpd.split("/").pop())
            added_compounds = []
            for added_cpd in pheno["additionalcompound_refs"]:
                added_compounds.append(added_cpd.split("/").pop())
            newpheno = MSGrowthPhenotype(
                media.info.id, media, pheno["normalizedGrowth"], geneko, added_compounds
            )
            new_phenos.append(newpheno)
        growthpheno.add_phenotypes(new_phenos)
        return growthpheno

    @staticmethod
    def from_kbase_file(
        filename,
        kbase_api,
        base_media=None,
        base_uptake=0,
        base_excretion=1000,
        global_atom_limits={},
    ):
        # TSV file with the following headers:media    mediaws    growth    geneko    addtlCpd
        growthpheno = MSGrowthPhenotypes(
            base_media, base_uptake, base_excretion, global_atom_limits
        )
        headings = []
        new_phenos = []
        with open(filename) as f:
            lines = f.readlines()
            for line in lines:
                items = line.split("\t")
                if headings == None:
                    headings = items
                else:
                    data = {}
                    for i in range(0, len(items)):
                        data[headings[i]] = items[i]
                    data = FBAHelper.validate_dictionary(
                        headings,
                        ["media", "growth"],
                        {"mediaws": None, "geneko": [], "addtlCpd": []},
                    )
                    media = kbase_api.get_from_ws(data["media"], data["mediaws"])
                    id = data["media"]
                    if len(data["geneko"]) > 0:
                        id += "-" + ",".join(data["geneko"])
                    if len(data["addtlCpd"]) > 0:
                        id += "-" + ",".join(data["addtlCpd"])
                    newpheno = MSGrowthPhenotype(
                        id, media, data["growth"], data["geneko"], data["addtlCpd"]
                    )
                    new_phenos.append(newpheno)
        growthpheno.add_phenotypes(new_phenos)
        return growthpheno

    @staticmethod
    def from_ms_file(
        filename,
        base_media=None,
        base_uptake=0,
        base_excretion=100,
        global_atom_limits={},
    ):
        growthpheno = MSGrowthPhenotypes(
            base_media, base_uptake, base_excretion, global_atom_limits
        )
        df = pd.read_csv(filename)
        required_headers = ["Compounds", "Growth"]
        for item in required_headers:
            if item not in df:
                raise ValueError("Required header " + item + " is missing!")
        new_phenos = []
        for row in df.rows:
            cpds = row["Compounds"].split(";")
            id = row["Compounds"]
            if "ID" in row:
                id = row["ID"]
            geneko = []
            if "GeneKO" in row:
                geneko = row["GeneKO"].split(";")
            newpheno = MSGrowthPhenotype(id, None, row["Growth"], geneko, cpds)
            new_phenos.append(newpheno)
        growthpheno.add_phenotypes(new_phenos)
        return growthpheno

    def to_kbase_json(self,genome_ref):
        pheno_data = {
            "id": self.id,
            "name": self.name,
            "source": self.source,
            "source_id": self.source_id,
            "type": self.type,
            "phenotypes": [],
            "genome_ref": genome_ref
        }
        for pheno in self.phenotypes:
            pheno_data["phenotypes"].append({
                "id": pheno.id,
                "name": pheno.name,
                "media_ref": pheno.media.info.ref,
                "normalizedGrowth": pheno.experimental_value,
                "geneko_refs": pheno.gene_ko,
                "additionalcompound_refs": pheno.additional_compounds
            })
        return pheno_data

    def build_super_media(self):
        super_media = None
        for pheno in self.phenotypes:
            if not super_media:
                super_media = pheno.build_media()
            else:
                super_media.merge(pheno.build_media(), overwrite_overlap=False)
        return super_media

    def add_phenotypes(self, new_phenotypes):
        keep_phenos = []
        for pheno in new_phenotypes:
            if pheno.id not in self.phenotypes:
                pheno.parent = self
                keep_phenos.append(pheno)
        additions = DictList(keep_phenos)
        self.phenotypes += additions

    def baseline_objective(self, model_or_mdlutl, objective):
        """Simulates all the specified phenotype conditions and saves results
        Parameters
        ----------
        model_or_modelutl : Model | MSModelUtl
            Model to use to run the simulations
        """
        # Discerning input is model or mdlutl and setting internal links
        modelutl = model_or_mdlutl
        if not isinstance(model_or_mdlutl, MSModelUtil):
            modelutl = MSModelUtil.get(model_or_mdlutl)
        # Checking if base growth already computed
        if modelutl in self.cached_based_growth:
            if objective in self.cached_based_growth[modelutl]:
                return self.cached_based_growth[modelutl][objective]
        else:
            self.cached_based_growth[modelutl] = {}
        # Setting objective
        modelutl.objective = objective
        # Setting media
        modelutl.pkgmgr.getpkg("KBaseMediaPkg").build_package(
            self.base_media, self.base_uptake, self.base_excretion
        )
        # Adding uptake limits
        if len(self.atom_limits) > 0:
            modelutl.pkgmgr.getpkg("ElementUptakePkg").build_package(self.atom_limits)
        # Simulating
        self.cached_based_growth[modelutl][objective] = modelutl.model.slim_optimize()
        return self.cached_based_growth[modelutl][objective]

    def simulate_phenotypes(
        self,
        model_or_mdlutl,
        multiplier=3,
        add_missing_exchanges=False,
        save_fluxes=False,
        save_reaction_list=False,
        gapfill_negatives=False,
        msgapfill=None,
        test_conditions=None,
        ignore_experimental_data=False,
        flux_coefficients=None,
        recall_phenotypes=True
    ):
        """Simulates all the specified phenotype conditions and saves results
        Parameters
        ----------
        model_or_mdlutl : Model | MSModelUtl
            Model to use to run the simulations
        multiplier : double
            Indicates a multiplier to use for positive growth above the growth on baseline media
        add_missing_exchanges : bool
            Boolean indicating if exchanges for compounds mentioned explicitly in phenotype media should be added to the model automatically
        save_fluxes : bool
            Indicates if the fluxes should be saved and returned with the results
        ignore_experimental_data : bool
            Indicates if existing growth data in the phenotype set should be ignored when computing the class of a simulated phenotype
        """
        # Discerning input is model or mdlutl and setting internal links
        modelutl = model_or_mdlutl
        if not isinstance(model_or_mdlutl, MSModelUtil):
            modelutl = MSModelUtil.get(model_or_mdlutl)
        # Establishing output of the simulation method
        summary = {
            "Label": ["Accuracy", "CP", "CN", "FP", "FN", "P", "N"],
            "Count": [0, 0, 0, 0, 0, 0, 0],
        }
        data = {
            "Phenotype": [],
            "Observed objective": [],
            "Simulated objective": [],
            "Class": [],
            "Transports missing": [],
            "Gapfilled reactions": [],
            "Gapfilling score": None,
        }
        # Running simulations
        gapfilling_solutions = {}
        totalcount = 0
        datahash = {}
        for pheno in self.phenotypes:
            result = pheno.simulate(
                modelutl,
                multiplier,
                add_missing_exchanges,
                save_fluxes,
                save_reaction_list=save_reaction_list,
                ignore_experimental_data=ignore_experimental_data,
                flux_coefficients=flux_coefficients
            )
            datahash[pheno.id] = result
            data["Class"].append(result["class"])
            data["Phenotype"].append(pheno.id)
            data["Observed objective"].append(pheno.experimental_value)
            data["Simulated objective"].append(result["objective_value"])
            data["Transports missing"].append(";".join(result["missing_transports"]))
            if result["class"] == "CP":
                summary["Count"][1] += 1
                summary["Count"][0] += 1
                totalcount += 1
            elif result["class"] == "CN":
                summary["Count"][2] += 1
                summary["Count"][0] += 1
                totalcount += 1
            elif result["class"] == "FP":
                summary["Count"][3] += 1
                totalcount += 1
            elif result["class"] == "FN":
                summary["Count"][4] += 1
                totalcount += 1
            elif result["class"] == "P":
                summary["Count"][5] += 1
            elif result["class"] == "N":
                summary["Count"][6] += 1
            # Gapfilling negative growth conditions
            if gapfill_negatives and result["class"] in ["N", "FN", "CN"]:
                gapfilling_solutions[pheno] = pheno.gapfill_model_for_phenotype(
                    msgapfill,
                    test_conditions,
                    multiplier,
                    add_missing_exchanges,
                )
                if gapfilling_solutions[pheno] != None:
                    data["Gapfilling score"] = 0
                    list = []
                    for rxn_id in gapfilling_solutions[pheno]["reversed"]:
                        list.append(
                            gapfilling_solutions[pheno]["reversed"][rxn_id] + rxn_id
                        )
                        data["Gapfilling score"] += 0.5
                    for rxn_id in gapfilling_solutions[pheno]["new"]:
                        list.append(gapfilling_solutions[pheno]["new"][rxn_id] + rxn_id)
                        data["Gapfilling score"] += 1
                    data["Gapfilled reactions"].append(";".join(list))
                else:
                    data["Gapfilled reactions"].append(None)
            else:
                data["Gapfilled reactions"].append(None)
        if totalcount == 0:
            summary["Count"][0] = None
        else:
            summary["Count"][0] = summary["Count"][0] / totalcount
        sdf = pd.DataFrame(summary)
        df = pd.DataFrame(data)
        self.adjust_phenotype_calls(df)
        return {"details": df, "summary": sdf,"data":datahash}

    def adjust_phenotype_calls(self,data,baseline_objective=0.01):
        lowest = data["Simulated objective"].min()
        if baseline_objective < lowest:
            lowest = baseline_objective
        highest = data["Simulated objective"].max()
        threshold = (highest-lowest)/2+lowest
        if highest/(lowest+0.000001) < 1.5:
            threshold = highest
        grow = 0
        nogrow = 0
        change = 0
        for (i,item) in data.iterrows():
            oldclass = item["Class"]
            if item["Simulated objective"] >= threshold:
                grow += 1
                if item["Class"] == "N":
                    data.loc[i, 'Class'] = "P"
                    change += 1
                elif item["Class"] == "FN":
                    data.loc[i, 'Class'] = "CP"
                    change += 1
                elif item["Class"] == "CN":
                    data.loc[i, 'Class'] = "FP"
                    change += 1   
            else:
                nogrow += 1
                if item["Class"] == "P":
                    data.loc[i, 'Class'] = "N"
                    change += 1
                elif item["Class"] == "CP":
                    data.loc[i, 'Class'] = "FN"
                    change += 1
                elif item["Class"] == "FP":
                    data.loc[i, 'Class'] = "CN"
                    change += 1 

    def fit_model_to_phenotypes(
        self,
        msgapfill,
        multiplier,
        correct_false_positives=False,
        minimize_new_false_positives=True,
        atp_safe=True,
        integrate_results=True,
        global_gapfilling=True,
    ):

        """Simulates all the specified phenotype conditions and saves results
        Parameters
        ----------
        msgapfill : MSGapfill
            Gapfilling object used for the gapfilling process
        correct_false_positives : bool
            Indicates if false positives should be corrected
        minimize_new_false_positives : bool
            Indicates if new false positivies should be avoided
        integrate_results : bool
            Indicates if the resulting modifications to the model should be integrated
        """

        # Running simulations
        positive_growth = []
        negative_growth = []
        for pheno in self.phenotypes:
            with model:
                result = pheno.simulate(
                    modelutl,
                    multiplier,
                    add_missing_exchanges,
                    save_fluxes,
                )
                # Gapfilling negative growth conditions
                if gapfill_negatives and result["class"] in ["N", "FN", "CN"]:
                    negative_growth.append(pheno.build_media())
                elif gapfill_negatives and result["class"] in ["P", "FP", "CP"]:
                    positive_growth.append(pheno.build_media())

        # Create super media for all
        super_media = self.build_super_media()
        # Adding missing exchanges
        msgapfill.gfmodel.add_missing_exchanges(super_media)
        # Adding elemental constraints
        self.add_elemental_constraints()
        # Getting ATP tests

        # Filtering database for ATP tests

        # Penalizing database to avoid creating false positives

        # Building additional tests from current correct negatives

        # Computing base-line growth

        # Computing growth threshold

        # Running global gapfill

        # Integrating solution

    def gapfill_all_phenotypes(
        self,
        model_or_mdlutl,
        msgapfill=None,  # Needed if the gapfilling object in model utl is not initialized
        threshold=None,
        add_missing_exchanges=False,
    ):
        mdlutl = MSModelUtil.get(model_or_mdlutl)
        # if msgapfill:
        #    mdlutl.gfutl = msgapfill
        # if not mdlutl.gfutl:
        #    logger.critical(
        #        "Must either provide a gapfilling object or provide a model utl with an existing gapfilling object"
        #    )
        # media_list = []
        # for pheno in self.phenotypes:
        #
        #
        # output = mdlutl.gfutl.run_multi_gapfill(
        #    media_list,
        #    default_minimum_objective=growth_threshold
        #    target=mdlutl.primary_biomass(),
        #
        #    binary_check=False,
        #    prefilter=True,
        #    check_for_growth=True,
        # )
