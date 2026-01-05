# Common MSModelUtil Patterns

## Pattern 1: Safe Instance Access

```python
from modelseedpy.core.msmodelutl import MSModelUtil

# Always use get() for consistent instance access
mdlutl = MSModelUtil.get(model)  # Works with model or mdlutl

# Multiple calls return same instance
mdlutl1 = MSModelUtil.get(model)
mdlutl2 = MSModelUtil.get(model)
assert mdlutl1 is mdlutl2  # True

# Functions should accept either model or mdlutl
def my_function(model_or_mdlutl):
    mdlutl = MSModelUtil.get(model_or_mdlutl)
    model = mdlutl.model
    # ... rest of function
```

## Pattern 2: Load and Analyze a Model

```python
from modelseedpy.core.msmodelutl import MSModelUtil
from modelseedpy.core.msmedia import MSMedia

# Load model
mdlutl = MSModelUtil.from_cobrapy("my_model.json")

# Set media
media = MSMedia.from_dict({"EX_cpd00027_e0": 10})  # Glucose
mdlutl.set_media(media)

# Run FBA
solution = mdlutl.model.optimize()
print(f"Growth: {solution.objective_value}")
```

## Pattern 3: Find and Operate on Metabolites

```python
# Always handle empty results
mets = mdlutl.find_met("glucose", "c0")
if mets:
    glucose = mets[0]
    # Do something with glucose
else:
    print("Glucose not found in model")

# Find by ModelSEED ID
mets = mdlutl.find_met("cpd00001")  # Water
mets = mdlutl.find_met("cpd00001", "c0")  # Cytosolic water

# Get all ModelSEED IDs
id_hash = mdlutl.msid_hash()
# id_hash["cpd00001"] = [<Metabolite cpd00001_c0>, <Metabolite cpd00001_e0>]
```

## Pattern 4: Add Exchanges for Media

```python
from modelseedpy.core.msmedia import MSMedia

# Before setting media, ensure exchanges exist
missing = mdlutl.add_missing_exchanges(media)
if missing:
    print(f"Added exchanges for: {missing}")

# Now set the media
mdlutl.set_media(media)

# Alternative: add specific exchanges
mets_e0 = mdlutl.find_met("glucose", "e0")
if mets_e0:
    mdlutl.add_exchanges_for_metabolites(mets_e0, uptake=10, excretion=0)
```

## Pattern 5: Test Growth Conditions

```python
# Define condition
condition = {
    "media": media,
    "objective": "bio1",
    "is_max_threshold": True,  # True = FAIL if value >= threshold
    "threshold": 0.1
}

# Apply and test (two-step)
mdlutl.apply_test_condition(condition)
passed = mdlutl.test_single_condition(condition, apply_condition=False)

# Or test directly (one-step)
passed = mdlutl.test_single_condition(condition, apply_condition=True)

# Test multiple conditions
all_passed = mdlutl.test_condition_list([cond1, cond2, cond3])
```

## Pattern 6: Gapfill and Validate

```python
from modelseedpy.core.msgapfill import MSGapfill

# Create gapfiller
gapfill = MSGapfill(mdlutl, default_target="bio1")

# Run gapfilling
solution = gapfill.run_gapfilling(media, target="bio1")

# Test which reactions are actually needed
unneeded = mdlutl.test_solution(
    solution,
    targets=["bio1"],
    medias=[media],
    thresholds=[0.1],
    remove_unneeded_reactions=True  # Actually remove them
)

# Record the gapfilling
mdlutl.add_gapfilling(solution)
```

## Pattern 7: ATP Correction

```python
from modelseedpy.core.mstemplate import MSTemplateBuilder

# Get core template
template = MSTemplateBuilder.build_core_template()

# Get ATP tests
tests = mdlutl.get_atp_tests(core_template=template)

# Run tests
for test in tests:
    passed = mdlutl.test_single_condition(test)
    print(f"{test['media'].id}: {'PASS' if passed else 'FAIL'}")
```

## Pattern 8: Find and Add Reactions

```python
# Find a metabolite
glucose_list = mdlutl.find_met("glucose", "c0")
if glucose_list:
    glucose = glucose_list[0]

    # Add exchange if missing
    if glucose not in mdlutl.exchange_hash():
        mdlutl.add_exchanges_for_metabolites([glucose], uptake=10, excretion=0)

# Add a transport reaction
mdlutl.add_transport_and_exchange_for_metabolite(glucose, direction=">")

# Add ModelSEED reactions
reactions = mdlutl.add_ms_reaction({
    "rxn00001": "c0",
    "rxn00002": "c0"
})
```

## Pattern 9: Debug FBA Issues

```python
import logging

# Enable debug logging
logging.getLogger("modelseedpy.core.msmodelutl").setLevel(logging.DEBUG)

# Print LP file for solver issues
mdlutl.printlp(print=True, filename="debug_problem")
# Creates debug_problem.lp in current directory

# Check metabolite hash is built
if mdlutl.metabolite_hash is None:
    mdlutl.build_metabolite_hash()

# Verify MSModelUtil caching
print(f"Cached models: {len(MSModelUtil.mdlutls)}")

# Find unproducible biomass compounds
unproducible = mdlutl.find_unproducible_biomass_compounds("bio1")
for met in unproducible:
    print(f"Cannot produce: {met.id}")
```

## Pattern 10: Compare Multiple Solutions

```python
# Run FBA under different conditions
solutions = {}

# Glucose media
mdlutl.set_media(glucose_media)
solutions["glucose"] = mdlutl.model.optimize()

# Acetate media
mdlutl.set_media(acetate_media)
solutions["acetate"] = mdlutl.model.optimize()

# Export comparison
mdlutl.print_solutions(solutions, "flux_comparison.csv")
```

## Common Mistakes

1. **Not using get()**: Creating multiple MSModelUtil instances for same model
   ```python
   # WRONG
   mdlutl1 = MSModelUtil(model)
   mdlutl2 = MSModelUtil(model)  # Different instances!

   # RIGHT
   mdlutl1 = MSModelUtil.get(model)
   mdlutl2 = MSModelUtil.get(model)  # Same instance
   ```

2. **Ignoring empty find_met results**: Always check if list is empty
   ```python
   # WRONG
   glucose = mdlutl.find_met("glucose")[0]  # IndexError if not found!

   # RIGHT
   mets = mdlutl.find_met("glucose")
   if mets:
       glucose = mets[0]
   ```

3. **Wrong threshold interpretation**: is_max_threshold=True means FAIL if value >= threshold
   ```python
   # is_max_threshold=True means:
   # - Test PASSES if objective < threshold
   # - Test FAILS if objective >= threshold
   # This is for testing "no ATP production" conditions
   ```

4. **Not adding exchanges before setting media**:
   ```python
   # WRONG
   mdlutl.set_media(media)  # May fail if exchanges missing

   # RIGHT
   mdlutl.add_missing_exchanges(media)
   mdlutl.set_media(media)
   ```

5. **Modifying model instead of mdlutl.model**:
   ```python
   # WRONG (if model was reassigned)
   model.reactions.get_by_id("bio1").bounds = (0, 1000)

   # RIGHT (always use mdlutl.model)
   mdlutl.model.reactions.get_by_id("bio1").bounds = (0, 1000)
   ```
