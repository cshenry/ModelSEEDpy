mscommphitting
--------------------------

+++++++++++++++++++++++++
MSCommPhitting()
+++++++++++++++++++++++++

This class contains the functions that load and parameterize experimental data, define a linear problem for the defined system with the parameterized data, simulates the LP, and graphically the results:

.. code-block:: python

 from modelseedpy.community import MSCommPhitting
 mscommfit = MSCommPhitting(msdb_path, community_members: dict=None, fluxes_df=None, 
                            growth_df=None, carbon_conc=None, media_conc=None, 
                            experimental_metadata=None, base_media=None, solver: str = "glpk", 
                            all_phenotypes=True, data_paths: dict = None, 
                            species_abundances: str = None, carbon_conc_series: dict = None,
                            ignore_trials: Union[dict, list] = None, ignore_timesteps: list = None, 
                            species_identities_rows=None, significant_deviation: float = 2, 
                            extract_zip_path: str = None)

The member models and experimental data can be parsed and parameterized or the processed files of experimental data can be passed in the class initialization. The former option is enacted by providing the ``community_members`` argument or when one of the ``fluxes_df`` and ``growth_df`` arguments are missing; the latter option is enacted otherwise.


- *msdb_path* ``str``: the path to the ModelSEED Database GitHub repository, which is loaded and referenced by the model. This is the only ubiquitously required argument.
- *community_members* ``dict``: a description of the member models and phenotypes in the simulated community. A community of *E. coli* (Acetate and Maltose phenotypes) and *Pseudomonas fluorescens* (Acetate and 4-Hydroxybenzoate phenotypes) would be expressed by the following block, where ``ecoli`` and ``pf`` denote the COBRA model objects and the list keys with "consumed" and "excreted" describe the set of metabolites that are consumed or excreted for the given growth phenotype, respectively.

.. code-block:: json

 {
   ecoli: {
     "name": "ecoli", 
     "phenotypes": {
       "Maltose": {"consumed":["cpd00179"], "excreted":["cpd00029"]},
       "Acetate": {"consumed":["cpd00029"]},
     }
 },
   pf: {
   	 "name": "pf",
     "phenotypes": {
       "Acetate": {"consumed":["cpd00029"]},
       "4-Hydroxybenzoate": {"consumed":["cpd00136"]}
     }
   }
 }

- *fluxes_df*  ``Pandas DataFrame``: a DataFrame that consists of the metabolic flux profile for each phenotype that is described in ``community_members`` and will be simulated by CommPhiting. Each column is a separate phenotype, each row is an exchange reaction, and each element is the flux of the exchange reaction for the respective phenotype. This argument offers an opportunity to save compute time by loading a defined DataFrame from a previous simulation.
- *growth_df*  ``Pandas DataFrame``: a DataFrame that contains parsed and organized experimental data to which the model will fit. The DataFrame is indexed by ``short_codes`` that concisely describe the experiment, while the ``trial_IDs`` fields offer more detail about the trial, including the relative abundances of each member and the initial *mM* concentrations of all pertinent compounds delimited by ``-`` hyphens. This argument offers an opportunity to save compute time by loading a defined DataFrame from a previous simulation.
- *carbon_conc* ``dict``: the concentrations (``values``) of carbon sources as ModelSEED IDs (``keys``) in the media, denoted by either ``columns`` or ``rows`` for the dimension in the experimental well-plate where the specified concentration varies.

.. code-block:: json

 {
 "rows": {
    "cpd00136": {"B":0, "C": 0, "D": 1, "E": 1, "F": 4, "G": 4},
    "cpd00179": {"B":5, "C": 5, "D":5, "E": 5, "F": 5, "G": 5},
  },
 "columns": {
    "cpd00029": {2:100, 3: 50, 4: 25, 5: 12.5, 6: 6.25, 7: 3}
  }
 }

- *media_conc* ``dict``: the mM concentration of each media component indexed by its ModelSEED ID.
- *experimental_metadata* ``Pandas DataFrame``: a DataFrame that consists of metadata for the experiments, indexed by the ``short_codes``. The ``trial_IDs`` column emulates that of the ``growth_df`` DataFrame. The a ``additional_compounds`` column lists the chemicals, and their initial and final mM concentrations, that augment the media defined in the ``base_media`` column. The ``strains`` column lists the community members and their respective relative abundances (an abbreviated form of this information is provided in the ``trial_IDs`` column). The ``date`` column provides the date when the experiment occurred.
- *base_media* ``ModelSEEDpy Media``: a media object that is parsed to acquire the concentration for each component in the media, and can therefore supplement the omission of the ``media_conc`` argument.
- *solver* ``str``: the Linear Programming solver that will be used to solve the constructed problem. The open-source GLPK solveris used by default, to accommodate the greatest number of users.
- *all_phenotypes* ``bool``: specifies whether all phenotypes for the respective members will be defined and simulated.
- *data_paths* ``dict``: the local path to the data spreadsheet and the identification of pertinent content in the worksheets:

.. code-block:: json

 {
    "path":"data/Jeffs_data/PF-EC 4-29-22 ratios and 4HB changes.xlsx", 
    "Raw OD(590)":"OD", 
    "mNeonGreen":"pf", 
    "mRuby":"ecoli"
 }

- *species_abundance* ``dict``: the relative abundances of all members in the community for each column in the experimental well-plates:

.. code-block:: json

 {
    1:{"ecoli":0, "pf":1},
    2:{"ecoli":1, "pf":50},
    3:{"ecoli":1, "pf":20},
    4:{"ecoli":1, "pf":10},
    5:{"ecoli":1, "pf":3},
    6:{"ecoli":1, "pf":1},
    7:{"ecoli":3, "pf":1},
    8:{"ecoli":10, "pf":1},
    9:{"ecoli":20, "pf":1},
    10:{"ecoli":1, "pf":0},
    11:{"ecoli":0, "pf":0}
 }

- *ignore_trials* ``list``: the trials (identified through the row & column well-plate coordinates) that will be ignored in the simulation.
- *ignore_timesteps* ``list``: the timesteps that will be ignored in the simulation.
- *species_identities_rows* ``dict``: the specification of strains for each member species, where it differs, per row in the well-plate experiments:

.. code-block:: json

 {
    1:{"ecoli":"mRuby"},
    2:{"ecoli":"ACS"},
    3:{"ecoli":"mRuby"},
    4:{"ecoli":"ACS"},
    5:{"ecoli":"mRuby"},
    6:{"ecoli":"ACS"}
 }

- *significant_deviation* ``float``: the smallest multiple of a trial mean relative to its initial value that permits its inclusion in the simulation.
- *extract_zip_path* ``str``: the path of a zipped file that contents some or all of the files that must be loaded in the simulation.

-----------------------------
fit()
-----------------------------

The parsed experimental data is used to define and constrain a Global Linear Problem of the community system:

.. code-block:: python

 mscommfit.fit(parameters:dict=None, mets_to_track: list = None, 
               rel_final_conc:dict=None, zero_start:list=None, 
               abs_final_conc:dict=None, graphs: list = None, 
               data_timesteps: dict = None, export_zip_name: str = None, 
               export_parameters: bool = True, requisite_biomass: dict = None,
               export_lp: str = "CommPhitting.lp", figures_zip_name:str=None, 
               publishing:bool=False, primals_export_path=None)


- *parameters* ``dict``: simulation parameters that will overwrite default and calculated options. The possible key values include 

.. csv-table::
   :header: "Parameter", "Default", "Description"

   "timestep_hr",               "the average timestep that is parsed from the data",      "the timestep size of the simulation in hours"
   "cvct",               "0.01",      "the coefficient that penalizes phenotype conversion to the stationary phase"
   "cvcf",               "0.01",                "the coefficient that penalizes phenotype conversion from the stationary phase"
   "bcv",              "0.1",  "the highest fraction of species biomass that can convert phenotypes in a timestep"
   "cvmin",               "0",                "the lowest fraction of biomass that converts phenotypes in a single timestep"
   "kcat",              "0.33",  "the growth constant for linear 1st-order kinetics"
   "carbon_sources",               "["cpd00136", "cpd00179"]",                "the ModelSEED IDs of the carbon sources in the media"
   "diffpos",              "1",  "the objective coefficient that corresponds with the positive difference between experimental and predicted biomass values"
   "diffneg",			"1",	"the objective coefficient that corresponds with the negative difference between experimental and predicted biomass values"
   "stationary",		"0.075",  "the penalty coefficient for the stationary phenotype"

- *mets_to_track* ``list``: the ModelSEED ID"s of all compounds that will be graphically plotted, unless metabolites are specifically listed in a graph of the ``graphs`` argument.
- *rel_final_conc* ``dict``: the final concentration of a phenotype compound in the media that is normalized by its initial concentration: e.g.

.. code-block:: json

 {
    "cpd00179":0.1
 }

denotes that the final concentration of Maltose is 10% of its initial concentration.

- *zero_start* ``list``: the compounds that possess a zero initial concentration, which is often assumed for cross-feeding compounds that are not provided in the media.
- *abs_final_conc* ``dict``: the final mM concentration of a phenotype compound in the media, which follows the same syntactic structure as the ``rel_final_conc`` parameter.
- *graphs* ``list<dict>``: the collection of graphs that will be plotted from the primal values after the simulation executes. Each dictionary in the list describes a figure, with descriptive keys that specify the type of figure, attributes of the figure, and the data that populates the figure. The ``trial`` key designates which experimental trial will be simulated. The ``experimental_data`` key accepts a boolean for whether the experimental growth data is overlaid as a scatter upon the predicted biomass plots, where the default is ``true``. The ``content`` key designates what content of the trial will be plotted, with acceptable string values of

.. csv-table::
   :header: "content option", "Description"

   "biomass",               "The g/L biomass of the defined phenotypes"
   "total_biomass",			"The g/L biomass of the defined phenotypes and the total OD biomass of the complete community"
   "conc",					"The mM concentration of the metabolites that are defined in either 1) an accompanying ``mets`` key that corresponds to a list of metabolites to plot, 2) the ``mets_to_track`` parameter of the function, or 3) all carbonaceous metabolites in the simulated phenotypes as a default."

Graphing designations for non-concentration figures can be tailored with the ``species`` and ``phenotype`` keys, which correspond lists of the species and phenotypes for which primal values will be graphed, or a string ``"*"`` can be passed as the value to denote all available species and phenotypes will be plotted. Finally, the ``parsed`` key accepts a boolean for whether the biomass plots are segregated for each species, which can alleviate busyness for complex communities. All of these plots are all defined with time on the x-axis, and either mM concentration or g/L on the y-axis depending upon the plotted content.

The following ``graphs`` argument samples the range of supported figures:

.. code-block:: json

 [
    {
        "trial":"G48",
        "phenotype": "*",
        "content": "biomass",
        "experimental_data": false
    },
    {
        "trial":"G48",
        "content": "conc"
    },
    {
        "trial":"G48",
        "phenotype": "*",
        "content": "biomass",
        "parsed": true
    },
    {
        "trial":"G48",
        "content": "total_biomass",
        "experimental_data": true
    }
 ]
 
- *data_timesteps* ``dict``: a list of timesteps for each ``short_code`` trial that will be simulated, which can be a more succinct tool for tailoring a simulation than specifying the timesteps to ignore from the full dataset.
- *export_zip_name* ``str``: the name of the zip file to which the simulation contents will be stored, where the omission of this parameter does not export content to a zip file.
- *export_parameters* ``bool``: specifies whether the simulation parameters will be exported as CSV to the current working directory.
- *requisite_biomass* ``dict``: the requisite amount of biomass that must grow for the prescribed final metabolite concentration to be achieved, according to the phenotype flux profiles. This is calculated in the ``MSCommPhitting`` initialization when ``community_members`` is defined, but this parameter option allows previous or custom objects to be provided for the simulation.
- *export_lp* ``str``: the name of the LP file, including the ".lp" extension, that will be exported to the current working directory. The default is "CommPhitting.lp".
- *figures_zip_name* ``str``: the name of the zip file to which all of the figures will be exported, where omitting this argument exports the figures to the current working directory.
- *publishing* ``bool``: specifies whether figure proportions and attributes are tailored to make the figures more desirable for publication or poster formats.
- *primals_export_path* ``str``: the path to which simulation primal values will be exported, which defaults to the ``export_lp`` name with "json" extension.


-----------------------------
fit_kcat()
-----------------------------

This function simulates the defined community while implementing a range growth kinetic constants for  each phenotype and refining the estimate of phenotype growth kinetics through a few iterative simulations. The parameters are identical to the ``fit()`` function:

.. code-block:: python

 mscommfit.fit_kcat(parameters:dict=None, mets_to_track: list = None, 
                    rel_final_conc:dict=None, zero_start:list=None, 
               		abs_final_conc:dict=None, graphs: list = None, 
               		data_timesteps: dict = None, export_zip_name: str = None, 
               		export_parameters: bool = True, requisite_biomass: dict = None,
               		export_lp: str = "CommPhitting.lp", figures_zip_name:str=None, 
               		publishing:bool=False, primals_export_path=None)
                       







++++++++++++++++++++++++++++++++++++
Un-updated documentation
++++++++++++++++++++++++++++++++++++







----------------------
compute()
----------------------

The Linear Problem is simulated, and the primal values are parsed, optionally exported, and visualized as figures.

.. code-block:: python

 mscommfit.compute(graphs=[], zip_name=None)

- *zip_name* ``str``: the name of the export zip file to which content will be exported.
                       
                       
----------------------
graph()
----------------------

Primal values are visualized as figures.

.. code-block:: python

 mscommfit.compute(graphs=[], primal_values_filename=None, primal_values_zip_path=None, zip_name=None, data_timestep_hr=0.163)

- *graph* ``list``: the graph specifications that specify which primal values will be graphed, which is elaborated above for the ``compute`` function. 
- *primal_values_filename* ``str``: the name of the primal value JSON file ("primal_values.json")
- *primal_values_zip_path* ``str``: the path of the zip file that contains the primal values file
- *zip_name* ``str``: the name of the export zip file to which content will be exported.
- *data_timestep_hr* ``float``: the timestep value in hours of the data that is being graphed. This permits graphing primal values without previously simulating a model. The value is automatically overwritten by previously defined data timesteps in the ``MSCommFitting`` class object.

                       
----------------------
load_model()
----------------------

A JSON model file is imported.

.. code-block:: python

 mscommfit.load_model(mscomfit_json_path, zip_name=None, class_object=False)

- *mscomfit_json_path* ``str``: the path of the JSON model file that will be loaded and simulated. 
- *zip_name* ``str``: the path of the zip file that contains the JSON model file.
- *class_object* ``bool``: specifies whether the loaded model will be defined in the class object.
                       
**returns** *model* ``Optland.Model``: The model that is loaded via the .
 
----------------------
change_parameters()
----------------------

Primal values are visualized figures.

.. code-block:: python

 mscommfit.load_model(cvt=None, cvf=None, diff=None, vmax=None, mscomfit_json_path="mscommfitting.json", zip_name=None, class_object=False)

- *cvt*, *cvf*, *diff*, & *vmax* ``float`` or ``dict``: the parameter values that will replace existing values in the LP file. The parameters may be defined as either floats, which will be applied globally to all applicable instances in the model, or as dictionaries that defined values at specific times and possibly at specific trials for a certain time. The latter follows a dictionary structure of ``param["time"]["trial"]``, where the "trial" level can be omitted to applied a parameter value at every trial of a time. A default value can also be specified in the dictionary ``param["default"]`` that applies to times+trials that are not captured by the defined conditions.
- *mscomfit_json_path* ``str``: the path of the JSON model file that will be loaded and simulated.
- *zip_name* ``str``: the zipfile to which the edited LP JSON will be exported .


----------------------
Accessible content
----------------------

Several objects within the ``MSCommFitting`` class may be useful for subsequent post-processing or troubleshooting:

- *problem* ``Optlang.Model``: the LP model of the experimental system that is simulated.
- *carbon_conc* ``dict``: the media concentrations per substrate as defined in ``carbon_conc_series``.
- *variables* & *constraints* ``dict``: the complete collection of all variables and constraints that comprise the LP model.
