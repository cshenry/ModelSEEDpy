# KBase Workspace Data Types Reference

## Overview

KBase has **223 data types** across **45 modules**. This reference provides a quick lookup for the most commonly used types.

**Full Specifications:** `/Users/chenry/Dropbox/Projects/workspace_deluxe/agent-io/docs/WorkspaceDataTypes/`
- `all_types_list.json` - Complete list of all types
- `all_type_specs.json` - Full specifications
- `individual_specs/` - Individual type specification files

## Types by Module

### Most Used Modules

| Module | Type Count | Description |
|--------|-----------|-------------|
| KBaseFBA | 21 | Flux Balance Analysis, models |
| KBaseGenomes | 8 | Genomes, contigs, features |
| KBaseSets | 8 | Set collections |
| KBaseRNASeq | 13 | RNA sequencing |
| KBaseBiochem | 6 | Biochemistry, media |
| Communities | 31 | Metagenomics |

---

## Core Genome Types (KBaseGenomes)

### Genome
**Type:** `KBaseGenomes.Genome`

The primary genome object containing annotations.

**Key Fields:**
- `id` - Genome identifier
- `scientific_name` - Organism name
- `domain` - Bacteria, Archaea, Eukaryota
- `features` - List of genomic features
- `contigs` - Contig sequences (or reference)
- `source` - Data source (RefSeq, etc.)

**Usage:**
```python
genome = utils.get_object(workspace, genome_ref)
features = genome.get('features', [])
```

### ContigSet
**Type:** `KBaseGenomes.ContigSet`

Set of DNA contigs/sequences.

**Key Fields:**
- `id` - ContigSet identifier
- `contigs` - List of contig objects
- `source` - Data source

### Feature
**Type:** `KBaseGenomes.Feature`

Individual genomic feature (gene, CDS, etc.).

**Key Fields:**
- `id` - Feature identifier
- `type` - Feature type (CDS, gene, rRNA, etc.)
- `location` - Genomic coordinates
- `function` - Functional annotation
- `protein_translation` - Amino acid sequence

### Pangenome
**Type:** `KBaseGenomes.Pangenome`

Comparison of multiple genomes.

---

## FBA and Modeling Types (KBaseFBA)

### FBAModel
**Type:** `KBaseFBA.FBAModel`

Metabolic model for flux balance analysis.

**Key Fields:**
- `id` - Model identifier
- `name` - Model name
- `modelreactions` - List of reactions
- `modelcompounds` - List of metabolites
- `modelcompartments` - Compartments
- `biomasses` - Biomass reactions
- `genome_ref` - Reference to source genome

**Usage:**
```python
model = utils.get_object(workspace, model_ref)
reactions = model.get('modelreactions', [])
```

### FBA
**Type:** `KBaseFBA.FBA`

FBA simulation result.

**Key Fields:**
- `id` - FBA identifier
- `fbamodel_ref` - Reference to model
- `media_ref` - Media used
- `objectiveValue` - Objective function value
- `FBAReactionVariables` - Reaction flux values
- `FBAMetaboliteVariables` - Metabolite values

### Gapfilling
**Type:** `KBaseFBA.Gapfilling`

Gapfilling solution.

### ModelTemplate
**Type:** `KBaseFBA.ModelTemplate`

Template for building models.

### ModelComparison
**Type:** `KBaseFBA.ModelComparison`

Comparison of multiple models.

---

## Biochemistry Types (KBaseBiochem)

### Media
**Type:** `KBaseBiochem.Media`

Growth media definition.

**Key Fields:**
- `id` - Media identifier
- `name` - Media name
- `mediacompounds` - List of compounds and concentrations
- `type` - Media type

**Usage:**
```python
media = utils.get_object(workspace, media_ref)
compounds = media.get('mediacompounds', [])
```

### Biochemistry
**Type:** `KBaseBiochem.Biochemistry`

Biochemistry database (compounds, reactions).

### CompoundSet
**Type:** `KBaseBiochem.CompoundSet`

Collection of compounds.

---

## Set Types (KBaseSets)

### GenomeSet
**Type:** `KBaseSets.GenomeSet`

Set of genome references.

**Key Fields:**
- `description` - Set description
- `items` - List of genome references with labels

### AssemblySet
**Type:** `KBaseSets.AssemblySet`

Set of assembly references.

### ReadsSet
**Type:** `KBaseSets.ReadsSet`

Set of reads library references.

### ExpressionSet
**Type:** `KBaseSets.ExpressionSet`

Set of expression data references.

### SampleSet
**Type:** `KBaseSets.SampleSet`

Set of sample references.

---

## Assembly Types (KBaseAssembly)

### PairedEndLibrary
**Type:** `KBaseAssembly.PairedEndLibrary`

Paired-end reads library.

### SingleEndLibrary
**Type:** `KBaseAssembly.SingleEndLibrary`

Single-end reads library.

### AssemblyReport
**Type:** `KBaseAssembly.AssemblyReport`

Assembly quality report.

---

## RNA-Seq Types (KBaseRNASeq)

### RNASeqAlignment
**Type:** `KBaseRNASeq.RNASeqAlignment`

Read alignment result.

### RNASeqExpression
**Type:** `KBaseRNASeq.RNASeqExpression`

Expression values from RNA-Seq.

### RNASeqDifferentialExpression
**Type:** `KBaseRNASeq.RNASeqDifferentialExpression`

Differential expression analysis.

### RNASeqSampleSet
**Type:** `KBaseRNASeq.RNASeqSampleSet`

Set of RNA-Seq samples.

---

## Expression Types (KBaseFeatureValues)

### ExpressionMatrix
**Type:** `KBaseFeatureValues.ExpressionMatrix`

Gene expression matrix.

**Key Fields:**
- `genome_ref` - Reference genome
- `data` - Expression values matrix
- `feature_ids` - Row identifiers (genes)
- `condition_ids` - Column identifiers (conditions)

### FeatureClusters
**Type:** `KBaseFeatureValues.FeatureClusters`

Clustered features from expression data.

---

## Annotation Types (KBaseGenomeAnnotations)

### Assembly
**Type:** `KBaseGenomeAnnotations.Assembly`

Genome assembly (newer format).

### GenomeAnnotation
**Type:** `KBaseGenomeAnnotations.GenomeAnnotation`

Genome with annotations (newer format).

### Taxon
**Type:** `KBaseGenomeAnnotations.Taxon`

Taxonomic information.

---

## Report Type (KBaseReport)

### Report
**Type:** `KBaseReport.Report`

Standard app output report.

**Key Fields:**
- `text_message` - Report text
- `objects_created` - List of created objects
- `file_links` - Links to downloadable files
- `html_links` - Links to HTML reports
- `warnings` - Warning messages

**Usage:**
```python
report_info = utils.create_extended_report({
    'message': 'Analysis complete',
    'workspace_name': workspace,
    'objects_created': [{'ref': obj_ref, 'description': 'My output'}],
    'file_links': [{'path': '/path/to/file.txt', 'name': 'results.txt'}]
})
```

---

## File Types (KBaseFile)

### FileRef
**Type:** `KBaseFile.FileRef`

Reference to a file in Shock/Blobstore.

### PairedEndLibrary
**Type:** `KBaseFile.PairedEndLibrary`

Paired-end library (file-based).

### SingleEndLibrary
**Type:** `KBaseFile.SingleEndLibrary`

Single-end library (file-based).

---

## Matrix Types (KBaseMatrices)

### ExpressionMatrix
**Type:** `KBaseMatrices.ExpressionMatrix`

Expression data matrix (newer format).

### AmpliconMatrix
**Type:** `KBaseMatrices.AmpliconMatrix`

Amplicon abundance matrix.

### MetaboliteMatrix
**Type:** `KBaseMatrices.MetaboliteMatrix`

Metabolite abundance matrix.

### FitnessMatrix
**Type:** `KBaseMatrices.FitnessMatrix`

Gene fitness data.

---

## Phenotype Types (KBasePhenotypes)

### PhenotypeSet
**Type:** `KBasePhenotypes.PhenotypeSet`

Set of phenotype measurements.

**Key Fields:**
- `genome_ref` - Associated genome
- `phenotypes` - List of phenotypes with media/gene knockouts

### PhenotypeSimulationSet
**Type:** `KBasePhenotypes.PhenotypeSimulationSet`

Predicted phenotypes from FBA.

---

## Tree Types (KBaseTrees)

### Tree
**Type:** `KBaseTrees.Tree`

Phylogenetic tree.

### MSA
**Type:** `KBaseTrees.MSA`

Multiple sequence alignment.

---

## Complete Type List by Module

### KBaseFBA (21 types)
- FBAModel, FBA, Gapfilling, Gapgeneration
- ModelTemplate, NewModelTemplate, ModelComparison
- FBAComparison, FBAModelSet
- FBAPathwayAnalysis, FBAPathwayAnalysisMultiple
- BooleanGeneExpressionData, BooleanGeneExpressionDataCollection
- Classifier, ClassifierResult, ClassifierTrainingSet
- ETC, EscherConfiguration, EscherMap
- PromConstraint, ReactionProbabilities
- ReactionSensitivityAnalysis, SubsystemAnnotation
- MissingRoleData, regulatory_network

### KBaseGenomes (8 types)
- Genome, ContigSet, Feature
- GenomeComparison, GenomeDomainData
- MetagenomeAnnotation, Pangenome
- ProbabilisticAnnotation

### KBaseSets (8 types)
- AssemblySet, DifferentialExpressionMatrixSet
- ExpressionSet, FeatureSetSet
- GenomeSet, ReadsAlignmentSet
- ReadsSet, SampleSet

### KBaseBiochem (6 types)
- Biochemistry, BiochemistryStructures
- CompoundSet, Media, MediaSet
- MetabolicMap

### KBaseRNASeq (13 types)
- RNASeqAlignment, RNASeqAlignmentSet
- RNASeqAnalysis, RNASeqExpression
- RNASeqExpressionSet, RNASeqSample
- RNASeqSampleAlignment, RNASeqSampleSet
- RNASeqDifferentialExpression
- RNASeqCuffdiffdifferentialExpression
- RNASeqCuffmergetranscriptome
- Bowtie2IndexV2, Bowtie2Indexes
- GFFAnnotation, ReferenceAnnotation
- AlignmentStatsResults, DifferentialExpressionStat
- cummerbund_output, cummerbundplot

### KBaseCollections (6 types)
- FBAModelList, FBAModelSet
- FeatureList, FeatureSet
- GenomeList, GenomeSet

---

## Type Reference Usage

When you need detailed information about a specific type:

```python
# Read the individual spec file
spec_path = f"/Users/chenry/Dropbox/Projects/workspace_deluxe/agent-io/docs/WorkspaceDataTypes/individual_specs/{module}_{type}.json"
```

Example spec file name: `KBaseGenomes_Genome.json`
