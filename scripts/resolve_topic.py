from __future__ import annotations

import os

import requests


WIKIDATA_API = "https://www.wikidata.org/w/api.php"

USER_AGENT = os.getenv(
    "WIKIPEDIA_SKILL_USER_AGENT",
    "WikipediaInterestSkill/0.1 educational-project",
)


def _session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
        }
    )
    return session


def search_wikidata(
    topic: str,
    language: str = "en",
    limit: int = 5,
) -> list[dict]:

    params = {
        "action": "wbsearchentities",
        "search": topic,
        "language": language,
        "format": "json",
        "limit": limit,
    }

    response = _session().get(
        WIKIDATA_API,
        params=params,
        timeout=30,
    )
    response.raise_for_status()

    return response.json().get("search", [])


def get_sitelinks(
    qid: str,
    languages: list[str],
) -> dict[str, str]:

    params = {
        "action": "wbgetentities",
        "ids": qid,
        "props": "sitelinks",
        "format": "json",
    }

    response = _session().get(
        WIKIDATA_API,
        params=params,
        timeout=30,
    )
    response.raise_for_status()

    entity = response.json()["entities"][qid]

    sitelinks = entity.get("sitelinks", {})

    result = {}

    for language in languages:
        key = f"{language}wiki"

        if key in sitelinks:
            result[language] = sitelinks[key]["title"]

    return result


def search_local_wikipedia(
    topic: str,
    language: str,
    limit: int = 5,
) -> list[dict]:

    api_url = f"https://{language}.wikipedia.org/w/api.php"

    params = {
        "action": "query",
        "list": "search",
        "srsearch": topic,
        "format": "json",
        "utf8": 1,
        "srlimit": limit,
    }

    response = _session().get(
        api_url,
        params=params,
        timeout=30,
    )
    response.raise_for_status()

    results = (
        response.json()
        .get("query", {})
        .get("search", [])
    )

    return [
        {
            "title": item["title"],
            "snippet": item.get("snippet", ""),
        }
        for item in results
    ]


def resolve_topic(
    topic: str,
    languages: list[str],
    topic_language: str = "en",
    qid: str | None = None,
    overrides: dict[str, str] | None = None,
) -> dict:

    overrides = overrides or {}

    resolved = {
        language: overrides[language]
        for language in languages
        if language in overrides
    }

    warnings = []
    candidates = []

    selected_qid = qid

    # Если агент уже выбрал QID — используем его.
    # Если нет — только получаем кандидатов, но не выбираем первый вслепую.
    if not selected_qid:
        candidates = search_wikidata(
            topic=topic,
            language=topic_language,
        )

        if not candidates:
            raise ValueError(
                f"No Wikidata candidates found for topic: {topic}"
            )

        raise ValueError(
            "Topic requires Wikidata candidate selection. "
            "Provide --qid after choosing a candidate."
        )

    # Получаем реальные Wikipedia sitelinks выбранной сущности
    sitelinks = get_sitelinks(
        selected_qid,
        languages,
    )

    for language, article in sitelinks.items():
        resolved.setdefault(
            language,
            article,
        )

    # НИКОГДА больше не берём первый local search result автоматически
    missing = [
        language
        for language in languages
        if language not in resolved
    ]

    if missing:
        raise ValueError(
            "Missing Wikipedia article mapping for: "
            + ", ".join(missing)
            + ". Provide explicit --article overrides."
        )

    return {
        "topic": topic,
        "qid": selected_qid,
        "resolved_pages": resolved,
        "wikidata_candidates": [],
        "warnings": warnings,
    }