"""
🎙️ The Brain — YatriAI LangGraph & Groq Backend Server (Port 8002)

===============================================================================
BEGINNER DEVELOPER ARCHITECTURE GUIDE:
===============================================================================

1. What is this file?
   This file is the "Brain" of YatriAI (यात्री AI). It runs a Python FastAPI web server
   on Port 8002 that hosts an autonomous LangGraph agent powered by Groq / OpenAI.

2. How does an Agent differ from a standard Chatbot?
   - Simple Chatbot: Takes a prompt string, calls an LLM, and sends back a static JSON string.
     If you refresh the page, the bot forgets who you are.
   - LangGraph Agent: Operates on a state graph (nodes & edges). It maintains long-term
     session memory (via MemorySaver), can call external tools (weather, train schedules,
     itinerary cards), and streams tokens in real time.

3. The 3-Tier Decoupled Flow:
   [1. React UI (:3002)] 
         │ (User types: "Plan 4 days in Jaipur")
         ▼
   [2. CopilotRuntime Gateway (:4002)] 
         │ (Routes request based on agentId="default")
         ▼
   [3. LangGraph FastAPI Backend (:8002)] <-- YOU ARE HERE!
         │ (Retrieves conversation history via thread_id, applies guardrails, calls LLM)
         ▼
   [4. Groq / OpenAI LLM]
         │ (Streams tokens back via Server-Sent Events [SSE] protocol)
         ▼
   [Live typewriter response in React chat bubble!]

4. What are Domain Guardrails?
   In enterprise applications, you never want your travel assistant answering coding
   questions, writing essays, or discussing world politics. We enforce strict "guardrails"
   inside the system prompt that instruct the LLM to politely refuse any query that is
   not about traveling within India.
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

# Default networking configuration
HOST = "0.0.0.0"
PORT = 8002
MODEL = "gpt-4.1"


def _ensure_openai_api_key() -> None:
    """
    Ensure at least one valid LLM API key (GROQ_API_KEY or OPENAI_API_KEY) is present.
    If not, attempts to load from helper utility or raises a helpful error.
    """
    if os.environ.get("GROQ_API_KEY") or os.environ.get("OPENAI_API_KEY"):
        return

    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from helper import get_openai_api_key

    os.environ["OPENAI_API_KEY"] = get_openai_api_key()


def build_chat_model(model_name: str = MODEL):
    """
    Component 1: The Model Connector (LLM Factory)
    -------------------------------------------------
    This function dynamically connects to the best available LLM provider:
    
    1. Groq (High-Speed Inference):
       - If GROQ_API_KEY is found in .env, it routes inference to Groq's LPUs
         (Language Processing Units) using 'openai/gpt-oss-120b'.
       - Benefit: Delivers response latency under ~0.8s (10x faster than standard APIs).
       
    2. OpenAI (Fallback):
       - If no Groq key is found, it seamlessly falls back to standard OpenAI.
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


# =============================================================================
# Component 2: System Prompt & Domain Guardrails
# =============================================================================
# The System Prompt is the "charter" or "instruction manual" for the LLM.
# It sets the persona, tone, rules, and negative constraints (what NOT to answer).
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
    """
    Component 3: LangGraph Agent Graph with Persistent Memory
    ----------------------------------------------------------
    Builds the state graph that drives the conversation:

    - chat_model: The LLM configured above (Groq / OpenAI).
    - checkpointer=MemorySaver(): 
        CRITICAL: Instead of storing chat history in a fragile browser cookie
        or frontend localStorage, MemorySaver stores state on the server.
        Every user conversation receives a unique 'thread_id'. When the user
        sends a new message, LangGraph reloads past turns for that thread_id
        so the agent has complete context of earlier discussion.
    - middleware=[CopilotKitMiddleware()]:
        Bridges LangGraph internal events into CopilotKit frontend protocols,
        allowing the agent to trigger generative UI components on the client.
    - system_prompt:
        Enforces our India Travel guardrails and persona.
    """
    chat_model = build_chat_model(model_name=model_name)
    return create_agent(
        model=chat_model,
        tools=[],
        middleware=[CopilotKitMiddleware()],
        checkpointer=MemorySaver(),
        system_prompt=INDIA_TRAVEL_SYSTEM_PROMPT,
    )


# =============================================================================
# Component 4: FastAPI Server & AG-UI Server-Sent Events (SSE) Endpoint
# =============================================================================
# Exposes an AG-UI compatible streaming endpoint at http://localhost:8002/.
#
# Why Server-Sent Events (SSE)?
# - Standard REST APIs wait until the ENTIRE answer is generated before returning.
#   For an LLM generating a 400-word itinerary, the user would stare at a spinner for 10s.
# - SSE opens a persistent one-way HTTP connection that streams token chunks as they
#   are generated, giving the user an instant, real-time "typewriter" animation!
#
# What are 'name' and 'description' used for?
# - name: Unique agent identifier visible in discovery endpoints.
# - description: Used by multi-agent orchestrator gateways to route questions
#   to specialized agents based on user intent.
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
