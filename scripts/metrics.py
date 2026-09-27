from __future__ import annotations

import numpy as np
import pandas as pd


def _linear_trend(values: np.ndarray) -> tuple[float, float]:
    """
    Returns:
        normalized slope in % of mean value per month,
        R²
    """

    if len(values) < 2:
        return 0.0, 0.0

    x = np.arange(len(values), dtype=float)
    y = values.astype(float)

    slope, intercept = np.polyfit(x, y, 1)

    predicted = slope * x + intercept

    ss_res = np.sum((y - predicted) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)

    if ss_tot == 0:
        r2 = 1.0
    else:
        r2 = 1 - ss_res / ss_tot

    mean_value = np.mean(y)

    slope_pct = (
        slope / mean_value * 100
        if mean_value > 0
        else 0.0
    )

    return float(slope_pct), float(r2)


def analyze_series(
    dataframe: pd.DataFrame,
) -> tuple[pd.DataFrame, dict, list[str]]:

    df = dataframe.copy()

    df["date"] = (
        pd.to_datetime(df["date"])
        .dt.to_period("M")
        .dt.to_timestamp()
    )

    df = df.sort_values("date").reset_index(drop=True)

    warnings = []

    if df["date"].duplicated().any():
        warnings.append(
            "Duplicate monthly observations were found."
        )

        df = df.drop_duplicates(
            subset=["date"],
            keep="last",
        )

    expected_dates = pd.date_range(
        df["date"].min(),
        df["date"].max(),
        freq="MS",
    )

    if len(expected_dates) != len(df):
        warnings.append(
            "The time series contains missing months."
        )

    df["rolling_3m"] = (
        df["views"]
        .rolling(
            window=3,
            min_periods=1,
        )
        .mean()
    )

    df["yoy_pct"] = (
        df["views"]
        .pct_change(
            periods=12,
            fill_method=None,
        )
        * 100
    )

    non_zero = df.loc[df["views"] > 0, "views"]

    if len(non_zero):
        baseline = float(non_zero.iloc[0])

        df["index_100"] = (
            df["views"] / baseline * 100
        )
    else:
        df["index_100"] = np.nan

    if "total_project_views" in df.columns:

        denominator = df["total_project_views"].replace(
            0,
            np.nan,
        )

        df["views_per_million"] = (
            df["views"]
            / denominator
            * 1_000_000
        )

    number_of_months = len(df)

    total_views = int(df["views"].sum())

    average_monthly_views = float(
        df["views"].mean()
    )

    current_12m_views = None
    previous_12m_views = None
    yoy_growth_pct = None

    if number_of_months >= 12:
        current_12m_views = int(
            df["views"].tail(12).sum()
        )

    if number_of_months >= 24:
        previous_12m_views = int(
            df["views"]
            .iloc[-24:-12]
            .sum()
        )

        if previous_12m_views > 0:
            yoy_growth_pct = (
                current_12m_views
                / previous_12m_views
                - 1
            ) * 100

    recent_yoy = (
        df["yoy_pct"]
        .dropna()
        .tail(12)
    )

    median_monthly_yoy_pct = None

    if len(recent_yoy):
        median_monthly_yoy_pct = float(
            recent_yoy.median()
        )

    trend_slope_pct_per_month, trend_r2 = _linear_trend(
        df["views"].to_numpy()
    )

    max_month_share_pct = (
        float(df["views"].max() / total_views * 100)
        if total_views
        else 0.0
    )

    if yoy_growth_pct is not None:
        if yoy_growth_pct > 5:
            growth_direction = "growing"
        elif yoy_growth_pct < -5:
            growth_direction = "declining"
        else:
            growth_direction = "roughly_flat"
    else:
        if trend_slope_pct_per_month > 0.3:
            growth_direction = "growing"
        elif trend_slope_pct_per_month < -0.3:
            growth_direction = "declining"
        else:
            growth_direction = "unclear"

    directional_ratio = None

    if len(recent_yoy):
        if growth_direction == "growing":
            directional_ratio = float(
                (recent_yoy > 0).mean()
            )

        elif growth_direction == "declining":
            directional_ratio = float(
                (recent_yoy < 0).mean()
            )

        else:
            directional_ratio = float(
                (recent_yoy.abs() <= 10).mean()
            )

    evidence_points = 0

    if number_of_months >= 24:
        evidence_points += 1

    if (
        directional_ratio is not None
        and directional_ratio >= 0.75
    ):
        evidence_points += 1

    if trend_r2 >= 0.35:
        evidence_points += 1

    if max_month_share_pct <= 15:
        evidence_points += 1

    if number_of_months < 12:
        evidence_strength = "weak"

    elif evidence_points >= 3:
        evidence_strength = "strong"

    elif evidence_points >= 2:
        evidence_strength = "moderate"

    else:
        evidence_strength = "weak"

    if number_of_months < 24:
        warnings.append(
            "Less than 24 months of observations are available; "
            "year-over-year conclusions are less robust."
        )

    if max_month_share_pct > 20:
        warnings.append(
            "A large share of all views comes from a single month; "
            "the result may be event-driven."
        )

    relative_interest = None

    if (
        "views_per_million" in df.columns
        and df["views_per_million"].notna().any()
    ):
        relative_interest = float(
            df["views_per_million"]
            .tail(12)
            .mean()
        )

    metrics = {
        "months": int(number_of_months),
        "total_views": total_views,
        "average_monthly_views": average_monthly_views,
        "current_12m_views": current_12m_views,
        "previous_12m_views": previous_12m_views,
        "yoy_growth_pct": (
            float(yoy_growth_pct)
            if yoy_growth_pct is not None
            else None
        ),
        "median_monthly_yoy_pct": median_monthly_yoy_pct,
        "directional_month_ratio": directional_ratio,
        "trend_slope_pct_per_month": trend_slope_pct_per_month,
        "trend_r2": trend_r2,
        "max_month_share_pct": max_month_share_pct,
        "relative_interest_views_per_million": relative_interest,
        "growth_direction": growth_direction,
        "evidence_strength": evidence_strength,
    }

    return df, metrics, warnings