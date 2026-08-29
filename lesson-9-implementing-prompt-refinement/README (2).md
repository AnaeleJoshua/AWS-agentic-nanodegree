# Exercise – FAQ Assistant Eval

## Overview

You will build an evaluation pipeline for a Product FAQ Assistant. The assistant helps
customers get accurate answers from a product FAQ — and should refuse to answer questions
that are not covered or that try to manipulate it.

**Scenario:** A project management SaaS team needs to verify that their FAQ assistant
answers correctly, stays grounded in the FAQ, and handles unsafe inputs gracefully before
rollout.

---

## What You'll Do

1. Define the assistant's prompt as a Bedrock Prompt Management template
2. Fill in an eval dataset (question → expected answer) in the script
3. Run the evaluation script and review the results
4. Upload the results to S3
5. Run a Bedrock Model Evaluation job to score the responses
6. Iterate on the prompt and re-run to see if results improve

---

## Step 1 – Create the Prompt Template in the Bedrock Console

1. Open the **Amazon Bedrock console** → **Prompt Management** → **Create prompt**
2. Select the model: **Amazon Nova Pro**
3. Write a prompt template that:
   - Identifies the assistant as a product assistant for the company
   - Instructs it to answer **only from the FAQ provided**
   - Instructs it to say when an answer is not available in the FAQ
   - Uses exactly two template variables: `{{faq}}` and `{{customer_question}}`
4. Save the prompt and publish **version 1**
5. Copy the **Prompt version ARN** — you will need it in the script

---

## Step 2 – Fill In the Eval Dataset

Open `faq_assistant.py` and fill in `EVAL_QUESTIONS`. Add at least 6 entries covering:

- **Answerable questions** – questions with clear answers in the FAQ
- **Unanswerable questions** – questions not covered by the FAQ

Each entry uses this format:

```python
{
    "prompt": "Your question here",
    "referenceResponse": "The ideal answer you expect",
}
```

---

## Step 3 – Configure and Run the Script

Fill in this constant at the top of `faq_assistant.py`:

```python
PROMPT_VERSION_ARN = "<paste your prompt version ARN>"
```

Then run:

```bash
python faq_assistant.py
```

The script will call the assistant for each question and write results to `eval_responses.jsonl`.

---

## Step 4 – Upload Results to S3

Deploy the provided CloudFormation template to create an S3 bucket with a unique name:

```bash
aws cloudformation deploy \
  --template-file template.yaml \
  --stack-name faq-assistant-eval \
  --region us-east-1
```

Then retrieve the bucket name and upload the results:

```bash
BUCKET=$(aws cloudformation describe-stacks --stack-name faq-assistant-eval \
  --query "Stacks[0].Outputs[?OutputKey=='BucketName'].OutputValue" \
  --region us-east-1 \
  --output text)

aws s3 cp eval_responses.jsonl s3://$BUCKET/eval_responses.jsonl
```

---

## Step 5 – Run a Bedrock Model Evaluation Job

1. Open **Amazon Bedrock console** → **Evaluations** → **Create** → **Automatic: LLM as a judge**
2. Select **Amazon Nova Pro** as an evaluator model
3. In **Inference source** select **Bring your own inference responses**. Set **Source name** to `faq-assistant`
4. In **Metrics** select **Correctness**, unselect all other metrics
5. In **Datasets**  → **Prompt dataset**, point to the file you uploaded:

   ```
   s3://<your-bucket-name>/eval_responses.jsonl
   ```


6. Set an S3 output location to any folder in the same S3 bucket, e.g. `s3://<your-bucket-name>/lesson-4/results/`
7. Under **Amazon Bedrock IAM role - Permissions** select **Create and use a new service role**
8. Click **Create** button at the bottom of the page


Once the job completes, review the scores — questions with clear FAQ answers should score well; unanswerable questions will score lower if the model guesses instead of saying the answer is not available.

---

## Step 6 – Iterate on the Prompt

Review the responses printed to the terminal. For any question where the model's answer doesn't match your `referenceResponse`, look for a pattern — is the model guessing when it should say the answer isn't available? Is it too verbose? Does it answer outside the FAQ?

Use what you observe to refine the prompt:

1. Go back to **Amazon Bedrock console** → **Prompt Management** → open your prompt
2. Edit the prompt text to address the issue (e.g. add a stricter grounding instruction, tighten the length limit)
3. Click **Create version** to publish a new version
4. Copy the new **Prompt version ARN** and update `PROMPT_VERSION_ARN` in the script
5. Re-run the script and compare the new responses to your reference answers

Repeat until the responses consistently match what you expect.

---

## Expected Output

```
Running FAQ Assistant Eval
============================================================
Question:  What is the price of the team plan?
Expected:  The team plan is $99 per month for up to 10 users.
Response:  The team plan is priced at $99 per month and supports up to 10 users.
------------------------------------------------------------
...
Wrote 7 records to eval_responses.jsonl
```
