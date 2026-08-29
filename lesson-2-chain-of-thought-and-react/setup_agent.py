#!/usr/bin/env python3
"""Create the restaurant recommendation agent on Amazon Bedrock AgentCore.

This script wires together everything the CloudFormation stack deployed:

    1. Creates an AgentCore Gateway (the agent's toolbox, speaking MCP).
    2. Adds one gateway target per tool Lambda, with the tool's schema.
    3. Creates an AgentCore managed harness (the agent itself) with your
       instruction prompt. No "prepare" step is needed — once the harness
       reaches READY you can invoke it immediately.

YOUR TASK — fill in the two TODO sections below:
    - SYSTEM_PROMPT: the agent instruction (the assessed part).
    - TOOL_TARGETS: the tool descriptions and parameter schemas
      (the exact values are in the README tables).

Usage:
    python setup_agent.py [--stack-name restaurant-agent]

It reads the Lambda ARNs and role ARNs from the CloudFormation stack outputs,
and writes agent_config.json next to this script for invoke_agent.py /
cleanup.py to use.
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

REGION = "us-east-1"

# Pin the model. Do NOT rely on the harness default model — it is not
# available in the lab AWS accounts. temperature 0.0 + topK 1 make Nova's
# tool calling deterministic and reliable.
MODEL_ID = "us.amazon.nova-pro-v1:0"

# ---------------------------------------------------------------------------
# TODO 1 — write your agent instruction (system prompt). It should:
#   - describe the agent as a restaurant recommendation assistant for a
#     single city (so it never asks the user where they are),
#   - tell it to ALWAYS use the tools before making suggestions,
#   - tell it to base its recommendation only on tool results — never invent
#     restaurants, ratings, or availability,
#   - tell it to confirm availability before recommending, and to try the
#     next best option if a restaurant is unavailable.
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """\
"""

# ---------------------------------------------------------------------------
# TODO 2 — describe the tools. One gateway target per Lambda; the wiring to
# each Lambda is done for you. Fill in each tool's "description", and the
# parameter schema for search_restaurants and get_availability, using the
# tables in the README.
#
# RULE: target names may use ONLY letters and digits; tool names ONLY
# letters, digits, and underscores. Never use a dash in either: the model
# sees tools namespaced as "<targetName>___<toolName>", and a dash in that
# string breaks tool calling.
# ---------------------------------------------------------------------------
TOOL_TARGETS = [
    {
        "target_name": "cuisines",
        "lambda_output_key": "GetCuisinesFunctionArn",
        "tools": [
            {
                "name": "get_cuisines",
                "description": "",  # TODO (see README table)
                "inputSchema": {"type": "object", "properties": {}},
            }
        ],
    },
    {
        "target_name": "restaurants",
        "lambda_output_key": "SearchRestaurantsFunctionArn",
        "tools": [
            {
                "name": "search_restaurants",
                "description": "",  # TODO (see README table)
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        # TODO: add the optional "cuisine" string parameter
                        # with a good description (see README table).
                    },
                },
            }
        ],
    },
    {
        "target_name": "availability",
        "lambda_output_key": "GetAvailabilityFunctionArn",
        "tools": [
            {
                "name": "get_availability",
                "description": "",  # TODO (see README table)
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        # TODO: add the required "restaurant_id" string
                        # parameter (see README table)...
                    },
                    # TODO: ...and mark it required:
                    # "required": ["restaurant_id"],
                },
            }
        ],
    },
]

CONFIG_PATH = Path(__file__).parent / "agent_config.json"


def check_inputs():
    """Fail fast on the two classic mistakes: no prompt, dashed names."""
    if not SYSTEM_PROMPT.strip():
        sys.exit("SYSTEM_PROMPT is empty — write your agent instruction first "
                 "(TODO 1, see the README).")
    for target in TOOL_TARGETS:
        if not re.fullmatch(r"[A-Za-z0-9]+", target["target_name"]):
            sys.exit(f"Invalid target name '{target['target_name']}': gateway "
                     "target names may only contain letters and digits — the "
                     "API rejects underscores, and a dash breaks tool calling.")
        for tool in target["tools"]:
            if not re.fullmatch(r"[A-Za-z0-9_]+", tool["name"]):
                sys.exit(f"Invalid tool name '{tool['name']}': tool names may "
                         "only contain letters, digits, and underscores — "
                         "no dashes.")
            if not tool["description"].strip():
                sys.exit(f"Tool '{tool['name']}' has an empty description — "
                         "fill in TODO 2; the model relies on descriptions to "
                         "pick the right tool.")


def stack_outputs(stack_name):
    """Read the CloudFormation outputs (Lambda ARNs + role ARNs)."""
    cfn = boto3.client("cloudformation", region_name=REGION)
    try:
        stack = cfn.describe_stacks(StackName=stack_name)["Stacks"][0]
    except ClientError:
        sys.exit(f"Could not read stack '{stack_name}'. Deploy it first "
                 "(see the README) or pass --stack-name.")
    return {o["OutputKey"]: o["OutputValue"] for o in stack.get("Outputs", [])}


def create_with_retry(fn, what, attempts=3, delay=10):
    """New IAM roles can take a few seconds to propagate; retry politely."""
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except ClientError as err:
            if attempt == attempts:
                raise
            code = err.response.get("Error", {}).get("Code", "error")
            print(f"  {what} failed ({code}); retrying in {delay}s — "
                  "new IAM roles can take a moment to propagate...")
            time.sleep(delay)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stack-name", default="restaurant-agent",
                        help="CloudFormation stack you deployed (default: restaurant-agent)")
    args = parser.parse_args()

    check_inputs()

    outputs = stack_outputs(args.stack_name)
    for key in ("GatewayRoleArn", "HarnessRoleArn"):
        if key not in outputs:
            sys.exit(f"Stack output '{key}' not found — did you deploy the "
                     "template from this exercise?")

    # Two different naming rules apply (both enforced by the API):
    #   - Gateway names allow letters, digits, and dashes — no underscores.
    #   - Harness names allow letters, digits, and underscores — no dashes.
    gateway_name = f"{args.stack_name}-gw"
    harness_name = args.stack_name.replace("-", "_") + "_harness"

    acc = boto3.client("bedrock-agentcore-control", region_name=REGION)

    # -- 1. Gateway (the agent's toolbox) -----------------------------------
    print(f"Creating AgentCore Gateway '{gateway_name}'...")
    gw = create_with_retry(
        lambda: acc.create_gateway(
            name=gateway_name,
            roleArn=outputs["GatewayRoleArn"],
            protocolType="MCP",
            authorizerType="AWS_IAM",
        ),
        "create_gateway",
    )
    gateway_id = gw["gatewayId"]
    gateway_arn = gw["gatewayArn"]

    # Gateway creation is asynchronous — wait for READY before adding targets.
    deadline = time.time() + 5 * 60
    while True:
        status = acc.get_gateway(gatewayIdentifier=gateway_id).get("status")
        if status == "READY":
            break
        if status in ("FAILED", "DELETING"):
            sys.exit(f"Gateway entered status {status} — run cleanup.py and "
                     "try again.")
        if time.time() > deadline:
            sys.exit("Timed out waiting for the gateway to become READY.")
        time.sleep(5)
    print(f"  gateway ready: {gateway_arn}")

    # -- 2. One target per tool Lambda --------------------------------------
    for target in TOOL_TARGETS:
        print(f"Adding gateway target '{target['target_name']}' "
              f"-> {target['lambda_output_key']}...")
        create_with_retry(
            lambda t=target: acc.create_gateway_target(
                gatewayIdentifier=gateway_id,
                name=t["target_name"],
                targetConfiguration={
                    "mcp": {
                        "lambda": {
                            "lambdaArn": outputs[t["lambda_output_key"]],
                            "toolSchema": {"inlinePayload": t["tools"]},
                        }
                    }
                },
                credentialProviderConfigurations=[
                    {"credentialProviderType": "GATEWAY_IAM_ROLE"}
                ],
            ),
            f"create_gateway_target({target['target_name']})",
        )

    # -- 3. Managed harness (the agent itself) ------------------------------
    print(f"Creating AgentCore managed harness '{harness_name}'...")
    harness = create_with_retry(
        lambda: acc.create_harness(
            harnessName=harness_name,
            executionRoleArn=outputs["HarnessRoleArn"],
            model={
                "bedrockModelConfig": {
                    "modelId": MODEL_ID,
                    "temperature": 0.0,
                    "additionalParams": {
                        "additionalModelRequestFields": {
                            "inferenceConfig": {"topK": 1}
                        }
                    },
                }
            },
            systemPrompt=[{"text": SYSTEM_PROMPT}],
        ),
        "create_harness",
    )["harness"]
    harness_id = harness["harnessId"]
    harness_arn = harness["arn"]

    # No "prepare" step exists (or is needed): just wait for READY (~2-3 min).
    print("  waiting for the harness to become READY (usually 2-3 minutes)...")
    deadline = time.time() + 12 * 60
    while True:
        h = acc.get_harness(harnessId=harness_id)["harness"]
        status = h.get("status")
        if status == "READY":
            break
        if status in ("CREATE_FAILED", "FAILED", "DELETING"):
            reason = h.get("failureReason") or "no reason given"
            sys.exit(f"Harness entered status {status}: {reason}\n"
                     "Run 'python cleanup.py --keep-stack', wait for it to "
                     "finish, then run setup_agent.py again.")
        if time.time() > deadline:
            sys.exit("Timed out waiting for the harness to become READY.")
        print(f"    status: {status}")
        time.sleep(15)
    print(f"  harness READY: {harness_arn}")

    # -- 4. Save what invoke_agent.py / cleanup.py need ---------------------
    CONFIG_PATH.write_text(json.dumps({
        "stack_name": args.stack_name,
        "gateway_name": gateway_name,
        "gateway_id": gateway_id,
        "gateway_arn": gateway_arn,
        "harness_name": harness_name,
        "harness_id": harness_id,
        "harness_arn": harness_arn,
    }, indent=2))
    print(f"\nWrote {CONFIG_PATH.name}. Test your agent with:")
    print('  python invoke_agent.py "Find me an Italian restaurant for tonight."')


if __name__ == "__main__":
    main()
