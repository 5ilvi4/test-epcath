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
import random
import streamlit as st
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
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

BG   = "#F7F5F2"
C1   = "#3B6EA5"
C2   = "#C0392B"
C3   = "#6B7A8F"
GRID = "#E6E6E6"

CURRENT_HB_COUNT = 21   # existing plan bay count

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

def _style(ax, grid_axis="y"):
    ax.set_facecolor(BG)
    ax.grid(axis=grid_axis, color=GRID, linewidth=0.7)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#CFCFCF")
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

    ax.stackplot(
        df["hb_count"],
        df["cancellation_cost"],
        df["empty_holding_bay_cost"],
        labels=["Cancellation cost", "Empty bay cost"],
        colors=[C2, C1],
        alpha=0.75,
    )
    ax.plot(df["hb_count"], df["total_holding_bay_cost"],
            color="#222222", linewidth=1.5, label="Total cost")

    # Mark current plan
    if CURRENT_HB_COUNT in df["hb_count"].values:
        cur = df[df["hb_count"] == CURRENT_HB_COUNT].iloc[0]
        ax.axvline(CURRENT_HB_COUNT, color=C3, linestyle="--", linewidth=1.2, label=f"Current plan ({CURRENT_HB_COUNT} bays)")
        ax.scatter([CURRENT_HB_COUNT], [cur["total_holding_bay_cost"]], color=C3, zorder=5, s=60)

    # Mark cost-minimizing point
    best = df.loc[df["total_holding_bay_cost"].idxmin()]
    ax.axvline(best["hb_count"], color=C2, linestyle="--", linewidth=1.2,
               label=f"Cost-minimizing ({int(best['hb_count'])} bays)")
    ax.scatter([best["hb_count"]], [best["total_holding_bay_cost"]], color=C2, zorder=5, s=60)

    ax.set_title("Daily holding bay cost vs bay count", fontsize=11, fontweight="bold", loc="left")
    ax.set_xlabel("Number of holding bays")
    ax.set_ylabel("Cost per day ($)")
    ax.legend(frameon=False, fontsize=8, loc="upper right")
    _style(ax, "y")
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

st.title("EP/CATH Lab Simulation")
st.markdown(
    "Explore the underlying procedure and shift data, set parameters, and run the "
    "discrete event simulation to get holding bay sizing and cost recommendations."
)

# ── sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Parameters")
    scenario_label = st.selectbox("Case volume scenario", list(SCENARIOS.keys()))
    priority_rule  = st.selectbox("Scheduling priority rule", PRIORITY_RULES)
    num_cath_rooms = st.slider("Cath rooms", 1, 10, 5)
    hb_clean_time  = st.slider("Mean HB cleaning time (hours)", 0.01, 1.0, 0.10, step=0.01)
    resolution     = st.selectbox("Time resolution (minutes)", [1.0, 5.0, 10.0], index=1)
    random_seed    = st.number_input("Random seed", value=30, min_value=0, step=1)
    compare_policies = st.checkbox(
        "Compare all scheduling policies", value=False,
        help="Runs 5 simulations — takes longer but adds policy comparison charts.",
    )
    st.divider()
    run = st.button("Run Simulation", type="primary", use_container_width=True)

# ── load data (always) ────────────────────────────────────────────────────────
scenario_key = SCENARIOS[scenario_label]
proc_file, shift_file = get_file_paths(scenario_key)
proc_df  = load_proc_data(proc_file)
shift_df = load_shift_data(shift_file)
cost_table_baseline = get_baseline_cost_table()

tabs = ["Data Overview", "Summary", "Charts", "Cost Analysis"]
tab_eda, tab_summary, tab_charts, tab_cost = st.tabs(tabs)

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
        st.pyplot(plot_volume_by_lab(proc_df))
    with c2:
        st.pyplot(plot_proc_duration(proc_df))

    c3, c4 = st.columns([1, 1.8])
    with c3:
        st.pyplot(plot_horizon(proc_df))
    with c4:
        st.pyplot(plot_pre_post_times(proc_df))

    st.pyplot(plot_daily_volume(proc_df))
    st.pyplot(plot_provider_workload(proc_df))

    st.subheader("Procedure Duration Summary")
    stats = proc_df.groupby("lab_name")["proc_time_min"].describe().round(1)
    stats.columns = ["Count", "Mean (min)", "Std", "Min", "25%", "Median", "75%", "Max"]
    st.dataframe(stats, use_container_width=True)

    # ── Shift Data ────────────────────────────────────────────────────────────
    st.divider()
    st.subheader("Shift Data")
    m5, m6, m7 = st.columns(3)
    m5.metric("Total shifts",             f"{len(shift_df):,}")
    m6.metric("Unique providers",         str(shift_df["provider"].nunique()))
    m7.metric("Avg procedures per shift", f"{shift_df['num_procedures'].mean():.1f}")

    c5, c6 = st.columns([1, 1.8])
    with c5:
        st.pyplot(plot_shift_types(shift_df))
    with c6:
        st.pyplot(plot_shift_load(shift_df))

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
    st.dataframe(assump_df, use_container_width=True, hide_index=True)

    st.divider()

    # HB demand drivers
    st.markdown("**What drives holding bay demand?**")
    st.caption(
        "Longer post-procedure recovery times mean patients occupy a holding bay longer, "
        "increasing peak occupancy and the risk of overcapacity."
    )
    ca1, ca2 = st.columns([1, 1.6])
    with ca1:
        st.pyplot(plot_post_time_by_lab(proc_df))
    with ca2:
        st.pyplot(plot_hb_demand_by_type(proc_df))

    st.divider()

    # Current vs recommended cost
    st.markdown("**Current setup vs cost-minimizing recommendation**")
    st.caption(
        "The existing plan uses 21 holding bays. The chart below shows how cost changes "
        "as bay count varies — too few bays causes cancellations, too many wastes money on idle space."
    )
    st.pyplot(plot_cost_curve(cost_table_baseline))

    # Savings summary
    cur_row  = cost_table_baseline[cost_table_baseline["hb_count"] == CURRENT_HB_COUNT]
    best_row = cost_table_baseline.loc[cost_table_baseline["total_holding_bay_cost"].idxmin()]
    if not cur_row.empty:
        cur_cost  = cur_row.iloc[0]["total_holding_bay_cost"]
        best_cost = best_row["total_holding_bay_cost"]
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

# ── simulation result tabs ────────────────────────────────────────────────────
if not run:
    with tab_summary:
        st.info("Click **Run Simulation** in the sidebar to see results here.")
    with tab_charts:
        st.info("Click **Run Simulation** in the sidebar to see charts here.")
    with tab_cost:
        st.info("Click **Run Simulation** in the sidebar to see cost analysis here.")
    st.stop()

# ── run simulation ────────────────────────────────────────────────────────────
with st.spinner("Running simulation... this may take 30-60 seconds."):
    random.seed(int(random_seed))
    try:
        p = make_params(scenario_key, priority_rule, hb_clean_time, num_cath_rooms, resolution)
    except Exception as e:
        st.error(f"Failed to initialize parameters: {e}")
        st.stop()

    policy_results = None
    if compare_policies:
        try:
            policy_results = Simulation.comparePriorityRules(p, saveResults=False)
        except Exception as e:
            st.warning(f"Policy comparison failed: {e}")

    try:
        timePeriod, summary = Simulation.RunSimulation(
            p,
            saveOutputs=False,
            printStats=False,
            printRecommendations=False,
            showVisualizations=False,
            policyResults=policy_results,
        )
    except Exception as e:
        st.error(f"Simulation failed: {e}")
        import traceback
        st.code(traceback.format_exc())
        st.stop()

st.success("Simulation complete!")

# ── Tab: Summary ──────────────────────────────────────────────────────────────
with tab_summary:
    hb = summary["holding_bay"]

    st.subheader("Key Metrics")
    c1, c2, c3 = st.columns(3)
    c1.metric("Recommended holding bays", f"{hb['recommended_bays_p95']} bays",
              help="95th percentile daily peak")
    c2.metric("Cath lab utilization", f"{round(summary['cath_utilization_avg'] * 100, 1)}%")
    c3.metric("EP lab utilization",   f"{round(summary['ep_utilization_avg'] * 100, 1)}%")

    c4, c5, c6 = st.columns(3)
    c4.metric("Procedures scheduled",    f"{summary['procs_placed']} / {summary['total_procs']}")
    c5.metric("Overflow (past closing)", str(summary["overflow_total"]))
    c6.metric("Recommended HB close time", str(hb["recommended_close_p95"]))

    st.divider()
    st.subheader("Close-time Sensitivity")
    close_df = pd.DataFrame(summary["close_time_eval"]).rename(columns={
        "close_time": "Close time",
        "days_with_any_demand_after_close": "Days with demand after close",
        "total_bay_hours_after_close": "Total bay-hours after close",
        "average_bay_hours_after_close_per_day": "Avg bay-hours/day after close",
    })
    st.dataframe(close_df.drop(columns=["close_hour"], errors="ignore"), use_container_width=True)

# ── Tab: Charts ───────────────────────────────────────────────────────────────
with tab_charts:
    if "cost_analysis" not in summary:
        st.warning("Cost analysis data unavailable — some charts cannot be generated.")
    else:
        try:
            figs = VA.build_all_key_figures(
                summary,
                policy_results=policy_results,
                source_note="Source: EP/CATH simulation based on July 2015 data",
            )
            for name, fig in figs.items():
                st.subheader(name.replace("_", " ").title())
                st.pyplot(fig)
        except Exception as e:
            st.error(f"Chart generation failed: {e}")
            import traceback
            st.code(traceback.format_exc())

# ── Tab: Cost Analysis ────────────────────────────────────────────────────────
with tab_cost:
    if "cost_analysis" not in summary:
        st.warning("Cost analysis not available.")
    else:
        ca = summary["cost_analysis"]

        st.subheader("Holding Bay Recommendations")
        hb_service = ca["hb"]["service_constraint_recommendation"]
        hb_cost_r  = ca["hb"]["cost_recommendation"]
        cc1, cc2 = st.columns(2)
        cc1.metric("Service-constrained recommendation", f"{int(hb_service['hb_count'])} bays",
                   help="Minimum bays meeting <=5% overcapacity days constraint")
        cc2.metric("Cost-minimizing recommendation", f"{int(hb_cost_r['hb_count'])} bays",
                   help="Bay count with lowest total cost")

        st.subheader("Holding Bay Cost Table")
        st.dataframe(
            ca["hb"]["cost_table"].style.format({
                "cancellation_cost":       "${:.2f}",
                "empty_holding_bay_cost":  "${:.2f}",
                "total_holding_bay_cost":  "${:.2f}",
                "pct_days_with_instances": "{:.1%}",
            }),
            use_container_width=True,
        )

        st.divider()

        close_rec = ca["close"]["cost_recommendation"]
        st.subheader("Close Time Recommendations")
        cc3, cc4 = st.columns(2)
        cc3.metric("Cost-minimizing close time", str(close_rec["close_time_hhmm"]))
        cc4.metric("Estimated total cost", f"${close_rec['total_cost']:.2f}/day")

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
            use_container_width=True,
        )
