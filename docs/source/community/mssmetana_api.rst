mssmetana
--------------------------

+++++++++++++++++++++
MSSmetana()
+++++++++++++++++++++

TThis class provides metrics of various dimensions in microbial communities to quantify interactions among community members. Many of the scores -- principally MRO and MIP -- are curated versions from the SMETANA suite of scores (Zelezniak et al., 2015, https://doi.org/10.1073/pnas.1421834112), while the other scores are original metrics that capture additional biological dimensions for comparison. Both class methods, which support multiple scores to be efficiently calculated for a single community of members, and  ``staticmethods``, which support in-line calculation of single scores ad hoc, are available for each score:

.. code-block:: python

 from modelseedpy.community import MSSmetana
 mssmet = MSSmetana(self, member_models: Iterable, min_growth=0.1, n_solutions=100, 
                    environment=None, abstol=1e-3, media_dict=None, 
                    printing=True, raw_content=False, antismash_json_path:str=None,
                    antismash_zip_path:str=None, minimal_media_method="minFlux")

- *member_models* ``list|set <cobra.core.model.Model>``: the collection of member models for which the metric scores will be calculated.
- *min_growth* ``float``: the smallest growth rate that is specified during minimal media calculations.
- *n_solutions*  ``int``: the number of exploratory loops that the MILP algorithms of the ``MU`` and ``SC`` SMETANA scores will execute.
- *environment*  ``dict|kbase_media_object``: the media in which the community will be simulated, which can be a dictionary of exchanges and their fluxes or a KBase Media object.
- *abstol* ``float``: the flux threshold above which cross-feeding will be considered significant and therefore tracked for the ``MP``, ``MU``, and ``SC`` scores of SMETANA.
- *media_dict* ``dict``: the minimal media of the community members, which can be provided to expedite computational time by not recalculating it repeatedly during development sessions. The media must be defined with the following structure:

.. code-block:: json

 { 
    "members": {
       "Bacillus_sp._bc15.RAST.fbamodel": {
          "media": {
                  "EX_cpd00051_e0": 0.024950298185467054, "EX_cpd00644_e0": 0.0005612318319214348, 
                  "EX_cpd00654_e0": 0.0011184174481049735, "EX_cpd00393_e0": 0.0008418477478827718, 
                  "EX_cpd00149_e0": 0.00028061591596092344, "EX_cpd00030_e0": 0.0002806159159609234, 
                  "EX_cpd00182_e0": 0.012823174793819692, "EX_cpd00367_e0": 0.019860385045891646, 
                  "EX_cpd00063_e0": 0.0002806159159609234, "EX_cpd00066_e0": 0.015451949003231678, 
                  "EX_cpd00099_e0": 0.00028061591596092344, "EX_cpd15603_e0": 0.040392130687977465, 
                  "EX_cpd00254_e0": 0.00028061591596092344, "EX_cpd00264_e0": 0.00028061591596092344, 
                  "EX_cpd00209_e0": 0.29280989138763885, "EX_cpd00007_e0": 0.0007015397899023084, 
                  "EX_cpd00104_e0": 0.00028061591596092344, "EX_cpd00158_e0": 0.8572001890264485, 
                  "EX_cpd00065_e0": 0.004720191914454185, "EX_cpd10515_e0": 0.0008418477478827702, 
                  "EX_cpd00069_e0": 0.012067660460609869, "EX_cpd00048_e0": 0.00028061591596092344, 
                  "EX_cpd00793_e0": 0.0002806159159609235, "EX_cpd00058_e0": 0.00028061591596092344, 
                  "EX_cpd00107_e0": 0.037538884754252475, "EX_cpd00119_e0": 0.00792636000742222, 
                  "EX_cpd00156_e0": 0.035223318909387485, "EX_cpd00034_e0": 0.00028061591596092344, 
                  "EX_cpd00179_e0": 4.162129853322901e-13, "EX_cpd00017_e0": 0.0019643114116915986, 
                  "EX_cpd00205_e0": 0.00028061591596092344, "EX_cpd00277_e0": 0.014659099568563774, 
                  "EX_cpd00355_e0": 0.08097665993895736, "EX_cpd00220_e0": 0.0008418477478827705, 
                  "EX_cpd00322_e0": 0.024179851033877948, "EX_cpd00028_e0": 0.00028061591596092344
                  }
          },
       "Sphingobium_AP49_pacbio_v2.RAST.fbamodel": {
              "media": {
                  "EX_cpd00039_e0": 0.028543802049017904, "EX_cpd00118_e0": 0.000280615915959131, 
                  "EX_cpd01017_e0": 0.008456496968388943, "EX_cpd00051_e0": 0.024669682270134097, 
                  "EX_cpd00136_e0": 0.00028061591595913087, "EX_cpd00161_e0": 0.03565680232766155, 
                  "EX_cpd00009_e0": 0.08097472586643507, "EX_cpd00644_e0": 0.0005612318318649744, 
                  "EX_cpd00654_e0": 0.0011501166238305303, "EX_cpd00393_e0": 0.0008418477478774078, 
                  "EX_cpd00149_e0": 0.000280615915959131, "EX_cpd00030_e0": 0.000280615915959131, 
                  "EX_cpd00132_e0": 0.0200830806928348, "EX_cpd00060_e0": 0.011096446763321909, 
                  "EX_cpd00063_e0": 0.000280615915959131, "EX_cpd00066_e0": 0.015451949003134501, 
                  "EX_cpd00099_e0": 0.00028061591595913103, "EX_cpd00794_e0": 0.2508330788175711, 
                  "EX_cpd03847_e0": 0.00250105977108944, "EX_cpd00254_e0": 0.00028061591595913103, 
                  "EX_cpd00264_e0": 0.000280615915959131, "EX_cpd00007_e0": 1.181243853603619, 
                  "EX_cpd00104_e0": 0.000280615915959131, "EX_cpd00065_e0": 0.004720191914502181, 
                  "EX_cpd10515_e0": 0.0008418477478773928, "EX_cpd00069_e0": 0.0120676604606612, 
                  "EX_cpd00053_e0": 0.20365017006808284, "EX_cpd00048_e0": 0.000280615915959131, 
                  "EX_cpd00793_e0": 0.000280615915959131, "EX_cpd00058_e0": 0.00028061591595913103, 
                  "EX_cpd00107_e0": 0.0375388847540127, "EX_cpd00119_e0": 0.00792636000737159, 
                  "EX_cpd00156_e0": 0.035223318909181824, "EX_cpd00034_e0": 0.000280615915959131, 
                  "EX_cpd00215_e0": 0.000280615915959131, "EX_cpd00166_e0": 5.3065904751139414e-20, 
                  "EX_cpd00017_e0": 0.001964311411713922, "EX_cpd00205_e0": 0.0002806159159591311, 
                  "EX_cpd00277_e0": 0.00205355085202053, "EX_cpd00220_e0": 0.0008418477478773926, 
                  "EX_cpd00322_e0": 0.024179851033723505, "EX_cpd00028_e0": 0.00028061591595913103
                  }
          }
     },
     "community_media": {
     	"EX_cpd00039_e0": 0.028543802049017904, "EX_cpd00118_e0": 0.000280615915959131, 
        "EX_cpd01017_e0": 0.008456496968388943, "EX_cpd00051_e0": 0.024669682270134097, 
        "EX_cpd00136_e0": 0.00028061591595913087, "EX_cpd00161_e0": 0.03565680232766155, 
        "EX_cpd00009_e0": 0.08097472586643507, "EX_cpd00644_e0": 0.0005612318318649744, 
        "EX_cpd00654_e0": 0.0011501166238305303, "EX_cpd00393_e0": 0.0008418477478774078, 
        "EX_cpd00149_e0": 0.000280615915959131, "EX_cpd00030_e0": 0.000280615915959131, 
        "EX_cpd00132_e0": 0.0200830806928348, "EX_cpd00060_e0": 0.011096446763321909, 
        "EX_cpd00063_e0": 0.000280615915959131, "EX_cpd00066_e0": 0.015451949003134501, 
        "EX_cpd00099_e0": 0.00028061591595913103, "EX_cpd00794_e0": 0.2508330788175711, 
        "EX_cpd03847_e0": 0.00250105977108944, "EX_cpd00254_e0": 0.00028061591595913103, 
        "EX_cpd00264_e0": 0.000280615915959131, "EX_cpd00007_e0": 1.181243853603619, 
        "EX_cpd00104_e0": 0.000280615915959131, "EX_cpd00065_e0": 0.004720191914502181, 
        "EX_cpd10515_e0": 0.0008418477478773928, "EX_cpd00069_e0": 0.0120676604606612, 
        "EX_cpd00053_e0": 0.20365017006808284, "EX_cpd00048_e0": 0.000280615915959131, 
        "EX_cpd00793_e0": 0.000280615915959131, "EX_cpd00058_e0": 0.00028061591595913103, 
        "EX_cpd00107_e0": 0.0375388847540127, "EX_cpd00119_e0": 0.00792636000737159, 
        "EX_cpd00156_e0": 0.035223318909181824, "EX_cpd00034_e0": 0.000280615915959131, 
        "EX_cpd00215_e0": 0.000280615915959131, "EX_cpd00166_e0": 5.3065904751139414e-20, 
        "EX_cpd00017_e0": 0.001964311411713922, "EX_cpd00205_e0": 0.0002806159159591311, 
        "EX_cpd00277_e0": 0.00205355085202053, "EX_cpd00220_e0": 0.0008418477478773926, 
        "EX_cpd00322_e0": 0.024179851033723505, "EX_cpd00028_e0": 0.00028061591595913103
      }
 }

The ``"community_media"`` key contains the minimal media of the community model, while the ``"members"`` key contains information for each community member. The key:value pairings of exchange reactions and their respective fluxes, with (+) denoting influx, is loaded by the package.

- *printing* ``bool``: specifies whether progress, warnings, and results are printed to the User"s interface.
- *raw_content* ``bool``: specifies whether the returned content is processed or raw intermediate values that contain additional dimensions of information.
- *antismash_json_path* ``str``: the path to antiSMASH data of the simulated community, which is only used for the ``antiSMASH_scores`` function.
- *antismash_zip_path* ``str``: the path to a raw antiSMASH zip file, which is unzipped by the ``antiSMASH_scores`` function to access the data that constitutes our score.
- *minimal_media_method* ``str``: specifies which minimal media method is employed when calculating the minimal media for the members and community. The "minFlux" selection minimizes total consumption flux while "minComponents" minimizes the number of compounds that are consumed. These options significantly alter the metrics of our scores.


-----------------------------
all_scores()
-----------------------------

All of the defined scores can be simulated on the initalized community system through the ``all_scores`` function. Omission of the *kbase_obj*, *RAST_genomes*, and both of the *cobrakbase_path* and *kbase_token_path* omits the ``RFC`` score from output:

.. code-block:: python

 scores = mssmet.all_scores(mp_score=True, kbase_obj=None, cobrakbase_path:str=None,
                            kbase_token_path:str=None, RAST_genomes:dict=None)


- *mp_score* ``bool``: specifies whether the MP score will be calculated. 
- *kbase_obj* ``kbase_api_object``: the KBase API object from which member genomes can be loaded to calculate the RAST Functional Complementary (RFC) score. 
- *cobrakbase_path* & *kbase_token_path* ``str``: the local paths to the COBRA-Kbase repository, which is necessary to load genomes for specified models, and the KBase User's token, which is necessary to access the KBase API.
- *RAST_genomes* ``dict``: the collection of RAST genomes, indexed by the IDs of their respective community members, that are used for calculating the ``RFC`` score.


**Returns** *scores* ``dict``: the dictionary of outputs for each score:

.. code-block:: json

 {
    "mro": mro_output,
    "mip": mip_output,
    "mp" mp_output,
    "mu": mu_output,
    "sc": sc_score,
    "smetana": smetana_score,
    "grd": grd_score,
    "rfc": rfc_score
 }

 
--------------------------
report_generation()
--------------------------

The scores can be calculated over a large range of models, either for specified pairs or for all combinations of all models. This process can be expedited with optional parallelization. This function is a **Staticmethod**, and therefore cannot access any content that is loaded in the class object of the aforementioned functions.

.. code-block:: python

 scores_df, mets = mssmet.report_generation(all_models:iter=None, pairs:dict=None, mem_media:dict=None,
                                       pair_limit:int=None, exclude_pairs:list=None, kbase_obj=None, 
                                       RAST_genomes:dict=None, see_media:bool=True,
                                       environment:Union[dict]=None,  # can be KBase media object
                                       lazy_load:bool=False, pool_size:int=None)

- *all_models* ``list|set``: the collection of all member models.
- *pairs* ``dict``: the specification of individual member pairings that are sought. The keys are either model objects per se, the permanent KBase model ID, or a tuple of the KBase object name and Narrative ID. The latter two options require that the *kbase_obj* argument is also provided to load the models, but is advantageously coupled with lazy loading via the *lazy_load* argument to minimize RAM consumption for large-scale analyses with numerous models. The values are an iterable of the models that will be coupled with the key model:

.. code-block:: json

 {
 	model1: [model2, model3, model4, model5],
    model2: [model4, model6],
    model4: [model5, model7]
 }

- *mem_media* ``dict``: the minimal media of members, which obviates duplicated computation with subsequent iteractions. The form is the sub-dictionary within the "members" key of the previously defined minimal media dictionary, where the top-level keys are the model IDs, the second-level keys is "media", and the values are the media dictionaries of exchange IDs and their respective fluxes.
- *pair_limit* ``int``: the maximal number of member pairs that are examined, which is applicable when *pairs* are not specified and an all v. all comparison is conducted.
- *excluded_pairs* ``iterable``: the member pairs that will be omitted, which is valuable for the excluding pairs from the all versus all comparison perspective.
- *RAST_genomes* ``iterable``: the genomes of the members that will be examined, where the omission of this argument does not calculate the ``RFC`` score.
- *see_media* ``bool``: specifies whether the *mem_media* dictionary is printed if it is printed from scratch and not loaded as an argument, which can allow the user to copy it and pass it as the *mem_media* argument in future computations.
- *environment* ``dict|KBase_media_object``: the media in which the community will be simulated, which can be a dictionary of exchanges and their fluxes or a KBase Media object.
- *lazy_load* ``bool``: specifies whether models will only be loaded as they are used in a comparison, which limits RAM consumption by only ever containing two models in memory at a time.
- *pool_size* ``int``: the number of parallel processes across which pairwise scores will be calculated, where omitting this score does not parallelize the process. Our observation is that the processes are not very CPU intensive, even when specifying the maximal number of cores, so this option should be utilized for >50 models, especially for all versus all comparisons.


**Returns** *scores_df* & *mets* ``Pandas.DataFrame`` & ``list<dict>``: a dataframe of all scores for all computed pairs and a list of the metabolites the comprise the ``MRO`` and ``MIP`` scores, for additional information of differences between the members, respectively. These returned objects can be directly passed as inputs into the ``commscores_report`` function of ModelSEEDpy to create an HTML output of the results, which processes the DataFrame into a quantitative heatmap and will eventually include the extra metabolites as hoverover metadata for access to users.



----------------------------------------------------------------------------------------
mro_score(), mip_score(), mu_score(), mp_score(), sc_score(), smetana_score()
----------------------------------------------------------------------------------------

The individual SMETANA scores can be succinctly calculated in any order from the aforementioned class object, without the need for further parameters:

.. code-block:: python

 mro = smtna.mro_score()
 mip = smtna.mip_score()
 mu = smtna.mu_score()
 mp = smtna.mp_score()
 sc = smtna.sc_score()
 smetana = smtna.smetana_score()
 
 **returns** the respective score of the defined community system:

- *mro* & *mip* ``float``: The numerous scores from the MRO and MIP scores, respectively. 
- *mu*, *mp*, *sc*, & *smetana*  ``dict``: The collections of scores, organized by model IDs, for the MU, MP, SC, and SMETANA scores, respectively.
       
-----------------------------
Attributes
-----------------------------

The ``MSSmetana`` class object stores numerous attributes for subsequent post-processing or troubleshooting:

- *community* ``MSModelUtil``: the MSModelUtil model object of the community model.
- *models* ``list<cobra.core.model.Model>``: the collection of compatibilized member models that are examined.
- *mro* & *mip* ``float``: The numerous scores from the MRO and MIP scores, respectively. 
- *mu*, *mp*, *sc*, *smetana*, *grd_val*, *rfc_val*, & *antismash*  ``dict``: The collections of scores, organized by model IDs, for the *MU*, *MP*, *SC*, and *smetana* SMETANA scores, respectively, as well as the original *grd_val*, *rfc_val*, & *antismash* scores.
- *media* ``dict``: The media object of the community.
- *printing* ``bool``: The setting for whether results of the alignment functionality, respectively, are printed to the console.

      
---------
mro()
---------

**Staticmethod**

The MRO SMETANA score can be specifically calculated without constructing a class object:

.. code-block:: python

 MSSmetana.mro(cobra_models, min_growth=0.1, media_dict=None, compatibilize=True)

- *cobra_models* ``list o cobra.core.model.Model``: the collection of member models that comprise the examined community. 
- *min_growth* ``float``: the minimal permissible community biomass objective value from simulation.
- *media_dict* ``dict``: A dictionary of predetermined minimal media, per the above definition.
- *compatibilize* ``bool``: specifies whether the member models will be standardized to the ModelSEED Database conventions.


--------
mip()
--------

**Staticmethod**

The MIP SMETANA score can be specifically calculated without constructing a class object:

.. code-block:: python

 MSSmetana.mip(com_model, cobra_models, min_growth=0.1, interacting_media_dict=None,
            noninteracting_media_dict=None, compatibilize=True)

- *com_model* ``cobra.core.model.Model``: the community model that combines the individual member models.
- *cobra_models* ``list o cobra.core.model.Model``: the collection of member models that comprise the examined community. 
- *min_growth* ``float``: the minimal permissible community biomass objective value from simulation.
- *interacting_media_dict* & *noninteracting_media_dict* ``dict``: Dictionaries of the predetermined minimal media that include and exclude cross-feeding (syntrophy), respectively. The MIP formulation essentially compares these two media, hence the calculation can be tremenedously expedited if both of these media objects are parameterized and need not be calculated in the logic.
- *compatibilize* ``bool``: specifies whether the member models will be standardized to the ModelSEED Database conventions.
       
       
---------
mu()
---------

**Staticmethod**

The MU SMETANA score can be specifically calculated without constructing a class object:

.. code-block:: python

 MSSmetana.mu(cobra_models, n_solutions=100, abstol=1e-3, compatibilize=True)

- *cobra_models* ``list o cobra.core.model.Model``: the collection of member models that comprise the examined community. 
- *n_solutions* ``int``: the number of loops over which the MILP algorithms of the SMETANA scores search.
- *abstol* ``float``: the minimum flux above which the flux is considered to be non-zero.
- *compatibilize* ``bool``: specifies whether the member models will be standardized to the ModelSEED Database conventions.
       
---------
mp()
---------

**Staticmethod**

The MP SMETANA score can be specifically calculated without constructing a class object:

.. code-block:: python

 MSSmetana.mp(cobra_models=None, com_model=None, abstol=1e-3, compatibilize=True)
       
- *cobra_models* ``list o cobra.core.model.Model``: the collection of member models that comprise the examined community. 
- *com_model* ``cobra.core.model.Model``: the community model that combines the individual member models.
- *abstol* ``float``: the minimum flux above which the flux is considered to be non-zero.
- *compatibilize* ``bool``: specifies whether the member models will be standardized to the ModelSEED Database conventions.
       
---------
sc()
---------

**Staticmethod**

The SC SMETANA score can be specifically calculated without constructing a class object:

.. code-block:: python

 MSSmetana.sc(cobra_models=None, com_model=None, min_growth=0.1, 
              n_solutions=100, abstol=1e-3, compatibilize=True)
       
- *cobra_models* ``list o cobra.core.model.Model``: the collection of member models that comprise the examined community. 
- *com_model* ``cobra.core.model.Model``: the community model that combines the individual member models.
- *min_growth* ``float``: the minimal permissible community biomass objective value from simulation.
- *n_solutions* ``int``: the number of loops over which the MILP algorithms of the SMETANA scores search.
- *abstol* ``float``: the minimum flux above which the flux is considered to be non-zero.
- *compatibilize* ``bool``: specifies whether the member models will be standardized to the ModelSEED Database conventions.


-----------
smetana()
-----------

**Staticmethod**

The smetana SMETANA superscore can be specifically calculated without constructing a class object:

.. code-block:: python

 MSSmetana.smetana(cobra_models, com_model=None, min_growth=0.1, n_solutions=100, abstol=1e-6,
                prior_values=None, compatibilize=False, sc_coupling=False)

- *cobra_models* ``list o cobra.core.model.Model``: the collection of member models that comprise the examined community. 
- *com_model* ``cobra.core.model.Model``: the community model that combines the individual member models.
- *min_growth* ``float``: the minimal permissible community biomass objective value from simulation.
- *n_solutions* ``int``: the number of loops over which the MILP algorithms of the SMETANA scores search.
- *abstol* ``float``: the minimum flux above which the flux is considered to be non-zero.
- *prior_values* ``Iterable``: The collection of ``SC``, ``MU``, and ``MP`` score results that were previously calculated for the studied system, and thus do not need to be recalculated.
- *compatibilize* ``bool``: specifies whether the member models will be standardized to the ModelSEED Database conventions.
- *sc_coupling* ``bool``: specifies whether the SC score contributes to the calculation of the smetana score.
