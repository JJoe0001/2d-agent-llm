# Implemented screening parameters and revision checks

Values below were read from this repository's source on 7 October 2026. They describe the current code, not necessarily the configuration of the historical 143,259-parent production run. The latter needs a versioned run manifest or logs to establish exactly.

| Stage | Current implemented value | Source | Revision check |
| --- | --- | --- | --- |
| Smart extraction delta scan | `[1.2, 1.3, 1.1, 1.4, 1.5]` in that order | `code/exfo_agent/tools/workflow.py` | Manuscript currently says 1.2–1.5 and omits 1.1; identify historical route script and reconcile. |
| Planar density grid | `32×32×32` in smart workflow | `workflow.py` | Repeat 24³, 32³, 48³ on a frozen test panel. |
| Gaussian smoothing | `sigma=0.5*(mean grid count/mean lattice length)` in grid units; comments call it ~0.5 Å | `code/exfo_agent/core/utils.py` | Check actual physical width for anisotropic cells. |
| Normalized density gap level | `0.75` | `core/utils.py`, `tools/planar_gap.py` | Repeat 0.65, 0.75, 0.85. |
| Minimum planar spacing | `dmin=1.8 Å`, then safe minimum at least 1.5 Å or shortest lattice vector/15 | `core/utils.py`, `tools/planar_gap.py` | Repeat 1.5, 1.8, 2.1 Å. |
| Gap score | `width × mean(max(0, gap_level-normalized_density))`; retain positive scores, rank top `k=3` | `core/utils.py`, `workflow.py` | Do not describe a nonzero fixed score cutoff unless found in production config. |
| BONDDEL clustered energy step | `0.03 eV` | `core/config.py` | Repeat 0.02, 0.03, 0.05 eV. |
| BONDDEL weak-bond scan floor | only energy levels `> -2.0 eV` | `core/config.py` | Repeat −1.5, −2.0, −2.5 eV. |
| BONDDEL size/time cap | 600 atoms / 60 seconds, current default | `tools/bond_del.py` | Distinguish from the manuscript's 500-atom **CHGNet** cap. |
| StructureMatcher | `ltol=0.2`, `stol=0.3`, `angle_tol=5°`, primitive cell on | `tools/deduplicate_utils.py` | Repeat tighter and looser tolerance pairs on the same merged CIF panel. |

Sensitivity design: freeze 200–500 parent IDs before testing, stratified by classical layered compounds, mixed-anion/oxide compounds, multi-route parents, and failed/near-threshold cases. Preserve the same code commit, input structures, CHGNet model, and random seeds. Vary one parameter at a time. For each setting report generated structures, deduplicated structures, Jaccard overlap of parent and candidate identifiers with baseline, relaxed-2D retention, and runtime/failure categories. A change in one parameter may alter downstream route calls; record that causal path instead of just plotting final totals.

There is no sensitivity result in this repository yet. Do not claim parameter robustness until those reruns are actually done. If the production code version is unavailable, report the sensitivity as a *new rerun on the published implementation* rather than as a reconstruction of the original production run.
