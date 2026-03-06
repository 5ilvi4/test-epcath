from __future__ import annotations

"""
Cost-analysis helpers for the Joint EP/CATH Lab case.

This module sits on top of the DES outputs. It implements the case assumptions:
- <= 10% of operating days with at least one overcapacity instance
- $600 contribution margin lost per cancelled procedure
- $10 per empty holding-bay hour
- $230 per admitted patient at close
- 4:1 patient-to-nurse ratio
- $48/hour base nursing wage
- 1.5x overtime wage

Use this module after running the DES and creating summary tables.
"""

from dataclasses import dataclass
from math import ceil
from typing import Iterable, Optional, Union

import pandas as pd


@dataclass(frozen=True)
class HoldingBayCostParams:
    simulated_days: int = 260
    overcapacity_day_threshold: float = 0.10
    contribution_margin_per_cancelled_procedure: float = 600.0
    empty_holding_bay_cost_per_hour: float = 10.0
    overcapacity_block_minutes: int = 5


@dataclass(frozen=True)
class CloseTimeCostParams:
    admission_cost_per_patient: float = 230.0
    nurse_to_patient_ratio: float = 4.0
    base_wage_per_hour: float = 48.0
    overtime_multiplier: float = 1.5
    coverage_quantile: float = 0.95
    baseline_close_time: str = "17:00"


TimeLike = Union[str, float, int]


def _to_dataframe(data: Union[pd.DataFrame, Iterable[dict]]) -> pd.DataFrame:
    if isinstance(data, pd.DataFrame):
        return data.copy()
    return pd.DataFrame(list(data))


def _time_to_hours(value: TimeLike) -> float:
    if isinstance(value, (float, int)):
        return float(value)
    value = str(value).strip()
    if ":" in value:
        hh, mm = value.split(":", 1)
        return int(hh) + int(mm) / 60.0
    return float(value)


def _hours_to_hhmm(hours: float) -> str:
    total_minutes = int(round(hours * 60))
    hh = total_minutes // 60
    mm = total_minutes % 60
    return f"{hh:02d}:{mm:02d}"


# -----------------------------------------------------------------------------
# Holding-bay sizing analysis
# -----------------------------------------------------------------------------

def compute_overcapacity_service_table(
    overcapacity_data: Union[pd.DataFrame, Iterable[dict]],
    params: HoldingBayCostParams = HoldingBayCostParams(),
    hb_col: str = "hb_count",
    days_col: str = "days_with_instances",
    pct_col: Optional[str] = None,
) -> pd.DataFrame:
    df = _to_dataframe(overcapacity_data)

    if pct_col is None and "pct_days_with_instances" in df.columns:
        pct_col = "pct_days_with_instances"

    if days_col not in df.columns and pct_col is None:
        raise ValueError("Need either days_with_instances or pct_days_with_instances")

    if days_col not in df.columns:
        df[days_col] = df[pct_col] * params.simulated_days

    if pct_col is None:
        pct_col = "pct_days_with_instances"
        df[pct_col] = df[days_col] / params.simulated_days

    df["meets_service_constraint"] = df[pct_col] <= params.overcapacity_day_threshold
    df["max_allowed_days"] = params.simulated_days * params.overcapacity_day_threshold
    return df.sort_values(hb_col).reset_index(drop=True)


def recommend_hb_by_service_constraint(
    overcapacity_data: Union[pd.DataFrame, Iterable[dict]],
    params: HoldingBayCostParams = HoldingBayCostParams(),
    hb_col: str = "hb_count",
    days_col: str = "days_with_instances",
    pct_col: Optional[str] = None,
):
    df = compute_overcapacity_service_table(
        overcapacity_data, params=params, hb_col=hb_col, days_col=days_col, pct_col=pct_col
    )
    feasible = df[df["meets_service_constraint"]]
    if feasible.empty:
        raise ValueError("No candidate holding-bay count satisfies the service constraint.")
    return feasible.sort_values(hb_col).iloc[0]


def compute_hb_cost_table(
    overcapacity_data: Union[pd.DataFrame, Iterable[dict]],
    empty_bay_data: Union[pd.DataFrame, Iterable[dict]],
    params: HoldingBayCostParams = HoldingBayCostParams(),
    hb_col: str = "hb_count",
    avg_instances_col: str = "avg_instances_per_day",
    avg_empty_hour_blocks_col: str = "avg_daily_empty_hour_blocks",
) -> pd.DataFrame:
    over_df = _to_dataframe(overcapacity_data)
    empty_df = _to_dataframe(empty_bay_data)
    merged = pd.merge(over_df, empty_df, on=hb_col, how="inner")

    merged["delay_60min_blocks"] = (
        merged[avg_instances_col] * params.overcapacity_block_minutes / 60.0
    )
    merged["cancellation_cost"] = (
        merged["delay_60min_blocks"] * params.contribution_margin_per_cancelled_procedure
    )
    merged["empty_holding_bay_cost"] = (
        merged[avg_empty_hour_blocks_col] * params.empty_holding_bay_cost_per_hour
    )
    merged["total_holding_bay_cost"] = (
        merged["cancellation_cost"] + merged["empty_holding_bay_cost"]
    )
    return merged.sort_values(hb_col).reset_index(drop=True)


def recommend_hb_by_total_cost(
    overcapacity_data: Union[pd.DataFrame, Iterable[dict]],
    empty_bay_data: Union[pd.DataFrame, Iterable[dict]],
    params: HoldingBayCostParams = HoldingBayCostParams(),
    hb_col: str = "hb_count",
    avg_instances_col: str = "avg_instances_per_day",
    avg_empty_hour_blocks_col: str = "avg_daily_empty_hour_blocks",
):
    table = compute_hb_cost_table(
        overcapacity_data,
        empty_bay_data,
        params=params,
        hb_col=hb_col,
        avg_instances_col=avg_instances_col,
        avg_empty_hour_blocks_col=avg_empty_hour_blocks_col,
    )
    return table.sort_values(["total_holding_bay_cost", hb_col]).iloc[0]


# -----------------------------------------------------------------------------
# Closing-time analysis
# -----------------------------------------------------------------------------

def compute_incremental_close_benefit(
    close_data: Union[pd.DataFrame, Iterable[dict]],
    time_col: str = "close_time",
    avg_occ_col: str = "avg_occupancy",
) -> pd.DataFrame:
    df = _to_dataframe(close_data)
    df["close_hours"] = df[time_col].map(_time_to_hours)
    df = df.sort_values("close_hours").reset_index(drop=True)
    df["incremental_pct_diff"] = df[avg_occ_col].pct_change()
    return df


def _staff_cost(hours: float, rounded_staff: int, hourly_rate: float) -> float:
    return hours * rounded_staff * hourly_rate


def compute_close_time_cost_table(
    close_data: Union[pd.DataFrame, Iterable[dict]],
    params: CloseTimeCostParams = CloseTimeCostParams(),
    time_col: str = "close_time",
    avg_occ_col: str = "avg_occupancy",
    p95_occ_col: str = "p95_occupancy",
) -> pd.DataFrame:
    df = _to_dataframe(close_data)
    required = {time_col, avg_occ_col, p95_occ_col}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns for close-time analysis: {sorted(missing)}")

    baseline_hours = _time_to_hours(params.baseline_close_time)
    df["close_hours"] = df[time_col].map(_time_to_hours)
    df = df.sort_values("close_hours").reset_index(drop=True)

    df["incremental_hours"] = df["close_hours"] - baseline_hours
    df["base_staff_float"] = df[avg_occ_col] / params.nurse_to_patient_ratio
    df["base_staff_rounded"] = df["base_staff_float"].apply(lambda x: max(1, ceil(x)))

    df["additional_patients_95"] = (df[p95_occ_col] - df[avg_occ_col]).clip(lower=0.0)
    df["overtime_staff_float"] = df["additional_patients_95"] / params.nurse_to_patient_ratio
    df["overtime_staff_rounded"] = df["overtime_staff_float"].apply(
        lambda x: 0 if x <= 0 else ceil(x)
    )

    df["base_staff_cost"] = [
        _staff_cost(h, s, params.base_wage_per_hour)
        for h, s in zip(df["incremental_hours"], df["base_staff_rounded"])
    ]
    overtime_rate = params.base_wage_per_hour * params.overtime_multiplier
    df["overtime_staff_cost"] = [
        _staff_cost(h, s, overtime_rate)
        for h, s in zip(df["incremental_hours"], df["overtime_staff_rounded"])
    ]
    df["estimated_labor_cost"] = df["base_staff_cost"] + df["overtime_staff_cost"]

    # At 95% coverage, use p95 end-of-day occupancy as admitted patients.
    df["admitted_patients_95"] = df[p95_occ_col]
    df["admission_cost"] = df["admitted_patients_95"] * params.admission_cost_per_patient
    df["total_cost"] = df["estimated_labor_cost"] + df["admission_cost"]
    df["close_time_hhmm"] = df["close_hours"].map(_hours_to_hhmm)
    return df


def recommend_close_time_by_total_cost(
    close_data: Union[pd.DataFrame, Iterable[dict]],
    params: CloseTimeCostParams = CloseTimeCostParams(),
    time_col: str = "close_time",
    avg_occ_col: str = "avg_occupancy",
    p95_occ_col: str = "p95_occupancy",
):
    table = compute_close_time_cost_table(
        close_data, params=params, time_col=time_col, avg_occ_col=avg_occ_col, p95_occ_col=p95_occ_col
    )
    return table.sort_values(["total_cost", "close_hours"]).iloc[0]


# -----------------------------------------------------------------------------
# Convenience wrappers
# -----------------------------------------------------------------------------

def summarize_hb_decision(
    overcapacity_data: Union[pd.DataFrame, Iterable[dict]],
    empty_bay_data: Union[pd.DataFrame, Iterable[dict]],
    params: HoldingBayCostParams = HoldingBayCostParams(),
    hb_col: str = "hb_count",
    days_col: str = "days_with_instances",
    pct_col: Optional[str] = None,
    avg_instances_col: str = "avg_instances_per_day",
    avg_empty_hour_blocks_col: str = "avg_daily_empty_hour_blocks",
) -> dict:
    service_choice = recommend_hb_by_service_constraint(
        overcapacity_data, params=params, hb_col=hb_col, days_col=days_col, pct_col=pct_col
    )
    cost_table = compute_hb_cost_table(
        overcapacity_data,
        empty_bay_data,
        params=params,
        hb_col=hb_col,
        avg_instances_col=avg_instances_col,
        avg_empty_hour_blocks_col=avg_empty_hour_blocks_col,
    )
    cost_choice = cost_table.sort_values(["total_holding_bay_cost", hb_col]).iloc[0]
    return {
        "service_constraint_recommendation": service_choice,
        "cost_recommendation": cost_choice,
        "cost_table": cost_table,
    }


def summarize_close_time_decision(
    close_data: Union[pd.DataFrame, Iterable[dict]],
    params: CloseTimeCostParams = CloseTimeCostParams(),
    time_col: str = "close_time",
    avg_occ_col: str = "avg_occupancy",
    p95_occ_col: str = "p95_occupancy",
) -> dict:
    benefit_table = compute_incremental_close_benefit(
        close_data, time_col=time_col, avg_occ_col=avg_occ_col
    )
    cost_table = compute_close_time_cost_table(
        close_data,
        params=params,
        time_col=time_col,
        avg_occ_col=avg_occ_col,
        p95_occ_col=p95_occ_col,
    )
    cost_choice = cost_table.sort_values(["total_cost", "close_hours"]).iloc[0]
    return {
        "incremental_benefit_table": benefit_table,
        "cost_table": cost_table,
        "cost_recommendation": cost_choice,
    }
