# EP/CATH Lab Planning Simulator

> **New here?** Start with the [Plain-Language Overview](#plain-language-overview) — no medical or technical background needed. The deeper technical sections follow after.

---

## Plain-Language Overview

### What is this?

This is a planning tool built for a hospital that is designing a new medical procedure lab. It helps answer three very practical questions before the lab is even built:

1. **How many recovery spaces do we need?**
2. **What time can we close the recovery area each day?**
3. **What is the best way to order patient procedures each morning?**

Getting these decisions wrong is costly. Too few recovery spaces means patients have nowhere to go after their procedure — leading to cancellations and delays. Too many spaces means the hospital paid to build and staff rooms that sit empty most of the day. Closing too early strands patients and forces expensive hospital admissions. The wrong procedure order wastes room time and creates unnecessary overtime.

This simulator uses real historical data to test different options and recommend the best configuration before anything is built or changed.

---

### What are EP and Cath labs?

A hospital's **Cath lab** (Catheterization laboratory) is where doctors insert thin tubes (catheters) into blood vessels to diagnose and treat heart conditions — such as clearing a blockage or placing a stent.

An **EP lab** (Electrophysiology laboratory) is where doctors diagnose and treat electrical problems in the heart — such as abnormal heart rhythms (arrhythmias). Treatments include ablations and pacemaker implants.

Both labs involve highly specialised equipment and staff, and both require patients to recover in a monitored space before going home or to a regular hospital room. This hospital is building a **joint lab** — one shared facility that handles both Cath and EP procedures — which means they need to carefully plan how the two types of work will share rooms, staff, and recovery space.

---

### What is a "holding bay"?

The **holding bay (HB)** is the recovery area — the room (or set of beds/spaces) where patients wait before their procedure and recover after it. Think of it like a waiting and recovery lounge managed by nurses.

- **Before the procedure:** the patient is prepared in the holding bay (IV lines placed, consent confirmed, monitoring started).
- **After the procedure:** the patient returns to the holding bay to recover — typically for 1–8 hours depending on the procedure — before being discharged or transferred.

Each space in the holding bay can only hold one patient at a time. If all spaces are occupied and another patient finishes their procedure, there is a problem: that patient has nowhere to go, which delays the room being cleaned and used for the next case.

---

### What is the "simulation"?

The simulator **replays one full year of procedures** (7,402 procedures from July 2015 data, projected forward) as if they were happening day by day. For each day, it:

1. Assigns providers (doctors, nurses) to rooms based on who is working that day
2. Schedules each procedure into the next available room slot
3. Tracks exactly when each patient finishes and enters the recovery holding bay
4. Tracks how many holding bay spaces are occupied at every 5-minute interval throughout the day
5. Records any procedures that couldn't fit into the day (called "overflow")

By running this replay, we get a detailed picture of what a typical day — and a peak day — actually looks like.

---

### Why use a simulation instead of just estimating?

A simple estimate might say: "We do about 30 procedures a day, each takes about 4 hours to recover, so we need about 5 bays." But real life is messier:

- Some days have 20 procedures, some days have 45
- Recovery times range from 30 minutes to 8 hours
- Some procedures run over their scheduled time
- Some days have more emergency cases that jump the queue
- Some providers work only half-days

A simulation captures all of this variability and tells you what actually happens 95% of the time — not just on an average day.

---

### The three planning questions, explained simply

#### Question 1: How many holding bays do we need?

The answer comes from looking at the busiest moments across all 260 simulated operating days. Specifically, the tool looks at the **95th percentile peak** — the number of bays occupied simultaneously on one of the 13 busiest days of the year.

> **Why 95th percentile and not the absolute worst day?**
> If you build for the single worst day in history, you end up with bays that sit empty 364 days a year — very expensive. The 95th percentile means the facility handles 95% of days without any bottleneck, and accepts a mild overflow on the remaining 5% (about 13 days per year). This is the standard planning benchmark in healthcare capacity design.

The tool also runs a cost check: it calculates what it costs if you have *too few* bays (procedures get cancelled or delayed, losing revenue) versus *too many* bays (idle space that still costs money to maintain). The final recommendation is the higher of (a) the cost-minimizing count and (b) the 95th-percentile safety floor.

---

#### Question 2: What time should the holding bay close?

The holding bay doesn't stay open all night — nurses need to go home. But closing too early means patients who are still recovering have to be admitted to a regular hospital bed (an "inpatient admission"), which is expensive and disruptive.

The tool evaluates every possible closing time from 5:00 PM to midnight and calculates the total cost of each option:

- **Close too early** → more patients stranded → more expensive inpatient admissions
- **Close too late** → longer nursing shifts → more overtime pay

The optimal closing time is where those two costs balance out and the total is lowest.

---

#### Question 3: Which scheduling policy is best?

Every morning, someone decides what order to run the day's procedures. The tool tests five different orderings:

| Policy | What it does |
|--------|-------------|
| **Historical** | Uses the same order as the real historical schedule |
| **Longest procedure first** | Puts the most time-consuming cases at the start of the day |
| **Shortest procedure first** | Knocks out the quick cases first |
| **Longest recovery time first** | Prioritises patients who will need the most time in recovery, getting them through earlier |
| **Shortest recovery time first** | Prioritises patients who recover fastest, clearing recovery space quickly |

Each policy is tested with everything else held equal. The one that produces the fewest delays, lowest peak holding bay demand, and best room efficiency is recommended.

> **Note:** "Compare all scheduling policies" is enabled by default — the app runs all five policies automatically when you click **Run Simulation**.

---

### How to read the app

The app has six tabs:

| Tab | What you'll find |
|-----|-----------------|
| **Data Overview** | Charts about the input data — how many procedures, how long they take, who's working, what recovery times look like. No simulation needed to see this. |
| **Summary** | After running the simulation: the key numbers at a glance — recommended bay count, room usage rates, number of delayed procedures, recommended closing time. Each metric has a collapsible `📐 Definition & formula` toggle. |
| **Charts** | Detailed charts: cost curves, utilization trends, overflow breakdown, holding bay demand over time, plus two heatmaps (HB demand by day/time and room schedule by room/time). Every chart has a `📐 Definition & formula` expander. |
| **Cost Analysis** | The economic trade-off tables with a full "Cost Model Assumptions & Calculation Overview" at the top, column-level definitions under each table, and the formulas behind every recommendation. |
| **Policy Comparison** | Side-by-side comparison of all five scheduling orders across every metric — composite score, radar chart, heatmap, and metric breakdowns. Enabled by default. |
| **Recommendations & Conclusion** | A consolidated summary of all three decisions — bay count, close time, and scheduling policy — with the evidence behind each, in one place. |

---

## Metrics: What Each Number Means

This section explains every metric the simulator produces. Each metric has a plain-English definition, the exact formula used to calculate it, and an explanation of why it matters.

> **Tip:** Every chart and table inside the app also has a `📐 Definition & formula` expander that you can open for a quick in-context reference.

---

### Room Utilization

**Plain English:** What percentage of the time each procedure room was actually in use during its scheduled working hours?

Think of it like a taxi on shift — a taxi with a passenger has 100% utilization; a taxi driving empty or parked has 0%. A room sitting idle between procedures is like a parked taxi: the driver (doctor/nurse) is still getting paid, but no revenue is being generated.

---

#### Cath Lab Utilization (`cath_utilization_avg`)

**Definition:** The fraction of total available Cath room-time that was occupied by a scheduled procedure, averaged across all simulated days.

**Formula:**
```
cath_utilization_avg =
    total minutes of procedures scheduled in Cath rooms (all days combined)
    ÷
    total available Cath room-minutes (rooms × shift length, all days combined)
```

**What "good" looks like:** 70–85% is typically considered healthy. Below 60% suggests the rooms are underused. Above 90% leaves no buffer for emergencies or overruns.

**Why it matters:** The main business case for hiring an additional EP provider depends on demonstrating that the EP rooms will be busy enough to justify the cost. This number is the evidence.

---

#### EP Lab Utilization (`ep_utilization_avg`)

**Definition / Formula:** Identical to Cath utilization, but calculated only for EP rooms and EP providers.

**Why it matters:** Same logic as above. If EP utilization is low under the current setup, adding another provider may not be justified. If it's high, there is a strong case for expansion.

---

#### Mean Room Utilization (`mean_room_utilization`)

**Definition:** The simple average of Cath and EP utilization.

**Formula:**
```
mean_room_utilization = (cath_utilization_avg + ep_utilization_avg) / 2
```

**Why it matters:** Used as a single summary number when comparing scheduling policies. Higher is better.

---

### Overflow (Procedures That Didn't Fit)

**Plain English:** How many procedures could not be started before their room had to close for the day?

Imagine a restaurant that stops seating new customers at 9 PM. If the kitchen is still behind at 9 PM and a table is waiting for their main course, that is an "overflow" — demand that the available time could not accommodate.

---

#### Total Overflow (`overflow_total`)

**Definition:** The number of procedures across all days and all room types that could not be scheduled before the room's closing time.

**Formula:**
```
overflow_total = overflowCath + overflowEP + overflowMiddle
```

| Component | Meaning |
|-----------|---------|
| `overflow_cath` | Cath-room procedures that didn't fit |
| `overflow_ep` | EP-room procedures that didn't fit |
| `overflow_middle` | Flex-room procedures that didn't fit |

**What causes overflow:** A procedure is counted as overflow when the scheduling algorithm runs out of time in a room's shift before placing all of that day's cases. This happens when earlier procedures run long, or when same-day and emergency cases (which get priority) consume more time than planned.

**Why it matters:** Each overflow event represents a patient whose care was delayed. Reducing overflow is the most direct way to improve patient access and reduce staff overtime.

---

### Crossover Procedures (`crossover_total`)

**Plain English:** How many procedures were done in a room of the "wrong" lab type?

For example, a Cath procedure placed into an EP room when the Cath rooms were all full, or vice versa. This is only possible in a joint lab where some rooms are flexible.

**Formula:**
```
crossover_total = cathToEP + epToCath
```

**Why it matters:** Crossover is actually a sign that the joint lab concept is working — spare capacity in one lab is being used to absorb excess demand from the other. However, it also means nurses and technicians need to be cross-trained in both types of procedure. High crossover numbers strengthen the argument for joint staffing.

---

### Holding Bay (Recovery Space) Metrics

The holding bay is the recovery area where patients spend time before and after their procedure. The simulator tracks how many bays are occupied at every 5-minute interval across the entire day, for every simulated day.

**How occupancy is counted:**
```
Patient occupies a bay from:
  procedure_end_time
  until:
  procedure_end_time + recovery_hours + bay_cleaning_time
```

The simulation window is 40 hours (to catch rare cases where recovery extends past midnight). Occupancy is recorded in 5-minute slots.

---

#### Daily Peak Bay Occupancy (`daily_peak_bays`)

**Plain English:** On each day, what was the maximum number of bays occupied at the same time?

**Formula:**
```
daily_peak_bays[day] = highest simultaneous occupancy count recorded that day
```

**Example:** If at 3:15 PM on a Tuesday there were 12 patients in the holding bay at the same time, that day's peak is 12 — even if the rest of the day was much quieter.

**Why it matters:** This is the number that determines how many bays you actually needed on that day. If the peak ever exceeds the number of bays you built, a bottleneck occurred.

---

#### Overall Peak (`overall_peak_bays`)

**Plain English:** What was the single busiest moment across the entire year?

**Formula:**
```
overall_peak_bays = maximum of all daily_peak_bays values
```

**Why it matters:** This is the worst case. It's useful to know, but sizing the facility to handle the absolute worst day every day would be over-engineering — that worst day may happen only once a year.

---

#### P90 and P95 Daily Peak (`peak_bays_p90`, `peak_bays_p95`)

**Plain English:** What bay count would be enough on 90% (or 95%) of days?

**Formula:**
```
Sort all 260 daily peak values from lowest to highest.
P90 = the value at position 234  (90% of the way through the sorted list)
P95 = the value at position 247  (95% of the way through the sorted list)
```

**Example:** If P95 = 14, then on 247 out of 260 simulated days, the peak never exceeded 14 bays. Only the 13 busiest days exceeded it.

**Why P95 is the recommendation threshold:** Building to P95 means the facility handles 95% of all operating days without any bottleneck. The 5% of days that exceed capacity are rare and manageable (e.g., with temporary overflow protocols). Sizing to P90 saves money but accepts more frequent bottlenecks.

---

#### Recommended Bay Count (`recommended_bays_p95`)

**Formula:**
```
recommended_bays_p95 = ceiling( peak_bays_p95 )
```

Ceiling means rounding up to the next whole number, because you cannot build half a bay.

---

#### Daily Last Occupied Time (`daily_last_occupied_hours`)

**Plain English:** What time did the last patient leave the holding bay on each day?

**Formula:**
```
Find the last 5-minute slot of the day where any patient was in the bay.
Convert that slot number to a clock time (hours since midnight).
```

**Example:** If the last occupied slot was slot 228 (at 5-minute intervals), that is 228 × 5 = 1,140 minutes = 19 hours = 7:00 PM.

**Why it matters:** This tells you when the bay is actually empty — not just when the last procedure ends, but when the last recovering patient has left. This drives the closing time recommendation.

---

#### Recommended Close Time (`recommended_close_p95`)

**Plain English:** On 95% of days, what time is the last patient gone from the holding bay?

**Formula:**
```
last_occupied_p95_hours = 95th percentile of all daily_last_occupied_hours values
recommended_close_p95   = convert to HH:MM format
```

**Important note:** On rare occasions (when late procedures have very long recovery times), this value can exceed midnight and will be shown as "next day HH:MM". This is not a bug — it reflects real late-ending case days.

**Why it matters:** This is the capacity-based answer to "when can we close?" — derived purely from when patients actually leave, independent of cost. The cost model below may suggest a different closing time based on economic trade-offs.

---

### Close-Time Sensitivity Analysis

**Plain English:** If we close the holding bay at a given time, how many patients would still be in recovery?

For each candidate closing time from 5:00 PM to midnight, the simulator counts:

| Metric | Meaning |
|--------|---------|
| `days_with_any_demand_after_close` | How many days per year would still have at least one patient in the bay after this closing time |
| `total_bay_hours_after_close` | The total "patient-hours" of recovery demand that falls after this closing time, summed across all days |
| `avg_bay_hours_after_close_per_day` | The average amount of recovery demand left unserved per day at this closing time |

**Why it matters:** These patients do not disappear when the bay "closes." They become inpatient admissions — expensive hospital stays that could have been avoided with a slightly later close time. This table makes that trade-off visible before any decision is made.

---

### Heatmaps

Two heatmaps are available in the **Charts** tab after running the simulation.

#### Holding-Bay Demand Heatmap

Each row is one simulated day; each column is a 5-minute time slot (06:00–24:00). Colour intensity shows how many patients were in the holding bay during that slot — light yellow = few patients, dark red = many patients.

**Formula:**
```
demand(day, slot) = bins[2][(day, slot_index)]
where slot_index = minutes_from_midnight / resolution
```

Use this to spot the time-of-day patterns in HB pressure, and identify whether peak demand is consistently at the same time or scattered across the afternoon.

#### Room Schedule Heatmap

Each row is one procedure room (Cath 1–N or EP 1–N); each column is a 5-minute time slot (07:00–22:00). Colour shows the percentage of simulated days on which that room had at least one procedure scheduled in that slot — white = never used, dark blue = used almost every day.

**Formula:**
```
utilisation%(room, slot) = (# days with a procedure in that slot) / total_days × 100
```

Use this to see which rooms are heavily scheduled and when, and identify rooms or time windows that are underutilised.

---

### Cost Analysis Metrics

All cost figures represent **daily average costs** unless stated otherwise. They are used to find the combination of bay count and close time that minimizes total spending while still meeting patient care standards.

> **Full calculation walkthrough:** Open the **"Cost Model Assumptions & Calculation Overview"** expander at the top of the Cost Analysis tab for step-by-step formulas and a parameter reference table.

---

#### Cancellation Cost (too few bays)

**Plain English:** How much does it cost per day when the holding bay is full and patients can't enter recovery?

When all bays are occupied and another patient finishes their procedure, the room cannot be turned over — the next scheduled case is delayed or cancelled. Each such delay carries a financial cost in lost revenue and wasted physician time.

**Formula:**
```
delay_hours       = (average overcapacity 5-minute slots per day) × 5 min ÷ 60
cancellation_cost = delay_hours × $600 per hour
```

The $600/hour figure represents the contribution margin (revenue minus direct costs) lost when a procedure is cancelled or significantly delayed.

---

#### Empty Bay Cost (too many bays)

**Plain English:** How much does it cost per day to have bays that nobody is using?

Built bays still cost money: cleaning supplies, allocated nursing time, equipment maintenance, and overhead. Every hour a bay sits empty is money spent on capacity that isn't generating value.

**Formula:**
```
empty_holding_bay_cost = (average idle bay-hours per day) × $10 per hour
```

---

#### Total Holding Bay Cost

**Plain English:** The combined daily cost at any given bay count — balancing the risk of having too few versus the waste of having too many.

**Formula:**
```
total_holding_bay_cost = cancellation_cost + empty_holding_bay_cost
```

This creates a U-shaped cost curve. The bottom of the U is the cost-minimizing bay count. Building fewer bays than this point makes cancellations expensive enough to outweigh any savings. Building more drives up idle-space costs.

---

#### Service Constraint (the patient-care floor)

**Plain English:** Even if the cost-minimizing bay count is acceptable financially, we also require that the bay is not overwhelmed too often. The constraint is: **no more than 5% of operating days can have any overcapacity event.**

**Formula:**
```
pct_days_with_overcapacity = days where peak exceeded bay count ÷ 260 total days
passes_constraint          = pct_days_with_overcapacity ≤ 5%
```

**Final bay count recommendation:** The higher of (a) the cost-minimizing count and (b) the minimum count that meets the 5% service constraint. This ensures both financial efficiency and patient care reliability.

---

#### Close Time — Labor Cost

**Plain English:** How much more does it cost in nursing wages for every extra hour the holding bay stays open beyond 5:00 PM?

**Formula:**
```
extra_hours          = closing_time − 17:00 (5:00 PM baseline)
nurses_needed        = round up( average occupancy ÷ 4 )     ← 4 patients per nurse
surge_nurses         = round up( (P95 occupancy − average) ÷ 4 )  ← for busy days

base_labor_cost      = extra_hours × nurses_needed × $48/hr
overtime_labor_cost  = extra_hours × surge_nurses × ($48 × 1.5)/hr
total_labor_cost     = base_labor_cost + overtime_labor_cost
```

The 4:1 patient-to-nurse ratio is the standard post-procedure staffing ratio. Surge nurses are needed on the 5% of days when occupancy is higher than average — they are paid at the overtime rate.

---

#### Close Time — Admission Cost

**Plain English:** How much does it cost when the bay closes while patients are still recovering?

Patients who haven't finished recovery when the bay closes must be admitted to a regular hospital bed as unplanned inpatients. This costs the hospital approximately $230 per patient in added overhead, bed management, and nursing reallocation.

**Formula:**
```
stranded_patients = P95 occupancy at the closing time
admission_cost    = stranded_patients × $230
```

**Why P95 and not the average?** We use the 95th-percentile demand to be conservative — we're calculating the cost on a high-demand day, not just an average day.

---

#### Total Close Time Cost

**Plain English:** The combined daily cost of choosing a particular closing time — staffing cost plus admission cost.

**Formula:**
```
total_cost = estimated_labor_cost + admission_cost
```

As closing time moves later: labor cost goes up (more hours, more nurses), admission cost goes down (fewer patients stranded). The recommended closing time is where total cost is lowest.

---

### Policy Ranking

**Plain English:** When comparing all five scheduling policies, which one "wins"?

The policies are ranked using a priority list — like a tiebreaker system in a competition:

| Priority | What is compared | Which is better | Why this order |
|----------|-----------------|-----------------|----------------|
| 1st | Total overflow (delayed procedures) | Fewer is better | Patient access comes first |
| 2nd | P95 peak holding bay count | Fewer is better | Fewer required bays = lower capital and staffing cost |
| 3rd | P95 last occupied time | Earlier is better | Earlier close = lower labor cost |
| 4th | Mean room utilization | Higher is better | More productive use of rooms |

The policy with the fewest overflow procedures wins. If two policies tie on overflow, the one requiring fewer holding bays wins. And so on.

---

### Composite Score

**Plain English:** A single 0-to-1 score that summarises how each scheduling policy performs across all metrics at once. Think of it like a school grade: 1.0 is the top of the class, 0.0 is the bottom.

**How it is calculated:**

First, each metric is rescaled so that 1.0 = best policy, 0.0 = worst policy on that metric:

```
For metrics where lower is better (overflow, bay count, close time):
  score = (worst value − this policy's value) ÷ (worst value − best value)

For metrics where higher is better (utilization):
  score = (this policy's value − worst value) ÷ (best value − worst value)

If all policies are identical on a metric:
  score = 1.0 (no difference to distinguish them)
```

Then the composite score is the average of all five rescaled scores:

```
composite_score = average of (
  rescaled cath utilization,
  rescaled EP utilization,
  rescaled overflow,
  rescaled P95 peak bays,
  rescaled P95 close time
)
```

**Caveat:** All five metrics are weighted equally. If your team cares more about one metric (e.g., patient access = minimise overflow), don't rely only on the composite score — use the performance heatmap in the Policy Comparison tab to apply your own priorities visually.

---

### Multi-Metric Radar Chart (Spider Chart)

**Plain English:** A spider web diagram that shows all five metrics and all five policies on one chart simultaneously — so you can immediately see which policy is strongest overall and exactly where each policy wins or loses.

#### What it looks like

Imagine a spider web. There are 5 "spokes" radiating from the centre, each representing one metric:

- **Cath utilization** — how busy the Cath rooms are
- **EP utilization** — how busy the EP rooms are
- **Overflow** — how many procedures didn't fit into the day
- **HB peak** — how many recovery bays were needed at the busiest moment
- **Close time** — what time the last patient left recovery

Each scheduling policy is drawn as a coloured polygon connecting its score on each spoke. All five polygons appear on the same chart.

#### How each spoke works

Every spoke runs from **0 at the centre** to **1 at the outer edge**, where **1 always means best on that metric** — regardless of whether the raw number is high or low:

| Metric | What you want | Who scores 1.0 |
|--------|--------------|----------------|
| Utilization | Higher is better | Policy with the highest utilization |
| Overflow | Lower is better | Policy with the fewest delayed procedures |
| HB peak | Lower is better | Policy needing the fewest recovery bays |
| Close time | Earlier is better | Policy where the last patient leaves earliest |

This rescaling (min-max normalisation) means you can compare percentages, procedure counts, bay counts, and clock hours all on the same chart — apples to apples.

#### How to read a polygon

- **Point near the outer edge on a spoke** → strong on that metric
- **Point near the centre on a spoke** → weak on that metric
- **Large polygon overall** → strong across the board
- **Lopsided polygon** → excels on some metrics but sacrifices others — a visible trade-off
- **The ideal policy** would fill the entire chart, touching the outer edge on all five spokes simultaneously

#### Example

Say Policy A (blue) reaches the outer edge on Utilization and Overflow but collapses toward the centre on Close Time. That means:
- ✓ It keeps rooms busy and avoids delays
- ✗ But patients are still in recovery late into the evening

Policy B (orange) might have a smaller but more evenly-shaped polygon — not the best at any single metric, but consistently decent across all five. Which is better depends on what the hospital prioritises most.

#### Why no policy fills the whole chart

No policy achieves a perfect pentagon. Improving one metric often worsens another — for example, front-loading long-recovery patients reduces holding bay peak (good) but may push long procedures into the end of the day and increase overflow (bad). The radar chart makes these trade-offs immediately visible, so the planning team can make an informed decision rather than optimising blindly for a single number.

---

## Economic Assumptions at a Glance

| Assumption | Value | What it represents |
|-----------|-------|-------------------|
| Lost revenue per cancelled procedure | $600 | Contribution margin lost when a case is cancelled due to no recovery space |
| Cost of an empty bay-hour | $10/hr | Maintenance, allocated staff time, and overhead for an unused bay |
| Maximum acceptable overcapacity days | 5% (≈13 days/year) | Patient care quality floor — the facility should handle 95% of days without any bottleneck |
| Patients per nurse in recovery | 4 : 1 | Standard post-procedure nursing ratio |
| Base nursing wage | $48/hr | Hourly labor cost for scheduling close-time staffing |
| Overtime multiplier | 1.5× ($72/hr) | Premium for hours worked beyond standard shift |
| Unplanned inpatient admission cost | $230 | Marginal cost when a recovery patient is admitted overnight due to early bay closure |
| Baseline close time reference | 17:00 (5:00 PM) | All incremental labor costs are calculated relative to this starting point |
| Simulated operating days | 260 days | Standard working-year assumption (5 days/week, 52 weeks) |
| Occupancy time slot | 5 minutes | Resolution at which bay occupancy is recorded during simulation |

---

## Project Structure

```
test-epcath/
├── app.py                         # The interactive web app (Streamlit)
├── Simulation.py                  # The simulation engine — runs the day-by-day replay
├── Params.py                      # All configurable parameters for the simulation
├── CostAnalysis.py                # The cost calculations (bay count and close time)
├── VisualizationAnalysis.py       # Chart generation
├── EP_CATH_Python_Code_Viz.ipynb  # Standalone version that runs in Google Colab
├── data/                          # Input data files (procedures and provider shifts)
└── requirements.txt               # Python packages required to run the app
```

---

## Technical Reference: How `app.py` Works

> This section is for developers. If you are not modifying the code, you can skip it.

`app.py` is the Streamlit front-end. It is structured in six logical sections:

### 1. Bootstrap and imports
Fixes the Python path so all modules can be imported regardless of launch location. Patches `os.chdir` to prevent Colab-specific directory changes from breaking the Streamlit Cloud deployment. Imports all required libraries and project modules. Sets `figure.max_open_warning = 0` to suppress batch-creation noise (figures are properly closed in `_show_fig`).

### 2. Constants and helpers

| Constant | Purpose |
|----------|---------|
| `SCENARIOS` | Maps human-readable scenario labels to internal keys used by `Params` |
| `PRIORITY_RULES` | The five scheduling rules shown in the sidebar dropdown |
| `BG`, `C1`, `C2`, `C3`, `GRID` | Shared dark-theme color palette for all charts |
| `COST_ASSUMPTIONS` | Cost parameters displayed in the Data Overview tab |
| `CURRENT_HB_COUNT` | The existing plan's bay count (21), used to mark the cost curve |
| `_CHART_META` | Dict of title, definition, and formula strings for every chart in the Charts tab |

Helper functions:
- **`_show_fig(fig)`** — saves any matplotlib figure to a `BytesIO` PNG buffer, calls `plt.close(fig)` to free memory, then renders with `st.image()`.
- **`_style(ax)`** — applies the shared dark visual style to any axes object.
- **`_fmt_close(t)`** — converts decimal hours to `HH:MM`; displays "next day HH:MM" for values ≥ 24h.
- **`_cached_simulation(...)`** — `@st.cache_resource` wrapper around `RunSimulation` + `comparePriorityRules`. Results are shared across all concurrent user sessions with identical parameters, preventing duplicate computation and reducing crash risk under load.

Data loaders (`load_proc_data`, `load_shift_data`, `get_baseline_cost_table`, `get_baseline_simulation_summary`) use `@st.cache_data` to run only once per deployment.

### 3. Chart functions
All chart functions return `matplotlib.figure.Figure` and are rendered with `_show_fig(...)`.

**EDA charts** (Data Overview tab — no simulation required):
`plot_volume_by_lab`, `plot_proc_duration`, `plot_horizon`, `plot_pre_post_times`, `plot_daily_volume`, `plot_provider_workload`, `plot_shift_types`, `plot_shift_load`

**Cost context charts** (Data Overview tab):
`plot_post_time_by_lab`, `plot_hb_demand_by_type`, `plot_cost_curve`

**Simulation output charts** (require `summary` dict from `RunSimulation`):
`plot_hb_peak_distribution`, `plot_close_time_sensitivity`, `plot_hb_demand_heatmap`, `plot_room_schedule_heatmap`

**Policy comparison charts** (require `policy_results` list from `comparePriorityRules`):
`plot_policy_utilization`, `plot_policy_overflow`, `plot_policy_hb_and_close`, `plot_policy_summary_table`, `plot_policy_radar`, `plot_policy_heatmap`, `plot_policy_composite_score`

### 4. Page layout and sidebar

| Sidebar control | Default | Effect |
|-----------------|---------|--------|
| Case volume scenario | Historical | Selects input CSV files |
| Scheduling priority rule | Historical | Sets procedure sort order for the single-run simulation |
| Cath rooms | 5 | Number of available Cath rooms (valid range: 4–7) |
| Mean HB cleaning time | — | Average time (hours) to clean a bay between patients |
| Time resolution | 5 min | Discretization bin size (1, 5, or 10 minutes) |
| Compare all scheduling policies | **Checked** | Runs 5 simulations to populate the Policy Comparison tab |
| Run Simulation | — | Triggers the simulation |

> **Cath room range:** Values below 4 cause a scheduling crash (rooms stack past midnight), and values above 7 exceed the maximum rooms the historical data ever needs. The slider is restricted to 4–7 to prevent invalid states.

### 5. Data Overview tab (always visible)
Renders without simulation. Shows EDA charts, shift statistics, cost assumptions, HB demand drivers, and baseline cost curve.

### 6. Simulation execution and result tabs
On button click, `_cached_simulation(...)` is called with the current sidebar parameters. On a cache hit (same parameters already computed), results are returned instantly. On a cache miss, the simulation runs and the result is cached for all future sessions with the same parameters.

Results populate five tabs:

- **Summary** — key metric cards with `📐 Definition & formula` expanders, HB peak histogram, overflow breakdown, close-time sensitivity chart
- **Charts** — full figure suite from `VA.build_all_key_figures()` with per-chart `📐 Definition & formula` expanders, plus HB demand heatmap and room schedule heatmap
- **Cost Analysis** — "Cost Model Assumptions & Calculation Overview" expander at top, cost tables with column-level `📐 Column definitions` expanders, and recommendation metrics
- **Policy Comparison** — composite score, radar chart, performance heatmap, summary table, metric breakdowns (always runs when "Compare all scheduling policies" is enabled, which is the default)
- **Recommendations & Conclusion** — consolidated decision summary for all three planning questions with expandable evidence and a written conclusion

### Concurrency and performance notes

- `@st.cache_resource` is used (not `@st.cache_data`) because `timePeriod` contains custom class instances that should not be pickled/copied. The cached object is shared read-only across sessions.
- All matplotlib figures are closed immediately after rendering (`plt.close(fig)` inside `_show_fig`) to prevent memory accumulation across Streamlit reruns.
- The Streamlit Community Cloud free tier provides ~800 MB RAM and 1 shared CPU. If many users run unique parameter combinations simultaneously, resource limits may still be reached. For higher concurrency, consider upgrading to a paid Streamlit tier or deploying on a dedicated VM.

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
