/**
 * 🎙️ The User Interface — React 19 + CopilotKit Chat Client (Port 3002)
 *
 * ============================================================================
 * BEGINNER DEVELOPER ARCHITECTURE GUIDE:
 * ============================================================================
 *
 * 1. What is this component?
 *    This React component is the primary user-facing interface for YatriAI.
 *    It uses CopilotKit's pre-built `<CopilotChat />` component to render
 *    a full-featured conversational interface.
 *
 * 2. What does <CopilotChat /> handle automatically?
 *    - Real-Time Token Streaming: Renders tokens character-by-character as they
 *      arrive from Groq/OpenAI over Server-Sent Events (SSE).
 *    - Auto-scrolling: Kept pinned to the bottom during live output.
 *    - Message History: Displays human and AI bubbles with timestamps.
 *    - Session Management: Manages thread IDs so the agent remembers multi-turn context.
 *
 * 3. The `agentId` prop:
 *    Tells the CopilotRuntime Gateway (`:4002`) which backend agent to route messages to:
 *    - "default" -> YatriAI LangGraph Agent (Port 8002, Groq / OpenAI)
 *    - "gemini"  -> Google ADK Agent (Port 8009, Gemini)
 */

import { CopilotChat } from "@copilotkit/react-core/v2";

// Choose active agent backend: "default" (LangGraph :8002) or "gemini" (ADK :8009)
export const agentId = "default";

export default function App() {
  return (
    <div className="flex flex-col h-screen bg-slate-50 text-slate-800">
      {/* Brand Header with Indian Flag Gradient Accent */}
      <header className="bg-gradient-to-r from-orange-600 via-amber-500 to-emerald-600 text-white shadow-md px-6 py-4 flex items-center justify-between z-10">
        <div className="flex items-center space-x-3">
          <span className="text-3xl">🪔</span>
          <div>
            <h1 className="text-xl font-bold tracking-tight">YatriAI (यात्री AI)</h1>
            <p className="text-xs text-orange-100 font-medium">Your Incredible India Travel Companion 🇮🇳</p>
          </div>
        </div>
        <div className="hidden sm:flex items-center space-x-3 text-xs bg-white/20 backdrop-blur-sm px-4 py-1.5 rounded-full font-medium shadow-inner">
          <span>🏰 Royal Heritage</span>
          <span>•</span>
          <span>🌴 Backwaters</span>
          <span>•</span>
          <span>🏔️ Himalayas</span>
          <span>•</span>
          <span>🚆 IRCTC Tips</span>
        </div>
      </header>

      {/* Main Chat Interface */}
      <main className="flex-1 flex flex-col overflow-hidden">
        <CopilotChat agentId={agentId} />
      </main>
    </div>
  );
}
