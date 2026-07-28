import logging
from langgraph.graph import StateGraph, START, END

from backend.agents.graph.state import TutorSystemDesignState
from backend.agents.nodes.tutor_nodes.sysdesign_tutor_node import system_design_question_node
from backend.agents.nodes.tutor_nodes.system_design_hint_node import system_design_hints_node
from backend.agents.nodes.tutor_nodes.whiteboard_vision_node import whiteboard_vision_node
from backend.agents.nodes.tutor_nodes.design_validator_node import design_validator_node

logger = logging.getLogger("mockai-practice-graph")


def route_after_pause(state: TutorSystemDesignState) -> str:
    action = state.get("user_action")
    if action == "stop":
        return "stop"
    if action == "ask_question":
        return "ask_question"
    if action == "ask_concept":
        return "ask_concept"
    return "submit_image"


def build_tutor_graph(checkpointer):
    graph = StateGraph(TutorSystemDesignState)

    graph.add_node("system_design_question_node", system_design_question_node)
    graph.add_node("system_design_hints_node", system_design_hints_node)
    graph.add_node("whiteboard_vision_node", whiteboard_vision_node)
    graph.add_node("response_validator_node", design_validator_node)

    graph.add_edge(START, "system_design_question_node")
    graph.add_edge("system_design_question_node", "system_design_hints_node")

    route_map = {
        "submit_image": "whiteboard_vision_node",
        "ask_question": "response_validator_node",
        "ask_concept":"response_validator_node",
        "stop": END,
    }
    graph.add_conditional_edges("system_design_hints_node", route_after_pause, route_map)
    graph.add_conditional_edges("response_validator_node", route_after_pause, route_map)
    graph.add_edge("whiteboard_vision_node", "response_validator_node")

    return graph.compile(
        checkpointer=checkpointer,
        interrupt_after=["system_design_hints_node", "response_validator_node"],
    )