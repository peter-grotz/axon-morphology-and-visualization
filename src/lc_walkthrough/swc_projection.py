from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
import numpy as np


AP = 0
DV = 1
ML = 2

DEFAULT_CCF_EXTENT_UM = (13200.0, 8000.0, 11400.0)

TYPE_STYLES = {
    2: {"label": "axon", "color": "#d81b60", "linewidth": 0.55, "alpha": 0.78},
    3: {"label": "dendrite", "color": "#00897b", "linewidth": 0.75, "alpha": 0.9},
}
DEFAULT_STYLE = {"label": "other", "color": "#616161", "linewidth": 0.45, "alpha": 0.55}


@dataclass(frozen=True)
class ProjectionView:
    name: str
    title: str
    axes: tuple[int, int]
    axis_labels: tuple[str, str]
    limits: tuple[tuple[float, float], tuple[float, float]]
    invert_y: bool


def read_swc(path: Path) -> np.ndarray:
    data = np.loadtxt(path, comments="#")
    if data.ndim != 2 or data.shape[1] < 7:
        raise ValueError(f"Expected an SWC table with at least 7 columns: {path}")
    return data[:, :7]


def ccf_extent_from_nifti(path: Path) -> tuple[float, float, float]:
    try:
        import nibabel as nib
    except ImportError as exc:
        raise RuntimeError("Install nibabel to derive CCF extents from a NIfTI header.") from exc

    image = nib.load(str(path))
    shape = image.shape[:3]
    zooms_mm = image.header.get_zooms()[:3]
    extents_um = tuple(float(size * zoom_mm * 1000.0) for size, zoom_mm in zip(shape, zooms_mm))
    if len(extents_um) != 3:
        raise ValueError(f"Expected a 3D annotation image: {path}")
    return extents_um


def build_segments(data: np.ndarray) -> dict[int, np.ndarray]:
    node_ids = data[:, 0].astype(int)
    parents = data[:, 6].astype(int)
    id_to_row = {node_id: row for row, node_id in enumerate(node_ids)}
    grouped: dict[int, list[np.ndarray]] = {}

    for row, parent_id in enumerate(parents):
        if parent_id < 0 or parent_id not in id_to_row:
            continue
        parent_row = id_to_row[parent_id]
        swc_type = int(data[row, 1])
        grouped.setdefault(swc_type, []).append(data[[parent_row, row], 2:5])

    return {swc_type: np.asarray(parts) for swc_type, parts in grouped.items()}


def soma_xyz(data: np.ndarray) -> np.ndarray:
    root_rows = np.flatnonzero(data[:, 6] < 0)
    return data[root_rows[0] if len(root_rows) else 0, 2:5]


def projection_views(extent_um: tuple[float, float, float]) -> list[ProjectionView]:
    ap_extent, dv_extent, ml_extent = extent_um
    return [
        ProjectionView(
            name="coronal",
            title="Coronal projection",
            axes=(ML, DV),
            axis_labels=("ML (um)", "DV (um)"),
            limits=((0.0, ml_extent), (0.0, dv_extent)),
            invert_y=True,
        ),
        ProjectionView(
            name="sagittal",
            title="Sagittal projection",
            axes=(AP, DV),
            axis_labels=("AP (um)", "DV (um)"),
            limits=((0.0, ap_extent), (0.0, dv_extent)),
            invert_y=True,
        ),
        ProjectionView(
            name="horizontal",
            title="Horizontal projection",
            axes=(ML, AP),
            axis_labels=("ML (um)", "AP (um)"),
            limits=((0.0, ml_extent), (0.0, ap_extent)),
            invert_y=True,
        ),
    ]


def tight_limits(data: np.ndarray, axes: tuple[int, int], padding_um: float) -> tuple[tuple[float, float], tuple[float, float]]:
    points = data[:, 2:5]
    x = points[:, axes[0]]
    y = points[:, axes[1]]
    return (
        (float(x.min() - padding_um), float(x.max() + padding_um)),
        (float(y.min() - padding_um), float(y.max() + padding_um)),
    )


def add_view(
    ax: plt.Axes,
    grouped_segments: dict[int, np.ndarray],
    soma: np.ndarray,
    view: ProjectionView,
    frame: str,
    data: np.ndarray,
    padding_um: float,
) -> None:
    ax.set_facecolor("#fafafa")
    ax.grid(color="#dddddd", linewidth=0.5, alpha=0.7)
    ax.set_axisbelow(True)

    for swc_type, segments in grouped_segments.items():
        style = TYPE_STYLES.get(swc_type, DEFAULT_STYLE)
        collection = LineCollection(
            segments[:, :, view.axes],
            colors=style["color"],
            linewidths=style["linewidth"],
            alpha=style["alpha"],
            capstyle="round",
            joinstyle="round",
            label=style["label"] if swc_type in TYPE_STYLES else f"type {swc_type}",
        )
        ax.add_collection(collection)

    ax.scatter(
        [soma[view.axes[0]]],
        [soma[view.axes[1]]],
        s=28,
        c="#111111",
        edgecolors="white",
        linewidths=0.5,
        zorder=10,
        label="soma",
    )

    xlim, ylim = view.limits if frame == "full" else tight_limits(data, view.axes, padding_um)
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    if view.invert_y:
        ax.invert_yaxis()
    ax.set_aspect("equal", adjustable="box")
    ax.set_title(view.title, fontsize=12, weight="bold")
    ax.set_xlabel(view.axis_labels[0])
    ax.set_ylabel(view.axis_labels[1])


def write_summary(path: Path, source_swc: Path, data: np.ndarray, soma: np.ndarray, extent_um: tuple[float, float, float]) -> None:
    mins = data[:, 2:5].min(axis=0)
    maxs = data[:, 2:5].max(axis=0)
    type_counts = {
        int(swc_type): int(count)
        for swc_type, count in zip(*np.unique(data[:, 1].astype(int), return_counts=True))
    }
    lines = [
        f"source_swc: {source_swc}",
        f"node_count: {len(data)}",
        f"soma_xyz_um: {soma.tolist()}",
        f"xyz_min_um: {mins.tolist()}",
        f"xyz_max_um: {maxs.tolist()}",
        f"type_counts: {type_counts}",
        f"ccf_extent_ap_dv_ml_um: {list(extent_um)}",
        "coordinate_assumption: SWC x/y/z are Allen CCF AP/DV/ML in microns.",
    ]
    path.write_text("\n".join(lines) + "\n")


def write_projection_set(
    swc_path: Path,
    out_dir: Path,
    prefix: str | None = None,
    frame: str = "full",
    padding_um: float = 250.0,
    ccf_extent_um: tuple[float, float, float] = DEFAULT_CCF_EXTENT_UM,
) -> list[Path]:
    data = read_swc(swc_path)
    grouped_segments = build_segments(data)
    soma = soma_xyz(data)
    views = projection_views(ccf_extent_um)
    output_prefix = prefix or swc_path.stem

    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    fig, axes = plt.subplots(1, 3, figsize=(18, 7.2), constrained_layout=True)
    for ax, view in zip(axes, views):
        add_view(ax, grouped_segments, soma, view, frame=frame, data=data, padding_um=padding_um)
    fig.suptitle(f"{swc_path.name} in CCF space", fontsize=15, weight="bold")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=3, frameon=False)
    combined_path = out_dir / f"{output_prefix}_ccf_three_view_projection.png"
    fig.savefig(combined_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    written.append(combined_path)

    for view in views:
        fig, ax = plt.subplots(figsize=(7.5, 7.0), constrained_layout=True)
        add_view(ax, grouped_segments, soma, view, frame=frame, data=data, padding_um=padding_um)
        ax.legend(loc="upper right", frameon=True, framealpha=0.9)
        path = out_dir / f"{output_prefix}_ccf_{view.name}_projection.png"
        fig.savefig(path, dpi=300, bbox_inches="tight")
        plt.close(fig)
        written.append(path)

    summary_path = out_dir / f"{output_prefix}_ccf_projection_summary.txt"
    write_summary(summary_path, swc_path, data, soma, ccf_extent_um)
    written.append(summary_path)

    return written


def parse_extent(values: Iterable[str] | None) -> tuple[float, float, float]:
    if values is None:
        return DEFAULT_CCF_EXTENT_UM
    parsed = tuple(float(value) for value in values)
    if len(parsed) != 3:
        raise ValueError("--ccf-extent-um expects AP DV ML values.")
    return parsed


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create coronal, sagittal, and horizontal CCF projections from an SWC.")
    parser.add_argument("swc", type=Path, help="Input SWC with x/y/z as AP/DV/ML CCF microns.")
    parser.add_argument("--out-dir", type=Path, default=Path("assets/ccf_projections"))
    parser.add_argument("--prefix", default=None)
    parser.add_argument("--frame", choices=["full", "tight"], default="full")
    parser.add_argument("--padding-um", type=float, default=250.0, help="Padding used when --frame tight.")
    parser.add_argument(
        "--ccf-extent-um",
        nargs=3,
        metavar=("AP", "DV", "ML"),
        default=None,
        help="CCF extents in microns. Defaults to Allen CCF 10 um annotation dimensions.",
    )
    parser.add_argument("--annotation-nifti", type=Path, default=None, help="Optional NIfTI annotation to derive extents.")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_arg_parser().parse_args(argv)
    ccf_extent_um = ccf_extent_from_nifti(args.annotation_nifti) if args.annotation_nifti else parse_extent(args.ccf_extent_um)
    for path in write_projection_set(
        args.swc,
        args.out_dir,
        prefix=args.prefix,
        frame=args.frame,
        padding_um=args.padding_um,
        ccf_extent_um=ccf_extent_um,
    ):
        print(path)


if __name__ == "__main__":
    main()
