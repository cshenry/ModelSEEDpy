# KBUtilLib Architecture

Comprehensive architecture documentation for KBUtilLib developers.

## Core Design Philosophy

KBUtilLib is built on three core principles:

1. **Composability** - Utility classes combine via multiple inheritance
2. **Modularity** - Each utility is independent and self-contained
3. **Simplicity** - Focused classes with clear responsibilities

## Repository Structure

```
KBUtilLib/
├── src/kbutillib/              # Main package (37 modules, ~16,800 lines)
│   ├── __init__.py             # Public exports and __all__
│   ├── __main__.py             # CLI entry point (Click-based)
│   │
│   ├── # Foundation Layer
│   ├── base_utils.py           # BaseUtils - logging, provenance, common methods
│   ├── shared_env_utils.py     # SharedEnvUtils - config, tokens, env vars
│   │
│   ├── # KBase Integration Layer
│   ├── kb_ws_utils.py          # KBWSUtils - Workspace Service API
│   ├── kb_genome_utils.py      # KBGenomeUtils - genome analysis
│   ├── kb_annotation_utils.py  # KBAnnotationUtils - annotations
│   ├── kb_model_utils.py       # KBModelUtils - metabolic models
│   ├── kb_reads_utils.py       # KBReadsUtils - reads/assemblies
│   ├── kb_callback_utils.py    # KBCallbackUtils - callback services
│   ├── kb_sdk_utils.py         # KBSDKUtils - SDK development
│   ├── kb_uniprot_utils.py     # KBUniProtUtils - UniProt API
│   ├── kb_plm_utils.py         # KBPLMUtils - protein language models
│   │
│   ├── # ModelSEED Integration Layer
│   ├── ms_biochem_utils.py     # MSBiochemUtils - biochemistry DB
│   ├── ms_fba_utils.py         # MSFBAUtils - FBA operations
│   ├── ms_reconstruction_utils.py  # MSReconstructionUtils - model building
│   │
│   ├── # AI/ML Layer
│   ├── argo_utils.py           # ArgoUtils - LLM integration
│   ├── ai_curation_utils.py    # AICurationUtils - AI curation
│   │
│   ├── # External APIs Layer
│   ├── bvbrc_utils.py          # BVBRCUtils - BV-BRC API
│   ├── patric_ws_utils.py      # PatricWSUtils - PATRIC workspace
│   ├── rcsb_pdb_utils.py       # RCSBPDBUtils - PDB structures
│   │
│   ├── # Utility Layer
│   ├── notebook_utils.py       # NotebookUtils - Jupyter enhancements
│   ├── escher_utils.py         # EscherUtils - visualization
│   ├── skani_utils.py          # SKANIUtils - genome distance
│   ├── model_standardization_utils.py  # Model standardization
│   └── thermo_utils.py         # ThermoUtils - thermodynamics
│
├── notebooks/                   # Example Jupyter notebooks
│   ├── ConfigureEnvironment.ipynb
│   ├── BVBRCGenomeConversion.ipynb
│   ├── AssemblyUploadDownload.ipynb
│   ├── SKANIGenomeDistance.ipynb
│   ├── ProteinLanguageModels.ipynb
│   ├── StoichiometryAnalysis.ipynb
│   ├── AICuration.ipynb
│   └── KBaseWorkspaceUtilities.ipynb
│
├── examples/                    # Standalone example scripts
│   ├── example_ai_curation_usage.py
│   ├── example_bvbrc_usage.py
│   └── example_skani_usage.py
│
├── tests/                       # pytest test suite
│   ├── conftest.py             # Fixtures and configuration
│   ├── test_base_utils.py
│   └── test_*.py               # Module-specific tests
│
├── docs/                        # Sphinx documentation
│   ├── conf.py                 # Sphinx configuration
│   ├── index.md                # Documentation home
│   └── modules/                # Module documentation
│
├── dependencies/                # Git submodules
│   ├── ModelSEEDpy/
│   ├── ModelSEEDDatabase/
│   ├── cobrakbase/
│   └── cb_annotation_ontology_api/
│
├── config/                      # Configuration templates
│   └── default_config.yaml
│
├── pyproject.toml              # UV/pip packaging
├── DEPENDENCIES.md             # Dependency management docs
└── README.md                   # Project overview
```

## Module Hierarchy

### Inheritance Tree

```
BaseUtils (base_utils.py)
│
│   Core functionality:
│   - Logging (logger, log_info, log_debug, log_error)
│   - Provenance tracking (initialize_call, provenance list)
│   - Argument validation (validate_args)
│   - Data I/O (save_util_data, load_util_data)
│
└── SharedEnvUtils (shared_env_utils.py)
    │
    │   Configuration management:
    │   - Config file loading (load_config, config object)
    │   - Token management (get_token, set_token)
    │   - Environment variables
    │
    ├── KBWSUtils (kb_ws_utils.py)
    │   │   KBase Workspace Service:
    │   │   - Object retrieval/storage
    │   │   - Type specs
    │   │   - Workspace listing
    │   │
    │   ├── KBGenomeUtils (kb_genome_utils.py)
    │   │       Genome analysis:
    │   │       - Feature extraction
    │   │       - Sequence translation
    │   │       - Annotation access
    │   │
    │   ├── KBAnnotationUtils (kb_annotation_utils.py)
    │   │       Annotation management:
    │   │       - Ontology filtering
    │   │       - EC/KEGG extraction
    │   │       - Reaction mapping
    │   │
    │   ├── KBModelUtils (kb_model_utils.py)
    │   │       Model operations:
    │   │       - Model retrieval
    │   │       - Reaction/metabolite access
    │   │       - Template management
    │   │
    │   └── KBReadsUtils (kb_reads_utils.py)
    │           Reads/assembly handling:
    │           - Assembly objects
    │           - ReadSet management
    │
    ├── PatricWSUtils (patric_ws_utils.py)
    │       PATRIC workspace access
    │
    ├── MSBiochemUtils (ms_biochem_utils.py)
    │       ModelSEED biochemistry:
    │       - Compound/reaction search
    │       - Database indexing
    │
    ├── MSFBAUtils (ms_fba_utils.py)
    │       FBA operations:
    │       - Run FBA/pFBA/FVA
    │       - Media configuration
    │       - Constraints
    │
    ├── MSReconstructionUtils (ms_reconstruction_utils.py)
    │       Model reconstruction:
    │       - Draft model building
    │       - Gap-filling
    │
    ├── ArgoUtils (argo_utils.py)
    │   │   LLM integration:
    │   │   - Query Argo API
    │   │   - Model selection
    │   │
    │   └── AICurationUtils (ai_curation_utils.py)
    │           AI curation:
    │           - Reaction curation
    │           - Caching
    │
    ├── BVBRCUtils (bvbrc_utils.py)
    │       BV-BRC API access
    │
    ├── KBUniProtUtils (kb_uniprot_utils.py)
    │       UniProt REST API
    │
    ├── RCSBPDBUtils (rcsb_pdb_utils.py)
    │       PDB structure access
    │
    ├── KBPLMUtils (kb_plm_utils.py)
    │       Protein language models
    │
    └── SKANIUtils (skani_utils.py)
            Genome distance computation

# Independent utilities (not in SharedEnvUtils hierarchy)
├── NotebookUtils (notebook_utils.py) - inherits BaseUtils
├── EscherUtils (escher_utils.py) - inherits BaseUtils
├── ModelStandardizationUtils - inherits BaseUtils
└── ThermoUtils - inherits BaseUtils
```

## Configuration System

### Config File Priority
1. Explicit `config_file` parameter
2. `~/kbutillib_config.yaml` (user config)
3. `config/default_config.yaml` (repository defaults)

### Config File Structure
```yaml
# Example configuration
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
```

### Token Management
```python
# Tokens stored per namespace
tokens = {
    "kbase": "...",
    "argo": "...",
    "custom": "..."
}

# Environment variables also checked:
# KBASE_AUTH_TOKEN, ARGO_API_TOKEN
```

## Provenance System

Every method call can be tracked for reproducibility:

```python
class MyUtils(BaseUtils):
    def my_method(self, param1):
        # Start tracking
        self.initialize_call("my_method", {"param1": param1})

        # Method implementation
        result = self._do_work(param1)

        # Logged to provenance list
        return result

# Access provenance
utils = MyUtils()
utils.my_method("test")
print(utils.provenance)
# [{"method": "my_method", "params": {"param1": "test"}, "timestamp": "..."}]
```

## Export System

The `__init__.py` uses try/except for optional dependencies:

```python
# src/kbutillib/__init__.py

# Always available
from .base_utils import BaseUtils
from .shared_env_utils import SharedEnvUtils

# Optional - may have missing dependencies
try:
    from .kb_plm_utils import KBPLMUtils
except ImportError:
    KBPLMUtils = None

__all__ = [
    "BaseUtils",
    "SharedEnvUtils",
    "KBPLMUtils",  # May be None
    # ...
]
```

## Dependency Architecture

### Core Dependencies (always required)
- `requests` - HTTP client
- `pyyaml` - Configuration files
- `python-dotenv` - Environment variables

### Optional Dependencies (graceful degradation)
- `pandas` - DataFrame operations
- `cobra` - Constraint-based modeling
- `ipywidgets` - Notebook widgets
- `escher` - Pathway visualization

### Git Submodule Dependencies
Located in `dependencies/`:
- `ModelSEEDpy` - Metabolic modeling
- `ModelSEEDDatabase` - Biochemistry data
- `cobrakbase` - KBase COBRA extensions
- `cb_annotation_ontology_api` - Annotation ontology

## Testing Architecture

### Test Organization
```
tests/
├── conftest.py          # Shared fixtures
├── test_base_utils.py   # BaseUtils tests
├── test_kb_ws_utils.py  # KBWSUtils tests
└── ...
```

### Fixtures (conftest.py)
```python
import pytest

@pytest.fixture
def mock_config():
    return {
        "kbase": {"endpoint": "https://test.kbase.us"}
    }

@pytest.fixture
def base_utils():
    return BaseUtils()
```

### Test Patterns
```python
class TestBaseUtils:
    def test_initialization(self, base_utils):
        assert base_utils.logger is not None

    def test_logging(self, base_utils):
        base_utils.log_info("Test message")
        # Assert logging occurred

    @pytest.mark.parametrize("level", ["DEBUG", "INFO", "WARNING"])
    def test_log_levels(self, base_utils, level):
        base_utils.logger.setLevel(level)
        assert base_utils.logger.level == getattr(logging, level)
```

## CI/CD Pipeline

### GitHub Actions Workflow
```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          submodules: recursive

      - name: Install uv
        uses: astral-sh/setup-uv@v1

      - name: Run tests
        run: uv run pytest

      - name: Lint
        run: uv run ruff check src/

      - name: Type check
        run: uv run mypy src/kbutillib/
```

## Build System

### pyproject.toml Structure
```toml
[project]
name = "kbutillib"
version = "0.1.0"
description = "Modular utility framework for bioinformatics"
requires-python = ">=3.9"
dependencies = [
    "requests>=2.28",
    "pyyaml>=6.0",
    "python-dotenv>=1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
    "ruff>=0.1",
    "mypy>=1.0",
]
notebooks = [
    "jupyter>=1.0",
    "ipywidgets>=8.0",
    "itables>=1.0",
]

[project.scripts]
kbutillib = "kbutillib.__main__:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
line-length = 100
target-version = "py39"

[tool.mypy]
python_version = "3.9"
ignore_missing_imports = true
```

## Documentation System

### Sphinx + MyST Configuration
```python
# docs/conf.py
extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
]

myst_enable_extensions = [
    "colon_fence",
    "deflist",
]
```

### Documentation Structure
```
docs/
├── conf.py              # Sphinx config
├── index.md             # Home page
├── getting-started.md   # Quick start
├── modules/             # Module docs
│   ├── base_utils.md
│   ├── kb_ws_utils.md
│   └── ...
└── api/                 # Auto-generated API docs
```

## Error Handling Patterns

### Standard Error Pattern
```python
def my_method(self, required_param, optional_param=None):
    # Validate required parameters
    if not required_param:
        raise ValueError("required_param is required")

    try:
        result = self._external_call(required_param)
    except ConnectionError as e:
        self.log_error(f"Connection failed: {e}")
        raise
    except Exception as e:
        self.log_error(f"Unexpected error: {e}")
        raise

    return result
```

### Graceful Degradation
```python
try:
    from .optional_module import OptionalFeature
    HAS_OPTIONAL = True
except ImportError:
    OptionalFeature = None
    HAS_OPTIONAL = False

class MyUtils(BaseUtils):
    def optional_method(self):
        if not HAS_OPTIONAL:
            self.log_warning("Optional feature not available")
            return None
        return OptionalFeature.do_something()
```
