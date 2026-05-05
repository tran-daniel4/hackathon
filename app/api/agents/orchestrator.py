from typing import TypedDict
from langgraph.graph import StateGraph, END

from agents.repo_analyzer import analyze_repo
from agents.system_designer import design_system
from agents.bottleneck_detector import detect_bottlenecks
from agents.diagram_generator import generate_diagram


class PipelineState(TypedDict):
    # Inputs
    file_tree: str
    file_contents: str
    # Agent outputs
    repo_analysis: dict
    system_design: dict
    bottlenecks: dict
    diagram: dict


def _run_repo_analyzer(state: PipelineState) -> PipelineState:
    state["repo_analysis"] = analyze_repo(state["file_tree"], state["file_contents"])
    return state


def _run_system_designer(state: PipelineState) -> PipelineState:
    state["system_design"] = design_system(state["repo_analysis"])
    return state


def _run_bottleneck_detector(state: PipelineState) -> PipelineState:
    state["bottlenecks"] = detect_bottlenecks(state["system_design"])
    return state


def _run_diagram_generator(state: PipelineState) -> PipelineState:
    state["diagram"] = generate_diagram(state["system_design"], state["bottlenecks"])
    return state


def _build_graph() -> StateGraph:
    graph = StateGraph(PipelineState)

    graph.add_node("analyze", _run_repo_analyzer)
    graph.add_node("design", _run_system_designer)
    graph.add_node("bottleneck", _run_bottleneck_detector)
    graph.add_node("diagram", _run_diagram_generator)

    graph.set_entry_point("analyze")
    graph.add_edge("analyze", "design")
    graph.add_edge("design", "bottleneck")
    graph.add_edge("bottleneck", "diagram")
    graph.add_edge("diagram", END)

    return graph.compile()


_pipeline = _build_graph()


def run_pipeline(file_tree: str, file_contents: str) -> dict:
    """Run the full analysis pipeline. Returns the complete final state."""
    initial_state: PipelineState = {
        "file_tree": file_tree,
        "file_contents": file_contents,
        "repo_analysis": {},
        "system_design": {},
        "bottlenecks": {},
        "diagram": {},
    }
    return _pipeline.invoke(initial_state)
