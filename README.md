# 685221 Visualization Walkthrough

This repo is a clean notebook-first walkthrough for the current `685221` analysis outputs in the surrounding workspace.

It covers:

- the latest sagittal 3D CCF render
- CCF renders with aligned SWC reconstructions inside the atlas
- exact-coordinate level-0 XY MIPs
- automated local carveouts and SWC-derived masks
- XY-only PCA and UMAP
- morphology-only PCA and UMAP

## Layout

- `notebooks/685221_visualization_walkthrough.ipynb`
  Main walkthrough notebook.
- `src/lc_walkthrough/paths.py`
  Small helper module with canonical paths to the current outputs.
- `pyproject.toml`
  Minimal project metadata for notebook use.

## Notes

- The notebook reads from the existing analysis outputs already present under:
  - [`685221/analysis`](/Users/peter.grotz/Documents/LC-images/685221/analysis)
  - [`analysis`](/Users/peter.grotz/Documents/LC-images/analysis)
- It does not duplicate the heavy processing steps. Instead it documents the exact scripts and outputs used in the current workspace.
- The morphology-only UMAP output used by the notebook is:
  [`balanced_carveouts_120_combined_morphology_only_umap`](/Users/peter.grotz/Documents/LC-images/685221/analysis/balanced_carveouts_120_combined_morphology_only_umap)
