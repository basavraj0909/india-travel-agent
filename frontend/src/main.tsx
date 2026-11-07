
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { CopilotKit } from "@copilotkit/react-core/v2";
import "@copilotkit/react-core/v2/styles.css";
import "./globals.css";
import App from "./App";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <main className="h-screen w-screen">
      <CopilotKit
        runtimeUrl={
          import.meta.env.VITE_COPILOTKIT_RUNTIME_URL || "/api/copilotkit"
        }
        useSingleEndpoint={false}
      >
        <App />
      </CopilotKit>
    </main>
  </StrictMode>,
);
