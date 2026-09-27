import os
import pytest

from scripts.wikimedia_client import WikimediaClient


@pytest.mark.skipif(
    os.getenv(
        "RUN_NETWORK_TESTS"
    ) != "1",
    reason="Network test disabled",
)
def test_real_wikimedia_request():

    client = WikimediaClient(
        user_agent=(
            "WikipediaInterestSkill/0.1 "
            "educational-project"
        )
    )

    df = client.pageviews_per_article(
        project="en.wikipedia.org",
        article="Astronomy",
        start="2025-01-01",
        end="2025-03-31",
    )

    assert len(df) > 0
    assert "views" in df.columns
    assert df["views"].sum() > 0