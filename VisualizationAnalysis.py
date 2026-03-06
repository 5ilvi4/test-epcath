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

This version also supports comparison of full recommendation packages, e.g.:
- historical + 17 bays + 22:30
- historical + 18 bays + 22:30
- longest recovery first + 18 bays + 22:30
- shortest recovery first + 18 bays + 24:00

All functions return matplotlib Figure objects.
"""

import matplotlib.pyplot as plt
import pandas as pd

# Presentation palette
# Economist-like presentation palette
PRIMARY = "#C0392B"      # muted Economist-style red for recommendation
SECONDARY = "#C0392B"    # keep recommendation consistent
ACCENT = "#3B6EA5"       # restrained blue accent
BENCHMARK = "#6B7A8F"    # blue-gray for existing plan
ALTERNATIVE = "#D9DDE3"  # soft gray for other options
GRID = "#E6E6E6"
TEXT = "#222222"
BG = "#F7F5F2"


def _style_axes(ax, grid_axis="x"):
    ax.set_facecolor(BG)
    ax.grid(axis=grid_axis, alpha=1.0, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color("#CFCFCF")
    ax.tick_params(colors=TEXT, length=0)
    ax.title.set_color(TEXT)
    ax.xaxis.label.set_color(TEXT)
    ax.yaxis.label.set_color(TEXT)


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
        )



def _build_option_label(row, policy_col="priority_rule", hb_col="hb_count", close_col="close_time"):
    parts = []
    if policy_col in row and pd.notna(row[policy_col]):
        parts.append(str(row[policy_col]))
    if hb_col in row and pd.notna(row[hb_col]):
        parts.append(str(int(row[hb_col])) + " bays")
    if close_col in row and pd.notna(row[close_col]):
        parts.append("close " + str(row[close_col]))
    return "
".join(parts) if len(parts) > 0 else "option"



def _short_option_label(label: str) -> str:
    """Compact labels for slides and charts."""
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


# -----------------------------------------------------------------------------
# Policy comparison plots (from comparePriorityRules)
# -----------------------------------------------------------------------------

def plot_policy_overflow(results):
    df = _expand_policy_df(_ranked_to_df(results))
    fig, ax = plt.subplots(figsize=(9, 5), facecolor=BG)
    ax.bar(df["priority_rule"], df["overflow_total"])
    ax.set_title("Late-running procedures by scheduling policy")
    ax.set_xlabel("Scheduling policy")
    ax.set_ylabel("Procedures scheduled past room closing")
    ax.tick_params(axis="x", rotation=20)
    _annotate_bar_values(ax, decimals=0)
    fig.tight_layout()
    return fig



def plot_policy_utilization(results):
    df = _expand_policy_df(_ranked_to_df(results))
    x = range(len(df))
    width = 0.38

    fig, ax = plt.subplots(figsize=(9, 5), facecolor=BG)
    ax.bar([i - width / 2 for i in x], df["cath_utilization_avg"], width=width, label="Cath")
    ax.bar([i + width / 2 for i in x], df["ep_utilization_avg"], width=width, label="EP")

    ax.set_xticks(list(x))
    ax.set_xticklabels(df["priority_rule"], rotation=20)
    ax.set_title("Average room utilization by scheduling policy")
    ax.set_xlabel("Scheduling policy")
    ax.set_ylabel("Average utilization")
    ax.legend()
    fig.tight_layout()
    return fig



def plot_policy_hb_peaks(results):
    df = _expand_policy_df(_ranked_to_df(results))
    fig, ax = plt.subplots(figsize=(9, 5), facecolor=BG)
    ax.bar(df["priority_rule"], df["recommended_bays_p95"])
    ax.set_title("Recommended holding bays (P95) by scheduling policy")
    ax.set_xlabel("Scheduling policy")
    ax.set_ylabel("Recommended holding bays")
    ax.tick_params(axis="x", rotation=20)
    _annotate_bar_values(ax, decimals=0)
    fig.tight_layout()
    return fig



def plot_policy_close_burden(results):
    df = _expand_policy_df(_ranked_to_df(results))
    fig, ax = plt.subplots(figsize=(9, 5), facecolor=BG)
    ax.bar(df["priority_rule"], df["last_occupied_p95_hours"])
    ax.set_title("P95 last occupied time by scheduling policy")
    ax.set_xlabel("Scheduling policy")
    ax.set_ylabel("Hours since midnight")
    ax.tick_params(axis="x", rotation=20)
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

    ax.set_xticks(list(x))
    ax.set_xticklabels(df["priority_rule"], rotation=20)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Normalized score (higher is better)")
    ax.set_title("Policy comparison scorecard")
    ax.legend()
    fig.tight_layout()
    return fig


# -----------------------------------------------------------------------------
# Summary-based plots (from one RunSimulation summary)
# -----------------------------------------------------------------------------

def plot_close_time_sensitivity(summary):
    df = pd.DataFrame(summary["close_time_eval"])
    fig, ax = plt.subplots(figsize=(9, 5), facecolor=BG)
    ax.plot(df["close_time"], df["total_bay_hours_after_close"], marker="o")
    ax.set_title("Holding-bay demand remaining after closing time")
    ax.set_xlabel("Candidate close time")
    ax.set_ylabel("Total bay-hours after close")
    ax.tick_params(axis="x", rotation=30)
    fig.tight_layout()
    return fig



def plot_close_time_days_with_demand(summary):
    df = pd.DataFrame(summary["close_time_eval"])
    fig, ax = plt.subplots(figsize=(9, 5), facecolor=BG)
    ax.bar(df["close_time"], df["days_with_any_demand_after_close"])
    ax.set_title("Days with any demand after close")
    ax.set_xlabel("Candidate close time")
    ax.set_ylabel("Days")
    ax.tick_params(axis="x", rotation=30)
    _annotate_bar_values(ax, decimals=0)
    fig.tight_layout()
    return fig


# -----------------------------------------------------------------------------
# Cost-analysis plots (from summary['cost_analysis'])
# -----------------------------------------------------------------------------

def plot_hb_total_cost(summary):
    df = summary["cost_analysis"]["hb"]["cost_table"].copy().sort_values("hb_count")
    fig, ax = plt.subplots(figsize=(8, 5), facecolor=BG)
    ax.plot(df["hb_count"], df["total_holding_bay_cost"], marker="o")
    ax.set_title("Total holding-bay cost by bay count")
    ax.set_xlabel("Number of holding bays")
    ax.set_ylabel("Total holding-bay cost")
    fig.tight_layout()
    return fig



def plot_hb_cost_components(summary):
    df = summary["cost_analysis"]["hb"]["cost_table"].copy().sort_values("hb_count")
    fig, ax = plt.subplots(figsize=(9, 5), facecolor=BG)
    ax.bar(df["hb_count"], df["cancellation_cost"], label="Cancellation cost")
    ax.bar(df["hb_count"], df["empty_holding_bay_cost"], bottom=df["cancellation_cost"], label="Empty-bay cost")
    ax.set_title("Holding-bay cost components")
    ax.set_xlabel("Number of holding bays")
    ax.set_ylabel("Cost")
    ax.legend()
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
    ax.plot(df["hb_count"], df["days_with_instances"], marker="o")
    ax.axhline(threshold_days, linestyle="--", label=f"Service threshold ({threshold_days:.0f} days)")
    ax.set_title("Service constraint by holding-bay count")
    ax.set_xlabel("Number of holding bays")
    ax.set_ylabel("Days with >=1 overcapacity event")
    ax.legend()
    fig.tight_layout()
    return fig



def plot_close_time_total_cost(summary):
    df = summary["cost_analysis"]["close"]["cost_table"].copy().sort_values("close_hours")
    fig, ax = plt.subplots(figsize=(9, 5), facecolor=BG)
    ax.plot(df["close_time_hhmm"], df["total_cost"], marker="o")
    ax.set_title("Total cost by holding-bay close time")
    ax.set_xlabel("Holding-bay close time")
    ax.set_ylabel("Total cost")
    ax.tick_params(axis="x", rotation=30)
    fig.tight_layout()
    return fig



def plot_close_time_cost_components(summary):
    df = summary["cost_analysis"]["close"]["cost_table"].copy().sort_values("close_hours")
    fig, ax = plt.subplots(figsize=(9, 5), facecolor=BG)
    ax.bar(df["close_time_hhmm"], df["estimated_labor_cost"], label="Labor cost")
    ax.bar(df["close_time_hhmm"], df["admission_cost"], bottom=df["estimated_labor_cost"], label="Admission cost")
    ax.set_title("Close-time cost components")
    ax.set_xlabel("Holding-bay close time")
    ax.set_ylabel("Cost")
    ax.tick_params(axis="x", rotation=30)
    ax.legend()
    fig.tight_layout()
    return fig


# -----------------------------------------------------------------------------
# Recommendation option comparison
# -----------------------------------------------------------------------------

def options_to_df(options):
    """
    Convert a list of recommendation options into a DataFrame.

    Each option can contain fields like:
    - option_name
    - priority_rule
    - hb_count
    - close_time
    - overflow_total
    - mean_room_utilization
    - total_holding_bay_cost
    - total_close_cost
    - total_cost
    - days_with_instances
    - admitted_patients_95
    - is_existing_plan
    - is_recommended
    """
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
    df["label_short"] = df["option_name"].apply(_short_option_label)
    df = df.sort_values("total_cost", ascending=True)

    colors = []
    for _, row in df.iterrows():
        if row["is_recommended"]:
            colors.append(SECONDARY)
        elif row["is_existing_plan"]:
            colors.append(BENCHMARK)
        else:
            colors.append(ALTERNATIVE)

    fig, ax = plt.subplots(figsize=(9, 5), facecolor=BG)
    ax.barh(df["label_short"], df["total_cost"], color=colors, height=0.65)
    ax.set_title(
        title or "Recommended redesign keeps annual cost below the existing plan",
        loc="left", fontsize=14, fontweight="bold"
    )
    if subtitle:
        ax.text(0, 1.04, subtitle, transform=ax.transAxes, ha="left", va="bottom", fontsize=9, color=TEXT)
    ax.set_xlabel("Estimated total cost ($)")
    ax.set_ylabel("")
    _style_axes(ax, grid_axis="x")

    for i, v in enumerate(df["total_cost"]):
        ax.text(v, i, f"  ${v:,.0f}", va="center", fontsize=9, color=TEXT)

    if source_note:
        fig.text(0.01, 0.01, source_note, ha="left", va="bottom", fontsize=8, color="#666666")

    fig.tight_layout(rect=(0, 0.03, 1, 1))
    return fig



def plot_option_cost_components(options):
    df = options_to_df(options).copy()
    hb = df["total_holding_bay_cost"] if "total_holding_bay_cost" in df.columns else pd.Series([0.0] * len(df))
    close = df["total_close_cost"] if "total_close_cost" in df.columns else pd.Series([0.0] * len(df))

    fig, ax = plt.subplots(figsize=(10, 5), facecolor=BG)
    ax.bar(df["option_name"], hb, label="Holding-bay cost")
    ax.bar(df["option_name"], close, bottom=hb, label="Close-time cost")
    ax.set_title("Cost components by recommendation option")
    ax.set_xlabel("Recommendation option")
    ax.set_ylabel("Cost")
    ax.tick_params(axis="x", rotation=0)
    ax.legend()
    fig.tight_layout()
    return fig



def plot_option_overflow(options, title=None, subtitle=None, source_note=None):
    df = options_to_df(options).copy()
    if "overflow_total" not in df.columns:
        raise ValueError("Each option must include 'overflow_total'.")
    df["label_short"] = df["option_name"].apply(_short_option_label)
    df = df.sort_values("overflow_total", ascending=True)

    colors = []
    for _, row in df.iterrows():
        if row["is_recommended"]:
            colors.append(SECONDARY)
        elif row["is_existing_plan"]:
            colors.append(BENCHMARK)
        else:
            colors.append(ALTERNATIVE)

    fig, ax = plt.subplots(figsize=(9, 5), facecolor=BG)
    ax.barh(df["label_short"], df["overflow_total"], color=colors, height=0.65)
    ax.set_title(
        title or "Scheduling by longest recovery time reduces late-running procedures",
        loc="left", fontsize=14, fontweight="bold"
    )
    if subtitle:
        ax.text(0, 1.04, subtitle, transform=ax.transAxes, ha="left", va="bottom", fontsize=9, color=TEXT)
    ax.set_xlabel("Procedures scheduled past room closing")
    ax.set_ylabel("")
    _style_axes(ax, grid_axis="x")

    for i, v in enumerate(df["overflow_total"]):
        ax.text(v, i, f"  {int(v)}", va="center", fontsize=9, color=TEXT)

    if source_note:
        fig.text(0.01, 0.01, source_note, ha="left", va="bottom", fontsize=8, color="#666666")

    fig.tight_layout(rect=(0, 0.03, 1, 1))
    return fig



def plot_option_tradeoff_scatter(options, x_col="overflow_total", y_col="total_cost", label_col="option_name", title=None, subtitle=None, source_note=None):
    df = options_to_df(options).copy()
    if x_col not in df.columns or y_col not in df.columns:
        raise ValueError(f"Options must include '{x_col}' and '{y_col}'.")
    df["label_short"] = df[label_col].apply(_short_option_label)

    fig, ax = plt.subplots(figsize=(8, 6), facecolor=BG)

    base = df[(~df["is_existing_plan"]) & (~df["is_recommended"])]
    existing = df[df["is_existing_plan"]]
    recommended = df[df["is_recommended"]]

    if len(base) > 0:
        ax.scatter(base[x_col], base[y_col], color=ALTERNATIVE, s=55)
    if len(existing) > 0:
        ax.scatter(existing[x_col], existing[y_col], color=BENCHMARK, marker="s", s=110)
    if len(recommended) > 0:
        ax.scatter(recommended[x_col], recommended[y_col], color=SECONDARY, marker="*", s=240)

    for _, row in existing.iterrows():
        ax.annotate(row["label_short"], (row[x_col], row[y_col]), textcoords="offset points", xytext=(6, 6), fontsize=8, color=TEXT)
    for _, row in recommended.iterrows():
        ax.annotate(row["label_short"], (row[x_col], row[y_col]), textcoords="offset points", xytext=(6, 6), fontsize=8, color=TEXT)
    for _, row in base.iterrows():
        ax.annotate(row["label_short"], (row[x_col], row[y_col]), textcoords="offset points", xytext=(4, 4), fontsize=7, color="#777777")

    ax.set_title(
        title or "The recommended package improves flow without raising total cost",
        loc="left", fontsize=14, fontweight="bold"
    )
    if subtitle:
        ax.text(0, 1.04, subtitle, transform=ax.transAxes, ha="left", va="bottom", fontsize=9, color=TEXT)
    ax.set_xlabel("Procedures scheduled past room closing")
    ax.set_ylabel("Estimated total cost ($)")
    ax.grid(alpha=1.0, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#CFCFCF")
    ax.spines["bottom"].set_color("#CFCFCF")
    ax.tick_params(colors=TEXT, length=0)

    if source_note:
        fig.text(0.01, 0.01, source_note, ha="left", va="bottom", fontsize=8, color="#666666")

    fig.tight_layout(rect=(0, 0.03, 1, 1))
    return fig



def plot_option_scorecard(options, title=None, subtitle=None, source_note=None):
    """
    Clearer comparison vs the existing plan.
    Shows percentage improvement where possible.
    Positive values are better than the existing plan.
    """
    df = options_to_df(options).copy()
    if df["is_existing_plan"].sum() != 1:
        raise ValueError("plot_option_scorecard expects exactly one existing-plan benchmark.")

    base = df[df["is_existing_plan"]].iloc[0]
    others = df[~df["is_existing_plan"]].copy()
    others["label_short"] = others["option_name"].apply(_short_option_label)

    rows = []
    for _, row in others.iterrows():
        record = {"label_short": row["label_short"]}
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
    metrics = [c for c in comp.columns if c != "label_short"]
    if len(metrics) == 0:
        raise ValueError("No comparable metrics found for scorecard.")

    x = range(len(comp))
    width = 0.72 / len(metrics)
    fig, ax = plt.subplots(figsize=(11, 5), facecolor=BG)

    palette = [PRIMARY, ACCENT, BENCHMARK, "#A88E62"]
    for i, metric in enumerate(metrics):
        offset = (i - (len(metrics) - 1) / 2.0) * width
        ax.bar([j + offset for j in x], comp[metric], width=width, label=metric, color=palette[i % len(palette)])

    ax.axhline(0, color="#7A8793", linewidth=1)
    ax.set_xticks(list(x))
    ax.set_xticklabels(comp["label_short"])
    ax.set_ylabel("Improvement vs existing plan (%)")
    ax.set_title(
        title or "The recommended redesign outperforms the existing plan on key metrics",
        loc="left", fontsize=14, fontweight="bold"
    )
    if subtitle:
        ax.text(0, 1.04, subtitle, transform=ax.transAxes, ha="left", va="bottom", fontsize=9, color=TEXT)
    ax.legend(frameon=False, fontsize=9, labelcolor=TEXT, ncol=min(len(metrics), 4), loc="upper left")
    _style_axes(ax, grid_axis="y")

    if source_note:
        fig.text(0.01, 0.01, source_note, ha="left", va="bottom", fontsize=8, color="#666666")

    fig.tight_layout(rect=(0, 0.03, 1, 1))
    return fig


# -----------------------------------------------------------------------------
# Existing-plan benchmark helper
# -----------------------------------------------------------------------------

def add_existing_plan_option(options, *, hb_count=21, close_time="24:00", priority_rule="historical",
                             overflow_total=None, mean_room_utilization=None,
                             total_holding_bay_cost=None, total_close_cost=None,
                             days_with_instances=None, option_name=None):
    """
    Append the hospital's existing/proposed plan as a benchmark option.

    Typical use:
    - hb_count=21
    - close_time='24:00'
    - priority_rule='historical'

    Example:
        options = add_existing_plan_option(
            options,
            hb_count=21,
            close_time='24:00',
            priority_rule='historical',
            overflow_total=144,
            mean_room_utilization=0.4939,
            total_holding_bay_cost=131.0,
            total_close_cost=1700.0,
            days_with_instances=0,
        )
    """
    if option_name is None:
        option_name = f"Existing plan
{priority_rule}
{hb_count} bays
{close_time}"

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
