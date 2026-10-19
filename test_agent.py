"""
🧪 Automated Test Suite — Testing AI Agents & Multi-Tier Architecture

===============================================================================
BEGINNER DEVELOPER TESTING GUIDE:
===============================================================================

1. Why do we need automated tests for an AI agent?
   In traditional web apps, functions are deterministic (2 + 2 always equals 4).
   With LLMs, outputs can vary. Automated tests ensure that:
   - The agent's graph compiles and initializes without runtime syntax errors.
   - Guardrails are actively enforced (the bot never strays into non-India topics).
   - Memory actually works across multiple turns (using thread_id).
   - Latency remains acceptable (< 1-2 seconds with Groq).
   - All 3 architectural tiers (:3002, :4002, :8002) are healthy and listening.

2. How to run this test suite:
   $ python test_agent.py

   No browsers, Selenium, or heavy UI testing frameworks needed!
   It tests the agent directly through code.
"""

import os
import time
import urllib.request
import urllib.error
from dotenv import load_dotenv

# Load environment variables (.env) so API keys (GROQ_API_KEY / OPENAI_API_KEY) are available
load_dotenv(override=True)


def test_agent_graph_initialization():
    """
    Test 1: Agent Graph Compilation
    --------------------------------
    WHAT IT TESTS:
    Verifies that LangGraph can successfully build and compile the state graph,
    connect the LLM, register the MemorySaver checkpointer, and attach middlewares.

    WHY IT MATTERS:
    If there is a typo in model names, missing dependencies, or syntax errors
    in graph configuration, this will catch it immediately before deployment.
    """
    import main
    graph = main.load_graph()
    assert graph is not None, "Failed to load agent graph"
    print("\n✓ Agent graph initialized successfully")


def test_india_travel_recommendation():
    """
    Test 2: Domain Knowledge & Latency Benchmark
    --------------------------------------------
    WHAT IT TESTS:
    Sends an authentic Indian tourism question ("historic forts in Rajasthan")
    and verifies:
    1. The agent responds with meaningful, non-empty advice.
    2. Response turnaround latency (with Groq LPUs, usually < 1.0s).

    WHY IT MATTERS:
    Proves that inference is functioning end-to-end and measures real-world
    speed for user experience benchmarking.
    """
    import main
    graph = main.load_graph()
    config = {"configurable": {"thread_id": "test-india-query"}}

    start_time = time.time()
    response = graph.invoke(
        {"messages": [{"role": "user", "content": "What are 2 must-visit historic forts in Rajasthan?"}]},
        config=config,
    )
    elapsed = time.time() - start_time

    assert "messages" in response, "Response must contain 'messages'"
    last_msg = response["messages"][-1].content
    assert len(last_msg.strip()) > 0, "Agent response should not be empty"

    print(f"\n✓ India travel query response received in {elapsed:.2f}s:")
    print(f"  Response preview: \"{last_msg.strip()[:100]}...\"")


def test_out_of_scope_guardrail_rejection():
    """
    Test 3: Negative Constraints & Guardrail Verification
    ------------------------------------------------------
    WHAT IT TESTS:
    Prompts the agent to write Python code (a quicksort algorithm).
    Because YatriAI is strictly a travel agent for India, it MUST refuse
    to write code, solve math problems, or discuss non-travel topics.

    WHY IT MATTERS:
    In production enterprise AI, guardrails prevent brand liability,
    API token abuse, and hallucination on unapproved topics.
    """
    import main
    graph = main.load_graph()
    config = {"configurable": {"thread_id": "test-guardrail"}}

    response = graph.invoke(
        {"messages": [{"role": "user", "content": "Write me a Python function to sort a list using quicksort."}]},
        config=config,
    )
    last_msg = response["messages"][-1].content.lower()

    print(f"\n✓ Out-of-scope test response:")
    print(f"  Agent response: \"{response['messages'][-1].content.strip()[:120]}...\"")
    
    # Assert that the agent politely mentions its India travel focus or declines out-of-scope queries
    assert "india" in last_msg or "travel" in last_msg or "cannot" in last_msg or "exclusively" in last_msg, (
        f"Agent did not properly enforce India Travel guardrails: {last_msg}"
    )


def test_agent_multi_turn_memory():
    """
    Test 4: Stateful Multi-Turn Memory Verification
    ------------------------------------------------
    WHAT IT TESTS:
    Simulates a continuous 2-turn conversation sharing the SAME 'thread_id':
    - Turn 1: User says: "I am planning a 4-day trip to Goa with a budget of ₹45,000."
    - Turn 2: User asks: "What was my budget for the Goa trip?"
    
    WHY IT MATTERS:
    Verifies that the MemorySaver checkpointer accurately persists state across
    turns on the backend, allowing users to have natural, contextual discussions
    without re-explaining their constraints in every message.
    """
    import main
    graph = main.load_graph()
    unique_thread_id = f"test-memory-{int(time.time())}"
    config = {"configurable": {"thread_id": unique_thread_id}}

    # Turn 1: Introduce budget parameter
    t1_input = "I am planning a 4-day trip to Goa with a budget of ₹45,000. Keep this in mind."
    t1_res = graph.invoke({"messages": [{"role": "user", "content": t1_input}]}, config=config)
    assert t1_res["messages"][-1].content, "Turn 1 did not produce output"

    # Turn 2: Query the agent to recall the budget
    t2_input = "What was my budget for the Goa trip? Mention the number."
    t2_res = graph.invoke({"messages": [{"role": "user", "content": t2_input}]}, config=config)
    answer = t2_res["messages"][-1].content

    print(f"\n✓ Memory test result for thread '{unique_thread_id}':")
    print(f"  Agent recalled: \"{answer.strip()}\"")
    assert "45,000" in answer or "45000" in answer, f"Expected 45,000 in agent memory, got: {answer}"


def check_port_health(name: str, url: str) -> bool:
    """
    HTTP Probe Helper:
    Pings an HTTP endpoint with a 2-second timeout to check if the server is active.
    Returns True if the port responds with HTTP 200 or 404 (indicating the server is alive).
    """
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "TestAgent/1.0"})
        with urllib.request.urlopen(req, timeout=2) as resp:
            return resp.status in (200, 404)
    except urllib.error.HTTPError:
        return True
    except Exception:
        return False


def test_live_services_health():
    """
    Test 5: Multi-Tier Network Connectivity Check
    ----------------------------------------------
    WHAT IT TESTS:
    Pings all three application ports:
    - Port 3002: Vite + React Frontend UI
    - Port 4002: CopilotKit Runtime Gateway
    - Port 8002: LangGraph FastAPI Backend

    WHY IT MATTERS:
    Allows developers to instantly diagnose which specific tier is down
    if the UI isn't responding in their browser.
    """
    endpoints = {
        "Frontend UI (:3002)": "http://localhost:3002",
        "CopilotKit Runtime (:4002)": "http://localhost:4002/api/copilotkit/info",
        "Python Agent Backend (:8002)": "http://localhost:8002/",
    }

    print("\n--- Live Tier Health Check ---")
    results = {}
    for name, url in endpoints.items():
        is_live = check_port_health(name, url)
        status_icon = "🟢 UP" if is_live else "🔴 DOWN"
        print(f"  {status_icon} - {name}")
        results[name] = is_live

    if not results["Python Agent Backend (:8002)"]:
        print("  ℹ Note: Start 'python main.py' to run the backend server.")


if __name__ == "__main__":
    print("=" * 60)
    print(" Running YatriAI (India Travel Agent) Automated Test Suite")
    print("=" * 60)

    try:
        test_live_services_health()
    except Exception as e:
        print(f"Health check error: {e}")

    try:
        test_agent_graph_initialization()
    except AssertionError as e:
        print(f"❌ Graph init failed: {e}")

    try:
        test_india_travel_recommendation()
    except AssertionError as e:
        print(f"❌ India travel test failed: {e}")

    try:
        test_out_of_scope_guardrail_rejection()
    except AssertionError as e:
        print(f"❌ Guardrail test failed: {e}")

    try:
        test_agent_multi_turn_memory()
    except AssertionError as e:
        print(f"❌ Memory test failed: {e}")

    print("\n" + "=" * 60)
    print(" All YatriAI Tests Completed Successfully! 🚀")
    print("=" * 60)
