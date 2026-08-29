import boto3
import json

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")

# TODO: Fill in after completing the console steps in the README.
PROMPT_VERSION_ARN = "arn:aws:bedrock:us-east-1:121062621575:prompt/VCWU4XVXPU:1"

OUTPUT_FILE = "eval_responses.jsonl"

# ---------------------------------------------------------------------------
# Product FAQ (provided)
# ---------------------------------------------------------------------------
PRODUCT_FAQ = """\
Product FAQ

Pricing:
- Individual plan: $29 per month
- Team plan: $99 per month (up to 10 users)
- Enterprise: contact sales for custom pricing

Free Trial:
- 14-day free trial available for all plans
- No credit card required to start

Features:
- Task management with priority levels and due dates
- Time tracking built into each task
- Gantt chart view for project timelines
- Integrations: Slack and Google Workspace only

Storage:
- Individual plan: 10 GB per user
- Team plan: 100 GB shared across the team

Supported Platforms:
- Web browsers (Chrome, Firefox, Safari, Edge)
- iOS and Android mobile apps

Security:
- SOC 2 Type II certified
- All data encrypted at rest and in transit

Support:
- Email support for all plans
- Live chat support for Team and Enterprise plans only\
"""

# ---------------------------------------------------------------------------
# TODO: Fill in the eval dataset.
#
# Each entry must have:
#   "prompt"            – the customer question
#   "referenceResponse" – the ideal answer you expect from the assistant
#
# Include at least:
#   - 4 answerable questions (clear answers exist in the FAQ above)
#   - 2 unanswerable questions (not covered by the FAQ)
# ---------------------------------------------------------------------------
EVAL_QUESTIONS = [
    {
        "prompt": "How much does the Team plan cost per month?",
        "referenceResponse": "The Team plan costs $99 per month and supports up to 10 users."
    },
    {
        "prompt": "Do I need a credit card to start the free trial?",
        "referenceResponse": "No. The 14-day free trial is available for all plans and does not require a credit card to start."
    },
    {
        "prompt": "What integrations does the product support?",
        "referenceResponse": "The product supports Slack and Google Workspace integrations."
    },
    {
        "prompt": "Is my data encrypted?",
        "referenceResponse": "Yes. All data is encrypted at rest and in transit. The product is also SOC 2 Type II certified."
    },
    {
        "prompt": "Does the product support Microsoft Teams integration?",
        "referenceResponse": "The FAQ does not provide information about Microsoft Teams integration."
    },
    {
        "prompt": "Can I export my projects to a PDF file?",
        "referenceResponse": "The FAQ does not provide information about exporting projects to PDF files."
    }
]

# ---------------------------------------------------------------------------
# Invoke the stored prompt template
# ---------------------------------------------------------------------------
def invoke(question: str) -> str:
    response = bedrock.invoke_model(
        modelId=PROMPT_VERSION_ARN,
        body=json.dumps({
            "promptVariables": {
                "faq":               {"text": PRODUCT_FAQ},
                "customer_question": {"text": question},
            }
        }),
        contentType="application/json",
        accept="application/json",
    )
    result = json.loads(response["body"].read())
    return result["output"]["message"]["content"][0]["text"]


# ---------------------------------------------------------------------------
# Main – run eval and write results
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    records = []

    print("Running FAQ Assistant Eval\n")
    print("=" * 60)

    for item in EVAL_QUESTIONS:
        question = item["prompt"]
        reference = item["referenceResponse"]
        response = invoke(question)

        print(f"Question:  {question}")
        print(f"Expected:  {reference}")
        print(f"Response:  {response}")
        print("-" * 60)

        records.append({
            "prompt": question,
            "referenceResponse": reference,
            "modelResponses": [
                {
                    "response": response,
                    "modelIdentifier": "faq-assistant",
                }
            ],
        })

    with open(OUTPUT_FILE, "w") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")

    print(f"\nWrote {len(records)} records to {OUTPUT_FILE}")
