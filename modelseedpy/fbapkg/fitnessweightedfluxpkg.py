# -*- coding: utf-8 -*-

from __future__ import absolute_import

import logging
from optlang.symbolics import Zero
from modelseedpy.fbapkg.basefbapkg import BaseFBAPkg

logger = logging.getLogger(__name__)


def penalty_direction_values(penalty):
    """Return (forward, reverse) penalty values.

    A penalty is either a scalar (same weight both directions) or a dict
    {">": forward, "<": reverse}.
    """
    if isinstance(penalty, dict):
        return penalty.get(">"), penalty.get("<")
    return penalty, penalty


def validate_penalties(penalties):
    """Raise ValueError if any penalty direction is missing or not strictly positive.

    A zero penalty would let that reaction carry flux, including loop flux, for free.
    """
    for rxn_id, penalty in penalties.items():
        forward, reverse = penalty_direction_values(penalty)
        for direction, value in ((">", forward), ("<", reverse)):
            if value is None or value <= 0:
                raise ValueError(
                    "penalties must be strictly > 0 (reaction "
                    + str(rxn_id)
                    + " direction "
                    + direction
                    + " got "
                    + str(value)
                    + ")"
                )


class FitnessWeightedFluxPkg(BaseFBAPkg):
    """Objective package: minimise sum_r (p_fwd[r] * v_fwd[r] + p_rev[r] * v_rev[r]).

    Uses cobra's own forward_variable / reverse_variable split, so no variables or
    constraints are added; build_package only replaces the model objective. With strictly
    positive penalties the minimiser never runs both directions of a reaction, so the
    objective equals sum_r p[r] * |v[r]| at the optimum. Reactions without a penalty get a
    zero coefficient (free with respect to this objective).
    """

    def __init__(self, model):
        BaseFBAPkg.__init__(self, model, "fitness weighted flux", {}, {})

    def build_package(self, penalties):
        """Install the weighted minimum-flux objective.

        Parameters
        ----------
        penalties : dict
            {reaction_id: penalty}, where penalty is a positive scalar or a dict
            {">": forward, "<": reverse} with positive values.

        Returns
        -------
        optlang Objective
        """
        validate_penalties(penalties)
        self.parameters["penalties"] = penalties
        objective = self.model.problem.Objective(Zero, direction="min")
        coef = {}
        priced = 0
        for reaction in self.model.reactions:
            if reaction.id not in penalties:
                continue
            forward, reverse = penalty_direction_values(penalties[reaction.id])
            coef[reaction.forward_variable] = forward
            coef[reaction.reverse_variable] = reverse
            priced += 1
        self.model.objective = objective
        objective.set_linear_coefficients(coef)
        logger.debug(
            "FitnessWeightedFluxPkg: priced %d of %d reactions",
            priced,
            len(self.model.reactions),
        )
        return objective
