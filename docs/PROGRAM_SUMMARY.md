# Program summary

## Program title

Route-aware high-throughput exfoliation workflow for two-dimensional materials discovery

## Authors

Author A, Musen Li, Tianhao Su, Zihang Li, Shunbo Hu, Tongyi Zhang

## Licensing provisions

MIT-style academic open-source license. See `../LICENSE`.

## Programming language

Python 3.10 or newer. The original production environment used Python 3.11 for the MCP server and scientific Python libraries.

## External routines/libraries

Core dependencies include `pymatgen`, `numpy`, `pandas`, `scipy`, `networkx`, `mcp`, `fastmcp`, `torch`, `chgnet`, `ase`, `matplotlib`, `seaborn`, `tqdm`, `joblib`, and `pebble`.

## Nature of problem

High-throughput 2D materials discovery is sensitive to the exfoliation criterion used to generate candidates from 3D parent crystals. Single-route screening can bias the candidate set toward familiar layered materials. The program organizes topological, layered-supercell, and hybrid geometric/weak-bond exfoliation routes in a unified MCP-accessible workflow, then supports deduplication, dimensionality filtering, and CHGNet-based energy evaluation.

## Solution method

The package exposes route-level and batch-level tools through an MCP service. The topological route detects 2D connected components in periodic graphs. The layered route identifies layered parents through supercell cluster scaling. The hybrid route combines plane-averaged density scanning, geometric layer extraction, and XCP-weighted weak-bond deletion. Candidate structures can then be merged, deduplicated with structure matching, relaxed with CHGNet, and summarized into parent- and candidate-level labels.

## Restrictions

Large-scale production runs require a complete parent-structure database and sufficient CPU/GPU resources. CHGNet relaxation requires the `chgnet` and `torch` stack. The large generated CIF libraries are not included in this compact submission package and should be distributed through an external repository.

## Typical running time

The minimal example is intended only for input-format and data-schema verification. Full screening over more than \(10^5\) parent structures is a high-throughput run whose wall time depends on route settings, candidate count, CPU parallelism, and whether CHGNet relaxation is enabled.

## Included data

The package includes processed parent-level and candidate-level labels, route-source summaries, energy summaries, and a minimal parent-structure sample. Full generated CIF files are treated as external large files.
