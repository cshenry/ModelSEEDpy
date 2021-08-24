import logging
import itertools
import cobra
from numpy import zeros
from itertools import combinations
import networkx
from modelseedpy.core import FBAHelper, MSGapfill
from modelseedpy.fbapkg.mspackagemanager import MSPackageManager
from modelseedpy.fbapkg.gapfillingpkg import default_blacklist

logger = logging.getLogger(__name__)

#Adding a few exception classes to handle different types of errors
class CommunityError(Exception):
    """Error in community FBA"""
    pass


class MSCommunity:

    def __init__(self,model):
        self.model = model
        self.gapfilling  = None
        self.metabolite_uptake = {}
        self.print_lp = False
        self.compartments = None
        self.production = None
        self.consumption = None
        self.solution = None
        self.suffix = ""
        self.pkgmgr = MSPackageManager.get_pkg_mgr(model)     
    
    def set_objective(self,target = "bio1",maximize = True):
        #Setting objective function
        sense = "min"
        if maximize:
            sense = "max"
        model.objective = model.problem.Objective(
            1 * model.reactions.get_by_id(target).flux_expression,
            direction=sense)
    
    def gapfill(self,media = None,target_reaction = "bio1",maximize = True,default_gapfill_templates = [],default_gapfill_models = [],test_conditions = [],reaction_scores = {},blacklist = []):
        self.set_objective(self,target,maximize)
        self.gapfilling = MSGapfill(self.model,default_gapfill_templates,default_gapfill_models,test_conditions,reaction_scores,blacklist)
        gfresults = gapfiller.run_gapfilling(media,target_reaction)
        return gapfiller.integrate_gapfill_solution(gfresults)
    
    def run(self,target = "bio1",maximize = True,pfba = True):
        self.set_objective(self,target,maximize)
        # conditionally print the LP file of the model
        if self.print_lp:
            count_iteration = 0
            file_name = self.suffix
            while exists(file_name):
                count_iteration += 1
                file_name = re.sub('(_\d)', f'_{count_iteration}', file_name)
            with open(file_name, 'w') as out:
                out.write(str(self.model.solver))
                out.close()
        #Solving model
        solution = self.model.optimize()
        if pfba:
            solution = cobra.flux_analysis.pfba(self.model)
        #Checking that an optimal solution exists
        if solution.objective_value == 0 or solution.status != 'optimal':
            logger.warning("No solution found for %s", media)
            return None
        return solution
        
    def compute_interactions(self,solution):
        # calculate the metabolic exchanges
        self.compartments = set
        self.metabolite_uptake = {}
        for rxn in self.model.reactions:
            cmp = rxn.id.split("_").pop()
            comp_index = int(comp_index[1:])
            compartments.add(comp_index)
            for metabolite in rxn.metabolites:
                if metabolite.compartment == "e0":
                    flux = solution.fluxes[rxn.id]
                    if flux != 0:
                        rate_law = rxn.metabolites[metabolite]*flux
                        self.metabolite_uptake[(metabolite.id, comp_index)] = rate_law
        # calculate cross feeding of extracellular metabolites 
        self.number_of_compartments = len(compartments)
        self.production = zeros((number_of_compartments, number_of_compartments)) 
        self.consumption = zeros((number_of_compartments, number_of_compartments))
        cross_all = []
        for rxn in self.model.reactions:
            for metabolite in rxn.metabolites:
                if metabolite.compartment == "e0":
                    # determine each directional flux rate 
                    rate_out = {compartment_number: rate for (metabolite_id, compartment_number), rate in metabolite_uptake.items() if metabolite_id == metabolite.id and rate > 0}
                    rate_in = {compartment_number: abs(rate) for (metabolite_id, compartment_number), rate in metabolite_uptake.items() if metabolite_id == metabolite.id and rate < 0}
                    # determine total directional flux rate 
                    total_in = sum(rate_in.values())
                    total_out = sum(rate_out.values())
                    max_total_rate = max(total_in, total_out)
                    # determine net flux 
                    net_flux = total_in - total_out
                    if net_flux > 0:
                        rate_out[None] = net_flux
                    if net_flux < 0:
                        rate_in[None] = abs(net_flux)
                    # establish the metabolites that partake in cross feeding 
                    for donor, rate_1 in rate_out.items():
                        if donor is not None:
                            donor_index = int(donor) - 1           
                            for receiver, rate_2 in rate_in.items():
                                if receiver is not None:
                                    receiver_index = int(receiver) - 1

                                    # assign calculated feeding rates to the production and consumption matrices
                                    rate = rate_1 * rate_2 / max_total_rate
                                    self.production[donor_index][receiver_index] += rate
                                    self.consumption[receiver_index][donor_index] += rate
    
    def constrain(self,media = None,element_uptake_limit = None, kinetic_coeff = None, abundances = None, msdb_path_for_fullthermo = None):
        # applying media constraints
        self.pkgmgr.getpkg("KBaseMediaPkg").build_package(media)
        # applying uptake constraints
        element_contraint_name = ''
        if element_uptake_limit is not None:
            self.pkgmgr.getpkg("ElementUptakePkg").build_package(element_uptake_limit)
            element_contraint_name = 'eup'
        # applying kinetic constraints
        kinetic_contraint_name = ''
        if kinetic_coeff is not None:
            self.pkgmgr.getpkg("CommKineticPkg").build_package(kinetic_coeff,abundances)
            kinetic_contraint_name = 'ckp'
        # applying FullThermo constraints
        thermo_contraint_name = ''
        if msdb_path_for_fullthermo is not None:
            self.pkgmgr.getpkg("FullThermoPkg").build_package({'modelseed_path':msdb_path_for_fullthermo})
            thermo_contraint_name = 'ftp'
        self.suffix = '_'.join([self.model.id, thermo_contraint_name, kinetic_contraint_name, element_contraint_name, str(count_iteration)])+".lp"
        
    def visualize(self, graph = True, table = True):
        ''' VISUALIZE FLUXES ''' 
        # graph the community network
        if graph:
            graph = networkx.Graph()
            for num in self.compartments:
                graph.add_node(num)
            for com in combinations(self.compartments, 2):
                species_1 = int(com[0])-1
                species_2 = int(com[1])-1

                interaction_net_flux = round(self.production[species_1][species_2] - self.consumption[species_1][species_2], 4)
                if species_1 < species_2:
                    graph.add_edge(com[0],com[1],flux = interaction_net_flux)
                elif species_1 > species_2:
                    graph.add_edge(com[0],com[1],flux = -interaction_net_flux)

            pos = networkx.circular_layout(graph)
            networkx.draw_networkx(graph,pos)
            labels = networkx.get_edge_attributes(graph,'flux')
            networkx.draw_networkx_edge_labels(graph,pos,edge_labels=labels)
        
        # view the cross feeding matrices
        if table:
            from pandas import DataFrame as df

            species = [num+1 for num in range(len(self.production))]

            print('\nProduction matrix:')
            prod_df = df(self.production)
            prod_df.index = prod_df.columns = species
            prod_df.index.name = 'Donor'
            print(prod_df)

            print('\n\nConsumption matrix:')
            cons_df = df(self.consumption)
            cons_df.index = cons_df.columns = species
            cons_df.index.name = 'Receiver'
            print(cons_df)

    @staticmethod
    def community_fba(model,media = None,target_reaction = "bio1",maximize = True,element_uptake_limit = None, kinetic_coeff = None, abundances = None, msdb_path_for_fullthermo = None):
        community = MSCommunity(model)
        community.constrain(media,element_uptake_limit, kinetic_coeff, abundances, msdb_path_for_fullthermo)
        self.solution = community.run(target,maximize)
        community.compute_interactions(self.solution)
        community.visualize()
        return community