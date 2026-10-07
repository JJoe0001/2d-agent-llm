# Revision data audit (7 October 2026)

Run `python scripts/revision_audit.py` to regenerate `data/computed_results/revision_screening_summary.json`. The script checks unique candidate identifiers, route flags, parent mappings, dimensionality-table joins, and route classifications against filename suffixes. All counts below use the compact files packaged in this repository.

## Corrected screening counts

| Stage | Topological | Layered | Hybrid | Total |
| --- | ---: | ---: | ---: | ---: |
| Route CIFs before deduplication | 32,876 | 6,266 | 37,710 | 76,852 |
| Candidate rows after deduplication | 29,614 | 6,046 | 37,445 | 73,105 |
| Relaxed and classified 2D, unpassivated | 28,359 | 5,977 | 33,753 | 68,089 |

The submitted manuscript assigns 37,710 to the topological route and 32,876 to the hybrid route. This reverses the provenance shown by the merged CIF suffixes (`_2D_ortho` for topological; numeric suffix for hybrid), the final candidate `route_*` flags, and the original route plot script. Correct the manuscript text and Figure 2 candidate-yield labels. Parent-level overlap is a different metric and must be checked independently before editing its labels. Some original local directories have misleading route names; the file-level manifest and final candidate flags are the audit sources.

The 73,105 rows map to 47,617 distinct MP parent identifiers. One additional candidate, `mvc-5327_2D_ortho.cif`, has a blank `parent_id`; retain it in the candidate denominator and disclose its missing parent link. There are 3,747 deduplicated CIFs.

## Screening funnel and interpretation

| Stage (denominator 73,105 unique candidates) | Count |
| --- | ---: |
| `is_relaxed=True` in the final table | 69,624 |
| `is_relaxed=False` | 3,481 |
| Unpassivated `dim_type=2D` label, regardless of relaxation | 71,096 |
| **Unpassivated relaxed and `dim_type=2D`** | **68,089** |
| `dim_type=2D` without successful relaxation | 3,007 |
| Unpassivated fragmented / parse error / 1D | 1,582 / 425 / 2 |
| Passivated relaxed and `dim_type=2D` | 63,464 |

The original `validation_status="Thermo Stable (No Mech)"` appears on 72,577 rows, including unrelaxed rows. It is a pipeline label, **not** evidence of stability on a 2D convex hull, phonon stability, or experimental exfoliability. The 68,089 figure is a geometrical screening count conditioned on successful CHGNet relaxation; it does not establish 2D thermodynamic stability. Formation energies and parent MP hull energies likewise cannot substitute for a 2D hull calculation.

Two candidate rows have no formula string. Among the other rows there are 39,709 distinct formula strings and 16,124 distinct element sets (chemical systems). Formula strings are not normalized compositions or structure prototypes; these figures are descriptive composition metrics and should not be called unique phases. Route-specific formula/chemical-system counts are in the JSON summary; overlap means their sum exceeds the whole-set total.

## Items still requiring external calculation or source evidence

- DFT slab and parent bulk relaxations and energies, in-plane variable-cell comparison, and phonons on representative structures. The prepared CIFs and protocol are in `examples/dft_validation/` and `docs/VASP_VALIDATION_PROTOCOL.md`. No DFT result is claimed here.
- Among the eight DFT examples, the Na7TiNb2Si4P2O25F cut slab is oxygen-deficient relative to its MP parent; it requires an explicit mass-balanced reaction or chemical-potential reference before an exfoliation/cleavage energy can be defined.
- Database recovery rates for 2DMatPedia, MC2D, and C2DB require versioned reference structures and a stated structural matching tolerance. The submitted "no direct match" entries are currently unverified; do not call them newly discovered phases.
- `docs/DATABASE_BENCHMARK_PROTOCOL.md` specifies reference snapshots, denominators, matching hierarchy, and novelty terminology; a historical 2DMatPedia pilot exists locally but does not satisfy the complete three-database benchmark.
- Threshold sensitivity requires rerunning the route extraction with frozen parent subsets and exact code/configuration versions. The repository now exposes the implemented parameters, but historical large-scale input/output logs are incomplete.
- A 48-parent, seven-setting planar-gap sensitivity rerun and two actual hybrid-route worked examples are now in `docs/PLANAR_SENSITIVITY_RESULTS.md` and `docs/HYBRID_WORKED_EXAMPLES.md`. Their scope and failure to establish physical stability are stated there.
- `docs/PARAMETER_AUDIT.md` records current implementation values and flags two manuscript/code differences: the smart route includes a 1.1 delta trial, and BONDDEL's current 600-atom cap is separate from the 500-atom CHGNet cap.
- The authors recall GPT-5.4, but the production API model ID/snapshot, prompts, tool-call traces, retry rates, token use, and context failures cannot be reconstructed from the present files. State the evidence gap in the response and do not invent operational statistics. See `docs/LLM_CODE_MAP.md`.
- Archive the full derived candidate CIF library and figure inputs with a DOI; add both a version DOI and a concept/latest DOI to the Data Availability Statement. Verify Materials Project redistribution terms before publishing parent CIFs.
