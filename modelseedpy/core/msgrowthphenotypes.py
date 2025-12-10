# -*- coding: utf-8 -*-
import pandas as pd
import logging
import cobra
from cobra.core.dictlist import DictList
from modelseedpy.core.msmedia import MSMedia
from modelseedpy.fbapkg.mspackagemanager import MSPackageManager
from modelseedpy.fbapkg.objectivepkg import ObjectiveData
from modelseedpy.core.msmodelutl import MSModelUtil
from modelseedpy.core.msgapfill import MSGapfill
from modelseedpy.core.msmedia import MSMedia

logger = logging.getLogger(__name__)
logger.setLevel(
    logging.INFO
)  # When debugging - set this to INFO then change needed messages below from DEBUG to INFO

zero_threshold = 0.0000001

class MSGrowthPhenotype:
    def __init__(
        self,
        id,
        base_media=None,
        experimental_value=None,
        experimental_value_is_binary=False,
        knockouts=[],
        additional_compounds={},
        primary_compounds=[],
        name=None,
        gene_association_scores={},
        objective=ObjectiveData.from_string("MAX{bio1}"),
        target_element=None,
        target_element_limit=10,
        parent=None
    ):
        self.id = id
        self.name = name
        if name == None:
            self.name = self.id
        self.experimental_value = experimental_value
        self.experimental_value_is_binary = experimental_value_is_binary
        self.base_media = base_media
        self.knockouts = knockouts
        self.additional_compounds = additional_compounds
        self.primary_compounds = primary_compounds
        self.target_element = target_element
        self.gene_association_scores = gene_association_scores
        self.objective = objective
        self.parent = parent

    def to_dict(self, media_output_type="complete"):
        """
        Convert MSGrowthPhenotype to a dictionary.

        Parameters:
            media_output_type (str): Output type for media serialization.
                Options: "minimal", "bounds", "complete" (default: "complete")

        Returns:
            dict: Dictionary representation of the phenotype
        """
        output = {
            'id': self.id,
            'name': self.name,
            'experimental_value': self.experimental_value,
            'experimental_value_is_binary': self.experimental_value_is_binary,
            'knockouts': list(self.knockouts) if self.knockouts else [],
            'additional_compounds': dict(self.additional_compounds) if self.additional_compounds else {},
            'primary_compounds': list(self.primary_compounds) if self.primary_compounds else [],
            'gene_association_scores': dict(self.gene_association_scores) if self.gene_association_scores else {},
            'target_element': self.target_element,
            'target_element_limit': getattr(self, 'target_element_limit', 10),
            'objective': self.objective.to_string() if self.objective else None,
        }

        # Serialize base_media if present
        if self.base_media:
            output['base_media'] = self.base_media.to_dict(output_type=media_output_type)
            output['base_media_id'] = self.base_media.id
            output['base_media_name'] = self.base_media.name
            output['base_media_ref'] = self.base_media.media_ref

        return output

    @staticmethod
    def from_dict(data, parent=None):
        """
        Create MSGrowthPhenotype from a dictionary.

        Parameters:
            data (dict): Dictionary containing phenotype data
            parent (MSGrowthPhenotypes, optional): Parent phenotype set

        Returns:
            MSGrowthPhenotype: A new MSGrowthPhenotype instance
        """
        # Reconstruct base_media if present
        base_media = None
        if 'base_media' in data and data['base_media']:
            base_media = MSMedia.from_dict(data['base_media'])
            base_media.id = data.get('base_media_id', 'media')
            base_media.name = data.get('base_media_name', '')
            base_media.media_ref = data.get('base_media_ref')

        # Reconstruct objective
        objective = None
        if 'objective' in data and data['objective']:
            objective = ObjectiveData.from_string(data['objective'])

        return MSGrowthPhenotype(
            id=data.get('id'),
            base_media=base_media,
            experimental_value=data.get('experimental_value'),
            experimental_value_is_binary=data.get('experimental_value_is_binary', False),
            knockouts=data.get('knockouts', []),
            additional_compounds=data.get('additional_compounds', {}),
            primary_compounds=data.get('primary_compounds', []),
            name=data.get('name'),
            gene_association_scores=data.get('gene_association_scores', {}),
            objective=objective,
            target_element=data.get('target_element'),
            target_element_limit=data.get('target_element_limit', 10),
            parent=parent
        )

    def build_media(self):
        """Builds media object to use when simulating the phenotype
        Parameters
        ----------
        include_base_media : bool
            Indicates whether to include the base media for the phenotype set in the formulation
        """
        cpd_hash = {}
        if self.base_media:
            cpd_hash = self.base_media.to_dict()       
        for cpd in self.additional_compounds:
            cpd_hash[cpd] = self.additional_compounds[cpd]
        for cpd in self.primary_compounds:
            if cpd not in cpd_hash:
                cpd_hash[cpd] = 100 # Default flux for primary compounds
        full_media = MSMedia.from_dict(cpd_hash)
        if self.parent and self.parent.base_media:
            print("Adding parent base media to phenotype media")
            full_media.merge(self.parent.base_media, overwrite_overlap=False)
        return full_media

    def configure_model_for_phenotype(self,model_or_mdlutl,add_missing_exchanges=True):
        """Configures the model to run this phenotype
        Parameters
        ----------
        model_or_modelutl : Model | MSModelUtl
            Model to use to run the simulations
        """
        output = {"baseline_objective":0.01}
        #Translating model is not MSModelUtil
        modelutl = model_or_mdlutl
        if not isinstance(model_or_mdlutl, MSModelUtil):
            modelutl = MSModelUtil.get(model_or_mdlutl)
        #Setting the phenotype objective
        modelutl.pkgmgr.getpkg("ObjectivePkg").build_package(
            objective_or_string=self.objective,
            objective_name=self.name,
            set_objective=True
        )
        # Setting media in model
        modelutl.pkgmgr.getpkg("KBaseMediaPkg").build_package(
            self.build_media(), self.parent.base_uptake, self.parent.base_excretion
        )
        # Adding transport reactions
        if add_missing_exchanges:
            ex_output = modelutl.add_missing_exchanges(self.build_media())
            output["missing_transports"] = ex_output
        # Adding elemental constraints
        if self.target_element:
            print("Target element: "+self.target_element)
            #Computing baseline growth
            reaction_exceptions = []
            modelutl.pkgmgr.getpkg("ElementUptakePkg").build_package(
                {self.target_element:self.target_element_limit}, exception_reactions=reaction_exceptions
            )
            output["baseline_objective"] = modelutl.model.slim_optimize()
            #Resetting elemental constraints with exception reactions
            exchange_hash = modelutl.exchange_hash()
            for item in self.primary_compounds:
                if item in exchange_hash:
                    for rxn in exchange_hash[item]:
                        if rxn not in reaction_exceptions:
                            reaction_exceptions.append(rxn)
            modelutl.pkgmgr.getpkg("ElementUptakePkg").clear()
            modelutl.pkgmgr.getpkg("ElementUptakePkg").build_package(
                {self.target_element:self.target_element_limit}, exception_reactions=reaction_exceptions
            )
        return output

    def simulate(
        self,
        model_or_mdlutl,
        add_missing_exchanges=False,
        growth_threshold=0.01,
        gapfilling=False,
        msgapfill=None,
        annoont=None,
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
        output = {
            "objective_value": 0,
            "experimental_value": self.experimental_value,
            "class": "N",
            "reactions":None,
            "gfreactions":None,
            "gapfill_count":0,
            "gapfill_count_with_genes":0,
            "reaction_count":0,
            "fluxes":None,
            "objective_string":self.objective.to_string()
        }
        #Translating model is not MSModelUtil
        modelutl = model_or_mdlutl
        if not isinstance(model_or_mdlutl, MSModelUtil):
            modelutl = MSModelUtil.get(model_or_mdlutl)
        target_mdlutl = modelutl
        #Switching target model to msgapfill if gapfilling is True
        if gapfilling:
            if msgapfill == None:
                logger.warning(
                    "MSGapfill must be provided in order to run phenotype gapfilling analysis!"
                )
                return None
            target_mdlutl = msgapfill.gfmodelutl
        #Setting the default score for all model reactions to 0.1
        reaction_scores = {}
        for rxn in target_mdlutl.model.reactions:
            reaction_scores[rxn.id] = {}
            if rxn.id in modelutl.model.reactions:
                
                if modelutl.model.reactions.get_by_id(rxn.id).upper_bound > 0:
                    reaction_scores[rxn.id][">"] = 0.01
                else:
                    reaction_scores[rxn.id][">"] = 2
                if modelutl.model.reactions.get_by_id(rxn.id).lower_bound > 0:
                    reaction_scores[rxn.id]["<"] = 0.01
                else:
                    reaction_scores[rxn.id]["<"] = 2
            else:
                reaction_scores[rxn.id][">"] = 2
                reaction_scores[rxn.id]["<"] = 2
        #Computing gene associations and reaction scores from annotation ontology
        rxn_gene_hash = {}
        if annoont != None:
            rxn_gene_hash = annoont.get_reaction_gene_hash(feature_type="gene")
            direction_list = [">","<"]
            for rxn in rxn_gene_hash:
                rxnid = rxn+"_c0"
                if rxnid not in reaction_scores:
                    reaction_scores[rxnid] = {">": 2, "<": 2}
                for direction in direction_list:
                    current_score = reaction_scores[rxnid][direction]
                    rxn_score = None
                    for gene in rxn_gene_hash[rxn]:
                        new_score = rxn_gene_hash[rxn][gene]["probability"]
                        if gene in self.gene_association_scores:
                            new_score = -1*(1-self.gene_association_scores[gene])*new_score
                        if rxn_score == None or (new_score < 0 and new_score < rxn_score) or (current_score > 0.1 and rxn_score > 0 and new_score > rxn_score):
                            rxn_score = new_score
                    if rxn_score != None:
                        if rxn_score > 0:
                            rxn_score = 1+rxn_score
                        reaction_scores[rxnid][direction] = rxn_score
        #Configuring the model for the phenotype
        configuration_output = self.configure_model_for_phenotype(target_mdlutl,add_missing_exchanges=add_missing_exchanges)
        output["missing_transports"] = configuration_output["missing_transports"]
        output["baseline_objective"] = configuration_output["baseline_objective"]
        multiplier = 3
        with target_mdlutl.model:
            #Implementing knockouts
            for item in self.knockouts:
                if item in target_mdlutl.model.genes:
                    geneobj = target_mdlutl.model.genes.get_by_id(item)
                    geneobj.knock_out()
                elif item in target_mdlutl.model.reactions:
                    rxnobj = target_mdlutl.model.reactions.get_by_id(item)
                    rxnobj.knock_out()
                else:
                    logger.warning("Gene or reaction "+item+" not found in model")
            #Print model LP for debugging
            #modelutl.printlp(path="LP_files/",filename=self.id,print=True)
            #Getting objective value
            solution = target_mdlutl.model.optimize()
            print(self.id,solution.status,solution.objective_value)
            modelutl.printlp(path="LP_files/",filename="Base-"+self.id,print=True)
            output["objective_value"] = solution.objective_value
            if output["objective_value"] < 0.000001:
                output["objective_value"] = 0
                if gapfilling:
                    output["status"] = "gapfilling failed"
                else:
                    output["status"] = "no growth without gapfilling"
            else:
                output["class"] = "P"
                target_mdlutl.model.reactions.get_by_id("bio1").lower_bound = output["objective_value"] * multiplier
                original_objective = target_mdlutl.model.objective
                coefobj = target_mdlutl.model.problem.Objective(0, direction="min")
                target_mdlutl.model.objective = coefobj
                obj_coef = {}
                direction_list = [">","<"]
                for rxn in reaction_scores:
                    if rxn in target_mdlutl.model.reactions:
                        rxnobj = target_mdlutl.model.reactions.get_by_id(rxn)
                        for direction in direction_list:
                            if direction == ">":
                                obj_coef[rxnobj.forward_variable] = reaction_scores[rxn][direction]
                            elif direction == "<":
                                obj_coef[rxnobj.reverse_variable] = reaction_scores[rxn][direction]
                coefobj.set_linear_coefficients(obj_coef)
                modelutl.printlp(path="LP_files/",filename=self.id,print=True)
                solution = target_mdlutl.model.optimize()
                target_mdlutl.model.objective = original_objective
                target_mdlutl.model.reactions.get_by_id("bio1").lower_bound = 0
                #Processing solution
                output["fluxes"] = {}
                output["reactions"] = []
                output["gfreactions"] = {}
                for rxn in target_mdlutl.model.reactions:
                    if rxn.id in solution.fluxes:
                        flux = solution.fluxes[rxn.id]
                        if abs(flux) > 0.000001:
                            output["fluxes"][rxn.id] = flux
                            if rxn.id[0:3] != "bio" and rxn.id[0:3] != "EX_" and rxn.id[0:3] != "DM_" and rxn.id[0:3] != "SK":
                                output["reaction_count"] += 1
                                output["reactions"].append(rxn.id)
                                if rxn.id not in modelutl.model.reactions or (flux < -0.000001 and modelutl.model.reactions.get_by_id(rxn.id).lower_bound == 0) or (flux > 0.000001 and modelutl.model.reactions.get_by_id(rxn.id).upper_bound == 0):
                                    output["gapfill_count"] += 1
                                    output["gfreactions"][rxn.id] = None
                                    if rxn.id in rxn_gene_hash and len(rxn_gene_hash[rxn.id]) > 0:
                                        output["gfreactions"][rxn.id] = list(rxn_gene_hash[rxn.id].keys())
                                        output["gapfill_count_with_genes"] += 1
        # Determining phenotype class
        multiplier = 3
        ignore_experimental_data = False
        if output["objective_value"] != None and output["objective_value"] >= output["baseline_objective"] * multiplier:
            output["postive"] = True
            if self.experimental_value == None or ignore_experimental_data:
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
        # Check if base_media is a MSMedia object
        if not isinstance(base_media, MSMedia) and base_media is not None:
            base_media = MSMedia.from_kbase_object(base_media)
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

    def to_dict(self, media_output_type="complete"):
        """
        Convert MSGrowthPhenotypes to a dictionary.

        This function serializes the entire phenotype set including all media objects,
        allowing the phenotype set to be saved locally and restored later without
        needing to re-fetch from KBase.

        Parameters:
            media_output_type (str): Output type for media serialization.
                Options: "minimal", "bounds", "complete" (default: "complete")

        Returns:
            dict: Dictionary representation of the phenotype set
        """
        output = {
            'id': self.id,
            'name': self.name,
            'source': self.source,
            'source_id': self.source_id,
            'type': self.type,
            'base_uptake': self.base_uptake,
            'base_excretion': self.base_excretion,
            'atom_limits': dict(self.atom_limits) if self.atom_limits else {},
        }

        # Serialize base_media if present
        if self.base_media:
            output['base_media'] = self.base_media.to_dict(output_type=media_output_type)
            output['base_media_id'] = self.base_media.id
            output['base_media_name'] = self.base_media.name
            output['base_media_ref'] = self.base_media.media_ref

        # Serialize all phenotypes
        output['phenotypes'] = []
        for pheno in self.phenotypes:
            output['phenotypes'].append(pheno.to_dict(media_output_type=media_output_type))

        return output

    @staticmethod
    def from_dict(data):
        """
        Create MSGrowthPhenotypes from a dictionary.

        This function reconstructs the entire phenotype set from a dictionary,
        including all media objects. Use this to load a phenotype set that was
        previously saved using to_dict().

        Parameters:
            data (dict): Dictionary containing phenotype set data

        Returns:
            MSGrowthPhenotypes: A new MSGrowthPhenotypes instance
        """
        # Reconstruct base_media if present
        base_media = None
        if 'base_media' in data and data['base_media']:
            base_media = MSMedia.from_dict(data['base_media'])
            base_media.id = data.get('base_media_id', 'media')
            base_media.name = data.get('base_media_name', '')
            base_media.media_ref = data.get('base_media_ref')

        # Create the phenotype set
        growthpheno = MSGrowthPhenotypes(
            base_media=base_media,
            base_uptake=data.get('base_uptake', 0),
            base_excretion=data.get('base_excretion', 1000),
            global_atom_limits=data.get('atom_limits', {}),
            id=data.get('id'),
            name=data.get('name'),
            source=data.get('source'),
            source_id=data.get('source_id'),
            type=data.get('type')
        )

        # Reconstruct all phenotypes
        new_phenos = []
        for pheno_data in data.get('phenotypes', []):
            newpheno = MSGrowthPhenotype.from_dict(pheno_data, parent=growthpheno)
            new_phenos.append(newpheno)

        growthpheno.add_phenotypes(new_phenos)
        return growthpheno

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
            msmedia = MSMedia.from_kbase_object(media)
            newpheno = MSGrowthPhenotype(
                msmedia.id,name=msmedia.name, base_media=msmedia, experimental_value=pheno["normalizedGrowth"], knockouts=geneko, additional_compounds=added_compounds,parent=growthpheno
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
                    msmedia = MSMedia(media.id, name=media.name)
                    msmedia.mediacompounds = media.mediacompounds
                    id = data["media"]
                    if len(data["geneko"]) > 0:
                        id += "-" + ",".join(data["geneko"])
                    if len(data["addtlCpd"]) > 0:
                        id += "-" + ",".join(data["addtlCpd"])
                    newpheno = MSGrowthPhenotype(
                        id, msmedia, data["growth"], data["geneko"], data["addtlCpd"]
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
                "media_ref": pheno.base_media.media_ref,
                "normalizedGrowth": pheno.experimental_value,
                "geneko_refs": pheno.knockouts,
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
        datahash = {"summary": {}}
        for pheno in self.phenotypes:
            result = pheno.simulate(
                modelutl,
                add_missing_exchanges=add_missing_exchanges
            )
            datahash[pheno.id] = result
            data["Class"].append(result["class"])
            data["Phenotype"].append(pheno.id)
            data["Observed objective"].append(pheno.experimental_value)
            data["Simulated objective"].append(result["objective_value"])
            data["Transports missing"].append(";".join(result["missing_transports"]))
            if result["class"] == "CP":
                summary["Count"][1] += 1
                summary["Count"][5] += 1
                summary["Count"][0] += 1
                totalcount += 1
            elif result["class"] == "CN":
                summary["Count"][2] += 1
                summary["Count"][0] += 1
                summary["Count"][6] += 1
                totalcount += 1
            elif result["class"] == "FP":
                summary["Count"][3] += 1
                summary["Count"][5] += 1
                totalcount += 1
            elif result["class"] == "FN":
                summary["Count"][4] += 1
                summary["Count"][6] += 1
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
        datahash["summary"]["accuracy"] = summary["Count"][0]
        datahash["summary"]["CP"] = summary["Count"][1]
        datahash["summary"]["CN"] = summary["Count"][2]
        datahash["summary"]["FP"] = summary["Count"][3]
        datahash["summary"]["FN"] = summary["Count"][4]
        datahash["summary"]["P"] = summary["Count"][5]
        datahash["summary"]["N"] = summary["Count"][6]
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
