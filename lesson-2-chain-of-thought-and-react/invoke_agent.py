#!/usr/bin/env python3
"""Send a prompt to your restaurant agent and watch the ReAct loop live.

Usage:
    python invoke_agent.py "Find me an Italian restaurant for tonight."
    python invoke_agent.py                      # uses that prompt by default
    python invoke_agent.py --session <id> "..." # continue an earlier session

The harness runs the whole agent loop server-side: it calls the model, the
model asks for tools, the harness invokes them through the AgentCore Gateway,
and the loop repeats until the model produces a final answer. This script
streams that loop and prints every tool call it sees, then checks that all
three tools were used — the proof that the answer is tool-grounded.
"""
import argparse
import json
import sys
import uuid
from pathlib import Path

import boto3

REGION = "us-east-1"
CONFIG_PATH = Path(__file__).parent / "agent_config.json"

EXPECTED_TOOLS = {"get_cuisines", "search_restaurants", "get_availability"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt", nargs="?",
                        default="Find me an Italian restaurant for tonight.")
    parser.add_argument("--session", default=None,
                        help="Reuse a session id to continue a conversation "
                             "(harness sessions are stateful).")
    args = parser.parse_args()

    if not CONFIG_PATH.exists():
        sys.exit("agent_config.json not found — run setup_agent.py first.")
    cfg = json.loads(CONFIG_PATH.read_text())

    rt = boto3.client("bedrock-agentcore", region_name=REGION)

    # Session ids must be at least 33 characters; a UUID plus a suffix is
    # a simple way to guarantee that.
    session_id = args.session or f"{uuid.uuid4()}-restaurant-session"

    print(f"session: {session_id}")
    print(f"you:     {args.prompt}\n")

    response = rt.invoke_harness(
        harnessArn=cfg["harness_arn"],
        runtimeSessionId=session_id,
        messages=[{"role": "user", "content": [{"text": args.prompt}]}],
        # Attach the gateway: this is what gives the agent its three tools.
        tools=[{
            "type": "agentcore_gateway",
            "name": "restaurant_tools",
            "config": {"agentCoreGateway": {"gatewayArn": cfg["gateway_arn"]}},
        }],
    )

    stream = response.get("stream")
    if stream is None:  # defensive: locate the event stream if the key differs
        stream = next(v for v in response.values()
                      if hasattr(v, "__iter__")
                      and not isinstance(v, (str, bytes, dict, list)))

    tool_calls = []       # tool names in the order the agent called them
    current_tool = None   # tool whose input is currently streaming
    tool_input = ""
    at_line_start = True  # so every [tool call] gets its own line

    for event in stream:
        if "contentBlockStart" in event:
            start = event["contentBlockStart"].get("start", {})
            if "toolUse" in start:
                current_tool = start["toolUse"].get("name", "?")
                tool_input = ""
        elif "contentBlockDelta" in event:
            delta = event["contentBlockDelta"].get("delta", {})
            if "text" in delta:
                print(delta["text"], end="", flush=True)
                at_line_start = delta["text"].endswith("\n")
            elif "toolUse" in delta:
                tool_input += delta["toolUse"].get("input", "")
        elif "contentBlockStop" in event:
            if current_tool is not None:
                if not at_line_start:
                    print()
                print(f"[tool call] {current_tool}({tool_input or ''})")
                at_line_start = True
                tool_calls.append(current_tool)
                current_tool = None
        elif "messageStop" in event:
            reason = event["messageStop"].get("stopReason")
            if reason == "end_turn":
                print()

    # ------------------------------------------------------------------
    # Verify grounding: did the agent really consult all three tools?
    # (Gateway tools stream namespaced as "<targetName>___<toolName>".)
    # ------------------------------------------------------------------
    called = {name.split("___")[-1] for name in tool_calls}
    print("\n--- tool calls observed:", ", ".join(sorted(called)) or "NONE")
    missing = EXPECTED_TOOLS - called
    if not missing:
        print("--- All three tools were used before the recommendation: "
              "the answer is tool-grounded.")
    elif args.session:
        print("--- not called this turn:", ", ".join(sorted(missing)))
        print("--- Continued session: the harness remembers earlier turns, so "
              "the agent may reuse earlier tool results instead of calling "
              "the tools again. Judge the three-tool check on the first turn "
              "of a fresh session.")
    else:
        print("--- MISSING:", ", ".join(sorted(missing)))
        print("--- The agent skipped tools — tighten your instruction prompt "
              "so every recommendation is grounded in tool results.")


if __name__ == "__main__":
    main()
