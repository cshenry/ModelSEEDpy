# KIDL Specification Reference

## Overview

KIDL (KBase Interface Description Language) defines the interface for KBase modules. It specifies:
- Data types (typedefs)
- Function signatures
- Authentication requirements
- Documentation

## Basic Types

| Type | Description | Example |
|------|-------------|---------|
| `string` | Text value | `"hello"` |
| `int` | Integer | `42` |
| `float` | Floating point | `3.14` |
| `bool` | Boolean (0 or 1) | `1` |
| `UnspecifiedObject` | Any JSON object | `{}` |
| `list<T>` | List of type T | `["a", "b"]` |
| `mapping<K, V>` | Key-value pairs | `{"key": "value"}` |
| `tuple<T1, T2>` | Fixed-length tuple | `["a", 1]` |

## Type Definitions

### Simple Typedef
```kidl
typedef string genome_ref;
typedef int workspace_id;
```

### Structure Typedef
```kidl
typedef structure {
    string workspace_name;
    string object_name;
    string object_ref;
} ObjectInfo;
```

### Nested Structures
```kidl
typedef structure {
    string id;
    string name;
    list<string> aliases;
} Feature;

typedef structure {
    string id;
    list<Feature> features;
} Genome;
```

### Optional Fields
```kidl
typedef structure {
    string required_field;
    string optional_field;  /* marked optional in spec.json */
} MyParams;
```

### Mappings and Lists
```kidl
typedef mapping<string, int> StringToIntMap;
typedef list<string> StringList;
typedef mapping<string, list<string>> StringToListMap;
```

### Tuple Types
```kidl
typedef tuple<string object_id, int version> ObjectVersion;
```

## Function Definitions

### Basic Function
```kidl
funcdef my_function(MyParams params)
    returns (MyResults results)
    authentication required;
```

### Function with Multiple Returns
```kidl
funcdef get_info(string ref)
    returns (string name, int size, string type)
    authentication required;
```

### Function with No Return
```kidl
funcdef log_event(string message)
    returns ()
    authentication required;
```

### Function Documentation
```kidl
/*
 * Short description of function.
 *
 * Longer description with details about what the function does,
 * what parameters it expects, and what it returns.
 *
 * @param params The input parameters
 * @return results The output results
 */
funcdef documented_function(Params params)
    returns (Results results)
    authentication required;
```

## Authentication Options

```kidl
/* Requires valid KBase token */
funcdef secure_func(Params p) returns (Results r) authentication required;

/* No authentication needed */
funcdef public_func(Params p) returns (Results r) authentication none;

/* Optional authentication */
funcdef optional_auth_func(Params p) returns (Results r) authentication optional;
```

## Complete Module Example

```kidl
/*
 * A KBase module: GenomeAnalyzer
 *
 * This module provides tools for analyzing genome data,
 * including feature extraction and sequence analysis.
 */
module GenomeAnalyzer {

    /* Reference to a genome object */
    typedef string genome_ref;

    /* Reference to a workspace object */
    typedef string ws_ref;

    /* Feature information extracted from genome */
    typedef structure {
        string feature_id;
        string feature_type;
        int start;
        int end;
        string strand;
        string sequence;
    } FeatureInfo;

    /* Input parameters for analyze_genome */
    typedef structure {
        string workspace_name;
        genome_ref genome_ref;
        int min_feature_length;
        list<string> feature_types;
    } AnalyzeGenomeParams;

    /* Results from analyze_genome */
    typedef structure {
        string report_name;
        ws_ref report_ref;
        int features_analyzed;
        list<FeatureInfo> feature_summary;
    } AnalyzeGenomeResults;

    /* Input for batch analysis */
    typedef structure {
        string workspace_name;
        list<genome_ref> genome_refs;
    } BatchAnalyzeParams;

    /* Results from batch analysis */
    typedef structure {
        string report_name;
        ws_ref report_ref;
        mapping<genome_ref, int> genome_feature_counts;
    } BatchAnalyzeResults;

    /*
     * Analyze a single genome for features.
     *
     * This function extracts and analyzes features from the specified
     * genome, filtering by minimum length and feature type.
     *
     * @param params Analysis parameters including genome reference
     * @return results Analysis results with report reference
     */
    funcdef analyze_genome(AnalyzeGenomeParams params)
        returns (AnalyzeGenomeResults results)
        authentication required;

    /*
     * Analyze multiple genomes in batch.
     *
     * @param params Batch parameters with list of genome references
     * @return results Batch results with per-genome counts
     */
    funcdef batch_analyze(BatchAnalyzeParams params)
        returns (BatchAnalyzeResults results)
        authentication required;
};
```

## Compilation

After modifying the spec file, always run:
```bash
make
```

This regenerates:
- `lib/MyModule/MyModuleImpl.py` - Implementation stubs
- `lib/MyModule/MyModuleServer.py` - Server code
- `lib/MyModule/MyModuleClient.py` - Client code

## Common Patterns

### Workspace References
```kidl
typedef string ws_ref;  /* Format: "workspace/object" or "workspace/object/version" */
```

### Report Output
```kidl
typedef structure {
    string report_name;
    string report_ref;
} ReportOutput;
```

### Standard Input Pattern
```kidl
typedef structure {
    string workspace_name;
    string workspace_id;  /* Alternative to name */
    /* ... other params */
} StandardParams;
```

## Tips

1. **Keep types simple** - Complex nested structures are hard to maintain
2. **Use meaningful names** - `genome_ref` not `gr` or `ref1`
3. **Document everything** - Comments become API documentation
4. **Use lists for collections** - `list<Feature>` not repeated fields
5. **Use mappings for lookups** - `mapping<string, Feature>` for ID-based access
