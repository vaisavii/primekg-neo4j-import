import pandas as pd
import re
from tqdm import tqdm

# -------------------------------------------------------------------
# PrimeKG -> Neo4j bulk import preprocessing
# -------------------------------------------------------------------

NODES_PATH = "/research/groups/bioinformaticians/internship/vaisavii/primekg/primekg_raw/nodes.tab"
EDGES_PATH = "/research/groups/bioinformaticians/internship/vaisavii/primekg/primekg_raw/edges.csv"

OUT_NODES = "primekg_nodes_neo.csv"
OUT_RELS  = "primekg_rels_neo.csv"

CHUNK_SIZE = 1_000_000

# -------------------------------------------------------------------
# Helper: sanitize labels and relationship types
# -------------------------------------------------------------------
_token_re = re.compile(r"[^0-9A-Za-z_]+")

def clean_token(x: str) -> str:
    """Neo4j-safe LABEL/TYPE token: [A-Za-z_][A-Za-z0-9_]*"""
    if pd.isna(x):
        x = ""
    x = str(x).strip()
    x = _token_re.sub("_", x)
    x = re.sub(r"_+", "_", x).strip("_")
    if x == "" or x[0].isdigit():
        x = "T_" + x
    return x

def make_primekg_key(node_source: str, node_id: str) -> str:
    """
    Smooth stable key for matching from Excel:
      - If node_id already contains ':' (e.g. 'SBO:0000185'), keep it as-is
      - Else use 'source:node_id' (e.g. 'DrugBank:DB01050')
    """
    s = "" if pd.isna(node_source) else str(node_source).strip()
    i = "" if pd.isna(node_id) else str(node_id).strip()
    if i == "":
        return ""
    if ":" in i:
        return i
    if s == "":
        return i
    return f"{s}:{i}"

# -------------------------------------------------------------------
# NODES (streaming write)
# Output columns:
#   node_index:ID, node_id, node_source, node_type, node_name, primekg_key, :LABEL
# Notes:
#   - node_index is used as admin-import internal ID
#   - node_id + node_source are kept for debugging and lookups
#   - primekg_key enables stable matching from Excel
#   - add generic label :Node for easy indexing and queries
# -------------------------------------------------------------------
labels_base_seen = set()

nodes_reader = pd.read_csv(
    NODES_PATH,
    sep="\t",
    low_memory=False,
    chunksize=CHUNK_SIZE
)

with open(OUT_NODES, "w") as f_out:
    header_written = False

    for chunk in tqdm(nodes_reader, desc="Processing/writing PrimeKG nodes"):
        # select
        df = chunk[["node_index", "node_id", "node_source", "node_type", "node_name"]].copy()

        # minimal validation
        df = df.dropna(subset=["node_index", "node_id", "node_type"])

        # rename for neo4j-admin import
        df.rename(columns={"node_index": "node_index:ID"}, inplace=True)

        # stable external key (best for your future Cypher + Excel)
        df["primekg_key"] = [
            make_primekg_key(s, i) for s, i in zip(df["node_source"], df["node_id"])
        ]

        # labels: node_type + generic Node label (multi-label separated by ';')
        df["_base_label"] = df["node_type"].map(clean_token)
        df[":LABEL"] = df["_base_label"] + ";Node"
        labels_base_seen.update(df["_base_label"].unique().tolist())
        df.drop(columns=["_base_label"], inplace=True)

        # write chunk
        df.to_csv(f_out, index=False, header=(not header_written))
        header_written = True

# -------------------------------------------------------------------
# RELATIONSHIPS (streaming write)
# Output columns:
#   :START_ID, :END_ID, :TYPE, relation, display_relation
# Notes:
#   - 30 relationship types is fine -> keep :TYPE = relation (sanitized)
#   - also keep raw relation + display_relation as properties for readability/debug
# -------------------------------------------------------------------
types_seen = set()

rels_reader = pd.read_csv(
    EDGES_PATH,
    low_memory=False,
    chunksize=CHUNK_SIZE
)

with open(OUT_RELS, "w") as f_out:
    header_written = False

    for chunk in tqdm(rels_reader, desc="Processing/writing PrimeKG rels"):
        df = chunk[["x_index", "y_index", "relation", "display_relation"]].copy()

        # minimal validation
        df = df.dropna(subset=["x_index", "y_index", "relation"])

        # rename for neo4j-admin import
        df.rename(columns={"x_index": ":START_ID", "y_index": ":END_ID"}, inplace=True)

        # relationship type token
        df[":TYPE"] = df["relation"].map(clean_token)
        types_seen.update(df[":TYPE"].unique().tolist())

        df = df[[":START_ID", ":END_ID", ":TYPE", "relation", "display_relation"]]

        # write chunk
        df.to_csv(f_out, index=False, header=(not header_written))
        header_written = True

# -------------------------------------------------------------------
# Summary
# -------------------------------------------------------------------
print(f"Wrote {OUT_NODES} and {OUT_RELS}")
print("Unique base node labels (node_type):", len(labels_base_seen))
print("Unique Neo4j relationship types:", len(types_seen))
print("All nodes also have :Node label and 'primekg_key' for easy matching.")
