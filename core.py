"""Données, import Excel, projets et annotations pour Motor OP Studio."""
from __future__ import annotations

import io
import json
import math
import zipfile
from bisect import bisect_left
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from openpyxl import load_workbook

SHEET_NAME = "Characteristics Nom OP"
PROJECT_VERSION = 1  # Les projets .mop V1 / V1.1 restent compatibles.

# Ordre des colonnes Excel : B, C, D, E (RPM), F.
# Couleurs calquées sur la référence : courant rouge, couple bleu, puissance jaune, rendement vert.
METRICS = OrderedDict([
    ("current", {"name": "Phase current [Arms]", "axis_title": "Current [Arms]", "unit": "Arms", "col": 2, "color": "#C56649"}),
    ("torque", {"name": "Torque [Nm]", "axis_title": "Torque [Nm]", "unit": "Nm", "col": 3, "color": "#1780A7"}),
    ("power", {"name": "Power [kW]", "axis_title": "Power [kW]", "unit": "kW", "col": 4, "color": "#DEA92D"}),
    ("efficiency", {"name": "Efficiency", "axis_title": "Efficiency [%]", "unit": "%", "col": 6, "color": "#79A94B"}),
])

DEFAULT_SETTINGS = {
    "theme": "Clair", "markers": False, "line_width": 2.5,
    "visible": {key: True for key in METRICS},
    "efficiency_mode": "Auto",
    "chart_title": "", "chart_height": 440,
}


def normalize_settings(settings: Any) -> dict:
    """Lecture tolérante : ajoute les nouveaux paramètres aux anciens .mop."""
    if not isinstance(settings, dict):
        settings = {}
    widths = to_number(settings.get("line_width"))
    visible = settings.get("visible", {})
    if not isinstance(visible, dict):
        visible = {}
    mode = settings.get("efficiency_mode", "Auto")
    return {
        "theme": "Sombre" if settings.get("theme") == "Sombre" else "Clair",
        "markers": bool(settings.get("markers", DEFAULT_SETTINGS["markers"])),
        "line_width": min(6., max(1., widths if widths is not None else 2.5)),
        "visible": {key: bool(visible.get(key, True)) for key in METRICS},
        "efficiency_mode": mode if mode in ("Auto", "Valeurs en %", "Valeurs 0–1") else "Auto",
        "chart_title": str(settings.get("chart_title") or "").strip()[:160],
        "chart_height": max(330, min(750, int(to_number(settings.get("chart_height")) or 440))),
    }


def to_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, str):
        value = value.strip().replace("\u00a0", "").replace(" ", "").replace(",", ".")
        if not value:
            return None
    try:
        f = float(value)
        return f if math.isfinite(f) else None
    except (ValueError, TypeError, OverflowError):
        return None


def parse_excel(raw_excel: bytes) -> tuple[dict, dict]:
    """Recherche automatiquement la feuille. B,C,D,E,F depuis ligne 3 ; arrêt strict à B vide."""
    try:
        wb = load_workbook(io.BytesIO(raw_excel), read_only=True, data_only=True)
    except Exception as exc:
        raise ValueError("Le fichier n'est pas un classeur Excel .xlsx/.xlsm valide.") from exc
    try:
        if SHEET_NAME not in wb.sheetnames:
            names = ", ".join(wb.sheetnames[:12])
            raise ValueError(f"Feuille « {SHEET_NAME} » introuvable. Feuilles présentes : {names}")
        ws = wb[SHEET_NAME]
        data = {"rpm": [], **{key: [] for key in METRICS}}
        stats = {"rows_seen": 0, "rows_kept": 0, "bad_speed": 0,
                 "invalid_values": {key: 0 for key in METRICS}, "stopped_at": None}
        for excel_row, values in enumerate(
            ws.iter_rows(min_row=3, min_col=2, max_col=6, values_only=True), start=3
        ):
            b, c, d, e, f = values
            if b is None or (isinstance(b, str) and not b.strip()):
                stats["stopped_at"] = excel_row
                break
            stats["rows_seen"] += 1
            rpm = to_number(e)
            if rpm is None:
                stats["bad_speed"] += 1
                continue
            data["rpm"].append(rpm)
            raw = {"current": b, "torque": c, "power": d, "efficiency": f}
            for metric, value in raw.items():
                numeric = to_number(value)
                if numeric is None:
                    stats["invalid_values"][metric] += 1
                data[metric].append(numeric)
            stats["rows_kept"] += 1
        if not data["rpm"]:
            raise ValueError("Aucune ligne exploitable à partir de la ligne 3 (vérifier B et E).")
        return data, stats
    finally:
        wb.close()


def xy_for(data: dict, metric: str) -> tuple[list[float], list[float]]:
    xy = [(x, y) for x, y in zip(data["rpm"], data[metric]) if y is not None]
    xy.sort(key=lambda pair: pair[0])
    return [p[0] for p in xy], [p[1] for p in xy]


def interp(data: dict, metric: str, rpm: float) -> float | None:
    """Interpolation linéaire sans extrapolation, régime RPM dupliqué pris en charge."""
    xs, ys = xy_for(data, metric)
    if not xs or rpm < xs[0] or rpm > xs[-1]:
        return None
    j = bisect_left(xs, rpm)
    if j < len(xs) and xs[j] == rpm:
        return ys[j]
    if j == 0 or j >= len(xs) or xs[j] == xs[j - 1]:
        return None
    t = (rpm - xs[j - 1]) / (xs[j] - xs[j - 1])
    return ys[j - 1] + t * (ys[j] - ys[j - 1])


def efficiency_factor(data: dict, settings: dict) -> float:
    """Convertit les fractions Excel (0.95) en pourcentage (95) uniquement à l'affichage."""
    mode = settings.get("efficiency_mode", "Auto")
    if mode == "Valeurs 0–1":
        return 100.
    if mode == "Valeurs en %":
        return 1.
    values = [v for v in data.get("efficiency", []) if v is not None]
    # Évite de considérer une valeur 0..1 comme une fraction si l'ensemble contient des % > 1.
    return 100. if values and min(values) >= 0 and max(values) <= 1.05 else 1.


def display_factor(metric: str, data: dict, settings: dict) -> float:
    return efficiency_factor(data, settings) if metric == "efficiency" else 1.


def visible_metrics(settings: dict) -> list[str]:
    return [k for k in METRICS if settings.get("visible", {}).get(k, True)]


def nice_range(values: list[float], percent: bool = False) -> tuple[float, float, float]:
    """Limites en 0..max et graduation bien espacée, propres à chaque grandeur."""
    finite = [v for v in values if v is not None and math.isfinite(v)]
    if not finite:
        return (0., 100., 20.) if percent else (0., 1., .2)
    low, high = min(finite), max(finite)
    if percent and low >= 0 and high <= 100:
        return 0., 100., 20.
    low_hint = min(0., low) if low >= 0 else low * 1.05
    high_hint = high * 1.06 if high > 0 else max(0.1, abs(low) * .1)
    span = max(1e-9, high_hint - low_hint)
    rough = span / 5
    order = 10 ** math.floor(math.log10(rough))
    step = next((m * order for m in (1, 2, 2.5, 5, 10) if m * order >= rough), 10 * order)
    lower = min(0., math.floor(low_hint / step) * step)
    upper = max(step, math.ceil(high_hint / step) * step)
    return float(round(lower, 10)), float(round(upper, 10)), float(step)


def axis_ranges(data: dict, annotations: list[dict], settings: dict) -> dict:
    """Axes indépendants. Inclut les annotations pour éviter de les couper."""
    result = {}
    for metric in METRICS:
        factor = display_factor(metric, data, settings)
        values = [v * factor for v in data[metric] if v is not None]
        for ann in annotations:
            if ann["metric"] != metric:
                continue
            coords = [ann["y"]] if ann["type"] == "point" else [ann["y0"], ann["y1"]]
            values.extend(c * factor for c in coords)
        result[metric] = nice_range(values, percent=(metric == "efficiency"))
    return result


def new_point(metric: str, x: float, y: float, label: str = "", color: str = "#EF4444") -> dict:
    return dict(id=uuid4().hex[:12], type="point", metric=metric,
                x=float(x), y=float(y), label=label[:100], color=color)


def new_segment(metric: str, x0: float, y0: float, x1: float, y1: float,
                label: str = "", color: str = "#EF4444") -> dict:
    return dict(id=uuid4().hex[:12], type="segment", metric=metric,
                x0=float(x0), y0=float(y0), x1=float(x1), y1=float(y1),
                label=label[:100], color=color)


def validated_annotations(items: Any) -> list[dict]:
    if not isinstance(items, list) or len(items) > 100000:
        raise ValueError("Annotations de projet non valides.")
    clean = []
    for a in items:
        if not isinstance(a, dict) or a.get("metric") not in METRICS or a.get("type") not in {"point", "segment"}:
            raise ValueError("Une annotation du projet est invalide.")
        fields = ["x", "y"] if a["type"] == "point" else ["x0", "y0", "x1", "y1"]
        coordinates = {f: to_number(a.get(f)) for f in fields}
        if any(v is None for v in coordinates.values()):
            raise ValueError("Coordonnées d'annotation non numériques.")
        color = str(a.get("color", "#EF4444"))
        if len(color) != 7 or not color.startswith("#") or any(c not in "0123456789abcdefABCDEF" for c in color[1:]):
            color = "#EF4444"
        clean.append(dict(id=str(a.get("id", uuid4().hex[:12]))[:50],
                          type=a["type"], metric=a["metric"],
                          label=str(a.get("label", ""))[:100], color=color, **coordinates))
    return clean


def make_project(excel: bytes, filename: str, annotations: list[dict], settings: dict) -> bytes:
    metadata = {
        "version": PROJECT_VERSION,
        "format": "Motor OP Studio",
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "excel_filename": filename,
        "annotations": validated_annotations(annotations),
        "settings": normalize_settings(settings),
    }
    out = io.BytesIO()
    with zipfile.ZipFile(out, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        z.writestr("project.json", json.dumps(metadata, ensure_ascii=False, indent=2))
        z.writestr("source.xlsx", excel)
    return out.getvalue()


def read_project(project_bytes: bytes) -> tuple[bytes, dict]:
    try:
        with zipfile.ZipFile(io.BytesIO(project_bytes)) as z:
            names = set(z.namelist())
            if {"project.json", "source.xlsx"} - names:
                raise ValueError("Archive projet incomplète.")
            if z.getinfo("source.xlsx").file_size > 512_000_000 or z.getinfo("project.json").file_size > 10_000_000:
                raise ValueError("Projet trop volumineux.")
            meta = json.loads(z.read("project.json").decode("utf-8"))
            excel = z.read("source.xlsx")
    except (zipfile.BadZipFile, UnicodeDecodeError, json.JSONDecodeError, KeyError) as exc:
        raise ValueError("Le projet .mop ne peut pas être lu.") from exc
    if meta.get("version") != PROJECT_VERSION or not isinstance(meta.get("settings", {}), dict):
        raise ValueError("Version ou structure de projet non prise en charge.")
    meta["annotations"] = validated_annotations(meta.get("annotations", []))
    meta["settings"] = normalize_settings(meta.get("settings", {}))
    return excel, meta
