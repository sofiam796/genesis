from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import pandas as pd

from .metrics import analyze_series
from .report import create_chart, create_pdf
from .resolve_topic import resolve_topic
from .wikimedia_client import WikimediaClient


DEFAULT_LIMITATIONS = [
    (
        "Wikipedia pageviews measure article viewing activity, "
        "not unique people or market demand."
    ),
    (
        "News events, seasonality and temporary attention spikes "
        "can influence the observed trend."
    ),
    (
        "Comparisons between language editions should account "
        "for differences in the overall size of each Wikipedia."
    ),
]


def parse_article_overrides(
    values: list[str] | None,
) -> dict[str, str]:

    result = {}

    for value in values or []:

        if "=" not in value:
            raise ValueError(
                "--article must use LANGUAGE=ARTICLE format"
            )

        language, article = value.split(
            "=",
            1,
        )

        result[language.strip()] = article.strip()

    return result


def load_json(path: str | Path) -> dict:
    return json.loads(
        Path(path).read_text(
            encoding="utf-8"
        )
    )


def save_json(
    path: str | Path,
    data: dict,
) -> None:

    Path(path).write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def build_findings(
    entities: list[dict],
) -> list[str]:

    findings = []

    for entity in entities:

        metrics = entity["metrics"]

        yoy = metrics["yoy_growth_pct"]

        if yoy is not None:
            findings.append(
                (
                    f'{entity["language"]}: '
                    f'12-month pageviews changed '
                    f'{yoy:+.1f}% year over year; '
                    f'evidence is '
                    f'{metrics["evidence_strength"]}.'
                )
            )

        else:
            findings.append(
                (
                    f'{entity["language"]}: '
                    f'the series is classified as '
                    f'{metrics["growth_direction"]}; '
                    f'evidence is '
                    f'{metrics["evidence_strength"]}.'
                )
            )

    return findings


def main() -> None:

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--config",
    )

    parser.add_argument(
        "--topic",
    )

    parser.add_argument(
        "--topic-language",
    )

    parser.add_argument(
        "--languages",
        nargs="+",
    )

    parser.add_argument(
        "--start",
    )

    parser.add_argument(
        "--end",
    )

    parser.add_argument(
        "--output",
    )

    parser.add_argument(
        "--qid",
    )

    parser.add_argument(
        "--article",
        action="append",
    )

    parser.add_argument(
        "--exclude-month",
        action="append",
    )

    args = parser.parse_args()

    config = {}

    if args.config:
        config = load_json(args.config)

    topic = (
        args.topic
        or config.get("topic")
    )

    topic_language = (
        args.topic_language
        or config.get("topic_language")
        or "en"
    )

    languages = (
        args.languages
        or config.get("languages")
    )

    start = (
        args.start
        or config.get("start")
    )

    end = (
        args.end
        or config.get("end")
    )

    output = (
        args.output
        or config.get("output")
        or "output"
    )

    qid = (
        args.qid
        or config.get("qid")
    )

    if not topic:
        raise ValueError(
            "Topic is required."
        )

    if not languages:
        raise ValueError(
            "At least one language is required."
        )

    if not start or not end:
        raise ValueError(
            "Start and end dates are required."
        )

    article_overrides = dict(
        config.get("articles", {})
    )

    article_overrides.update(
        parse_article_overrides(
            args.article
        )
    )

    exclude_months = set(
        config.get(
            "exclude_months",
            [],
        )
    )

    exclude_months.update(
        args.exclude_month or []
    )

    output_dir = Path(output)

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    resolution = resolve_topic(
        topic=topic,
        languages=languages,
        topic_language=topic_language,
        qid=qid,
        overrides=article_overrides,
    )

    user_agent = os.getenv(
        "WIKIPEDIA_SKILL_USER_AGENT",
        "WikipediaInterestSkill/0.1 educational-project",
    )

    client = WikimediaClient(
        user_agent=user_agent,
        cache_dir=output_dir / ".cache",
    )

    processed_series = {}

    all_frames = []

    entities = []

    global_warnings = list(
        resolution["warnings"]
    )

    for language in languages:

        article = resolution[
            "resolved_pages"
        ][language]

        project = (
            f"{language}.wikipedia.org"
        )

        pageviews = client.pageviews_per_article(
            project=project,
            article=article,
            start=start,
            end=end,
        )

        try:
            aggregate = client.aggregate_pageviews(
                project=project,
                start=start,
                end=end,
            )

            data = pageviews.merge(
                aggregate,
                on="date",
                how="left",
            )

        except Exception as error:

            data = pageviews

            global_warnings.append(
                (
                    f"{language}: total Wikipedia traffic "
                    f"could not be retrieved: {error}"
                )
            )

        if exclude_months:

            month_strings = (
                data["date"]
                .dt.strftime("%Y-%m")
            )

            data = data[
                ~month_strings.isin(
                    exclude_months
                )
            ].copy()

        processed, metrics, warnings = analyze_series(
            data
        )

        processed["language"] = language
        processed["article"] = article

        processed_series[
            language
        ] = processed

        all_frames.append(
            processed
        )

        entities.append(
            {
                "language": language,
                "project": project,
                "article": article,
                "metrics": metrics,
                "warnings": warnings,
            }
        )

        global_warnings.extend(
            f"{language}: {warning}"
            for warning in warnings
        )

    combined = pd.concat(
        all_frames,
        ignore_index=True,
    )

    combined.to_csv(
        output_dir / "data.csv",
        index=False,
    )

    saved_config = {
        "topic": topic,
        "topic_language": topic_language,
        "languages": languages,
        "start": start,
        "end": end,
        "output": output,
        "qid": resolution["qid"],
        "articles": resolution[
            "resolved_pages"
        ],
        "exclude_months": sorted(
            exclude_months
        ),
    }

    save_json(
        output_dir / "analysis_config.json",
        saved_config,
    )

    analysis = {
        "topic": topic,
        "period": {
            "start": start,
            "end": end,
        },
        "resolution": resolution,
        "entities": entities,
        "excluded_months": sorted(
            exclude_months
        ),
        "summary_findings": build_findings(
            entities
        ),
        "warnings": sorted(
            set(global_warnings)
        ),
        "limitations": DEFAULT_LIMITATIONS,
    }

    chart_path = (
        output_dir / "chart.png"
    )

    create_chart(
        series=processed_series,
        topic=topic,
        output_path=chart_path,
    )

    pdf_path = (
        output_dir / "report.pdf"
    )

    create_pdf(
        analysis=analysis,
        chart_path=chart_path,
        output_path=pdf_path,
    )

    analysis["outputs"] = {
        "data": str(
            output_dir / "data.csv"
        ),
        "chart": str(chart_path),
        "pdf": str(pdf_path),
        "config": str(
            output_dir
            / "analysis_config.json"
        ),
    }

    save_json(
        output_dir / "analysis.json",
        analysis,
    )

    print(
        json.dumps(
            analysis,
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()