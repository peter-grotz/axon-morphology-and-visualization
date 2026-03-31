# 685221 Visualization Walkthrough

This repo is a clean notebook-first walkthrough for the current `685221` analysis outputs.

It covers:

- the latest sagittal 3D CCF render
- CCF renders with aligned SWC reconstructions inside the atlas
- exact-coordinate level-0 XY MIPs
- automated local carveouts and SWC-derived masks
- XY-only PCA and UMAP
- morphology-only PCA and UMAP

The repo now includes the key rendered figures directly under `assets/`, so the main visual outputs are visible on GitHub and do not depend on external local paths.

## Layout

- `assets/`
  Bundled visualization outputs used in the notebook.
- `notebooks/685221_visualization_walkthrough.ipynb`
  Main walkthrough notebook.
- `src/lc_walkthrough/paths.py`
  Small helper module with canonical paths to the bundled assets and to the original workspace scripts.
- `pyproject.toml`
  Minimal project metadata for notebook use.

## Notes

- The notebook reads visual outputs from the repo-local `assets/` directory.
- The notebook still points to the original workspace scripts for the processing entry points, so the implementation references remain accurate.
- The morphology-only UMAP output used by the notebook is:
  [`balanced_carveouts_120_combined_morphology_only_umap`](/Users/peter.grotz/Documents/LC-images/685221/analysis/balanced_carveouts_120_combined_morphology_only_umap)
