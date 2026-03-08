# EP/CATH Lab Planning Simulator

A Discrete Event Simulation (DES) tool for planning a joint Electrophysiology (EP) and Catheterization (Cath) lab. Built with Python and deployed as an interactive Streamlit web app.

## What it does

The simulator helps hospital planners answer three key operational questions:

1. **How many holding bay spaces are needed?**
2. **What time should the holding bay close each day?**
3. **Which scheduling priority rule minimizes patient delays and maximizes room utilization?**

It runs a day-by-day simulation of 7,402 patient procedures (based on July 2015 case data), tracks room occupancy, holding bay demand, and overflow events — then recommends the optimal configuration using cost-benefit analysis.

---

## Live App

The app is deployed on [Streamlit Cloud](https://streamlit.io/cloud). Use the sidebar to configure parameters and click **Run Simulation**.

---

## App Tabs

| Tab | Contents |
|-----|----------|
| **Summary** | Key metrics, holding bay capacity histogram, overflow breakdown, close-time sensitivity chart |
| **Charts** | Full visualization suite: cost curves, utilization, overflow, HB peaks, close-time burden |
| **Cost Analysis** | Economic trade-off tables for bay count and close time, with cost-minimizing and service-constraint recommendations |
| **Raw Data** | Downloadable simulation outputs |
| **Policy Comparison** | Side-by-side comparison of all 5 scheduling priority rules — composite score, radar chart, heatmap, and individual KPI charts |

---

## Scheduling Priority Rules

The simulator can compare five different ways to order procedures each day:

- **Historical order** — as recorded in the original schedule
- **Longest procedure first** — fills the longest slots early
- **Shortest procedure first** — minimizes idle gaps
- **Longest recovery time first** — moves high-demand HB patients through earlier
- **Shortest recovery time first** — clears the HB faster at end of day

The **Policy Comparison** tab ranks all five rules across five KPIs (room utilization, overflow, HB peak, HB close hour) and highlights the recommended rule.

---

## Simulation Logic

### Input data
- **Shift data** — which providers work which rooms on which days
- **Procedure data** — 7,402 procedures with durations, types, and urgency levels

### Core steps
1. **Clean procedure times** — add turnover time; cap at max room time
2. **Pack shifts into rooms** — assign provider shifts to Cath, EP, or flex rooms
3. **Pack procedures into shifts** — schedule each procedure into the next available slot using the chosen priority rule; same-day and emergency cases get priority
4. **Track holding bay occupancy** — patients enter the HB when their procedure ends and leave after recovery + cleaning time; occupancy is recorded every 5 minutes
5. **Build summary statistics** — room utilization, overflow count, crossover count, HB demand

### Sizing recommendation
Recommendations use the **95th percentile** of daily peak demand — this handles 95% of operating days without overcapacity, avoiding over-building for rare worst-case days.

---

## Cost Analysis

### Holding bay count
For each candidate bay count, the model computes:

```
cancellation_cost = avg overcapacity instances/day × (5 min / 60) × $600/cancellation
empty_bay_cost    = avg empty bay-hours/day × $10/hour
total_cost        = cancellation_cost + empty_bay_cost
```

A **service constraint** also applies: no more than 5% of operating days may have any overcapacity event. The final recommendation is the higher of the cost-minimizing count and the service-constraint minimum.

### Holding bay close time
For each candidate close time (17:00–24:00):

```
base_staff_cost  = incremental hours × ceil(avg occupancy / 4) × $48/hr
overtime_cost    = incremental hours × ceil((P95 − avg occupancy) / 4) × $72/hr
admission_cost   = P95 occupancy × $230/admission
total_cost       = labor_cost + admission_cost
```

The optimal close time minimizes total cost.

### Economic assumptions

| Parameter | Value | Role |
|-----------|-------|------|
| Lost margin per cancellation | $600 | Penalizes too few bays |
| Empty bay holding cost | $10/hr | Penalizes too many bays |
| Max overcapacity days | 5% | Service constraint floor |
| Patient-to-nurse ratio | 4 : 1 | Staffing calculation |
| Base nurse wage | $48/hr | Close time labor cost |
| Overtime multiplier | 1.5× | Late-hour premium |
| Inpatient admission cost | $230 | Penalizes closing too early |

---

## Project Structure

```
test-epcath/
├── app.py                      # Streamlit web app
├── Simulation.py               # DES engine and priority rule comparison
├── Params.py                   # Simulation parameters
├── CostAnalysis.py             # HB count and close-time cost models
├── VisualizationAnalysis.py    # Chart generation (matplotlib)
├── EP_CATH_Python_Code_Viz.ipynb  # Google Colab notebook (standalone run)
├── data/                       # Input CSVs (shift and procedure data)
└── requirements.txt
```

---

## How `app.py` Works

`app.py` is the Streamlit front-end. It is structured in six logical sections:

### 1. Bootstrap and imports (lines 1–34)
Before anything else, the script fixes the Python path so that `Simulation`, `Params`, `CostAnalysis`, and `VisualizationAnalysis` can be imported regardless of where Streamlit launches from. It also patches `os.chdir` to prevent Colab-specific directory changes from breaking the app when it runs on Streamlit Cloud. Then it imports all required libraries and project modules.

### 2. Constants and helpers (lines 36–128)
Global constants are defined once and reused throughout:

| Constant | Purpose |
|----------|---------|
| `SCENARIOS` | Maps human-readable scenario labels to the internal keys used by `Params` |
| `PRIORITY_RULES` | List of the five scheduling rules shown in the sidebar dropdown |
| `BG`, `C1`, `C2`, `C3`, `GRID` | Shared color palette for all charts |
| `COST_ASSUMPTIONS` | Cost parameters displayed in the Data Overview tab |
| `CURRENT_HB_COUNT` | The existing plan's bay count (21), used to mark the cost curve |

Two helper functions keep chart code clean:
- **`_show_fig(fig)`** — saves any matplotlib figure to a `BytesIO` PNG buffer and renders it with `st.image()`. This avoids the `MediaFileStorageError` that occurs on Streamlit Cloud when `st.pyplot()` is used and the figure is garbage-collected before the browser fetches it.
- **`_style(ax)`** — applies the shared visual style (background color, grid, spine removal) to any axes object.

Data loaders are decorated with `@st.cache_data` so they only run once per session:
- `load_proc_data` / `load_shift_data` — read the CSV input files and add human-readable label columns
- `get_file_paths` — resolves the correct file paths for the selected scenario
- `get_baseline_cost_table` — computes the HB cost curve from hardcoded case tables (no simulation needed; visible immediately on page load)

### 3. Chart functions (lines 135–611)
All chart functions return a `matplotlib.figure.Figure` and are called with `_show_fig(...)`. They are grouped by purpose:

**Exploratory Data Analysis (EDA)**
Used in the Data Overview tab. None of these require the simulation to have run.

| Function | Chart |
|----------|-------|
| `plot_volume_by_lab` | Bar: procedure count by Cath vs EP |
| `plot_proc_duration` | Overlapping histogram: procedure duration distribution |
| `plot_horizon` | Horizontal bar: scheduling horizon (emergency / same-day / same-week) |
| `plot_pre_post_times` | Dual histogram: pre- and post-procedure HB times |
| `plot_daily_volume` | Line chart: daily procedure count over the simulation period |
| `plot_provider_workload` | Horizontal bar: top 20 providers by volume |
| `plot_shift_types` | Bar: shift types (full / half / quarter day) |
| `plot_shift_load` | Line chart: daily provider capacity |

**Cost context**
Also in the Data Overview tab, these show the economic backdrop before running the simulation.

| Function | Chart |
|----------|-------|
| `plot_post_time_by_lab` | Bar: average post-procedure HB recovery time by lab |
| `plot_hb_demand_by_type` | Horizontal bar: top procedure types by HB recovery time |
| `plot_cost_curve` | Stacked area + line: daily HB cost vs bay count, marking the current plan and cost-minimizing point |

**Simulation output charts**
These require simulation results (`summary` dict from `RunSimulation`).

| Function | Chart |
|----------|-------|
| `plot_hb_peak_distribution` | Histogram of daily peak HB occupancy with P90/P95 markers |
| `plot_close_time_sensitivity` | Dual-axis: days with HB demand after close + avg bay-hours after close |

**Policy comparison charts**
These require the ranked policy results list from `comparePriorityRules`. Each accepts the `policy_results` list (one dict per policy).

| Function | Chart |
|----------|-------|
| `plot_policy_utilization` | Grouped bar: Cath and EP utilization per policy |
| `plot_policy_overflow` | Stacked bar: overflow procedures by room type per policy |
| `plot_policy_hb_and_close` | Side-by-side horizontal bars: recommended HB count and close hour per policy |
| `plot_policy_summary_table` | Returns a `DataFrame` for `st.dataframe` (not a chart) |
| `plot_policy_radar` | Radar/spider chart: 5 policies × 5 normalised KPIs |
| `plot_policy_heatmap` | Color-coded heatmap: green = better, red = worse per metric |
| `plot_policy_composite_score` | Horizontal bar: average normalised score across all KPIs |

The helper `_norm(vals, higher_is_better)` min-max normalises a list to [0, 1] and optionally inverts it, so all metrics can be compared on the same scale regardless of direction.

### 4. Page layout and sidebar (lines 613–650)
`st.set_page_config` sets the title, icon, and wide layout. The sidebar contains all user controls:

| Control | Effect |
|---------|--------|
| Case volume scenario | Selects the input CSV files (historical / high-volume EP / Cath only) |
| Scheduling priority rule | Sets the sort order for procedures in the single-run simulation |
| Cath rooms | How many Cath procedure rooms are available |
| Mean HB cleaning time | Average time (hours) to clean a bay between patients |
| Time resolution | Discretization bin size for the simulation (1, 5, or 10 minutes) |
| Random seed | Fixes randomness for reproducibility |
| Compare all scheduling policies | Runs 5 simulations instead of 1 to populate the Policy Comparison tab |
| Run Simulation | Triggers the simulation; nothing runs until this is clicked |

After the sidebar, the app immediately loads procedure and shift data (always visible, cached) and creates the five tabs.

### 5. Data Overview tab (always visible, lines 652–760)
This tab renders without any simulation. It shows EDA charts, shift statistics, cost assumptions, HB demand drivers, and the baseline cost curve. Users can explore the input data and understand the economic model before running anything.

### 6. Simulation execution and result tabs (lines 762–1037)
If **Run Simulation** has not been clicked, placeholder info messages are shown in all result tabs and execution stops.

When the button is clicked, the app runs inside `st.spinner`:

1. **Build parameters** — `make_params()` constructs a `Params` object from sidebar values
2. **Policy comparison (optional)** — if the checkbox is ticked, `Simulation.comparePriorityRules()` runs the simulation once per priority rule and returns `{"best": ..., "ranked": [...]}`. The ranked list and best policy dict are stored separately.
3. **Main simulation** — `Simulation.RunSimulation()` runs the simulation with the user-selected priority rule and returns `(timePeriod, summary)`. The ranked policy list is passed in so `VisualizationAnalysis` can include policy comparison charts if available.

Results populate four tabs:

**Summary tab**
Key metric cards (recommended bays, utilization, overflow, close time), the HB peak occupancy histogram, an overflow breakdown by room, and the close-time sensitivity chart with a data table.

**Charts tab**
Calls `VA.build_all_key_figures(summary, policy_results=...)` which returns a dict of named figures. Each figure is rendered with `_show_fig`. If policy results are available, policy comparison charts are included here too.

**Cost Analysis tab**
Displays the cost tables and recommendations from `summary["cost_analysis"]` — holding bay count (service-constrained vs cost-minimizing) and close time (cost-minimizing).

**Policy Comparison tab**
Only active when "Compare all scheduling policies" was checked. Shows:
- A success banner naming the top-ranked policy
- Composite score bar chart (recommended policy highlighted in blue)
- Radar/spider chart (normalised KPIs, larger polygon = better)
- Performance heatmap (green = better per column)
- Summary table with all KPIs per policy
- Individual metric breakdowns (utilization, overflow, HB count and close time)
- Selected-policy detail cards for the currently chosen priority rule

---

## Running Locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Running in Google Colab

Open `EP_CATH_Python_Code_Viz.ipynb` and run all cells in order:

1. **Cell 4** — clones the latest code from GitHub
2. **Cell 5** — imports and reloads modules
3. **Cell 6** — runs the simulation and generates charts

> Cells 2 and 3 are legacy leftovers and can be ignored or deleted.
