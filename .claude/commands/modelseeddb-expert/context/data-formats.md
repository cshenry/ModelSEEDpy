# ModelSEED Database Data Formats

## File Organization

Data files are located in `/Biochemistry/`:
- **Compounds**: `compound_00.tsv` through `compound_35.tsv` (~45,756 total entries)
- **Reactions**: `reaction_00.tsv` through `reaction_60.tsv` (~56,070 total entries)
- Each has corresponding `.json` format (auto-generated from TSV)

**Important**: TSV files are the master format. Never edit JSON files directly.

## Compound Schema (21 fields)

| # | Field | Type | Description |
|---|-------|------|-------------|
| 1 | id | string | Unique ID format `cpdNNNNN` (e.g., cpd00001) |
| 2 | abbreviation | string | Short name of compound |
| 3 | name | string | Long descriptive name |
| 4 | formula | string | Chemical formula (Hill system, protonated form) |
| 5 | mass | float/null | Molecular weight or "null" |
| 6 | source | string | Source database (currently "Primary Database") |
| 7 | inchikey | string | IUPAC InChI Key identifier |
| 8 | charge | int | Electric charge of compound |
| 9 | is_core | bool | True if in core biochemistry (all true currently) |
| 10 | is_obsolete | bool | True if obsolete/replaced |
| 11 | linked_compound | string | Semicolon-separated related compound IDs or "null" |
| 12 | is_cofactor | bool | True if compound is a cofactor |
| 13 | deltag | float/null | Free energy change (kcal/mol) or "null" |
| 14 | deltagerr | float/null | Free energy error or "null" |
| 15 | pka | string | Acid dissociation constants (see format below) |
| 16 | pkb | string | Base dissociation constants (see format below) |
| 17 | abstract_compound | bool | Abstraction flag (all null currently) |
| 18 | comprised_of | string | Component info or "null" |
| 19 | aliases | string | Semicolon-separated alternative names (see format below) |
| 20 | smiles | string | SMILES structure representation |
| 21 | notes | string | Abbreviated notes (GC, EQ, EQU, etc.) |

### pKa/pKb Format

Format: `fragment:atom:value`

- **fragment**: Molecular fragment index (usually 1)
- **atom**: Atom index within fragment
- **value**: Dissociation constant value

Multiple values separated by semicolon.

Example for NAD:
```
1:17:1.8;1:18:2.56;1:6:12.32;1:25:11.56;1:35:13.12
```

### Alias Format

Format: `"source:value"`

- **source**: Name of external database
- **value**: ID or name in that database

Multiple aliases separated by semicolon.

Example for Cobamide (cpd00181):
```
"KEGG:C00210";"name:Cobamide";"searchname:cobamide";"ModelSEED:cpd00181";"KBase:kb|cpd.181"
```

Common alias sources:
- KEGG, BiGG, MetaCyc, ChEBI, HMDB
- name, searchname (normalized lowercase)
- ModelSEED, KBase

### Example Compound Entry (cpd00001 - Water)

```
id: cpd00001
abbreviation: H2O
name: H2O
formula: H2O
mass: 18.0
charge: 0
inchikey: XLYOFNOQVPJJNP-UHFFFAOYSA-N
deltag: -37.54
is_cofactor: 0
smiles: O
```

## Reaction Schema (22 fields)

| # | Field | Type | Description |
|---|-------|------|-------------|
| 1 | id | string | Unique ID format `rxnNNNNN` (e.g., rxn00001) |
| 2 | abbreviation | string | Short reaction name |
| 3 | name | string | Long reaction name |
| 4 | code | string | Equation using compound IDs (pre-protonation) |
| 5 | stoichiometry | string | Detailed stoichiometry format |
| 6 | is_transport | bool | True if transport reaction |
| 7 | equation | string | Equation using compound IDs (post-protonation) |
| 8 | definition | string | Equation using compound names |
| 9 | reversibility | string | Direction: ">", "<", "=", "?" |
| 10 | direction | string | Direction: ">", "<", "=" |
| 11 | abstract_reaction | bool | Abstraction flag (all null currently) |
| 12 | pathways | string | Semicolon-separated pathway associations |
| 13 | aliases | string | Alternative names (same format as compounds) |
| 14 | ec_numbers | string | Enzyme Commission numbers |
| 15 | deltag | float | Free energy change or 10000000 if unknown |
| 16 | deltagerr | float | Free energy error or 10000000 if unknown |
| 17 | compound_ids | string | Semicolon-separated compound IDs involved |
| 18 | status | string | Validation status (see below) |
| 19 | is_obsolete | bool | True if obsolete/replaced |
| 20 | linked_reaction | string | Related reaction IDs or "null" |
| 21 | notes | string | Abbreviated notes |
| 22 | source | string | Source database |

### Equation Format (code/equation fields)

Format: `(n) cpdid[m]`

- **n**: Coefficient
- **cpdid**: Compound ID
- **m**: Compartment index (0=cytosol, 1=extracellular, etc.)

Compounds separated by `+`, sides separated by direction symbol (`<=>`, `=>`, `<=`).

Example (rxn00001):
```
(1) cpd00001[0] + (1) cpd00012[0] <=> (2) cpd00009[0] + (1) cpd00067[0]
```

### Definition Format (compound names)

Same format but with compound names instead of IDs:
```
(1) H2O[0] + (1) PPi[0] <=> (2) Phosphate[0] + (1) H+[0]
```

### Stoichiometry Format

Format: `n:cpdid:m:i:"cpdname"`

- **n**: Coefficient (negative=reactant, positive=product)
- **cpdid**: Compound ID
- **m**: Compartment index
- **i**: Community index (legacy, usually 0)
- **cpdname**: Compound name

Compounds separated by semicolon.

Example (rxn00001):
```
-1:cpd00001:0:0:"H2O";-1:cpd00012:0:0:"PPi";2:cpd00009:0:0:"Phosphate";1:cpd00067:0:0:"H+"
```

### Status Field Values

Multiple values separated by `|` character.

| Status | Meaning |
|--------|---------|
| OK | Reaction is valid and balanced |
| MI:element:diff | Mass imbalance (e.g., MI:C:-1 = 1 extra C on left) |
| CI:value | Charge imbalance (positive = right side larger) |
| HB | Hydrogen-balanced (H added to balance) |
| EMPTY | Reactants cancel out completely |
| CPDFORMERROR | Compound has no/invalid formula |

**Mass Imbalance Example** (rxn00277):
```
(1) Glycine[0] <=> (1) HCN[0]
Status: MI:C:-1/H:-4/O:-2
```
(1 extra C, 4 extra H, 2 extra O on left side)

**Charge Imbalance Example** (rxn00008):
```
(2) H2O[0] <=> (1) H2O2[0] + (2) H+[0]
Status: CI:2
```
(Right side has +2 charge imbalance)

### Example Reaction Entry (rxn00001)

```
id: rxn00001
name: diphosphate phosphohydrolase
code: (1) cpd00001 + (1) cpd00012 <=> (2) cpd00009 + (1) cpd00067
equation: (1) cpd00001[0] + (1) cpd00012[0] <=> (2) cpd00009[0] + (1) cpd00067[0]
definition: (1) H2O[0] + (1) PPi[0] <=> (2) Phosphate[0] + (1) H+[0]
stoichiometry: -1:cpd00001:0:0:"H2O";-1:cpd00012:0:0:"PPi";2:cpd00009:0:0:"Phosphate";1:cpd00067:0:0:"H+"
status: OK
is_transport: 0
reversibility: =
direction: =
ec_numbers: 3.6.1.1
compound_ids: cpd00001;cpd00009;cpd00012;cpd00067
```

## Compartment Indices

| Index | Compartment |
|-------|-------------|
| 0 | Cytosol (c0) |
| 1 | Extracellular (e0) |
| 2+ | Other compartments (model-specific) |

## Supporting Data Directories

### Aliases/ Directory
- `Unique_ModelSEED_Compound_Aliases.txt` - Compound to external ID mappings
- `Unique_ModelSEED_Reaction_Aliases.txt` - Reaction to external ID mappings
- `Unique_ModelSEED_Reaction_Pathways.txt` - Pathway associations
- `Unique_ModelSEED_Reaction_ECs.txt` - EC number mappings
- `Source_Classifiers.txt` - Three-tier source classification

### Structures/ Directory
- SMILES, InChI, InChIKey from multiple sources
- pKa/pKb calculations from Marvin
- Charged vs Original structure variants

### Thermodynamics/ Directory
- Group contribution calculations
- eQuilibrator estimates
- Delta G values and errors

### Provenance/ Directory
- Original source files from KEGG, MetaCyc, Rhea, ChEBI
- MetaNetX mapping files
