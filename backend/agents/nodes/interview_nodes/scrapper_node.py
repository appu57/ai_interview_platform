# backend/agents/graph/nodes/company_scraper_node.py
import logging
from typing import Dict, Any

from backend.agents.graph.state import InterviewState
from backend.agents.tools.company_rounds import scrape_company_interview_data

logger = logging.getLogger("mockai-adaptive-graph")


async def company_scraper_node(state: InterviewState) -> Dict[str, Any]:
    target_company = state.get("target_company")
    job_title = state["job_title"]

    if not target_company:
        logger.info("[Scraper] No target_company set — skipping Tavily, using generic defaults.")
        return {
            "target_company_data": {
                "rounds_observed": [], "common_topics": [], "sample_questions": [],
                "culture_notes": "No specific target company — generic best-practice structure.",
                "sources": [], "research_confidence": "low",
            }
        }

    try:
        company_data = await scrape_company_interview_data(target_company, job_title)
        logger.info(f"[Scraper] Research complete for '{target_company}'.")
    except Exception as e:
        logger.error(f"[Scraper Error] Unexpected failure for '{target_company}': {e}")
        company_data = {
            "rounds_observed": [], "common_topics": [], "sample_questions": [],
            "culture_notes": f"Research failed for {target_company} — generic defaults.",
            "sources": [], "research_confidence": "low",
        }

    return {"target_company_data": company_data}