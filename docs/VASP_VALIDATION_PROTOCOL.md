# VASP validation plan for the revision

This is an executable calculation plan, not a record of completed DFT results. The 16 CIFs in `examples/dft_validation/` are paired initial and CHGNet-relaxed geometries for two familiar controls (GaS, WS2) and six complex oxide or mixed-anion candidates. File identity and SHA-256 hashes are in `structure_manifest.csv`. All eight were marked relaxed and 2D in the packaged unpassivated screening tables. Start from the CHGNet-relaxed geometry, but retain the initial geometry for a second-start check on any suspicious reconstruction.

## Priority and calculations

| Priority | Candidate file | Role | Atoms in screening table |
| --- | --- | --- | ---: |
| 1 | `mp-2507_2D_ortho.cif` | GaS control | 4 |
| 1 | `mp-224_2DMatPedia.cif` | WS2 control | 3 |
| 1 | `mp-2222863_4607.cif` | BaYMgCuAgO5, highlighted oxide | 10 |
| 1 | `mp-1211355_20554.cif` | KLiAl2Si4(O5F)2, highlighted mixed anion | 20 |
| 2 | `mp-1223590_21201.cif` | KMgMn2AlGe3(O5F)2 | 20 |
| 2 | `mp-1194882_5319.cif` | BaMnPClO4F | 36 |
| 3 | `mp-1221200_44751.cif` | Na4Li4MnFe3P4(O4F)4 | 72 |
| 3 | `mp-1200090_46069.cif` | Na7TiNb2Si4P2O25F | 84 |

Run fixed-cell slab relaxation on all eight; run in-plane variable-cell relaxation on at least the four priority-1 structures plus the two priority-2 structures. Run phonons on both controls and the two highlighted nonclassical structures, then extend if affordable. Include failures in the results table instead of silently replacing them.

## Preparation

1. Record VASP version, PAW potential names/hash or release, exchange-correlation functional, dispersion scheme, machine/parallel settings, and all input/output files. Use one functional and one POTCAR family consistently across slab and bulk energy comparisons. Do not upload licensed POTCAR files to GitHub.
2. Use `examples/dft_validation/prepared_vasp/<candidate>/POSCAR` and `KPOINTS` as **starting geometry inputs**. `scripts/prepare_vasp_structures.py` generated them with ASE from the checksum-verified relaxed CIFs, oriented the slab normal along `c`, and replaced the original very large/oblique vacuum vector with a perpendicular one. Check the atom count, formula, slab normal, layer thickness, and local coordination visually before running. The supplied k mesh is an initial guess, not a converged value. POTCAR and INCAR are intentionally candidate- and machine-specific.
3. Each prepared POSCAR has 20 Å of empty vacuum between periodic slab images. Compare 20 Å and 25 Å on the four priority-1 structures; require the total energy difference per atom to fall below the chosen convergence tolerance. Use identical vacuum in both fixed and variable-cell slab calculations.
4. Check nearest-neighbor distances and formal charge plausibility, especially for the bond-cleaved structures. A compositionally non-neutral or physically disjoint slab needs an explicit termination/chemical-potential model before an exfoliation energy is meaningful.

The local parent-CIF audit found a concrete non-stoichiometric example: `mp-1200090_46069.cif` contains 50 O atoms in its 84-atom slab, while two units of its `mp-1200090` parent cell contain 58 O atoms. A simple slab-minus-bulk exfoliation energy is therefore **invalid** for this candidate. The other seven selected slab/parent pairs have proportional elemental counts; this is a necessary but insufficient condition for a meaningful exfoliation pathway.

## Common convergence and relaxation settings

Use PBE plus D3(BJ), `IVDW=12`, as a documented baseline. Test at least one control and one nonclassical slab for sensitivity to dispersion. Set `PREC=Accurate`, `LASPH=.TRUE.`, `EDIFF=1E-6` eV, `EDIFFG=-0.02` eV/Å, `IBRION=2`, `NSW=200`, `ISMEAR=0`, and `SIGMA=0.05` eV for initial relaxation. Choose `ENCUT` from the POTCAR maximum ENMAX and converge it (start at `1.3×max(ENMAX)`). For metallic solutions, perform a final static energy with appropriate smearing and report the choice. Use `ISPIN=2` and explicit candidate-specific `MAGMOM` starts for Mn/Fe and other likely magnetic systems; compare at least two plausible magnetic initializations. None of these defaults replaces a convergence test.

Begin with an in-plane mesh corresponding to VASP `KSPACING` near 0.25 Å⁻¹, then repeat at 0.20 Å⁻¹ or tighter as needed; use `k_z=1` for isolated slabs. Compare at least two meshes and require energy differences below 1–2 meV/atom and force differences small enough for the relaxation conclusion. The [VASP KSPACING definition](https://vasp.at/wiki/KSPACING) specifies the reciprocal-vector convention. For polar slabs, test `LDIPOL=.TRUE.; IDIPOL=3` with `DIPOL` centered on the slab. The [VASP dipole documentation](https://vasp.at/wiki/LDIPOL) describes this correction and its convergence issues.

**Fixed cell:** `ISIF=2`, relax atom positions only. **In-plane variable cell:** on VASP 6.5.1 or later, `ISIF=3` with `LATTICE_CONSTRAINTS=.TRUE. .TRUE. .FALSE.` for a slab in the `a`–`b` plane; confirm the `c` vector stays fixed in `OUTCAR`. The [VASP lattice-constraint documentation](https://vasp.at/wiki/LATTICE_CONSTRAINTS) notes version limits and caveats for non-orthorhombic cells. If the installed version cannot safely constrain the vacuum vector, instead scan a two-dimensional grid of in-plane lattice strains (for example −4%, −2%, 0, +2%, +4% on each axis, allowing angles if needed), relax atoms at each point with `ISIF=2`, and fit the minimum. Do not report an unconstrained `ISIF=3` slab calculation as an in-plane-only relaxation.

Compare fixed versus variable-cell: in-plane area change, maximum bond-length change, layer thickness change, energy difference per atom, whether 2D connectivity survives, and maximum residual force. Recheck both endpoint structures rather than assuming the CHGNet 2D label survives DFT.

## Energies and phonons

For a **stoichiometrically matching** slab and bulk parent, calculate the reference bulk with the same VASP settings and use

\[ E_{\rm exfol}/A=(E_{\rm slab}-nE_{\rm bulk,formula})/A, \]

where `n` is the number of bulk formula units in the slab and `A` is the in-plane area. Define whether `E_slab` is one monolayer and report the number of surfaces. A symmetric two-surface cleavage calculation uses `2A` in the denominator. If the cut slab differs in composition from the parent, the simple expression is invalid: provide a mass-balanced reaction or grand-potential expression with explicit chemical potentials, and call it a cleavage/formation estimate under those assumptions. The MP parent `E_hull` is not a 2D `E_hull`; a 2D hull requires a consistent set of competing 2D reference phases at the same chemistry and functional. If that set is unavailable, omit a numerical 2D-hull claim.

For phonons, converge the DFT-relaxed geometry more tightly (`EDIFF≤1E-7`, `EDIFFG≤-0.01` eV/Å), use a 2D in-plane supercell whose force constants decay before its boundary, and compare at least two supercell sizes. VASP `IBRION=6` computes finite-difference force constants; a primitive-cell run only gives Γ-point modes, while a supercell is needed for dispersion ([VASP phonon guide](https://vasp.at/wiki/Phonons_from_finite_differences)). Check imaginary branches against k mesh, vacuum, displacement, supercell size, and acoustic-sum-rule treatment. Report genuine unstable modes instead of describing every imaginary frequency as numerical noise.

## Results to return for manuscript integration

Fill `examples/dft_validation/results_template.csv` with one row per candidate and relaxation mode. Attach `INCAR`, `KPOINTS`, `POSCAR`, `CONTCAR`, `OUTCAR`, `vasprun.xml`, phonon force constants/plots, and reference bulk inputs/outputs. The response should report numbers only after these files are checked. Record failed or unconverged jobs in the same table with an error description.
