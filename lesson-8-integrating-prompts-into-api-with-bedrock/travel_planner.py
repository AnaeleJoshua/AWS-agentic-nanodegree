import boto3

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")

MODEL_ID = "amazon.nova-lite-v1:0"

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

# TODO (Task 1): Write the system prompt.
# The assistant should:
# - Help users plan visits to cities
# - NOT answer from memory — always use tools first
# - Base recommendations only on tool results
SYSTEM_PROMPT = """\
    
You are a Travel Planning Assistant that helps users plan short city visits.

Your recommendations MUST be grounded in the results returned by the available tools.

TOOLS

You have access to:
- get_weather(city, date): returns weather information for a city and date.
- get_top_attractions(city): returns available attractions for a city.

MANDATORY TOOL USE

For every city-visit planning request, you MUST call the relevant tools before making a recommendation.

For a request involving a specific city and date:

1. Identify the city from the user's request.
2. Determine the requested date.
3. Call get_weather with the city and date.
4. Call get_top_attractions with the city.
5. Wait for the tool results.
6. Generate the final recommendation using only information returned by the tools.

Do not provide a recommendation before the required tool calls are completed.

GROUNDING

You MUST NOT use your pretrained knowledge or general world knowledge to answer the user's travel request.

You MUST NOT invent or add:
- attractions
- activities
- restaurants
- prices
- opening hours
- addresses
- travel times
- weather information
- events
- other travel facts

Only recommend attractions that appear in the result returned by get_top_attractions.

You may summarize, organize, filter, prioritize, and combine information returned by the tools, but you must not introduce new factual information.

USER PREFERENCES

Use information explicitly provided by the user to select and organize the available tool results.

If the user mentions a family or children:
- Prefer attractions where family_friendly is true.
- Do not describe an attraction as family-friendly unless family_friendly is true in the tool result.

If the user specifies a time limit:
- Use avg_visit_hours to calculate the total estimated visit time.
- Do not recommend a combination whose total visit time exceeds the user's stated time limit.

WEATHER

Use the weather returned by get_weather when deciding how to prioritize attractions.

Use the attraction type returned by get_top_attractions:
- Prefer indoor attractions when the returned weather indicates rain.
- Prefer outdoor attractions when the returned weather is clear or sunny.
- Attractions marked outdoor/indoor may be considered for either condition.

Do not invent weather details or weather implications that are not supported by the tool result.

MISSING DATA

If get_weather returns "No data available", do not guess the weather.

If get_top_attractions returns an empty attractions list, do not invent alternative attractions.

If a tool does not return the information needed to make a recommendation, clearly state that the information is unavailable rather than guessing.

FINAL RESPONSE

After the tool calls, provide a concise recommendation based only on the tool results.

Explain briefly why the selected attractions fit the user's stated preferences and the returned weather.

Every factual claim in the final recommendation must be supported by the tool results.
"""

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------
WEATHER_DATA = {
    ("london", "2026-03-14"): {
        "city": "London",
        "date": "2026-03-14",
        "condition": "Light rain in the morning, clearing to partly cloudy by afternoon",
        "temperature_celsius": 11,
        "wind_mph": 12,
        "recommendation": "Bring a light jacket and umbrella for the morning",
    },
    ("london", "2026-03-15"): {
        "city": "London",
        "date": "2026-03-15",
        "condition": "Clear and sunny throughout the day",
        "temperature_celsius": 14,
        "wind_mph": 8,
        "recommendation": "Great day to spend time outdoors",
    },
}

ATTRACTIONS_DATA = {
    "london": {
        "city": "London",
        "attractions": [
            {"name": "British Museum",        "type": "indoor",          "family_friendly": True, "avg_visit_hours": 2.0},
            {"name": "Tower of London",       "type": "outdoor/indoor",  "family_friendly": True, "avg_visit_hours": 2.5},
            {"name": "Natural History Museum","type": "indoor",          "family_friendly": True, "avg_visit_hours": 2.0},
            {"name": "Hyde Park",             "type": "outdoor",         "family_friendly": True, "avg_visit_hours": 1.5},
            {"name": "Covent Garden",         "type": "outdoor/indoor",  "family_friendly": True,  "avg_visit_hours": 1.0},
            {"name": "The Comedy Store",      "type": "indoor",          "family_friendly": False, "avg_visit_hours": 2.0},
            {"name": "Soho Nightlife",        "type": "outdoor/indoor",  "family_friendly": False, "avg_visit_hours": 3.0},
            {"name": "Shoreditch Bar Crawl",  "type": "outdoor/indoor",  "family_friendly": False, "avg_visit_hours": 4.0},
        ],
    }
}

# ---------------------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------------------
TOOLS = [

    {

        "toolSpec": {

            "name": "get_weather",

            "description": "Returns weather conditions and forecast information for a given city and date.",

            "inputSchema": {

                "json": {

                    "type": "object",

                    "properties": {

                        "city": {

                            "type": "string",

                            "description": "The city for which weather information is requested."

                        },

                        "date": {

                            "type": "string",

                            "description": "The date for the weather forecast in YYYY-MM-DD format."

                        },

                    },

                    "required": [

                        "city",

                        "date"

                    ],

                }

            },

        }

    },

    {

        "toolSpec": {

            "name": "get_top_attractions",

            "description": "Returns a list of top attractions in a given city, including their type, family-friendliness, and estimated visit duration.",

            "inputSchema": {

                "json": {

                    "type": "object",

                    "properties": {

                        "city": {

                            "type": "string",

                            "description": "The city for which top attractions are requested."

                        },

                    },

                    "required": [

                        "city"

                    ],

                }

            },

        }

    },

]
# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------
def get_weather(city: str, date: str) -> dict:
    return WEATHER_DATA.get(
        (city.lower(), date),
        {"city": city, "date": date, "condition": "No data available"},
    )


def get_top_attractions(city: str) -> dict:
    return ATTRACTIONS_DATA.get(
        city.lower(),
        {"city": city, "attractions": []},
    )


def execute_tool(name: str, tool_input: dict) -> dict:
    if name == "get_weather":
        return get_weather(tool_input["city"], tool_input["date"])
    elif name == "get_top_attractions":
        return get_top_attractions(tool_input["city"])
    return {"error": f"Unknown tool: {name}"}


# ---------------------------------------------------------------------------
# Converse loop
# ---------------------------------------------------------------------------
def run_chat() -> None:
    messages = []

    print("Travel Planner")
    print("=" * 40)
    print("Ask me to help plan your visit to a city.\n")

    try:
        user_input = input("You: ").strip()
    except (EOFError, KeyboardInterrupt):
        return

    if not user_input:
        print("No input provided.")
        return

    messages.append({"role": "user", "content": [{"text": user_input}]})

    while True:
        response = bedrock.converse(
            modelId=MODEL_ID,
            system=[{"text": SYSTEM_PROMPT}],
            messages=messages,
            toolConfig={"tools": TOOLS},
        )

        stop_reason = response["stopReason"]
        output_message = response["output"]["message"]
        messages.append(output_message)

        if stop_reason == "end_turn":
            for block in output_message["content"]:
                if "text" in block:
                    print(f"\nAssistant: {block['text']}\n")
            break

        elif stop_reason == "tool_use":
            tool_results = []

            for block in output_message["content"]:
                if "toolUse" in block:
                    tool_name = block["toolUse"]["name"]
                    tool_input = block["toolUse"]["input"]
                    tool_use_id = block["toolUse"]["toolUseId"]

                    print(f"  [tool call] {tool_name}({tool_input})")
                    result = execute_tool(tool_name, tool_input)
                    print(f"  [tool result] {result}")

                    tool_results.append({
                        "toolResult": {
                            "toolUseId": tool_use_id,
                            "content": [{"json": result}],
                        }
                    })

            messages.append({"role": "user", "content": tool_results})


if __name__ == "__main__":
    run_chat()
