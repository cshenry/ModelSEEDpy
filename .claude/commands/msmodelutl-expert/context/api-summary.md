# MSModelUtil API Quick Reference

## Core Concepts

- **Singleton pattern**: Use `MSModelUtil.get(model)` to get/create instances
- **Wraps cobra.Model**: Access via `mdlutl.model`
- **Integrates with MSPackageManager**: Access via `mdlutl.pkgmgr`
- **Location**: `modelseedpy/core/msmodelutl.py` (~2,000 lines)

## Essential Methods

### Factory/Initialization
| Method | Description |
|--------|-------------|
| `MSModelUtil.get(model)` | Get or create instance (PREFERRED) |
| `MSModelUtil.from_cobrapy(filename)` | Load from file |
| `MSModelUtil(model)` | Direct construction |

### Metabolite Search
| Method | Description |
|--------|-------------|
| `find_met(name, compartment=None)` | Find metabolites by name/ID |
| `msid_hash()` | Get ModelSEED ID to metabolite mapping |
| `metabolite_msid(met)` [static] | Extract ModelSEED ID from metabolite |
| `build_metabolite_hash()` | Build internal lookup caches |

### Reaction Operations
| Method | Description |
|--------|-------------|
| `rxn_hash()` | Get stoichiometry to reaction mapping |
| `find_reaction(stoichiometry)` | Find reaction by stoichiometry |
| `exchange_list()` | Get exchange reactions |
| `exchange_hash()` | Metabolite to exchange mapping |
| `is_core(rxn)` | Check if reaction is core metabolism |

### Exchange/Transport
| Method | Description |
|--------|-------------|
| `add_exchanges_for_metabolites(cpds, uptake, excretion)` | Add exchanges |
| `add_transport_and_exchange_for_metabolite(met, direction)` | Add transport |
| `add_missing_exchanges(media)` | Fill media gaps |

### Media/FBA
| Method | Description |
|--------|-------------|
| `set_media(media)` | Configure growth media |
| `apply_test_condition(condition)` | Apply test constraints |
| `test_single_condition(condition)` | Run single test |
| `test_condition_list(conditions)` | Run multiple tests |

### Gapfilling Support
| Method | Description |
|--------|-------------|
| `test_solution(solution, targets, medias, thresholds)` | Validate solutions |
| `add_gapfilling(solution)` | Record integrated gapfilling |
| `reaction_expansion_test(rxn_list, conditions)` | Find minimal sets |

### ATP Correction
| Method | Description |
|--------|-------------|
| `get_atputl()` | Get ATP correction utility |
| `get_atp_tests()` | Get ATP test conditions |

### Model Editing
| Method | Description |
|--------|-------------|
| `add_ms_reaction(rxn_dict)` | Add ModelSEED reactions |
| `add_atp_hydrolysis(compartment)` | Add ATP hydrolysis |
| `get_attributes()` / `save_attributes()` | Model metadata |

### Analysis
| Method | Description |
|--------|-------------|
| `assign_reliability_scores_to_reactions()` | Score reactions |
| `find_unproducible_biomass_compounds()` | Biomass sensitivity |
| `analyze_minimal_reaction_set(solution, label)` | Alternative analysis |

### I/O
| Method | Description |
|--------|-------------|
| `save_model(filename, format)` | Save model to file |
| `printlp(filename)` | Write LP for debugging |
| `print_solutions(solution_hash, filename)` | Export solutions to CSV |

## Key Instance Attributes

```python
self.model              # The wrapped cobra.Model
self.pkgmgr             # MSPackageManager for this model
self.atputl             # MSATPCorrection instance (lazy-loaded)
self.gfutl              # MSGapfill reference (set by gapfiller)
self.metabolite_hash    # Metabolite lookup cache
self.test_objective     # Current test objective value
self.reaction_scores    # Gapfilling reaction scores
self.integrated_gapfillings  # List of integrated solutions
self.attributes         # Model metadata dictionary
```

## Condition Dictionary Format

```python
condition = {
    "media": MSMedia,           # Media object
    "objective": "bio1",        # Objective reaction ID
    "is_max_threshold": True,   # True = FAIL if value >= threshold
    "threshold": 0.1            # Threshold value
}
```

## Solution Dictionary Format

```python
solution = {
    "new": {"rxn00001_c0": ">"},      # Newly added reactions
    "reversed": {"rxn00002_c0": "<"}, # Direction-reversed reactions
    "media": media,                    # Media used
    "target": "bio1",                  # Target reaction
    "minobjective": 0.1,              # Minimum objective
    "binary_check": True              # Binary filtering done
}
```
