# System Architecture & Debugging Guide

Welcome to the internal engineering guide for this CopilotKit + Agentic Backend application. This document details the architectural design, end-to-end data flow, backend implementation, and common debugging workflows.

---

## 1. High-Level Architecture (3-Tier Design)

Unlike traditional web applications where a frontend either calls an API or directly connects to an LLM, this system implements an **Enterprise Agentic Architecture**:

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Frontend Tier (React + Vite)                             │
│    URL: http://localhost:3002                               │
│    Role: Chat UI, message rendering, generative UI tools    │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTP Proxy (/api/copilotkit)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Agent Gateway Tier (CopilotKit Runtime / Node.js + Hono) │
│    URL: http://localhost:4002                               │
│    Role: Multi-agent routing, protocol bridge, agent discovery│
└───────────────┬─────────────────────────────┬───────────────┘
                │                             │
   agentId="default"                          agentId="gemini"
   AG-UI Protocol (SSE/POST)                  AG-UI Protocol (SSE/POST)
                │                             │
                ▼                             ▼
┌───────────────────────────────┐ ┌───────────────────────────┐
│ 3A. Python Backend: LangGraph │ │ 3B. Python Backend: ADK   │
│     URL: http://localhost:8002│ │     URL: http://localhost:8009│
│     File: main.py             │ │     File: adk_server.py   │
│     Model: Groq / OpenAI      │ │     Model: Google Gemini  │
└───────────────┬───────────────┘ └───────────┬───────────────┘
                │                             │
                ▼                             ▼
        Groq / OpenAI API             Google Gemini API
```

### 🔌 Port Mapping & Service Breakdown

|     Port     |     Service      |     Tech Stack               | Entry Point |
| :---:        | :---             | :---                         | :---      |
| **`3002`** | 🌐 **Frontend UI** | React 19 + Vite + TailwindCSS | [`frontend/src/App.tsx`](frontend/src/App.tsx) |
| **`4002`** | 🚪 **Agent Gateway** | Node.js + Hono + `@copilotkit/runtime` | [`frontend/server.ts`](frontend/server.ts) |
| **`8002`** | 🧠 **LangGraph Agent** | Python 3.12 + FastAPI + LangGraph | [`main.py`](main.py) |
| **`8009`** | 🤖 **Google ADK Agent** | Python 3.12 + FastAPI + Google GenAI | [`adk_server.py`](adk_server.py) |

#### Service Responsibilities:

- **🌐 Frontend Web App (`:3002`)**
  - **Role**: Renders the chat interface, streams response tokens in real-time, and displays Generative UI components.
  - **Proxy**: Automatically forwards all `/api/copilotkit` traffic to the gateway on port `4002`.

- **🚪 Agent Gateway / CopilotKit Runtime (`:4002`)**
  - **Role**: Multi-agent router and protocol translator. Reads `agentId` from the frontend and forwards to the target Python backend:
    - `agentId = "default"` ➔ routes to LangGraph (`http://localhost:8002`)
    - `agentId = "gemini"`  ➔ routes to ADK (`http://localhost:8009`)

- **🧠 LangGraph Python Agent (`:8002`)**
  - **Role**: Handles conversation logic and multi-turn session memory using `MemorySaver`.
  - **Models**: Supported via **Groq** (`openai/gpt-oss-120b`) or **OpenAI** (`gpt-4.1`).

- **🤖 Google ADK Python Agent (`:8009`)**
  - **Role**: Runs Google's Agent Development Kit with stateful in-memory conversation services.
  - **Models**: Supported via **Google Gemini** (`gemini-2.0-flash`).

---

## 2. End-to-End Chat & Response Lifecycle

Here is what happens under the hood when a user types `"Hello"` into the chat box:

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant UI as React App (:3002)
    participant GW as CopilotKit Runtime (:4002)
    participant PY as FastAPI Agent (:8009 or :8002)
    participant LLM as Google Gemini / OpenAI

    User->>UI: Types "Hello" & hits Enter
    UI->>GW: POST /api/copilotkit/agent/{agentId}/connect
    Note over GW: Looks up agentId in agents map (server.ts)
    GW->>PY: POST / (AG-UI protocol payload with message history & session)
    Note over PY: Session manager loads history & constructs model prompt
    PY->>LLM: Stream request (generate_content_stream / astream)
    LLM-->>PY: Yields response chunks / tokens
    Note over PY: EventTranslator transforms raw chunks into AG-UI SSE events
    PY-->>GW: Server-Sent Events stream (TEXT_MESSAGE_START, TEXT_MESSAGE_CONTENT...)
    GW-->>UI: Forwards SSE stream in real-time
    UI-->>User: Renders characters streaming into the chat bubble
    PY-->>GW: Emits TEXT_MESSAGE_END & RUN_FINISHED
```

### Why AG-UI Protocol?
Traditional REST APIs use Request-Response (`{"reply": "..."}`). Agents require a streaming protocol because:
1. **Token Streaming**: Users expect instant feedback rather than waiting 5–10 seconds for the entire response.
2. **Tool Execution Events**: The backend must inform the frontend when a tool is running (e.g. `TOOL_CALL_START`).
3. **Generative UI**: Agents can stream structured payloads that render interactive React components (charts, forms).
4. **Human-in-the-Loop**: The agent can yield an `INTERRUPT` event requiring user confirmation before proceeding.

---

### 2.1 Code-Level Trace of One Real Message

The diagram above is the mental model. This section is the **ground truth**, captured by hitting the running backend directly with `curl` (see [§5.8](#8-reproduce-the-full-event-stream-with-curl) for the command).

**Input:** `"Name one fort in Jaipur in 5 words."`
**Output:** `"Amber Fort of Jaipur, Rajasthan 🙏"`

#### Step ① — Browser: where the request is born
[`frontend/src/main.tsx`](frontend/src/main.tsx) wraps the app with a **relative** runtime URL — no host, no port:
```tsx
<CopilotKit runtimeUrl="/api/copilotkit" useSingleEndpoint={false}>
```
[`frontend/src/App.tsx`](frontend/src/App.tsx) renders `<CopilotChat agentId="default" />`. On Enter, CopilotChat builds an AG-UI payload. The `threadId` is generated client-side and **reused for the whole session** — it is the key that memory hangs on:
```json
{
  "threadId": "walkthrough-demo-2",
  "runId": "run-2",
  "messages": [{ "id": "m1", "role": "user", "content": "Name one fort in Jaipur in 5 words." }],
  "tools": [], "context": [], "state": {}, "forwardedProps": {}
}
```

#### Step ② — Vite proxy: why there is no CORS config anywhere
[`frontend/vite.config.ts`](frontend/vite.config.ts) → `proxy: { "/api/copilotkit": "http://127.0.0.1:4002" }`
The browser believes it is talking to `:3002`; Vite forwards to `:4002` server-side.

#### Step ③ — Gateway: `agentId` → backend URL
[`frontend/server.ts`](frontend/server.ts) does a dictionary lookup — `agents.default` → `LangGraphHttpAgent({ url: "http://127.0.0.1:8002" })` — then opens an SSE stream to Python and **pipes every event straight back** to the browser. It adds nothing; it is a pure router.

#### Step ④ — FastAPI + LangGraph: the graph is 4 nodes, not 1
[`main.py`](main.py) → `add_langgraph_fastapi_endpoint(app, agent, path="/")` parses the payload, loads the `thread_id` from `MemorySaver`, and runs the graph. The `STEP_STARTED` events reveal the real node sequence:

| Step | Node | Added by | Purpose |
| :--- | :--- | :--- | :--- |
| 1 | `CopilotKitMiddleware.before_agent` | `middleware=[CopilotKitMiddleware()]` | Injects a system msg `App Context: {"thread_id": …}` plus any frontend actions/context |
| 2 | `model` | `create_agent(model=…)` | **The LLM call** |
| 3 | `CopilotKitMiddleware.after_model` | middleware | Inspects output for tool calls / generative-UI payloads |
| 4 | `CopilotKitMiddleware.after_agent` | middleware | Finalizes state for the frontend |

#### Step ⑤ — What the `model` node actually sends to Groq
The `TEXT_MESSAGE_END` event echoes the full `input`. This is **proof** that `system_prompt=` in `create_agent()` is prepended as message `[0]` on every call — it is the entire isolation mechanism:
```
[0] system : "You are 'YatriAI' … STRICT SCOPE & GUARDRAILS … 'REGRET! 🙏 …'"   ← INDIA_TRAVEL_SYSTEM_PROMPT
[1] human  : "Name one fort in Jaipur in 5 words."
[2] system : "App Context: { \"thread_id\": \"walkthrough-demo-2\" }"              ← injected by before_agent
```
Usage from the same event: `model=openai/gpt-oss-120b`, `inputTokens=553` (mostly the prompt), `outputTokens=153` of which `reasoningTokens=136` — only ~17 tokens became visible text.

#### Step ⑥ — The SSE stream, filtered to what matters
The raw stream also carries one `{"type":"RAW", …}` event per internal LangChain callback — the browser ignores those. The events `<CopilotChat>` acts on:
```json
{"type":"RUN_STARTED","threadId":"walkthrough-demo-2","runId":"run-2"}
{"type":"STEP_STARTED","stepName":"CopilotKitMiddleware.before_agent"}
{"type":"STEP_FINISHED","stepName":"CopilotKitMiddleware.before_agent"}
{"type":"STEP_STARTED","stepName":"model"}
{"type":"TEXT_MESSAGE_START","messageId":"lc_run--01a15e06-…"}
{"type":"TEXT_MESSAGE_CONTENT","messageId":"lc_run--01a15e06-…","delta":"Amber"}
{"type":"TEXT_MESSAGE_CONTENT","messageId":"lc_run--01a15e06-…","delta":" Fort"}
{"type":"TEXT_MESSAGE_CONTENT","messageId":"lc_run--01a15e06-…","delta":" of"}
{"type":"TEXT_MESSAGE_CONTENT","messageId":"lc_run--01a15e06-…","delta":" Jaipur,"}
{"type":"TEXT_MESSAGE_CONTENT","messageId":"lc_run--01a15e06-…","delta":" Rajasthan"}
{"type":"TEXT_MESSAGE_CONTENT","messageId":"lc_run--01a15e06-…","delta":" 🙏"}
{"type":"TEXT_MESSAGE_END","messageId":"lc_run--01a15e06-…"}
{"type":"STEP_FINISHED","stepName":"model"}
{"type":"STEP_STARTED","stepName":"CopilotKitMiddleware.after_model"}
{"type":"STEP_FINISHED","stepName":"CopilotKitMiddleware.after_model"}
{"type":"STEP_STARTED","stepName":"CopilotKitMiddleware.after_agent"}
{"type":"STEP_FINISHED","stepName":"CopilotKitMiddleware.after_agent"}
{"type":"RUN_FINISHED","threadId":"walkthrough-demo-2","runId":"run-2","usage":[{"model":"openai/gpt-oss-120b","inputTokens":553,"outputTokens":153,"reasoningTokens":136}]}
```
`<CopilotChat>` appends each `delta` to the bubble whose `messageId` matches — that is the entire typewriter effect.

#### Step ⑦ — Checkpoint
After `RUN_FINISHED`, `MemorySaver` persists the full message list under `thread_id`. The next message on the same thread will have `"Name one fort…"` + `"Amber Fort…"` pre-loaded before the LLM sees it.

---


## 3. Backend Code Breakdown

### `adk_server.py` (Google ADK + Gemini)

```python
import os
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from ag_ui_adk import ADKAgent, add_adk_fastapi_endpoint
from google.adk.agents import LlmAgent

# 1. Load keys from .env
load_dotenv()

# 2. Define the core LLM Agent
gemini_agent = LlmAgent(
    name="assistant",
    model="gemini-3.8-flash",       # or "gemini-2.0-flash" for high capacity
    instruction="Be helpful and fun!",
)

# 3. Wrap with Stateful Session & Memory management
adk_agent = ADKAgent(
    adk_agent=gemini_agent,
    app_name="demo_app",
    user_id="demo_user",
    session_timeout_seconds=3600,   # Conversation memory persists for 1 hour
    use_in_memory_services=True,    # In-memory chat history
)

# 4. Bind the AG-UI SSE endpoint to FastAPI
app_adk = FastAPI()
add_adk_fastapi_endpoint(app_adk, adk_agent, path="/")

# 5. Start the ASGI Server
if __name__ == "__main__":
    uvicorn.run(app_adk, host="0.0.0.0", port=8009)
```

**Key Takeaways:**
- `LlmAgent`: Defines model identity, system prompt, and capabilities.
- `ADKAgent`: Handles conversation state. Without this, the model would forget previous messages.
- `add_adk_fastapi_endpoint`: Exposes an AG-UI compatible endpoint on `/` that streams Server-Sent Events.

---

### `main.py` (LangGraph + OpenAI)

```python
from fastapi import FastAPI
import uvicorn
from ag_ui_langgraph import add_langgraph_fastapi_endpoint
from copilotkit import CopilotKitMiddleware, LangGraphAGUIAgent
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver

# 1. Memory checkpointer for multi-turn history
checkpointer = MemorySaver()

# 2. LangChain model with CopilotKit middleware
model = ChatOpenAI(model="gpt-4.1")

# 3. Create the LangGraph graph
graph = create_agent(
    model=model,
    tools=[],
    middleware=[CopilotKitMiddleware()],
    checkpointer=checkpointer,
    system_prompt="You are a helpful assistant..."
)

# 4. AG-UI wrapper for LangGraph
agent = LangGraphAGUIAgent(
    name="lesson2_agent",
    description="Lesson 2 chart agent",
    graph=graph,
)

# 5. Mount on FastAPI
app = FastAPI()
add_langgraph_fastapi_endpoint(app=app, agent=agent, path="/")
```

---

### `frontend/server.ts` (CopilotKit Node Runtime)

```typescript
import { CopilotRuntime, createCopilotEndpoint } from "@copilotkit/runtime/v2";
import { HttpAgent } from "@ag-ui/client";
import { LangGraphHttpAgent } from "@copilotkit/runtime/langgraph";
import { serve } from "@hono/node-server";

// 1. Define agent remote endpoints
const langGraphAgent = new LangGraphHttpAgent({
  url: process.env.LANGGRAPH_DEPLOYMENT_URL || "http://localhost:8002",
});

const adkAgent = new HttpAgent({
  url: process.env.ADK_AGENT_URL || "http://localhost:8009",
});

// 2. Register agents in the CopilotRuntime registry
const runtime = new CopilotRuntime({
  agents: {
    default: langGraphAgent, // Used when agentId="default" or omitted
    gemini: adkAgent,        // Used when agentId="gemini"
  },
});

// 3. Expose /api/copilotkit endpoint on port 4002
const app = createCopilotEndpoint({ runtime, basePath: "/api/copilotkit" });
serve({ fetch: app.fetch, port: 4002 });
```

---

## 4. How to Switch Between Agents

To toggle between OpenAI and Gemini:

1. Open [`frontend/src/App.tsx`](file:///Users/basavraj/Desktop/PERSONAL_DEV/frontend/src/App.tsx):
   - For **Gemini**: `export const agentId = "gemini";`
   - For **OpenAI**: `export const agentId = "default";`

2. Run the corresponding backend terminal:
   - For **Gemini**: `python adk_server.py` (Port 8009)
   - For **OpenAI**: `python main.py` (Port 8002)

---

## 5. Troubleshooting & Debugging Reference

### 1. `AggregateError [ECONNREFUSED]` on `/api/copilotkit/agent/...`
- **Symptom**: Frontend shows proxy error connecting to port 8002 or 8009.
- **Root Cause**: The Python backend matching `agentId` is not running.
- **Fix**: Check `App.tsx`:
  - If `agentId = "gemini"`, start `python adk_server.py`.
  - If `agentId = "default"`, start `python main.py`.

### 2. `Error code: 429 - insufficient_quota / credit_balance_exhausted`
- **Symptom**: OpenAI API returns 429 when sending a message.
- **Root Cause**: OpenAI developer account has $0 prepaid balance.
- **Fix**: Either add $5 at [platform.openai.com/billing](https://platform.openai.com/settings/organization/billing/) or switch to Gemini (`agentId = "gemini"`).

### 3. `ImportError: cannot import name 'ThinkingStartEvent' from 'ag_ui.core'`
- **Symptom**: `adk_server.py` fails on startup.
- **Root Cause**: `ag-ui-protocol 1.0.0` renamed `Thinking*` events to `Reasoning*`. `ag_ui_adk` expects `<1.0.0`.
- **Fix**: Run `pip install "ag-ui-protocol<1.0.0"`.

### 4. `404 Not Found: model models/gemini-2.5-flash is no longer available`
- **Symptom**: Google API rejects the model name.
- **Root Cause**: The course notebook specified a deprecated model.
- **Fix**: In `adk_server.py`, change model to `"gemini-3.8-flash"` or `"gemini-2.0-flash"`.

### 5. `503 Service Unavailable: This model is currently experiencing high demand`
- **Symptom**: Temporary capacity error from Google on free tier.
- **Fix**:
  1. Wait 5–10 seconds and retry.
  2. Or change model in `adk_server.py` to `model="gemini-2.0-flash"`.

### 6. `Port already in use` error
- **Fix**: Run in terminal to kill processes holding the ports:
  ```bash
  # Check what is using the port
  lsof -ti :3002 -ti :4002 -ti :8002 -ti :8009 | xargs kill -9
  ```

### 7. How to inspect traffic in Browser DevTools
- Open Chrome DevTools (`Cmd + Option + I` or `F12`).
- Go to the **Network** tab.
- Filter by `copilotkit`.
- Look at the `connect` request: under **EventStream**, you can watch live AG-UI protocol events arriving chunk-by-chunk!

### 8. Reproduce the full event stream with `curl`
Bypass the browser **and** the gateway and talk to the Python agent directly. This is how the trace in [§2.1](#21-code-level-trace-of-one-real-message) was captured.

```bash
curl -s -N -X POST http://127.0.0.1:8002/ \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "threadId": "debug-1",
    "runId": "run-1",
    "messages": [{"id":"m1","role":"user","content":"Name one fort in Jaipur in 5 words."}],
    "tools": [], "context": [], "state": {}, "forwardedProps": {}
  }'
```

Filter out the noisy `RAW` events and show only the ones the UI acts on:
```bash
curl -s -N -X POST http://127.0.0.1:8002/ \
  -H "Content-Type: application/json" -H "Accept: text/event-stream" \
  -d '{"threadId":"debug-1","runId":"run-1","messages":[{"id":"m1","role":"user","content":"Name one fort in Jaipur in 5 words."}],"tools":[],"context":[],"state":{},"forwardedProps":{}}' \
  | grep -E '"type":"(RUN_|STEP_|TEXT_MESSAGE_)' \
  | sed 's/^data: //'
```

**Test memory:** send a second request with the **same** `threadId` and a question like `"What did I just ask you?"` — the agent will answer from the `MemorySaver` checkpoint.

**Test guardrails:** change `content` to `"Write a quicksort in Python"` and watch the `TEXT_MESSAGE_CONTENT` deltas spell out the refusal.

