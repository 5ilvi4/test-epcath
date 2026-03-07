# test-epcath

What the Simulation Does
This is a Discrete Event Simulation (DES) of a hospital's joint EP (Electrophysiology) and Cath (Catheterization) lab. The goal is to figure out:

How many holding bay spaces to build
What time the holding bay needs to stay open until
How well the labs are utilized
The Core Logic Flow
1. Read Input Data
readShiftData and readProcData load two CSV files:

Shift data — which doctors/providers work which rooms on which days
Procedure data — all 7,402 patient procedures with their durations, types, urgency levels
2. Clean Procedure Times (cleanProcTimes)
Each procedure time gets turnover time added (time to clean the room between patients). If the total exceeds the max room time, it's capped. This prevents procedures from running impossibly long.

3. Pack Shifts into Rooms
timePeriod.packShifts(shifts, myP) — assigns each provider shift to a specific room for that day. Rooms are divided into Cath rooms, EP rooms, and a "middle" room.

4. Pack Procedures into Shifts (the core simulation)
timePeriod.packProcedures(procedures, myP) — this is where the actual scheduling happens:

Procedures are sorted by priority rule (historical order, longest first, shortest first, etc.)
Each procedure is placed into the next available time slot in the appropriate room
If a procedure runs past the room's closing time → it counts as an "overflow"
Same-day and emergency procedures get priority over pre-scheduled ones
5. Track Holding Bay (HB) Occupancy
As procedures finish in the lab, patients move to the holding bay for recovery. The simulation tracks:

How many patients are in the holding bay at every 5-minute interval, every day
The peak occupancy per day
6. Build Summary Statistics
buildScenarioSummary collects:

Room utilization (% of scheduled time actually used)
Overflow count (procedures that ran late)
Crossover count (Cath procedures done in EP rooms or vice versa)
Holding bay demand over time
7. Cost Analysis (runCostAnalysis)
Uses economic assumptions to calculate the optimal number of holding bays:

Too few bays → patients get delayed or cancelled → lost revenue ($600/cancellation)
Too many bays → empty bays sitting idle → wasted cost ($10/empty bay-hour)
The optimal point minimizes the sum of both costs
Similarly for closing time:

Staying open later → labor cost (nurses at $48/hr base, 1.5x overtime)
Closing too early → patients admitted to inpatient beds → $230/admission
8. Visualizations
VA.build_all_key_figures generates charts for all of the above — cost curves, utilization bars, policy comparisons.

Key Design Choices
Concept	How it works
Priority rules	You can compare 5 different ways to sort procedures (historical, longest first, etc.) to see which minimizes overflow
5-minute resolution	Time is discretized into 5-minute bins — procedures occupy a set of bins
Holding bay model	Each patient occupies the HB from procedure end until post-proc time finishes, then a random cleaning time
Overflow	If a shift ends and a procedure isn't done, it's counted as overflow (the room runs late)
95th percentile sizing	Rather than sizing for the worst ever day, the recommendation is the 95th percentile — handles 95% of days without overcapacity
now do the same for CostAnalysis
I already read CostAnalysis.py earlier, so here's the full breakdown:

What CostAnalysis Does
It answers two specific planning questions using economics:

How many holding bay spaces should we build?
What time should the holding bay close?
Question 1: How Many Holding Bays?
The core idea is a cost trade-off curve. As you add more bays:

Overcapacity days go down (fewer cancellations) → cancellation cost decreases
Empty bays increase (more wasted space) → empty bay cost increases
The optimal number is where the total cost is minimized.

The math (compute_hb_cost_table)
For each candidate bay count (e.g., 11 through 21 bays):


cancellation_cost = avg_overcapacity_instances_per_day
                    × (5 min block / 60)        ← convert to hours
                    × $600 per cancellation

empty_bay_cost    = avg_empty_bay_hours_per_day
                    × $10 per empty bay-hour

total_cost        = cancellation_cost + empty_bay_cost
Assumptions baked in:

Each overcapacity instance = a 5-minute delay block
A delay block = a potential cancellation worth $600 in lost contribution margin
An empty bay costs $10/hour
Service constraint (recommend_hb_by_service_constraint)
Even if cost says "fewer bays is cheaper," there's a hard service rule:

No more than 5% of operating days should have any overcapacity event

So the final recommendation takes the higher of:

The cost-minimizing bay count
The minimum bay count that satisfies the ≤5% rule
Question 2: What Time Should the Holding Bay Close?
For each candidate close time (17:00 through 24:00), the model calculates:

The math (compute_close_time_cost_table)

incremental_hours = close_time - 17:00 baseline

base_staff        = ceil(avg_occupancy / 4)     ← 4:1 patient-to-nurse ratio
overtime_staff    = ceil(95th_pct_occupancy - avg_occupancy) / 4

base_staff_cost   = incremental_hours × base_staff × $48/hr
overtime_cost     = incremental_hours × overtime_staff × $72/hr  (1.5× overtime)

admission_cost    = 95th_pct_occupancy × $230    ← cost of admitting remaining patients

total_cost        = labor_cost + admission_cost
Assumptions baked in:

Baseline close time is 17:00 — anything later is incremental cost
4 patients per nurse ratio
Nurses cost $48/hour base, $72/hour overtime
Admitting a patient to inpatient costs $230
The optimal close time is whichever hour minimizes total_cost.

How the Two Analyses Connect to the Simulation

Simulation runs
    ↓
buildCostInputsFromSimulation()   ← uses actual simulated HB occupancy
    ↓ produces:
    overcap_rows    → how many days were over capacity at each bay count
    empty_rows      → how many empty bay-hours at each bay count
    close_rows      → avg & 95th pct occupancy at each close time
    ↓
CostAnalysis functions compute costs
    ↓
Recommendations printed + visualized
Summary Table
Parameter	Value	Affects
$600	Lost contribution margin per cancellation	Penalizes too few bays
$10/hr	Empty bay holding cost	Penalizes too many bays
5%	Max days with overcapacity	Service constraint floor
4:1	Patient-to-nurse ratio	Staffing cost calculation
$48/hr	Base nurse wage	Close time labor cost
1.5×	Overtime multiplier	Late-hour staffing premium
$230	Admission cost per patient	Penalizes closing too early
