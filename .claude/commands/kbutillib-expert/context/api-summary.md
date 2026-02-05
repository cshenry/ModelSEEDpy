# KBUtilLib API Quick Reference

Quick reference for the most commonly used APIs in KBUtilLib.

## Configuration & Setup

### Initialize with Configuration
```python
from kbutillib import SharedEnvUtils

class MyTools(SharedEnvUtils):
    pass

# Default configuration (auto-loads from standard locations)
tools = MyTools()

# Explicit configuration file
tools = MyTools(config_file="/path/to/config.yaml")

# With explicit token
tools = MyTools(kbase_token="YOUR_TOKEN")
```

### Configuration File Format (YAML)
```yaml
# ~/kbutillib_config.yaml
kbase:
  endpoint: https://kbase.us/services
  workspace_url: https://kbase.us/services/ws

argo:
  endpoint: https://api.cels.anl.gov/argo/api/v1

modelseed:
  database_path: /path/to/ModelSEEDDatabase

logging:
  level: INFO
```

### Token Management
```python
# Get tokens
kbase_token = tools.get_token("kbase")
argo_token = tools.get_token("argo")

# Set tokens programmatically
tools.set_token("NEW_TOKEN", namespace="kbase")

# Tokens can also be set via environment variables:
# KBASE_AUTH_TOKEN, ARGO_API_TOKEN
```

## KBase Workspace Operations

### Retrieve Objects
```python
from kbutillib import KBWSUtils

ws = KBWSUtils()

# Get any object
obj = ws.get_object(workspace_id=12345, object_ref="MyObject/1")

# Get with specific version
obj = ws.get_object(12345, "MyObject/3")

# Get object info (metadata only)
info = ws.get_object_info(12345, "MyObject")
# Returns: [id, name, type, save_date, version, ...]
```

### List Objects
```python
# List all objects in workspace
objects = ws.list_objects(workspace_id=12345)

# Filter by type
genomes = ws.list_objects(12345, type_filter="KBaseGenomes.Genome")
models = ws.list_objects(12345, type_filter="KBaseFBA.FBAModel")
```

### Save Objects
```python
# Save object to workspace
ws.save_object(
    workspace_id=12345,
    obj_type="KBaseGenomes.Genome",
    data=genome_data,
    name="MyNewGenome"
)
```

## Genome Operations

### Get and Analyze Genomes
```python
from kbutillib import KBWSUtils, KBGenomeUtils

class GenomeTools(KBWSUtils, KBGenomeUtils):
    pass

tools = GenomeTools()

# Get genome
genome = tools.get_genome(workspace_id=12345, genome_ref="MyGenome/1")

# Get all features
features = tools.get_features(genome)

# Filter by type
cds_features = tools.get_features_by_type(genome, "CDS")
rna_features = tools.get_features_by_type(genome, "rRNA")

# Filter by function
transporters = tools.get_features_by_function(genome, "transport")
```

### Sequence Translation
```python
# Translate single feature
protein_seq = tools.translate_feature(feature)

# Bulk translation
proteins = tools.translate_features(cds_features)
# Returns: {feature_id: protein_sequence, ...}

# Get contig sequences
contigs = tools.get_contig_sequences(genome)
# Returns: {contig_id: sequence, ...}
```

## Annotation Operations

### Access Annotations
```python
from kbutillib import KBWSUtils, KBAnnotationUtils

class AnnotationTools(KBWSUtils, KBAnnotationUtils):
    pass

tools = AnnotationTools()

# Get all annotations
annotations = tools.get_annotations(genome)

# Get annotation history
events = tools.get_annotation_events(genome)

# Filter by ontology
ec_annotations = tools.filter_annotations_by_ontology(annotations, "EC")
kegg_annotations = tools.filter_annotations_by_ontology(annotations, "KEGG")
```

### Extract Identifiers
```python
# Get EC numbers for a feature
ec_numbers = tools.get_ec_numbers(feature)
# Returns: ["1.1.1.1", "2.3.4.5"]

# Get KEGG IDs
kegg_ids = tools.get_kegg_ids(feature)
# Returns: ["K00001", "K00002"]

# Map function to reactions
reactions = tools.map_function_to_reactions("alcohol dehydrogenase")
```

## ModelSEED Biochemistry

### Search Compounds
```python
from kbutillib import MSBiochemUtils

biochem = MSBiochemUtils()

# Search by name
compounds = biochem.search_compounds("glucose")
# Returns list of matching compounds

# Search by ID
atp = biochem.get_compound("cpd00002")

# Search by formula
c6h12o6 = biochem.search_by_formula("C6H12O6")

# Search by structure
compound = biochem.search_by_inchikey("WQZGKKKJIJFFOK-...")
```

### Search Reactions
```python
# Search by name/equation
reactions = biochem.search_reactions("glycolysis")

# Get specific reaction
reaction = biochem.get_reaction("rxn00001")

# Get stoichiometry
stoich = biochem.get_reaction_stoichiometry("rxn00001")
# Returns: {"cpd00001": -1, "cpd00002": 1, ...}
```

## Metabolic Model Operations

### Get and Analyze Models
```python
from kbutillib import KBWSUtils, KBModelUtils

class ModelTools(KBWSUtils, KBModelUtils):
    pass

tools = ModelTools()

# Get model
model = tools.get_model(workspace_id=12345, model_ref="MyModel/1")

# Get model components
reactions = tools.get_model_reactions(model)
metabolites = tools.get_model_metabolites(model)
genes = tools.get_model_genes(model)
```

### Modify Models
```python
# Add reaction
tools.add_reaction(model, reaction_data)

# Remove reaction
tools.remove_reaction(model, "rxn00001_c0")

# Get reconstruction template
template = tools.get_template("GramNegative")
```

## FBA Operations

### Run FBA
```python
from kbutillib import KBModelUtils, MSFBAUtils

class FBATools(KBModelUtils, MSFBAUtils):
    pass

tools = FBATools()

# Basic FBA
solution = tools.run_fba(model)
print(f"Objective value: {solution.objective_value}")

# FBA with specific media
tools.set_media(model, "Complete")
solution = tools.run_fba(model)

# Parsimonious FBA
solution = tools.run_pfba(model)
```

### Flux Analysis
```python
# Flux Variability Analysis
fva_results = tools.run_fva(model)
# Returns: {reaction_id: (min_flux, max_flux), ...}

# FVA on specific reactions
fva_results = tools.run_fva(model, reactions=["rxn00001", "rxn00002"])

# Set fraction of optimum constraint
tools.set_fraction_of_optimum(model, 0.9)  # 90% of optimal
fva_results = tools.run_fva(model)
```

### Constraints and Objectives
```python
# Set objective
tools.set_objective(model, "bio1")  # Biomass reaction

# Add flux constraint
tools.add_constraint(model, {
    "reaction": "rxn00001",
    "lower_bound": 0,
    "upper_bound": 10
})
```

## AI Curation

### Reaction Curation
```python
from kbutillib import AICurationUtils

curator = AICurationUtils()

# Curate reaction direction
result = curator.curate_reaction_direction(reaction_data)
# Returns direction analysis with confidence

# Categorize stoichiometry
category = curator.categorize_stoichiometry(reaction)
# Returns: "balanced", "transport", "exchange", etc.

# Evaluate equivalence
are_equivalent = curator.evaluate_equivalence(reaction1, reaction2)
```

### Gene-Reaction Assessment
```python
# Validate gene-reaction association
assessment = curator.assess_gene_reaction(gene_info, reaction_info)
# Returns confidence score and reasoning
```

### Caching
```python
# Results are automatically cached
# Check cache
cached = curator.get_cached_result(query_hash)

# Clear cache
curator.clear_cache()
```

## External APIs

### BV-BRC
```python
from kbutillib import BVBRCUtils

bvbrc = BVBRCUtils()

# Get genome
genome = bvbrc.get_bvbrc_genome("83332.12")

# Search genomes
genomes = bvbrc.search_bvbrc_genomes("Escherichia coli")

# Convert to KBase format
kb_genome = bvbrc.convert_to_kbase(genome)
```

### UniProt
```python
from kbutillib import KBUniProtUtils

uniprot = KBUniProtUtils()

# Get entry
entry = uniprot.get_uniprot_entry("P00533")

# Get sequence
sequence = uniprot.get_protein_sequence("P00533")

# Search
results = uniprot.search_uniprot("alcohol dehydrogenase AND organism:ecoli")

# ID mapping
mapped = uniprot.map_ids(["P00533", "P12345"], from_db="UniProtKB_AC", to_db="PDB")
```

### PDB
```python
from kbutillib import RCSBPDBUtils

pdb = RCSBPDBUtils()

# Get structure info
structure = pdb.get_structure("1HHO")

# Search
structures = pdb.search_structures("hemoglobin")

# Get sequence
sequence = pdb.get_sequence("1HHO", chain="A")
```

## Visualization

### Escher Maps
```python
from kbutillib import EscherUtils

escher = EscherUtils()

# Create map
map = escher.create_map(reaction_list)

# Visualize FBA results
escher.visualize_fluxes(map, fba_solution)

# Custom coloring
escher.set_reaction_colors(map, {
    "rxn00001": "red",
    "rxn00002": "blue"
})

# Save
escher.save_map(map, "my_map.json")
```

## Notebook Utilities

### Enhanced Display
```python
from kbutillib import NotebookUtils

nb = NotebookUtils()

# Display DataFrame with interactive features
nb.display_dataframe(df)

# Progress bar
with nb.create_progress_bar(total=100) as pbar:
    for i in range(100):
        # do work
        pbar.update(1)
```

### Data Objects with Provenance
```python
# Create tracked data object
data = nb.DataObject(
    name="my_analysis",
    data=result_data,
    source="genome_analysis",
    params={"param1": "value1"}
)

# Access provenance
print(data.provenance)
```

## Error Handling

```python
try:
    genome = tools.get_genome(12345, "NonExistentGenome")
except ValueError as e:
    print(f"Object not found: {e}")

try:
    result = curator.curate_reaction_direction(bad_data)
except Exception as e:
    tools.log_error(f"Curation failed: {e}")
```

## Logging

```python
# Set log level
tools.logger.setLevel("DEBUG")

# Log messages
tools.log_info("Starting analysis")
tools.log_debug("Processing item 1 of 100")
tools.log_error("Failed to process item")
```
