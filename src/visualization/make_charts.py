"""Publication-quality charts for the onboarding analysis.

Every chart shows *aggregates only*. Titles state the finding and are built
from the data, so the same code labels real and synthetic runs correctly.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless / CI-safe

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import seaborn as sns  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

from src.analysis.analyze_onboarding_funnel import (  # noqa: E402
    APPROVED_STATUSES,
    DECLINED_STATUSES,
    OUTCOME_GROUPS,
    OUTCOME_ORDER,
)
from src.analysis.onboarding_behaviour import (  # noqa: E402
    KNOWN_PLATFORMS,
    build_daily_summary,
    build_hourly_profile,
    build_platform_cancellation_summary,
    build_platform_stage_dropoff,
    build_stage_dropoff_summary,
)

# --------------------------------------------------------------------------- #
# Style
# --------------------------------------------------------------------------- #
INK = "#1F2933"
MUTED = "#6B7785"
GRID = "#E4E7EB"
ACCENT = "#1F5F8B"

OUTCOME_COLORS = {
    "Approved": "#2E8B6E",
    "Declined": "#C8553D",
    "Cancelled by user": "#E3A13A",
    "No completion recorded": "#9AA5B1",
    "Error / needs review": "#7B5EA7",
}

STATUS_LABELS = {
    "auto_approved": "Auto-approved",
    "manually_approved": "Manually approved",
    "auto_declined": "Auto-declined",
    "manually_declined": "Manually declined",
    "user_cancelled": "Cancelled by user",
    "started": "Started, no completion recorded",
    "error": "Error",
    "needs_review": "Needs review",
}

PLATFORM_LABELS = {
    "android": "Android",
    "ios": "iOS",
    "windows": "Windows",
    "macos": "macOS",
}

DPI = 170


def apply_style() -> None:
    sns.set_theme(style="white")
    plt.rcParams.update({
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.edgecolor": GRID,
        "axes.labelcolor": MUTED,
        "axes.labelsize": 10.5,
        "xtick.color": MUTED,
        "ytick.color": INK,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10.5,
        "font.family": "DejaVu Sans",
        "axes.spines.top": False,
        "axes.spines.right": False,
    })


def _thousands(value, _pos=None) -> str:
    return f"{value:,.0f}"


def _pct(value: float) -> str:
    """Format a percentage, avoiding a misleading '0.0%' for tiny shares."""

    if value == 0:
        return "0%"
    if value < 0.1:
        return "<0.1%"
    return f"{value:.1f}%"


def _title(fig, title: str, subtitle: str | None = None) -> None:
    fig.text(0.015, 0.965, title, ha="left", va="top",
             fontsize=15.5, fontweight="bold", color=INK)
    if subtitle:
        fig.text(0.015, 0.905, subtitle, ha="left", va="top",
                 fontsize=10.5, color=MUTED)


def _footer(fig, text: str, synthetic: bool) -> None:
    label = "SYNTHETIC DEMO DATA  |  " if synthetic else ""
    fig.text(0.015, 0.012, f"{label}{text}", ha="left", va="bottom",
             fontsize=8.5, color=MUTED)


def _save(fig, name: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / name
    fig.savefig(path, dpi=DPI, facecolor="white")
    plt.close(fig)
    return path


def _clean_axes(ax, grid_axis: str = "x") -> None:
    ax.grid(axis=grid_axis, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.spines["left"].set_visible(False)
    ax.tick_params(length=0)


# --------------------------------------------------------------------------- #
# Individual charts
# --------------------------------------------------------------------------- #
def chart_kpi_banner(df, out_dir, synthetic=False):
    total = len(df)
    approved = int(df["status"].isin(APPROVED_STATUSES).sum())
    declined = int(df["status"].isin(DECLINED_STATUSES).sum())
    cancelled = int((df["status"] == "user_cancelled").sum())
    started = int((df["status"] == "started").sum())
    decided = approved + declined

    cards = [
        ("Attempts analysed", f"{total:,}", "onboarding transactions", ACCENT),
        ("Approved", f"{approved / total * 100:.1f}%",
         "auto + manual approvals", OUTCOME_COLORS["Approved"]),
        ("Approval rate", f"{approved / decided * 100:.1f}%",
         "among decided cases", OUTCOME_COLORS["Approved"]),
        ("Cancelled", f"{cancelled / total * 100:.1f}%",
         "of attempts, by the user", OUTCOME_COLORS["Cancelled by user"]),
        ("No completion", f"{started / total * 100:.1f}%",
         "started, never finished",
         OUTCOME_COLORS["No completion recorded"]),
    ]

    fig = plt.figure(figsize=(12.5, 2.6))
    ax = fig.add_axes([0.005, 0.12 if synthetic else 0.04, 0.99,
                       0.84 if synthetic else 0.92])
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")

    gap = 1.6
    width = (100 - gap * (len(cards) - 1)) / len(cards)

    for i, (label, value, note, color) in enumerate(cards):
        x = i * (width + gap)
        ax.add_patch(FancyBboxPatch(
            (x, 4), width, 92, boxstyle="round,pad=0,rounding_size=3",
            facecolor="#F7F9FB", edgecolor=GRID, linewidth=1.2))
        ax.add_patch(FancyBboxPatch(
            (x + 3, 84), 7, 3.2, boxstyle="round,pad=0,rounding_size=1.5",
            facecolor=color, edgecolor="none"))
        ax.text(x + 3, 68, label.upper(), fontsize=9, color=MUTED,
                fontweight="bold", va="center")
        ax.text(x + 3, 42, value, fontsize=25, color=INK,
                fontweight="bold", va="center")
        ax.text(x + 3, 17, note, fontsize=9, color=MUTED, va="center")

    if synthetic:
        fig.text(0.008, 0.015, "SYNTHETIC DEMO DATA", fontsize=8.5,
                 color=MUTED)

    return _save(fig, "00_kpi_banner.png", out_dir)


def chart_outcome_breakdown(df, out_dir, source_label, synthetic=False):
    counts = df["status"].value_counts()
    total = len(df)

    order = counts.index.tolist()
    values = counts.values
    groups = [OUTCOME_GROUPS[s] for s in order]
    colors = [OUTCOME_COLORS[g] for g in groups]
    labels = [STATUS_LABELS.get(s, s) for s in order]

    no_decision = 100 - (
        df["status"].isin(APPROVED_STATUSES | DECLINED_STATUSES).mean() * 100
    )
    approved_pct = df["status"].isin(APPROVED_STATUSES).mean() * 100

    fig, ax = plt.subplots(figsize=(11, 6))
    fig.subplots_adjust(left=0.27, right=0.95, top=0.82, bottom=0.12)

    bars = ax.barh(range(len(order)), values, color=colors, height=0.66)
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.xaxis.set_major_formatter(FuncFormatter(_thousands))
    ax.set_xlabel("Onboarding attempts")
    _clean_axes(ax)

    for bar, value in zip(bars, values):
        ax.text(
            bar.get_width() + total * 0.005,
            bar.get_y() + bar.get_height() / 2,
            f"{value:,}  ({_pct(value / total * 100)})",
            va="center", fontsize=10, color=INK,
        )

    ax.set_xlim(0, values.max() * 1.25)

    handles = [plt.Rectangle((0, 0), 1, 1, color=OUTCOME_COLORS[g])
               for g in OUTCOME_ORDER]
    ax.legend(handles, OUTCOME_ORDER, loc="lower right", frameon=False,
              fontsize=9.5, labelcolor=INK)

    _title(
        fig,
        f"{approved_pct:.0f}% of onboarding attempts are approved, "
        f"but {no_decision:.0f}% never reach a decision",
        "Outcome of every onboarding attempt, by final recorded status",
    )
    _footer(fig, f"{source_label} (n = {total:,}). Aggregate counts only.",
            synthetic)
    return _save(fig, "01_outcome_breakdown.png", out_dir)


def chart_stage_dropoff(df, out_dir, source_label, synthetic=False):
    summary = build_stage_dropoff_summary(df)

    top = summary.iloc[0]
    top_two = summary.head(2)["pct_of_status"].sum()

    # Fold stages under 1% (and unrecorded stages) into one bar.
    minor = (summary["pct_of_status"] < 1) | (
        summary["stage"] == "No stage recorded"
    )
    if minor.any():
        folded = pd.DataFrame([{
            "stage": "Other / minor stages",
            "transactions": int(summary.loc[minor, "transactions"].sum()),
            "pct_of_status": round(summary.loc[minor, "pct_of_status"].sum(), 2),
        }])
        summary = pd.concat([summary.loc[~minor], folded], ignore_index=True)

    fig, ax = plt.subplots(figsize=(11, 5.6))
    fig.subplots_adjust(left=0.24, right=0.94, top=0.82, bottom=0.13)

    colors = [ACCENT if i == 0 else "#9DB7CC" for i in range(len(summary))]
    bars = ax.barh(summary["stage"], summary["transactions"],
                   color=colors, height=0.62)
    ax.invert_yaxis()
    ax.xaxis.set_major_formatter(FuncFormatter(_thousands))
    ax.set_xlabel("User-cancelled attempts")
    _clean_axes(ax)

    for bar, (_, row) in zip(bars, summary.iterrows()):
        ax.text(
            bar.get_width() + summary["transactions"].max() * 0.012,
            bar.get_y() + bar.get_height() / 2,
            f"{int(row['transactions']):,}  ({_pct(row['pct_of_status'])})",
            va="center", fontsize=10, color=INK,
        )

    ax.set_xlim(0, summary["transactions"].max() * 1.28)

    _title(
        fig,
        f"{top['stage']} is the biggest drop-off point "
        f"({top['pct_of_status']:.0f}% of cancellations)",
        f"Last recorded stage before a user cancelled. The top two stages "
        f"account for {top_two:.0f}% of cancellations.",
    )
    _footer(fig, f"{source_label}. Stage = last executed module, grouped "
                 "into generic labels.", synthetic)
    return _save(fig, "02_stage_dropoff.png", out_dir)


def chart_platform_cancellations(df, out_dir, source_label, synthetic=False):
    platform = build_platform_cancellation_summary(df)
    platform = platform[platform["platform"].isin(KNOWN_PLATFORMS)]
    platform = platform.sort_values("cancellation_rate", ascending=False)

    stage = build_platform_stage_dropoff(df)

    hi = platform.iloc[0]
    lo = platform.iloc[-1]

    fig, (ax1, ax2) = plt.subplots(
        1, 2, figsize=(13, 5.8), gridspec_kw={"width_ratios": [1, 1.25]}
    )
    fig.subplots_adjust(left=0.08, right=0.97, top=0.80, bottom=0.25,
                        wspace=0.42)

    # Left: cancellation rate ------------------------------------------
    names = [PLATFORM_LABELS[p] for p in platform["platform"]]
    bars = ax1.barh(names, platform["cancellation_rate"], color=ACCENT,
                    height=0.6)
    ax1.invert_yaxis()
    ax1.set_xlim(0, platform["cancellation_rate"].max() * 1.3)
    ax1.set_xlabel("Cancellation rate (% of completed-flow records)")
    _clean_axes(ax1)

    for bar, (_, row) in zip(bars, platform.iterrows()):
        ax1.text(
            bar.get_width() + 0.6,
            bar.get_y() + bar.get_height() / 2,
            f"{row['cancellation_rate']:.1f}%  "
            f"(n={int(row['finished_transactions']):,})",
            va="center", fontsize=9.5, color=INK,
        )

    ax1.set_title("How often users cancel", loc="left", fontsize=11.5,
                  color=INK, fontweight="bold", pad=10)

    # Right: where they cancel -----------------------------------------
    pivot = (
        stage.pivot(index="platform_normalized", columns="stage",
                    values="pct_of_platform_cancellations")
        .fillna(0)
        .reindex(platform["platform"])
    )
    # Keep the five largest stages; fold everything else into one group so the
    # legend stays readable on real data with many tiny categories.
    ranked = [
        stage_name
        for stage_name in build_stage_dropoff_summary(df)["stage"]
        if stage_name in pivot.columns
        and stage_name not in ("No stage recorded", "Other")
    ]
    top_stages = ranked[:5]
    other_columns = [c for c in pivot.columns if c not in top_stages]

    pivot = pivot[top_stages].assign(
        **{"Other / unrecorded": pivot[other_columns].sum(axis=1)}
    )
    stage_order = list(pivot.columns)

    palette = ["#1F5F8B", "#5FA3C7", "#E3A13A", "#C8553D", "#7B5EA7",
               "#9AA5B1"]
    left = np.zeros(len(pivot))

    for color, stage_name in zip(palette, stage_order):
        values = pivot[stage_name].values
        ax2.barh([PLATFORM_LABELS[p] for p in pivot.index], values,
                 left=left, color=color, height=0.6, label=stage_name)

        for i, (value, start) in enumerate(zip(values, left)):
            if value >= 9:
                ax2.text(start + value / 2, i, f"{value:.0f}%",
                         ha="center", va="center", fontsize=9,
                         color="white", fontweight="bold")
        left += values

    ax2.invert_yaxis()
    ax2.set_xlim(0, 100)
    ax2.set_xlabel("Share of that platform's cancellations (%)")
    _clean_axes(ax2)
    handles, legend_labels = ax2.get_legend_handles_labels()
    fig.legend(handles, legend_labels, loc="lower center",
               bbox_to_anchor=(0.5, 0.07), ncol=len(legend_labels),
               frameon=False, fontsize=9, labelcolor=INK)
    ax2.set_title("Where they cancel", loc="left", fontsize=11.5,
                  color=INK, fontweight="bold", pad=10)

    ratio = hi["cancellation_rate"] / lo["cancellation_rate"]
    _title(
        fig,
        f"{PLATFORM_LABELS[hi['platform']]} users cancel "
        f"{ratio:.1f}x as often as {PLATFORM_LABELS[lo['platform']]} users",
        "Platform comparison among completed-flow records "
        "(excludes 'started' and agent-updated records)",
    )
    _footer(fig, f"{source_label}. Platforms with unknown or missing "
                 "values excluded.", synthetic)
    return _save(fig, "03_platform_cancellations.png", out_dir)


def chart_daily_volume(df, out_dir, source_label, synthetic=False):
    daily = build_daily_summary(df)
    dates = pd.to_datetime(daily["created_date"])

    fig, ax = plt.subplots(figsize=(12, 5.8))
    fig.subplots_adjust(left=0.08, right=0.97, top=0.82, bottom=0.17)

    bottom = np.zeros(len(daily))
    for group in OUTCOME_ORDER:
        ax.bar(dates, daily[group], bottom=bottom,
               color=OUTCOME_COLORS[group], width=0.82, label=group)
        bottom += daily[group].values

    ax.yaxis.set_major_formatter(FuncFormatter(_thousands))
    ax.set_ylabel("Onboarding attempts per day")
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%b %d"))
    ax.xaxis.set_major_locator(matplotlib.dates.DayLocator(interval=3))
    plt.setp(ax.get_xticklabels(), rotation=0)
    _clean_axes(ax, grid_axis="y")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=5,
              frameon=False, fontsize=9.5, labelcolor=INK)

    avg = daily["total"].mean()
    _title(
        fig,
        f"Daily volume averages {avg:,.0f} attempts "
        f"({daily['total'].min():,} to {daily['total'].max():,})",
        "Daily onboarding attempts by outcome, by record creation date",
    )
    _footer(fig, f"{source_label}. Dates as recorded; timezone not verified.",
            synthetic)
    return _save(fig, "04_daily_volume.png", out_dir)


def chart_activity_heatmap(df, out_dir, source_label, synthetic=False):
    profile = build_hourly_profile(df)

    pivot = profile.pivot(index="weekday", columns="created_hour",
                          values="avg_transactions_per_day")
    weekday_order = [
        "Monday", "Tuesday", "Wednesday", "Thursday",
        "Friday", "Saturday", "Sunday",
    ]
    pivot = pivot.reindex(weekday_order)

    hourly = pivot.mean(axis=0)
    peak, trough = int(hourly.idxmax()), int(hourly.idxmin())

    fig, ax = plt.subplots(figsize=(12, 5.4))
    fig.subplots_adjust(left=0.1, right=0.98, top=0.82, bottom=0.13)

    sns.heatmap(
        pivot, ax=ax, cmap="YlGnBu", linewidths=0.6, linecolor="white",
        cbar_kws={"label": "Avg attempts per day in that hour", "shrink": 0.85},
    )
    ax.set_xlabel("Hour of day (as recorded)")
    ax.set_ylabel("")
    ax.set_xticklabels([f"{h:02d}" for h in range(24)], rotation=0)
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)

    _title(
        fig,
        f"Activity peaks around {peak:02d}:00 and is quietest around "
        f"{trough:02d}:00",
        "Average onboarding attempts per hour, by weekday and hour of day",
    )
    _footer(fig, f"{source_label}. Timestamps as recorded; "
                 "timezone not verified.", synthetic)
    return _save(fig, "05_activity_heatmap.png", out_dir)


def chart_time_spent(df, out_dir, source_label, synthetic=False):
    keep = ["auto_approved", "auto_declined", "user_cancelled", "error"]
    timed = df[df["status"].isin(keep)].dropna(subset=["time_spent_seconds"])

    order = (
        timed.groupby("status")["time_spent_seconds"].median()
        .sort_values(ascending=False).index.tolist()
    )
    labels = [STATUS_LABELS[s] for s in order]
    colors = [OUTCOME_COLORS[OUTCOME_GROUPS[s]] for s in order]

    data = [timed.loc[timed["status"] == s, "time_spent_seconds"] / 60
            for s in order]

    fig, ax = plt.subplots(figsize=(11, 5.4))
    fig.subplots_adjust(left=0.2, right=0.95, top=0.82, bottom=0.14)

    box = ax.boxplot(
        data, orientation="horizontal", patch_artist=True, showfliers=False,
        widths=0.55, tick_labels=labels,
        medianprops={"color": INK, "linewidth": 2},
        whiskerprops={"color": MUTED}, capprops={"color": MUTED},
    )
    for patch, color in zip(box["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.85)
        patch.set_edgecolor("white")

    ax.invert_yaxis()
    for i, series in enumerate(data, start=1):
        ax.text(series.median(), i - 0.40, f"median {series.median():.1f} min",
                ha="center", va="bottom", fontsize=9, color=INK)

    ax.set_xlabel("Journey duration (minutes)")
    _clean_axes(ax)

    med = {s: d.median() for s, d in zip(order, data)}
    _title(
        fig,
        f"Approved journeys take ~{med.get('auto_approved', np.nan):.1f} min; "
        f"cancellations leave after ~{med.get('user_cancelled', np.nan):.1f} min",
        "Time spent per journey by outcome (boxes = middle 50%, whiskers = "
        "1.5x IQR)",
    )
    _footer(fig, f"{source_label}. Assumes time_spent is in milliseconds; "
                 "journeys over 60 min excluded.", synthetic)
    return _save(fig, "06_time_spent_by_outcome.png", out_dir)


def chart_reconciliation(overlap, names, out_dir, synthetic=False):
    """Heatmap: % of the row dataset's unique IDs found in the column one."""

    datasets = list(dict.fromkeys(
        list(overlap["dataset_a"]) + list(overlap["dataset_b"])
    ))
    matrix = pd.DataFrame(np.nan, index=datasets, columns=datasets)

    for _, row in overlap.iterrows():
        matrix.loc[row["dataset_a"], row["dataset_b"]] = row["overlap_pct_of_a"]
        matrix.loc[row["dataset_b"], row["dataset_a"]] = row["overlap_pct_of_b"]

    matrix.index = [textwrap.fill(names.get(d, d), 22) for d in datasets]
    matrix.columns = [textwrap.fill(names.get(d, d), 13) for d in datasets]

    fig, ax = plt.subplots(figsize=(11.5, 7.4))
    fig.subplots_adjust(left=0.19, right=0.97, top=0.84, bottom=0.14)

    sns.heatmap(
        matrix, ax=ax, annot=True, fmt=".1f", cmap="Blues", vmin=0, vmax=100,
        linewidths=1, linecolor="white", annot_kws={"fontsize": 9.5},
        cbar_kws={"label": "% of row dataset's IDs found in column dataset",
                  "shrink": 0.8},
    )
    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.tick_params(length=0, labelsize=9)
    plt.setp(ax.get_xticklabels(), rotation=0)
    for spine in ax.spines.values():
        spine.set_visible(False)

    _title(
        fig,
        "Extracts overlap unevenly, so they cannot be simply combined",
        "Share of each row-dataset's unique transaction IDs that also appear "
        "in the column dataset (identifiers are never shown)",
    )
    _footer(fig, "ID-level reconciliation of private extracts. Percentages "
                 "only.", synthetic)
    return _save(fig, "07_dataset_reconciliation.png", out_dir)


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def make_all_charts(
    df: pd.DataFrame,
    out_dir: Path,
    source_label: str,
    synthetic: bool = False,
    overlap: pd.DataFrame | None = None,
    names: dict[str, str] | None = None,
) -> list[Path]:
    """Generate every chart and return the written paths."""

    apply_style()

    paths = [
        chart_kpi_banner(df, out_dir, synthetic),
        chart_outcome_breakdown(df, out_dir, source_label, synthetic),
        chart_stage_dropoff(df, out_dir, source_label, synthetic),
        chart_platform_cancellations(df, out_dir, source_label, synthetic),
        chart_daily_volume(df, out_dir, source_label, synthetic),
        chart_activity_heatmap(df, out_dir, source_label, synthetic),
        chart_time_spent(df, out_dir, source_label, synthetic),
    ]

    if overlap is not None and not overlap.empty:
        paths.append(
            chart_reconciliation(overlap, names or {}, out_dir, synthetic)
        )

    return paths
