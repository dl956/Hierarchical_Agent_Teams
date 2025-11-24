from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env
import tools
import os
import logging
import json
import asyncio

from collector import AsyncYieldCollector
from graph import build_research_team_graph, build_writing_team_graph, build_super_team_graph



your_openai_api_key = os.getenv("OPENAI_API_KEY")
if not your_openai_api_key:
    raise RuntimeError("OPENAI_API_KEY is not set. Please check your environment variables or .env file.")

WORKING_DIRECTORY = tools.WORKING_DIRECTORY

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

llm = ChatOpenAI(
    model_name="gpt-4o-mini",
    streaming=True,
    openai_api_key=your_openai_api_key,
    base_url="https://api.poixe.com/v1"
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.websocket("/ws/stream")
async def ws_stream(websocket: WebSocket):
    await websocket.accept()
    try:
        # 等待前端发来的 {"query": "...", "graph": "..."}
        data = await websocket.receive_json()
        query = data.get("query", "")
        graph_name = data.get("graph", "supervisor")

        InnerMessageCollector = AsyncYieldCollector()
        research_team = build_research_team_graph(llm, tools.tavily_tool, on_yield=InnerMessageCollector.on_yield)
        writing_team = build_writing_team_graph(llm, WORKING_DIRECTORY, on_yield=InnerMessageCollector.on_yield)
        super_team = build_super_team_graph(llm, research_team, writing_team)

        user_input = {"messages": [HumanMessage(content=query)]}
        logger.info(f"agent_stream: user_input={user_input}")
        stream_config = {"recursion_limit": 100}
        superTeamAstream = super_team.astream(user_input, stream_config, stream_mode="messages")

        superTeamAstream_task = asyncio.create_task(superTeamAstream.__anext__())
        InnerMessageCollector_task = asyncio.create_task(InnerMessageCollector.get())

        while True:
            done, pending = await asyncio.wait(
                [superTeamAstream_task, InnerMessageCollector_task], return_when=asyncio.FIRST_COMPLETED
            )
            if superTeamAstream_task in done:
                try:
                    message, metadata = superTeamAstream_task.result()

                    for token in message.content:
                        response_data = {"content": token, "metadata": metadata.get("langgraph_checkpoint_ns")}
                        await websocket.send_text(json.dumps(response_data))
                        await asyncio.sleep(0.003)

                    superTeamAstream_task = asyncio.create_task(superTeamAstream.__anext__())
                except StopAsyncIteration:
                    break
                except Exception as e:
                    logger.exception("Error in superTeamAstream_task")
                    await websocket.send_text(json.dumps({"event": "error", "msg": str(e)}))
            if InnerMessageCollector_task in done:
                try:
                    msg = InnerMessageCollector_task.result()
                    for token in msg['content']:
                        response_data = {"content": token, "metadata": msg['agent']}
                        await websocket.send_text(json.dumps(response_data))
                        await asyncio.sleep(0.003)
                    InnerMessageCollector_task = asyncio.create_task(InnerMessageCollector.get())
                except Exception as e:
                    logger.exception("Error in InnerMessageCollector_task")
                    await websocket.send_text(json.dumps({"event": "error", "msg": str(e)}))

        await websocket.send_text(json.dumps({"event": "end"}))
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.exception("WebSocket stream error")
        await websocket.send_text(json.dumps({"event": "error", "msg": str(e)}))

@app.get("/files")
async def list_files() -> JSONResponse:
    """
    Get list of files in working directory, sorted by creation time (newest first)
    """
    file_objs = []
    for file_path in WORKING_DIRECTORY.glob("**/*"):
        if file_path.is_file():
            rel_path = file_path.relative_to(WORKING_DIRECTORY)
            ctime = file_path.stat().st_ctime  # creation time
            file_objs.append((str(rel_path), ctime))
    # Sort by creation time, newest first
    file_objs.sort(key=lambda x: -x[1])
    files = [name for name, _ in file_objs]
    return JSONResponse(content={"files": files})

@app.get("/download")
async def download_file(file_name: str) -> FileResponse:
    """
    Download file from working directory with directory traversal protection
    """
    full_path = (WORKING_DIRECTORY / file_name).resolve()
    if not str(full_path).startswith(str(WORKING_DIRECTORY.resolve())):
        raise HTTPException(status_code=403, detail="Invalid file path (possible traversal attack)")
    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        path=str(full_path),
        filename=full_path.name,
        media_type="application/octet-stream"
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)