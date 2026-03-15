import os
import sys

# ── path & chdir setup (must happen before any project imports) ───────────────
_repo_root = os.path.dirname(os.path.abspath(__file__))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

_orig_chdir = os.chdir
def _safe_chdir(path):
    if "/content/test-epcath" in str(path):
        return
    _orig_chdir(path)
os.chdir = _safe_chdir
_safe_chdir(_repo_root)

# ── imports ───────────────────────────────────────────────────────────────────
import io
import random
import streamlit as st
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
matplotlib.rcParams.update({
    "text.color":           "#e2e8f0",
    "axes.labelcolor":      "#e2e8f0",
    "axes.titlecolor":      "#f1f5f9",
    "xtick.color":          "#94a3b8",
    "ytick.color":          "#94a3b8",
    "legend.facecolor":     "#1a2233",
    "legend.edgecolor":     "#2a3547",
    "legend.labelcolor":    "#e2e8f0",
    "figure.max_open_warning": 0,   # suppress batch-creation warning; figures are closed in _show_fig
})
import pandas as pd
import numpy as np

from Params import Params
import Simulation
import VisualizationAnalysis as VA
from CostAnalysis import (
    HoldingBayCostParams, CloseTimeCostParams,
    summarize_hb_decision, summarize_close_time_decision,
    compute_hb_cost_table,
)

# ── constants ─────────────────────────────────────────────────────────────────
SCENARIOS = {
    "Historical (Flat Cath / Flat EP)": "historical",
    "High-volume EP (+2 EP providers)": "two additional high-volume EP providers",
    "Cath lab only": "CATH lab only",
}

PRIORITY_RULES = [
    "historical",
    "longest procedures first",
    "shortest procedures first",
    "longest recovery time first",
    "shortest recovery time first",
]

PROC_COLS = [
    "day", "week", "lab", "proc_time_min", "sched_horizon",
    "room_constraint", "pre_time_hr", "post_time_hr", "proc_type",
    "provider", "pre_clean_hr", "post_clean_hr", "hist_order",
    "proc_time_no_to", "post_to_time", "proc_id",
]

SHIFT_COLS = ["day", "shift_length_hr", "num_procedures", "shift_type", "lab", "provider", "room_constraint"]

LAB_MAP     = {0.0: "Cath", 1.0: "EP"}
HORIZON_MAP = {1: "Emergency", 2: "Same day", 3: "Same week"}
ROOM_MAP    = {0.0: "Cath only", 1.0: "EP only", 2.0: "Flexible"}
SHIFT_MAP   = {0.25: "Quarter day", 0.5: "Half day", 1.0: "Full day"}

BG   = "#1a2233"   # chart face — matches Streamlit secondary bg
C1   = "#e07878"   # coral red  (Cath)
C2   = "#5b9bd5"   # blue       (EP)
C3   = "#7a8ba0"   # muted slate
GRID = "#2a3547"   # subtle grid
TEXT = "#e2e8f0"   # light text on dark backgrounds

CURRENT_HB_COUNT = 21   # existing plan bay count

# Default (baseline) parameter values — used to detect when user has changed something
# and to run a cached baseline simulation for comparison
BASELINE_SCENARIO_KEY  = "historical"
BASELINE_PRIORITY_RULE = "historical"
BASELINE_CATH_ROOMS    = 5
BASELINE_HB_CLEAN_TIME = 0.10
BASELINE_RESOLUTION    = 5.0

# Cost assumptions (from CostAnalysis.py)
COST_ASSUMPTIONS = {
    "Contribution margin lost per cancellation": "$600",
    "Empty holding bay cost per idle hour":      "$10",
    "Max days with overcapacity (service rule)": "5% of days",
    "Patient admission cost (close too early)":  "$230 per patient",
    "Nurse-to-patient ratio":                    "1 nurse : 4 patients",
    "Base nursing wage":                         "$48 / hour",
    "Overtime multiplier":                       "1.5× ($72 / hour)",
    "Baseline close time":                       "17:00",
}

def _show_fig(fig):
    """Render a matplotlib figure to PNG bytes and display via st.image().

    st.pyplot() in Streamlit 1.55 can raise MediaFileStorageError when the
    figure object is garbage-collected before the browser fetches the image.
    Writing to a BytesIO buffer first avoids that race condition.
    """
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    buf.seek(0)
    plt.close(fig)
    st.image(buf)

def _fmt_close(t):
    """Format a close-time value (string 'HH:MM' or float hours) for display.

    The simulation tracks holding-bay bins up to 40 h past midnight, so the
    raw P95 last-occupied time can exceed 24:00 when late procedures push
    recovery into the next calendar day.  We detect that and show it as
    'next day HH:MM' so planners aren't confused by '31:20' or '36.83'.
    """
    if t is None:
        return "—"
    # Handle float/int hours directly (e.g. 36.833 → next day 12:50)
    if isinstance(t, (int, float)):
        total = int(round(float(t) * 60))
        hh, mm = total // 60, total % 60
        if hh >= 24:
            return f"next day {hh % 24:02d}:{mm:02d}"
        return f"{hh:02d}:{mm:02d}"
    s = str(t).strip()
    try:
        parts = s.split(":")
        hh = int(parts[0])
        mm = int(parts[1]) if len(parts) > 1 else 0
        if hh >= 24:
            return f"next day {hh % 24:02d}:{mm:02d}"
        return f"{hh:02d}:{mm:02d}"
    except Exception:
        return s

def _show_run_config(scenario_label, priority_rule, num_cath_rooms, hb_clean_time, resolution, compare_policies):
    """Render a compact banner showing the parameters used for the current simulation run."""
    parts = [
        f"**Scenario:** {scenario_label}",
        f"**Priority rule:** {priority_rule}",
        f"**Cath rooms:** {num_cath_rooms}",
        f"**HB clean time:** {hb_clean_time:.2f} h",
        f"**Resolution:** {int(resolution)} min",
    ]
    if compare_policies:
        parts.append("**Policies compared:** all 5")
    st.caption("Configuration used for this run — " + " · ".join(parts))


def _is_baseline_run(scenario_key, priority_rule, num_cath_rooms, hb_clean_time, resolution):
    return (
        scenario_key == BASELINE_SCENARIO_KEY
        and priority_rule == BASELINE_PRIORITY_RULE
        and num_cath_rooms == BASELINE_CATH_ROOMS
        and abs(hb_clean_time - BASELINE_HB_CLEAN_TIME) < 0.001
        and resolution == BASELINE_RESOLUTION
    )


def _show_baseline_comparison(summary, baseline):
    """Render a compact delta comparison between the current run and the baseline."""
    hb  = summary["holding_bay"]
    bhb = baseline["holding_bay"]

    st.markdown("**How this run compares to the default baseline** *(Historical scenario · historical priority · 5 Cath rooms · 0.10 h cleaning · 5 min resolution)*")

    d1, d2, d3 = st.columns(3)
    hb_delta = hb["recommended_bays_p95"] - bhb["recommended_bays_p95"]
    d1.metric(
        "Recommended HB bays",
        f"{hb['recommended_bays_p95']}",
        delta=f"{hb_delta:+d} vs baseline ({bhb['recommended_bays_p95']})",
        delta_color="inverse",  # more bays = more cost = shown in red
        help="Baseline: historical scenario, historical priority, 5 rooms, 0.10h cleaning, 5 min resolution",
    )

    cath_delta = round((summary["cath_utilization_avg"] - baseline["cath_utilization_avg"]) * 100, 1)
    d2.metric(
        "Cath utilization",
        f"{round(summary['cath_utilization_avg'] * 100, 1)}%",
        delta=f"{cath_delta:+.1f}pp vs baseline ({round(baseline['cath_utilization_avg']*100,1)}%)",
    )

    ep_delta = round((summary["ep_utilization_avg"] - baseline["ep_utilization_avg"]) * 100, 1)
    d3.metric(
        "EP utilization",
        f"{round(summary['ep_utilization_avg'] * 100, 1)}%",
        delta=f"{ep_delta:+.1f}pp vs baseline ({round(baseline['ep_utilization_avg']*100,1)}%)",
    )

    d4, d5, d6 = st.columns(3)
    overflow_delta = summary["overflow_total"] - baseline["overflow_total"]
    d4.metric(
        "Overflow procedures",
        str(summary["overflow_total"]),
        delta=f"{overflow_delta:+d} vs baseline ({baseline['overflow_total']})",
        delta_color="inverse",
    )

    peak_delta = round(hb["peak_bays_p95"] - bhb["peak_bays_p95"], 1)
    d5.metric(
        "HB peak P95",
        f"{hb['peak_bays_p95']:.1f} bays",
        delta=f"{peak_delta:+.1f} vs baseline ({bhb['peak_bays_p95']:.1f})",
        delta_color="inverse",
    )

    close_delta_h = round(hb["last_occupied_p95_hours"] - bhb["last_occupied_p95_hours"], 2)
    close_sign = "earlier" if close_delta_h < 0 else "later"
    d6.metric(
        "Rec. close time (P95)",
        _fmt_close(hb["recommended_close_p95"]),
        delta=f"{abs(close_delta_h):.2f} h {close_sign} than baseline ({_fmt_close(bhb['recommended_close_p95'])})",
        delta_color="inverse" if close_delta_h > 0 else "normal",
    )


def _style(ax, grid_axis="y"):
    ax.set_facecolor(BG)
    ax.grid(axis=grid_axis, color=GRID, linewidth=0.6, alpha=0.8)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#2a3547")
    ax.tick_params(length=0, labelsize=9)

# ── data loaders ──────────────────────────────────────────────────────────────
@st.cache_data
def load_proc_data(path):
    df = pd.read_csv(path, header=None, names=PROC_COLS)
    df["lab_name"]     = df["lab"].map(LAB_MAP)
    df["horizon_name"] = df["sched_horizon"].map(HORIZON_MAP).fillna("Unknown")
    df["room_name"]    = df["room_constraint"].map(ROOM_MAP).fillna("Other")
    return df

@st.cache_data
def load_shift_data(path):
    df = pd.read_csv(path, header=None, names=SHIFT_COLS)
    df["lab_name"]   = df["lab"].map(LAB_MAP)
    df["shift_name"] = df["shift_type"].map(SHIFT_MAP).fillna("Unknown")
    return df

def get_file_paths(scenario_key):
    p = Params()
    p.wFiles.value = scenario_key
    p.getScenarioFileNames()
    return p.procDataFile, p.shiftDataFile

@st.cache_data
def get_baseline_cost_table():
    """Cost table from hardcoded case data — no simulation needed."""
    overcap_rows, empty_rows, _ = Simulation.buildCostInputsFromCaseTables()
    return compute_hb_cost_table(overcap_rows, empty_rows, params=HoldingBayCostParams())

@st.cache_data
def get_baseline_simulation_summary():
    """Run the default configuration once and cache it for comparison."""
    random.seed(30)
    p = make_params(
        BASELINE_SCENARIO_KEY, BASELINE_PRIORITY_RULE,
        BASELINE_HB_CLEAN_TIME, BASELINE_CATH_ROOMS, BASELINE_RESOLUTION,
    )
    _, bsummary = Simulation.RunSimulation(
        p, saveOutputs=False, printStats=False,
        printRecommendations=False, showVisualizations=False,
        policyResults=None,
    )
    return bsummary

@st.cache_resource(show_spinner=False)
def _cached_simulation(scenario_key, priority_rule, num_cath_rooms, hb_clean_time, resolution, compare_policies, _v=13):
    """Run simulation once per unique parameter set; result shared across all user sessions."""
    random.seed(30)
    p = make_params(scenario_key, priority_rule, hb_clean_time, num_cath_rooms, resolution)

    policy_results, policy_best = None, None
    if compare_policies:
        _pr = Simulation.comparePriorityRules(p, saveResults=False)
        policy_results = _pr["ranked"]
        policy_best    = _pr["best"]

    random.seed(30)
    timePeriod, summary = Simulation.RunSimulation(
        p,
        saveOutputs=False,
        printStats=False,
        printRecommendations=False,
        showVisualizations=False,
        policyResults=policy_results,
    )
    return timePeriod, summary, policy_results, policy_best


# ── EDA chart functions ───────────────────────────────────────────────────────
def plot_volume_by_lab(df):
    counts = df["lab_name"].value_counts()
    fig, ax = plt.subplots(figsize=(5, 3.5), facecolor=BG)
    bars = ax.bar(counts.index, counts.values, color=[C1, C2], width=0.5)
    ax.bar_label(bars, padding=4, fontsize=9)
    ax.set_title("Procedures by lab", fontsize=11, fontweight="bold", loc="left")
    ax.set_ylabel("Procedures")
    _style(ax)
    fig.tight_layout()
    return fig

def plot_proc_duration(df):
    fig, ax = plt.subplots(figsize=(6, 3.5), facecolor=BG)
    for lab, color in [("Cath", C1), ("EP", C2)]:
        sub = df[df["lab_name"] == lab]["proc_time_min"]
        ax.hist(sub, bins=40, alpha=0.7, color=color, label=lab, edgecolor="none")
    ax.set_title("Procedure duration distribution", fontsize=11, fontweight="bold", loc="left")
    ax.set_xlabel("Duration (minutes)")
    ax.set_ylabel("Count")
    ax.legend(frameon=False, fontsize=9)
    _style(ax, "y")
    fig.tight_layout()
    return fig

def plot_horizon(df):
    counts = df["horizon_name"].value_counts().reindex(["Same week", "Same day", "Emergency"], fill_value=0)
    fig, ax = plt.subplots(figsize=(5, 3.5), facecolor=BG)
    bars = ax.barh(counts.index, counts.values, color=[C1, C2, "#E67E22"], height=0.5)
    ax.bar_label(bars, padding=4, fontsize=9)
    ax.set_title("Scheduling horizon", fontsize=11, fontweight="bold", loc="left")
    ax.set_xlabel("Procedures")
    _style(ax, "x")
    fig.tight_layout()
    return fig

def plot_pre_post_times(df):
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.5), facecolor=BG)
    fig.patch.set_facecolor(BG)
    for ax, col, title in zip(
        axes,
        ["pre_time_hr", "post_time_hr"],
        ["Pre-procedure HB time (hours)", "Post-procedure HB time (hours)"],
    ):
        ax.hist(df[col].clip(upper=df[col].quantile(0.99)), bins=40, color=C1, edgecolor="none", alpha=0.85)
        ax.set_title(title, fontsize=10, fontweight="bold", loc="left")
        ax.set_xlabel("Hours")
        ax.set_ylabel("Count")
        _style(ax, "y")
    fig.tight_layout()
    return fig

def plot_daily_volume(df):
    daily = df.groupby(["day", "lab_name"]).size().unstack(fill_value=0)
    fig, ax = plt.subplots(figsize=(9, 3.5), facecolor=BG)
    if "Cath" in daily.columns:
        ax.plot(daily.index, daily["Cath"], color=C1, linewidth=0.9, label="Cath", alpha=0.85)
    if "EP" in daily.columns:
        ax.plot(daily.index, daily["EP"], color=C2, linewidth=0.9, label="EP", alpha=0.85)
    ax.set_title("Daily procedure volume over simulation period", fontsize=11, fontweight="bold", loc="left")
    ax.set_xlabel("Day")
    ax.set_ylabel("Procedures")
    ax.legend(frameon=False, fontsize=9)
    _style(ax, "y")
    fig.tight_layout()
    return fig

def plot_provider_workload(df):
    top = df["provider"].value_counts().head(20)
    fig, ax = plt.subplots(figsize=(8, 4), facecolor=BG)
    ax.barh(top.index.astype(str)[::-1], top.values[::-1], color=C1, height=0.6)
    ax.set_title("Top 20 providers by procedure volume", fontsize=11, fontweight="bold", loc="left")
    ax.set_xlabel("Procedures")
    _style(ax, "x")
    fig.tight_layout()
    return fig

def plot_shift_types(sdf):
    counts = sdf["shift_name"].value_counts().reindex(["Full day", "Half day", "Quarter day"], fill_value=0)
    fig, ax = plt.subplots(figsize=(5, 3.5), facecolor=BG)
    bars = ax.bar(counts.index, counts.values, color=[C1, C2, C3], width=0.5)
    ax.bar_label(bars, padding=4, fontsize=9)
    ax.set_title("Shift types", fontsize=11, fontweight="bold", loc="left")
    ax.set_ylabel("Shifts")
    _style(ax)
    fig.tight_layout()
    return fig

def plot_shift_load(sdf):
    daily = sdf.groupby(["day", "lab_name"])["num_procedures"].sum().unstack(fill_value=0)
    fig, ax = plt.subplots(figsize=(9, 3.5), facecolor=BG)
    if "Cath" in daily.columns:
        ax.plot(daily.index, daily["Cath"], color=C1, linewidth=0.9, label="Cath", alpha=0.85)
    if "EP" in daily.columns:
        ax.plot(daily.index, daily["EP"], color=C2, linewidth=0.9, label="EP", alpha=0.85)
    ax.set_title("Daily provider capacity (procedures scheduled per day)", fontsize=11, fontweight="bold", loc="left")
    ax.set_xlabel("Day")
    ax.set_ylabel("Scheduled procedures")
    ax.legend(frameon=False, fontsize=9)
    _style(ax, "y")
    fig.tight_layout()
    return fig

# ── cost context chart functions ──────────────────────────────────────────────
def plot_post_time_by_lab(df):
    """Average post-procedure HB time by lab — shows who drives HB demand."""
    avg = df.groupby("lab_name")["post_time_hr"].mean()
    fig, ax = plt.subplots(figsize=(5, 3.5), facecolor=BG)
    bars = ax.bar(avg.index, avg.values, color=[C1, C2], width=0.5)
    ax.bar_label(bars, fmt="%.2f hrs", padding=4, fontsize=9)
    ax.set_title("Avg post-procedure HB time by lab", fontsize=11, fontweight="bold", loc="left")
    ax.set_ylabel("Hours")
    _style(ax)
    fig.tight_layout()
    return fig

def plot_hb_demand_by_type(df):
    """Top procedure types by avg post-procedure HB time."""
    type_stats = (
        df.groupby("proc_type")["post_time_hr"]
        .agg(avg="mean", count="count")
        .query("count >= 20")
        .nlargest(15, "avg")
        .reset_index()
    )
    fig, ax = plt.subplots(figsize=(8, 4), facecolor=BG)
    ax.barh(
        type_stats["proc_type"].astype(str)[::-1],
        type_stats["avg"][::-1],
        color=C1, height=0.6,
    )
    ax.set_title("Top 15 procedure types by avg HB recovery time\n(min. 20 occurrences)",
                 fontsize=11, fontweight="bold", loc="left")
    ax.set_xlabel("Avg post-procedure HB time (hours)")
    _style(ax, "x")
    fig.tight_layout()
    return fig

def plot_cost_curve(cost_table):
    """Total holding bay cost vs bay count — shows the trade-off."""
    df = cost_table.sort_values("hb_count")
    fig, ax = plt.subplots(figsize=(8, 4), facecolor=BG)

    # Palette-aligned colors — distinct from Cath (red) and EP (blue)
    _CANCEL_CLR = "#e8956d"   # muted orange  — cancellation cost
    _EMPTY_CLR  = "#56b4a0"   # muted teal    — empty bay cost
    _BEST_CLR   = "#c9b060"   # muted gold    — cost-minimising marker

    ax.stackplot(
        df["hb_count"],
        df["cancellation_cost"],
        df["empty_holding_bay_cost"],
        labels=["Cancellation cost", "Empty bay cost"],
        colors=[_CANCEL_CLR, _EMPTY_CLR],
        alpha=0.75,
    )
    ax.plot(df["hb_count"], df["total_holding_bay_cost"],
            color="#e2e8f0", linewidth=1.5, label="Total cost")

    # Mark current plan
    if CURRENT_HB_COUNT in df["hb_count"].values:
        cur = df[df["hb_count"] == CURRENT_HB_COUNT].iloc[0]
        ax.axvline(CURRENT_HB_COUNT, color=C3, linestyle="--", linewidth=1.2, label=f"Current plan ({CURRENT_HB_COUNT} bays)")
        ax.scatter([CURRENT_HB_COUNT], [cur["total_holding_bay_cost"]], color=C3, zorder=5, s=60)

    # Mark cost-minimizing point
    best = df.loc[df["total_holding_bay_cost"].idxmin()]
    ax.axvline(best["hb_count"], color=_BEST_CLR, linestyle="--", linewidth=1.2,
               label=f"Cost-minimizing ({int(best['hb_count'])} bays)")
    ax.scatter([best["hb_count"]], [best["total_holding_bay_cost"]], color=_BEST_CLR, zorder=5, s=60)

    ax.set_title("Daily holding bay cost vs bay count", fontsize=11, fontweight="bold", loc="left")
    ax.set_xlabel("Number of holding bays")
    ax.set_ylabel("Cost per day ($)")
    ax.legend(frameon=False, fontsize=8, loc="upper right")
    _style(ax, "y")
    fig.tight_layout()
    return fig

# ── comparison & sensitivity chart functions ──────────────────────────────────

def plot_hb_peak_distribution(summary):
    """Histogram of daily peak holding-bay occupancy with P90/P95 markers."""
    peaks = summary["holding_bay"]["daily_peak_bays"]
    hb = summary["holding_bay"]
    fig, ax = plt.subplots(figsize=(8, 4), facecolor=BG)
    ax.hist(peaks, bins=range(0, max(peaks) + 2), color=C1, edgecolor="white",
            alpha=0.85, linewidth=0.5)
    ax.axvline(hb["peak_bays_p90"], color=C3, linestyle="--", linewidth=1.2,
               label=f"P90 = {hb['peak_bays_p90']:.1f} bays")
    ax.axvline(hb["peak_bays_p95"], color=C2, linestyle="--", linewidth=1.5,
               label=f"P95 = {hb['peak_bays_p95']:.1f} bays (recommended: {hb['recommended_bays_p95']})")
    ax.set_title("Daily peak holding-bay occupancy distribution",
                 fontsize=11, fontweight="bold", loc="left")
    ax.set_xlabel("Peak bays occupied that day")
    ax.set_ylabel("Number of days")
    ax.legend(frameon=False, fontsize=9)
    _style(ax, "y")
    fig.tight_layout()
    return fig


def plot_hb_demand_heatmap(summary, resolution=5):
    """Heatmap: days × time-of-day, coloured by holding-bay occupancy count."""
    import numpy as np

    tp   = summary["timePeriod"]
    bins = tp.bins[2]          # {(day, slot_float): count}
    days = tp.numDays

    # slot i → minutes from midnight = i * resolution
    # show 06:00 → 24:00 (the typical operating window)
    slot_start = int(6 * 60 / resolution)
    slot_end   = int(24 * 60 / resolution)
    n_slots    = slot_end - slot_start

    matrix = np.zeros((days, n_slots), dtype=float)
    for d in range(days):
        for j, i in enumerate(range(slot_start, slot_end)):
            matrix[d, j] = bins.get((d, float(i)), 0)

    # x-axis tick labels every hour
    tick_step   = int(60 / resolution)
    tick_pos    = list(range(0, n_slots, tick_step))
    tick_labels = [f"{6 + k}:00" for k in range(len(tick_pos))]

    fig, ax = plt.subplots(figsize=(12, max(4, days * 0.12 + 2)), facecolor=BG)
    im = ax.imshow(matrix, aspect="auto", cmap="YlOrRd",
                   interpolation="nearest", origin="upper")
    cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    cbar.set_label("Patients in HB", color=TEXT, fontsize=9)
    cbar.ax.yaxis.set_tick_params(color=TEXT)
    plt.setp(cbar.ax.yaxis.get_ticklabels(), color=TEXT)

    ax.set_xticks(tick_pos)
    ax.set_xticklabels(tick_labels, fontsize=8, color=TEXT)
    ax.set_ylabel("Simulation day", color=TEXT, fontsize=9)
    ax.set_xlabel("Time of day", color=TEXT, fontsize=9)
    ax.tick_params(colors=TEXT)
    ax.set_title("Holding-bay demand heatmap (patients per 5-min slot)",
                 fontsize=11, fontweight="bold", loc="left", color=TEXT)
    ax.set_facecolor(BG)
    for spine in ax.spines.values():
        spine.set_edgecolor(TEXT)
    fig.tight_layout()
    return fig


def plot_room_schedule_heatmap(summary, resolution=5):
    """Heatmap: rooms × time-of-day, coloured by avg % of days with a procedure in that slot."""
    import numpy as np

    tp      = summary["timePeriod"]
    schedules = tp.bins[0]    # {(day, labID, room): Schedule}
    days      = tp.numDays
    n_cath    = tp.numCathRooms
    n_ep      = tp.numEPRooms

    # build list of (labID, room, label)
    cathID, epID = 0.0, 1.0
    rooms = [(cathID, r, f"Cath {r+1}") for r in range(n_cath)] + \
            [(epID,   r, f"EP {r+1}")   for r in range(n_ep)]
    n_rooms = len(rooms)

    # show 07:00 → 22:00
    slot_start = (7,  0)
    slot_end   = (22, 0)
    minutes_per_slot = resolution
    start_min  = slot_start[0] * 60 + slot_start[1]
    end_min    = slot_end[0]   * 60 + slot_end[1]
    slots      = [(h * 60 + m) for h in range(24) for m in range(0, 60, minutes_per_slot)
                  if start_min <= h * 60 + m < end_min]
    slot_keys  = [((s // 60), (s % 60)) for s in slots]
    n_slots    = len(slots)

    matrix = np.zeros((n_rooms, n_slots), dtype=float)
    for ri, (lab, room, _) in enumerate(rooms):
        for si, sk in enumerate(slot_keys):
            occupied = sum(
                1 for d in range(days)
                if (d, lab, room) in schedules
                and len(schedules[(d, lab, room)].timeSlots.get(sk, [])) > 0
            )
            matrix[ri, si] = occupied / days * 100.0   # % of days occupied

    # x-axis tick labels every 2 hours
    tick_step   = int(120 / resolution)
    tick_pos    = list(range(0, n_slots, tick_step))
    tick_labels = [f"{7 + k * 2}:00" for k in range(len(tick_pos))]

    fig, ax = plt.subplots(figsize=(12, max(3, n_rooms * 0.55 + 1.5)), facecolor=BG)
    im = ax.imshow(matrix, aspect="auto", cmap="Blues",
                   interpolation="nearest", origin="upper", vmin=0, vmax=100)
    cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    cbar.set_label("% of days occupied", color=TEXT, fontsize=9)
    cbar.ax.yaxis.set_tick_params(color=TEXT)
    plt.setp(cbar.ax.yaxis.get_ticklabels(), color=TEXT)

    ax.set_yticks(range(n_rooms))
    ax.set_yticklabels([r[2] for r in rooms], fontsize=9, color=TEXT)
    ax.set_xticks(tick_pos)
    ax.set_xticklabels(tick_labels, fontsize=8, color=TEXT)
    ax.set_xlabel("Time of day", color=TEXT, fontsize=9)
    ax.tick_params(colors=TEXT)
    ax.set_title("Room schedule heatmap (% of simulated days with a procedure in that slot)",
                 fontsize=11, fontweight="bold", loc="left", color=TEXT)
    ax.set_facecolor(BG)
    for spine in ax.spines.values():
        spine.set_edgecolor(TEXT)
    fig.tight_layout()
    return fig


def plot_close_time_sensitivity(summary):
    """Dual-axis: days with HB demand after close + avg bay-hours after close."""
    rows = summary["close_time_eval"]
    labels  = [r["close_time"] for r in rows]
    days    = [r["days_with_any_demand_after_close"] for r in rows]
    bh_avg  = [r["average_bay_hours_after_close_per_day"] for r in rows]

    fig, ax1 = plt.subplots(figsize=(9, 4), facecolor=BG)
    fig.patch.set_facecolor(BG)
    ax2 = ax1.twinx()

    ax1.bar(labels, days, color=C1, alpha=0.7, width=0.4, label="Days with demand after close")
    ax2.plot(labels, bh_avg, color=C2, linewidth=2, marker="o", markersize=5,
             label="Avg bay-hours/day after close")

    ax1.set_title("Impact of holding-bay close time on residual demand",
                  fontsize=11, fontweight="bold", loc="left")
    ax1.set_xlabel("Close time")
    ax1.set_ylabel("Days with demand after close", color=C1)
    ax2.set_ylabel("Avg bay-hours remaining / day", color=C2)
    ax1.tick_params(axis="y", labelcolor=C1, length=0, labelsize=9)
    ax2.tick_params(axis="y", labelcolor=C2, length=0, labelsize=9)
    ax1.tick_params(axis="x", length=0, labelsize=9)
    ax1.set_facecolor(BG)
    ax1.grid(axis="y", color=GRID, linewidth=0.6, alpha=0.8)
    ax1.set_axisbelow(True)
    ax1.spines[["top", "right"]].set_visible(False)
    ax1.spines[["left", "bottom"]].set_color("#2a3547")
    ax2.spines[["top", "left"]].set_visible(False)
    ax2.spines[["right", "bottom"]].set_color("#2a3547")

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, frameon=False, fontsize=8, loc="upper right")
    fig.tight_layout()
    return fig


def plot_policy_utilization(policy_results):
    """Grouped bar: Cath and EP room utilization per scheduling policy."""
    labels = [r["priority_rule"] for r in policy_results]
    cath_u = [r["cath_utilization_avg"] * 100 for r in policy_results]
    ep_u   = [r["ep_utilization_avg"] * 100 for r in policy_results]
    x = range(len(labels))
    w = 0.35

    fig, ax = plt.subplots(figsize=(9, 4), facecolor=BG)
    bars1 = ax.bar([i - w/2 for i in x], cath_u, w, color=C1, alpha=0.85, label="Cath")
    bars2 = ax.bar([i + w/2 for i in x], ep_u,   w, color=C2, alpha=0.85, label="EP")
    ax.bar_label(bars1, fmt="%.1f%%", padding=3, fontsize=8)
    ax.bar_label(bars2, fmt="%.1f%%", padding=3, fontsize=8)
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, rotation=15, ha="right", fontsize=9)
    ax.set_title("Room utilization by scheduling policy", fontsize=11, fontweight="bold", loc="left")
    ax.set_ylabel("Utilization (%)")
    ax.legend(frameon=False, fontsize=9)
    _style(ax, "y")
    fig.tight_layout()
    return fig


def plot_policy_overflow(policy_results):
    """Grouped bar: overflow procedures per scheduling policy by lab."""
    labels  = [r["priority_rule"] for r in policy_results]
    ov_cath = [r.get("overflow_cath", 0) for r in policy_results]
    ov_ep   = [r.get("overflow_ep", 0) for r in policy_results]
    ov_flex = [r.get("overflow_middle", 0) for r in policy_results]
    x = range(len(labels))

    fig, ax = plt.subplots(figsize=(9, 4), facecolor=BG)
    b1 = ax.bar(x, ov_cath, color=C1, alpha=0.85, label="Cath overflow")
    b2 = ax.bar(x, ov_ep,   bottom=ov_cath, color=C2, alpha=0.85, label="EP overflow")
    bot3 = [a + b for a, b in zip(ov_cath, ov_ep)]
    b3 = ax.bar(x, ov_flex, bottom=bot3, color=C3, alpha=0.85, label="Flex room overflow")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, rotation=15, ha="right", fontsize=9)
    ax.set_title("Procedures scheduled past room closing time (overflow) by policy",
                 fontsize=11, fontweight="bold", loc="left")
    ax.set_ylabel("Overflow procedures")
    ax.legend(frameon=False, fontsize=9)
    _style(ax, "y")
    fig.tight_layout()
    return fig


def plot_policy_hb_and_close(policy_results):
    """Side-by-side: recommended HB count and close time P95 per policy."""
    labels   = [r["priority_rule"] for r in policy_results]
    hb_rec   = [r["holding_bay"]["recommended_bays_p95"] for r in policy_results]
    close_h  = [r["holding_bay"]["last_occupied_p95_hours"] for r in policy_results]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4), facecolor=BG)
    fig.patch.set_facecolor(BG)

    bars1 = ax1.barh(labels, hb_rec, color=C1, alpha=0.85, height=0.5)
    ax1.bar_label(bars1, fmt="%d bays", padding=4, fontsize=9)
    ax1.set_title("Recommended HB count (P95 peak)", fontsize=10, fontweight="bold", loc="left")
    ax1.set_xlabel("Holding bays")
    _style(ax1, "x")

    # Convert raw float hours to HH:MM labels (handle cross-midnight values)
    close_labels = [_fmt_close(h) for h in close_h]
    bars2 = ax2.barh(labels, close_h, color=C2, alpha=0.85, height=0.5)
    for bar, lbl in zip(bars2, close_labels[::-1]):
        ax2.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height() / 2,
                 lbl, va="center", fontsize=9, color=TEXT)
    ax2.set_title("Recommended close time (P95 last occupied)", fontsize=10, fontweight="bold", loc="left")
    ax2.set_xlabel("Time of day")
    from matplotlib.ticker import FuncFormatter
    ax2.xaxis.set_major_formatter(FuncFormatter(lambda x, _: _fmt_close(x)))
    _style(ax2, "x")

    fig.tight_layout()
    return fig


def plot_policy_summary_table(policy_results):
    """Return a DataFrame summarising all policies — for st.dataframe."""
    rows = []
    for r in policy_results:
        hb = r["holding_bay"]
        rows.append({
            "Priority rule":        r["priority_rule"],
            "HB peak P95":          round(hb["peak_bays_p95"], 1),
            "Overflow (total)":     r["overflow_total"],
            "Close hr P95":         _fmt_close(hb["recommended_close_p95"]),
            "Min total cost ($)":   round(r.get("min_total_cost", float("inf")), 2),
            "Procs placed":         r["procs_placed"],
            "Recommended HB bays":  hb["recommended_bays_p95"],
        })
    return pd.DataFrame(rows)


def _norm(vals, higher_is_better=True):
    """Min-max normalise a list to [0,1]; invert if lower is better."""
    lo, hi = min(vals), max(vals)
    if hi == lo:
        return [0.5] * len(vals)
    normed = [(v - lo) / (hi - lo) for v in vals]
    return normed if higher_is_better else [1 - n for n in normed]


def plot_policy_radar(policy_results):
    """Radar/spider chart: 5 policies × 4 normalised KPIs."""
    labels = [r["priority_rule"] for r in policy_results]

    # Raw values per metric (each column = one policy)
    raw = {
        "Low HB\nPeak":  [r["holding_bay"]["peak_bays_p95"] for r in policy_results],  # lower better
        "Low\nOverflow": [r["overflow_total"] for r in policy_results],   # lower better
        "Early\nClose":  [r["holding_bay"]["last_occupied_p95_hours"] for r in policy_results],  # lower better
        "Low\nCost":     [r.get("min_total_cost", float("inf")) for r in policy_results],  # lower better
    }
    higher = {"Low HB\nPeak": False, "Low\nOverflow": False, "Early\nClose": False,
              "Low\nCost": False}

    categories = list(raw.keys())
    N = len(categories)
    angles = [n / N * 2 * np.pi for n in range(N)]
    angles += angles[:1]   # close the polygon

    POLICY_COLORS = ["#3B6EA5", "#C0392B", "#6B7A8F", "#27AE60", "#E67E22"]

    fig = plt.figure(figsize=(7, 7), facecolor=BG)
    ax = fig.add_subplot(111, polar=True)
    ax.set_facecolor(BG)

    for idx, (label, color) in enumerate(zip(labels, POLICY_COLORS)):
        scores = [_norm(raw[cat], higher_is_better=higher[cat])[idx] for cat in categories]
        scores += scores[:1]
        ax.plot(angles, scores, color=color, linewidth=2, label=label)
        ax.fill(angles, scores, color=color, alpha=0.12)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, fontsize=9, color=TEXT)
    ax.set_yticks([0.25, 0.5, 0.75, 1.0])
    ax.set_yticklabels(["25%", "50%", "75%", "Best"], fontsize=7, color="#7a8ba0")
    ax.set_ylim(0, 1)
    ax.spines["polar"].set_color("#2a3547")
    ax.grid(color=GRID, linewidth=0.6)
    ax.set_title("Policy comparison — normalised KPIs\n(outer edge = best on each metric)",
                 fontsize=11, fontweight="bold", pad=20)
    ax.legend(loc="upper right", bbox_to_anchor=(1.35, 1.1),
              frameon=False, fontsize=8)
    fig.tight_layout()
    return fig


def plot_policy_heatmap(policy_results):
    """Color-coded heatmap: policies × KPIs, green = better, red = worse."""
    labels = [r["priority_rule"] for r in policy_results]

    def _fmt_hhmm(h):
        total = int(round(h * 60))
        hh, mm = total // 60, total % 60
        suffix = "+" if hh >= 24 else ""
        return f"{hh % 24:02d}:{mm:02d}{suffix}"

    metrics_cfg = [
        ("HB peak P95",      [r["holding_bay"]["peak_bays_p95"] for r in policy_results],False, "{:.1f}".format),
        ("Overflow",         [r["overflow_total"] for r in policy_results],              False, "{:.0f}".format),
        ("Close hr P95",     [r["holding_bay"]["last_occupied_p95_hours"] for r in policy_results], False, _fmt_hhmm),
        ("Min cost ($)",     [r.get("min_total_cost", float("inf")) for r in policy_results], False, "${:.0f}".format),
    ]

    n_policies = len(labels)
    n_metrics  = len(metrics_cfg)

    # Build normalised score matrix (rows = metrics, cols = policies)
    score_matrix = np.zeros((n_metrics, n_policies))
    cell_text    = [[""] * n_policies for _ in range(n_metrics)]

    for row, (_, vals, hib, fmt) in enumerate(metrics_cfg):
        normed = _norm(vals, higher_is_better=hib)
        for col in range(n_policies):
            score_matrix[row, col] = normed[col]
            cell_text[row][col] = fmt(vals[col])

    # policy_results is already ranked best-first by comparePriorityRules — preserve that order
    fig, ax = plt.subplots(figsize=(max(6, n_policies * 1.8), n_metrics * 0.9 + 1.5), facecolor=BG)
    im = ax.imshow(score_matrix, cmap="Blues", vmin=0, vmax=1, aspect="auto")

    ax.set_xticks(range(n_policies))
    ax.set_xticklabels(labels, fontsize=9, rotation=20, ha="right")
    ax.set_yticks(range(n_metrics))
    ax.set_yticklabels([m[0] for m in metrics_cfg], fontsize=9)
    ax.tick_params(length=0)

    for row in range(n_metrics):
        for col in range(n_policies):
            brightness = score_matrix[row, col]
            txt_color = "white" if brightness > 0.55 else "#1a2233"
            ax.text(col, row, cell_text[row][col],
                    ha="center", va="center", fontsize=9, color=txt_color, fontweight="bold")

    ax.set_title("Performance heatmap — darker blue = better on each metric",
                 fontsize=11, fontweight="bold", loc="left")
    fig.tight_layout()
    return fig


def plot_policy_composite_score(policy_results):
    """Horizontal bar: composite score = average normalised rank across all KPIs."""
    labels = [r["priority_rule"] for r in policy_results]

    raw = {
        "Cath util":    ([r["cath_utilization_avg"] * 100 for r in policy_results], True),
        "EP util":      ([r["ep_utilization_avg"] * 100 for r in policy_results],   True),
        "Low overflow": ([r["overflow_total"] for r in policy_results],              False),
        "Low HB peak":  ([r["holding_bay"]["peak_bays_p95"] for r in policy_results], False),
        "Early close":  ([r["holding_bay"]["last_occupied_p95_hours"] for r in policy_results], False),
    }

    composite = np.zeros(len(labels))
    for vals, hib in raw.values():
        composite += np.array(_norm(vals, higher_is_better=hib))
    composite /= len(raw)   # average normalised score (0=worst, 1=best)

    # sort best → worst
    order = np.argsort(composite)[::-1]
    sorted_labels = [labels[i] for i in order]
    sorted_scores = composite[order]
    colors = [C1 if i == 0 else C3 for i in range(len(order))]

    fig, ax = plt.subplots(figsize=(8, max(3, len(labels) * 0.6 + 1)), facecolor=BG)
    bars = ax.barh(sorted_labels[::-1], sorted_scores[::-1], color=colors[::-1],
                   height=0.55, alpha=0.9)
    ax.bar_label(bars, fmt="%.2f", padding=4, fontsize=9)
    ax.set_xlim(0, 1.15)
    ax.set_title("Composite performance score (avg normalised rank across 5 KPIs)\n"
                 "Higher = better overall — blue bar is the top-ranked policy",
                 fontsize=11, fontweight="bold", loc="left")
    ax.set_xlabel("Score (0 = worst, 1 = best)")
    _style(ax, "x")
    fig.tight_layout()
    return fig


# ── helpers ───────────────────────────────────────────────────────────────────
def make_params(scenario_key, priority_rule, hb_clean_time, num_cath_rooms, resolution):
    p = Params()
    p.wFiles.value = scenario_key
    p.getScenarioFileNames()
    p.wSortPriority.value = priority_rule
    p.getSortPriorityVars()
    p.desiredPreCleanMean = hb_clean_time
    p.desiredPostCleanMean = hb_clean_time
    p.resolution = resolution
    p.numCathRooms = num_cath_rooms
    return p

# ── page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="EP/CATH Lab Simulation",
    page_icon="🏥",
    layout="wide",
)

st.markdown("""
<style>
/* ── App shell ────────────────────────────────────────────────── */
.stApp { background-color: #0f1623; }

/* ── Sidebar ─────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background-color: #131d2e;
    border-right: 1px solid #1e2e45;
}
[data-testid="stSidebar"] .stMarkdown h2,
[data-testid="stSidebar"] .stMarkdown p { color: #c8d6e5; }

/* ── Metric cards ─────────────────────────────────────────────── */
[data-testid="metric-container"] {
    background: #1a2233;
    border: 1px solid #243048;
    border-radius: 12px;
    padding: 18px 20px 14px;
}
[data-testid="stMetricValue"] { color: #5b9bd5; font-size: 1.5rem; }
[data-testid="stMetricLabel"] { color: #94a3b8; font-size: 0.8rem; }
[data-testid="stMetricDelta"] { font-size: 0.8rem; }

/* ── Tabs ─────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    background: #131d2e;
    border-radius: 10px;
    padding: 4px 6px;
    gap: 4px;
    border: 1px solid #1e2e45;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px;
    color: #7a8ba0;
    padding: 8px 18px;
    font-size: 0.88rem;
    font-weight: 500;
    border: none;
}
.stTabs [aria-selected="true"] {
    background: #243048 !important;
    color: #e2e8f0 !important;
    font-weight: 600;
}

/* ── Buttons ─────────────────────────────────────────────────── */
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #3b6fb5 0%, #2a5298 100%);
    border: none;
    border-radius: 8px;
    font-weight: 600;
    letter-spacing: 0.02em;
    box-shadow: 0 4px 14px rgba(59,111,181,0.4);
    transition: box-shadow 0.2s;
}
.stButton > button[kind="primary"]:hover {
    box-shadow: 0 6px 20px rgba(59,111,181,0.6);
}

/* ── Dividers ────────────────────────────────────────────────── */
hr { border-color: #1e2e45 !important; opacity: 1; }

/* ── Alert / info boxes ───────────────────────────────────────── */
[data-testid="stAlert"] {
    border-radius: 10px;
    border-left-width: 4px;
}

/* ── DataFrames ──────────────────────────────────────────────── */
[data-testid="stDataFrame"] {
    border-radius: 10px;
    overflow: hidden;
    border: 1px solid #243048;
}

/* ── Images (charts) ─────────────────────────────────────────── */
[data-testid="stImage"] img {
    border-radius: 10px;
    border: 1px solid #243048;
}

/* ── Spinner text ─────────────────────────────────────────────── */
[data-testid="stSpinner"] { color: #5b9bd5; }

/* ── Headings ─────────────────────────────────────────────────── */
h1 { color: #f1f5f9 !important; font-weight: 700; letter-spacing: -0.5px; }
h2, h3 { color: #cbd5e1 !important; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

st.title("EP/CATH Lab Simulation")
st.caption("v2 — emergency fix applied")
st.markdown(
    "Explore the underlying procedure and shift data, set parameters, and run the "
    "discrete event simulation to get holding bay sizing and cost recommendations."
)

# ── sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Parameters")
    scenario_label = st.selectbox(
        "Case volume scenario", list(SCENARIOS.keys()),
        help=(
            "Controls which patient volume dataset is loaded. "
            "'Historical' uses the base 2015 data. "
            "'High-volume EP' adds two extra EP providers, raising EP procedure counts and holding bay demand. "
            "'Cath lab only' removes all EP cases. "
            "Affects every metric — utilization, overflow, recommended bay count, and close time."
        ),
    )
    priority_rule  = st.selectbox(
        "Scheduling priority rule", PRIORITY_RULES,
        help=(
            "Determines the order in which procedures are assigned to rooms each day. "
            "Longest first → fills rooms with high-revenue cases early, may reduce overflow. "
            "Shortest first → more procedures start on time, but room utilization may drop. "
            "Recovery-time rules push high-HB-demand patients earlier or later in the day, "
            "directly shifting the peak holding bay occupancy and recommended close time. "
            "Enable 'Compare all scheduling policies' to see all five rules side by side."
        ),
    )
    num_cath_rooms = st.slider(
        "Cath rooms", 1, 10, 5,
        help=(
            "Number of Cath lab procedure rooms available. "
            "More rooms raise Cath capacity — reducing overflow for Cath procedures — "
            "but do not affect EP capacity or holding bay demand directly. "
            "If Cath utilization is already low, adding rooms will not improve efficiency."
        ),
    )
    hb_clean_time  = st.slider(
        "Mean HB cleaning time (hours)", 0.01, 1.0, 0.10, step=0.01,
        help=(
            "Average time a holding bay is unavailable between patients (cleaning and prep). "
            "Higher values reduce effective bay throughput: each bay turns over more slowly, "
            "so peak simultaneous occupancy rises and the recommended bay count increases. "
            "Lower values allow faster throughput and may reduce the required bay count. "
            "Default 0.10 h (6 min) reflects typical turnover assumptions."
        ),
    )
    resolution     = st.selectbox(
        "Time resolution (minutes)", [1.0, 5.0, 10.0], index=1,
        help=(
            "Simulation clock tick size. "
            "1 min → most accurate, slowest (best for final analysis). "
            "5 min → balanced accuracy and speed (recommended for exploration). "
            "10 min → fastest, slightly less precise timestamps for close-time and HB peak estimates."
        ),
    )
    compare_policies = st.checkbox(
        "Compare all scheduling policies", value=True,
        help=(
            "Runs five simulations — one per priority rule — keeping all other parameters fixed. "
            "Adds the Policy Comparison tab with radar chart, heatmap, and composite scores. "
            "Takes roughly 5× longer than a single run."
        ),
    )
    st.divider()
    run = st.button("Run Simulation", type="primary", width='stretch')

# ── load data (always) ────────────────────────────────────────────────────────
scenario_key = SCENARIOS[scenario_label]
proc_file, shift_file = get_file_paths(scenario_key)
proc_df  = load_proc_data(proc_file)
shift_df = load_shift_data(shift_file)
cost_table_baseline = get_baseline_cost_table()

tabs = ["Data Overview", "HB Peak P95", "Overflow", "Close hr P95", "Min Cost", "Policy Comparison", "Recommendations & Conclusion"]
tab_eda, tab_hb, tab_overflow, tab_close, tab_mincost, tab_policy, tab_conclusion = st.tabs(tabs)

# ── Tab: Data Overview (EDA) ──────────────────────────────────────────────────
with tab_eda:

    # ── Procedure Data ────────────────────────────────────────────────────────
    st.subheader("Procedure Data")
    total  = len(proc_df)
    cath_n = (proc_df["lab_name"] == "Cath").sum()
    ep_n   = (proc_df["lab_name"] == "EP").sum()
    days_n = proc_df["day"].nunique()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total procedures", f"{total:,}")
    m2.metric("Cath procedures",  f"{cath_n:,}")
    m3.metric("EP procedures",    f"{ep_n:,}")
    m4.metric("Simulation days",  str(days_n))

    st.divider()

    c1, c2 = st.columns([1, 1.3])
    with c1:
        _show_fig(plot_volume_by_lab(proc_df))
    with c2:
        _show_fig(plot_proc_duration(proc_df))

    c3, c4 = st.columns([1, 1.8])
    with c3:
        _show_fig(plot_horizon(proc_df))
    with c4:
        _show_fig(plot_pre_post_times(proc_df))

    _show_fig(plot_daily_volume(proc_df))
    _show_fig(plot_provider_workload(proc_df))

    st.subheader("Procedure Duration Summary")
    stats = proc_df.groupby("lab_name")["proc_time_min"].describe().round(1)
    stats.columns = ["Count", "Mean (min)", "Std", "Min", "25%", "Median", "75%", "Max"]
    st.dataframe(stats, width='stretch')

    # ── Shift Data ────────────────────────────────────────────────────────────
    st.divider()
    st.subheader("Shift Data")
    m5, m6, m7 = st.columns(3)
    m5.metric("Total shifts",             f"{len(shift_df):,}")
    m6.metric("Unique providers",         str(shift_df["provider"].nunique()))
    m7.metric("Avg procedures per shift", f"{shift_df['num_procedures'].mean():.1f}")

    c5, c6 = st.columns([1, 1.8])
    with c5:
        _show_fig(plot_shift_types(shift_df))
    with c6:
        _show_fig(plot_shift_load(shift_df))

    # ── Cost Context ──────────────────────────────────────────────────────────
    st.divider()
    st.subheader("Cost Context")
    st.markdown(
        "The simulation uses economic assumptions to recommend the right number of "
        "holding bays and the right closing time. Here's what drives the cost model."
    )

    # Cost assumptions table
    st.markdown("**Cost assumptions used in the analysis**")
    assump_df = pd.DataFrame(
        list(COST_ASSUMPTIONS.items()),
        columns=["Parameter", "Value"]
    )
    st.dataframe(assump_df, width='stretch', hide_index=True)

    st.divider()

    # HB demand drivers
    st.markdown("**What drives holding bay demand?**")
    st.caption(
        "Longer post-procedure recovery times mean patients occupy a holding bay longer, "
        "increasing peak occupancy and the risk of overcapacity."
    )
    ca1, ca2 = st.columns([1, 1.6])
    with ca1:
        _show_fig(plot_post_time_by_lab(proc_df))
    with ca2:
        _show_fig(plot_hb_demand_by_type(proc_df))


# ── simulation result tabs ────────────────────────────────────────────────────
if not run:
    with tab_hb:
        st.info("Click **Run Simulation** in the sidebar to see results here.")
    with tab_overflow:
        st.info("Click **Run Simulation** in the sidebar to see results here.")
    with tab_close:
        st.info("Click **Run Simulation** in the sidebar to see results here.")
    with tab_mincost:
        st.info("Click **Run Simulation** in the sidebar to see results here.")
    with tab_policy:
        st.info("Enable **Compare all scheduling policies** in the sidebar, then click **Run Simulation**.")
    with tab_conclusion:
        st.info("Click **Run Simulation** in the sidebar to see the final recommendations and conclusion.")
    st.stop()

# ── run simulation ────────────────────────────────────────────────────────────
with st.spinner("Running simulation... this may take 30-60 seconds."):
    try:
        timePeriod, summary, policy_results, policy_best = _cached_simulation(
            scenario_key, priority_rule, num_cath_rooms, hb_clean_time, resolution, compare_policies, _v=13
        )
    except Exception as e:
        st.error(f"Simulation failed: {e}")
        import traceback
        st.code(traceback.format_exc())
        st.stop()

st.success("Simulation complete!")

# ── Per-chart definitions & formulas ──────────────────────────────────────────
_CHART_META = {
    "close_time_sensitivity": {
        "title": "Close-Time Sensitivity — Bay-Hours After Close",
        "definition": (
            "Total holding-bay occupancy that would remain **unserved** if the bay closed at each "
            "candidate time, expressed in bay-hours (one patient in one bay for one hour). "
            "Higher values mean more patients are still recovering after the candidate close time."
        ),
        "formula": (
            "bay_hours_after_close(T) = Σ_{t > T}  occupancy(t) × (resolution / 60)\n"
            "where  occupancy(t) = number of patients in the HB at 5-min slot t,\n"
            "       T             = candidate close time,\n"
            "       resolution    = 5 min."
        ),
    },
    "close_time_days_with_demand": {
        "title": "Days With HB Demand After Close",
        "definition": (
            "Number of simulated days on which at least one patient was still occupying a holding-bay "
            "slot after the candidate close time. Even a single occupied slot counts as 'demand after close'."
        ),
        "formula": (
            "days_with_demand(T) = |{ d : ∃ t > T such that occupancy(d, t) > 0 }|\n"
            "i.e. count days where any slot past time T has non-zero occupancy."
        ),
    },
    "hb_total_cost": {
        "title": "Holding Bay — Total Daily Cost vs Bay Count",
        "definition": (
            "Estimated total daily cost of holding-bay operations at each candidate bay count, "
            "balancing the cost of turning patients away (too few bays = cancellations) against "
            "idle capacity (too many bays = empty-bay waste)."
        ),
        "formula": (
            "total_cost = cancellation_cost + empty_bay_cost\n\n"
            "cancellation_cost  = (avg_overcapacity_5min_blocks/day ÷ 12)  × $600\n"
            "empty_bay_cost     = avg_empty_bay_hours/day                  × $10\n\n"
            "Assumptions: $600 contribution margin per cancelled procedure;\n"
            "             $10 per idle bay-hour."
        ),
    },
    "hb_cost_components": {
        "title": "Holding Bay — Cost Components vs Bay Count",
        "definition": (
            "The two cost components plotted separately so you can see where each bay count "
            "sits on the cost curve. The optimal count minimises the sum; visually it is near "
            "where the two curves cross."
        ),
        "formula": (
            "cancellation_cost  = (avg_overcapacity_5min_blocks/day ÷ 12) × $600\n"
            "empty_bay_cost     = avg_empty_bay_hours/day × $10\n\n"
            "overcapacity_5min_block = one 5-min interval where demand > available bays;\n"
            "empty_bay_hour          = one bay-hour with zero occupancy."
        ),
    },
    "hb_service_constraint": {
        "title": "Holding Bay — Service Constraint (Overcapacity Days)",
        "definition": (
            "Number of the 260 simulated operating days on which demand exceeded the available "
            "bay count at least once. The service constraint requires this to be ≤ 5 % of days "
            "(≤ 13 days). The minimum bay count that satisfies this is the service-constrained "
            "recommendation."
        ),
        "formula": (
            "overcapacity_days(N) = |{ d : max_t occupancy(d,t) > N }|\n"
            "Service constraint:    overcapacity_days(N) / 260  ≤  0.05\n"
            "Recommendation:        min N such that constraint holds."
        ),
    },
    "close_time_total_cost": {
        "title": "Close Time — Total Daily Cost vs Close Time",
        "definition": (
            "Total estimated daily cost of keeping the holding bay open until each candidate time, "
            "combining nursing labour (base + overtime) and hospital admission costs for patients "
            "still in recovery at close."
        ),
        "formula": (
            "total_cost = labor_cost + admission_cost\n\n"
            "labor_cost     = incremental_hours × ⌈avg_occupancy / 4⌉ × $48       (base)\n"
            "               + incremental_hours × ⌈extra_p95_patients / 4⌉ × $72  (overtime)\n"
            "admission_cost = P95_occupancy_at_close × $230\n\n"
            "Assumptions: 4:1 patient-to-nurse ratio; $48/hr base wage;\n"
            "             1.5× overtime multiplier ($72/hr); $230 per admission;\n"
            "             incremental_hours measured from 17:00 baseline."
        ),
    },
    "close_time_cost_components": {
        "title": "Close Time — Cost Components vs Close Time",
        "definition": (
            "Labour and admission costs plotted separately so you can see how each component "
            "changes with the close time. Labour rises with extra open hours; admissions fall "
            "as later closes allow more patients to complete recovery."
        ),
        "formula": (
            "Base staff    = ⌈avg_occupancy / 4⌉  nurses  @ $48/hr\n"
            "Overtime staff= ⌈(P95_occupancy − avg_occupancy) / 4⌉  nurses  @ $72/hr\n"
            "Admitted pats = P95_occupancy at close time, each costing $230\n\n"
            "labor_cost     = incremental_hours × (base_staff_cost + overtime_staff_cost)\n"
            "admission_cost = admitted_pats × $230"
        ),
    },
    "policy_overflow": {
        "title": "Policy Comparison — Procedure Overflow",
        "definition": (
            "Total number of procedures across all simulated days that could not start before "
            "the room's scheduled closing time under each priority rule. Lower is better."
        ),
        "formula": (
            "overflow_total = |{ p : start_time(p) > room_close_time }|\n"
            "summed across all procedures p and all simulated days."
        ),
    },
    "policy_utilization": {
        "title": "Policy Comparison — Room Utilization",
        "definition": (
            "Average fraction of each room's prime-time shift hours that was occupied by "
            "a procedure (including turnover), averaged first across rooms then across all "
            "simulated days."
        ),
        "formula": (
            "room_util(d, r) = Σ procedure_prime_time_minutes(d,r) / total_prime_time_minutes\n"
            "lab_util        = mean over all rooms r and days d\n\n"
            "prime time = shift hours before room_close_time."
        ),
    },
    "policy_hb_peaks": {
        "title": "Policy Comparison — Recommended HB Bay Count",
        "definition": (
            "Recommended number of holding bays for each priority rule, defined as the "
            "95th-percentile daily peak simultaneous occupancy rounded up to the nearest integer."
        ),
        "formula": (
            "recommended_bays = ⌈P95(daily_peak_bays)⌉\n"
            "daily_peak_bays(d) = max_t occupancy(d, t)"
        ),
    },
    "policy_close_burden": {
        "title": "Policy Comparison — Recommended HB Close Time",
        "definition": (
            "Recommended holding-bay close time for each priority rule, defined as the "
            "95th-percentile of the last time slot with any occupancy across all simulated days."
        ),
        "formula": (
            "recommended_close = P95(last_occupied_time_per_day)\n"
            "last_occupied_time(d) = max{ t : occupancy(d, t) > 0 }"
        ),
    },
}

# Load baseline for comparison (cached — runs only once)
_baseline_is_current = _is_baseline_run(scenario_key, priority_rule, num_cath_rooms, hb_clean_time, resolution)
try:
    _baseline_summary = get_baseline_simulation_summary()
except Exception:
    _baseline_summary = None

# ── Tab: HB Peak P95 ──────────────────────────────────────────────────────────
with tab_hb:
    _show_run_config(scenario_label, priority_rule, num_cath_rooms, hb_clean_time, resolution, compare_policies)
    hb = summary["holding_bay"]

    st.subheader("Holding Bay Peak Demand (P95)")
    st.caption(
        "HB Peak P95 is the primary ranking criterion. It measures the 95th-percentile of the "
        "maximum simultaneous holding-bay occupancy across all simulated days — i.e., how many "
        "bays are needed on the worst 5% of days."
    )

    oh1, oh2, oh3 = st.columns(3)
    oh1.metric("Worst-case peak (all days)", f"{hb['overall_peak_bays']} bays")
    oh2.metric("P90 daily peak", f"{hb['peak_bays_p90']:.1f} bays")
    oh3.metric("P95 daily peak → recommendation", f"{hb['recommended_bays_p95']} bays")

    _show_fig(plot_hb_peak_distribution(summary))

    with st.expander("📐 Definition & formula", expanded=False):
        st.markdown("""
**What is being counted:** For each procedure whose post-procedure time exceeds the minimum threshold, the simulation adds +1 to every 5-min holding-bay slot the patient occupies (both pre- and post-procedure). The peak is the maximum slot value across an entire day.

**Pre-procedure HB window:**
> `[procStartTime − preTime,  procStartTime + preCleanTime)`

**Post-procedure HB window:**
> `[procStartTime + procTime_min/60,  procStartTime + procTime_min/60 + postTime + postCleanTime)`

**Daily peak:**
> `daily_peak(d) = max_t  occupancy(d, t)`

**P95 recommendation:**
> `recommended_bays = ⌈P95(daily_peak)⌉`
""")

    st.divider()

    if "cost_analysis" in summary:
        try:
            for key in ["hb_service_constraint"]:
                fig = getattr(VA, f"plot_{key}")(summary)
                meta = _CHART_META.get(key, {})
                st.subheader(meta.get("title", key))
                if "definition" in meta:
                    with st.expander("📐 Definition & formula", expanded=False):
                        st.markdown(meta["definition"])
                        if "formula" in meta:
                            st.code(meta["formula"], language=None)
                _show_fig(fig)
        except Exception as e:
            st.error(f"Chart failed: {e}")

    if compare_policies and policy_results:
        st.divider()
        try:
            fig = VA.plot_policy_hb_peaks(policy_results)
            meta = _CHART_META.get("policy_hb_peaks", {})
            st.subheader(meta.get("title", "Policy Comparison — HB Peak"))
            if "definition" in meta:
                with st.expander("📐 Definition & formula", expanded=False):
                    st.markdown(meta["definition"])
                    if "formula" in meta:
                        st.code(meta["formula"], language=None)
            _show_fig(fig)
        except Exception as e:
            st.error(f"Policy HB peaks chart failed: {e}")

# ── Tab: Overflow ─────────────────────────────────────────────────────────────
with tab_overflow:
    _show_run_config(scenario_label, priority_rule, num_cath_rooms, hb_clean_time, resolution, compare_policies)
    hb = summary["holding_bay"]

    st.subheader("Procedure Overflow")
    st.caption(
        "Overflow is the second ranking criterion. It counts procedures that could not start "
        "before the room's scheduled closing time — a direct measure of scheduling delays and care access."
    )

    ov1, ov2, ov3, ov4, ov5 = st.columns(5)
    ov1.metric("Total overflow",      str(summary["overflow_total"]))
    ov2.metric("Cath overflow",       str(summary.get("overflow_cath", "—")))
    ov3.metric("EP overflow",         str(summary.get("overflow_ep", "—")))
    ov4.metric("Flex room overflow",  str(summary.get("overflow_middle", "—")))
    ov5.metric("Recommended HB bays", f"{hb['recommended_bays_p95']} bays",
               help="HB peak P95 — bays needed to absorb overflow demand")

    with st.expander("📐 Definition & formula", expanded=False):
        st.markdown("""
**Overflow (past closing)** — Number of procedures whose scheduled start time fell after the room's closing time, meaning they were delayed or deferred.
> `overflow = |{ p : start_time(p) > room_close_time }|`
""")

    # Overflow vs HB demand
    st.divider()
    st.subheader("Overflow & Holding Bay Demand")
    st.caption(
        "Overflow and HB peak are closely linked — procedures that overflow (run late) continue "
        "occupying holding-bay slots longer, driving up peak demand. This histogram shows the "
        "distribution of daily HB peak occupancy."
    )
    _show_fig(plot_hb_peak_distribution(summary))

    if compare_policies and policy_results:
        st.divider()
        try:
            for key in ["policy_overflow", "policy_hb_peaks"]:
                fig = getattr(VA, f"plot_{key}")(policy_results)
                meta = _CHART_META.get(key, {})
                st.subheader(meta.get("title", key))
                if "definition" in meta:
                    with st.expander("📐 Definition & formula", expanded=False):
                        st.markdown(meta["definition"])
                        if "formula" in meta:
                            st.code(meta["formula"], language=None)
                _show_fig(fig)
        except Exception as e:
            st.error(f"Chart failed: {e}")


# ── Tab: Close hr P95 ─────────────────────────────────────────────────────────
with tab_close:
    _show_run_config(scenario_label, priority_rule, num_cath_rooms, hb_clean_time, resolution, compare_policies)
    hb = summary["holding_bay"]

    st.subheader("Holding Bay Close Time (P95)")
    st.caption(
        "Close hr P95 is the third ranking criterion. It measures the 95th-percentile of the "
        "last time slot with any holding-bay occupancy across all simulated days — i.e., how late "
        "the unit needs to stay open on the worst 5% of days."
    )

    c1, c2 = st.columns(2)
    c1.metric("Recommended HB close time (P95)", _fmt_close(hb["recommended_close_p95"]))
    c2.metric("Overall last occupied", _fmt_close(hb.get("overall_last_occupied_hours", 0)))

    with st.expander("📐 Definition & formula", expanded=False):
        st.markdown("""
**Recommended HB close time** — Latest time a patient is still in the holding bay, at the 95th percentile across all simulated days.
> `recommended_close = P95(last_occupied_time_per_day)`
> `last_occupied_time(d) = latest 5-min slot with occupancy > 0`
""")

    st.divider()

    st.subheader("Close-time Sensitivity")
    st.caption(
        "Closing the holding bays earlier saves staff cost but risks leaving recovering patients "
        "without a bay — requiring hospital admission. Later close times increase nurse labour cost."
    )
    _show_fig(plot_close_time_sensitivity(summary))

    close_df = pd.DataFrame(summary["close_time_eval"]).rename(columns={
        "close_time": "Close time",
        "days_with_any_demand_after_close": "Days with demand after close",
        "total_bay_hours_after_close": "Total bay-hours after close",
        "average_bay_hours_after_close_per_day": "Avg bay-hours/day after close",
    })
    st.dataframe(close_df.drop(columns=["close_hour"], errors="ignore"), width='stretch')

    if "cost_analysis" in summary:
        st.divider()
        ca = summary["cost_analysis"]
        close_rec = ca["close"]["cost_recommendation"]
        st.subheader("Close Time Cost Recommendations")
        cc3, cc4 = st.columns(2)
        cc3.metric("Cost-minimizing close time", str(close_rec["close_time_hhmm"]))
        cc4.metric("Estimated total cost", f"${close_rec['total_cost']:.2f}/day")

        try:
            for key in ["close_time_sensitivity", "close_time_days_with_demand"]:
                fig = getattr(VA, f"plot_{key}")(summary)
                meta = _CHART_META.get(key, {})
                st.subheader(meta.get("title", key))
                if "definition" in meta:
                    with st.expander("📐 Definition & formula", expanded=False):
                        st.markdown(meta["definition"])
                        if "formula" in meta:
                            st.code(meta["formula"], language=None)
                _show_fig(fig)
        except Exception as e:
            st.error(f"Chart failed: {e}")

        st.subheader("Close Time Cost Table")
        close_cost_df = ca["close"]["cost_table"][[
            "close_time_hhmm", "incremental_hours",
            "estimated_labor_cost", "admission_cost", "total_cost"
        ]].copy()
        st.dataframe(
            close_cost_df.style.format({
                "estimated_labor_cost": "${:.2f}",
                "admission_cost":       "${:.2f}",
                "total_cost":           "${:.2f}",
            }),
            width='stretch',
        )
        with st.expander("📐 Column definitions", expanded=False):
            st.markdown("""
| Column | Meaning | Formula |
|---|---|---|
| `close_time_hhmm` | Candidate close time (HH:MM) | — |
| `incremental_hours` | Extra open hours beyond the 17:00 baseline | `close_hours − 17.0` |
| `estimated_labor_cost` | Total nursing labour cost for incremental hours | `incremental_hrs × (base_staff × $48 + overtime_staff × $72)` |
| `admission_cost` | Cost of admitting stranded patients to hospital | `admitted_patients_95 × $230` |
| `total_cost` | Total daily cost at this close time | `estimated_labor_cost + admission_cost` |
""")

    if compare_policies and policy_results:
        st.divider()
        try:
            fig = VA.plot_policy_close_burden(policy_results)
            meta = _CHART_META.get("policy_close_burden", {})
            st.subheader(meta.get("title", "Policy Comparison — Close Burden"))
            if "definition" in meta:
                with st.expander("📐 Definition & formula", expanded=False):
                    st.markdown(meta["definition"])
                    if "formula" in meta:
                        st.code(meta["formula"], language=None)
            _show_fig(fig)
        except Exception as e:
            st.error(f"Policy close burden chart failed: {e}")

# ── Tab: Min Cost ──────────────────────────────────────────────────────────────
with tab_mincost:
    _show_run_config(scenario_label, priority_rule, num_cath_rooms, hb_clean_time, resolution, compare_policies)

    st.subheader("Minimum Total Cost")
    st.caption(
        "Min cost is the fourth (tiebreaker) ranking criterion. It is the lowest estimated "
        "daily cost — combining nurse labour and inpatient admission costs — at the optimal "
        "holding-bay close time."
    )

    if "cost_analysis" not in summary:
        st.warning("Cost analysis not available.")
    else:
        ca = summary["cost_analysis"]
        hb_cost_r = ca["hb"]["cost_recommendation"]
        hb_service = ca["hb"]["service_constraint_recommendation"]
        close_rec  = ca["close"]["cost_recommendation"]

        cc1, cc2, cc3 = st.columns(3)
        cc1.metric("Cost-minimizing bay count", f"{int(hb_cost_r['hb_count'])} bays",
                   help="Bay count with lowest total holding-bay cost")
        cc2.metric("Service-constrained bay count", f"{int(hb_service['hb_count'])} bays",
                   help="Minimum bays meeting ≤5% overcapacity days")
        cc3.metric("Min estimated total cost", f"${close_rec['total_cost']:.2f}/day")

        # Current setup vs cost-minimizing recommendation
        st.divider()
        st.subheader("Current Setup vs Cost-Minimizing Recommendation")
        st.caption(
            "The existing plan uses 21 holding bays. The chart below shows how cost changes "
            "as bay count varies — too few bays causes cancellations, too many wastes money on idle space."
        )
        _show_fig(plot_cost_curve(cost_table_baseline))
        cur_row  = cost_table_baseline[cost_table_baseline["hb_count"] == CURRENT_HB_COUNT]
        best_row = cost_table_baseline.loc[cost_table_baseline["total_holding_bay_cost"].idxmin()]
        if not cur_row.empty:
            cur_cost     = cur_row.iloc[0]["total_holding_bay_cost"]
            best_cost    = best_row["total_holding_bay_cost"]
            savings_day  = cur_cost - best_cost
            savings_year = savings_day * 260
            sc1, sc2, sc3 = st.columns(3)
            sc1.metric("Current plan daily cost (21 bays)", f"${cur_cost:.2f}/day")
            sc2.metric(
                f"Cost-minimizing option ({int(best_row['hb_count'])} bays)",
                f"${best_cost:.2f}/day",
                delta=f"-${savings_day:.2f}/day vs current",
            )
            sc3.metric("Estimated annual savings", f"${savings_year:,.0f}/year")

        with st.expander("📋 Cost Model Assumptions", expanded=False):
            st.markdown("""
### Cost Model Assumptions

| Parameter | Value | Source |
|---|---|---|
| Contribution margin per cancelled procedure | $600 | Case assumption |
| Empty holding-bay cost per idle hour | $10 | Case assumption |
| Base nursing wage | $48 / hr | Case assumption |
| Overtime multiplier | 1.5× ($72 / hr) | Case assumption |
| Nurse-to-patient ratio | 4 : 1 | Case assumption |
| Baseline close time (reference) | 17:00 | Case assumption |
| Inpatient admission cost per stranded patient | $230 | Case assumption |
| Simulated operating days | 260 | 52 weeks × 5 days |
""")

        st.divider()

        try:
            for key in ["hb_total_cost", "hb_cost_components"]:
                fig = getattr(VA, f"plot_{key}")(summary)
                meta = _CHART_META.get(key, {})
                st.subheader(meta.get("title", key))
                if "definition" in meta:
                    with st.expander("📐 Definition & formula", expanded=False):
                        st.markdown(meta["definition"])
                        if "formula" in meta:
                            st.code(meta["formula"], language=None)
                _show_fig(fig)
        except Exception as e:
            st.error(f"Chart failed: {e}")

        st.subheader("Holding Bay Cost Table")
        st.dataframe(
            ca["hb"]["cost_table"].style.format({
                "cancellation_cost":       "${:.2f}",
                "empty_holding_bay_cost":  "${:.2f}",
                "total_holding_bay_cost":  "${:.2f}",
                "pct_days_with_instances": "{:.1%}",
            }),
            width='stretch',
        )

        st.divider()

        try:
            for key in ["close_time_total_cost", "close_time_cost_components"]:
                fig = getattr(VA, f"plot_{key}")(summary)
                meta = _CHART_META.get(key, {})
                st.subheader(meta.get("title", key))
                if "definition" in meta:
                    with st.expander("📐 Definition & formula", expanded=False):
                        st.markdown(meta["definition"])
                        if "formula" in meta:
                            st.code(meta["formula"], language=None)
                _show_fig(fig)
        except Exception as e:
            st.error(f"Chart failed: {e}")

# ── Tab: Policy Comparison ────────────────────────────────────────────────────
with tab_policy:
    _show_run_config(scenario_label, priority_rule, num_cath_rooms, hb_clean_time, resolution, compare_policies)
    if not compare_policies or policy_results is None or policy_best is None:
        st.info(
            "Enable **Compare all scheduling policies** in the sidebar and click "
            "**Run Simulation** to compare all five scheduling rules side by side."
        )
    else:
        st.markdown(
            "The simulation was run five times — once per scheduling priority rule — "
            "keeping all other parameters identical. Use these charts to select the rule "
            "that best balances room utilization, patient delays (overflow), and holding bay demand."
        )

        best_rule = policy_best["priority_rule"]   # ranked #1 by comparePriorityRules

        # ── at-a-glance winner callout ─────────────────────────────────────
        st.success(
            f"**Top-ranked policy: {best_rule}** — ranked by fewest overflow → lowest HB peak "
            f"→ earliest close time → highest utilization."
        )

        # ── visual 1: radar chart ──────────────────────────────────────────
        st.subheader("Multi-Metric Radar Chart (Spider Chart)")
        st.caption(
            "**What it looks like:** A spider web with 5 spokes radiating from the centre — "
            "one spoke per metric: Cath utilization, EP utilization, overflow (delays), "
            "holding bay peak, and close time. Each scheduling policy is drawn as a coloured "
            "polygon connecting its score on each spoke. All five policies appear on the same chart."
        )
        st.caption(
            "**How each spoke works:** Every spoke runs from 0 at the centre to 1 at the outer edge, "
            "where **1 always means best on that metric** — regardless of whether the raw number is "
            "high or low. Utilization: higher raw → score 1. Overflow, HB peak, close time: "
            "lower raw → score 1. This rescaling lets you compare percentages, procedure counts, "
            "bay counts, and clock hours all on the same chart."
        )
        st.caption(
            "**How to read a polygon:** A point near the outer edge = strong on that metric. "
            "A point near the centre = weak. A large polygon = strong across the board. "
            "A lopsided polygon = excels on some metrics but sacrifices others — a visible trade-off. "
            "The ideal policy would fill the entire chart, touching the outer edge on all five spokes."
        )
        st.caption(
            "**Planning implication:** No policy achieves a perfect pentagon — improving one metric "
            "often worsens another. For example, front-loading long-recovery patients reduces HB peak "
            "but may increase overflow. Use the radar to see exactly where each policy wins and where "
            "it gives something up. Then decide based on what your team prioritises most."
        )
        _show_fig(plot_policy_radar(policy_results))

        st.divider()

        # ── visual 3: heatmap ──────────────────────────────────────────────
        st.subheader("Performance Heatmap")
        st.caption(
            "**What it shows:** A grid of all five policies (rows) against all key metrics "
            "(columns). Each cell is colour-coded green (better) to red (worse) relative to "
            "the other policies in that column. The raw value is shown inside each cell."
        )
        st.caption(
            "**How to read it:** Scan across a row to quickly profile one policy — a mostly-green "
            "row indicates a consistently strong policy, while a row with mixed colours shows "
            "trade-offs. Scan down a column to compare all policies on a single metric — the "
            "greenest cell in each column is the best performer for that KPI."
        )
        st.caption(
            "**Planning implication:** This chart is useful when stakeholders have different "
            "priorities. If minimising overflow is non-negotiable (patient access), focus on "
            "the Overflow column. If capital cost is the constraint, focus on the HB count column. "
            "The heatmap lets you apply your own weighting to the decision without re-running "
            "any calculations."
        )
        _show_fig(plot_policy_heatmap(policy_results))

        st.divider()

        # ── summary table ─────────────────────────────────────────────────
        st.subheader("Summary Table — Raw KPI Values")
        st.caption(
            "**What it shows:** The underlying numbers behind the charts above — one row per "
            "policy with the exact values for every KPI. This is the primary reference for "
            "reporting and for validating the visual summaries. "
            "**How to read it:** Columns follow the ranking order — lower HB peak, overflow, close time, and cost are all better. "
            "Sort any column by clicking its header to quickly find the top-performing policy "
            "on a specific metric."
        )
        policy_df = plot_policy_summary_table(policy_results)
        st.dataframe(policy_df, width='stretch', hide_index=True)

        st.divider()

        # ── metric breakdowns ──────────────────────────────────────────────
        st.subheader("Metric Breakdowns")

        st.markdown("**Room Utilization by Policy**")
        st.caption(
            "**What it shows:** Average Cath and EP room utilization (%) for each scheduling policy. "
            "Utilization is the fraction of each room's available shift time that is occupied by a "
            "procedure, including setup and turnover. The two bars per policy show Cath and EP "
            "separately so you can see whether a scheduling change benefits one lab more than the other."
        )
        st.caption(
            "**Planning implication:** Higher utilization directly supports the financial case for "
            "adding a new EP provider. A policy that raises EP utilization without significantly "
            "worsening overflow or holding bay demand is particularly valuable. If all policies "
            "yield similar utilization, the scheduling rule is not the driver of room efficiency — "
            "look at room count or shift length instead."
        )
        _show_fig(plot_policy_utilization(policy_results))

        st.markdown("**Procedure Delays (Overflow) by Policy**")
        st.caption(
            "**What it shows:** The total number of procedures that could not be started before "
            "the room's scheduled closing time, summed across all simulated days. A procedure "
            "counted as overflow either ran long into the next shift or had to be rescheduled, "
            "directly impacting patient access to care."
        )
        st.caption(
            "**How to read it:** Lower bars are better. Even small reductions in overflow can "
            "represent dozens of avoided delays per year. If one policy produces significantly "
            "fewer overflow events, it is managing room time more efficiently — fitting more "
            "procedures into the available hours before closing."
        )
        st.caption(
            "**Planning implication:** If patient access and care delays are the primary concern, "
            "weight this chart most heavily. Overflow is also a staff experience indicator — "
            "rooms that routinely run over schedule lead to unpaid overtime and burnout."
        )
        _show_fig(plot_policy_overflow(policy_results))

        st.markdown("**Holding Bay Requirements & Close Time by Policy**")
        st.caption(
            "**What it shows:** Two side-by-side charts. Left: the recommended holding bay count "
            "(P95 of daily peak occupancy) for each policy. Right: the recommended HB close time "
            "(P95 of the last occupied time each day) for each policy. Both are driven by when "
            "patients finish their procedures and enter recovery."
        )
        st.caption(
            "**How to read it:** A policy that front-loads longer-recovery procedures means "
            "those patients cycle through the HB earlier in the day, potentially reducing the "
            "required bay count and allowing an earlier close time. Conversely, a policy that "
            "defers long-recovery cases to the afternoon will increase late-day HB demand."
        )
        st.caption(
            "**Planning implication:** Each holding bay is a capital and staffing commitment. "
            "A policy that requires one fewer bay saves both construction cost and daily nurse "
            "staffing. A policy that enables an earlier close time saves overtime pay. Use this "
            "chart to quantify the operational cost impact of the scheduling decision beyond "
            "just room utilization."
        )
        _show_fig(plot_policy_hb_and_close(policy_results))

        st.divider()

        # ── current run detail ─────────────────────────────────────────────
        st.subheader("Selected Policy Detail")
        st.caption(f"Results for the currently selected policy: **{summary['priority_rule']}**")
        d1, d2, d3, d4, d5 = st.columns(5)
        d1.metric("Cath utilization",    f"{round(summary['cath_utilization_avg']*100,1)}%")
        d2.metric("EP utilization",      f"{round(summary['ep_utilization_avg']*100,1)}%")
        d3.metric("Overflow procedures", str(summary["overflow_total"]))
        d4.metric("Recommended HB bays", str(summary["holding_bay"]["recommended_bays_p95"]))
        d5.metric("Recommended close",   _fmt_close(summary["holding_bay"]["recommended_close_p95"]))

# ── Tab: Recommendations & Conclusion ─────────────────────────────────────────
with tab_conclusion:
    _show_run_config(scenario_label, priority_rule, num_cath_rooms, hb_clean_time, resolution, compare_policies)
    hb      = summary["holding_bay"]
    ca      = summary.get("cost_analysis", {})
    hb_ca   = ca.get("hb", {})
    close_ca = ca.get("close", {})

    hb_service_rec  = hb_ca.get("service_constraint_recommendation", {})
    hb_cost_rec     = hb_ca.get("cost_recommendation", {})
    close_cost_rec  = close_ca.get("cost_recommendation", {})

    rec_bays_service = int(hb_service_rec.get("hb_count", hb["recommended_bays_p95"]))
    rec_bays_cost    = int(hb_cost_rec.get("hb_count", hb["recommended_bays_p95"]))
    rec_bays_final   = max(rec_bays_service, rec_bays_cost)
    rec_close_str    = _fmt_close(hb["recommended_close_p95"])
    rec_close_cost   = str(close_cost_rec.get("close_time_hhmm", "—"))
    rec_policy       = policy_best["priority_rule"] if policy_best else summary["priority_rule"]

    st.markdown(
        "This tab consolidates every recommendation produced by the simulation into a single "
        "decision-ready summary. Each section answers one of the three key planning questions, "
        "shows the evidence behind the recommendation, and explains the trade-off accepted."
    )

    # ── Q1: Holding Bay Count ─────────────────────────────────────────────────
    st.subheader("Decision 1 — How many holding bays are needed?")
    st.caption(
        "The holding bay (HB) is the pre/post-procedure recovery space. Too few bays creates "
        "bottlenecks and forces cancellations; too many wastes capital and nurse staffing budget."
    )

    r1c1, r1c2, r1c3 = st.columns(3)
    r1c1.metric(
        "Current plan",
        f"{CURRENT_HB_COUNT} bays",
        help="The existing design assumption being evaluated."
    )
    r1c2.metric(
        "Cost-minimizing recommendation",
        f"{rec_bays_cost} bays",
        delta=f"{rec_bays_cost - CURRENT_HB_COUNT:+d} vs current",
        help="Bay count that minimises combined cancellation cost + idle-bay holding cost."
    )
    r1c3.metric(
        "Service-constrained recommendation",
        f"{rec_bays_service} bays",
        delta=f"{rec_bays_service - CURRENT_HB_COUNT:+d} vs current",
        help="Minimum bays that keep overcapacity days ≤ 5% of all operating days."
    )

    st.info(
        f"**Final recommendation: {rec_bays_final} holding bays.** "
        f"This is the higher of the cost-minimizing count ({rec_bays_cost}) and the service "
        f"constraint floor ({rec_bays_service}), ensuring that both financial efficiency and "
        f"patient care reliability are met simultaneously. "
        + (
            f"Compared to the current plan of {CURRENT_HB_COUNT} bays, this represents a "
            f"{'reduction' if rec_bays_final < CURRENT_HB_COUNT else 'increase'} of "
            f"{abs(rec_bays_final - CURRENT_HB_COUNT)} bay(s)."
            if rec_bays_final != CURRENT_HB_COUNT else
            f"The current plan of {CURRENT_HB_COUNT} bays already meets both criteria."
        )
    )

    with st.expander("Evidence: P95 daily peak occupancy drives the recommendation"):
        st.caption(
            "The chart below shows the distribution of peak simultaneous bay occupancy across "
            "all simulated days. The P95 marker — the level exceeded on only 5% of days — is "
            "used as the recommendation. Sizing to the absolute worst case would result in "
            "chronically empty bays on 95% of days."
        )
        _show_fig(plot_hb_peak_distribution(summary))

    if hb_ca.get("cost_table") is not None:
        with st.expander("Evidence: Cost curve — cancellation cost vs idle-bay cost"):
            st.caption(
                "As bay count increases, cancellation cost (too few bays) falls while idle-bay "
                "holding cost rises. The cost-minimizing point is where total cost is lowest. "
                "The service constraint floor may push the final recommendation above this point "
                "to protect patient access on peak days."
            )
            _show_fig(VA.plot_hb_total_cost(summary))

    st.divider()

    # ── Q2: Holding Bay Close Time ────────────────────────────────────────────
    st.subheader("Decision 2 — What time should the holding bay close?")
    st.caption(
        "The HB close time determines when nursing staff can end their shift. Closing too early "
        "strands patients still in recovery and triggers unplanned inpatient admissions. "
        "Closing too late drives overtime costs."
    )

    r2c1, r2c2 = st.columns(2)
    r2c2.metric(
        "Cost-minimizing close time",
        rec_close_cost,
        help="Close time with lowest combined labor + inpatient admission cost."
    )
    r2c1.metric(
        "P95 last occupied time",
        rec_close_str,
        help="On 95% of days, all bays are empty by this time — the capacity-driven close time."
    )

    st.info(
        f"**Recommendation: close at {rec_close_cost}** based on cost minimisation. "
        f"The P95 last-occupied time ({rec_close_str}) confirms that the majority of days "
        f"clear well before this hour. Closing earlier than the P95 time would expose "
        f"the unit to inpatient admission costs on the busiest 5% of days."
    )

    with st.expander("Evidence: Close-time sensitivity — demand remaining after close"):
        st.caption(
            "Each candidate close time is evaluated for how many days still have patients "
            "in the HB after that hour, and how many total bay-hours of demand fall outside "
            "the closing window. Moving close time earlier increases both figures."
        )
        _show_fig(plot_close_time_sensitivity(summary))

    if close_ca.get("cost_table") is not None:
        with st.expander("Evidence: Cost curve — labor vs admission cost by close time"):
            st.caption(
                "Later close times raise labor cost (more nurse hours, including overtime) "
                "but reduce inpatient admission cost (fewer patients stranded without a bay). "
                "The optimal close time is the crossover point where total cost is minimised."
            )
            _show_fig(VA.plot_close_time_total_cost(summary))
            _show_fig(VA.plot_close_time_cost_components(summary))

    st.divider()

    # ── Q3: Scheduling Priority Rule ─────────────────────────────────────────
    st.subheader("Decision 3 — Which scheduling priority rule should be adopted?")
    st.caption(
        "The scheduling rule determines the order in which procedures are assigned to rooms "
        "each day. Different orderings change room utilization, patient delays (overflow), "
        "holding bay demand, and close time — all without adding any resources."
    )

    if policy_results:
        _pdf = pd.DataFrame(policy_results)
        _hb_col = None
        if "holding_bay" in _pdf.columns:
            _pdf["_rec_bays"] = _pdf["holding_bay"].apply(lambda x: x.get("recommended_bays_p95", None))
            _pdf["_close_h"]  = _pdf["holding_bay"].apply(lambda x: x.get("recommended_close_p95", None))
            _hb_col = "_rec_bays"

        rows_data = []
        for _, row in _pdf.iterrows():
            rows_data.append({
                "Policy":            row["priority_rule"],
                "Cath util (%)":     f"{row['cath_utilization_avg']*100:.1f}",
                "EP util (%)":       f"{row['ep_utilization_avg']*100:.1f}",
                "Overflow":          int(row["overflow_total"]),
                "Rec. HB bays":      int(row["_rec_bays"]) if _hb_col else "—",
                "Rec. close time":   _fmt_close(row["_close_h"]) if "_close_h" in row and row["_close_h"] else "—",
                "Best policy?":      "✓ Recommended" if row["priority_rule"] == rec_policy else "",
            })

        _summary_df = pd.DataFrame(rows_data)
        st.dataframe(_summary_df, width="stretch", hide_index=True)

        st.success(
            f"**Recommended scheduling policy: {rec_policy}**  \n"
            f"This policy achieved the best composite score across room utilization, "
            f"procedure overflow, holding bay peak, and close time. "
            f"It is the single scheduling change that most improves operational efficiency "
            f"without requiring any additional rooms, staff, or capital investment."
        )

        with st.expander("Evidence: Policy comparison charts"):
            _show_fig(plot_policy_radar(policy_results))
            _show_fig(plot_policy_heatmap(policy_results))
    else:
        st.info(
            f"Policy comparison was not run. The simulation used **{summary['priority_rule']}**. "
            "Enable **Compare all scheduling policies** in the sidebar and re-run to see a "
            "full cross-policy recommendation here."
        )

    st.divider()

    # ── Baseline comparison in conclusion tab ─────────────────────────────────
    if _baseline_summary is not None and not _baseline_is_current:
        with st.expander("Compare vs default baseline", expanded=False):
            _show_baseline_comparison(summary, _baseline_summary)

    st.divider()

    # ── Final Conclusion ──────────────────────────────────────────────────────
    st.subheader("Final Conclusion")

    # Use policy comparison results for the recommended policy if available
    _best_row = next((r for r in (policy_results or []) if r["priority_rule"] == (rec_policy if policy_best else summary["priority_rule"])), None)
    cath_util_pct = round((_best_row["cath_utilization_avg"] if _best_row else summary["cath_utilization_avg"]) * 100, 1)
    ep_util_pct   = round((_best_row["ep_utilization_avg"]   if _best_row else summary["ep_utilization_avg"])   * 100, 1)
    overflow_n    = _best_row["overflow_total"] if _best_row else summary["overflow_total"]
    min_cost      = _best_row.get("min_total_cost") if _best_row else None

    st.markdown(
        f"Based on a discrete-event simulation of **{summary.get('total_procs', 7402):,} procedures** "
        f"drawn from July 2015 EP/CATH case data, the following configuration is recommended "
        f"for the joint lab:"
    )

    conc1, conc2, conc3 = st.columns(3)
    conc1.metric("Holding bay count",    f"{rec_bays_final} bays")
    conc2.metric("Holding bay close time", rec_close_cost)
    conc3.metric("Scheduling policy",    rec_policy if policy_best else summary["priority_rule"])

    st.markdown(
        f"""
**Holding bays ({rec_bays_final}):** The simulation recorded a P95 daily peak of
{hb['peak_bays_p95']:.0f} simultaneous bays occupied. Providing {rec_bays_final} bays
satisfies both the service constraint (≤5% of days with overcapacity) and the
cost-minimizing criterion, keeping the balance between cancellation risk and idle-space waste.

**Close time ({rec_close_cost}):** This is the cost-minimizing close time, where the sum of
nurse labor (including overtime) and inpatient admission costs is lowest.
The P95 last-occupied time of {rec_close_str} confirms the unit naturally clears by this hour
on the vast majority of operating days.

**Scheduling policy ({rec_policy}):** Of the five priority rules evaluated, this policy
produced the lowest estimated total cost{f" (${min_cost:,.2f}/day)" if min_cost is not None else ""},
with room utilization (Cath: {cath_util_pct}%, EP: {ep_util_pct}%),
procedure overflow ({overflow_n} procedures past room closing), and the best overall
holding bay demand. It requires no additional resources — only a change in how
procedures are ordered each morning.
        """
    )

    st.markdown(
        "**Together, these three changes address the core planning questions: "
        "right-sizing the recovery space, aligning staffing hours with actual demand, "
        "and reducing scheduling-driven delays — all derived from real operational data.**"
    )
