import json
import os
import subprocess
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv
from datetime import date
from scripts.resolve_topic import (
    search_wikidata,
    get_sitelinks,
    search_local_wikipedia,
)

load_dotenv()

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"],
)


def parse_json_object(text: str | None) -> dict:
    if not text:
        return {}

    text = text.strip()

    if not text:
        return {}

    if text.startswith("```"):
        lines = text.splitlines()

        if lines:
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        text = "\n".join(lines).strip()

    try:
        decoder = json.JSONDecoder()
        obj, _ = decoder.raw_decode(text)

        if isinstance(obj, dict):
            return obj

    except json.JSONDecodeError:
        pass

    return {}


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "analyze_wikipedia_interest",
            "description": (
                "Analyze Wikipedia pageview interest for a topic "
                "across one or more language editions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": (
                            "Canonical English name of the topic to analyze. "
                            "Translate the user's topic to English before calling "
                            "this tool. Example: 'інтервальне голодування' -> "
                            "'intermittent fasting'."
                        ),
                    },
                    "languages": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "description": (
                            "Wikipedia language editions to analyze"
                        ),
                    },
                    "start": {
                        "type": "string",
                        "description": "Start date YYYY-MM-DD",
                    },
                    "end": {
                        "type": "string",
                        "description": "End date YYYY-MM-DD",
                    },
                },
                "required": [
                    "topic",
                    "languages",
                    "start",
                    "end",
                ],
            },
        },
    }
]


def choose_wikidata_candidate(
    topic: str,
    candidates: list[dict],
) -> str:

    simplified = [
        {
            "id": candidate.get("id"),
            "label": candidate.get("label"),
            "description": candidate.get("description"),
        }
        for candidate in candidates
    ]

    response = client.chat.completions.create(
        model="anthropic/claude-haiku-4.5",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are resolving a topic to a Wikidata entity. "
                    "Choose ONLY one of the provided candidates. "
                    "The entity must represent the same concept as the topic. "
                    "Do not invent a QID. "
                    "If none match, return {\"qid\": null}."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "topic": topic,
                        "candidates": simplified,
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        response_format={
            "type": "json_object",
        },
    )

    result = parse_json_object(
        response.choices[0].message.content
    )

    selected_qid = result.get("qid")

    valid_qids = {
        candidate["id"]
        for candidate in simplified
    }

    if selected_qid not in valid_qids:
        raise ValueError(
            f"LLM could not safely resolve topic: {topic}"
        )

    return selected_qid

def choose_local_article(
    topic: str,
    language: str,
    candidates: list[dict],
    wikidata_description: str | None = None,
) -> str:

    if not candidates:
        raise ValueError(
            f"No Wikipedia candidates found for language: {language}"
        )

    response = client.chat.completions.create(
        model="anthropic/claude-haiku-4.5",
        messages=[
            {
                "role": "system",
                "content": (
                    "Choose the Wikipedia article that best matches the requested topic. "
                    "Prefer an exact semantic equivalent. "
                    "If no exact equivalent exists, choose the closest relevant article. "
                    "Choose ONLY from the provided candidates. "
                    "Do not invent article titles."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "topic": topic,
                        "wikidata_description": wikidata_description,
                        "language": language,
                        "candidates": candidates,
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        response_format={
            "type": "json_object",
        },
    )

    result = parse_json_object(
        response.choices[0].message.content
    )

    selected_title = result.get("title")

    valid_titles = {
        candidate["title"]
        for candidate in candidates
    }

    if selected_title in valid_titles:
        return selected_title

    fallback_title = candidates[0]["title"]

    return fallback_title

def translate_article_titles_to_uk(
    articles: dict[str, str],
) -> dict[str, str]:

    response = client.chat.completions.create(
        model="anthropic/claude-haiku-4.5",
        messages=[
            {
                "role": "system",
                "content": (
                    "Translate Wikipedia article titles into Ukrainian. "
                    "Preserve the exact meaning. "
                    "Return only a JSON object where keys are language codes "
                    "and values are Ukrainian translations."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    articles,
                    ensure_ascii=False,
                ),
            },
        ],
        response_format={
            "type": "json_object",
        },
    )

    translated = parse_json_object(
        response.choices[0].message.content
    )

    return translated

def analyze_wikipedia_interest(
    topic,
    languages,
    start,
    end,
):
    output_dir = "agent-output"

    # 1. Получаем реальные Wikidata candidates
    wikidata_candidates = search_wikidata(
        topic=topic,
        language="en",
        limit=5,
    )

    if not wikidata_candidates:
        return {
            "status": "error",
            "error": (
                f"No Wikidata candidates found for topic: {topic}"
            ),
        }

    # 2. LLM выбирает только из этих candidates
    selected_qid = choose_wikidata_candidate(
        topic=topic,
        candidates=wikidata_candidates,
    )

    selected_candidate = next(
        candidate
        for candidate in wikidata_candidates
        if candidate["id"] == selected_qid
    )

    wikidata_description = selected_candidate.get(
        "description"
    )

    # 3. Получаем Wikipedia sitelinks из Wikidata
    sitelinks = get_sitelinks(
        qid=selected_qid,
        languages=languages,
    )

    articles = dict(sitelinks)

    for language in languages:
        if language in articles:
            continue

        local_candidates = search_local_wikipedia(
            topic=topic,
            language=language,
            limit=5,
        )

        selected_article = choose_local_article(
            topic=topic,
            language=language,
            candidates=local_candidates,
            wikidata_description=wikidata_description,
        )

        articles[language] = selected_article

    article_titles_uk = translate_article_titles_to_uk(
        articles
    )


    # 6. Теперь run_analysis получает уже выбранный QID
    # и проверенные article mappings
    command = [
        "python",
        "-m",
        "scripts.run_analysis",
        "--topic",
        topic,
        "--topic-language",
        "en",
        "--languages",
        *languages,
        "--start",
        start,
        "--end",
        end,
        "--output",
        output_dir,
        "--qid",
        selected_qid,
    ]

    # Передаём явные article mappings
    for language, article in articles.items():
        command.extend(
            [
                "--article",
                f"{language}={article}",
            ]
        )

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return {
            "status": "error",
            "error": result.stderr,
        }

    analysis_path = (
        Path(output_dir)
        / "analysis.json"
    )

    analysis = json.loads(
        analysis_path.read_text(
            encoding="utf-8"
        )
    )

    # Добавляем информацию о выборе LLM
    analysis["agent_resolution"] = {
        "qid": selected_qid,
        "articles": articles,
        "article_titles_uk": article_titles_uk,
    }

    analysis_path.write_text(
        json.dumps(
            analysis,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return analysis


def run_agent(user_question):
    today = date.today().isoformat()
    skill_text = Path(
        "SKILL.md"
    ).read_text(
        encoding="utf-8"
    )

    messages = [
        {
            "role": "system",
            "content": (
                f"You are a Wikipedia interest research agent.\n"
                f"Today's date is {today}.\n\n"
                "When calling analyze_wikipedia_interest:\n"
                "- translate the topic to its canonical English name;\n"
                "- use ISO dates YYYY-MM-DD;\n"
                "- for relative periods such as 'last two years', "
                "interpret them relative to today's date;\n"
                "- because analysis uses monthly data, prefer complete "
                "months and avoid the current incomplete month.\n\n"
                "Follow this skill:\n\n"
                + skill_text
            ),
        },
        {
            "role": "user",
            "content": user_question,
        },
    ]

    response = client.chat.completions.create(
        model="anthropic/claude-haiku-4.5",
        messages=messages,
        tools=TOOLS,
        tool_choice="auto",
    )

    message = response.choices[0].message

    messages.append(message)

    if not message.tool_calls:
        return message.content

    for tool_call in message.tool_calls:
        arguments = json.loads(
            tool_call.function.arguments
        )

        if tool_call.function.name == (
            "analyze_wikipedia_interest"
        ):
            result = analyze_wikipedia_interest(
                **arguments
            )
        else:
            raise ValueError(
                "Unknown tool"
            )

        messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(
                    result,
                    ensure_ascii=False,
                ),
            }
        )

    messages.append(
        {
            "role": "system",
            "content": (
                "Write the final report summary for a one-page PDF. "
                "Use 80-120 words total. "
                "Use plain text only, without Markdown headings, bullets, tables, or bold formatting. "
                "Include: "
                "1) the main trend, "
                "2) the key comparison between languages, "
                "3) the most important supporting metrics, "
                "4) one important limitation or warning. "
                "Do not repeat every metric. "
                "Do not make claims that are not supported by the analysis. "
                "If topic resolution contains a warning or suspicious article mapping, mention it clearly."
            ),
        }
    )

    final_response = client.chat.completions.create(
        model="anthropic/claude-haiku-4.5",
        messages=messages,
        tools=TOOLS,
    )

    final_text = (
        final_response
        .choices[0]
        .message
        .content
    )

    analysis_path = Path("agent-output/analysis.json")

    analysis = json.loads(
        analysis_path.read_text(
            encoding="utf-8"
        )
    )

    analysis["llm_summary"] = final_text

    analysis_path.write_text(
        json.dumps(
            analysis,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    from scripts.report import create_pdf

    create_pdf(
        analysis=analysis,
        chart_path="agent-output/chart.png",
        output_path="agent-output/report.pdf",
    )

    return final_text


if __name__ == "__main__":
    question = input(
        "Question: "
    )

    answer = run_agent(
        question
    )

    print("\nAnswer:\n")
    print(answer)