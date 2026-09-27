import numpy as np
import pandas as pd

from scripts.metrics import analyze_series


def make_dataframe(
    values: list[int],
) -> pd.DataFrame:

    return pd.DataFrame(
        {
            "date": pd.date_range(
                "2024-01-01",
                periods=len(values),
                freq="MS",
            ),
            "views": values,
        }
    )


def test_growing_series():

    first_year = [
        1000
    ] * 12

    second_year = [
        1300
    ] * 12

    df = make_dataframe(
        first_year + second_year
    )

    _, metrics, _ = analyze_series(
        df
    )

    assert round(
        metrics["yoy_growth_pct"],
        1,
    ) == 30.0

    assert (
        metrics["growth_direction"]
        == "growing"
    )


def test_flat_series():

    df = make_dataframe(
        [1000] * 24
    )

    _, metrics, _ = analyze_series(
        df
    )

    assert round(
        metrics["yoy_growth_pct"],
        1,
    ) == 0.0

    assert (
        metrics["growth_direction"]
        == "roughly_flat"
    )


def test_declining_series():

    df = make_dataframe(
        [1000] * 12
        + [700] * 12
    )

    _, metrics, _ = analyze_series(
        df
    )

    assert metrics[
        "yoy_growth_pct"
    ] < 0

    assert (
        metrics["growth_direction"]
        == "declining"
    )


def test_large_spike_produces_warning():

    values = [
        100
    ] * 23 + [
        5000
    ]

    df = make_dataframe(
        values
    )

    _, _, warnings = analyze_series(
        df
    )

    assert any(
        "single month" in warning
        for warning in warnings
    )


def test_relative_interest():

    df = make_dataframe(
        [1000] * 24
    )

    df["total_project_views"] = (
        np.array(
            [10_000_000] * 24
        )
    )

    processed, metrics, _ = analyze_series(
        df
    )

    assert (
        "views_per_million"
        in processed.columns
    )

    assert round(
        metrics[
            "relative_interest_views_per_million"
        ],
        1,
    ) == 100.0