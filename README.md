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
