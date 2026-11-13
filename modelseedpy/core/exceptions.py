# -*- coding: utf-8 -*-

# Adding a few exception classes to handle different types of errors in a central file
class ModelSEEDError(Exception):
    """Error in ModelSEED execution logic"""

    pass


class FeasibilityError(Exception):
    """Error in FBA formulation"""

    def __init__(self, message):
        super(FeasibilityError, self).__init__(message)


# PackageError is defined in mspackagemanager to avoid circular imports
# Import it here for backwards compatibility
from modelseedpy.fbapkg.mspackagemanager import PackageError

class GapfillingError(Exception):
    """Error in model gapfilling"""
    pass

class ParameterError(Exception):
    """Error in a parameterization"""
    pass 

class ObjectAlreadyDefinedError(Exception):
    pass

class NoFluxError(Exception):
    """Error for FBA solutions"""
    pass

class ObjectiveError(Exception):
    """Erroneous assignment of a secondary objective via a constraint"""
    pass

class ModelError(Exception):
    """Errors in a model that corrupt the simulation"""
    pass


class ObjectError(Exception):
    """Error in the construction of a base KBase object"""
    pass
