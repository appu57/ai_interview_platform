import logging
from langgraph.graph import StateGraph, START, END


from backend.agents.graph.state import InterviewState
from backend.agents.nodes.interview_nodes.scrapper_node import company_scraper_node
from backend.agents.nodes.interview_nodes.planner_node import planner_agent_node
from backend.agents.nodes.interview_nodes.oa_node import oa_agent_node
from backend.agents.nodes.interview_nodes.technical_interviewer_node import technical_agent_node
from backend.agents.nodes.interview_nodes.system_design_node import system_design_agent_node
from backend.agents.nodes.interview_nodes.behavioural_node import behavioral_agent_node
from backend.agents.nodes.interview_nodes.evaluator_node import evaluator_agent_node
from backend.agents.nodes.interview_nodes.feedback_ledger_node import feedback_agent_node
from backend.agents.nodes.interview_nodes.guardrail_node import guardrail_check_node
from backend.agents.nodes.interview_nodes.memory_node import memory_sync_node
from backend.agents.nodes.interview_nodes.early_termination_node import early_termination_node
from backend.agents.nodes.interview_nodes.router_node import (
    route_after_guardrail,
    route_after_evaluator,
    dispatch_round_node_for_index,
)

logger = logging.getLogger("mockai-adaptive-graph")

ROUND_NODE_NAMES = [
    "oa_agent_node",
    "technical_agent_node",
    "system_design_agent_node",
    "behavioral_agent_node",
]


def build_interview_graph(checkpointer):
    """
    Compiles the interview graph with the given checkpointer.
    """
    graph = StateGraph(InterviewState)

    graph.add_node("company_scraper_node", company_scraper_node)
    graph.add_node("planner_agent_node", planner_agent_node)
    graph.add_node("oa_agent_node", oa_agent_node)
    graph.add_node("technical_agent_node", technical_agent_node)
    graph.add_node("system_design_agent_node", system_design_agent_node)
    graph.add_node("behavioral_agent_node", behavioral_agent_node)
    graph.add_node("guardrail_check_node", guardrail_check_node)
    graph.add_node("memory_sync_node", memory_sync_node)
    graph.add_node("early_termination_node", early_termination_node)
    graph.add_node("evaluator_agent_node", evaluator_agent_node)
    graph.add_node("feedback_agent_node", feedback_agent_node)

    graph.add_edge(START, "company_scraper_node")
    graph.add_edge("company_scraper_node", "planner_agent_node")

    graph.add_conditional_edges(
        "planner_agent_node",
        dispatch_round_node_for_index,
        {
            "oa_agent_node": "oa_agent_node",
            "technical_agent_node": "technical_agent_node",
            "system_design_agent_node": "system_design_agent_node",
            "behavioral_agent_node": "behavioral_agent_node",
            "feedback_agent_node": "feedback_agent_node",
        },
    )

    for node_name in ROUND_NODE_NAMES:
        graph.add_edge(node_name, "guardrail_check_node")

    graph.add_edge("guardrail_check_node", "memory_sync_node")

    route_targets = {n: n for n in ROUND_NODE_NAMES}
    route_targets["evaluator_agent_node"] = "evaluator_agent_node"
    route_targets["early_termination_node"] = "early_termination_node"
    graph.add_conditional_edges("memory_sync_node", route_after_guardrail, route_targets)

    graph.add_edge("early_termination_node", "feedback_agent_node")

    evaluator_route_targets = {n: n for n in ROUND_NODE_NAMES}
    evaluator_route_targets["planner_agent_node"] = "planner_agent_node"
    evaluator_route_targets["feedback_agent_node"] = "feedback_agent_node"
    graph.add_conditional_edges(
        "evaluator_agent_node",
        route_after_evaluator,
        evaluator_route_targets,
    )

    graph.add_edge("feedback_agent_node", END)

    return graph.compile(
        checkpointer=checkpointer,
        interrupt_after=ROUND_NODE_NAMES,
    )
