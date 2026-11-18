# -*- coding: utf-8 -*-
import logging
from typing import Tuple
from modelseedpy.helpers import get_template, get_classifier
from modelseedpy.core.mstemplate import MSTemplateBuilder, MSTemplate
from modelseedpy.core.msgenome import MSGenome
from modelseedpy.core.msbuilder import MSGenomeClass

logger = logging.getLogger(__name__)

DEFAULT_CLASSIFIER = "knn_ACNP_RAST_filter_01_17_2023"

# genome class -> (core template, genome-scale template), the same choice
# MSBuilder.auto_select_template makes
TEMPLATE_IDS = {
    MSGenomeClass.N: ("template_core", "template_gram_neg"),
    MSGenomeClass.C: ("template_core", "template_gram_neg"),
    MSGenomeClass.A: ("template_core", "template_gram_neg"),
    MSGenomeClass.P: ("template_core", "template_gram_pos"),
}


class MSPredict:
    """Predict a genome's class with the packaged classifier and pick its templates.

    The classifier (data/ml) was trained on RAST functional roles, so the genome's
    features need RAST ontology terms.
    """

    def __init__(self, classifier=DEFAULT_CLASSIFIER):
        logger.debug(f"Initializing MSPredict with classifier: {classifier}")
        self.genome_classifier = get_classifier(classifier)

    def predict(self, genome: MSGenome) -> MSGenomeClass:
        """
        Predicts the genome class for a given genome.

        :param genome: MSGenome - The genome to predict the class for.
        :return: MSGenomeClass - The genome class for the given genome.
        """
        genome_class_str = str(self.genome_classifier.classify(genome))
        logger.debug(f"Predicted genome class: {genome_class_str}")
        if genome_class_str not in MSGenomeClass.__members__:
            raise ValueError(f"Unknown genome class: {genome_class_str}")
        return MSGenomeClass[genome_class_str]

    @staticmethod
    def auto_select_template(
        genome_class: MSGenomeClass,
    ) -> Tuple[MSTemplate, MSTemplate]:
        """
        Builds the templates for a given genome class.

        :param genome_class: MSGenomeClass - The genome class to select the templates for.
        :return: Tuple[MSTemplate, MSTemplate] - The core and the genome-scale template.
        """
        if genome_class not in TEMPLATE_IDS:
            raise ValueError(f"Unknown genome class: {genome_class}")
        template_core_id, template_genome_scale_id = TEMPLATE_IDS[genome_class]
        template_core = MSTemplateBuilder.from_dict(
            get_template(template_core_id)
        ).build()
        template_genome_scale = MSTemplateBuilder.from_dict(
            get_template(template_genome_scale_id)
        ).build()
        return template_core, template_genome_scale
