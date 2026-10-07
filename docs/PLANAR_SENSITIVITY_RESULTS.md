# Planar-gap sensitivity: 48-parent stratified rerun

Run on 7 October 2026 with the published `code/exfo_agent` implementation, pymatgen 2026.9.24, and a fixed seed of 20261007. `scripts/planar_sensitivity.py` sampled six parent IDs from each of the eight possible topological/layered/hybrid parent-label signatures, including the `000` negative group. The exact IDs, 336 run records, and aggregate results are in `data/computed_results/planar_sensitivity_*`. The local parent CIF library used for this rerun is not in the GitHub package; refer to the parent IDs and original MP source.

| Setting changed from baseline | Parents yielding ≥1 scored plane | Same highest-ranked Miller plane as baseline |
| --- | ---: | ---: |
| Baseline: gap 0.75, dmin 1.8 Å, grid 32³ | 48/48 | 48/48 |
| Gap threshold 0.65 | 47/48 | 38/48 |
| Gap threshold 0.85 | 48/48 | 42/48 |
| Minimum plane spacing 1.5 Å | 48/48 | 36/48 |
| Minimum plane spacing 2.1 Å | 48/48 | 43/48 |
| Density grid 24³ | 48/48 | 36/48 |
| Density grid 48³ | 48/48 | 38/48 |

Every run completed without a Python exception. The best plane changes for 5–12 of 48 parents under the tested settings, which shows that the ranking has material parameter sensitivity. This check ends **before** layer extraction, deduplication, CHGNet, or 2D retention, so the table must not be read as a final candidate-yield or stability sensitivity result. Even the `000` group yields geometric planes: a positive gap score alone is not a recovered 2D material. A full sensitivity claim still requires downstream reruns and BONDDEL/StructureMatcher variation.
