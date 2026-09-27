from __future__ import annotations

from pathlib import Path

import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import pandas as pd
import textwrap


def create_chart(
    series: dict[str, pd.DataFrame],
    topic: str,
    output_path: str | Path,
) -> None:

    fig, ax = plt.subplots(figsize=(10, 5))

    if len(series) == 1:

        language, df = next(iter(series.items()))

        ax.plot(
            df["date"],
            df["views"],
            label="Monthly views",
        )

        ax.plot(
            df["date"],
            df["rolling_3m"],
            label="3-month rolling average",
        )

        ax.set_ylabel("Pageviews")

    else:

        for language, df in series.items():
            ax.plot(
                df["date"],
                df["index_100"],
                label=language,
            )

        ax.axhline(
            100,
            linewidth=1,
            linestyle="--",
        )

        ax.set_ylabel("Indexed interest, first month = 100")

    ax.set_title(
        f"Wikipedia interest: {topic}"
    )

    ax.set_xlabel("Date")

    ax.legend()

    ax.grid(
        True,
        alpha=0.25,
    )

    fig.tight_layout()

    fig.savefig(
        output_path,
        dpi=160,
        bbox_inches="tight",
    )

    plt.close(fig)


def _format_number(value) -> str:
    if value is None:
        return "n/a"

    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"

    if abs(value) >= 1_000:
        return f"{value / 1_000:.1f}k"

    return f"{value:.0f}"


def create_pdf(
    analysis: dict,
    chart_path: str | Path,
    output_path: str | Path,
) -> None:

    fig = plt.figure(
        figsize=(8.27, 11.69)
    )

    fig.text(
        0.06,
        0.955,
        "Wikipedia Interest Report",
        fontsize=20,
        weight="bold",
    )

    fig.text(
        0.06,
        0.925,
        analysis["topic"],
        fontsize=13,
    )

    fig.text(
        0.06,
        0.902,
        (
            f'{analysis["period"]["start"]} — '
            f'{analysis["period"]["end"]}'
        ),
        fontsize=9,
    )

    image = mpimg.imread(chart_path)

    chart_ax = fig.add_axes(
        [0.07, 0.56, 0.86, 0.30]
    )

    chart_ax.imshow(image)
    chart_ax.axis("off")

    table_ax = fig.add_axes(
        [0.05, 0.345, 0.90, 0.19]
    )

    table_ax.axis("off")

    rows = []

    translations = (
        analysis
        .get("agent_resolution", {})
        .get("article_titles_uk", {})
    )

    for entity in analysis["entities"][:6]:
        metrics = entity["metrics"]

        yoy = metrics["yoy_growth_pct"]

        yoy_text = (
            f"{yoy:+.1f}%"
            if yoy is not None
            else "n/a"
        )

        article_translation = translations.get(
            entity["language"],
            "",
        )

        # Оригинальное название + украинский перевод на новой строке
        article_label = entity["article"]

        if article_translation:
            article_label = (
                f"{article_label}\n"
                f"{article_translation}"
            )

        rows.append(
            [
                entity["language"].upper(),
                article_label,
                _format_number(
                    metrics["current_12m_views"]
                ),
                yoy_text,
                metrics["growth_direction"],
                metrics["evidence_strength"],
            ]
        )

    table = table_ax.table(
        cellText=rows,
        colLabels=[
            "Wiki",
            "Article",
            "12m views",
            "YoY",
            "Trend",
            "Evidence",
        ],
        colWidths=[
            0.07,   # Wiki
            0.38,   # Article
            0.13,   # 12m views
            0.10,   # YoY
            0.16,   # Trend
            0.16,   # Evidence
        ],
        cellLoc="center",
        loc="center",
    )

    table.auto_set_font_size(False)
    table.set_fontsize(7.3)

    # Делаем строки выше, чтобы помещались две строки названия
    table.scale(1, 1.8)

    # Оформление отдельных ячеек
    for (row, col), cell in table.get_celld().items():

        # Header
        if row == 0:
            cell.set_text_props(
                weight="bold",
                fontsize=7.5,
            )

        # Article column
        if col == 1 and row > 0:
            cell.get_text().set_ha("left")
            cell.get_text().set_va("center")
            cell.PAD = 0.04

    fig.text(
        0.06,
        0.31,
        "Analysis",
        fontsize=11,
        weight="bold",
    )

    summary = analysis.get(
        "llm_summary",
        "",
    )

    # Если LLM summary ещё нет, используем обычные findings
    if not summary:
        summary = " ".join(
            analysis.get(
                "summary_findings",
                [],
            )
        )

    # Убираем простую Markdown-разметку
    summary = (
        summary
        .replace("**", "")
        .replace("##", "")
        .replace("###", "")
    )

    wrapped_summary = textwrap.fill(
        summary,
        width=105,
    )

    fig.text(
        0.06,
        0.285,
        wrapped_summary,
        fontsize=8.2,
        va="top",
        wrap=True,
    )

    fig.text(
        0.06,
        0.11,
        "Limitations",
        fontsize=11,
        weight="bold",
    )

    limitations = analysis.get(
        "limitations",
        [],
    )[:3]

    y = 0.085

    for limitation in limitations:
        fig.text(
            0.075,
            y,
            f"• {limitation}",
            fontsize=7.5,
            wrap=True,
        )
        y -= 0.022

    fig.text(
        0.06,
        0.035,
        "Source: Wikimedia Analytics API",
        fontsize=7,
    )

    fig.savefig(
        output_path,
        format="pdf",
        bbox_inches="tight",
    )

    plt.close(fig)