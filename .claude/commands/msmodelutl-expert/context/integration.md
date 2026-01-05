# MSModelUtil Integration Map

## Module Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         MSModelUtil                              │
│                    (Central Model Wrapper)                       │
└───────────────────────────┬─────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────────────┐
│    MSFBA      │   │  MSGapfill    │   │   MSPackageManager    │
│  (FBA runner) │   │  (Gapfilling) │   │  (Constraint pkgs)    │
└───────────────┘   └───────────────┘   └───────────────────────┘
        │                   │                   │
        └───────────────────┼───────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────────────┐
│  MSMedia      │   │MSATPCorrection│   │   ModelSEEDBiochem    │
│  (Media def)  │   │ (ATP tests)   │   │  (Reaction database)  │
└───────────────┘   └───────────────┘   └───────────────────────┘
```

## Key Relationships

### MSModelUtil ↔ MSGapfill

**Connection:**
- MSGapfill takes MSModelUtil in constructor
- Sets `mdlutl.gfutl = self` for bidirectional access

**Methods Used:**
- `mdlutl.test_solution()` - Validates gapfilling solutions
- `mdlutl.reaction_expansion_test()` - Finds minimal reaction sets
- `mdlutl.add_gapfilling()` - Records integrated solutions
- `mdlutl.assign_reliability_scores_to_reactions()` - Scores reactions for gapfilling

**Example:**
```python
from modelseedpy.core.msgapfill import MSGapfill

# MSGapfill stores reference to mdlutl
gapfill = MSGapfill(mdlutl, default_target="bio1")
# Now: mdlutl.gfutl == gapfill

# Use mdlutl methods for solution validation
solution = gapfill.run_gapfilling(media, target="bio1")
unneeded = mdlutl.test_solution(solution, ["bio1"], [media], [0.1])
```

### MSModelUtil ↔ MSPackageManager

**Connection:**
- Created automatically in `__init__`: `self.pkgmgr = MSPackageManager.get_pkg_mgr(model)`
- Provides FBA constraint packages

**Methods Used:**
- `mdlutl.pkgmgr.getpkg("KBaseMediaPkg").build_package(media)` - Apply media constraints
- `mdlutl.pkgmgr.getpkg("ObjectivePkg")` - Set objectives
- All FBA packages access model through MSPackageManager

**Example:**
```python
# MSModelUtil uses pkgmgr internally for set_media()
mdlutl.set_media(media)
# Equivalent to:
# mdlutl.pkgmgr.getpkg("KBaseMediaPkg").build_package(media)
```

### MSModelUtil ↔ MSATPCorrection

**Connection:**
- Lazy-loaded via `get_atputl()`
- Sets `self.atputl` for caching
- Used for ATP production tests during gapfilling

**Methods Used:**
- `mdlutl.get_atputl()` - Get or create MSATPCorrection
- `mdlutl.get_atp_tests()` - Get ATP test conditions
- ATP tests are used as constraints during gapfilling

**Example:**
```python
from modelseedpy.core.mstemplate import MSTemplateBuilder

template = MSTemplateBuilder.build_core_template()
atputl = mdlutl.get_atputl(core_template=template)
tests = mdlutl.get_atp_tests(core_template=template)

# Tests are condition dicts that can be used with test_single_condition
for test in tests:
    passed = mdlutl.test_single_condition(test)
```

### MSModelUtil ↔ ModelSEEDBiochem

**Connection:**
- Used for reaction/compound database lookups
- Not stored as instance attribute (imported when needed)

**Methods Used:**
- `mdlutl.add_ms_reaction()` - Adds reactions from ModelSEED database
- `mdlutl.assign_reliability_scores_to_reactions()` - Uses biochemistry data for scoring

**Example:**
```python
# Add ModelSEED reactions by ID
reactions = mdlutl.add_ms_reaction({
    "rxn00001": "c0",  # Reaction ID -> compartment
    "rxn00002": "c0"
})
```

### MSModelUtil ↔ MSFBA

**Connection:**
- MSFBA wraps `model_or_mdlutl` input
- Uses `MSModelUtil.get()` for consistent access

**Example:**
```python
from modelseedpy.core.msfba import MSFBA

# MSFBA internally calls MSModelUtil.get()
fba = MSFBA(mdlutl)
# or
fba = MSFBA(model)  # Will create/get MSModelUtil
```

### MSModelUtil ↔ MSMedia

**Connection:**
- MSMedia objects are passed to `set_media()`
- Used in test conditions

**Example:**
```python
from modelseedpy.core.msmedia import MSMedia

# Create media
media = MSMedia.from_dict({"EX_cpd00027_e0": 10})

# Apply to model
mdlutl.add_missing_exchanges(media)
mdlutl.set_media(media)
```

## Dependency Chain

```
User Code
    │
    ▼
MSGapfill / MSFBA / MSCommunity
    │
    ▼
MSModelUtil  ◄──────────────────┐
    │                           │
    ├── MSPackageManager ───────┤
    │       │                   │
    │       ▼                   │
    │   FBA Packages            │
    │                           │
    ├── MSATPCorrection ────────┤
    │                           │
    └── ModelSEEDBiochem        │
            │                   │
            └───────────────────┘
```

## Instance Attributes Set by Other Modules

| Attribute | Set By | Purpose |
|-----------|--------|---------|
| `mdlutl.gfutl` | MSGapfill | Reference to gapfiller |
| `mdlutl.atputl` | get_atputl() | Cached ATP correction utility |
| `mdlutl.pkgmgr` | __init__ | Package manager for constraints |
| `mdlutl.reaction_scores` | MSGapfill | Gapfilling reaction scores |

## Cross-Module Workflows

### Gapfilling Workflow

```python
# 1. Create MSModelUtil
mdlutl = MSModelUtil.get(model)

# 2. Create MSGapfill (sets mdlutl.gfutl)
gapfill = MSGapfill(mdlutl)

# 3. Get ATP tests (creates mdlutl.atputl)
atp_tests = mdlutl.get_atp_tests(core_template=template)

# 4. Run gapfilling (uses pkgmgr internally)
solution = gapfill.run_gapfilling(media, target="bio1")

# 5. Validate solution (uses test_solution)
unneeded = mdlutl.test_solution(solution, ["bio1"], [media], [0.1])

# 6. Record gapfilling
mdlutl.add_gapfilling(solution)
```

### FBA Workflow

```python
# 1. Create MSModelUtil
mdlutl = MSModelUtil.get(model)

# 2. Set media (uses pkgmgr)
mdlutl.add_missing_exchanges(media)
mdlutl.set_media(media)

# 3. Run FBA (through cobra.Model)
solution = mdlutl.model.optimize()

# 4. Analyze results
print(f"Growth: {solution.objective_value}")
```

### Community Modeling Workflow

```python
from modelseedpy.community.mscommunity import MSCommunity

# MSCommunity creates MSModelUtil for each member
community = MSCommunity(model=community_model, member_models=[m1, m2])

# Each member has its own MSModelUtil
for member in community.members:
    mdlutl = member.model_util
    # Work with individual member
```
