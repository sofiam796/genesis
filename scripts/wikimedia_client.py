from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import requests


BASE_URL = "https://wikimedia.org/api/rest_v1"


def _api_timestamp(value: str) -> str:
    """
    Convert values such as:
        2025-01-01
        2025-01
    to Wikimedia timestamp:
        2025010100
    """
    timestamp = pd.Timestamp(value)

    return timestamp.strftime("%Y%m%d00")


class WikimediaClient:
    def __init__(
        self,
        user_agent: str,
        cache_dir: str | Path | None = None,
        timeout: int = 30,
    ):
        self.timeout = timeout

        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": user_agent,
                "Accept": "application/json",
            }
        )

        self.cache_dir = Path(cache_dir) if cache_dir else None

        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_json(self, url: str) -> dict:
        cache_path = None

        if self.cache_dir:
            key = hashlib.sha256(url.encode("utf-8")).hexdigest()
            cache_path = self.cache_dir / f"{key}.json"

            if cache_path.exists():
                return json.loads(cache_path.read_text(encoding="utf-8"))

        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()

        data = response.json()

        if cache_path:
            cache_path.write_text(
                json.dumps(data, ensure_ascii=False),
                encoding="utf-8",
            )

        return data

    def pageviews_per_article(
        self,
        project: str,
        article: str,
        start: str,
        end: str,
        access: str = "all-access",
        agent: str = "user",
        granularity: str = "monthly",
    ) -> pd.DataFrame:

        article_encoded = quote(
            article.replace(" ", "_"),
            safe="",
        )

        url = (
            f"{BASE_URL}/metrics/pageviews/per-article/"
            f"{project}/"
            f"{access}/"
            f"{agent}/"
            f"{article_encoded}/"
            f"{granularity}/"
            f"{_api_timestamp(start)}/"
            f"{_api_timestamp(end)}"
        )

        data = self._get_json(url)

        items = data.get("items", [])

        if not items:
            raise ValueError(
                f"No pageview data returned for {project}: {article}"
            )

        rows = []

        for item in items:
            rows.append(
                {
                    "date": pd.to_datetime(
                        item["timestamp"][:8],
                        format="%Y%m%d",
                    ),
                    "views": int(item["views"]),
                }
            )

        return pd.DataFrame(rows)

    def aggregate_pageviews(
        self,
        project: str,
        start: str,
        end: str,
        access: str = "all-access",
        agent: str = "user",
        granularity: str = "monthly",
    ) -> pd.DataFrame:

        url = (
            f"{BASE_URL}/metrics/pageviews/aggregate/"
            f"{project}/"
            f"{access}/"
            f"{agent}/"
            f"{granularity}/"
            f"{_api_timestamp(start)}/"
            f"{_api_timestamp(end)}"
        )

        data = self._get_json(url)

        rows = []

        for item in data.get("items", []):
            rows.append(
                {
                    "date": pd.to_datetime(
                        item["timestamp"][:8],
                        format="%Y%m%d",
                    ),
                    "total_project_views": int(item["views"]),
                }
            )

        return pd.DataFrame(rows)