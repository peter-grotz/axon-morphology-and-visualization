from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = REPO_ROOT.parent


PATHS = {
    "workspace_root": WORKSPACE_ROOT,
    "latest_ccf_render": WORKSPACE_ROOT / "analysis" / "ccf_sagittal_3d_white_glass_fullbrain_4k_dimmer_moretranslucent.png",
    "ccf_overlay_n053": WORKSPACE_ROOT / "analysis" / "ccf_sagittal_3d_white_glass_fullbrain_4k_with_N053.png",
    "ccf_overlay_n047": WORKSPACE_ROOT / "analysis" / "ccf_sagittal_3d_white_glass_fullbrain_4k_with_N047.png",
    "render_script": WORKSPACE_ROOT / "scripts" / "render_ccf_sagittal_3d.py",
    "mip_script": WORKSPACE_ROOT / "scripts" / "generate_exact_level0_dual_mips.py",
    "carveout_script": WORKSPACE_ROOT / "scripts" / "generate_masked_local_swc_carveouts.py",
    "xy_pca_script": WORKSPACE_ROOT / "scripts" / "extract_xy_only_neurite_features.py",
    "morph_pca_script": WORKSPACE_ROOT / "scripts" / "analyze_morphology_only_pca.py",
    "xy_umap_script": WORKSPACE_ROOT / "scripts" / "plot_xy_umap.py",
    "mip_grouped_dir": WORKSPACE_ROOT / "685221" / "analysis" / "requested_six_more_level0_dual_grouped_images",
    "mip_batch_dir": WORKSPACE_ROOT / "685221" / "analysis" / "requested_six_more_level0_dual_publics3",
    "mask_examples_dir": WORKSPACE_ROOT / "685221" / "analysis" / "masked_local_carveouts_traced_examples",
    "mask_qc_example": WORKSPACE_ROOT / "685221" / "analysis" / "masked_local_carveouts_traced_examples" / "thalamus_thalamus_01_pvt_x18116p926_y11354p652_z13640p186_N053" / "qc_mask_visualization.png",
    "mask_overview_xy": WORKSPACE_ROOT / "685221" / "analysis" / "masked_local_carveouts_traced_examples" / "qc_overview_xy.png",
    "xy_pca_dir": WORKSPACE_ROOT / "685221" / "analysis" / "balanced_carveouts_120_combined_xy_only",
    "xy_umap_dir": WORKSPACE_ROOT / "685221" / "analysis" / "balanced_carveouts_120_combined_xy_only_umap",
    "morph_pca_dir": WORKSPACE_ROOT / "685221" / "analysis" / "balanced_carveouts_120_combined_morphology_only",
    "morph_umap_dir": WORKSPACE_ROOT / "685221" / "analysis" / "balanced_carveouts_120_combined_morphology_only_umap",
}
