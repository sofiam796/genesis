---
name: genesis
description: Analyze Wikipedia pageview trends across topics, languages, and time periods. Use for comparing topic interest, measuring growth, evaluating trend reliability, generating charts, or producing short Wikipedia interest reports.
---

# Wikipedia Interest Analysis

Use this skill when the user asks about Wikipedia interest, topic popularity, trend growth, or comparisons between language editions.

## Workflow

1. Identify:
   - topic
   - languages
   - period
   - comparison objective

2. Run `scripts/run_analysis.py` with the required parameters.

3. Read `output/analysis.json`.

4. Base conclusions on calculated metrics from the analysis.

5. Check warnings and topic resolution before presenting conclusions.

6. Clearly distinguish:
   - observations from the data
   - interpretations
   - limitations

7. Never claim that Wikipedia pageviews directly represent market demand or the number of unique people interested in a topic.

## Topic resolution

The agent resolves each topic using Wikidata and Wikipedia search candidates.

The language model may select among candidates returned by the APIs, but it must never invent a Wikidata QID or Wikipedia article.

If no candidate clearly represents the requested concept, do not continue the analysis with a related article.

Always inspect the resolved articles before presenting conclusions.

## Interpretation

Use the metrics produced by the script, including:
- pageviews
- year-over-year growth
- trend direction
- trend consistency
- relative interest across Wikipedia editions
- evidence strength

Treat `evidence_strength` as a descriptive assessment of how consistently the available data supports the observed trend, not as statistical significance.

When comparing language editions, do not rely only on absolute pageviews because Wikipedia editions differ greatly in total traffic.

## Follow-up requests

When the user changes:
- time range
- language
- topic mapping
- excluded outliers
- comparison criteria

reuse the previous configuration from `output/analysis_config.json` and rerun the analysis instead of rebuilding the request from scratch.

## Output

Return:
- concise findings
- relevant supporting metrics
- important warnings or limitations
- chart when useful
- PDF when a shareable report is requested

Prefer `analysis.json` over manually interpreting raw monthly data.