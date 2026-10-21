# 🏛️ Architecture Decision Records (ADRs) — YatriAI (India Travel Agent)

This document records the foundational architecture and design decisions made during the conception, design, and implementation of the **YatriAI (India Travel Agent)** application.

---

## 📑 Index of Decisions

- [ADR-001: Strict Domain Specialization & Regional Guardrails (India Only)](#adr-001-strict-domain-specialization--regional-guardrails-india-only)
- [ADR-002: Decoupled 3-Tier Multi-Agent Architecture with Hono Gateway](#adr-002-decoupled-3-tier-multi-agent-architecture-with-hono-gateway)
- [ADR-003: Agent Orchestration Engine Selection — LangGraph State Machine](#adr-003-agent-orchestration-engine-selection--langgraph-state-machine)
- [ADR-004: Server-Side State Checkpointing & Session Memory (`MemorySaver`)](#adr-004-server-side-state-checkpointing--session-memory-memorysaver)
- [ADR-005: Inference Provider Strategy — High-Speed Groq LPU with OpenAI Fallback](#adr-005-inference-provider-strategy--high-speed-groq-lpu-with-openai-fallback)
- [ADR-006: Streaming Communication Protocol — AG-UI & Server-Sent Events (SSE)](#adr-006-streaming-communication-protocol--ag-ui--server-sent-events-sse)
- [ADR-007: Multi-Runtime Extensibility — Google ADK & Gemini Support](#adr-007-multi-runtime-extensibility--google-adk--gemini-support)
- [ADR-008: Verification Strategy for Non-Deterministic AI Systems (`test_agent.py`)](#adr-008-verification-strategy-for-non-deterministic-ai-systems-test_agentpy)

---

## ADR-001: Strict Domain Specialization & Regional Guardrails (India Only)

* **Status:** Accepted  
* **Date:** October 2026  
* **Context:**  
  Foundational LLMs (like GPT-4, Llama-3) are trained on general internet data. Left unconstrained, a travel bot will happily answer general knowledge questions, solve math/coding problems, or discuss international tourism (e.g. Paris, New York). In an enterprise context, this causes:
  1. High API token costs and resource exhaustion.
  2. Brand and liability risks from inaccurate advice on unapproved domains.
  3. Loss of domain focus and conversational identity.

* **Decision:**  
  Constrain the agent strictly to tourism, heritage, transport, and itineraries within India (Bharat) using a 3-part guardrail strategy:
  1. **Explicit Whitelist (Closed-World Assumption):** Enumerate allowed topics (IRCTC, regional food, seasons, stays, routes).
  2. **Explicit Negative Constraints:** Explicitly ban coding, math, world politics, and international destinations.
  3. **Refusal & Steering Pattern:** Require polite refusal accompanied by an enthusiastic steering back to Indian destinations.
  4. **Tool Sandboxing (`tools=[]`):** Remove general-purpose execution tools (code interpreters, web search) so the LLM cannot bypass guardrails through tool calls.

* **Consequences:**  
  - *Positive:* Reliable domain boundaries, predictable token usage, and cultural authenticity.
  - *Trade-off:* Requires testing to ensure the model does not reject valid edge queries (e.g. asking about international flights arriving into Mumbai).
* **Implementation:** [`main.py:L128-L141`](file:///Users/basavraj/Desktop/india-travel-agent/main.py#L128-L141) (`INDIA_TRAVEL_SYSTEM_PROMPT`).

---

## ADR-002: Decoupled 3-Tier Multi-Agent Architecture with Hono Gateway

* **Status:** Accepted  
* **Date:** October 2026  
* **Context:**  
  Connecting a React frontend directly to a Python AI backend or directly to OpenAI API keys creates several problems:
  - Security vulnerability: Exposing API keys or internal microservice URLs to browser bundles.
  - Protocol lock-in: Frontend must be rewritten if backend changes from Python to Go or LangGraph to ADK.
  - Inability to route between multiple specialized agents (e.g., flight agent vs hotel agent).

* **Decision:**  
  Implement a **Decoupled 3-Tier Architecture**:
  1. **Frontend Tier (Port 3002):** React 19 + Vite + TailwindCSS.
  2. **Gateway Tier (Port 4002):** Node.js + Hono using `@copilotkit/runtime`.
  3. **Agent Tier (Port 8002 / 8009):** Python FastAPI hosting LangGraph or Google ADK.
  The frontend sends requests only to `/api/copilotkit`, and the Gateway resolves routing based on `agentId`.

* **Consequences:**  
  - *Positive:* High security, hot-swappable agent backends, protocol normalization, zero CORS issues via Vite dev proxy.
  - *Trade-off:* Requires running two processes during local development (`python main.py` and `npm run dev`).
* **Implementation:** [`frontend/src/App.tsx`](file:///Users/basavraj/Desktop/india-travel-agent/frontend/src/App.tsx), [`frontend/server.ts`](file:///Users/basavraj/Desktop/india-travel-agent/frontend/server.ts), [`frontend/vite.config.ts`](file:///Users/basavraj/Desktop/india-travel-agent/frontend/vite.config.ts).

---

## ADR-003: Agent Orchestration Engine Selection — LangGraph State Machine

* **Status:** Accepted  
* **Date:** October 2026  
* **Context:**  
  Simple chatbots use stateless completion loops (`openai.chat.completions.create`). Production-grade agents require:
  - Managing cycles, conditional branching, and tool calling loops.
  - State preservation across turns.
  - First-class middleware hooks for frontend UI streaming.

* **Alternatives Considered:**  
  - *LangChain Classic `AgentExecutor`:* Deprecated, rigid execution flow, difficult to customize.
  - *Custom Python `while` loops:* Brittle, lacks standardized serialization and event hooks.
  - *LangGraph:* Directed cyclic graph architecture with native checkpointer support.

* **Decision:**  
  Standardize on **LangGraph** (`langgraph` and `langchain.agents.create_agent`). LangGraph treats conversations as state graphs where each user turn, tool invocation, and LLM response is a state transition.

* **Consequences:**  
  - *Positive:* Cyclic graph capability, robust checkpointer interfaces, native compatibility with CopilotKit middleware.
  - *Trade-off:* Steeper initial learning curve than basic completion scripts.
* **Implementation:** [`main.py:L144-L170`](file:///Users/basavraj/Desktop/india-travel-agent/main.py#L144-L170) (`build_graph()`).

---

## ADR-004: Server-Side State Checkpointing & Session Memory (`MemorySaver`)

* **Status:** Accepted  
* **Date:** October 2026  
* **Context:**  
  Multi-turn conversations require the agent to remember earlier details (e.g. Turn 1: *"My budget is ₹45,000"*; Turn 2: *"What was my budget?"*).  
  Passing full conversation history in browser cookies or client requests causes bloated HTTP payloads, security risks (client tampering), and state loss when switching devices.

* **Decision:**  
  Use server-side state checkpointing via LangGraph's **`MemorySaver`**. Every conversation thread is identified by a unique `thread_id`. LangGraph automatically persists and restores past turns on the server for each turn.

* **Consequences:**  
  - *Positive:* Lightweight client payloads, tamper-proof state history, seamless multi-turn reasoning.
  - *Trade-off:* In-memory checkpointers reset on server restarts. (For multi-instance production, `MemorySaver` can be swapped for `PostgresSaver` without changing agent logic).
* **Implementation:** [`main.py:L168`](file:///Users/basavraj/Desktop/india-travel-agent/main.py#L168), [`test_agent.py:L117-L150`](file:///Users/basavraj/Desktop/india-travel-agent/test_agent.py#L117-L150).

---

## ADR-005: Inference Provider Strategy — High-Speed Groq LPU with OpenAI Fallback

* **Status:** Accepted  
* **Date:** October 2026  
* **Context:**  
  Travel itineraries are long-form outputs (often 300–600 tokens). Traditional cloud API endpoints can take 4–10 seconds to generate a full response, leading to user drop-off. Furthermore, developers may not have active paid accounts across all providers.

* **Decision:**  
  Implement a dynamic **dual-provider model connector**:
  1. **Primary (High-Speed):** If `GROQ_API_KEY` is present in `.env`, route to Groq's LPUs using `openai/gpt-oss-120b` via OpenAI-compatible endpoints. Delivers sub-second (< 0.8s) response turnaround.
  2. **Fallback:** If Groq is not configured, fall back to standard `ChatOpenAI` using `OPENAI_API_KEY`.

* **Consequences:**  
  - *Positive:* Blazing fast user experience, 10x lower latency, flexible API key management.
  - *Trade-off:* Open-source models on Groq may have minor phrasing differences compared to proprietary models.
* **Implementation:** [`main.py:L90-L121`](file:///Users/basavraj/Desktop/india-travel-agent/main.py#L90-L121) (`build_chat_model()`).

---

## ADR-006: Streaming Communication Protocol — AG-UI & Server-Sent Events (SSE)

* **Status:** Accepted  
* **Date:** October 2026  
* **Context:**  
  Users expect instant feedback. Waiting for a complete JSON response causes the UI to show an uninformative spinner for several seconds. WebSockets, while bidirectional, require stateful load balancers and complex reconnection handling.

* **Decision:**  
  Adopt the **AG-UI Protocol over Server-Sent Events (SSE)**.
  - The Python FastAPI backend exposes an SSE stream (`add_langgraph_fastapi_endpoint`).
  - Emits granular event types: `TEXT_MESSAGE_START`, `TEXT_MESSAGE_CONTENT` (token chunks), `TEXT_MESSAGE_END`, and `RUN_FINISHED`.
  - The CopilotKit Gateway and React client consume these events to render a live character-by-character typewriter effect.

* **Consequences:**  
  - *Positive:* Standard HTTP/1.1 and HTTP/2 compatibility, native browser event streaming, instant perceived latency.
  - *Trade-off:* One-way streaming from server to client (client messages sent via standard POST).
* **Implementation:** [`main.py:L174-L196`](file:///Users/basavraj/Desktop/india-travel-agent/main.py#L174-L196), [`frontend/server.ts`](file:///Users/basavraj/Desktop/india-travel-agent/frontend/server.ts).

---

## ADR-007: Multi-Runtime Extensibility — Google ADK & Gemini Support

* **Status:** Accepted  
* **Date:** October 2026  
* **Context:**  
  In modern enterprise architectures, teams should not be locked into a single AI framework. Developers need a clean way to benchmark LangGraph against alternative runtimes like Google's Agent Development Kit (ADK) using Google Gemini.

* **Decision:**  
  Provide a secondary, independent agent server in [`adk_server.py`](file:///Users/basavraj/Desktop/india-travel-agent/adk_server.py) running on port `8009`. The Gateway registers both agents simultaneously:
  - `agentId = "default"` ➔ LangGraph (:8002)
  - `agentId = "gemini"`  ➔ Google ADK (:8009)
  The frontend can switch runtimes by simply toggling `agentId` in `frontend/src/App.tsx`.

* **Consequences:**  
  - *Positive:* Zero vendor lock-in; easy side-by-side benchmarking of LangGraph vs Google ADK.
  - *Trade-off:* Requires maintaining compatibility across both agent frameworks.
* **Implementation:** [`adk_server.py`](file:///Users/basavraj/Desktop/india-travel-agent/adk_server.py), [`frontend/server.ts:L37-L46`](file:///Users/basavraj/Desktop/india-travel-agent/frontend/server.ts#L37-L46).

---

## ADR-008: Verification Strategy for Non-Deterministic AI Systems (`test_agent.py`)

* **Status:** Accepted  
* **Date:** October 2026  
* **Context:**  
  Traditional software tests rely on exact string equality (`assert result == "expected"`). Because LLMs produce non-deterministic phrasing, testing agents requires a different approach. Furthermore, heavyweight browser UI tests (Selenium / Playwright) are slow, flaky, and hard to run in lightweight CI pipelines.

* **Decision:**  
  Build a dedicated, headless programmatic test suite in [`test_agent.py`](file:///Users/basavraj/Desktop/india-travel-agent/test_agent.py) asserting **Architectural Invariants**:
  1. **Graph Compilation Invariant:** Ensures LangGraph compiles and registers middlewares without syntax errors.
  2. **Domain & Latency Invariant:** Validates response speed (< 2s) and domain accuracy for India queries.
  3. **Guardrail Invariant:** Asserts that out-of-scope prompts (e.g. quicksort algorithm) trigger refusal and regional steering.
  4. **State Retention Invariant:** Simulates multi-turn conversations sharing a `thread_id` to mathematically prove memory recall.
  5. **Live Port Connectivity Invariant:** Checks health across all 3 tiers (:3002, :4002, :8002).

* **Consequences:**  
  - *Positive:* Runs in seconds via `python test_agent.py`, catches prompt regressions, requires zero browser dependencies.
  - *Trade-off:* Tests require active API keys or credentials to execute live LLM calls.
* **Implementation:** [`test_agent.py`](file:///Users/basavraj/Desktop/india-travel-agent/test_agent.py).
