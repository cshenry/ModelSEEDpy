# BiochemPy Library API Reference

The BiochemPy library provides Python interfaces for loading and manipulating ModelSEED biochemistry data.

**Location:** `/Libs/Python/BiochemPy/`

**Setup:**
```python
import sys
sys.path.append("/path/to/ModelSEEDDatabase/Libs/Python")
from BiochemPy import Compounds, Reactions
```

## Compounds Class

### Constructor

```python
Compounds(biochem_root='../../../Biochemistry/', cpds_file='compound_00.tsv')
```

**Attributes:**
- `BiochemRoot` - Path to Biochemistry directory
- `CpdsFile` - Path to first compound TSV file
- `AliasFile` - Path to compound aliases file
- `NameFile` - Path to compound names file
- `StructRoot` - Path to Structures directory
- `Headers` - List of TSV column headers

### Loading Methods

#### loadCompounds()
Load all compounds from JSON files.

```python
cpds_helper = Compounds()
cpds_dict = cpds_helper.loadCompounds()

# Returns: dict keyed by compound ID
# cpds_dict["cpd00001"] = {
#     "id": "cpd00001",
#     "name": "H2O",
#     "formula": "H2O",
#     "charge": 0,
#     "mass": 18.0,
#     ...
# }
```

#### loadCompounds_tsv()
Load compounds from TSV file (legacy, loads only one file).

```python
cpds_dict = cpds_helper.loadCompounds_tsv()
# WARNING: Only loads first file - use loadCompounds() instead
```

#### loadMSAliases(sources_array=[])
Load compound aliases from external databases.

```python
# Load all aliases
aliases = cpds_helper.loadMSAliases()

# Load specific sources
aliases = cpds_helper.loadMSAliases(["KEGG", "BiGG"])

# Returns: dict[compound_id][source] = [alias_list]
# aliases["cpd00001"]["KEGG"] = ["C00001"]
```

#### loadSourceAliases()
Load aliases indexed by source then external ID.

```python
source_aliases = cpds_helper.loadSourceAliases()

# Returns: dict[source][external_id] = [modelseed_ids]
# source_aliases["KEGG"]["C00001"] = ["cpd00001"]
```

#### loadNames()
Load compound names.

```python
names = cpds_helper.loadNames()

# Returns: dict[compound_id] = [name_list]
# names["cpd00001"] = ["H2O", "Water", ...]
```

#### loadStructures(sources_array=[], db_array=[], unique=True)
Load molecular structures.

```python
# Default: SMILES, InChIKey, InChI from KEGG and MetaCyc
structs = cpds_helper.loadStructures()

# Specific sources
structs = cpds_helper.loadStructures(
    sources_array=["SMILE", "InChIKey"],
    db_array=["KEGG"]
)

# ModelSEED consolidated structures
structs = cpds_helper.loadStructures(db_array=["ModelSEED"])
```

### Saving Methods

#### saveCompounds(compounds_dict)
Save compounds to partitioned TSV and JSON files.

```python
# After modifying compounds
cpds_helper.saveCompounds(cpds_dict)
# Creates compound_00.tsv, compound_00.json, compound_01.tsv, ...
```

#### saveAliases(alias_dict)
Save compound aliases.

```python
cpds_helper.saveAliases(aliases)
```

#### saveNames(names_dict)
Save compound names.

```python
cpds_helper.saveNames(names)
```

### Static Utility Methods

#### Compounds.searchname(name)
Generate search variations of a compound name.

```python
variations = Compounds.searchname("D-Glucose")
# Returns: ["D-Glucose", "d-glucose", "dglucose", ...]
```

#### Compounds.parseFormula(formula)
Parse chemical formula into atom counts.

```python
atoms = Compounds.parseFormula("C6H12O6")
# Returns: {"C": 6, "H": 12, "O": 6}

atoms = Compounds.parseFormula("H2O")
# Returns: {"H": 2, "O": 1}
```

#### Compounds.mergeFormula(formula)
Parse and normalize complex formulas.

```python
formula, notes = Compounds.mergeFormula("Mg(Al,Fe)Si4O10(OH).4H2O")
# Returns: ("Al2H10MgO16Si4", "PO")  # PO = polymeric formula note
```

#### Compounds.buildFormula(atoms_dict)
Build formula string from atom counts (Hill sorted).

```python
formula = Compounds.buildFormula({"C": 6, "H": 12, "O": 6})
# Returns: "C6H12O6"
```

#### Compounds.hill_sorted(atoms)
Generator yielding atoms in Hill order (C, H, then alphabetical).

```python
sorted_atoms = list(Compounds.hill_sorted(["O", "C", "H", "N"]))
# Returns: ["C", "H", "N", "O"]
```

---

## Reactions Class

### Constructor

```python
Reactions(biochem_root='../../../Biochemistry/', rxns_file='reaction_00.tsv')
```

**Attributes:**
- `BiochemRoot` - Path to Biochemistry directory
- `RxnsFile` - Path to first reaction TSV file
- `AliasFile` - Path to reaction aliases file
- `NameFile` - Path to reaction names file
- `PwyFile` - Path to pathways file
- `ECFile` - Path to EC numbers file
- `Headers` - List of TSV column headers
- `CompoundsHelper` - Compounds instance for compound lookups
- `Compounds_Dict` - Loaded compounds dictionary

### Loading Methods

#### loadReactions()
Load all reactions from JSON files.

```python
rxns_helper = Reactions()
rxns_dict = rxns_helper.loadReactions()

# Returns: dict keyed by reaction ID
# rxns_dict["rxn00001"] = {
#     "id": "rxn00001",
#     "name": "diphosphate phosphohydrolase",
#     "equation": "(1) cpd00001[0] + (1) cpd00012[0] <=> ...",
#     "status": "OK",
#     ...
# }
```

#### loadMSAliases(sources_array=[])
Load reaction aliases.

```python
aliases = rxns_helper.loadMSAliases()
aliases = rxns_helper.loadMSAliases(["KEGG", "MetaCyc"])
```

#### loadNames()
Load reaction names.

```python
names = rxns_helper.loadNames()
```

#### loadPathways()
Load pathway associations.

```python
pathways = rxns_helper.loadPathways()
# Returns: dict[rxn_id][source] = [pathway_list]
```

#### loadECs()
Load EC number associations.

```python
ecs = rxns_helper.loadECs()
# Returns: dict[rxn_id] = [ec_list]
# ecs["rxn00001"] = ["3.6.1.1"]
```

### Parsing Methods

#### parseEquation(equation_string)
Parse reaction equation into reagent array.

```python
equation = "(1) cpd00001[0] + (1) cpd00012[0] <=> (2) cpd00009[0] + (1) cpd00067[0]"
reagents = rxns_helper.parseEquation(equation)

# Returns: list of dicts
# [
#     {"compound": "cpd00001", "compartment": 0, "coefficient": -1,
#      "name": "H2O", "formula": "H2O", "charge": 0},
#     {"compound": "cpd00012", "compartment": 0, "coefficient": -1, ...},
#     {"compound": "cpd00009", "compartment": 0, "coefficient": 2, ...},
#     {"compound": "cpd00067", "compartment": 0, "coefficient": 1, ...}
# ]
```

#### parseStoich(stoichiometry)
Parse stoichiometry string into reagent array.

```python
stoich = "-1:cpd00001:0:0:\"H2O\";-1:cpd00012:0:0:\"PPi\";2:cpd00009:0:0:\"Phosphate\""
reagents = rxns_helper.parseStoich(stoich)
```

### Reaction Manipulation Methods

#### balanceReaction(rgts_array, all_structures=False)
Check mass and charge balance of a reaction.

```python
rgts = rxns_helper.parseEquation(equation)
status = rxns_helper.balanceReaction(rgts)

# Returns status string:
# "OK" - balanced
# "MI:C:-1/H:-4" - mass imbalance
# "CI:2" - charge imbalance
# "EMPTY" - reactants cancel out
# "CPDFORMERROR" - invalid compound formula
# "Duplicate reagents" - same compound appears twice
```

#### adjustCompound(rxn_cpds_array, compound, adjustment, compartment=0)
Adjust coefficient of a compound in reaction.

```python
# Add 2 protons to right side (positive adjustment = subtract from left)
rxns_helper.adjustCompound(rgts, "cpd00067", 2, compartment=0)
```

#### replaceCompound(rxn_cpds_array, old_compound, new_compound)
Replace one compound with another.

```python
success = rxns_helper.replaceCompound(rgts, "cpd00001", "cpd00002")
# Returns: True if found and replaced, False otherwise
```

#### rebuildReaction(reaction_dict, stoichiometry=None)
Rebuild equation/code/definition from stoichiometry.

```python
rxn = rxns_dict["rxn00001"]
# After modifying stoichiometry...
rxns_helper.rebuildReaction(rxn)
# Updates: code, equation, definition, compound_ids fields
```

### Code Generation Methods

#### generateCode(rxn_cpds_array)
Generate unique reaction code for matching.

```python
rgts = rxns_helper.parseEquation(equation)
code = rxns_helper.generateCode(rgts)
# Returns: string like "cpd00001_0:1|cpd00012_0:1|=|cpd00009_0:2|cpd00067_0:1"
```

#### generateCodes(rxns_dict, check_obsolete=True)
Generate codes for all reactions.

```python
codes = rxns_helper.generateCodes(rxns_dict)
# Returns: dict[code] = {rxn_id: 1, ...}
```

### Static Utility Methods

#### Reactions.isTransport(rxn_cpds_array)
Check if reaction is a transport reaction.

```python
is_transport = Reactions.isTransport(rgts)
# Returns: 1 if multiple compartments, 0 otherwise
```

#### Reactions.buildStoich(rxn_cpds_array)
Build stoichiometry string from reagent array.

```python
stoich_string = Reactions.buildStoich(rgts)
# Returns: "-1:cpd00001:0:0:\"H2O\";-1:cpd00012:0:0:\"PPi\";..."
```

#### Reactions.removeCpdRedundancy(rgts_array)
Remove duplicate compounds by summing coefficients.

```python
cleaned_rgts = Reactions.removeCpdRedundancy(rgts)
```

### Saving Methods

#### saveReactions(reactions_dict)
Save reactions to partitioned TSV and JSON files.

```python
rxns_helper.saveReactions(rxns_dict)
```

#### saveAliases(alias_dict)
Save reaction aliases.

```python
rxns_helper.saveAliases(aliases)
```

#### saveNames(names_dict)
Save reaction names.

```python
rxns_helper.saveNames(names)
```

#### saveECs(ecs_dict)
Save EC number associations.

```python
rxns_helper.saveECs(ecs)
```

---

## Common Patterns

### Search for a compound by KEGG ID

```python
cpds = Compounds()
source_aliases = cpds.loadSourceAliases()

kegg_id = "C00031"  # D-Glucose
if "KEGG" in source_aliases and kegg_id in source_aliases["KEGG"]:
    ms_ids = source_aliases["KEGG"][kegg_id]
    print(f"ModelSEED IDs: {ms_ids}")
```

### Validate all reactions

```python
rxns = Reactions()
rxns_dict = rxns.loadReactions()

for rxn_id, rxn in rxns_dict.items():
    rgts = rxns.parseStoich(rxn["stoichiometry"])
    status = rxns.balanceReaction(rgts)
    if status != "OK":
        print(f"{rxn_id}: {status}")
```

### Find reactions containing a compound

```python
rxns = Reactions()
rxns_dict = rxns.loadReactions()

target_cpd = "cpd00027"  # D-Glucose
for rxn_id, rxn in rxns_dict.items():
    if target_cpd in rxn["compound_ids"]:
        print(f"{rxn_id}: {rxn['name']}")
```

### Modify and save a compound

```python
cpds = Compounds()
cpds_dict = cpds.loadCompounds()

# Modify
cpds_dict["cpd00001"]["deltag"] = -37.5

# Save all
cpds.saveCompounds(cpds_dict)
```
