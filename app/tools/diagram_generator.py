"""Engineering Diagram and Schematic Generator for UrjaKavach.

Generates high-resolution process flow diagrams (PFD), piping schematics,
and equipment performance degradation curves using Matplotlib and PIL.
Outputs are saved to app/outputs/ as high-DPI PNGs for display and download.
"""

import os
import uuid
from typing import Any, Dict, List, Optional

import matplotlib
matplotlib.use("Agg")  # Non-interactive headless backend
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np

from app import config


def generate_engineering_diagram(
    topic: str,
    context: str = "",
    diagram_type: str = "auto",
    task_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Synthesize an authoritative engineering diagram or schematic."""
    if not task_id:
        task_id = str(uuid.uuid4())[:8]

    out_filename = f"diagram_{task_id}.png"
    out_path = os.path.join(config.OUTPUTS_DIR, out_filename)

    topic_lower = topic.lower()
    context_lower = context.lower()

    if any(k in topic_lower or k in context_lower for k in ["heat exchanger", "fouling", "tema", "e-101", "tube bundle"]):
        title = "Shell & Tube Heat Exchanger Process Schematic"
        _draw_heat_exchanger_schematic(out_path, title)
    elif any(k in topic_lower or k in context_lower for k in ["corrosion", "thickness", "api 570", "api 510", "degradation", "remaining life"]):
        title = "Piping Wall Thickness Degradation vs API 570 Retirement Limit"
        _draw_corrosion_degradation_chart(out_path, title)
    elif any(k in topic_lower or k in context_lower for k in ["column", "distillation", "c-101", "reboiler", "reflux", "tower"]):
        title = "Fractionation Column (CDU) Process Flow Diagram"
        _draw_distillation_column_pfd(out_path, title)
    else:
        title = f"Industrial Engineering Schematic: {topic[:35]}"
        _draw_pump_manifold_schematic(out_path, title)

    return {
        "ok": True,
        "title": title,
        "filename": out_filename,
        "download_url": f"/api/download/{out_filename}",
        "file_type": "png",
        "task_id": task_id,
    }


def _draw_heat_exchanger_schematic(out_path: str, title: str):
    """Draw a clean TEMA Shell & Tube Heat Exchanger schematic."""
    fig, ax = plt.subplots(figsize=(10, 5.5), dpi=180)
    fig.patch.set_facecolor("#1e1e1e")
    ax.set_facecolor("#252526")

    # Shell outer body
    shell = patches.FancyBboxPatch(
        (2.0, 1.5), 6.0, 3.0,
        boxstyle="round,pad=0.2,rounding_size=0.8",
        linewidth=2.5, edgecolor="#569cd6", facecolor="#2d2d30"
    )
    ax.add_patch(shell)

    # Tube bundle passes (multiple horizontal lines)
    for y in np.linspace(2.0, 4.0, 7):
        ax.plot([2.5, 7.5], [y, y], color="#dcdcaa", linewidth=2.0, linestyle="--")

    # Baffles
    for x in [3.5, 4.5, 5.5, 6.5]:
        ax.plot([x, x], [1.7, 3.7], color="#c586c0", linewidth=3.0)

    # Inlets & Outlets
    # Tube inlet/outlet (left side heads)
    ax.annotate("Tube In (Crude)\n210°C / 14.2 bar", xy=(2.0, 3.8), xytext=(0.5, 4.4),
                arrowprops=dict(facecolor="#4ec9b0", shrink=0.08, width=2, headwidth=8),
                color="#4ec9b0", fontsize=9.5, fontweight="bold")
    ax.annotate("Tube Out\n285°C / 13.8 bar", xy=(2.0, 2.2), xytext=(0.5, 1.4),
                arrowprops=dict(facecolor="#4ec9b0", shrink=0.08, width=2, headwidth=8),
                color="#4ec9b0", fontsize=9.5, fontweight="bold")

    # Shell inlet/outlet
    ax.annotate("Shell In (Hot Oil)\n340°C", xy=(4.0, 4.7), xytext=(4.0, 5.4),
                arrowprops=dict(facecolor="#f48771", shrink=0.08, width=2, headwidth=8),
                color="#f48771", fontsize=9.5, fontweight="bold", ha="center")
    ax.annotate("Shell Out (Cooled Oil)\n260°C", xy=(6.0, 1.3), xytext=(6.0, 0.5),
                arrowprops=dict(facecolor="#f48771", shrink=0.08, width=2, headwidth=8),
                color="#f48771", fontsize=9.5, fontweight="bold", ha="center")

    # Labels
    ax.text(5.0, 2.9, "TEMA Class R Bundle\n(Carbon Steel 1.25Cr-0.5Mo)",
            color="#ffffff", fontsize=10, ha="center", va="center", fontweight="semibold")

    ax.set_xlim(-0.2, 8.8)
    ax.set_ylim(0.0, 6.0)
    ax.axis("off")
    ax.set_title(f"{title} (E-101 A/B)", color="#ffffff", fontsize=13, pad=15, fontweight="bold")

    plt.tight_layout()
    plt.savefig(out_path, facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)


def _draw_corrosion_degradation_chart(out_path: str, title: str):
    """Draw an ultrasonic wall thickness degradation trend vs retirement limit."""
    fig, ax = plt.subplots(figsize=(9, 5), dpi=180)
    fig.patch.set_facecolor("#1e1e1e")
    ax.set_facecolor("#252526")

    years = np.array([2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026, 2027, 2028])
    # Historical actual thickness
    actual_years = years[:7]
    thickness_actual = np.array([12.7, 12.3, 11.8, 11.2, 10.5, 9.9, 9.1])

    # Projected trendline
    proj_years = years[6:]
    # CR = ~0.6 mm/yr
    thickness_proj = 9.1 - 0.62 * (proj_years - 2024)

    t_min = 4.8  # Retirement limit

    # Plot actual
    ax.plot(actual_years, thickness_actual, marker="o", color="#4ec9b0", linewidth=2.5, label="Measured UT Thickness (CML-04)")
    # Plot projection
    ax.plot(proj_years, thickness_proj, linestyle="--", marker="s", color="#ce9178", linewidth=2.0, label="Projected Degradation (CR = 0.62 mm/yr)")
    # Retirement limit line
    ax.axhline(t_min, color="#f48771", linestyle="-.", linewidth=2.0, label=f"API 570 Retirement Limit (t_min = {t_min} mm)")

    # Fill risk zone
    ax.fill_between(years, 0, t_min, color="#f48771", alpha=0.15)
    ax.text(2027.5, 2.5, "RETIREMENT / FAILURE ZONE", color="#f48771", fontsize=9, fontweight="bold")

    ax.set_xlabel("Inspection Year", color="#d4d4d4", fontsize=10)
    ax.set_ylabel("Nominal Wall Thickness (mm)", color="#d4d4d4", fontsize=10)
    ax.set_title(title, color="#ffffff", fontsize=12, pad=12, fontweight="bold")
    ax.grid(True, color="#3e3e42", linestyle=":", alpha=0.6)
    ax.tick_params(colors="#d4d4d4")
    for spine in ax.spines.values():
        spine.set_color("#3e3e42")

    ax.legend(facecolor="#2d2d30", edgecolor="#3e3e42", labelcolor="#ffffff", fontsize=9)
    plt.tight_layout()
    plt.savefig(out_path, facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)


def _draw_distillation_column_pfd(out_path: str, title: str):
    """Draw a Process Flow Diagram of a Distillation Column."""
    fig, ax = plt.subplots(figsize=(9, 6), dpi=180)
    fig.patch.set_facecolor("#1e1e1e")
    ax.set_facecolor("#252526")

    # Column body
    col = patches.Rectangle((3.5, 1.5), 1.6, 4.5, linewidth=2.5, edgecolor="#569cd6", facecolor="#2d2d30")
    ax.add_patch(col)

    # Trays
    for y in np.linspace(2.0, 5.5, 9):
        ax.plot([3.6, 5.0], [y, y], color="#c586c0", linewidth=1.5, linestyle=":")

    # Feed line
    ax.annotate("Crude Feed (F-101)\n350°C", xy=(3.5, 2.8), xytext=(1.2, 2.8),
                arrowprops=dict(facecolor="#4ec9b0", shrink=0.08, width=2, headwidth=7),
                color="#4ec9b0", fontsize=9, fontweight="bold")

    # Overhead vapor to Condenser
    ax.annotate("Overhead Vapor", xy=(4.3, 6.0), xytext=(4.3, 6.7),
                arrowprops=dict(facecolor="#9cdcfe", shrink=0.08, width=2, headwidth=7),
                color="#9cdcfe", fontsize=9, ha="center")

    # Bottoms to Reboiler
    ax.annotate("Bottoms Residue", xy=(4.3, 1.5), xytext=(4.3, 0.7),
                arrowprops=dict(facecolor="#f48771", shrink=0.08, width=2, headwidth=7),
                color="#f48771", fontsize=9, ha="center")

    # Side draws
    ax.annotate("Heavy Gas Oil (HGO)", xy=(5.1, 4.8), xytext=(6.8, 4.8),
                arrowprops=dict(facecolor="#dcdcaa", shrink=0.08, width=1.5, headwidth=6),
                color="#dcdcaa", fontsize=8.5)
    ax.annotate("Diesel / Kerosene", xy=(5.1, 3.8), xytext=(6.8, 3.8),
                arrowprops=dict(facecolor="#dcdcaa", shrink=0.08, width=1.5, headwidth=6),
                color="#dcdcaa", fontsize=8.5)

    ax.text(4.3, 3.7, "C-101 Column\n(36 Trays)", color="#ffffff", fontsize=9.5,
            fontweight="bold", ha="center", va="center")

    ax.set_xlim(0.5, 8.8)
    ax.set_ylim(0.2, 7.3)
    ax.axis("off")
    ax.set_title(title, color="#ffffff", fontsize=12, pad=12, fontweight="bold")

    plt.tight_layout()
    plt.savefig(out_path, facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)


def _draw_pump_manifold_schematic(out_path: str, title: str):
    """Draw a standard Centrifugal Pump & Bypass Piping Manifold."""
    fig, ax = plt.subplots(figsize=(9, 5), dpi=180)
    fig.patch.set_facecolor("#1e1e1e")
    ax.set_facecolor("#252526")

    # Suction line
    ax.plot([1.0, 3.2], [2.5, 2.5], color="#569cd6", linewidth=3.0)
    # Pump circle
    pump = patches.Circle((3.8, 2.5), 0.6, linewidth=2.5, edgecolor="#4ec9b0", facecolor="#2d2d30")
    ax.add_patch(pump)
    # Impeller triangle
    impeller = patches.Polygon([[3.4, 2.1], [3.4, 2.9], [4.2, 2.5]], closed=True,
                               edgecolor="#4ec9b0", facecolor="#4ec9b0")
    ax.add_patch(impeller)

    # Discharge line
    ax.plot([4.4, 7.5], [2.5, 2.5], color="#569cd6", linewidth=3.0)

    # Bypass line
    ax.plot([2.0, 2.0, 6.5, 6.5], [2.5, 4.2, 4.2, 2.5], color="#c586c0", linewidth=2.0, linestyle="--")
    ax.text(4.25, 4.4, "Recirculation / Minimum Flow Bypass (FV-102)", color="#c586c0", fontsize=8.5, ha="center")

    # Annotations
    ax.annotate("Suction (1.8 bar)", xy=(1.2, 2.5), xytext=(0.5, 1.7),
                arrowprops=dict(facecolor="#569cd6", shrink=0.08, width=1.5, headwidth=6),
                color="#569cd6", fontsize=9, fontweight="bold")
    ax.annotate("Discharge (18.5 bar)", xy=(7.0, 2.5), xytext=(6.5, 1.7),
                arrowprops=dict(facecolor="#f48771", shrink=0.08, width=1.5, headwidth=6),
                color="#f48771", fontsize=9, fontweight="bold")

    ax.text(3.8, 1.5, "P-101A Primary Centrifugal Pump\n(Flow: 450 m³/h, Head: 165m)",
            color="#ffffff", fontsize=9.5, fontweight="bold", ha="center")

    ax.set_xlim(0.0, 8.5)
    ax.set_ylim(0.8, 5.2)
    ax.axis("off")
    ax.set_title(title, color="#ffffff", fontsize=12, pad=12, fontweight="bold")

    plt.tight_layout()
    plt.savefig(out_path, facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
