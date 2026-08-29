# Exercise – Restaurant Recommendation Agent

## Overview

In this exercise you build a restaurant recommendation agent on **Amazon Bedrock AgentCore**. The agent is an **AgentCore managed harness** (the agent runtime), and its tools are three Lambda functions exposed through an **AgentCore Gateway**. The Lambdas are provided and ready to deploy — your job is to deploy the infrastructure, **write the agent instruction**, describe the tools, and wire everything together.

> **Note:** This exercise previously used Bedrock Agents Classic, which closed to new customers on July 30, 2026. The AgentCore managed harness is its replacement: same ReAct loop, but the agent is created with a few lines of boto3 instead of console clicks — and there is no "prepare" step.

The skill being assessed is **prompting, not infrastructure**: your instruction must force *tool-grounded* answers. A correct agent calls all three tools at least once before recommending — and never invents a restaurant.

## What you build

```
you ──> managed harness (Amazon Nova Pro + your instruction)
              │  ReAct loop, runs server-side
              ▼
        AgentCore Gateway (MCP)
        ├── target "cuisines"      ──> get-cuisines Lambda
        ├── target "restaurants"   ──> search-restaurants Lambda
        └── target "availability"  ──> get-availability Lambda
```

Files in this folder:

| File | What it is |
|------|------------|
| `template.yaml` | CloudFormation: the 3 Lambdas + all IAM roles (one deploy) |
| `template_base.yaml`, `generate_template.py` | Sources for `template.yaml` — regenerate it if you edit the Lambdas |
| `lambda/*/lambda_function.py` | The three tool Lambdas (provided) |
| `setup_agent.py` | Creates the gateway + harness — **contains your two TODOs** |
| `invoke_agent.py` | Sends a prompt and prints every tool call it observes |
| `cleanup.py` | Deletes everything the exercise created |

## Setup

You need Python 3 with a recent `boto3`, and AWS credentials for your lab account. Everything runs in **us-east-1**.

**Step 1 – Deploy the infrastructure.** One CloudFormation deploy creates the three Lambdas, their execution role, the **gateway role** (the role the AgentCore Gateway assumes to invoke your Lambdas — this replaces the old resource-based permission for `bedrock.amazonaws.com`), and the **harness execution role**:

```bash
aws cloudformation deploy \
  --template-file template.yaml \
  --stack-name restaurant-agent \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1
```

## Steps

**Step 2 – Write the agent instruction** (`TODO 1` in `setup_agent.py`). Your `SYSTEM_PROMPT` must:

- Describe the agent as a restaurant recommendation assistant for a single city (so it never asks the user where they are)
- Tell it to **always use the tools** before making suggestions
- Tell it to base its recommendation **only on tool results** — never invent restaurants, ratings, or availability
- Tell it to confirm availability before recommending, and to try the next best option if a restaurant is unavailable

**Step 3 – Describe the tools** (`TODO 2` in `setup_agent.py`). The wiring of each gateway target to its Lambda is done for you; fill in each tool's description and parameters:

### `get_cuisines`

Returns the list of cuisine types available. Takes no parameters.

### `search_restaurants`

Searches for restaurants. Returns all restaurants if no cuisine is specified.

| Parameter | Type   | Required | Description                                                              |
|-----------|--------|----------|--------------------------------------------------------------------------|
| `cuisine` | string | No       | The cuisine type (e.g. Italian, Japanese). If omitted, all are returned. |

### `get_availability`

Checks whether a specific restaurant has availability for tonight.

| Parameter       | Type   | Required | Description                          |
|-----------------|--------|----------|--------------------------------------|
| `restaurant_id` | string | Yes      | The unique ID of the restaurant, e.g. `r1` |

> **Warning – naming rules:** Tool names may only contain letters, digits, and underscores (`get_cuisines`, never `get-cuisines`); gateway target names only letters and digits (`availability`) — the Gateway API rejects underscores in target names. The model sees each tool namespaced as `<targetName>___<toolName>`, and a dash anywhere in that string breaks tool calling.

**Step 4 – Create the agent:**

```bash
python setup_agent.py
```

This creates the gateway, its three targets, and the harness, then waits (2–3 minutes) for the harness to reach `READY`. Unlike Bedrock Agents Classic there is **no "prepare" step** — once `READY`, the agent is live.

## Test

```bash
python invoke_agent.py "Find me an Italian restaurant for tonight."
```

The harness runs the whole ReAct loop server-side and the script streams it. **How to verify the tool calls:**

- Every tool the agent uses is printed as a `[tool call] <target>___<tool>({...})` line — you should see all **three** tools before the final recommendation, and the script prints a verdict at the end telling you if any were skipped.
- Between the tool calls the model streams its reasoning in `<thinking>` tags — that is the ReAct "Thought" step, live.
- Each Lambda also logs the event it received to CloudWatch Logs (`/aws/lambda/restaurant-agent-*`), so you can confirm the calls landed.

A correct run recommends a restaurant that the tools actually returned **and** that has availability tonight. If the agent skips tools or names a restaurant the tools never mentioned, your instruction is not forcing grounding — tighten it and try again.

**Deliverable:** your agent instruction, plus the transcript from `invoke_agent.py` showing all three tool calls.

## Cleanup

When you are done, delete everything (agent, gateway, and the CloudFormation stack):

```bash
python cleanup.py
```

To iterate on your instruction *without* redeploying the Lambdas, keep the stack and recreate just the agent:

```bash
python cleanup.py --keep-stack
# edit SYSTEM_PROMPT in setup_agent.py
python setup_agent.py
```

Let cleanup finish before re-running setup: it also waits for the harness's managed session memory to delete (a minute or two) — recreating the agent under the same name too early fails with "Memory ... already exists".

## Hints

- **Dash-free names.** Tool names: letters, digits, and underscores. Target names: letters and digits only. `setup_agent.py` checks this for you.
- **No prepare step.** The harness needs no preparing and sessions are stateful — to change the instruction, run `cleanup.py --keep-stack` and `setup_agent.py` again.
- **Order the loop explicitly.** Instructions that spell out *discover cuisines → search restaurants → check availability* reliably produce all three tool calls; vague "use tools when helpful" phrasing lets the model skip steps.
- **Tool descriptions are prompts too.** The model chooses tools by their descriptions; a lazy description leads to skipped or misused tools.
- **Leave the model pinned.** `MODEL_ID` is set to Amazon Nova Pro because the harness default model is not available in the lab accounts.
- **A retry message during setup is normal** — freshly created IAM roles can take a few seconds to propagate, and the script retries automatically.
- **Multi-turn:** re-run `invoke_agent.py` with `--session <id>` (printed on the first run) to continue the same conversation. On follow-up turns the agent may reuse tool results from earlier in the session instead of re-calling every tool — the three-tool check applies to the first turn of a fresh session.
