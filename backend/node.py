from typing import Literal
from typing_extensions import TypedDict
import logging
import json
from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph import MessagesState, END
from langgraph.types import Command
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent
from langchain_community.tools.tavily_search import TavilySearchResults
import tools

# Get a logger for this module
logger = logging.getLogger(__name__)

class State(MessagesState):
    next: str

# Supervisor node: routes messages between team members
def make_supervisor_node(
    llm: BaseChatModel, 
    members: list[str], 
    on_yield=None, 
    node_name: str = "supervisor"
) -> callable:
    options = ["FINISH"] + members
    system_prompt = (
        "You are a supervisor tasked with managing a conversation between the"
        f" following workers: {members}. Given the following user request,"
        " respond with the worker to act next. Each worker will perform a"
        " task and respond with their results and status. When finished,"
        " respond with FINISH."
    )

    class Router(TypedDict):
        next: Literal[*options] # type: ignore

    async def supervisor_node(state: State) -> Command[Literal[*members, "__end__"]]: # type: ignore
        logger.info(f"supervisor_node called, state: {state}, node_name: {node_name}")
        messages = [
            {"role": "system", "content": system_prompt},
        ] + state["messages"]
        logger.info(f"Calling LLM for routing decision, messages length: {len(messages)}")
        response = await llm.with_structured_output(Router).ainvoke(messages)
        goto = response["next"]
        # Real-time message sent to frontend
        if on_yield is not None:
            await on_yield(
                node_name, 
                json.dumps({"next": goto})
            )
        if goto == "FINISH":
            goto = END
        logger.info(f"Routing decision result: {goto}")
        
        return Command(goto=goto, update={"next": goto})

    return supervisor_node

# Node for search agent
def make_search_node(
    llm: BaseChatModel, 
    tavily_tool: TavilySearchResults, 
    goto: str = 'supervisor', 
    on_yield=None
) -> callable:
    search_agent = create_react_agent(llm, tools=[tools.tavily_tool])

    async def search_node(state: State) -> Command:
        logger.info(f"search_node called, state: {state}")
        result = await search_agent.ainvoke(state)
        # Real-time message sent to frontend
        if on_yield is not None:
            await on_yield("search", result["messages"][-1].content)
        return Command(
            update={
                "messages": [
                    HumanMessage(content=result["messages"][-1].content, name="search")
                ]
            },
            goto=goto,
        )
    return search_node

# Node for web scraper agent
def make_web_scraper_node(
    llm: BaseChatModel, 
    goto: str = "supervisor", 
    on_yield=None
) -> callable:
    web_scraper_agent = create_react_agent(llm, tools=[tools.scrape_webpages])

    async def web_scraper_node(state: State) -> Command:
        logger.info(f"web_scraper_node called, state: {state}")
        result = await web_scraper_agent.ainvoke(state)
        #Real-time message sent to frontend
        if on_yield is not None:
            await on_yield("web_scraper", result["messages"][-1].content)
        return Command(
            update={
                "messages": [
                    HumanMessage(content=result["messages"][-1].content, name="web_scraper")
                ]
            },
            goto=goto,
        )
    return web_scraper_node

# Node for document writing agent
def make_doc_writing_node(
    llm: BaseChatModel, 
    goto: str = "supervisor", 
    on_yield=None, 
    node_name="doc_writer"
) -> callable:
    doc_writer_agent = create_react_agent(llm,
        tools=[tools.write_document, tools.edit_document, tools.read_document],
        prompt=(
            "You can read, write and edit documents based on note-taker's outlines. "
            "Don't ask follow-up questions."
        ),
    )

    async def doc_writing_node(state: State) -> Command[Literal["supervisor"]]:
        logger.info(f"doc_writing_node called, state: {state}")
        result = await doc_writer_agent.ainvoke(state)
        
        #Real-time message sent to frontend
        if on_yield is not None:
            await on_yield(node_name, result["messages"][-1].content)
        return Command(
            update={
                "messages": [
                    HumanMessage(content=result["messages"][-1].content, name=node_name)
                ]
            },
            goto=goto,
        )

    return doc_writing_node

# Node for note taking agent
def make_note_taking_node(
    llm: BaseChatModel, 
    goto: str = "supervisor", 
    on_yield=None, 
    node_name="note_taker"
) -> callable:
    note_taking_agent = create_react_agent(
        llm,
        tools=[tools.create_outline, tools.read_document],
        prompt=(
            "You can read documents and create outlines for the document writer. "
            "Don't ask follow-up questions."
        ),
    )

    async def note_taking_node(state: State) -> Command[Literal["supervisor"]]:
        logger.info(f"note_taking_node called, state: {state}")
        result = await note_taking_agent.ainvoke(state)
        
        #Real-time message sent to frontend
        if on_yield is not None:
            await on_yield(node_name, result["messages"][-1].content)
        return Command(
            update={
                "messages": [
                    HumanMessage(content=result["messages"][-1].content, name=node_name)
                ]
            },
            goto=goto,
        )

    return note_taking_node

# Node for chart generating agent
def make_chart_generating_node(
    llm: BaseChatModel, 
    goto: str = "supervisor", 
    on_yield=None, 
    node_name="chart_generator"
) -> callable:
    chart_generating_agent = create_react_agent(
        llm, tools=[tools.read_document, tools.python_repl_tool]
    )

    async def chart_generating_node(state: State) -> Command[Literal["supervisor"]]:
        logger.info(f"chart_generating_node called, state: {state}")
        result = await chart_generating_agent.ainvoke(state)
        
        #Real-time message sent to frontend
        if on_yield is not None:
            await on_yield(node_name, result["messages"][-1].content)
        return Command(
            update={
                "messages": [
                    HumanMessage(content=result["messages"][-1].content, name=node_name)
                ]
            },
            goto=goto,
        )

    return chart_generating_node

# Call the research team graph as a node
def make_call_research_team(research_graph):
    async def call_research_team(state: State) -> Command:
        logger.info(f"call_research_team called, state: {state}")
        if research_graph is None:
            logger.error("research_graph is None, cannot call invoke method")
            return Command(
                update={
                    "messages": [
                        HumanMessage(
                            content="Error: Research team graph is None, cannot process request", name="research_team"
                        )
                    ]
                },
                goto=END, # Cannot be handled by supervisor node, can only end
            )
        try:
            logger.info(f"Calling research_graph.ainvoke, input: {state['messages'][-1]}")
            response = await research_graph.ainvoke({"messages": state["messages"][-1]})
            return Command(
                update={
                    "messages": [
                        HumanMessage(
                            content=response["messages"][-1].content, name="research_team"
                        )
                    ]
                },
                goto="supervisor",
            )
        except Exception as e:
            logger.error(f"Error calling research_graph.ainvoke: {str(e)}", exc_info=True)
            return Command(
                update={
                    "messages": [
                        HumanMessage(
                            content=f"Error processing request by research team: {str(e)}", name="research_team"
                        )
                    ]
                },
                goto=END,
            )
    return call_research_team

# Call the writing team graph as a node
def make_call_paper_writing_team(writing_graph):
    async def call_paper_writing_team(state: State) -> Command:
        logger.info(f"call_paper_writing_team called, state: {state}")
        if writing_graph is None:
            logger.error("writing_graph is None, cannot call invoke method")
            return Command(
                update={
                    "messages": [
                        HumanMessage(
                            content="Error: Writing team graph is None, cannot process request", name="writing_team"
                        )
                    ]
                },
                goto=END,
            )
        try:
            logger.info(f"Calling writing_graph.ainvoke, input: {state['messages'][-1]}")
            response = await writing_graph.ainvoke({"messages": state["messages"][-1]})
            logger.info(f"writing_graph.ainvoke call result: {response}")
            return Command(
                update={
                    "messages": [
                        HumanMessage(
                            content=response["messages"][-1].content, name="writing_team"
                        )
                    ]
                },
                goto="supervisor",
            )
        except Exception as e:
            logger.error(f"Error calling writing_graph.ainvoke: {str(e)}", exc_info=True)
            return Command(
                update={
                    "messages": [
                        HumanMessage(
                            content=f"Error processing request by writing team: {str(e)}", name="writing_team"
                        )
                    ]
                },
                goto=END,
            )
    return call_paper_writing_team