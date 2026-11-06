"""Tracé combiné à quatre axes autonomes, interactif (Plotly) ou PNG (Matplotlib)."""
from __future__ import annotations

import io
import math
from html import escape

from core import METRICS, axis_ranges, display_factor, visible_metrics, xy_for

# Correspondance fixe des axes, même lorsqu'une courbe est masquée.
AXIS = {"torque": "y", "current": "y2", "power": "y3", "efficiency": "y4"}
AXIS_POS = {"torque": .17, "current": .83, "power": .065, "efficiency": .955}


def x_range(data: dict, annotations: list[dict]) -> tuple[float, float, float]:
    xs = list(data["rpm"])
    for ann in annotations:
        xs.extend([ann["x"]] if ann["type"] == "point" else [ann["x0"], ann["x1"]])
    if not xs:
        return 0, 1000, 200
    hi = max(xs)
    lo = min(0, min(xs) * 1.05)
    span = max(1, hi - lo)
    rough = span / 5
    order = 10 ** math.floor(math.log10(rough))
    step = next((m * order for m in (1, 2, 2.5, 5, 10) if m * order >= rough), 10 * order)
    return lo, max(hi + .025 * span, step), step


def build_combined(data: dict, annotations: list[dict], settings: dict,
                   edit_metric: str | None = None, pending: dict | None = None,
                   chart_height: int = 570):
    """Figure Plotly + mapping des indices de traces des mesures pour la sélection."""
    import plotly.graph_objects as go

    dark = settings.get("theme") == "Sombre"
    bg = "#101827" if dark else "#FFFFFF"
    fg = "#E6EAF0" if dark else "#243146"
    grid = "#344053" if dark else "#E5E8ED"
    ranges = axis_ranges(data, annotations, settings)
    selection_indices = {}
    fig = go.Figure()
    keys = visible_metrics(settings)
    for key in keys:
        item = METRICS[key]
        xs, ys = xy_for(data, key)
        factor = display_factor(key, data, settings)
        ys = [v * factor for v in ys]
        selection_indices[key] = len(fig.data)
        fig.add_trace(go.Scatter(
            x=xs, y=ys, name=item["name"], yaxis=AXIS[key],
            mode="lines+markers" if (settings.get("markers", False) or edit_metric == key) else "lines",
            marker=dict(size=6 if edit_metric == key else 4, color=item["color"]),
            line=dict(color=item["color"], width=settings.get("line_width", 2.5)),
            hovertemplate=(f"<b>{item['name']}</b><br>RPM : %{{x:,.0f}}<br>"
                           f"Valeur : %{{y:.3f}} {item['unit']}<extra></extra>"),
            selected=dict(marker=dict(opacity=1, size=9)),
            unselected=dict(marker=dict(opacity=0.9)),
        ))

    for ann in annotations:
        metric = ann["metric"]
        if metric not in keys:
            continue
        factor = display_factor(metric, data, settings)
        color = ann["color"]
        axis = AXIS[metric]
        if ann["type"] == "point":
            fig.add_trace(go.Scatter(
                x=[ann["x"]], y=[ann["y"] * factor], yaxis=axis,
                mode="markers", showlegend=False,
                marker=dict(color=color, size=12, symbol="diamond", line=dict(color=bg, width=1.4)),
                hovertemplate=f"Point : {ann['label'] or 'sans nom'}<br>RPM : %{{x:.1f}}<br>Y : %{{y:.3f}}<extra></extra>",
            ))
            label_x, label_y = ann["x"], ann["y"] * factor
        else:
            fig.add_trace(go.Scatter(
                x=[ann["x0"], ann["x1"]], y=[ann["y0"] * factor, ann["y1"] * factor],
                yaxis=axis, mode="lines+markers", showlegend=False,
                line=dict(color=color, width=3, dash="solid"), marker=dict(color=color, size=8),
                hovertemplate="Segment<br>RPM : %{x:.1f}<br>Y : %{y:.3f}<extra></extra>",
            ))
            label_x = (ann["x0"] + ann["x1"]) / 2
            label_y = (ann["y0"] + ann["y1"]) / 2 * factor
        if ann["label"]:
            fig.add_annotation(x=label_x, y=label_y, xref="x", yref=axis,
                               text=ann["label"], showarrow=False,
                               yshift=15, font=dict(color=color, size=11))

    if pending and pending["metric"] in keys:
        key = pending["metric"]
        fig.add_trace(go.Scatter(
            x=[pending["x"]], y=[pending["y"] * display_factor(key, data, settings)],
            yaxis=AXIS[key], mode="markers", showlegend=False,
            marker=dict(color="#E11D48", symbol="cross", size=16, line=dict(width=2)),
            name="Début de segment",
        ))

    xlo, xhi, xstep = x_range(data, annotations)
    fig.update_layout(
        paper_bgcolor=bg, plot_bgcolor=bg, font=dict(color=fg, size=12),
        height=chart_height, margin=dict(l=25, r=25, t=90, b=66),
        title=dict(text=escape(settings.get("chart_title") or "Motor characteristics"),
                   x=.5, xanchor="center", y=.985, yanchor="top",
                   font=dict(size=17, color=fg)),
        dragmode="select" if edit_metric else "zoom", hovermode="closest",
        showlegend=True, legend=dict(orientation="h", x=.5, xanchor="center", y=1.075,
                                     yanchor="bottom", font=dict(size=11)),
        xaxis=dict(domain=[.17, .83], range=[xlo, xhi], dtick=xstep,
                   title=dict(text="Speed [RPM]", font=dict(size=15)),
                   showgrid=True, gridcolor=grid, zeroline=False),
        uirevision="selection-axes",  # zoom is reset on project change via widget key
    )
    for key, item in METRICS.items():
        lower, upper, step = ranges[key]
        layout_key = "yaxis" if key == "torque" else "yaxis" + AXIS[key][1:]
        opts = dict(
            side="left" if key in {"power", "torque"} else "right",
            anchor="free", position=AXIS_POS[key],
            range=[lower, upper], dtick=step, fixedrange=False,
            title=dict(text=item["axis_title"], font=dict(color=item["color"], size=16), standoff=6),
            tickfont=dict(color=item["color"], size=12),
            tickcolor=item["color"], showline=True, linecolor=item["color"],
            zeroline=False, showgrid=(key == "torque"), gridcolor=grid,
            visible=key in keys,
        )
        if key != "torque":
            opts["overlaying"] = "y"
            opts["showgrid"] = False
        fig.update_layout(**{layout_key: opts})
    if not keys:
        fig.add_annotation(text="Sélectionnez au moins une courbe dans « Courbes visibles ».",
                           x=.5, y=.5, xref="paper", yref="paper", showarrow=False,
                           font=dict(color=fg, size=18))
    return fig, selection_indices


def render_png(data: dict, annotations: list[dict], settings: dict,
               metric: str | None = None, dpi: int = 180) -> bytes:
    """Export des courbes et annotations sur un SEUL graphique à 4 axes (ou une seule métrique)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import MultipleLocator

    dark = settings.get("theme") == "Sombre"
    bg = "#101827" if dark else "#FFFFFF"
    fg = "#E6EAF0" if dark else "#243146"
    grid = "#344053" if dark else "#E5E8ED"
    keys = [metric] if metric is not None else visible_metrics(settings)
    ranges = axis_ranges(data, annotations, settings)
    fig, torque_ax = plt.subplots(figsize=(15.0, 7.8), facecolor=bg)
    current_ax = torque_ax.twinx()
    power_ax = torque_ax.twinx()
    efficiency_ax = torque_ax.twinx()
    axs = {"torque": torque_ax, "current": current_ax, "power": power_ax, "efficiency": efficiency_ax}
    fig.subplots_adjust(left=.20, right=.80, top=.81, bottom=.15)
    for ax in axs.values():
        ax.patch.set_alpha(0)
        ax.tick_params(axis="y", length=4, width=1)
        ax.grid(False)
        ax.set_facecolor(bg)

    # Deux axes de chaque côté : jaune/bleu à gauche, orange/vert à droite.
    torque_ax.spines["right"].set_visible(False)
    current_ax.spines["left"].set_visible(False)
    power_ax.spines["right"].set_visible(False)
    power_ax.spines["left"].set_position(("axes", -.155))
    power_ax.yaxis.set_label_position("left")
    power_ax.yaxis.tick_left()
    efficiency_ax.spines["left"].set_visible(False)
    efficiency_ax.spines["right"].set_position(("axes", 1.155))

    handles = []
    for key, item in METRICS.items():
        ax = axs[key]
        if key not in keys:
            ax.yaxis.set_visible(False)
            ax.spines["left"].set_visible(False)
            ax.spines["right"].set_visible(False)
            continue
        ax.yaxis.set_visible(True)
        lo, hi, step = ranges[key]
        ax.set_ylim(lo, hi)
        ax.yaxis.set_major_locator(MultipleLocator(step))
        ax.set_ylabel(item["axis_title"], color=item["color"], fontsize=13, labelpad=12)
        ax.tick_params(axis="y", colors=item["color"], labelsize=11)
        spine_key = "left" if key in {"power", "torque"} else "right"
        ax.spines[spine_key].set_visible(True)
        ax.spines[spine_key].set_edgecolor(item["color"])
        factor = display_factor(key, data, settings)
        xs, ys = xy_for(data, key)
        (line,) = ax.plot(xs, [v * factor for v in ys], color=item["color"],
                          linewidth=settings.get("line_width", 2.5),
                          marker="o" if settings.get("markers", False) and len(xs) <= 600 else None,
                          markersize=3.1, label=item["name"], zorder=3)
        handles.append(line)
        for ann in annotations:
            if ann["metric"] != key:
                continue
            c = ann["color"]
            if ann["type"] == "point":
                ax.scatter(ann["x"], ann["y"] * factor, marker="D", s=60,
                           color=c, edgecolors=bg, linewidths=1, zorder=8)
                px, py = ann["x"], ann["y"] * factor
            else:
                ax.plot([ann["x0"], ann["x1"]],
                        [ann["y0"] * factor, ann["y1"] * factor],
                        color=c, linewidth=3, marker="o", markersize=5, zorder=7)
                px, py = (ann["x0"] + ann["x1"]) / 2, (ann["y0"] + ann["y1"]) / 2 * factor
            if ann["label"]:
                ax.annotate(ann["label"], (px, py), xytext=(5, 9), textcoords="offset points",
                            color=c, fontsize=9, fontweight="bold")

    xlo, xhi, step = x_range(data, annotations)
    torque_ax.set_xlim(xlo, xhi)
    torque_ax.xaxis.set_major_locator(MultipleLocator(step))
    torque_ax.set_xlabel("Speed [RPM]", fontsize=13, color=fg, labelpad=12)
    torque_ax.tick_params(axis="x", colors=fg, labelsize=11)
    torque_ax.spines["bottom"].set_color(grid)
    torque_ax.spines["top"].set_visible(False)
    torque_ax.grid(axis="both", color=grid, linewidth=.8, alpha=.9)
    fig.suptitle(settings.get("chart_title") or "Motor characteristics", color=fg,
                 fontsize=18, fontweight="bold", y=.985)
    if handles:
        fig.legend(handles, [h.get_label() for h in handles],
                   loc="upper center", bbox_to_anchor=(.5, .935), ncol=len(handles),
                   frameon=False, labelcolor=fg, fontsize=11)
    else:
        torque_ax.text(.5, .5, "Aucune courbe sélectionnée", color=fg,
                       ha="center", va="center", transform=torque_ax.transAxes)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, facecolor=bg, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()
