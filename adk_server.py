"""
🤖 Google ADK Agent Server — Gemini Agentic Runtime (Port 8009)

===============================================================================
BEGINNER DEVELOPER ARCHITECTURE GUIDE:
===============================================================================

1. What is this file?
   This file runs an alternative backend agent using Google's Agent Development
   Kit (ADK) and Google Gemini (gemini-3.8-flash / gemini-2.0-flash) on Port 8009.

2. How does ADK compare to LangGraph?
   - LangGraph (main.py): Graph-based state machine with nodes, edges, and checkpointers.
   - Google ADK (adk_server.py): High-level agent framework by Google with built-in
     session state management, in-memory conversation persistence, and Gemini-native tools.

3. Switching between LangGraph and Gemini in the UI:
   - To use LangGraph (:8002): Set `agentId = "default"` in frontend/src/App.tsx
   - To use Gemini (:8009):    Set `agentId = "gemini"` in frontend/src/App.tsx
   The CopilotKit Gateway (:4002) transparently routes traffic to the correct port.
"""

import os
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from ag_ui_adk import ADKAgent, add_adk_fastapi_endpoint
from google.adk.agents import LlmAgent

# Load environment variables (.env)
load_dotenv()

# Verify Google API key is set
if not os.getenv("GOOGLE_API_KEY") and not os.getenv("GEMINI_API_KEY"):
    print("⚠ Warning: GOOGLE_API_KEY is not set in your .env file!")

# Component 1: Google Gemini LLM Agent
# instruction: The System Prompt sent to the LLM (Gemini) before any conversation begins.
# Defines the agent's persona, tone, rules, and scope (equivalent to system_prompt in main.py).
gemini_agent = LlmAgent(
    name="assistant",
    model="gemini-3.8-flash",
    instruction="You are YatriAI, an expert and helpful India Travel Companion. Help users plan unforgettable trips across India.",
)

# Component 2: Stateful Session & Memory Management
# Wraps the raw LLM agent with conversation persistence so the model remembers multi-turn context.
adk_agent = ADKAgent(
    adk_agent=gemini_agent,
    app_name="yatri_ai",
    user_id="traveler",
    session_timeout_seconds=3600,
    use_in_memory_services=True,  # In-memory state management across conversation turns
)

# Component 3: FastAPI Server & AG-UI Streaming Endpoint
app_adk = FastAPI(title="YatriAI - Google ADK Gemini Agent API")
add_adk_fastapi_endpoint(app_adk, adk_agent, path="/")


def main() -> None:
    """Entry point when running 'python adk_server.py' from terminal."""
    print("✓ Starting Google ADK Gemini agent on http://localhost:8009 ...")
    uvicorn.run(app_adk, host="0.0.0.0", port=8009)


if __name__ == "__main__":
    main()

