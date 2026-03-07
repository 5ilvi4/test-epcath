import os
import sys

# ── path & chdir setup (must happen before any project imports) ───────────────
_repo_root = os.path.dirname(os.path.abspath(__file__))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

# Intercept Colab-specific os.chdir calls so the app works outside Colab
_orig_chdir = os.chdir
def _safe_chdir(path):
    if "/content/test-epcath" in str(path):
        return
    _orig_chdir(path)
os.chdir = _safe_chdir
_safe_chdir(_repo_root)  # start in repo root

# ── project imports ───────────────────────────────────────────────────────────
import random
import streamlit as st
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from Params import Params
import Simulation
import VisualizationAnalysis as VA

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

# ── helpers ───────────────────────────────────────────────────────────────────
def make_params(scenario_key, priority_rule, hb_clean_time, num_cath_rooms, resolution):
    """Create a configured Params object without ipywidgets or Colab dependencies."""
    p = Params()  # os.chdir inside __init__ is safely intercepted
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
    "Simulate patient scheduling through the Electrophysiology and Catheterization labs. "
    "Get recommendations for holding bay sizing, operating hours, and cost optimization."
)

# ── sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Parameters")

    scenario_label = st.selectbox("Case volume scenario", list(SCENARIOS.keys()))
    priority_rule = st.selectbox("Scheduling priority rule", PRIORITY_RULES)
    num_cath_rooms = st.slider("Cath rooms", 1, 10, 5)
    hb_clean_time = st.slider("Mean HB cleaning time (hours)", 0.01, 1.0, 0.10, step=0.01)
    resolution = st.selectbox("Time resolution (minutes)", [1.0, 5.0, 10.0], index=1)
    random_seed = st.number_input("Random seed", value=30, min_value=0, step=1)
    compare_policies = st.checkbox(
        "Compare all scheduling policies",
        value=False,
        help="Runs 5 simulations back-to-back — takes longer but adds policy comparison charts.",
    )

    st.divider()
    run = st.button("Run Simulation", type="primary", use_container_width=True)

# ── main area ─────────────────────────────────────────────────────────────────
if not run:
    st.info("Set your parameters in the sidebar, then click **Run Simulation**.")
    st.stop()

with st.spinner("Running simulation... this may take 30-60 seconds."):
    random.seed(int(random_seed))
    scenario_key = SCENARIOS[scenario_label]

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

# ── results tabs ──────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["Summary", "Charts", "Cost Analysis"])

# ── Tab 1: Summary ────────────────────────────────────────────────────────────
with tab1:
    hb = summary["holding_bay"]

    st.subheader("Key Metrics")
    c1, c2, c3 = st.columns(3)
    c1.metric("Recommended holding bays", f"{hb['recommended_bays_p95']} bays",
              help="95th percentile daily peak — handles 95% of days without overcapacity")
    c2.metric("Cath lab utilization", f"{round(summary['cath_utilization_avg'] * 100, 1)}%")
    c3.metric("EP lab utilization", f"{round(summary['ep_utilization_avg'] * 100, 1)}%")

    c4, c5, c6 = st.columns(3)
    c4.metric("Procedures scheduled", f"{summary['procs_placed']} / {summary['total_procs']}")
    c5.metric("Overflow (past closing)", str(summary["overflow_total"]))
    c6.metric("Recommended HB close time", str(hb["recommended_close_p95"]),
              help="95th percentile last patient departure time")

    st.divider()
    st.subheader("Close-time Sensitivity")
    close_df = pd.DataFrame(summary["close_time_eval"]).rename(columns={
        "close_time": "Close time",
        "days_with_any_demand_after_close": "Days with demand after close",
        "total_bay_hours_after_close": "Total bay-hours after close",
        "average_bay_hours_after_close_per_day": "Avg bay-hours/day after close",
    })
    st.dataframe(close_df.drop(columns=["close_hour"], errors="ignore"), use_container_width=True)

# ── Tab 2: Charts ─────────────────────────────────────────────────────────────
with tab2:
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
                plt.close(fig)
        except Exception as e:
            st.error(f"Chart generation failed: {e}")
            import traceback
            st.code(traceback.format_exc())

# ── Tab 3: Cost Analysis ──────────────────────────────────────────────────────
with tab3:
    if "cost_analysis" not in summary:
        st.warning("Cost analysis not available.")
    else:
        ca = summary["cost_analysis"]

        st.subheader("Holding Bay Recommendations")
        hb_service = ca["hb"]["service_constraint_recommendation"]
        hb_cost = ca["hb"]["cost_recommendation"]
        cc1, cc2 = st.columns(2)
        cc1.metric(
            "Service-constrained recommendation",
            f"{int(hb_service['hb_count'])} bays",
            help="Minimum bays meeting <=5% overcapacity days constraint",
        )
        cc2.metric(
            "Cost-minimizing recommendation",
            f"{int(hb_cost['hb_count'])} bays",
            help="Bay count with lowest total (cancellation + empty bay) cost",
        )

        st.subheader("Holding Bay Cost Table")
        st.dataframe(
            ca["hb"]["cost_table"].style.format({
                "cancellation_cost": "${:.2f}",
                "empty_holding_bay_cost": "${:.2f}",
                "total_holding_bay_cost": "${:.2f}",
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
                "admission_cost": "${:.2f}",
                "total_cost": "${:.2f}",
            }),
            use_container_width=True,
        )
