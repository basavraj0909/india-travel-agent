/**
 * 🎙️ The Gateway — Node.js + Hono API Router (Port 4002)
 *
 * ============================================================================
 * BEGINNER DEVELOPER ARCHITECTURE GUIDE:
 * ============================================================================
 *
 * 1. What is this file?
 *    This file runs a lightweight Node.js web server using the Hono framework.
 *    It acts as the single central "API Gateway" (Traffic Controller) between the
 *    React frontend UI and your backend Python AI agents.
 *
 * 2. Why don't we connect React directly to Python (Port 8002)?
 *    - Security & Auth: Keeps backend server URLs and potential API tokens hidden.
 *    - Protocol Normalization: React doesn't need to know if the backend is written
 *      in Python, Go, or Java, or whether it uses LangGraph or Google ADK.
 *    - Multi-Agent Routing: If you have 5 different agents (e.g. Travel, Flights,
 *      Hotels, Weather), the frontend simply calls `/api/copilotkit`, and this
 *      gateway inspects `agentId` to route traffic to the correct backend server!
 *
 * 3. Port Mapping:
 *    - Listens on: http://localhost:4002
 *    - Exposes endpoint: /api/copilotkit
 *    - Routes 'default' requests to Python LangGraph: http://127.0.0.1:8002
 */

import { CopilotRuntime, createCopilotEndpoint } from "@copilotkit/runtime/v2";
import { HttpAgent } from "@ag-ui/client";
import { LangGraphHttpAgent } from "@copilotkit/runtime/langgraph";
import { serve } from "@hono/node-server";

// 1. Define agent remote endpoints
const langGraphAgent = new LangGraphHttpAgent({
  url: process.env.LANGGRAPH_DEPLOYMENT_URL || "http://127.0.0.1:8002",
});

const adkAgent = new HttpAgent({
  url: process.env.ADK_AGENT_URL || "http://127.0.0.1:8009",
});

// 2. Register agents in the CopilotRuntime registry
const runtime = new CopilotRuntime({
  agents: {
    default: langGraphAgent, // Used when agentId="default" or omitted
    gemini: adkAgent,        // Used when agentId="gemini"
  },
});

const frontendOrigins = (process.env.FRONTEND_ORIGINS ?? "")
  .split(",")
  .map((origin) => origin.trim())
  .filter(Boolean);

const allowedOrigins =
  frontendOrigins.length > 0
    ? frontendOrigins
    : ["http://localhost:3002", "http://127.0.0.1:3002"];

// 3. Expose the /api/copilotkit endpoint on port 4002
const app = createCopilotEndpoint({
  runtime,
  basePath: "/api/copilotkit",
  cors: {
    origin: (origin) => (allowedOrigins.includes(origin) ? origin : null),
  },
});

const port = Number(process.env.PORT ?? 4002);

serve({ fetch: app.fetch, hostname: "0.0.0.0", port }, () => {
  console.log(`CopilotKit API server listening on port ${port}`);
});
