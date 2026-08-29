#!/usr/bin/env python3
"""Delete everything this exercise created.

Usage:
    python cleanup.py                      # delete agent + gateway + stack
    python cleanup.py --keep-stack         # keep the Lambdas/roles: use this
                                           # to iterate — cleanup, edit your
                                           # prompt, run setup_agent.py again
    python cleanup.py --stack-name <name>  # if you used a custom stack name

Deletes, in order: the managed harness, the gateway targets, the gateway,
and (unless --keep-stack) the CloudFormation stack.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

REGION = "us-east-1"
CONFIG_PATH = Path(__file__).parent / "agent_config.json"


def attempt(what, fn):
    """Run one deletion step; report and continue on failure."""
    try:
        fn()
        print(f"  deleted {what}")
        return True
    except ClientError as err:
        code = err.response.get("Error", {}).get("Code", "")
        if code in ("ResourceNotFoundException", "NotFoundException"):
            print(f"  {what}: already gone")
            return True
        print(f"  WARNING: could not delete {what}: {err}")
        return False


def find_ids(acc, stack_name):
    """If agent_config.json is missing, find our resources by name."""
    harness_name = stack_name.replace("-", "_") + "_harness"
    gateway_name = f"{stack_name}-gw"
    harness_id = gateway_id = None
    try:
        for h in acc.list_harnesses().get("harnesses", []):
            if h.get("harnessName") == harness_name:
                harness_id = h.get("harnessId")
        for g in acc.list_gateways().get("items", []):
            if g.get("name") == gateway_name:
                gateway_id = g.get("gatewayId") or g.get("gatewayIdentifier")
    except ClientError as err:
        print(f"  could not list AgentCore resources ({err}); "
              "if anything is left, delete it in the AgentCore console.")
    return harness_id, gateway_id


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stack-name", default="restaurant-agent")
    parser.add_argument("--keep-stack", action="store_true",
                        help="Keep the CloudFormation stack (Lambdas + roles) "
                             "so you can re-run setup_agent.py quickly.")
    args = parser.parse_args()

    cfg = {}
    if CONFIG_PATH.exists():
        cfg = json.loads(CONFIG_PATH.read_text())

    stack_name = cfg.get("stack_name", args.stack_name)
    acc = boto3.client("bedrock-agentcore-control", region_name=REGION)

    harness_id = cfg.get("harness_id")
    gateway_id = cfg.get("gateway_id")
    if not harness_id and not gateway_id:
        harness_id, gateway_id = find_ids(acc, stack_name)

    all_ok = True

    # -- 1. Harness (the agent) ---------------------------------------------
    if harness_id:
        all_ok &= attempt(f"harness {harness_id}",
                          lambda: acc.delete_harness(harnessId=harness_id,
                                                     deleteManagedMemory=True))
        # Wait until it is really gone before touching the gateway.
        deadline = time.time() + 5 * 60
        while time.time() < deadline:
            try:
                acc.get_harness(harnessId=harness_id)
                time.sleep(10)
            except ClientError:
                break
        # The harness's managed session memory (named after the harness) is
        # deleted asynchronously and can take a couple of minutes. Wait for
        # it: recreating a harness with the same name fails with
        # "Memory ... already exists" while the old memory is still deleting.
        harness_name = cfg.get("harness_name",
                               stack_name.replace("-", "_") + "_harness")
        try:
            printed = False
            deadline = time.time() + 10 * 60
            while time.time() < deadline:
                leftover = [m for m in acc.list_memories().get("memories", [])
                            if str(m.get("id", "")).startswith(harness_name + "-")]
                if not leftover:
                    break
                if not printed:
                    print("  waiting for the harness's managed memory to "
                          "finish deleting (takes a minute or two)...")
                    printed = True
                time.sleep(15)
            else:
                print("  WARNING: the harness memory is still deleting — if "
                      "setup_agent.py fails with 'Memory ... already exists', "
                      "wait a minute and re-run it.")
        except ClientError:
            pass  # listing memories is best-effort
    else:
        print("  no harness recorded — skipping")

    # -- 2. Gateway targets, then the gateway -------------------------------
    if gateway_id:
        try:
            targets = acc.list_gateway_targets(gatewayIdentifier=gateway_id)
            for item in targets.get("items", []):
                target_id = item.get("targetId")
                all_ok &= attempt(
                    f"gateway target {item.get('name', target_id)}",
                    lambda tid=target_id: acc.delete_gateway_target(
                        gatewayIdentifier=gateway_id, targetId=tid))
        except ClientError as err:
            code = err.response.get("Error", {}).get("Code", "")
            if code not in ("ResourceNotFoundException", "NotFoundException"):
                print(f"  WARNING: could not list gateway targets: {err}")
                all_ok = False

        def delete_gateway():
            # Targets can take a few seconds to finish deleting.
            for attempt_no in range(6):
                try:
                    acc.delete_gateway(gatewayIdentifier=gateway_id)
                    return
                except ClientError as err:
                    code = err.response.get("Error", {}).get("Code", "")
                    if code in ("ResourceNotFoundException", "NotFoundException"):
                        return
                    if attempt_no == 5:
                        raise
                    time.sleep(10)

        all_ok &= attempt(f"gateway {gateway_id}", delete_gateway)
    else:
        print("  no gateway recorded — skipping")

    # -- 3. CloudFormation stack (Lambdas + roles) --------------------------
    if args.keep_stack:
        print(f"  keeping stack '{stack_name}' (--keep-stack)")
    else:
        cfn = boto3.client("cloudformation", region_name=REGION)
        try:
            cfn.delete_stack(StackName=stack_name)
            print(f"  deleting stack '{stack_name}' (waiting)...")
            cfn.get_waiter("stack_delete_complete").wait(
                StackName=stack_name,
                WaiterConfig={"Delay": 10, "MaxAttempts": 60})
            print(f"  stack '{stack_name}' deleted")
        except ClientError as err:
            print(f"  WARNING: stack deletion problem: {err}")
            all_ok = False

    if CONFIG_PATH.exists():
        CONFIG_PATH.unlink()
        print("  removed agent_config.json")

    if not all_ok:
        sys.exit("Some resources could not be deleted — check the messages "
                 "above and remove them in the console.")
    print("Cleanup complete.")


if __name__ == "__main__":
    main()
