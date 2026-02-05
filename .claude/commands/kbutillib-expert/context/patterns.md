# KBUtilLib Common Patterns and Workflows

Practical patterns and complete workflows for using KBUtilLib.

## Pattern 1: Composable Class Design

The core pattern in KBUtilLib is combining utility classes via multiple inheritance.

### Basic Composition
```python
from kbutillib import KBWSUtils, KBGenomeUtils, MSBiochemUtils

# Combine utilities you need
class MyAnalysisTools(KBWSUtils, KBGenomeUtils, MSBiochemUtils):
    """Custom tool combining genome and biochemistry utilities."""

    def my_custom_method(self, genome_ref):
        """Custom method using inherited functionality."""
        genome = self.get_genome(self.workspace_id, genome_ref)
        features = self.get_features_by_type(genome, "CDS")

        # Use MSBiochemUtils methods
        for feature in features:
            reactions = self.map_function_to_reactions(feature['function'])
        return reactions

# Use the combined class
tools = MyAnalysisTools(workspace_id=12345)
```

### Specialized Stacks
```python
# Genomics-focused stack
class GenomicsStack(KBWSUtils, KBGenomeUtils, KBAnnotationUtils, BVBRCUtils):
    pass

# Modeling-focused stack
class ModelingStack(KBWSUtils, KBModelUtils, MSFBAUtils, MSBiochemUtils):
    pass

# Curation-focused stack
class CurationStack(AICurationUtils, MSBiochemUtils, NotebookUtils):
    pass

# Full analysis stack
class FullStack(KBGenomeUtils, KBAnnotationUtils, KBModelUtils,
                MSFBAUtils, MSBiochemUtils, NotebookUtils):
    pass
```

## Pattern 2: Configuration Management

### Standard Configuration Flow
```python
from kbutillib import SharedEnvUtils

class MyTools(SharedEnvUtils):
    pass

# Option 1: Auto-detect configuration
tools = MyTools()  # Loads from ~/kbutillib_config.yaml or defaults

# Option 2: Explicit configuration file
tools = MyTools(config_file="/path/to/my_config.yaml")

# Option 3: Runtime configuration
tools = MyTools()
tools.set_token("my_token", namespace="kbase")
```

### Configuration File Template
```yaml
# ~/kbutillib_config.yaml
kbase:
  endpoint: https://kbase.us/services
  workspace_url: https://kbase.us/services/ws
  auth_service_url: https://kbase.us/services/auth

argo:
  endpoint: https://api.cels.anl.gov/argo/api/v1
  default_model: gpt4o

modelseed:
  database_path: ~/ModelSEEDDatabase

logging:
  level: INFO
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Custom settings
my_analysis:
  output_dir: ~/analysis_results
  cache_enabled: true
```

### Accessing Configuration
```python
# Dot-notation access
endpoint = tools.get_config_value("kbase.endpoint")
output_dir = tools.get_config_value("my_analysis.output_dir")

# With defaults
cache = tools.get_config_value("my_analysis.cache_enabled", default=False)
```

## Pattern 3: Genome Analysis Workflow

### Complete Genome Analysis Pipeline
```python
from kbutillib import KBWSUtils, KBGenomeUtils, KBAnnotationUtils

class GenomeAnalyzer(KBWSUtils, KBGenomeUtils, KBAnnotationUtils):
    pass

analyzer = GenomeAnalyzer(workspace_id=12345)

# Step 1: Retrieve genome
genome = analyzer.get_genome(12345, "MyGenome/1")
print(f"Genome: {genome['scientific_name']}")
print(f"Features: {len(genome['features'])}")

# Step 2: Extract coding sequences
cds_features = analyzer.get_features_by_type(genome, "CDS")
print(f"CDS count: {len(cds_features)}")

# Step 3: Translate to proteins
proteins = analyzer.translate_features(cds_features)
print(f"Translated {len(proteins)} proteins")

# Step 4: Analyze annotations
annotations = analyzer.get_annotations(genome)
ec_annotations = analyzer.filter_annotations_by_ontology(annotations, "EC")
print(f"Features with EC numbers: {len(ec_annotations)}")

# Step 5: Extract functional roles
for feature in cds_features[:10]:
    ec_nums = analyzer.get_ec_numbers(feature)
    if ec_nums:
        reactions = analyzer.map_function_to_reactions(feature['function'])
        print(f"{feature['id']}: {len(reactions)} reactions")
```

## Pattern 4: Metabolic Model Analysis

### FBA Analysis Pipeline
```python
from kbutillib import KBWSUtils, KBModelUtils, MSFBAUtils, MSBiochemUtils

class ModelAnalyzer(KBWSUtils, KBModelUtils, MSFBAUtils, MSBiochemUtils):
    pass

analyzer = ModelAnalyzer(workspace_id=12345)

# Step 1: Get model
model = analyzer.get_model(12345, "MyModel/1")
print(f"Model has {len(analyzer.get_model_reactions(model))} reactions")

# Step 2: Set up simulation
analyzer.set_media(model, "Complete")
analyzer.set_objective(model, "bio1")  # Biomass reaction

# Step 3: Run FBA
solution = analyzer.run_fba(model)
print(f"Growth rate: {solution.objective_value}")

# Step 4: Analyze flux distribution
for reaction in solution.fluxes:
    if abs(solution.fluxes[reaction]) > 0.1:
        rxn_info = analyzer.get_reaction(reaction.split("_")[0])
        print(f"{reaction}: {solution.fluxes[reaction]:.2f}")

# Step 5: Flux Variability Analysis
analyzer.set_fraction_of_optimum(model, 0.9)
fva = analyzer.run_fva(model)
for rxn, (min_flux, max_flux) in fva.items():
    if min_flux != max_flux:
        print(f"{rxn}: [{min_flux:.2f}, {max_flux:.2f}]")
```

### Model Comparison
```python
# Compare two models
model1 = analyzer.get_model(12345, "Model1/1")
model2 = analyzer.get_model(12345, "Model2/1")

rxns1 = set(r['id'] for r in analyzer.get_model_reactions(model1))
rxns2 = set(r['id'] for r in analyzer.get_model_reactions(model2))

unique_to_1 = rxns1 - rxns2
unique_to_2 = rxns2 - rxns1
shared = rxns1 & rxns2

print(f"Shared reactions: {len(shared)}")
print(f"Unique to Model1: {len(unique_to_1)}")
print(f"Unique to Model2: {len(unique_to_2)}")
```

## Pattern 5: AI-Powered Curation

### Reaction Curation Pipeline
```python
from kbutillib import AICurationUtils, MSBiochemUtils

class CurationPipeline(AICurationUtils, MSBiochemUtils):
    pass

curator = CurationPipeline()

# Step 1: Get reactions to curate
reactions_to_curate = curator.search_reactions("transport")

# Step 2: Curate each reaction
results = []
for rxn in reactions_to_curate[:10]:
    # Check cache first
    cached = curator.get_cached_result(rxn['id'])
    if cached:
        results.append(cached)
        continue

    # Curate direction
    direction = curator.curate_reaction_direction(rxn)

    # Categorize stoichiometry
    category = curator.categorize_stoichiometry(rxn)

    result = {
        'reaction_id': rxn['id'],
        'direction': direction,
        'category': category
    }
    results.append(result)

    # Cache result
    curator.cache_result(rxn['id'], result)

# Step 3: Analyze results
reversible = sum(1 for r in results if r['direction'] == 'reversible')
print(f"Reversible reactions: {reversible}/{len(results)}")
```

### Gene-Reaction Validation
```python
# Validate gene-reaction associations
model = curator.get_model(12345, "MyModel/1")

for reaction in model['modelreactions'][:10]:
    for gene in reaction.get('genes', []):
        assessment = curator.assess_gene_reaction(gene, reaction)
        if assessment['confidence'] < 0.5:
            print(f"Low confidence: {gene['id']} -> {reaction['id']}")
            print(f"  Reason: {assessment['reasoning']}")
```

## Pattern 6: External Database Integration

### BV-BRC Genome Import
```python
from kbutillib import BVBRCUtils, KBWSUtils

class GenomeImporter(BVBRCUtils, KBWSUtils):
    pass

importer = GenomeImporter(workspace_id=12345)

# Step 1: Search for genomes
genomes = importer.search_bvbrc_genomes("Escherichia coli K-12")

# Step 2: Fetch complete genome
bvbrc_genome = importer.get_bvbrc_genome(genomes[0]['genome_id'])

# Step 3: Get features and sequences
features = importer.get_genome_features(genomes[0]['genome_id'])
sequences = importer.get_genome_sequences(genomes[0]['genome_id'])

# Step 4: Convert to KBase format
kb_genome = importer.convert_to_kbase(bvbrc_genome)

# Step 5: Save to KBase workspace
importer.save_object(
    workspace_id=12345,
    obj_type="KBaseGenomes.Genome",
    data=kb_genome,
    name="EcoliK12_imported"
)
```

### UniProt Annotation Enhancement
```python
from kbutillib import KBUniProtUtils, KBGenomeUtils

class AnnotationEnhancer(KBUniProtUtils, KBGenomeUtils):
    pass

enhancer = AnnotationEnhancer()

# Get genome features
genome = enhancer.get_genome(12345, "MyGenome/1")
features = enhancer.get_features_by_type(genome, "CDS")

# Enhance with UniProt data
for feature in features[:10]:
    # Search UniProt by sequence
    sequence = enhancer.translate_feature(feature)
    uniprot_hits = enhancer.search_uniprot(f"sequence:{sequence[:50]}")

    if uniprot_hits:
        entry = enhancer.get_uniprot_entry(uniprot_hits[0]['accession'])
        print(f"{feature['id']}: {entry['proteinDescription']}")
```

## Pattern 7: Notebook-Friendly Analysis

### Interactive Analysis Session
```python
from kbutillib import (KBWSUtils, KBGenomeUtils, KBModelUtils,
                        MSBiochemUtils, NotebookUtils)

class InteractiveAnalysis(KBWSUtils, KBGenomeUtils, KBModelUtils,
                          MSBiochemUtils, NotebookUtils):
    pass

tools = InteractiveAnalysis(workspace_id=12345)

# Create tracked data object
genome = tools.get_genome(12345, "MyGenome/1")
genome_data = tools.DataObject(
    name="my_genome",
    data=genome,
    source="kbase_workspace",
    params={"workspace": 12345, "ref": "MyGenome/1"}
)

# Display DataFrame with features
import pandas as pd
features_df = pd.DataFrame(tools.get_features(genome))
tools.display_dataframe(features_df)

# Progress bar for long operations
reactions = tools.search_reactions("metabolism")
with tools.create_progress_bar(total=len(reactions)) as pbar:
    for rxn in reactions:
        # Process reaction
        pbar.update(1)
```

## Pattern 8: Provenance Tracking

### Tracking Method Calls
```python
from kbutillib import BaseUtils

class TrackedAnalysis(BaseUtils):
    def analyze_data(self, data):
        # Initialize call tracking
        self.initialize_call("analyze_data", {"data_size": len(data)})

        # Perform analysis
        result = self._do_analysis(data)

        # Log progress
        self.log_info(f"Analyzed {len(data)} items")

        return result

    def save_results(self, results, filename):
        self.initialize_call("save_results", {"filename": filename})
        self.save_util_data(filename, results)
        self.log_info(f"Saved results to {filename}")

# Use and check provenance
analyzer = TrackedAnalysis()
result = analyzer.analyze_data(my_data)
analyzer.save_results(result, "analysis_results.json")

# View provenance
print(analyzer.provenance)
# [{"method": "analyze_data", "params": {...}, "timestamp": ...}, ...]
```

## Pattern 9: Error Handling

### Robust API Calls
```python
from kbutillib import KBWSUtils

ws = KBWSUtils()

def safe_get_object(workspace_id, object_ref):
    """Safely retrieve object with error handling."""
    try:
        return ws.get_object(workspace_id, object_ref)
    except ValueError as e:
        ws.log_error(f"Object not found: {object_ref}")
        return None
    except ConnectionError as e:
        ws.log_error(f"Connection failed: {e}")
        raise
    except Exception as e:
        ws.log_error(f"Unexpected error: {e}")
        raise

# Use with fallback
genome = safe_get_object(12345, "MyGenome/1")
if genome is None:
    genome = safe_get_object(12345, "MyGenome_backup/1")
```

### Batch Processing with Recovery
```python
def process_batch(object_refs, workspace_id):
    """Process multiple objects with error recovery."""
    results = []
    failed = []

    for ref in object_refs:
        try:
            obj = ws.get_object(workspace_id, ref)
            result = process_object(obj)
            results.append(result)
        except Exception as e:
            ws.log_error(f"Failed to process {ref}: {e}")
            failed.append({"ref": ref, "error": str(e)})

    ws.log_info(f"Processed {len(results)}/{len(object_refs)} objects")
    if failed:
        ws.log_warning(f"Failed: {len(failed)} objects")

    return results, failed
```

## Pattern 10: Caching Results

### File-Based Caching
```python
import os
import json
import hashlib

class CachedAnalysis(BaseUtils):
    def __init__(self, cache_dir="~/.kbutillib_cache"):
        super().__init__()
        self.cache_dir = os.path.expanduser(cache_dir)
        os.makedirs(self.cache_dir, exist_ok=True)

    def _cache_key(self, method, params):
        """Generate cache key from method and params."""
        key_str = f"{method}:{json.dumps(params, sort_keys=True)}"
        return hashlib.md5(key_str.encode()).hexdigest()

    def _get_cached(self, key):
        """Retrieve cached result."""
        cache_file = os.path.join(self.cache_dir, f"{key}.json")
        if os.path.exists(cache_file):
            return self.load_util_data(cache_file)
        return None

    def _set_cached(self, key, data):
        """Store result in cache."""
        cache_file = os.path.join(self.cache_dir, f"{key}.json")
        self.save_util_data(cache_file, data)

    def cached_operation(self, method_func, params):
        """Run operation with caching."""
        key = self._cache_key(method_func.__name__, params)

        cached = self._get_cached(key)
        if cached:
            self.log_debug(f"Cache hit: {key}")
            return cached

        self.log_debug(f"Cache miss: {key}")
        result = method_func(**params)
        self._set_cached(key, result)
        return result
```

## Example Notebooks Reference

| Notebook | Purpose | Key Patterns |
|----------|---------|--------------|
| `ConfigureEnvironment.ipynb` | Initial setup | Configuration, tokens |
| `BVBRCGenomeConversion.ipynb` | Import genomes | External API, conversion |
| `AssemblyUploadDownload.ipynb` | Assembly handling | Workspace operations |
| `SKANIGenomeDistance.ipynb` | Genome similarity | External tools, caching |
| `ProteinLanguageModels.ipynb` | PLM analysis | AI/ML integration |
| `StoichiometryAnalysis.ipynb` | Reaction analysis | Biochemistry operations |
| `AICuration.ipynb` | AI curation | LLM integration, caching |
| `KBaseWorkspaceUtilities.ipynb` | Workspace ops | Type discovery, metadata |
