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
    return "\n".join(parts) if len(parts) > 0 else "option"


# -----------------------------------------------------------------------------
# Policy comparison plots (from comparePriorityRules)
# -----------------------------------------------------------------------------

def plot_policy_overflow(results):
    df = _expand_policy_df(_ranked_to_df(results))
    fig, ax = plt.subplots(figsize=(9, 5))
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

    fig, ax = plt.subplots(figsize=(9, 5))
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
    fig, ax = plt.subplots(figsize=(9, 5))
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
    fig, ax = plt.subplots(figsize=(9, 5))
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
    fig, ax = plt.subplots(figsize=(10, 5))
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
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(df["close_time"], df["total_bay_hours_after_close"], marker="o")
    ax.set_title("Holding-bay demand remaining after closing time")
    ax.set_xlabel("Candidate close time")
    ax.set_ylabel("Total bay-hours after close")
    ax.tick_params(axis="x", rotation=30)
    fig.tight_layout()
    return fig



def plot_close_time_days_with_demand(summary):
    df = pd.DataFrame(summary["close_time_eval"])
    fig, ax = plt.subplots(figsize=(9, 5))
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
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(df["hb_count"], df["total_holding_bay_cost"], marker="o")
    ax.set_title("Total holding-bay cost by bay count")
    ax.set_xlabel("Number of holding bays")
    ax.set_ylabel("Total holding-bay cost")
    fig.tight_layout()
    return fig



def plot_hb_cost_components(summary):
    df = summary["cost_analysis"]["hb"]["cost_table"].copy().sort_values("hb_count")
    fig, ax = plt.subplots(figsize=(9, 5))
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

    fig, ax = plt.subplots(figsize=(8, 5))
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
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(df["close_time_hhmm"], df["total_cost"], marker="o")
    ax.set_title("Total cost by holding-bay close time")
    ax.set_xlabel("Holding-bay close time")
    ax.set_ylabel("Total cost")
    ax.tick_params(axis="x", rotation=30)
    fig.tight_layout()
    return fig



def plot_close_time_cost_components(summary):
    df = summary["cost_analysis"]["close"]["cost_table"].copy().sort_values("close_hours")
    fig, ax = plt.subplots(figsize=(9, 5))
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



def plot_option_total_cost(options):
    df = options_to_df(options).sort_values("total_cost")
    fig, ax = plt.subplots(figsize=(10, 5))

    colors = []
    for _, row in df.iterrows():
        if row["is_recommended"]:
            colors.append("tab:green")
        elif row["is_existing_plan"]:
            colors.append("tab:orange")
        else:
            colors.append("tab:blue")

    ax.bar(df["option_name"], df["total_cost"], color=colors)
    ax.set_title("Total cost by recommendation option")
    ax.set_xlabel("Recommendation option")
    ax.set_ylabel("Total cost")
    ax.tick_params(axis="x", rotation=0)
    _annotate_bar_values(ax, decimals=1)
    fig.tight_layout()
    return fig



def plot_option_cost_components(options):
    df = options_to_df(options).copy()
    hb = df["total_holding_bay_cost"] if "total_holding_bay_cost" in df.columns else pd.Series([0.0] * len(df))
    close = df["total_close_cost"] if "total_close_cost" in df.columns else pd.Series([0.0] * len(df))

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(df["option_name"], hb, label="Holding-bay cost")
    ax.bar(df["option_name"], close, bottom=hb, label="Close-time cost")
    ax.set_title("Cost components by recommendation option")
    ax.set_xlabel("Recommendation option")
    ax.set_ylabel("Cost")
    ax.tick_params(axis="x", rotation=0)
    ax.legend()
    fig.tight_layout()
    return fig



def plot_option_overflow(options):
    df = options_to_df(options).copy()
    if "overflow_total" not in df.columns:
        raise ValueError("Each option must include 'overflow_total'.")

    colors = []
    for _, row in df.iterrows():
        if row["is_recommended"]:
            colors.append("tab:green")
        elif row["is_existing_plan"]:
            colors.append("tab:orange")
        else:
            colors.append("tab:blue")

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(df["option_name"], df["overflow_total"], color=colors)
    ax.set_title("Late-running procedures by recommendation option")
    ax.set_xlabel("Recommendation option")
    ax.set_ylabel("Procedures scheduled past room closing")
    _annotate_bar_values(ax, decimals=0)
    fig.tight_layout()
    return fig



def plot_option_tradeoff_scatter(options, x_col="overflow_total", y_col="total_cost", label_col="option_name"):
    df = options_to_df(options).copy()
    if x_col not in df.columns or y_col not in df.columns:
        raise ValueError(f"Options must include '{x_col}' and '{y_col}'.")

    fig, ax = plt.subplots(figsize=(8, 6))

    base = df[(~df["is_existing_plan"]) & (~df["is_recommended"])]
    existing = df[df["is_existing_plan"]]
    recommended = df[df["is_recommended"]]

    if len(base) > 0:
        ax.scatter(base[x_col], base[y_col], label="Alternative options")
    if len(existing) > 0:
        ax.scatter(existing[x_col], existing[y_col], label="Existing plan", marker="s", s=90)
    if len(recommended) > 0:
        ax.scatter(recommended[x_col], recommended[y_col], label="Recommended option", marker="*", s=180)

    for _, row in df.iterrows():
        ax.annotate(row[label_col], (row[x_col], row[y_col]), textcoords="offset points", xytext=(5, 5), fontsize=9)

    ax.set_title(f"Tradeoff: {y_col.replace('_', ' ')} vs {x_col.replace('_', ' ')}")
    ax.set_xlabel(x_col.replace("_", " "))
    ax.set_ylabel(y_col.replace("_", " "))
    ax.legend()
    fig.tight_layout()
    return fig



def plot_option_scorecard(options):
    """
    Normalized scorecard for candidate recommendation packages.
    Higher is better.

    Uses these if present:
    - lower overflow_total is better
    - lower total_cost is better
    - lower days_with_instances is better
    - higher mean_room_utilization is better
    """
    df = options_to_df(options).copy()

    def best_when_low(series):
        if series.max() == series.min():
            return pd.Series([1.0] * len(series), index=series.index)
        return (series.max() - series) / (series.max() - series.min())

    def best_when_high(series):
        if series.max() == series.min():
            return pd.Series([1.0] * len(series), index=series.index)
        return (series - series.min()) / (series.max() - series.min())

    metrics = []
    labels = []

    if "overflow_total" in df.columns:
        df["score_overflow"] = best_when_low(df["overflow_total"])
        metrics.append("score_overflow")
        labels.append("Overflow")

    if "total_cost" in df.columns:
        df["score_total_cost"] = best_when_low(df["total_cost"])
        metrics.append("score_total_cost")
        labels.append("Total cost")

    if "days_with_instances" in df.columns:
        df["score_service"] = best_when_low(df["days_with_instances"])
        metrics.append("score_service")
        labels.append("Service")

    if "mean_room_utilization" in df.columns:
        df["score_utilization"] = best_when_high(df["mean_room_utilization"])
        metrics.append("score_utilization")
        labels.append("Utilization")

    if len(metrics) == 0:
        raise ValueError("No recognized metrics found in options for scorecard.")

    x = range(len(df))
    width = 0.8 / len(metrics)
    fig, ax = plt.subplots(figsize=(11, 5))

    for i, metric in enumerate(metrics):
        offset = (i - (len(metrics) - 1) / 2.0) * width
        ax.bar([j + offset for j in x], df[metric], width=width, label=labels[i])

    ax.set_xticks(list(x))
    ax.set_xticklabels(df["option_name"], rotation=0)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Normalized score (higher is better)")
    ax.set_title("Recommendation option scorecard")
    ax.legend()
    fig.tight_layout()
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
        option_name = f"Existing plan\\n{priority_rule}\\n{hb_count} bays\\n{close_time}"

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

def build_all_key_figures(summary, policy_results=None, options=None):
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
            "option_total_cost": plot_option_total_cost(options),
            "option_cost_components": plot_option_cost_components(options),
            "option_overflow": plot_option_overflow(options),
            "option_tradeoff": plot_option_tradeoff_scatter(options),
            "option_scorecard": plot_option_scorecard(options),
        })

    return figs
