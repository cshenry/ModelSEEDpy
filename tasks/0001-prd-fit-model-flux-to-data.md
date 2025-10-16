# Product Requirements Document: fit_model_flux_to_data Function

## 1. Introduction/Overview

This PRD outlines the implementation of a new function `fit_model_flux_to_data` in the `MSExpression` class. This function integrates gene/reaction expression data with constraint-based metabolic modeling to optimize model flux predictions based on experimental expression data.

**Problem Statement:**
Currently, users must manually convert expression data to appropriate formats and create activation/deactivation dictionaries to integrate expression data into flux balance analysis (FBA). This process is error-prone and requires deep knowledge of the internal workings of ModelSEEDpy's expression and FBA packages.

**Solution:**
The `fit_model_flux_to_data` function will provide a streamlined, user-friendly interface that automatically:
- Converts gene-level expression to reaction-level expression using GPR (Gene-Protein-Reaction) rules
- Transforms expression data into the appropriate format (RelativeAbundance)
- Builds activation/deactivation dictionaries based on configurable thresholds
- Integrates with ExpressionActivationPkg to constrain model fluxes
- Returns an optimized FBA solution reflecting expression constraints

**Target Users:**
Metabolic modelers and computational biologists working with multi-omics data integration for metabolic network analysis.

---

## 2. Goals

1. **Simplify expression-constrained FBA**: Provide a single function call to integrate expression data with metabolic models
2. **Ensure data compatibility**: Automatically handle data type conversions and model/genome-level expression
3. **Enable threshold-based flux constraints**: Allow users to define activation and deactivation thresholds for reaction expression
4. **Return actionable results**: Provide FBA solutions that reflect expression-constrained flux predictions
5. **Maintain data integrity**: Preserve original expression data during transformations
6. **Provide comprehensive validation**: Detect and report errors related to model mismatches, missing conditions, or invalid thresholds

---

## 3. User Stories

### Story 1: Gene Expression to Flux Prediction
**As a** metabolic modeler
**I want to** fit a metabolic model to gene expression data from a specific experimental condition
**So that** I can predict metabolic fluxes that are consistent with observed gene expression patterns

**Acceptance Criteria:**
- Function accepts MSModelUtil object and condition ID
- Gene expression is automatically converted to reaction expression via GPR rules
- FBA solution is returned with expression-constrained fluxes

### Story 2: Multi-Condition Expression Analysis
**As a** systems biologist
**I want to** compare metabolic flux predictions across multiple experimental conditions
**So that** I can identify condition-specific metabolic pathway utilization

**Acceptance Criteria:**
- Function can be called iteratively for different conditions
- Each condition produces independent FBA solutions
- Original expression data remains unchanged between calls

### Story 3: Custom Threshold Configuration
**As a** computational biologist
**I want to** define custom activation and deactivation thresholds
**So that** I can fine-tune the sensitivity of expression-based flux constraints based on my experimental system

**Acceptance Criteria:**
- Function accepts optional activation_threshold and deactivation_threshold parameters
- Default thresholds are used when not specified
- Invalid thresholds (activation <= deactivation) trigger validation errors

### Story 4: Expression Data Type Flexibility
**As a** data analyst
**I want to** use various expression data types (FPKM, TPM, Log2, etc.)
**So that** I can work with data in its native format without manual preprocessing

**Acceptance Criteria:**
- Function automatically detects current expression data type
- Transformation to RelativeAbundance occurs transparently
- Original data is preserved (not modified in place)

---

## 4. Functional Requirements

### FR1: Function Signature
The function must be implemented as a method of the `MSExpression` class with the following signature:

```python
def fit_model_flux_to_data(
    self,
    model: MSModelUtil,
    condition: str,
    activation_threshold: float = 0.002,
    deactivation_threshold: float = 0.000001
) -> cobra.Solution
```

**Parameters:**
- `model` (MSModelUtil, required): The metabolic model to fit to expression data
- `condition` (str, required): The condition ID whose expression values will be used
- `activation_threshold` (float, optional): Minimum expression value for reaction activation (default: 0.002)
- `deactivation_threshold` (float, optional): Maximum expression value for reaction deactivation (default: 0.000001)

**Return Value:**
- `cobra.Solution`: The optimized FBA solution with expression-based flux constraints

**File Location:** `/home/chenry/projects/ClaudeProjects/ModelSEEDpy/ModelSEEDpy/modelseedpy/multiomics/msexpression.py`

---

### FR2: Genome vs. Model Expression Handling
**Requirement:** The function must detect whether the MSExpression object contains gene-level or reaction-level expression data.

**Implementation Logic:**
1. Check if `self.object` is an instance of `MSGenome`:
   - If True: Call `self.build_reaction_expression(model.model)` to convert gene-level to reaction-level expression
   - Store the resulting reaction expression object in a local variable for subsequent processing
2. If `self.object` is a model object:
   - Compare `self.object` with `model.model` for equality (same reactions)
   - If models do not match: Raise `ValueError` with message: "Models must match when fitting flux to data"
3. Use the reaction-level expression object for all downstream processing

**Reference:** `MSExpression.build_reaction_expression()` (msexpression.py:454-504)

---

### FR3: Model Comparison Validation
**Requirement:** When the MSExpression object already contains reaction-level expression, validate that it matches the input model.

**Comparison Criteria:**
- Compare reaction IDs: `set(self.object.reactions.list_attr('id')) == set(model.model.reactions.list_attr('id'))`

**Error Message:**
```
ValueError: Models must match when fitting flux to data.
Expression model has {len(expr_rxns)} reactions, input model has {len(model_rxns)} reactions.
Missing in expression: {missing_in_expr}
Missing in model: {missing_in_model}
```

Where:
- `missing_in_expr`: Reactions in input model but not in expression model (show first 10)
- `missing_in_model`: Reactions in expression model but not in input model (show first 10)

---

### FR4: Condition Validation
**Requirement:** Verify that the specified condition exists in the expression data.

**Implementation:**
1. Check if `condition` exists in `self.conditions`:
   ```python
   if condition not in self.conditions:
       raise ValueError(f"Condition '{condition}' not found in expression data. Available conditions: {[c.id for c in self.conditions]}")
   ```

---

### FR5: Expression Data Type Transformation
**Requirement:** Transform expression data to RelativeAbundance type if not already in that format.

**Transformation Rules:**

| Source Type | Transformation Formula | Reference |
|-------------|------------------------|-----------|
| RelativeAbundance | No transformation needed | - |
| AbsoluteAbundance | `value / column_sum` | msexpression.py:210 |
| FPKM | `value / column_sum` | msexpression.py:212 |
| TPM | `value / column_sum` | msexpression.py:214 |
| Log2 | `2^(value - min_value) / 2^(column_sum - n*min_value)` | msexpression.py:216-217 |

**Implementation Details:**
1. Create a new MSExpression object with type "RelativeAbundance" (preserve original)
2. Copy features and conditions from the current object
3. For each feature and condition, apply the transformation formula
4. Use the condition-level statistics:
   - `condition.column_sum`: Sum of all expression values in the condition
   - `condition.lowest_value()`: Minimum expression value in the condition
   - `condition.feature_count`: Number of features in the condition

**Data Preservation:**
- The original `self._data` DataFrame must NOT be modified
- Create a new DataFrame for transformed data
- Use pandas `.copy()` to ensure deep copying

**Validation:**
- Log a warning if converting from Log2 scale data (scientific appropriateness check)
- Verify that transformed values are non-negative and finite

---

### FR6: Threshold Validation
**Requirement:** Validate that activation_threshold is greater than deactivation_threshold.

**Implementation:**
```python
if activation_threshold <= deactivation_threshold:
    raise ValueError(
        f"activation_threshold ({activation_threshold}) must be greater than "
        f"deactivation_threshold ({deactivation_threshold})"
    )
```

---

### FR7: Activation Dictionary Construction
**Requirement:** Build a dictionary of reactions to activate based on expression values exceeding the activation threshold.

**Dictionary Structure:**
```python
on_hash = {
    "rxn00001_c0": 0.003,  # activation value = expression - activation_threshold
    "rxn00002_c0": 0.001,
    # ... more reactions
}
```

**Construction Logic:**
1. Initialize empty dictionary: `on_hash = {}`
2. Iterate through all reactions in the model: `for rxn in model.model.reactions:`
3. Get expression value for the reaction in the specified condition:
   ```python
   expr_value = rxn_expression.get_value(rxn.id, condition)
   ```
4. If `expr_value is not None and expr_value > activation_threshold`:
   ```python
   on_hash[rxn.id] = expr_value - activation_threshold
   ```
5. Skip reactions with missing expression data (no entry in on_hash or off_hash)

**Edge Case Handling:**
- If NO reactions exceed the activation threshold:
  ```python
  raise ValueError(
      f"No reactions have expression values above activation threshold ({activation_threshold}). "
      f"Consider lowering the threshold or checking your expression data."
  )
  ```

---

### FR8: Deactivation Dictionary Construction
**Requirement:** Build a dictionary of reactions to deactivate based on expression values below the deactivation threshold.

**Dictionary Structure:**
```python
off_hash = {
    "rxn00100_c0": 0.000001,  # deactivation penalty = deactivation_threshold - expression
    "rxn00101_c0": 0.000000999,
    # ... more reactions
}
```

**Construction Logic:**
1. Initialize empty dictionary: `off_hash = {}`
2. Iterate through all reactions in the model: `for rxn in model.model.reactions:`
3. Get expression value for the reaction in the specified condition
4. If `expr_value is not None and expr_value < deactivation_threshold`:
   ```python
   off_hash[rxn.id] = deactivation_threshold - expr_value
   ```
5. Skip reactions with missing expression data

**Edge Case Note:**
- Unlike on_hash, an empty off_hash is acceptable (all reactions are expressed)

---

### FR9: Integration with ExpressionActivationPkg
**Requirement:** Use the activation and deactivation dictionaries to build an expression-constrained optimization problem.

**Implementation:**
1. Access the package manager from the model:
   ```python
   pkgmgr = model.pkgmgr
   ```
2. Get the ExpressionActivationPkg:
   ```python
   expr_pkg = pkgmgr.getpkg("ExpressionActivationPkg")
   ```
3. Build the package with the dictionaries:
   ```python
   expr_pkg.build_package(on_hash, off_hash)
   ```

**Reference:** ExpressionActivationPkg.build_package() (expressionactivationpkg.py:30-68)

**Package Behavior:**
- Creates reaction activation variables (fra, rra) via ReactionActivationPkg
- Sets objective to minimize flux through deactivated reactions
- Sets objective to maximize flux through activated reactions
- Uses hash values as objective coefficients

---

### FR10: Model Optimization and Solution Return
**Requirement:** Execute constrained FBA optimization and return the solution.

**Implementation Pattern (following MSGrowthPhenotypes.simulate):**

```python
# Use context manager to prevent permanent model modification
with model.model:
    # ExpressionActivationPkg has already been built (FR9)

    # Run optimization
    solution = model.model.optimize()

    # Validate solution
    if solution.status != "optimal":
        raise RuntimeError(
            f"Optimization failed with status: {solution.status}. "
            f"The model may be infeasible with the given expression constraints."
        )

    # Return the solution
    return solution
```

**Reference:** MSGrowthPhenotypes.simulate() (msgrowthphenotypes.py:229, 257)

**Solution Object Contents:**
- `solution.objective_value`: The optimized objective value
- `solution.fluxes`: pandas Series of reaction fluxes
- `solution.status`: Optimization status ('optimal', 'infeasible', etc.)

---

### FR11: Logging and Diagnostics
**Requirement:** Provide informative logging throughout the function execution.

**Logging Points:**
1. Function entry:
   ```python
   logger.info(f"Fitting model flux to expression data for condition: {condition}")
   ```

2. Data transformation:
   ```python
   logger.info(f"Transforming expression data from {self.type} to RelativeAbundance")
   if self.type == "Log2":
       logger.warning("Converting from Log2 scale - ensure this is scientifically appropriate for your analysis")
   ```

3. Dictionary construction:
   ```python
   logger.info(f"Identified {len(on_hash)} reactions for activation (above threshold {activation_threshold})")
   logger.info(f"Identified {len(off_hash)} reactions for deactivation (below threshold {deactivation_threshold})")
   ```

4. Optimization result:
   ```python
   logger.info(f"Optimization completed with objective value: {solution.objective_value}")
   ```

**Logger Import:**
```python
import logging
logger = logging.getLogger(__name__)
```

---

## 5. Non-Goals (Out of Scope)

The following features are explicitly **NOT** included in this implementation:

1. **Multi-condition optimization**: This function handles a single condition per call. Users must call the function multiple times for multi-condition analysis.

2. **Automatic threshold determination**: The function does not automatically calculate optimal thresholds from the data distribution. Users must provide thresholds or use defaults.

3. **Gapfilling integration**: Unlike `MSGrowthPhenotypes.simulate()`, this function does not perform automated gapfilling if the model is infeasible.

4. **Flux variability analysis (FVA)**: The function returns a single optimal solution, not a range of possible flux values.

5. **Model modification**: The function does not permanently modify the input model or expression data. All changes occur within a context manager.

6. **Expression data normalization**: Beyond type conversion to RelativeAbundance, the function does not perform additional normalization (e.g., quantile normalization, batch correction).

7. **Statistical significance testing**: The function does not assess whether expression differences are statistically significant before applying thresholds.

8. **Isoform handling**: The function does not handle alternative splicing or isoform-specific expression data.

9. **Time-series analysis**: The function does not model temporal dynamics or time-dependent expression changes.

10. **Visualization**: The function does not generate plots or visualizations of results.

---

## 6. Design Considerations

### 6.1 API Design Philosophy
- **Consistency**: Follow the naming conventions and parameter patterns of existing MSExpression methods
- **Simplicity**: Minimize required parameters (only model and condition are required)
- **Sensible defaults**: Use scientifically validated default thresholds based on literature
- **Context preservation**: Use cobrapy's context manager to ensure model state is not permanently altered

### 6.2 Data Flow Diagram

```
User Input:
  - MSExpression object (self)
  - MSModelUtil model
  - condition ID
  - optional thresholds
        |
        v
[1. Validate Inputs]
  - Check condition exists
  - Validate thresholds
        |
        v
[2. Prepare Expression Data]
  - Convert genome->model if needed
  - Transform to RelativeAbundance
        |
        v
[3. Build Activation Dictionaries]
  - on_hash: high expression reactions
  - off_hash: low expression reactions
        |
        v
[4. Apply Expression Constraints]
  - ExpressionActivationPkg.build_package()
        |
        v
[5. Optimize Model]
  - model.optimize() in context
        |
        v
[6. Return Solution]
  - cobra.Solution object
```

### 6.3 Performance Considerations
- **DataFrame operations**: Use vectorized pandas operations where possible for type transformations
- **Dictionary construction**: Single-pass iteration over reactions
- **Memory efficiency**: Avoid copying large DataFrames unless necessary
- **Expected runtime**: O(n) where n is the number of reactions in the model

### 6.4 Integration Points
- **MSExpression.build_reaction_expression()**: For genome-to-model conversion
- **ExpressionActivationPkg**: For building optimization constraints
- **MSModelUtil.pkgmgr**: For accessing FBA packages
- **cobrapy.Model.optimize()**: For solving the optimization problem

---

## 7. Technical Considerations

### 7.1 Dependencies
```python
# Required imports
import pandas as pd
import logging
from typing import Union, Optional
from cobra import Solution
from modelseedpy.core.msmodelutl import MSModelUtil
from modelseedpy.core.msgenome import MSGenome
```

### 7.2 Type Hints
The function should use proper type hints for all parameters and return values:

```python
def fit_model_flux_to_data(
    self,
    model: MSModelUtil,
    condition: str,
    activation_threshold: float = 0.002,
    deactivation_threshold: float = 0.000001
) -> Solution:
```

### 7.3 Exception Hierarchy
```
ValueError - for invalid inputs (mismatched models, missing conditions, invalid thresholds)
RuntimeError - for optimization failures
KeyError - for missing data access (should be caught and converted to ValueError)
```

### 7.4 Existing Code References

| Component | File Path | Lines |
|-----------|-----------|-------|
| MSExpression class | modelseedpy/multiomics/msexpression.py | 221-520 |
| build_reaction_expression | modelseedpy/multiomics/msexpression.py | 454-504 |
| Type transformations | modelseedpy/multiomics/msexpression.py | 209-217 |
| ExpressionActivationPkg | modelseedpy/fbapkg/expressionactivationpkg.py | 1-68 |
| MSModelUtil | modelseedpy/core/msmodelutl.py | Full file |
| MSGrowthPhenotypes.simulate | modelseedpy/core/msgrowthphenotypes.py | 121-297 |

### 7.5 Default Threshold Justification
- **activation_threshold = 0.002**: Represents 0.2% relative abundance, a common cutoff for meaningful expression in RNA-seq data
- **deactivation_threshold = 0.000001**: Represents near-zero expression (0.0001%), effectively marking genes as "not expressed"
- **Threshold gap**: 2000-fold difference ensures clear separation between active and inactive reactions

---

## 8. Success Metrics

### 8.1 Functional Success Criteria
1. **Correct model comparison**: Function correctly identifies when expression model matches/mismatches input model (100% accuracy on test cases)
2. **Accurate data transformation**: Type conversions produce mathematically correct RelativeAbundance values (validated against manual calculations)
3. **Proper threshold application**: Correct number of reactions activated/deactivated for test datasets
4. **Successful optimization**: Integration with downstream flux analysis produces valid FBA solutions
5. **Error handling**: All invalid inputs trigger appropriate, informative exceptions

### 8.2 Test Coverage Targets
- **Unit tests**: ≥95% code coverage for the new function
- **Integration tests**: ≥5 test scenarios covering different expression types and edge cases
- **Edge case tests**: All error conditions tested (mismatched models, missing conditions, invalid thresholds, empty dictionaries)

### 8.3 Documentation Completeness
- **Docstring**: Comprehensive function docstring with examples
- **Type hints**: All parameters and return values annotated
- **User guide**: At least one end-to-end example in documentation
- **API reference**: Function appears in generated API docs

### 8.4 Performance Benchmarks
- **Small model (500 reactions)**: < 1 second
- **Medium model (2000 reactions)**: < 5 seconds
- **Large model (5000 reactions)**: < 15 seconds

---

## 9. Testing Requirements

### 9.1 Unit Tests
**Test File:** `tests/multiomics/test_msexpression.py`

**Required Test Cases:**

1. **test_fit_model_flux_basic**
   - Load gene expression data (FPKM type)
   - Create MSModelUtil with small model
   - Call fit_model_flux_to_data with default thresholds
   - Assert solution.status == "optimal"
   - Assert solution.objective_value is reasonable

2. **test_fit_model_flux_genome_to_model_conversion**
   - Create MSExpression with MSGenome object
   - Call fit_model_flux_to_data
   - Verify build_reaction_expression was called
   - Verify optimization succeeds

3. **test_fit_model_flux_model_mismatch_error**
   - Create MSExpression with Model A
   - Call fit_model_flux_to_data with Model B
   - Assert ValueError is raised with "Models must match" message

4. **test_fit_model_flux_missing_condition_error**
   - Create MSExpression with conditions ["cond1", "cond2"]
   - Call with condition="cond3"
   - Assert ValueError with available conditions listed

5. **test_fit_model_flux_invalid_thresholds**
   - Call with activation_threshold=0.001, deactivation_threshold=0.002
   - Assert ValueError about threshold ordering

6. **test_fit_model_flux_type_transformations**
   - Test each expression type (AbsoluteAbundance, FPKM, TPM, Log2)
   - Verify transformation to RelativeAbundance
   - Verify original data unchanged

7. **test_fit_model_flux_custom_thresholds**
   - Call with activation_threshold=0.01, deactivation_threshold=0.0001
   - Verify correct number of reactions in on_hash and off_hash

8. **test_fit_model_flux_no_activated_reactions**
   - Use very high activation_threshold
   - Assert ValueError about no reactions above threshold

9. **test_fit_model_flux_all_reactions_activated**
   - Use very low activation_threshold
   - Verify off_hash is empty or minimal
   - Verify optimization succeeds

10. **test_fit_model_flux_missing_expression_data**
    - Create expression data missing some reactions
    - Verify those reactions are ignored (not in either hash)

### 9.2 Integration Tests

1. **test_fit_model_flux_with_real_model**
   - Use E. coli core model
   - Load real expression dataset
   - Run fit_model_flux_to_data
   - Compare results with manual ExpressionActivationPkg approach
   - Assert results are identical

2. **test_fit_model_flux_multiple_conditions**
   - Call function for 5 different conditions
   - Verify each returns different flux distributions
   - Verify original data unchanged after all calls

---

### 9.3 Example Test Implementation

```python
def test_fit_model_flux_basic_loading(self):
    """Test basic fit_model_flux_to_data functionality with default thresholds."""
    # Create test data
    data = pd.DataFrame({
        'gene_id': ['gene1', 'gene2', 'gene3'],
        'condition1': [10.5, 5.2, 0.001],
        'condition2': [15.3, 8.7, 0.0005]
    })

    # Create expression object
    expression = MSExpression.from_dataframe(
        data,
        id_column='gene_id',
        type='FPKM',
        genome=test_genome
    )

    # Create model
    model = MSModelUtil.from_cobrapy('test_model.json')

    # Fit model to data
    solution = expression.fit_model_flux_to_data(
        model=model,
        condition='condition1'
    )

    # Assertions
    self.assertEqual(solution.status, 'optimal')
    self.assertIsNotNone(solution.objective_value)
    self.assertGreater(len(solution.fluxes), 0)

def test_fit_model_flux_model_mismatch_raises_error(self):
    """Test that mismatched models raise appropriate error."""
    # Create expression with model A
    expression = MSExpression('RelativeAbundance')
    expression.object = model_a

    # Try to fit with model B
    with self.assertRaises(ValueError) as context:
        expression.fit_model_flux_to_data(
            model=model_util_b,
            condition='cond1'
        )

    self.assertIn('Models must match', str(context.exception))
```

---

## 10. Documentation Requirements

### 10.1 Docstring Format (NumPy Style)

```python
def fit_model_flux_to_data(
    self,
    model: MSModelUtil,
    condition: str,
    activation_threshold: float = 0.002,
    deactivation_threshold: float = 0.000001
) -> Solution:
    """
    Fit metabolic model fluxes to expression data using threshold-based constraints.

    This function integrates gene or reaction expression data with a metabolic model
    to predict fluxes that are consistent with observed expression patterns. Reactions
    with high expression are encouraged (activated), while reactions with low expression
    are discouraged (deactivated).

    The function automatically handles:
    - Conversion from gene-level to reaction-level expression (if needed)
    - Transformation of expression data types to RelativeAbundance
    - Construction of activation/deactivation dictionaries
    - Integration with ExpressionActivationPkg for constrained optimization

    Parameters
    ----------
    model : MSModelUtil
        The metabolic model to fit to expression data. Must contain the same reactions
        as the expression model (if expression is already at reaction level).
    condition : str
        The condition ID whose expression values will be used for fitting. Must exist
        in the expression data conditions.
    activation_threshold : float, optional
        Minimum relative abundance value for a reaction to be considered "active".
        Reactions with expression above this threshold will be encouraged in the
        optimization. Default: 0.002 (0.2% relative abundance).
    deactivation_threshold : float, optional
        Maximum relative abundance value for a reaction to be considered "inactive".
        Reactions with expression below this threshold will be discouraged in the
        optimization. Default: 0.000001 (0.0001% relative abundance).

    Returns
    -------
    cobra.Solution
        The optimized FBA solution with expression-based flux constraints. Contains:
        - objective_value: The optimized objective value
        - fluxes: pandas Series of reaction fluxes
        - status: Optimization status ('optimal', 'infeasible', etc.)

    Raises
    ------
    ValueError
        If the expression model does not match the input model (when expression is
        already at reaction level).
    ValueError
        If the specified condition does not exist in the expression data.
    ValueError
        If activation_threshold is less than or equal to deactivation_threshold.
    ValueError
        If no reactions have expression values above the activation threshold.
    RuntimeError
        If the optimization fails or produces an infeasible solution.

    Notes
    -----
    - This function does NOT modify the original expression data or model
    - All model modifications occur within a context manager and are reverted
    - Reactions without expression data are neither activated nor deactivated
    - The function uses ExpressionActivationPkg internally for constraint building

    Examples
    --------
    Basic usage with gene expression data:

    >>> # Load gene expression data
    >>> expression = MSExpression.from_dataframe(
    ...     gene_expr_df,
    ...     id_column='gene_id',
    ...     type='FPKM',
    ...     genome=my_genome
    ... )
    >>>
    >>> # Load metabolic model
    >>> model = MSModelUtil.from_cobrapy('ecoli_core.json')
    >>>
    >>> # Fit model to expression data for a specific condition
    >>> solution = expression.fit_model_flux_to_data(
    ...     model=model,
    ...     condition='glucose_aerobic'
    ... )
    >>>
    >>> # Examine results
    >>> print(f"Growth rate: {solution.objective_value}")
    >>> print(f"Top fluxes:\\n{solution.fluxes.nlargest(10)}")

    Using custom thresholds:

    >>> solution = expression.fit_model_flux_to_data(
    ...     model=model,
    ...     condition='stress_response',
    ...     activation_threshold=0.005,  # Higher threshold = stricter activation
    ...     deactivation_threshold=0.0001
    ... )

    Comparing multiple conditions:

    >>> conditions = ['glucose', 'xylose', 'glycerol']
    >>> solutions = {}
    >>> for cond in conditions:
    ...     solutions[cond] = expression.fit_model_flux_to_data(model, cond)
    >>>
    >>> # Compare growth rates
    >>> growth_rates = {cond: sol.objective_value for cond, sol in solutions.items()}

    See Also
    --------
    MSExpression.build_reaction_expression : Convert gene to reaction expression
    ExpressionActivationPkg.build_package : Build expression-based constraints
    MSModelUtil.test_single_condition : Run FBA on a single condition

    References
    ----------
    .. [1] Becker, S. A., & Palsson, B. O. (2008). Context-specific metabolic networks
       are consistent with experiments. PLoS computational biology, 4(5), e1000082.
    """
```

### 10.2 User Guide Example

**Location:** Documentation section on "Multi-omics Integration"

```markdown
## Fitting Model Fluxes to Expression Data

The `fit_model_flux_to_data` function provides a streamlined way to integrate
gene or reaction expression data with metabolic models for context-specific
flux predictions.

### Quick Start

```python
from modelseedpy.core.msmodelutl import MSModelUtil
from modelseedpy.multiomics.msexpression import MSExpression

# Load expression data (genes x conditions)
expression = MSExpression.from_spreadsheet(
    'gene_expression.xlsx',
    type='TPM'
)

# Load metabolic model
model = MSModelUtil.from_cobrapy('my_model.json')

# Fit model to expression data
solution = expression.fit_model_flux_to_data(
    model=model,
    condition='experimental_condition_1'
)

# Analyze results
print(f"Predicted growth rate: {solution.objective_value}")
growth_rxn = solution.fluxes['biomass_reaction']
```

### Understanding Thresholds

The function uses two thresholds to classify reactions:

- **Activation threshold** (default: 0.002): Reactions with relative abundance
  above this value are "highly expressed" and encouraged in the optimization

- **Deactivation threshold** (default: 0.000001): Reactions with relative abundance
  below this value are "lowly expressed" and discouraged

Reactions between these thresholds are neither strongly activated nor deactivated.

### Choosing Appropriate Thresholds

Default thresholds work well for most RNA-seq datasets, but you may want to adjust
based on your data characteristics:

```python
# More stringent activation (only very highly expressed reactions activated)
solution = expression.fit_model_flux_to_data(
    model=model,
    condition='my_condition',
    activation_threshold=0.01,  # Top 1% expression
    deactivation_threshold=0.0001
)

# More permissive activation (activate more reactions)
solution = expression.fit_model_flux_to_data(
    model=model,
    condition='my_condition',
    activation_threshold=0.001,  # Top 0.1% expression
    deactivation_threshold=0.00001
)
```
```

---

## 11. Open Questions

1. **Should we support batch processing of multiple conditions?**
   - Option A: Add optional `conditions` parameter accepting a list, returning dict of solutions
   - Option B: Keep single-condition only, users iterate manually
   - **Recommendation**: Start with Option B for simplicity, add Option A in future release if demanded

2. **How should we handle genes with multiple isoforms?**
   - Current GPR approach sums all isoform expression
   - Alternative: Use maximum isoform expression
   - **Recommendation**: Document current behavior, add parameter in future if needed

3. **Should we validate that transformation formulas are scientifically appropriate?**
   - Some conversions (e.g., Log2 → RelativeAbundance) may lose information
   - **Recommendation**: Log warning for Log2 conversion as specified, document limitations

4. **Should we cache transformed expression data for performance?**
   - Pro: Faster repeated calls with same parameters
   - Con: Increased memory usage, cache invalidation complexity
   - **Recommendation**: No caching in initial implementation, profile performance first

5. **Should we allow users to provide pre-computed on_hash/off_hash?**
   - Would provide more control for advanced users
   - **Recommendation**: Not in initial implementation, can add as optional parameters later

6. **How should we handle compartmentalized reactions?**
   - Some reactions exist in multiple compartments with same base ID
   - Current approach: Treat each compartmentalized reaction independently
   - **Recommendation**: Document behavior, consider compartment-aware matching in future

---

## 12. Implementation Checklist

- [ ] Implement `fit_model_flux_to_data` function in `MSExpression` class
- [ ] Add all required imports and type hints
- [ ] Implement validation logic (FR2-FR6)
- [ ] Implement type transformation logic (FR5)
- [ ] Implement dictionary construction (FR7-FR8)
- [ ] Integrate with ExpressionActivationPkg (FR9)
- [ ] Implement optimization and solution return (FR10)
- [ ] Add logging throughout (FR11)
- [ ] Write comprehensive docstring (Section 10.1)
- [ ] Write unit tests (Section 9.1, all 10 test cases)
- [ ] Write integration tests (Section 9.2)
- [ ] Add example to user documentation (Section 10.2)
- [ ] Generate API documentation
- [ ] Run full test suite and achieve ≥95% coverage
- [ ] Performance benchmark on small/medium/large models
- [ ] Code review and refinement

---

## Appendix A: Related Code Snippets

### A.1 Expression Type Transformation Reference

From `modelseedpy/multiomics/msexpression.py:209-217`:

```python
if self.parent.type == "AbsoluteAbundance":
    value = value / condition_obj.column_sum
elif self.parent.type == "FPKM":
    value = value / condition_obj.column_sum
elif self.parent.type == "TPM":
    value = value / condition_obj.column_sum
elif self.parent.type == "Log2":
    value = 2 ** (value - condition_obj.lowest_value()) / \
            2 ** (condition_obj.column_sum - self.parent.features.len() * condition_obj.lowest_value())
```

### A.2 ExpressionActivationPkg Integration Reference

From `modelseedpy/fbapkg/expressionactivationpkg.py:30-68`:

```python
def build_package(self, on_hash, off_hash, on_coeff=None,
                  off_coeff=None, other_coef=0.1, max_value=0.001):
    activation_filter = {}
    for rxn in on_hash:
        activation_filter[rxn] = 1

    self.pkgmgr.getpkg("ReactionActivationPkg").build_package(
        rxn_filter=activation_filter, max_value=max_value)

    expression_objective = self.model.problem.Objective(0, direction="min")
    obj_coef = dict()

    for rxn in self.model.reactions:
        if rxn.id in on_hash:
            coef = on_coeff if on_coeff else on_hash[rxn.id]
            obj_coef[self.pkgmgr.getpkg("ReactionActivationPkg")
                     .variables["fra"][rxn.id]] = -1*coef
            obj_coef[self.pkgmgr.getpkg("ReactionActivationPkg")
                     .variables["rra"][rxn.id]] = -1*coef
        elif rxn.id in off_hash:
            coef = off_coeff if off_coeff else off_hash[rxn.id]
            obj_coef[rxn.forward_variable] = coef
            obj_coef[rxn.reverse_variable] = coef
```

### A.3 Model Optimization Pattern Reference

From `modelseedpy/core/msgrowthphenotypes.py:215-258`:

```python
with target_mdlutl.model:
    # Apply constraints here

    # First optimization
    solution = target_mdlutl.model.optimize()

    # Check solution
    if solution.objective_value < 0.000001:
        # Handle failure
        pass

    # Optional: Second optimization with custom objective
    coefobj = target_mdlutl.model.problem.Objective(0, direction="min")
    target_mdlutl.model.objective = coefobj
    obj_coef = {}
    # ... build coefficients ...
    coefobj.set_linear_coefficients(obj_coef)
    solution = target_mdlutl.model.optimize()

    return solution
```

---

## Document Metadata

- **Version:** 1.0
- **Created:** 2025-10-16
- **Author:** Product Requirements (AI-Generated)
- **Status:** Ready for Implementation
- **Target Release:** Next minor version
- **Estimated Effort:** 3-5 days (implementation + testing + documentation)
