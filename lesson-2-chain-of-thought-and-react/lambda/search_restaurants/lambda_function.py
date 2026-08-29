import json

RESTAURANTS = [
    {"id": "r1", "name": "Trattoria Bella", "cuisine": "Italian",  "rating": 4.6},
    {"id": "r2", "name": "Osteria Romana",  "cuisine": "Italian",  "rating": 4.4},
    {"id": "r3", "name": "Sakura Garden",   "cuisine": "Japanese", "rating": 4.7},
    {"id": "r4", "name": "Ramen Yuki",      "cuisine": "Japanese", "rating": 4.9},
    {"id": "r5", "name": "El Mercado",      "cuisine": "Mexican",  "rating": 4.3},
    {"id": "r6", "name": "Spice Route",     "cuisine": "Indian",   "rating": 4.6},
    {"id": "r7", "name": "Le Bistro",       "cuisine": "French",   "rating": 4.8},
    {"id": "r8", "name": "The Grill House", "cuisine": "American", "rating": 4.2},
]


def tool_name(context):
    """The AgentCore Gateway sends the name of the tool being called
    (namespaced as "<targetName>___<toolName>") in the Lambda client context.
    """
    cc = getattr(context, "client_context", None)
    custom = getattr(cc, "custom", None) or {}
    return custom.get("bedrockAgentCoreToolName", "")


def lambda_handler(event, context):
    # The AgentCore Gateway invokes this Lambda with the TOOL ARGUMENTS as the
    # event itself — a plain dict such as {"cuisine": "Italian"}. This is NOT
    # the old Bedrock Agents action-group envelope.
    print(f"tool={tool_name(context)} event={json.dumps(event)}")  # CloudWatch Logs

    cuisine = str((event or {}).get("cuisine") or "").strip().lower()

    if cuisine:
        matches = [r for r in RESTAURANTS if r["cuisine"].lower() == cuisine]
        if not matches:
            result = {"error": f"No {cuisine.title()} restaurants found."}
        else:
            result = {"restaurants": matches}
    else:
        result = {"restaurants": RESTAURANTS}

    # Whatever this function returns is serialized back to the agent as the
    # tool result — no response envelope needed.
    return result
