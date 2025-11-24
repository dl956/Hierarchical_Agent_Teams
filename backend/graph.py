import logging
from langgraph.graph import StateGraph, START
from langchain_core.tools.base import BaseTool
from langchain_core.language_models.chat_models import BaseChatModel
from pathlib import Path

from node import State
from node import make_supervisor_node
from node import make_search_node, make_web_scraper_node
from node import make_doc_writing_node, make_note_taking_node, make_chart_generating_node
from node import make_call_research_team, make_call_paper_writing_team
import tools

from langchain_community.tools.tavily_search import TavilySearchResults
from typing import Callable, Any

logger = logging.getLogger(__name__)
WORKING_DIRECTORY = tools.WORKING_DIRECTORY


#Build the top-level supervisor graph that delegates tasks to research and writing teams.
def build_super_team_graph(
    llm: BaseChatModel,
    research_graph: Any,
    writing_graph: Any,
    on_yield: Callable = None
) -> Any:
    teams_supervisor_node = make_supervisor_node(llm, ["research_team", "writing_team"], on_yield=on_yield, node_name="super_team")
    # Assume research_graph and writing_graph have already recursively received on_yield
    call_research_team = make_call_research_team(research_graph)
    call_writing_team = make_call_paper_writing_team(writing_graph)
    super_builder = StateGraph(State)
    super_builder.add_node("supervisor", teams_supervisor_node)
    super_builder.add_node("research_team", call_research_team)
    super_builder.add_node("writing_team", call_writing_team)
    super_builder.add_edge(START, "supervisor")
    return super_builder.compile()

#Build the research team graph consisting of search and web scraper nodes.
def build_research_team_graph(
    llm: BaseChatModel,
    search_tool: TavilySearchResults,
    on_yield: Callable = None
) -> Any:
    research_supervisor_node = make_supervisor_node(llm, ["search", "web_scraper"], on_yield=on_yield, node_name="research_team")
    search_node = make_search_node(llm, search_tool, goto='supervisor', on_yield=on_yield)
    web_scraper_node = make_web_scraper_node(llm, goto='supervisor', on_yield=on_yield)
    research_builder = StateGraph(State)
    research_builder.add_node("supervisor", research_supervisor_node)
    research_builder.add_node("search", search_node)
    research_builder.add_node("web_scraper", web_scraper_node)
    research_builder.add_edge(START, "supervisor")
    return research_builder.compile()


#Build the writing team graph consisting of doc_writer, note_taker, and chart_generator nodes.
def build_writing_team_graph(
    llm: BaseChatModel,
    working_dir: Path = WORKING_DIRECTORY,
    on_yield: Callable = None
) -> Any:
    logger.info(f"Starting to build writing_team_graph, working_dir: {working_dir}")
    doc_writing_supervisor_node = make_supervisor_node(
        llm, ["doc_writer", "note_taker", "chart_generator"], on_yield=on_yield, node_name="writing_team"
    )
    doc_writing_node = make_doc_writing_node(llm, on_yield=on_yield, node_name="doc_writer")
    note_taking_node = make_note_taking_node(llm, on_yield=on_yield, node_name="note_taker")
    chart_generating_node = make_chart_generating_node(llm, on_yield=on_yield, node_name="chart_generator")

    paper_writing_builder = StateGraph(State)
    paper_writing_builder.add_node("supervisor", doc_writing_supervisor_node)
    paper_writing_builder.add_node("doc_writer", doc_writing_node)
    paper_writing_builder.add_node("note_taker", note_taking_node)
    paper_writing_builder.add_node("chart_generator", chart_generating_node)

    paper_writing_builder.add_edge(START, "supervisor")

    logger.info("writing_team_graph build completed")
    return paper_writing_builder.compile()