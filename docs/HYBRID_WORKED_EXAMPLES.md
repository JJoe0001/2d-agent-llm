# Reproduced hybrid-route examples

These are **new reruns of the published implementation** with pymatgen 2026.9.24, not reconstructed production logs. The parent MP CIFs are referenced by ID and SHA-256 but are not redistributed here. Run the two `scripts/reproduce_*_example.py` scripts with the corresponding local parent CIFs to regenerate the checked JSON files in `data/computed_results/`.

## Geometric branch: BaYMgCuAgO5 (`mp-2222863`)

The 10-site bulk parent is classified as a rank-2 connected structure by the current implementation, so the smart workflow selects its geometric slicing branch. The default 32³ density grid, gap threshold 0.75, and top-three plane search found 17 scored planes and considered these three:

| Miller plane | Gap score | First successful extraction delta | Extracted formula/sites | Matches archived candidate |
| --- | ---: | ---: | --- | --- |
| (−1, 1, 0) | 0.208639 | 1.2 | BaYMgCuAgO5 / 10 | `mp-2222863_4606.cif` |
| (−1, −1, 0) | 0.208632 | 1.2 | BaYMgCuAgO5 / 10 | `mp-2222863_4606.cif` |
| (−1, 0, 0) | 0.096663 | 1.2 | BaYMgCuAgO5 / 10 | `mp-2222863_4607.cif` |

The first two orientations resolve to the same archived candidate under `StructureMatcher(ltol=0.2, stol=0.3, angle_tol=5°)`. The third matches the highlighted candidate. These structural matches provide a concrete extraction trace, **not** DFT validation. The parent CIF SHA-256 is `beb52aa25b2e242a39986e88ca7cbc060a414d9839d703a8af9afaef5e61a8ec`.

## Bond-deletion branch: Zn2Cr2O5 (`mp-1376393`)

The current periodic-connectivity classifier gives the 18-site parent rank 3. The BONDDEL routine builds 434 weighted periodic graph edges. It obtains pair parameters from the 5×118×118 element-pair matrix `POTDATA_morse_yukawa_2025` (SHA-256 `213e68e6dc87dad20c5b65053f25df6c63c423137e307b0914b5a7d86eb7dc91`). At the first successful clustered threshold of **−1.557499 eV**, 419 graph edges have weights at or above the threshold and are removed; the graph search returns two rank-2 components, a 7-site Cr2O5 component and a 4-site CrO3 component. The source parent CIF SHA-256 is `3c89c30381259bbbaf1ae44afee8951f8b945367f55923c98abf6b25a0bacf46`.

The edge weight is the implemented heuristic

\[w_{ij}=D_{ij}(1-e^{\alpha_{ij}(r_{0,ij}-r_{ij})})^2-D_{ij}+C_{ij}e^{-\gamma_{ij}r_{ij}}/r_{ij}.\]

For this parent's six unordered element pairs, the loaded `(D [eV], α [Å⁻¹], r0 [Å], C, γ [Å⁻¹])` values are:

| Pair | D | α | r0 | C | γ |
| --- | ---: | ---: | ---: | ---: | ---: |
| Zn–Zn | 0.277223 | 3.052243 | 1.801275 | 0.394133 | 2.328597 |
| Zn–Cr | 0.542555 | 2.580373 | 2.609999 | 1.000000 | 0.000000 |
| Zn–O | 1.383760 | 1.883896 | 1.488958 | 0.386509 | 1.361271 |
| Cr–Cr | 0.173479 | 0.529136 | 4.126809 | 1.214459 | 1.691273 |
| Cr–O | 2.201410 | 1.773444 | 1.519514 | 0.006056 | 1.784954 |
| O–O | 0.509081 | 5.982612 | 1.221396 | −0.871259 | 4.918163 |

The potential table is included in the repository; its original fitting/source documentation is not present. The example illustrates a **candidate graph transformation**, not a physical cleavage energy. The 4-site CrO3 formula also occurs in the final candidate table, but a structural match between this rerun output and its archived CIF was not established. Do not claim the rerun exactly reconstructs that production candidate. Removing 419 of 434 graph edges emphasizes why DFT and a chemically balanced surface model are needed before interpreting physical feasibility.
