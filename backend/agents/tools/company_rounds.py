import asyncio
import json
import logging
from typing import Dict, Any, List
from tavily import TavilyClient
from groq import AsyncGroq

from backend.core.security import get_settings

settings = get_settings()
tavily_client = TavilyClient(api_key=settings.tavily_api_key)
groq_client = AsyncGroq(api_key=settings.groq_api_key)
logger = logging.getLogger("mockai-adaptive-graph")

SEARCH_QUERY_TEMPLATES = [
    "{company} {job_title} interview process rounds",
    "{company} {job_title} interview questions experience",
    "{company} software engineer interview leetcode questions",
]


def _run_tavily_search(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    try:
        response = tavily_client.search(
            query=query,
            search_depth="advanced",
            max_results=max_results,
            include_answer=False,
            include_raw_content=False,
        )
        return response.get("results", [])
    except Exception as e:
        logger.error(f"[Tavily] Search failed for query '{query}': {e}")
        return []


def _format_raw_results(all_results: List[Dict[str, Any]]) -> str:
    blocks = []
    for r in all_results:
        title = r.get("title", "untitled")
        url = r.get("url", "")
        content = (r.get("content") or "")[:1500]  # cap per-result so synth prompt stays bounded
        blocks.append(f"SOURCE: {title} ({url})\n{content}")
    return "\n\n---\n\n".join(blocks) if blocks else "(no search results found)"


async def scrape_company_interview_data(company: str, job_title: str) -> Dict[str, Any]:
    queries = [t.format(company=company, job_title=job_title) for t in SEARCH_QUERY_TEMPLATES]
    results_per_query = await asyncio.gather(
        *(asyncio.to_thread(_run_tavily_search, q) for q in queries)
    )
    all_results: List[Dict[str, Any]] = [r for batch in results_per_query for r in batch]

    if not all_results:
        logger.warning(f"[Tavily] No results for company='{company}'.")
        return {
            "rounds_observed": [], "common_topics": [], "sample_questions": [],
            "culture_notes": "No data found — use generic best-practice assumptions.",
            "sources": [], "research_confidence": "low",
        }

    raw_block = _format_raw_results(all_results)
    sources = list({r.get("url") for r in all_results if r.get("url")})

    system_prompt = (
        "You are a Research Synthesis Agent for Mock.ai. You receive raw, noisy web-search "
        "snippets about a company's interview process and extract a structured summary.\n\n"
        "--- CRITICAL RULES ---\n"
        "1. NEVER reproduce verbatim question text from sources. Extract the TOPIC/PATTERN behind "
        "each mentioned question (e.g. 'graph traversal — shortest path variant', not the literal wording).\n"
        "2. Prefer patterns that recur across multiple sources over single-source claims.\n"
        "3. If snippets don't actually describe interview content, say so honestly — never invent rounds.\n\n"
        "--- OUTPUT CONTRACT ---\n"
        "Respond with STRICT JSON only, no markdown fences:\n"
        "{\n"
        '  "rounds_observed": [string],\n'
        '  "common_topics": [string],\n'
        '  "sample_questions": [string],\n'
        '  "culture_notes": string,\n'
        '  "research_confidence": "low" | "medium" | "high"\n'
        "}"
    )
    user_prompt = f"""
    Company: {company}
    Target Role: {job_title}

    === RAW SEARCH RESULTS ===
    {raw_block}

    Synthesize the structured summary now.
    """

    try:
        completion = await groq_client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            temperature=0.2,
            max_tokens=1024,
            response_format={"type": "json_object"},
        )
        result = json.loads(completion.choices[0].message.content)
        logger.info(f"[Tavily+Synth] '{company}' synthesized, confidence={result.get('research_confidence')}.")
    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"[Tavily+Synth] Synthesis failed: {e}")
        result = None

    result["sources"] = sources
    return result