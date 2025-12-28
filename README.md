# primekg-neo4j-import
Pipeline for converting the PrimeKG biomedical knowledge graph into a Neo4j database using bulk import.

This work was carried out as part of an internship with the Systems Genomics Research Group at the University of Eastern Finland (UEF).

# PrimeKG → Neo4j Bulk Import Pipeline

This repository documents the process of converting the **PrimeKG biomedical knowledge graph**
into a **Neo4j-compatible graph database** using Neo4j’s **bulk import**.

The goal is to transform the original PrimeKG TSV/CSV files into a format that:
- preserves PrimeKG semantics,
- is scalable to millions of edges,
- enables efficient querying, visualization, and downstream analysis in Neo4j.

---

## Overview

**PrimeKG** is a large, heterogeneous biomedical knowledge graph containing:
- genes / proteins
- drugs
- diseases
- pathways
- phenotypes, anatomy, exposures, etc.

The original data is provided as:
- `nodes.tab`
- `edges.csv`

These files cannot be imported directly into Neo4j without preprocessing.

This pipeline:
1. Streams PrimeKG data in chunks.
2. Cleans labels and relationship types to be Neo4j-safe.
3. Produces two CSV files compatible with `neo4j-admin database import`.

---

## Input Data

The raw PrimeKG data used in this pipeline was downloaded from **Harvard Dataverse**: 
PrimeKG: A Precision Medicine Knowledge Graph https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/IXA7BM

### Nodes (`nodes.tab`)
Columns:
- `node_index` — internal numeric ID
- `node_id` — source-specific identifier
- `node_type` — entity type (e.g. `gene/protein`, `drug`)
- `node_name` — human-readable name
- `node_source` — originating database (NCBI, DrugBank, MONDO, etc.)

### Edges (`edges.csv`)
Columns:
- `x_index` — source node index
- `y_index` — target node index
- `relation` — machine-readable relationship type
- `display_relation` — human-friendly label

---

## Output Files

### `primekg_nodes_neo.csv`

Neo4j node import file with columns:

- `node_index:ID` — Neo4j internal node ID
- `node_id`
- `node_source`
- `node_type`
- `node_name`
- `primekg_key` — stable external identifier
- `:LABEL` — Neo4j labels

Each node has:
- a **type-specific label** (e.g. `gene_protein`, `drug`)
- a generic `Node` label for global indexing

---

### `primekg_rels_neo.csv`

Neo4j relationship import file with columns:

- `:START_ID`
- `:END_ID`
- `:TYPE` — sanitized relationship type
- `relation` — original PrimeKG relation
- `display_relation` — readable label

---

## Stable Node Identifier (`primekg_key`)

A stable external key is generated for every node:

- If `node_id` already contains a namespace (`SBO:0000185`), it is kept as-is.
- Otherwise, a key is constructed as:
<node_source>:<node_id>

Examples:
- `NCBI:5297`
- `DrugBank:DB01050`

This key enables:
- matching from Excel / CSV
- external enrichment

---

## Label & Relationship Sanitization

Neo4j requires labels and relationship types to match:
[A-Za-z_][A-Za-z0-9_]*

The pipeline:
- replaces illegal characters with `_`
- collapses repeated underscores
- prefixes tokens starting with digits

Example: gene/protein -> gene_protein

## Implementation Details

- **Chunked processing** (`chunksize = 1_000_000`)  
  → scalable to large graphs

- **Streaming writes**  
  → avoids loading full datasets into memory

- **Minimal validation**
  - drop rows missing critical IDs
  - keep raw relation fields for debugging

---

## Bulk Import into Neo4j

After preprocessing, the database is created using:

```bash
neo4j-admin database import full \
  --nodes=primekg_nodes_neo.csv \
  --relationships=primekg_rels_neo.csv \
  primekg
```
## Resulting Graph

After import, the Neo4j database contains approximately:
 - ~130k nodes
 - ~8 million relationships
---

<img width="230" height="485" alt="kuva" src="https://github.com/user-attachments/assets/cdec4ed9-5860-4f4c-91e8-886c85438eb9" />
The image illustrates the PrimeKG database structure and size in Neo4j after the import has completed.

<img width="468" height="446" alt="subgraph" src="https://github.com/user-attachments/assets/fa0a8317-f67d-4ad4-a223-8538e4015175" />
The image shows an example subgraph visualized in Neo4j Desktop after the bulk import has completed.
It illustrates approved HIV antiretroviral drugs connected to HIV-related disease entities (*HIV infectious disease* and *AIDS*) via `indication` relationships.


## Requirements

- Python 3.9+
- Neo4j 5.x
- Java 21 (required by Neo4j 5)

---

## How to Run

1. Download the PrimeKG raw data from Harvard Dataverse.
2. Update input paths in the preprocessing script to point to:
   - `nodes.tab`
   - `edges.csv`
3. Run the preprocessing script primekg_neo4j_preprocess.py
4. Import the generated CSV files into Neo4j using `neo4j-admin database import full`.
Note: the target database must not exist before running the bulk import.

---

## Scope/Limitations
This pipeline focuses solely on structural transformation and does not modify or enrich PrimeKG content.


