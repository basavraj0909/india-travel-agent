/**
 * 🎙️ Stop 1: The User Interface — Where It All Begins
 *
 * This React component renders the complete chat experience using CopilotKit.
 *
 * Key Concepts:
 * - agentId: Tells the CopilotRuntime gateway which backend agent to route to.
 *   - "default" -> LangGraph Agent on port 8002 (Groq / OpenAI)
 *   - "gemini"  -> Google ADK Agent on port 8009 (Google Gemini)
 *
 * - <CopilotChat />: Out-of-the-box UI component that handles:
 *   - Chat bubbles and message history display
 *   - Auto-scrolling and live token streaming character-by-character
 *   - Generative UI component rendering
 */

import { CopilotChat } from "@copilotkit/react-core/v2";

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
