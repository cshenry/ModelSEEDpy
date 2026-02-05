# ModelSEED Database Maintenance Workflows

## Environment Setup

```bash
# 1. Activate conda environment
conda activate msd-env

# 2. Set PYTHONPATH
export PYTHONPATH=$PYTHONPATH:/path/to/ModelSEEDDatabase/Libs/Python/

# 3. Change to Scripts/Biochemistry directory
cd /path/to/ModelSEEDDatabase/Scripts/Biochemistry/
```

## Validation Workflow

### Reprint_Biochemistry.py

The primary validation script. If no changes occur after running, the database is valid.

```bash
./Reprint_Biochemistry.py
git status -s
# If no changes, validation passed
```

**What it does:**
1. Loads all compounds from JSON
2. Saves compounds (regenerates TSV and JSON)
3. Loads and saves compound aliases and names
4. Loads all reactions from JSON
5. Rebuilds each reaction (recalculates equation, code, definition, compound_ids)
6. Saves reactions (regenerates TSV and JSON)
7. Loads and saves reaction aliases, names, and EC numbers

**Use after:** Any data modification to validate consistency.

---

## Adding New Compounds

### Input File Format

Create a TSV file with columns:
```
id	names	formula	charge	mass	inchi	inchikey	smiles
```

- **id**: External database ID (e.g., KEGG C00031)
- **names**: Pipe-separated names (e.g., "D-Glucose|Glucose|Dextrose")
- **formula**: Chemical formula (Hill system)
- **charge**: Integer charge
- **mass**: Molecular weight
- **inchi/inchikey/smiles**: Molecular structures (optional but recommended)

### Add_New_Compounds.py

```bash
./Update_DB/Add_New_Compounds.py compounds.tsv DATABASE [-s] [-r]

# Arguments:
#   compounds.tsv - Input file with new compounds
#   DATABASE      - Source database name (e.g., "KEGG", "MetaCyc", "User")
#   -s            - Save changes (without this, dry run only)
#   -r            - Generate report file
```

**Matching logic:**
1. Check if external ID already exists as alias → match
2. Check if structure (InChI > InChIKey > SMILES) matches → match
3. Check if name matches (only if no structure match for compounds with structures) → match
4. No match → create new compound with next available cpdNNNNN ID

**Example:**
```bash
# Dry run to see what would be matched/added
./Update_DB/Add_New_Compounds.py new_compounds.tsv KEGG -r

# Actually save changes
./Update_DB/Add_New_Compounds.py new_compounds.tsv KEGG -s
```

### Post-Addition Scripts

After adding compounds:
```bash
# Merge any duplicate formulas
./Update_DB/Merge_Formulas.py

# Update aliases in database
./Refresh_DB_after_Changes/Update_Compound_Aliases_in_DB.py

# If structures provided, update structure files
../Structures/List_ModelSEED_Structures.py
../Structures/Update_Compound_Structures_Formulas_Charge.py

# Rebalance any reactions affected
./Refresh_DB_after_Changes/Rebalance_Reactions.py

# Final validation
./Reprint_Biochemistry.py
```

---

## Adding New Reactions

### Input File Format

Create a TSV file with columns:
```
id	equation	names	ecs
```

- **id**: External database ID
- **equation**: Reaction equation using compound IDs
  - Format: `(coeff) cpdid[compartment] + ... <=> (coeff) cpdid[compartment] + ...`
  - Example: `(1) C00001[0] + (1) C00002[0] <=> (1) C00003[0]`
- **names**: Pipe-separated reaction names
- **ecs**: Pipe-separated EC numbers

### Add_New_Reactions.py

```bash
./Update_DB/Add_New_Reactions.py reactions.tsv CPD_DATABASE RXN_DATABASE [-s] [-r]

# Arguments:
#   reactions.tsv  - Input file with new reactions
#   CPD_DATABASE   - Source for compound IDs (e.g., "KEGG", "ModelSEED")
#   RXN_DATABASE   - Source database name for reactions
#   -s             - Save changes
#   -r             - Generate report file
```

**Matching logic:**
1. Translate compound IDs to ModelSEED IDs
2. Generate reaction code (unique identifier based on stoichiometry)
3. Check if code matches existing reaction → match
4. Check if code matches after water adjustment → match
5. No match → create new reaction with next available rxnNNNNN ID

### Post-Addition Scripts

After adding reactions:
```bash
# Rebalance to check mass/charge balance
./Refresh_DB_after_Changes/Rebalance_Reactions.py

# Adjust protons for balance
./Refresh_DB_after_Changes/Adjust_Reaction_Protons.py

# Adjust water for balance
./Refresh_DB_after_Changes/Adjust_Reaction_Water.py

# Merge any duplicate reactions (may occur after adjustments)
./Refresh_DB_after_Changes/Merge_Reactions.py

# Update aliases
./Refresh_DB_after_Changes/Update_Reaction_Aliases_in_DB.py

# Final validation
./Reprint_Biochemistry.py
```

---

## Maintenance Scripts

### Scripts/Biochemistry/Maintain/

| Script | Purpose |
|--------|---------|
| `Check_Charges.py` | Verify compound charges |
| `Check_Formulas.py` | Verify formula validity |
| `Check_Links.py` | Verify linked_compound/linked_reaction references |
| `Check_Transport.py` | Verify is_transport flags |
| `Check_Template_Reactions.py` | Check reactions against templates |
| `Fix_Compound_Obsolescence.py` | Handle obsolete compound transitions |
| `Fix_Values.py` | Fix common data issues |
| `Manual_Update_Links.py` | Manually update links between entities |
| `Remove_Duplicate_Aliases.py` | Clean up duplicate alias entries |
| `Update_Obsolete_Compounds_in_Reactions.py` | Update reactions using obsolete compounds |

### Scripts/Biochemistry/Refresh_DB_after_Changes/

| Script | Purpose |
|--------|---------|
| `Rebalance_Reactions.py` | Recalculate mass/charge balance status |
| `Rebuild_Reactions.py` | Regenerate equation/code/definition fields |
| `Rebuild_Stoichiometry.py` | Regenerate stoichiometry field |
| `Adjust_Reaction_Protons.py` | Add/remove H+ to balance charges |
| `Adjust_Reaction_Water.py` | Add/remove H2O to balance mass |
| `Merge_Reactions.py` | Merge duplicate reactions |
| `Merge_Obsolete_Aliases.py` | Consolidate aliases for merged entities |
| `Remove_Newly_Obsolescent_Compounds.py` | Remove newly obsolete compounds |
| `Remove_Newly_Obsolescent_Reactions.py` | Remove newly obsolete reactions |
| `Update_Compound_Aliases_in_DB.py` | Sync aliases into compound records |
| `Update_Reaction_Aliases_in_DB.py` | Sync aliases into reaction records |
| `Update_Source_Column.py` | Update source field values |

---

## Common Editing Patterns

### Modify a Single Compound

```python
import sys
sys.path.append('/path/to/ModelSEEDDatabase/Libs/Python')
from BiochemPy import Compounds

cpds = Compounds()
cpds_dict = cpds.loadCompounds()

# Modify
cpds_dict["cpd00001"]["deltag"] = -37.5
cpds_dict["cpd00001"]["deltagerr"] = 0.5

# Save
cpds.saveCompounds(cpds_dict)
```

Then validate:
```bash
./Reprint_Biochemistry.py
git diff
```

### Modify a Single Reaction

```python
from BiochemPy import Reactions

rxns = Reactions()
rxns_dict = rxns.loadReactions()

# Modify
rxns_dict["rxn00001"]["reversibility"] = ">"
rxns_dict["rxn00001"]["direction"] = ">"

# Rebuild equation strings
rxns.rebuildReaction(rxns_dict["rxn00001"])

# Save
rxns.saveReactions(rxns_dict)
```

### Fix a Mass Imbalance

```python
from BiochemPy import Reactions

rxns = Reactions()
rxns_dict = rxns.loadReactions()

rxn = rxns_dict["rxn12345"]
rgts = rxn["stoichiometry"]

# Check current balance
status = rxns.balanceReaction(rgts)
print(f"Current status: {status}")  # e.g., "MI:H:-2/O:-1"

# Add water to balance (positive adjustment adds to right side)
rxns.adjustCompound(rgts, "cpd00001", -1)  # Add 1 H2O to left side

# Recheck
new_status = rxns.balanceReaction(rgts)
print(f"New status: {new_status}")

# Rebuild and save
rxns.rebuildReaction(rxn, rgts)
rxns.saveReactions(rxns_dict)
```

### Add an Alias to a Compound

```python
from BiochemPy import Compounds

cpds = Compounds()
aliases = cpds.loadMSAliases()

# Add new alias
cpd_id = "cpd00027"
source = "ChEBI"
new_alias = "CHEBI:4167"

if cpd_id not in aliases:
    aliases[cpd_id] = {}
if source not in aliases[cpd_id]:
    aliases[cpd_id][source] = []
aliases[cpd_id][source].append(new_alias)

# Save
cpds.saveAliases(aliases)

# Then sync to database
# Run: ./Refresh_DB_after_Changes/Update_Compound_Aliases_in_DB.py
```

### Search for Compounds by Name

```python
from BiochemPy import Compounds

cpds = Compounds()
cpds_dict = cpds.loadCompounds()
names = cpds.loadNames()

search_term = "glucose"
matches = []

for cpd_id, name_list in names.items():
    for name in name_list:
        if search_term.lower() in name.lower():
            matches.append((cpd_id, name, cpds_dict.get(cpd_id, {}).get("formula", "")))

for cpd_id, name, formula in matches:
    print(f"{cpd_id}: {name} ({formula})")
```

### Find Imbalanced Reactions

```python
from BiochemPy import Reactions

rxns = Reactions()
rxns_dict = rxns.loadReactions()

imbalanced = []
for rxn_id, rxn in rxns_dict.items():
    if rxn["status"] != "OK" and "CPDFORMERROR" not in rxn["status"]:
        imbalanced.append((rxn_id, rxn["name"], rxn["status"]))

print(f"Found {len(imbalanced)} imbalanced reactions:")
for rxn_id, name, status in imbalanced[:20]:  # Show first 20
    print(f"  {rxn_id}: {name} - {status}")
```

---

## Git Workflow

### Before Making Changes
```bash
git status
git checkout -b feature/my-changes
```

### After Making Changes
```bash
# Validate
./Reprint_Biochemistry.py
git status -s

# Review changes
git diff Biochemistry/

# Commit
git add Biochemistry/
git commit -m "Description of changes"
```

### Reverting Changes
```bash
# Revert all biochemistry changes
./Reset_Biochemistry_in_Git.sh

# Or manually
git checkout -- Biochemistry/
```

---

## Troubleshooting

### "CPDFORMERROR" Status
- Compound has no formula or invalid formula
- Check compound record for formula field
- May need to add formula from external source

### "MI" (Mass Imbalance)
- Atoms don't balance between left and right sides
- Run `Rebalance_Reactions.py` to identify issues
- May need `Adjust_Reaction_Water.py` or manual compound adjustment

### "CI" (Charge Imbalance)
- Charges don't balance
- Often fixed by `Adjust_Reaction_Protons.py`
- May indicate incorrect compound charges

### Duplicate Compounds
- Run `Remove_Duplicate_Aliases.py`
- Consider merging via obsolescence workflow

### Missing Compound in Reaction
- Ensure compound exists in database
- Check compound alias mapping
- May need to add compound first
