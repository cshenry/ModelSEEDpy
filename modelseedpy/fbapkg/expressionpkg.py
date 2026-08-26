from modelseedpy.fbapkg.basefbapkg import BaseFBAPkg
from modelseedpy.core.msmodelutl import MSModelUtil
from modelseedpy.biochem import from_local
from numpy import percentile


class ExpressionPkg(BaseFBAPkg):
    def __init__(self, model, msdb_path):
        BaseFBAPkg.__init__(
            self,
            model=model,
            name="expression",
            variable_types={"ex": "data"},
            constraint_types={
                "fu": "reaction",
                "ru": "reaction",
                "exclusion": "none",
                "urev": "reaction",
            },
        )
        self.util = MSModelUtil(self.model)
        self.msdb = from_local(msdb_path)

    def maximize_functionality(self, rxnIDs):
        # the default objective of biomass is probably sufficient
        self.util.add_objective(sum([self.msdb.reactions.get_by_id(rxnID).flux_expression for rxnID in rxnIDs]))
        sol = self.util.model.optimize()
        return sum([sol.fluxes[rxnID] for rxnID in rxnIDs])

    def build_gimme(self, ex_data, required_functionalities, minFunctionality=0.5, threshold_percentile=25):
        # determine the maximum flux for each required functionality
        required_functionalities = required_functionalities or self.util.bio_rxns_list()
        max_req_funcs = {list(rxnIDs): self.maximize_functionality(rxnIDs) for rxnIDs in required_functionalities}
        for rxnIDs, minFlux in max_req_funcs.items():
            for rxnID in rxnIDs:
                rxn = self.util.model.reactions.get_by_id(rxnID)
                rxn.lower_bound = minFlux*minFunctionality/len(rxnIDs)
        # integrate the expression data as flux bounds
        threshold = percentile(list(ex_data.values()), threshold_percentile)
        # The < ex_data > expression data object must be pre-processed into
        self.coefs = {r_id: threshold - val for r_id, val in ex_data.items() if val < threshold}
        objective_coefs = {}
        for rxn in self.util.model.reactions:
            if rxn.id not in ex_data:  continue
            rxn.lower_bound = ex_data[rxn.id]
            # rxn.upper_bound = ex_data[rxn.id]
            objective_coefs[rxn.forward_variable] = objective_coefs[rxn.reverse_variable] = self.coefs[rxn.id]
        # define the objective expression
        self.util.add_objective(sum(list(objective_coefs.keys())), "min", objective_coefs)
        return self.util.model

    def build_eFlux(self, ex_data):
        max_ex_data = max(ex_data.values())
        for rxnID, flux in ex_data:
            try:  rxn = self.model.reactions.get_by_id(rxnID)
            except:  continue
            rxn.lower_bound, rxn.upper_bound = (-flux/max_ex_data, flux/max_ex_data)

    def simulate(self):
        sol = self.util.model.optimize()
        # calculate the inconsistency score
        inconsistency_score = 0
        for rxn, flux in sol.fluxes.items():
            if rxn.id in self.coefs:  inconsistency_score += flux*self.coefs[rxn.id]
        return inconsistency_score
