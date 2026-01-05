# KBUtilLib Integration Guide

## Overview

KBUtilLib is a modular utility framework that should be used in ALL KBase SDK applications to avoid code duplication. The library provides composable utility classes that can be combined via multiple inheritance.

**Repository:** `/Users/chenry/Dropbox/Projects/KBUtilLib`
**GitHub:** https://github.com/cshenry/KBUtilLib

## Installation in Dockerfile

**ALWAYS include KBUtilLib in your Dockerfile:**

```dockerfile
# Install KBUtilLib for shared utilities
RUN cd /kb/module && \
    git clone https://github.com/cshenry/KBUtilLib.git && \
    cd KBUtilLib && \
    pip install -e .
```

## Available Modules

### Core Foundation

| Module | Purpose |
|--------|---------|
| `BaseUtils` | Logging, error handling, dependency management |
| `SharedEnvUtils` | Configuration files, authentication tokens |
| `NotebookUtils` | Jupyter integration, enhanced displays |

### KBase Data Access

| Module | Purpose |
|--------|---------|
| `KBWSUtils` | Workspace operations: get/save objects |
| `KBCallbackUtils` | Callback server handling for SDK apps |
| `KBSDKUtils` | SDK development utilities |

### Analysis Utilities

| Module | Purpose |
|--------|---------|
| `KBGenomeUtils` | Genome parsing, feature extraction, translation |
| `KBAnnotationUtils` | Gene/protein annotation workflows |
| `KBModelUtils` | Metabolic model analysis, FBA utilities |
| `MSBiochemUtils` | ModelSEED biochemistry database access |
| `KBReadsUtils` | Reads processing and QC |

### External Integrations

| Module | Purpose |
|--------|---------|
| `ArgoUtils` | Language model integration |
| `BVBRCUtils` | BV-BRC database access |
| `PatricWSUtils` | PATRIC workspace utilities |

## Usage Patterns

### Pattern 1: Single Module
```python
from kbutillib import KBWSUtils

class MyApp:
    def __init__(self, callback_url):
        self.ws_utils = KBWSUtils(callback_url=callback_url)

    def run(self, params):
        obj = self.ws_utils.get_object(params['workspace'], params['ref'])
```

### Pattern 2: Multiple Inheritance (Recommended)
```python
from kbutillib import KBWSUtils, KBGenomeUtils, KBCallbackUtils, SharedEnvUtils

class MyAppUtils(KBWSUtils, KBGenomeUtils, KBCallbackUtils, SharedEnvUtils):
    """Custom utility class combining needed modules."""
    pass

class MyApp:
    def __init__(self, callback_url):
        self.utils = MyAppUtils(callback_url=callback_url)

    def run(self, params):
        # Access all methods from combined classes
        genome = self.utils.get_object(params['workspace'], params['ref'])
        features = self.utils.extract_features_by_type(genome, 'CDS')
        report = self.utils.create_extended_report({...})
```

### Pattern 3: In Implementation File
```python
#BEGIN_HEADER
import os
from kbutillib import KBWSUtils, KBCallbackUtils, KBGenomeUtils

class AppUtils(KBWSUtils, KBCallbackUtils, KBGenomeUtils):
    """Combined utilities for this app."""
    pass
#END_HEADER

class MyModule:
    def __init__(self, config):
        #BEGIN_CONSTRUCTOR
        self.callback_url = os.environ['SDK_CALLBACK_URL']
        self.scratch = config['scratch']
        self.utils = AppUtils(
            callback_url=self.callback_url,
            scratch=self.scratch
        )
        #END_CONSTRUCTOR

    def my_method(self, ctx, params):
        #BEGIN my_method
        workspace = params['workspace_name']

        # Get genome using KBWSUtils
        genome = self.utils.get_object(workspace, params['genome_ref'])

        # Parse genome using KBGenomeUtils
        features = self.utils.extract_features_by_type(genome, 'CDS')

        # Create report using KBCallbackUtils
        report_info = self.utils.create_extended_report({
            'message': f'Found {len(features)} CDS features',
            'workspace_name': workspace
        })

        return [{
            'report_name': report_info['name'],
            'report_ref': report_info['ref']
        }]
        #END my_method
```

## Key Methods Reference

### KBWSUtils

```python
# Get a single object
obj_data = utils.get_object(workspace, object_ref)

# Get object with metadata
obj, info = utils.get_object_with_info(workspace, object_ref)

# Save an object
info = utils.save_object(workspace, obj_type, obj_name, obj_data)

# List objects in workspace
objects = utils.list_objects(workspace, type_filter='KBaseGenomes.Genome')
```

### KBCallbackUtils

```python
# Create a report
report_info = utils.create_extended_report({
    'message': 'Analysis complete',
    'workspace_name': workspace,
    'objects_created': [{'ref': new_ref, 'description': 'My output'}],
    'file_links': [{'path': '/path/to/file.txt', 'name': 'results.txt'}],
    'html_links': [{'path': '/path/to/report.html', 'name': 'report'}]
})

# Download staging file
local_path = utils.download_staging_file(staging_file_path)

# Upload file to shock
shock_id = utils.upload_to_shock(file_path)
```

### KBGenomeUtils

```python
# Extract all features of a type
cds_features = utils.extract_features_by_type(genome_data, 'CDS')

# Translate DNA sequence
protein = utils.translate_sequence(dna_seq)

# Find ORFs in sequence
orfs = utils.find_orfs(sequence, min_length=100)

# Parse genome object
genome_info = utils.parse_genome_object(genome_data)
```

### KBModelUtils

```python
# Load model data
model_data = utils.get_model(workspace, model_ref)

# Get reactions/metabolites
reactions = utils.get_model_reactions(model_data)
metabolites = utils.get_model_metabolites(model_data)

# Check model consistency
issues = utils.validate_model(model_data)
```

### MSBiochemUtils

```python
# Search compounds
compounds = utils.search_compounds("glucose")

# Get reaction info
reaction = utils.get_reaction("rxn00001")

# Search reactions by compound
reactions = utils.find_reactions_with_compound("cpd00001")
```

## When to Add Code to KBUtilLib

If you're writing a function that:
1. Could be used in multiple KBase apps
2. Performs a common operation (parsing, converting, validating)
3. Wraps a KBase service in a cleaner way
4. Provides utility for a common data type

**Consider adding it to KBUtilLib instead of your app.**

### How to Add

1. Identify which module it belongs in (or create new one)
2. Add the method to the appropriate class
3. Add tests in `tests/`
4. Update documentation
5. Push to GitHub
6. Update your app's Dockerfile to get latest

## Configuration

KBUtilLib can be configured via `config.yaml`:

```yaml
kbase:
  endpoint: https://kbase.us/services
  token_env: KB_AUTH_TOKEN

scratch: /kb/module/work/tmp

logging:
  level: INFO
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

Load configuration:
```python
utils = MyAppUtils(config_file='config.yaml')
# Or
utils = MyAppUtils(callback_url=url, scratch=scratch_dir)
```

## Error Handling

KBUtilLib provides consistent error handling:

```python
from kbutillib.base_utils import KBUtilLibError

try:
    result = utils.get_object(workspace, ref)
except KBUtilLibError as e:
    # Handle KBUtilLib-specific errors
    logger.error(f"KBUtilLib error: {e}")
except Exception as e:
    # Handle other errors
    logger.error(f"Unexpected error: {e}")
```

## Testing

Test your integration:

```python
import pytest
from kbutillib import KBWSUtils

def test_workspace_access():
    utils = KBWSUtils(callback_url=test_callback_url)
    obj = utils.get_object('test_workspace', 'test_object')
    assert obj is not None
```
