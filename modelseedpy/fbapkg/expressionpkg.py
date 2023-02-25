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

    def maximize_required_functionality(self, rxnIDs):
        # optimize the respective
        self.util.add_objective(sum([self.msdb.reactions.get_by_id(rxnID).flux_expression for rxnID in rxnIDs]))
        sol = self.util.model.optimize()
        return sum([sol.fluxes[rxnID] for rxnID in rxnIDs])

    def build_package(self, ex_data, required_functionalities, minFunctionality=0.5,
                      threshold_percentile=25, reversibility=False):
        # determine the maximum flux for each required functionality
        max_req_funcs = {rxnIDs:self.maximize_required_functionality(rxnIDs) for rxnIDs in required_functionalities}
        for rxnIDs, minFlux in max_req_funcs.items():
            for rxnID in rxnIDs:
                rxn = self.msdb.reactions.get_by_id(rxnID)
                rxn.lower_bound = minFlux*minFunctionality/len(rxnIDs)
        # integrate the expression data as flux bounds
        threshold = percentile(list(ex_data.values()), threshold_percentile)
        self.coefs = {r_id: threshold - val for r_id, val in ex_data.items() if val < threshold}
        objective_coefs = {}
        for rxn in self.model.reactions:
            if rxn.id not in ex_data:
                continue
            rxn.lower_bound = ex_data[rxn.id]
            # rxn.upper_bound = ex_data[rxn.id]
            objective_coefs[rxn.forward_variable] = objective_coefs[rxn.reverse_variable] = coefs[rxn.id]
        # define the objective expression
        self.util.add_objective(sum(list(objective_coefs.keys())), "min", objective_coefs)
        return self.util.model

    def simulate(self):
        sol = self.util.model.optimize()
        # calculate the inconsistency score
        inconsistency_score = 0
        for rxn, flux in sol.fluxes.items():
            if rxn.id in self.coefs:
                inconsistency_score += flux*self.coefs[rxn.id]

    # def build_variable(self, cobra_obj, direction):
    #     pass
    #
    # def build_constraint(self, cobra_obj, reversibility):
    #     pass
