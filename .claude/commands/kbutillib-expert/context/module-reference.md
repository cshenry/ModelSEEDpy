# KBUtilLib Module Reference

Complete reference for all utility modules in KBUtilLib.

## Module Hierarchy

```
BaseUtils (foundation)
├── SharedEnvUtils (configuration & tokens)
│   ├── KBWSUtils (KBase Workspace)
│   │   ├── KBGenomeUtils (genome analysis)
│   │   ├── KBAnnotationUtils (annotations)
│   │   ├── KBModelUtils (metabolic models)
│   │   └── KBReadsUtils (reads/assemblies)
│   ├── PatricWSUtils (PATRIC Workspace)
│   ├── MSBiochemUtils (ModelSEED biochemistry)
│   ├── MSFBAUtils (FBA analysis)
│   ├── MSReconstructionUtils (model reconstruction)
│   ├── ArgoUtils (LLM integration)
│   ├── AICurationUtils (AI curation)
│   ├── BVBRCUtils (BV-BRC API)
│   ├── KBUniProtUtils (UniProt API)
│   ├── RCSBPDBUtils (PDB structures)
│   ├── KBPLMUtils (protein language models)
│   └── SKANIUtils (genome distance)
├── EscherUtils (visualization)
├── NotebookUtils (Jupyter enhancements)
├── ModelStandardizationUtils (model standardization)
└── ThermoUtils (thermodynamics)
```

## Foundation Layer

### BaseUtils
**Location:** `src/kbutillib/base_utils.py`
**Purpose:** Base class providing core functionality for all utilities.

**Key Methods:**
- `initialize_call(method_name, params)` - Start provenance tracking
- `log_info(message)` / `log_debug(message)` / `log_error(message)` - Logging
- `validate_args(required_args, provided_args)` - Argument validation
- `save_util_data(filename, data)` - Save JSON data
- `load_util_data(filename)` - Load JSON data

**Attributes:**
- `logger` - Configured logging instance
- `provenance` - List of tracked method calls

### SharedEnvUtils
**Location:** `src/kbutillib/shared_env_utils.py` (~500 lines)
**Inherits:** BaseUtils
**Purpose:** Configuration and authentication management.

**Key Methods:**
- `load_config(config_file=None)` - Load YAML configuration
- `get_token(namespace="kbase")` - Get authentication token
- `set_token(token, namespace="kbase")` - Set authentication token
- `get_config_value(key)` - Get config value by dot-notation path

**Configuration Priority:**
1. Explicit `config_file` parameter
2. `~/kbutillib_config.yaml` (user config)
3. `repo/config/default_config.yaml` (defaults)

**Token Namespaces:**
- `kbase` - KBase authentication
- `argo` - Argo LLM service
- Custom namespaces as needed

## Data Access Layer

### KBWSUtils
**Location:** `src/kbutillib/kb_ws_utils.py` (~595 lines)
**Inherits:** SharedEnvUtils
**Purpose:** KBase Workspace Service API access.

**Key Methods:**
- `get_object(workspace_id, object_ref)` - Retrieve any workspace object
- `save_object(workspace_id, obj_type, data, name)` - Save object
- `list_objects(workspace_id, type_filter=None)` - List workspace objects
- `get_object_info(workspace_id, object_ref)` - Get object metadata
- `get_type_spec(type_name)` - Get type specification

**Workspace Reference Formats:**
- `ws_id/obj_name` - By workspace ID and name
- `ws_id/obj_name/version` - Specific version
- `obj_id` - Direct object ID

### PatricWSUtils
**Location:** `src/kbutillib/patric_ws_utils.py` (~609 lines)
**Inherits:** SharedEnvUtils
**Purpose:** PATRIC/BV-BRC Workspace access.

**Key Methods:**
- `get_patric_object(path)` - Get object from PATRIC workspace
- `list_patric_workspace(path)` - List workspace contents
- `get_patric_genome(genome_id)` - Get genome object
- `get_patric_model(model_id)` - Get metabolic model

## Bioinformatics Analysis Layer

### KBGenomeUtils
**Location:** `src/kbutillib/kb_genome_utils.py` (~770 lines)
**Inherits:** KBWSUtils
**Purpose:** Genome data analysis and manipulation.

**Key Methods:**
- `get_genome(workspace_id, genome_ref)` - Retrieve genome object
- `get_features(genome)` - Get all features
- `get_features_by_type(genome, feature_type)` - Filter by type (CDS, rRNA, etc.)
- `get_features_by_function(genome, function_pattern)` - Filter by function
- `translate_feature(feature)` - DNA to protein translation
- `translate_features(features)` - Bulk translation
- `get_contig_sequences(genome)` - Get contig sequences

**Feature Types:**
- `CDS` - Coding sequences
- `rRNA`, `tRNA` - RNA features
- `gene`, `mRNA` - Gene annotations

### KBAnnotationUtils
**Location:** `src/kbutillib/kb_annotation_utils.py` (~940 lines)
**Inherits:** KBWSUtils
**Purpose:** Gene and protein annotation management.

**Key Methods:**
- `get_annotations(genome)` - Get all annotations
- `get_annotation_events(genome)` - Get annotation event history
- `filter_annotations_by_ontology(annotations, ontology)` - Filter by source
- `get_ec_numbers(feature)` - Extract EC numbers
- `get_kegg_ids(feature)` - Extract KEGG identifiers
- `map_function_to_reactions(function)` - Map functional role to reactions

**Supported Ontologies:**
- EC numbers
- KEGG
- MetaCyc
- UniProt
- GO terms

### MSBiochemUtils
**Location:** `src/kbutillib/ms_biochem_utils.py` (~859 lines)
**Inherits:** SharedEnvUtils
**Purpose:** ModelSEED biochemistry database access.

**Key Methods:**
- `search_compounds(query)` - Search compounds by name/ID/formula
- `search_reactions(query)` - Search reactions by name/equation
- `get_compound(compound_id)` - Get compound by ID (cpd00001)
- `get_reaction(reaction_id)` - Get reaction by ID (rxn00001)
- `get_reaction_stoichiometry(reaction_id)` - Get stoichiometry dict
- `search_by_formula(formula)` - Find compounds by molecular formula
- `search_by_inchikey(inchikey)` - Find by structure

**ID Formats:**
- Compounds: `cpd#####` (e.g., cpd00001 = H2O)
- Reactions: `rxn#####` (e.g., rxn00001)

## Metabolic Modeling Layer

### KBModelUtils
**Location:** `src/kbutillib/kb_model_utils.py` (~696 lines)
**Inherits:** KBWSUtils
**Purpose:** Metabolic model analysis and manipulation.

**Key Methods:**
- `get_model(workspace_id, model_ref)` - Get FBA model
- `get_model_reactions(model)` - List model reactions
- `get_model_metabolites(model)` - List model metabolites
- `get_model_genes(model)` - List model genes
- `add_reaction(model, reaction)` - Add reaction to model
- `remove_reaction(model, reaction_id)` - Remove reaction
- `get_template(template_name)` - Get reconstruction template

**Model Object Structure:**
- `modelreactions` - List of reactions
- `modelcompounds` - List of metabolites
- `modelgenes` - List of genes
- `biomasses` - Biomass objective functions

### MSFBAUtils
**Location:** `src/kbutillib/ms_fba_utils.py` (~685 lines)
**Inherits:** SharedEnvUtils
**Purpose:** Flux Balance Analysis operations.

**Key Methods:**
- `run_fba(model, media=None)` - Run FBA simulation
- `run_pfba(model)` - Parsimonious FBA
- `run_fva(model, reactions=None)` - Flux Variability Analysis
- `set_media(model, media_id)` - Configure growth media
- `set_objective(model, reaction_id)` - Set objective function
- `add_constraint(model, constraint)` - Add flux constraint
- `set_fraction_of_optimum(model, fraction)` - Set optimality fraction

**Media Options:**
- `Complete` - Rich media
- `Minimal` - Minimal glucose
- Custom media definitions

### MSReconstructionUtils
**Location:** `src/kbutillib/ms_reconstruction_utils.py` (~757 lines)
**Inherits:** SharedEnvUtils
**Purpose:** Genome-scale model reconstruction.

**Key Methods:**
- `build_model_from_genome(genome, template)` - Build draft model
- `gapfill_model(model, media)` - Gap-fill model
- `prune_model(model)` - Remove unnecessary reactions
- `integrate_phenotypes(model, phenotype_data)` - Add phenotype constraints

### EscherUtils
**Location:** `src/kbutillib/escher_utils.py` (~1,089 lines)
**Inherits:** BaseUtils
**Purpose:** Escher pathway map visualization.

**Key Methods:**
- `create_map(reactions, layout=None)` - Create Escher map
- `visualize_fluxes(map, fba_solution)` - Overlay flux values
- `set_reaction_colors(map, color_dict)` - Custom reaction coloring
- `save_map(map, filename)` - Save to file
- `load_map(filename)` - Load existing map

## External API Layer

### BVBRCUtils
**Location:** `src/kbutillib/bvbrc_utils.py` (~463 lines)
**Inherits:** SharedEnvUtils
**Purpose:** BV-BRC (formerly PATRIC) API access.

**Key Methods:**
- `get_bvbrc_genome(genome_id)` - Fetch genome by ID
- `search_bvbrc_genomes(query)` - Search genomes
- `get_genome_features(genome_id)` - Get genome features
- `get_genome_sequences(genome_id)` - Get contig sequences
- `convert_to_kbase(bvbrc_genome)` - Convert to KBase format

### KBUniProtUtils
**Location:** `src/kbutillib/kb_uniprot_utils.py` (~651 lines)
**Inherits:** SharedEnvUtils
**Purpose:** UniProt REST API integration.

**Key Methods:**
- `get_uniprot_entry(accession)` - Get entry by accession
- `search_uniprot(query)` - Search UniProt
- `get_protein_sequence(accession)` - Get protein sequence
- `get_annotations(accession)` - Get functional annotations
- `map_ids(ids, from_db, to_db)` - ID mapping

### RCSBPDBUtils
**Location:** `src/kbutillib/rcsb_pdb_utils.py` (~598 lines)
**Inherits:** SharedEnvUtils
**Purpose:** RCSB PDB structure database access.

**Key Methods:**
- `get_structure(pdb_id)` - Get PDB structure
- `search_structures(query)` - Search PDB
- `get_sequence(pdb_id, chain)` - Get chain sequence
- `get_experimental_info(pdb_id)` - Get experimental metadata

## AI/ML Layer

### ArgoUtils
**Location:** `src/kbutillib/argo_utils.py`
**Inherits:** SharedEnvUtils
**Purpose:** Argo LLM service integration.

**Key Methods:**
- `query_argo(prompt, model="gpt4o")` - Send LLM query
- `query_argo_async(prompt, model)` - Async query with polling
- `get_available_models()` - List available models

**Available Models:**
- `gpt4o` - GPT-4o
- `gpt3mini` - GPT-3.5 Mini
- `o1`, `o1-mini`, `o3-mini` - Reasoning models

### AICurationUtils
**Location:** `src/kbutillib/ai_curation_utils.py` (~897 lines)
**Inherits:** ArgoUtils
**Purpose:** AI-powered biochemistry curation.

**Key Methods:**
- `curate_reaction_direction(reaction)` - Determine reaction reversibility
- `categorize_stoichiometry(reaction)` - Categorize reaction type
- `evaluate_equivalence(rxn1, rxn2)` - Check reaction equivalence
- `assess_gene_reaction(gene, reaction)` - Validate gene-reaction association
- `get_cached_result(query_hash)` - Get cached curation result
- `cache_result(query_hash, result)` - Cache curation result

**Backends:**
- `argo` - Argo LLM service
- `claude` - Claude Code integration

### KBPLMUtils
**Location:** `src/kbutillib/kb_plm_utils.py` (~804 lines)
**Inherits:** SharedEnvUtils
**Purpose:** Protein language model integration.

**Key Methods:**
- `search_homologs(sequence)` - PLM-based homology search
- `create_blast_db(sequences)` - Create BLAST database
- `search_blast(query, db)` - BLAST search
- `get_uniprot_for_hits(hits)` - Fetch UniProt info for hits

## Utility Layer

### NotebookUtils
**Location:** `src/kbutillib/notebook_utils.py` (~703 lines)
**Inherits:** BaseUtils
**Purpose:** Jupyter notebook enhancements.

**Key Classes:**
- `DataObject` - Standardized data object with provenance

**Key Methods:**
- `display_dataframe(df)` - Enhanced DataFrame display
- `create_progress_bar(total)` - Progress bar
- `display_html(html)` - Rich HTML output

### SKANIUtils
**Location:** `src/kbutillib/skani_utils.py` (~800 lines)
**Inherits:** SharedEnvUtils
**Purpose:** Fast genome distance computation using SKANI.

**Key Methods:**
- `compute_ani(genome1, genome2)` - Compute ANI between genomes
- `create_sketch_db(genomes)` - Create SKANI sketch database
- `search_db(query_genome, db)` - Search against database
- `clear_cache()` - Clear sketch cache

## Import Patterns

```python
# Import specific utilities
from kbutillib import KBWSUtils, KBGenomeUtils, MSBiochemUtils

# Import all (optional dependencies may fail gracefully)
from kbutillib import *

# Check what's available
import kbutillib
print(kbutillib.__all__)
```

## Composable Combinations

```python
# Genomics workflow
class GenomicsTools(KBWSUtils, KBGenomeUtils, KBAnnotationUtils):
    pass

# Metabolic modeling workflow
class ModelingTools(KBModelUtils, MSFBAUtils, MSBiochemUtils):
    pass

# AI curation workflow
class CurationTools(AICurationUtils, MSBiochemUtils, NotebookUtils):
    pass

# Full analysis stack
class FullStack(KBGenomeUtils, KBAnnotationUtils, KBModelUtils,
                MSBiochemUtils, MSFBAUtils, NotebookUtils):
    pass
```
