"""
🎙️ Stop 3: The Brain — LangGraph & Groq Backend

This is the primary Python backend server running on Port 8002.
It uses LangGraph to manage stateful multi-turn agent conversations and
streams responses using the AG-UI (Server-Sent Events) protocol.

Key Architectural Components:
1. Model Connector (build_chat_model):
   - Dynamically loads GROQ_API_KEY or OPENAI_API_KEY from .env.
   - Routes through Groq's high-speed API (openai/gpt-oss-120b) by default.

2. Agent Graph with Memory (build_graph):
   - MemorySaver(): Persists conversation state across multiple turns using thread IDs.
   - CopilotKitMiddleware(): Bridges LangGraph events into CopilotKit frontend tools.

3. AG-UI FastAPI Endpoint:
   - Exposes an SSE stream on "/" that emits token chunks, tool execution events,
     and run completion events directly to the gateway.
"""

from __future__ import annotations

import os
import subprocess as _sp
import sys
import threading
import time
import warnings
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Ensure .env overrides any environment variables cached in the shell session
load_dotenv(override=True)

warnings.filterwarnings("ignore")

import uvicorn
from ag_ui_langgraph import add_langgraph_fastapi_endpoint
from copilotkit import CopilotKitMiddleware, LangGraphAGUIAgent
from fastapi import FastAPI
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver

HOST = "0.0.0.0"
PORT = 8002
MODEL = "gpt-4.1"


def _ensure_openai_api_key() -> None:
    """Ensure at least one valid LLM API key is present."""
    if os.environ.get("GROQ_API_KEY") or os.environ.get("OPENAI_API_KEY"):
        return

    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from helper import get_openai_api_key

    os.environ["OPENAI_API_KEY"] = get_openai_api_key()


def build_chat_model(model_name: str = MODEL):
    """
    1. The Model Connector
    Inspects .env to configure either Groq or OpenAI:
    - If GROQ_API_KEY is present: Connects to Groq's high-speed OpenAI-compatible
      endpoint (https://api.groq.com/openai/v1) using 'openai/gpt-oss-120b'.
    - Otherwise: Falls back to standard OpenAI ChatOpenAI.
    """
    load_dotenv(override=True)
    groq_key = os.environ.get("GROQ_API_KEY")
    if groq_key:
        groq_model = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
        masked = groq_key[:8] + "..." + groq_key[-4:]
        print(f"✓ Active API Key in use: GROQ_API_KEY ({masked}) with model '{groq_model}'")
        return ChatOpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=groq_key,
            model=groq_model,
        )

    _ensure_openai_api_key()
    api_key = os.environ.get("OPENAI_API_KEY", "")
    masked = (api_key[:8] + "..." + api_key[-4:]) if api_key else "None"
    print(f"✓ Active API Key in use: OPENAI_API_KEY ({masked}) with model '{model_name}'")
    return ChatOpenAI(model=model_name, api_key=api_key if api_key else None)


INDIA_TRAVEL_SYSTEM_PROMPT = (
    "You are 'YatriAI' (यात्री AI), an expert, culturally rich, and highly specialized travel assistant dedicated EXCLUSIVELY to tourism and travel in India (Bharat).\n\n"
    "STRICT SCOPE & GUARDRAILS:\n"
    "1. You MUST ONLY answer questions related to travel, tourism, itineraries, sightseeing, culture, heritage, food, weather, transportation (IRCTC trains, domestic flights, cabs, buses), hotels, stays, and travel tips WITHIN INDIA.\n"
    "2. If the user asks about ANYTHING outside travel in India (such as general knowledge, coding, math, world politics, philosophy, or travel to destinations OUTSIDE India like Paris, Dubai, New York, Bali, etc.), you MUST politely and warmly DECLINE, and steer them back to Indian travel. For example:\n"
    "   'Namaste! 🙏 I am exclusively an India Travel Companion. I cannot help with topics outside travel in India. I would love to help you plan an unforgettable journey across India instead — from Kashmir to Kanyakumari! Where in India would you like to explore?'\n\n"
    "TRAVEL ASSISTANCE GUIDELINES:\n"
    "- Provide clear, realistic, day-by-day itineraries (e.g. Day 1, Day 2) with morning, afternoon, and evening suggestions.\n"
    "- Quote budgets and estimated costs in Indian Rupees (₹ / INR), offering budget (backpacker), mid-range, and luxury options.\n"
    "- Recommend authentic local culinary experiences (e.g. street food spots, regional thalis, iconic local restaurants).\n"
    "- Provide practical logistics: best railway stations, Vande Bharat/Rajdhani express trains, Tatkal booking advice, nearest domestic airports, state transport options, and auto/cab tips (Ola, Uber, prepaid taxi booths).\n"
    "- Highlight seasonal nuances: monsoon travel warnings, summer hill-station escapes, winter desert/beach getaways, and local festivals (Holi, Diwali, Pushkar Mela, Hornbill Festival, Durga Puja).\n"
    "- Tone: Warm, respectful, authentic, and inspiring (use Indian greetings like 'Namaste 🙏', 'Padharo Mhare Desh 🪔', etc.)."
)


def build_graph(model_name: str = MODEL):
    """Build the core LangGraph workflow for the India Travel Agent."""
    chat_model = build_chat_model(model_name=model_name)
    return create_agent(
        model=chat_model,
        tools=[],
        middleware=[CopilotKitMiddleware()],
        checkpointer=MemorySaver(),
        system_prompt=INDIA_TRAVEL_SYSTEM_PROMPT,
    )


# 3. FastAPI AG-UI Endpoint
app = FastAPI(title="YatriAI - India Travel Agent API")
graph = build_graph()
agent = LangGraphAGUIAgent(
    name="india_travel_agent",
    description="YatriAI: Dedicated India Travel & Itinerary Assistant",
    graph=graph,
)
add_langgraph_fastapi_endpoint(app=app, agent=agent, path="/")

_server_started = False
_server_lock = threading.Lock()


def _kill_port(port: int) -> None:
    """Kill any process currently listening on *port* (cross-platform for Windows, macOS, Linux)."""
    if sys.platform == "win32":
        try:
            # Query active TCP connections on Windows and kill listening PID
            out = _sp.run(
                ["netstat", "-ano"], capture_output=True, text=True, check=False
            ).stdout
            for line in out.splitlines():
                if f":{port}" in line and "LISTENING" in line:
                    parts = line.strip().split()
                    pid = parts[-1]
                    if pid and pid != "0":
                        print(
                            f"⚠ Found existing process (PID {pid}) on port {port} — killing it"
                        )
                        _sp.run(["taskkill", "/F", "/PID", pid], capture_output=True, check=False)
            time.sleep(0.5)
        except Exception:
            pass
    else:
        try:
            result = _sp.run(["lsof", "-ti", f":{port}"], capture_output=True, text=True)
            for pid in result.stdout.strip().split():
                if pid:
                    print(
                        f"⚠ Found existing process (PID {pid}) on port {port} — killing it"
                    )
                    os.kill(int(pid), 9)
            if result.stdout.strip():
                time.sleep(0.5)
        except Exception:
            pass


def load_graph(model_name: str = MODEL):
    """Rebuild and reload the graph with the specified model."""
    agent.graph = build_graph(model_name=model_name)
    return agent.graph


def start_backend(
    host: str = HOST, port: int = PORT, log_level: str = "warning"
) -> str:
    """Helper used in notebooks to start uvicorn in a background thread."""
    global _server_started

    with _server_lock:
        if not _server_started:
            _kill_port(port)
            threading.Thread(
                target=lambda: uvicorn.run(
                    app, host=host, port=port, log_level=log_level
                ),
                daemon=True,
            ).start()
            _server_started = True

    return f"http://localhost:{port}"


def main() -> None:
    """Entry point when running 'python main.py' from terminal."""
    load_graph()
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    main()
