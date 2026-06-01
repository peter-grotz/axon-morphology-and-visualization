#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import nrrd
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from skimage.measure import marching_cubes
import vtk


REPO_ROOT = Path(__file__).resolve().parents[1]
ROOT_MESH_DEFAULT = REPO_ROOT / "assets" / "ccf_meshes" / "annotation_10_nrrd_root_ds4.vtp"
ANNOTATION_25_DEFAULT = "/Users/peter.grotz/Desktop/scratch/swc_inputs/annotation/ccf_2017/annotation_25.nrrd"
GRACILE_LABEL_ID = 1039


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render sagittal, coronal, and horizontal glass CCF views with an SWC and highlighted CCF region."
    )
    parser.add_argument("--root-mesh", default=str(ROOT_MESH_DEFAULT))
    parser.add_argument("--swc-path", required=True)
    parser.add_argument("--annotation-25", default=ANNOTATION_25_DEFAULT)
    parser.add_argument("--region-label", type=int, default=GRACILE_LABEL_ID)
    parser.add_argument("--region-name", default="gracile_nucleus")
    parser.add_argument("--region-cache", default=None)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--prefix", default=None)
    parser.add_argument("--output-width", type=int, default=3200)
    parser.add_argument("--output-height", type=int, default=2200)
    parser.add_argument("--bar-mm", type=float, default=2.0)
    parser.add_argument("--background", choices=["transparent", "white"], default="white")
    parser.add_argument("--hemisphere", choices=["full", "closest"], default="full")
    parser.add_argument("--swc-color", nargs=3, type=float, default=[0.92, 0.22, 0.18])
    parser.add_argument("--swc-opacity", type=float, default=0.98)
    parser.add_argument("--swc-radius", type=float, default=16.0)
    parser.add_argument("--swc-mode", choices=["tubes", "lines"], default="tubes")
    parser.add_argument("--swc-stride", type=int, default=1)
    parser.add_argument("--region-color", nargs=3, type=float, default=[1.0, 0.45, 0.72])
    parser.add_argument("--region-opacity", type=float, default=0.42)
    parser.add_argument("--views", nargs="+", choices=["sagittal", "coronal", "horizontal"], default=["sagittal", "coronal", "horizontal"])
    return parser.parse_args()


def load_polydata(path: str | Path) -> vtk.vtkPolyData:
    reader = vtk.vtkXMLPolyDataReader()
    reader.SetFileName(str(path))
    reader.Update()
    poly = vtk.vtkPolyData()
    poly.ShallowCopy(reader.GetOutput())
    return poly


def write_polydata(poly: vtk.vtkPolyData, path: str | Path) -> None:
    writer = vtk.vtkXMLPolyDataWriter()
    writer.SetFileName(str(path))
    writer.SetInputData(poly)
    writer.Write()


def numpy_mesh_to_polydata(vertices: np.ndarray, faces: np.ndarray) -> vtk.vtkPolyData:
    points = vtk.vtkPoints()
    for x, y, z in vertices:
        points.InsertNextPoint(float(x), float(y), float(z))

    triangles = vtk.vtkCellArray()
    for face in faces:
        tri = vtk.vtkTriangle()
        tri.GetPointIds().SetId(0, int(face[0]))
        tri.GetPointIds().SetId(1, int(face[1]))
        tri.GetPointIds().SetId(2, int(face[2]))
        triangles.InsertNextCell(tri)

    poly = vtk.vtkPolyData()
    poly.SetPoints(points)
    poly.SetPolys(triangles)

    normals = vtk.vtkPolyDataNormals()
    normals.SetInputData(poly)
    normals.ConsistencyOn()
    normals.SplittingOff()
    normals.Update()

    smooth = vtk.vtkWindowedSincPolyDataFilter()
    smooth.SetInputConnection(normals.GetOutputPort())
    smooth.SetNumberOfIterations(18)
    smooth.SetPassBand(0.08)
    smooth.BoundarySmoothingOff()
    smooth.FeatureEdgeSmoothingOff()
    smooth.NormalizeCoordinatesOn()
    smooth.Update()

    out = vtk.vtkPolyData()
    out.ShallowCopy(smooth.GetOutput())
    return out


def build_region_mesh(annotation_path: Path, label_id: int, cache_path: Path) -> vtk.vtkPolyData:
    if cache_path.exists():
        return load_polydata(cache_path)

    data, header = nrrd.read(str(annotation_path))
    coords = np.argwhere(data == label_id)
    if len(coords) == 0:
        raise ValueError(f"Label {label_id} was not found in {annotation_path}")

    pad = 2
    min_idx = np.maximum(coords.min(axis=0) - pad, 0)
    max_idx = np.minimum(coords.max(axis=0) + pad + 1, data.shape)
    crop = data[min_idx[0] : max_idx[0], min_idx[1] : max_idx[1], min_idx[2] : max_idx[2]]
    mask = (crop == label_id).astype(np.uint8)

    spacing = np.asarray(header.get("space directions", np.eye(3) * 25.0), dtype=float)
    spacing_um = np.linalg.norm(spacing, axis=1)
    vertices, faces, _, _ = marching_cubes(mask, level=0.5, spacing=tuple(spacing_um))
    vertices += min_idx * spacing_um

    poly = numpy_mesh_to_polydata(vertices, faces)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    write_polydata(poly, cache_path)
    return poly


def scale_polydata(polydata: vtk.vtkPolyData, center_xyz: tuple[float, float, float], scale_xyz: tuple[float, float, float]) -> vtk.vtkPolyData:
    cx, cy, cz = center_xyz
    sx, sy, sz = scale_xyz
    transform = vtk.vtkTransform()
    transform.PostMultiply()
    transform.Translate(cx, cy, cz)
    transform.Scale(sx, sy, sz)
    transform.Translate(-cx, -cy, -cz)
    tf = vtk.vtkTransformPolyDataFilter()
    tf.SetInputData(polydata)
    tf.SetTransform(transform)
    tf.Update()
    out = vtk.vtkPolyData()
    out.ShallowCopy(tf.GetOutput())
    return out


def clip_closest_half(polydata: vtk.vtkPolyData, center_xyz: tuple[float, float, float], view: str) -> vtk.vtkPolyData:
    normals = {
        "sagittal": (0.0, 0.0, 1.0),
        "coronal": (1.0, 0.0, 0.0),
        "horizontal": (0.0, -1.0, 0.0),
    }
    plane = vtk.vtkPlane()
    plane.SetOrigin(center_xyz)
    plane.SetNormal(*normals[view])
    clip = vtk.vtkClipPolyData()
    clip.SetInputData(polydata)
    clip.SetClipFunction(plane)
    clip.InsideOutOn()
    clip.GenerateClippedOutputOff()
    clip.Update()
    out = vtk.vtkPolyData()
    out.ShallowCopy(clip.GetOutput())
    return out


def make_mapper(polydata: vtk.vtkPolyData) -> vtk.vtkPolyDataMapper:
    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputData(polydata)
    mapper.ScalarVisibilityOff()
    return mapper


def make_glass_actor(polydata: vtk.vtkPolyData, color: tuple[float, float, float], opacity: float, specular: float = 1.0) -> vtk.vtkActor:
    actor = vtk.vtkActor()
    actor.SetMapper(make_mapper(polydata))
    prop = actor.GetProperty()
    prop.SetInterpolationToPhong()
    prop.SetColor(*color)
    prop.SetOpacity(opacity)
    prop.SetAmbient(0.01)
    prop.SetDiffuse(0.34)
    prop.SetSpecular(specular)
    prop.SetSpecularPower(30.0)
    return actor


def swc_segments(path: Path) -> list[tuple[tuple[float, float, float], tuple[float, float, float]]]:
    nodes: dict[int, tuple[float, float, float, int]] = {}
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 7:
                continue
            node_id = int(parts[0])
            nodes[node_id] = (float(parts[2]), float(parts[3]), float(parts[4]), int(parts[6]))

    segments = []
    for _, (x, y, z, parent_id) in nodes.items():
        if parent_id < 0 or parent_id not in nodes:
            continue
        px, py, pz, _ = nodes[parent_id]
        segments.append(((px, py, pz), (x, y, z)))
    return segments


def make_swc_actor(path: Path, color: tuple[float, float, float], opacity: float, tube_radius: float, mode: str, stride: int) -> vtk.vtkActor:
    vtk_points = vtk.vtkPoints()
    lines = vtk.vtkCellArray()
    next_id = 0
    segments = swc_segments(path)
    if stride > 1:
        segments = segments[::stride]

    for p0, p1 in segments:
        line = vtk.vtkLine()
        vtk_points.InsertNextPoint(*p0)
        line.GetPointIds().SetId(0, next_id)
        next_id += 1
        vtk_points.InsertNextPoint(*p1)
        line.GetPointIds().SetId(1, next_id)
        next_id += 1
        lines.InsertNextCell(line)

    poly = vtk.vtkPolyData()
    poly.SetPoints(vtk_points)
    poly.SetLines(lines)
    mapper = vtk.vtkPolyDataMapper()
    if mode == "tubes":
        tube = vtk.vtkTubeFilter()
        tube.SetInputData(poly)
        tube.SetRadius(tube_radius)
        tube.SetNumberOfSides(14)
        tube.CappingOn()
        tube.Update()
        mapper.SetInputConnection(tube.GetOutputPort())
    else:
        mapper.SetInputData(poly)
    mapper.ScalarVisibilityOff()

    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
    prop = actor.GetProperty()
    prop.SetColor(*color)
    prop.SetOpacity(opacity)
    if mode == "tubes":
        prop.SetInterpolationToPhong()
        prop.SetAmbient(0.18)
        prop.SetDiffuse(0.72)
        prop.SetSpecular(0.38)
        prop.SetSpecularPower(24.0)
    else:
        prop.LightingOff()
        prop.SetLineWidth(2.0)
        prop.RenderLinesAsTubesOn()
    return actor


def add_lights(renderer: vtk.vtkRenderer, center: tuple[float, float, float], spans: tuple[float, float, float]) -> None:
    x_span, y_span, z_span = spans
    for position, intensity in [
        ((center[0] - 1.45 * x_span, center[1] - 0.62 * y_span, center[2] + 3.15 * z_span), 2.2),
        ((center[0] + 1.20 * x_span, center[1] - 0.20 * y_span, center[2] - 2.40 * z_span), 0.65),
    ]:
        light = vtk.vtkLight()
        light.SetLightTypeToSceneLight()
        light.SetPosition(*position)
        light.SetFocalPoint(*center)
        light.SetColor(1.0, 1.0, 1.0)
        light.SetIntensity(intensity)
        renderer.AddLight(light)


def camera_for_view(camera: vtk.vtkCamera, view: str, center: tuple[float, float, float], bounds: tuple[float, ...], width: int, height: int) -> None:
    x_span = bounds[1] - bounds[0]
    y_span = bounds[3] - bounds[2]
    z_span = bounds[5] - bounds[4]
    max_span = max(x_span, y_span, z_span)
    if view == "sagittal":
        camera.SetPosition(center[0] - 0.40 * x_span, center[1] - 0.14 * y_span, bounds[5] + 3.15 * z_span)
        camera.SetViewUp(0.0, -1.0, 0.0)
        fit_a = 0.58 * y_span
        fit_b = 0.58 * x_span / (width / height)
    elif view == "coronal":
        camera.SetPosition(bounds[1] + 2.75 * x_span, center[1] - 0.12 * y_span, center[2] + 0.05 * z_span)
        camera.SetViewUp(0.0, -1.0, 0.0)
        fit_a = 0.58 * y_span
        fit_b = 0.58 * z_span / (width / height)
    else:
        camera.SetPosition(center[0] - 0.12 * x_span, bounds[2] - 2.90 * y_span, center[2] + 0.10 * z_span)
        camera.SetViewUp(1.0, 0.0, 0.0)
        fit_a = 0.58 * x_span
        fit_b = 0.58 * z_span / (width / height)

    camera.SetFocalPoint(*center)
    camera.ParallelProjectionOn()
    camera.SetParallelScale(max(fit_a, fit_b))
    camera.SetClippingRange(100.0, 10.0 * max_span)


def write_png(render_window: vtk.vtkRenderWindow, path: Path) -> None:
    window_to_image = vtk.vtkWindowToImageFilter()
    window_to_image.SetInput(render_window)
    window_to_image.SetScale(1)
    window_to_image.SetInputBufferTypeToRGBA()
    window_to_image.ReadFrontBufferOff()
    window_to_image.Update()

    writer = vtk.vtkPNGWriter()
    writer.SetFileName(str(path))
    writer.SetInputConnection(window_to_image.GetOutputPort())
    writer.Write()


def load_font(size: int) -> ImageFont.ImageFont:
    for path in [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/SFNS.ttf",
    ]:
        try:
            return ImageFont.truetype(path, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def add_scalebar(path: Path, bar_mm: float, pixels_per_um: float, background: str) -> None:
    image = Image.open(path).convert("RGBA")
    if background == "white":
        base = Image.new("RGBA", image.size, (255, 255, 255, 255))
        image = Image.alpha_composite(base, image)
    draw = ImageDraw.Draw(image)
    margin_px = 64
    bar_height_px = 14
    label_gap_px = 28
    label_font_size = 72
    bar_width_px = max(1, int(round((bar_mm * 1000.0) * pixels_per_um)))
    x0 = margin_px
    x1 = x0 + bar_width_px
    y1 = image.height - margin_px
    y0 = y1 - bar_height_px
    draw.rectangle([x0, y0, x1, y1], fill=(0, 0, 0, 255))
    label = f"{bar_mm:g} mm"
    font = load_font(label_font_size)
    bbox = draw.textbbox((0, 0), label, font=font)
    draw.text((x0, y0 - (bbox[3] - bbox[1]) - label_gap_px), label, fill=(0, 0, 0, 255), font=font)
    image.save(path)


def render_view(args: argparse.Namespace, view: str, root_poly: vtk.vtkPolyData, region_poly: vtk.vtkPolyData, output_path: Path) -> None:
    view_root_poly = root_poly
    bounds = view_root_poly.GetBounds()
    center = (0.5 * (bounds[0] + bounds[1]), 0.5 * (bounds[2] + bounds[3]), 0.5 * (bounds[4] + bounds[5]))
    if args.hemisphere == "closest":
        view_root_poly = clip_closest_half(root_poly, center, view)
        bounds = view_root_poly.GetBounds()
        center = (0.5 * (bounds[0] + bounds[1]), 0.5 * (bounds[2] + bounds[3]), 0.5 * (bounds[4] + bounds[5]))

    x_span = bounds[1] - bounds[0]
    y_span = bounds[3] - bounds[2]
    z_span = bounds[5] - bounds[4]

    renderer = vtk.vtkRenderer()
    renderer.SetBackground(1.0, 1.0, 1.0)
    renderer.AutomaticLightCreationOff()

    renderer.AddActor(make_glass_actor(scale_polydata(view_root_poly, center, (1.0018, 1.0018, 1.0018)), (0.97, 0.98, 0.99), 0.08))
    renderer.AddActor(make_glass_actor(view_root_poly, (0.94, 0.96, 0.985), 0.13))
    renderer.AddActor(make_glass_actor(scale_polydata(view_root_poly, center, (0.9985, 0.9985, 0.9985)), (1.0, 1.0, 1.0), 0.05))
    renderer.AddActor(make_glass_actor(region_poly, tuple(args.region_color), args.region_opacity, specular=0.8))
    renderer.AddActor(make_swc_actor(Path(args.swc_path), tuple(args.swc_color), args.swc_opacity, args.swc_radius, args.swc_mode, max(1, args.swc_stride)))
    add_lights(renderer, center, (x_span, y_span, z_span))

    render_window = vtk.vtkRenderWindow()
    render_window.SetOffScreenRendering(1)
    render_window.AddRenderer(renderer)
    render_window.SetSize(args.output_width, args.output_height)
    render_window.SetAlphaBitPlanes(1)
    render_window.SetMultiSamples(8)

    camera = renderer.GetActiveCamera()
    camera_for_view(camera, view, center, bounds, args.output_width, args.output_height)
    render_window.Render()
    renderer.ResetCameraClippingRange()
    render_window.Render()

    write_png(render_window, output_path)
    pixels_per_um = args.output_height / (2.0 * camera.GetParallelScale())
    add_scalebar(output_path, args.bar_mm, pixels_per_um, args.background)
    print(output_path)
    print(f"{view}: parallel_scale_um={camera.GetParallelScale():.3f} pixels_per_um={pixels_per_um:.6f}")


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = args.prefix or Path(args.swc_path).stem

    bundled_region = REPO_ROOT / "assets" / "ccf_meshes" / f"{args.region_name}_{args.region_label}_25um.vtp"
    region_cache = Path(args.region_cache) if args.region_cache else bundled_region
    root_poly = load_polydata(args.root_mesh)
    region_poly = build_region_mesh(Path(args.annotation_25), args.region_label, region_cache)

    for view in args.views:
        output_path = output_dir / f"{prefix}_ccf_glass_{view}_with_{args.region_name}.png"
        render_view(args, view, root_poly, region_poly, output_path)


if __name__ == "__main__":
    main()
