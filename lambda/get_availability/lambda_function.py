import json

AVAILABILITY = {
    "r1": True,
    "r2": False,
    "r3": True,
    "r4": False,
    "r5": True,
    "r6": True,
    "r7": False,
    "r8": True,
}


def tool_name(context):
    """The AgentCore Gateway sends the name of the tool being called
    (namespaced as "<targetName>___<toolName>") in the Lambda client context.
    """
    cc = getattr(context, "client_context", None)
    custom = getattr(cc, "custom", None) or {}
    return custom.get("bedrockAgentCoreToolName", "")


def lambda_handler(event, context):
    # The AgentCore Gateway invokes this Lambda with the TOOL ARGUMENTS as the
    # event itself — a plain dict such as {"restaurant_id": "r1"}. This is NOT
    # the old Bedrock Agents action-group envelope.
    print(f"tool={tool_name(context)} event={json.dumps(event)}")  # CloudWatch Logs

    restaurant_id = str((event or {}).get("restaurant_id") or "").strip()

    # Whatever this function returns is serialized back to the agent as the
    # tool result — no response envelope needed.
    return {
        "restaurant_id": restaurant_id,
        "available": AVAILABILITY.get(restaurant_id, False),
    }
