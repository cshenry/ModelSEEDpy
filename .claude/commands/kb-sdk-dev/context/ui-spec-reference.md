# KBase Narrative UI Specification Reference

## File Structure

Each app method requires two files in `ui/narrative/methods/<method_id>/`:
- `spec.json` - Parameter mapping and validation
- `display.yaml` - UI labels, hints, and documentation

## spec.json Reference

### Complete Structure

```json
{
    "ver": "1.0.0",
    "authors": ["username"],
    "contact": "email@example.com",
    "categories": ["active"],
    "widgets": {
        "input": null,
        "output": "no-display"
    },
    "parameters": [...],
    "behavior": {
        "service-mapping": {...}
    },
    "job_id_output_field": "docker"
}
```

### Parameter Types

#### Text Input
```json
{
    "id": "my_string",
    "optional": false,
    "advanced": false,
    "allow_multiple": false,
    "default_values": ["default_value"],
    "field_type": "text",
    "text_options": {
        "valid_ws_types": []
    }
}
```

#### Integer Input
```json
{
    "id": "my_int",
    "optional": true,
    "advanced": false,
    "allow_multiple": false,
    "default_values": ["10"],
    "field_type": "text",
    "text_options": {
        "validate_as": "int",
        "min_int": 1,
        "max_int": 100
    }
}
```

#### Float Input
```json
{
    "id": "my_float",
    "optional": true,
    "advanced": true,
    "allow_multiple": false,
    "default_values": ["0.5"],
    "field_type": "text",
    "text_options": {
        "validate_as": "float",
        "min_float": 0.0,
        "max_float": 1.0
    }
}
```

#### Workspace Object Selector
```json
{
    "id": "genome_ref",
    "optional": false,
    "advanced": false,
    "allow_multiple": false,
    "default_values": [""],
    "field_type": "text",
    "text_options": {
        "valid_ws_types": ["KBaseGenomes.Genome"]
    }
}
```

#### Multiple Object Types
```json
{
    "id": "input_ref",
    "optional": false,
    "advanced": false,
    "allow_multiple": false,
    "default_values": [""],
    "field_type": "text",
    "text_options": {
        "valid_ws_types": [
            "KBaseGenomes.Genome",
            "KBaseGenomeAnnotations.Assembly"
        ]
    }
}
```

#### Dropdown/Select
```json
{
    "id": "algorithm",
    "optional": false,
    "advanced": false,
    "allow_multiple": false,
    "default_values": ["default"],
    "field_type": "dropdown",
    "dropdown_options": {
        "options": [
            {"value": "fast", "display": "Fast (less accurate)"},
            {"value": "default", "display": "Default"},
            {"value": "accurate", "display": "Accurate (slower)"}
        ]
    }
}
```

#### Checkbox (Boolean)
```json
{
    "id": "include_empty",
    "optional": true,
    "advanced": true,
    "allow_multiple": false,
    "default_values": ["0"],
    "field_type": "checkbox",
    "checkbox_options": {
        "checked_value": 1,
        "unchecked_value": 0
    }
}
```

#### Multiple Selection
```json
{
    "id": "genomes",
    "optional": false,
    "advanced": false,
    "allow_multiple": true,
    "default_values": [""],
    "field_type": "text",
    "text_options": {
        "valid_ws_types": ["KBaseGenomes.Genome"]
    }
}
```

#### Textarea (Multi-line)
```json
{
    "id": "description",
    "optional": true,
    "advanced": false,
    "allow_multiple": false,
    "default_values": [""],
    "field_type": "textarea",
    "textarea_options": {
        "n_rows": 5
    }
}
```

#### Output Object Name
```json
{
    "id": "output_name",
    "optional": false,
    "advanced": false,
    "allow_multiple": false,
    "default_values": [""],
    "field_type": "text",
    "text_options": {
        "valid_ws_types": [],
        "is_output_name": true
    }
}
```

### Behavior Section

#### Input Mapping

```json
"input_mapping": [
    {
        "narrative_system_variable": "workspace",
        "target_property": "workspace_name"
    },
    {
        "narrative_system_variable": "workspace_id",
        "target_property": "workspace_id"
    },
    {
        "input_parameter": "genome_ref",
        "target_property": "genome_ref",
        "target_type_transform": "resolved-ref"
    },
    {
        "input_parameter": "min_length",
        "target_property": "min_length",
        "target_type_transform": "int"
    },
    {
        "input_parameter": "threshold",
        "target_property": "threshold",
        "target_type_transform": "float"
    },
    {
        "input_parameter": "genomes",
        "target_property": "genome_refs",
        "target_type_transform": "list<resolved-ref>"
    }
]
```

#### Type Transforms

| Transform | Description |
|-----------|-------------|
| `resolved-ref` | Converts object name to full reference |
| `ref` | Keep as reference string |
| `int` | Parse as integer |
| `float` | Parse as float |
| `string` | Keep as string (default) |
| `list<resolved-ref>` | List of resolved references |
| `list<int>` | List of integers |

#### Output Mapping

```json
"output_mapping": [
    {
        "service_method_output_path": [0, "report_name"],
        "target_property": "report_name"
    },
    {
        "service_method_output_path": [0, "report_ref"],
        "target_property": "report_ref"
    },
    {
        "narrative_system_variable": "workspace",
        "target_property": "workspace_name"
    }
]
```

### Widget Options

```json
"widgets": {
    "input": null,
    "output": "no-display"
}
```

Common output widgets:
- `"no-display"` - No output display (use for report-based apps)
- `"kbaseReportView"` - Display KBase report

## display.yaml Reference

### Complete Structure

```yaml
name: My App Name

tooltip: |
    Brief one-line description of the app

screenshots:
    - my_screenshot.png

icon: icon.png

suggestions:
    apps:
        related:
            - related_app_1
            - related_app_2
        next:
            - follow_up_app
    methods:
        related: []
        next: []

parameters:
    genome_ref:
        ui-name: |
            Genome
        short-hint: |
            Select a genome object
        long-hint: |
            Select a genome object from your Narrative data panel.
            The genome should have annotated features.

    min_length:
        ui-name: |
            Minimum Length
        short-hint: |
            Minimum feature length
        long-hint: |
            Features shorter than this value will be excluded
            from the analysis. Default is 100 bp.

    output_name:
        ui-name: |
            Output Name
        short-hint: |
            Name for the output object
        long-hint: |
            Provide a name for the output object that will be
            saved to your Narrative.

description: |
    <p>Full description of the app in HTML format.</p>

    <h3>Overview</h3>
    <p>What this app does and why you would use it.</p>

    <h3>Inputs</h3>
    <ul>
        <li><b>Genome</b> - A KBase genome object</li>
        <li><b>Minimum Length</b> - Filter threshold</li>
    </ul>

    <h3>Outputs</h3>
    <p>This app produces:</p>
    <ul>
        <li>A summary report</li>
        <li>Downloadable data files</li>
    </ul>

    <h3>Algorithm</h3>
    <p>Description of the methodology used.</p>

publications:
    - pmid: 12345678
      display-text: |
          Author A, Author B (2024) Title of paper. Journal Name 10:123-456
      link: https://doi.org/10.xxxx/xxxxx

    - display-text: |
          Software documentation at https://example.com
      link: https://example.com
```

### Parameter Groups

For complex apps, group related parameters:

```yaml
parameter-groups:
    basic_options:
        ui-name: Basic Options
        short-hint: Core parameters for the analysis
        parameters:
            - genome_ref
            - output_name

    advanced_options:
        ui-name: Advanced Options
        short-hint: Fine-tune the analysis
        parameters:
            - min_length
            - threshold
            - algorithm
```

### Fixed Parameters

Parameters not shown in UI but passed to service:

```json
"fixed_parameters": [
    {
        "target_property": "version",
        "target_value": "1.0"
    }
]
```

## Common Workspace Types for valid_ws_types

| Type | Description |
|------|-------------|
| `KBaseGenomes.Genome` | Annotated genome |
| `KBaseGenomeAnnotations.Assembly` | Genome assembly |
| `KBaseSets.GenomeSet` | Set of genomes |
| `KBaseFBA.FBAModel` | Metabolic model |
| `KBaseFBA.FBA` | FBA solution |
| `KBaseFBA.Media` | Growth media |
| `KBaseRNASeq.RNASeqAlignment` | RNA-seq alignment |
| `KBaseMatrices.ExpressionMatrix` | Expression data |
| `KBaseFile.AssemblyFile` | Assembly file |
| `KBaseSets.ReadsSet` | Set of reads |

## Tips

1. **Use advanced: true** for optional parameters to reduce UI clutter
2. **Provide good defaults** - Apps should work with minimal configuration
3. **Write clear hints** - Users rely on short-hint for quick understanding
4. **Use dropdown for constrained choices** - Better than free text for enumerated options
5. **Group related parameters** - Improves usability for complex apps
6. **Include publications** - Helps users cite your work properly
