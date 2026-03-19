from __future__ import annotations

"""
Visualization helpers for the EP/CATH Simulation.py workflow.

Designed to work directly with these current outputs:
1. results = Simulation.comparePriorityRules(...)
   -> dict with keys: "best", "ranked"
2. timePeriod, summary = Simulation.RunSimulation(...)
   -> summary dict with keys like:
      - summary["priority_rule"]
      - summary["overflow_total"]
      - summary["cath_utilization_avg"]
      - summary["ep_utilization_avg"]
      - summary["mean_room_utilization"]
      - summary["holding_bay"]
      - summary["close_time_eval"]
      - summary["cost_analysis"]["hb"]["cost_table"]
      - summary["cost_analysis"]["close"]["cost_table"]

This version also supports comparison of full recommendation packages.
All functions return matplotlib Figure objects.
"""

import matplotlib.pyplot as plt
import pandas as pd

# -----------------------------------------------------------------------------
# Palette / theme
# -----------------------------------------------------------------------------

PRIMARY = "#5b9bd5"      # recommendation (blue)
SECONDARY = "#5b9bd5"
ACCENT = "#5b9bd5"
BENCHMARK = "#7a8ba0"    # existing plan (muted blue-gray)
ALTERNATIVE = "#4a5a70"  # alternatives (darker muted)
GRID = "#2a3547"
TEXT = "#e2e8f0"
BG = "#1a2233"
SUBTEXT = "#7a8ba0"


def _style_axes(ax, grid_axis="x"):
    ax.set_facecolor(BG)
    if grid_axis == "both":
        ax.grid(color=GRID, linewidth=0.8)
    else:
        ax.grid(axis=grid_axis, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(GRID)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=TEXT, length=0, labelsize=10)
    ax.xaxis.label.set_color(TEXT)
    ax.yaxis.label.set_color(TEXT)


def _title_block(ax, title, subtitle=None):
    ax.set_title(title, loc="left", fontsize=14, fontweight="bold", pad=12, color=TEXT)
    if subtitle:
        ax.text(
            0.0, 1.01, subtitle,
            transform=ax.transAxes,
            ha="left", va="bottom",
            fontsize=9, color=SUBTEXT
        )


def _source_note(fig, text):
    fig.text(0.012, 0.012, text, ha="left", va="bottom", fontsize=8, color=SUBTEXT)


# -----------------------------------------------------------------------------
# Internal helpers
# -----------------------------------------------------------------------------

def _ranked_to_df(results) -> pd.DataFrame:
    if isinstance(results, pd.DataFrame):
        return results.copy()
    if isinstance(results, dict) and "ranked" in results:
        return pd.DataFrame(results["ranked"])
    return pd.DataFrame(results)


def _expand_policy_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "holding_bay" in df.columns:
        df["recommended_bays_p95"] = df["holding_bay"].apply(lambda x: x["recommended_bays_p95"])
        df["peak_bays_p95"] = df["holding_bay"].apply(lambda x: x["peak_bays_p95"])
        df["last_occupied_p95_hours"] = df["holding_bay"].apply(lambda x: x["last_occupied_p95_hours"])
        df["recommended_close_p95"] = df["holding_bay"].apply(lambda x: x["recommended_close_p95"])
    return df


def _annotate_bar_values(ax, decimals: int = 0):
    fmt = "{:." + str(decimals) + "f}"
    for patch in ax.patches:
        value = patch.get_height()
        ax.annotate(
            fmt.format(value),
            (patch.get_x() + patch.get_width() / 2.0, value),
            ha="center",
            va="bottom",
            xytext=(0, 4),
            textcoords="offset points",
            fontsize=9,
            color=TEXT,
        )


def _build_option_label(row, policy_col="priority_rule", hb_col="hb_count", close_col="close_time"):
    parts = []
    if policy_col in row and pd.notna(row[policy_col]):
        parts.append(str(row[policy_col]))
    if hb_col in row and pd.notna(row[hb_col]):
        parts.append(str(int(row[hb_col])) + " bays")
    if close_col in row and pd.notna(row[close_col]):
        parts.append("close " + str(row[close_col]))
    return "\n".join(parts) if len(parts) > 0 else "option"


def _short_option_label(label: str) -> str:
    if label is None:
        return "option"
    label = str(label)
    replacements = {
        "longest recovery time first": "Longest recovery",
        "shortest recovery time first": "Shortest recovery",
        "longest procedures first": "Longest procedure",
        "shortest procedures first": "Shortest procedure",
        "historical": "Historical",
        "Existing plan": "Existing",
        "Recommended": "Recommended",
        "close ": "",
    }
    out = label
    for old, new in replacements.items():
        out = out.replace(old, new)
    return out


def _display_name(row):
    if row.get("is_existing_plan", False):
        return "Existing plan"
    if row.get("is_recommended", False):
        return "Recommended"
    return "Historical redesign"


def _option_colors(df):
    colors = []
    for _, row in df.iterrows():
        if row.get("is_recommended", False):
            colors.append(PRIMARY)
        elif row.get("is_existing_plan", False):
            colors.append(BENCHMARK)
        else:
            colors.append(ALTERNATIVE)
    return colors


# -----------------------------------------------------------------------------
# Policy comparison plots
# -----------------------------------------------------------------------------

def plot_policy_overflow(results):
    df = _expand_policy_df(_ranked_to_df(results))
    fig, ax = plt.subplots(figsize=(9, 5), facecolor=BG)
    ax.bar(df["priority_rule"], df["overflow_total"], color=ACCENT)
    _title_block(ax, "Late-running procedures by scheduling policy")
    ax.set_xlabel("Scheduling policy")
    ax.set_ylabel("Procedures scheduled past room closing")
    ax.tick_params(axis="x", rotation=20)
    _style_axes(ax, "y")
    _annotate_bar_values(ax, decimals=0)
    fig.tight_layout()
    return fig


def plot_policy_utilization(results):
    df = _expand_policy_df(_ranked_to_df(results))
    x = range(len(df))
    width = 0.38

    fig, ax = plt.subplots(figsize=(9, 5), facecolor=BG)
    ax.bar([i - width / 2 for i in x], df["cath_utilization_avg"], width=width, label="Cath", color=ACCENT)
    ax.bar([i + width / 2 for i in x], df["ep_utilization_avg"], width=width, label="EP", color=BENCHMARK)

    _title_block(ax, "Average room utilization by scheduling policy")
    ax.set_xticks(list(x))
    ax.set_xticklabels(df["priority_rule"], rotation=20)
    ax.set_xlabel("Scheduling policy")
    ax.set_ylabel("Average utilization")
    _style_axes(ax, "y")
    ax.legend(frameon=False)
    fig.tight_layout()
    return fig


def plot_policy_hb_peaks(results):
    df = _expand_policy_df(_ranked_to_df(results))
    fig, ax = plt.subplots(figsize=(9, 5), facecolor=BG)
    ax.bar(df["priority_rule"], df["recommended_bays_p95"], color=ACCENT)
    _title_block(ax, "Recommended holding bays (P95) by scheduling policy")
    ax.set_xlabel("Scheduling policy")
    ax.set_ylabel("Recommended holding bays")
    ax.tick_params(axis="x", rotation=20)
    _style_axes(ax, "y")
    _annotate_bar_values(ax, decimals=0)
    fig.tight_layout()
    return fig


def plot_policy_close_burden(results):
    df = _expand_policy_df(_ranked_to_df(results))
    fig, ax = plt.subplots(figsize=(9, 5), facecolor=BG)
    ax.bar(df["priority_rule"], df["last_occupied_p95_hours"], color=ACCENT)
    _title_block(ax, "P95 last occupied time by scheduling policy")
    ax.set_xlabel("Scheduling policy")
    ax.set_ylabel("Hours since midnight")
    ax.tick_params(axis="x", rotation=20)
    _style_axes(ax, "y")
    _annotate_bar_values(ax, decimals=2)
    fig.tight_layout()
    return fig


def plot_policy_summary_scorecard(results):
    df = _expand_policy_df(_ranked_to_df(results)).copy()

    def best_when_low(series):
        if series.max() == series.min():
            return pd.Series([1.0] * len(series), index=series.index)
        return (series.max() - series) / (series.max() - series.min())

    def best_when_high(series):
        if series.max() == series.min():
            return pd.Series([1.0] * len(series), index=series.index)
        return (series - series.min()) / (series.max() - series.min())

    df["score_overflow"] = best_when_low(df["overflow_total"])
    df["score_hb_peak"] = best_when_low(df["peak_bays_p95"])
    df["score_close_burden"] = best_when_low(df["last_occupied_p95_hours"])
    df["score_utilization"] = best_when_high(df["mean_room_utilization"])

    metrics = ["score_overflow", "score_hb_peak", "score_close_burden", "score_utilization"]
    labels = ["Overflow", "HB peak", "Close burden", "Utilization"]

    x = range(len(df))
    width = 0.18
    fig, ax = plt.subplots(figsize=(10, 5), facecolor=BG)
    for i, metric in enumerate(metrics):
        ax.bar([j + (i - 1.5) * width for j in x], df[metric], width=width, label=labels[i])

    _title_block(ax, "Policy comparison scorecard")
    ax.set_xticks(list(x))
    ax.set_xticklabels(df["priority_rule"], rotation=20)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Normalized score (higher is better)")
    _style_axes(ax, "y")
    ax.legend(frameon=False)
    fig.tight_layout()
    return fig


# -----------------------------------------------------------------------------
# Summary-based plots
# -----------------------------------------------------------------------------

def _preferred_close_time(summary):
    """Return preferred close time HH:MM string, or None if unavailable."""
    try:
        return summary["cost_analysis"]["close"]["cost_recommendation"]["close_time_hhmm"]
    except (KeyError, TypeError):
        return None


def _mark_preferred_hline(ax, x_labels, y_values, pref_label):
    """Draw a horizontal dashed red line at the y-value of the preferred option."""
    if pref_label is None:
        return
    labels = list(x_labels)
    yvals  = list(y_values)
    idx = next((i for i, v in enumerate(labels) if str(v) == str(pref_label)), None)
    if idx is None:
        idx = next((i for i, v in enumerate(labels) if str(pref_label) in str(v)), None)
    if idx is not None:
        ax.axhline(y=yvals[idx], color="red", linestyle="--", linewidth=1.8,
                   label=f"Preferred ({pref_label}): {yvals[idx]:.1f}")
        ax.legend(frameon=False, fontsize=8)


def plot_close_time_sensitivity(summary):
    df = pd.DataFrame(summary["close_time_eval"])
    fig, ax = plt.subplots(figsize=(9, 5), facecolor=BG)
    ax.plot(df["close_time"], df["total_bay_hours_after_close"], marker="o", color=ACCENT)
    _title_block(ax, "Holding-bay demand remaining after closing time")
    ax.set_xlabel("Candidate close time")
    ax.set_ylabel("Total bay-hours after close")
    ax.tick_params(axis="x", rotation=30)
    _style_axes(ax, "y")
    _mark_preferred_hline(ax, df["close_time"], df["total_bay_hours_after_close"], _preferred_close_time(summary))
    fig.tight_layout()
    return fig


def plot_close_time_days_with_demand(summary):
    df = pd.DataFrame(summary["close_time_eval"])
    fig, ax = plt.subplots(figsize=(9, 5), facecolor=BG)
    ax.bar(df["close_time"], df["days_with_any_demand_after_close"], color=ACCENT)
    _title_block(ax, "Days with any demand after close")
    ax.set_xlabel("Candidate close time")
    ax.set_ylabel("Days")
    ax.tick_params(axis="x", rotation=30)
    _style_axes(ax, "y")
    _annotate_bar_values(ax, decimals=0)
    _mark_preferred_hline(ax, df["close_time"], df["days_with_any_demand_after_close"], _preferred_close_time(summary))
    fig.tight_layout()
    return fig


# -----------------------------------------------------------------------------
# Cost-analysis plots
# -----------------------------------------------------------------------------

def plot_hb_total_cost(summary):
    df = summary["cost_analysis"]["hb"]["cost_table"].copy().sort_values("hb_count")
    fig, ax = plt.subplots(figsize=(8, 5), facecolor=BG)
    ax.plot(df["hb_count"], df["total_holding_bay_cost"], marker="o", color=ACCENT)
    _title_block(ax, "Total holding-bay cost by bay count")
    ax.set_xlabel("Number of holding bays")
    ax.set_ylabel("Total holding-bay cost")
    _style_axes(ax, "y")
    fig.tight_layout()
    return fig


def plot_hb_cost_components(summary):
    df = summary["cost_analysis"]["hb"]["cost_table"].copy().sort_values("hb_count")
    fig, ax = plt.subplots(figsize=(9, 5), facecolor=BG)
    ax.bar(df["hb_count"], df["cancellation_cost"], label="Lost Contribution Margin / Foregone Revenue", color=ACCENT)
    ax.bar(df["hb_count"], df["empty_holding_bay_cost"], bottom=df["cancellation_cost"], label="Empty-bay cost", color=BENCHMARK)
    _title_block(ax, "Holding-bay cost components")
    ax.set_xlabel("Number of holding bays")
    ax.set_ylabel("Cost")
    _style_axes(ax, "y")
    ax.legend(frameon=False)
    fig.tight_layout()
    return fig


def plot_hb_service_constraint(summary):
    hb = summary["cost_analysis"]["hb"]
    service_choice = hb["service_constraint_recommendation"]
    threshold_days = service_choice["max_allowed_days"]
    df = hb["cost_table"].copy().sort_values("hb_count")

    if "days_with_instances" not in df.columns:
        raise ValueError("HB cost table does not include 'days_with_instances'.")

    fig, ax = plt.subplots(figsize=(8, 5), facecolor=BG)
    ax.plot(df["hb_count"], df["days_with_instances"], marker="o", color=ACCENT)
    ax.axhline(threshold_days, linestyle="--", color=BENCHMARK, label=f"Service threshold ({threshold_days:.0f} days)")
    _title_block(ax, "Service constraint by holding-bay count")
    ax.set_xlabel("Number of holding bays")
    ax.set_ylabel("Days with >=1 overcapacity event")
    _style_axes(ax, "y")
    ax.legend(frameon=False)
    fig.tight_layout()
    return fig


def plot_close_time_total_cost(summary):
    df = summary["cost_analysis"]["close"]["cost_table"].copy().sort_values("close_hours")
    pref = _preferred_close_time(summary)
    fig, ax = plt.subplots(figsize=(9, 5), facecolor=BG)
    ax.plot(df["close_time_hhmm"], df["total_cost"], marker="o", color=ACCENT)
    _title_block(ax, "Total cost by holding-bay close time")
    ax.set_xlabel("Holding-bay close time")
    ax.set_ylabel("Total cost")
    ax.tick_params(axis="x", rotation=30)
    _style_axes(ax, "y")
    _mark_preferred_hline(ax, df["close_time_hhmm"], df["total_cost"], pref)
    fig.tight_layout()
    return fig


def plot_close_time_cost_components(summary):
    df = summary["cost_analysis"]["close"]["cost_table"].copy().sort_values("close_hours")
    pref = _preferred_close_time(summary)
    total = df["estimated_labor_cost"] + df["admission_cost"]
    fig, ax = plt.subplots(figsize=(9, 5), facecolor=BG)
    ax.bar(df["close_time_hhmm"], df["estimated_labor_cost"], label="Labor cost", color=ACCENT)
    ax.bar(df["close_time_hhmm"], df["admission_cost"], bottom=df["estimated_labor_cost"], label="Admission cost", color=BENCHMARK)
    _title_block(ax, "Close-time cost components")
    ax.set_xlabel("Holding-bay close time")
    ax.set_ylabel("Cost")
    ax.tick_params(axis="x", rotation=30)
    _style_axes(ax, "y")
    _mark_preferred_hline(ax, df["close_time_hhmm"], total, pref)
    fig.tight_layout()
    return fig


# -----------------------------------------------------------------------------
# Recommendation option comparison
# -----------------------------------------------------------------------------

def options_to_df(options):
    df = pd.DataFrame(options).copy()
    if "option_name" not in df.columns:
        df["option_name"] = df.apply(_build_option_label, axis=1)
    if "total_cost" not in df.columns:
        hb = df["total_holding_bay_cost"] if "total_holding_bay_cost" in df.columns else 0.0
        close = df["total_close_cost"] if "total_close_cost" in df.columns else 0.0
        df["total_cost"] = hb + close
    if "is_existing_plan" not in df.columns:
        df["is_existing_plan"] = False
    if "is_recommended" not in df.columns:
        df["is_recommended"] = False
    return df


def plot_option_total_cost(options, title=None, subtitle=None, source_note=None):
    df = options_to_df(options).copy()
    df["display_name"] = df.apply(_display_name, axis=1)
    df = df.sort_values("total_cost", ascending=True)
    colors = _option_colors(df)

    fig, ax = plt.subplots(figsize=(8.4, 4.8), facecolor=BG)
    ax.barh(df["display_name"], df["total_cost"], color=colors, height=0.56)

    _title_block(
        ax,
        title or "The recommended package costs slightly less than the existing plan",
        subtitle or "Estimated total annual cost across tested recommendation packages."
    )

    ax.set_xlabel("Estimated total cost ($)")
    ax.set_ylabel("")
    _style_axes(ax, "x")

    xmin = min(df["total_cost"]) * 0.985
    xmax = max(df["total_cost"]) * 1.01
    ax.set_xlim(xmin, xmax)

    for i, v in enumerate(df["total_cost"]):
        ax.text(v + (xmax - xmin) * 0.01, i, f"${v:,.1f}", va="center", fontsize=10, color=TEXT)

    if source_note:
        _source_note(fig, source_note)

    plt.tight_layout(rect=(0, 0.04, 1, 0.98))
    return fig


def plot_option_cost_components(options):
    df = options_to_df(options).copy()
    hb = df["total_holding_bay_cost"] if "total_holding_bay_cost" in df.columns else pd.Series([0.0] * len(df))
    close = df["total_close_cost"] if "total_close_cost" in df.columns else pd.Series([0.0] * len(df))

    fig, ax = plt.subplots(figsize=(10, 5), facecolor=BG)
    ax.bar(df["option_name"], hb, label="Holding-bay cost", color=ACCENT)
    ax.bar(df["option_name"], close, bottom=hb, label="Close-time cost", color=BENCHMARK)
    _title_block(ax, "Cost components by recommendation option")
    ax.set_xlabel("Recommendation option")
    ax.set_ylabel("Cost")
    _style_axes(ax, "y")
    ax.legend(frameon=False)
    fig.tight_layout()
    return fig


def plot_option_overflow(options, title=None, subtitle=None, source_note=None):
    df = options_to_df(options).copy()
    if "overflow_total" not in df.columns:
        raise ValueError("Each option must include 'overflow_total'.")
    df["display_name"] = df.apply(_display_name, axis=1)
    df = df.sort_values("overflow_total", ascending=True)
    colors = _option_colors(df)

    fig, ax = plt.subplots(figsize=(8.4, 4.8), facecolor=BG)
    ax.barh(df["display_name"], df["overflow_total"], color=colors, height=0.56)

    _title_block(
        ax,
        title or "Scheduling by longest recovery time reduces late-running procedures",
        subtitle or "Annual procedures scheduled past room closing."
    )

    ax.set_xlabel("Procedures scheduled past room closing")
    ax.set_ylabel("")
    _style_axes(ax, "x")

    xmax = max(df["overflow_total"]) * 1.12
    ax.set_xlim(0, xmax)

    for i, v in enumerate(df["overflow_total"]):
        ax.text(v + xmax * 0.008, i, f"{int(v)}", va="center", fontsize=10, color=TEXT)

    if source_note:
        _source_note(fig, source_note)

    plt.tight_layout(rect=(0, 0.04, 1, 0.98))
    return fig


def plot_option_tradeoff_scatter(options, x_col="overflow_total", y_col="total_cost", label_col="option_name",
                                 title=None, subtitle=None, source_note=None):
    df = options_to_df(options).copy()
    if x_col not in df.columns or y_col not in df.columns:
        raise ValueError(f"Options must include '{x_col}' and '{y_col}'.")

    df["display_name"] = df.apply(_display_name, axis=1)

    fig, ax = plt.subplots(figsize=(7.8, 5.6), facecolor=BG)
    ax.set_facecolor(BG)

    for _, row in df.iterrows():
        if row.get("is_recommended", False):
            ax.scatter(row[x_col], row[y_col], s=220, marker="*", color=PRIMARY, zorder=4)
        elif row.get("is_existing_plan", False):
            ax.scatter(row[x_col], row[y_col], s=90, marker="s", color=BENCHMARK, zorder=3)
        else:
            ax.scatter(row[x_col], row[y_col], s=60, marker="o", color=ALTERNATIVE, zorder=2)

    _title_block(
        ax,
        title or "The recommended package improves flow without increasing cost",
        subtitle or "Lower and left is better: fewer late-running procedures at lower annual cost."
    )

    ax.set_xlabel("Procedures scheduled past room closing")
    ax.set_ylabel("Estimated total annual cost ($)")
    _style_axes(ax, "both")

    xpad = (df[x_col].max() - df[x_col].min()) * 0.12 if df[x_col].max() != df[x_col].min() else 5
    ypad = (df[y_col].max() - df[y_col].min()) * 0.18 if df[y_col].max() != df[y_col].min() else 5

    ax.set_xlim(df[x_col].min() - xpad * 0.4, df[x_col].max() + xpad * 0.7)
    ax.set_ylim(df[y_col].min() - ypad * 0.4, df[y_col].max() + ypad * 0.45)

    for _, row in df.iterrows():
        if row.get("is_recommended", False):
            offset = (8, 8)
            fsize = 10
            color = TEXT
        elif row.get("is_existing_plan", False):
            offset = (6, 6)
            fsize = 9
            color = TEXT
        else:
            offset = (6, 4)
            fsize = 8.5
            color = SUBTEXT

        ax.annotate(
            row["display_name"],
            (row[x_col], row[y_col]),
            textcoords="offset points",
            xytext=offset,
            fontsize=fsize,
            color=color,
        )

    if source_note:
        _source_note(fig, source_note)

    plt.tight_layout(rect=(0, 0.04, 1, 0.98))
    return fig


def plot_option_scorecard(options, title=None, subtitle=None, source_note=None):
    df = options_to_df(options).copy()
    if df["is_existing_plan"].sum() != 1:
        raise ValueError("plot_option_scorecard expects exactly one existing-plan benchmark.")

    base = df[df["is_existing_plan"]].iloc[0]
    others = df[~df["is_existing_plan"]].copy()
    others["display_name"] = others.apply(_display_name, axis=1)

    rows = []
    for _, row in others.iterrows():
        record = {"display_name": row["display_name"]}
        if pd.notna(row.get("overflow_total")) and pd.notna(base.get("overflow_total")) and base["overflow_total"] != 0:
            record["Late procedures"] = 100.0 * (base["overflow_total"] - row["overflow_total"]) / base["overflow_total"]
        if pd.notna(row.get("total_cost")) and pd.notna(base.get("total_cost")) and base["total_cost"] != 0:
            record["Total cost"] = 100.0 * (base["total_cost"] - row["total_cost"]) / base["total_cost"]
        if pd.notna(row.get("mean_room_utilization")) and pd.notna(base.get("mean_room_utilization")) and base["mean_room_utilization"] != 0:
            record["Utilization"] = 100.0 * (row["mean_room_utilization"] - base["mean_room_utilization"]) / base["mean_room_utilization"]
        if pd.notna(row.get("days_with_instances")) and pd.notna(base.get("days_with_instances")) and base["days_with_instances"] != 0:
            record["Overcapacity days"] = 100.0 * (base["days_with_instances"] - row["days_with_instances"]) / base["days_with_instances"]
        rows.append(record)

    comp = pd.DataFrame(rows).fillna(0.0)
    metrics = [c for c in comp.columns if c != "display_name"]
    if len(metrics) == 0:
        raise ValueError("No comparable metrics found for scorecard.")

    x = range(len(comp))
    width = 0.72 / len(metrics)
    fig, ax = plt.subplots(figsize=(11, 5), facecolor=BG)

    palette = [PRIMARY, "#e07878", BENCHMARK, "#a3c9a8"]
    for i, metric in enumerate(metrics):
        offset = (i - (len(metrics) - 1) / 2.0) * width
        ax.bar([j + offset for j in x], comp[metric], width=width, label=metric, color=palette[i % len(palette)])

    _title_block(
        ax,
        title or "The recommended redesign outperforms the existing plan on key metrics",
        subtitle or "Positive values indicate improvement relative to the current plan."
    )

    ax.axhline(0, color=GRID, linewidth=1)
    ax.set_xticks(list(x))
    ax.set_xticklabels(comp["display_name"])
    ax.set_ylabel("Improvement vs existing plan (%)")
    _style_axes(ax, "y")
    ax.legend(frameon=False, fontsize=9, ncol=min(len(metrics), 4), loc="upper left")

    if source_note:
        _source_note(fig, source_note)

    plt.tight_layout(rect=(0, 0.04, 1, 0.98))
    return fig


# -----------------------------------------------------------------------------
# Existing-plan benchmark helper
# -----------------------------------------------------------------------------

def add_existing_plan_option(options, *, hb_count=21, close_time="24:00", priority_rule="historical",
                             overflow_total=None, mean_room_utilization=None,
                             total_holding_bay_cost=None, total_close_cost=None,
                             days_with_instances=None, option_name=None):
    if option_name is None:
        option_name = (
            f"Existing plan\n"
            f"{priority_rule}\n"
            f"{hb_count} bays\n"
            f"{close_time}"
        )

    row = {
        "option_name": option_name,
        "priority_rule": priority_rule,
        "hb_count": hb_count,
        "close_time": close_time,
        "overflow_total": overflow_total,
        "mean_room_utilization": mean_room_utilization,
        "total_holding_bay_cost": total_holding_bay_cost,
        "total_close_cost": total_close_cost,
        "days_with_instances": days_with_instances,
        "is_existing_plan": True,
        "is_recommended": False,
    }

    if options is None:
        return [row]
    return list(options) + [row]

# -----------------------------------------------------------------------------
# Convenience bundle
# -----------------------------------------------------------------------------

def build_all_key_figures(summary, policy_results=None, options=None, source_note=None):
    figs = {
        "close_time_sensitivity": plot_close_time_sensitivity(summary),
        "close_time_days_with_demand": plot_close_time_days_with_demand(summary),
        "hb_total_cost": plot_hb_total_cost(summary),
        "hb_cost_components": plot_hb_cost_components(summary),
        "hb_service_constraint": plot_hb_service_constraint(summary),
        "close_time_total_cost": plot_close_time_total_cost(summary),
        "close_time_cost_components": plot_close_time_cost_components(summary),
    }

    if policy_results is not None:
        figs.update({
            "policy_overflow": plot_policy_overflow(policy_results),
            "policy_utilization": plot_policy_utilization(policy_results),
            "policy_hb_peaks": plot_policy_hb_peaks(policy_results),
            "policy_close_burden": plot_policy_close_burden(policy_results),
            "policy_scorecard": plot_policy_summary_scorecard(policy_results),
        })

    if options is not None:
        figs.update({
            "option_total_cost": plot_option_total_cost(options, source_note=source_note),
            "option_overflow": plot_option_overflow(options, source_note=source_note),
            "option_tradeoff": plot_option_tradeoff_scatter(options, source_note=source_note),
            "option_scorecard": plot_option_scorecard(options, source_note=source_note),
            "option_cost_components": plot_option_cost_components(options),
        })

    return figs
