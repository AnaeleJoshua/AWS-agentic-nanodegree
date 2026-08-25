# Exercise – Technical Documentation Assistant

## Setup

- **Model:** Select **Amazon Nova Pro** from the model dropdown in Bedrock Playground.

---

## Overview

Your engineering team writes fast, messy implementation notes during feature development. Those notes are hard for other developers to understand later. Your task is to build a Bedrock Playground prompt that turns informal notes into polished internal documentation. The assistant should behave like an experienced technical writer who understands software systems and writes clearly for engineers.

---

## Task 1 – Establish a Baseline (No Role)

Before writing a role-based prompt, send the notes below to the model with no role instruction — just a plain request like "Turn these notes into documentation."

```
<engineering_notes>
added caching for product listings - deployed tuesday

before: every request hit the db directly
now: cache results in redis, expire after 5 min then refetch from db

why: product page was slow during peak hours, db cpu kept spiking

what we handle:
- cache miss: falls through to db, result gets cached for next request
- product updated: we clear the cache entry when a product is saved
- sold-out items: might still show as available for up to 5 min. known tradeoff, acceptable for now

still to do: add metrics to track cache hit rate. also might need to tune the 5 min ttl depending on how often products change
</engineering_notes>
```

Note the output's structure, tone, and completeness. You will compare against this baseline in Task 3.

---

## Task 2 – Write an Initial Role-Based Prompt

Write a prompt that:

- Assigns the model a clear role as a technical documentation specialist
- Specifies the audience as internal software engineers
- Describes the expected output format (structured sections, clear language)
- Includes the engineering notes from Task 1

Run it and compare the output to your Task 1 baseline.

---

## Task 3 – Refine Your Prompt

Based on what you observed, update your prompt to address at least two of the following:

- Output structure (headings, sections, bullet lists)
- Level of detail (technical depth vs. plain language)
- What to do with incomplete items (the "not done yet" notes)
- Tone (neutral/formal vs. conversational)

Run the same notes through the refined prompt and compare the outputs.

---

## Task 4 – Experiment

Try at least one of the following and note what changes:

- Swap to a different model and run the same prompt
- Adjust Temperature (try 0 vs. 0.7) and observe variation
- Change the audience in your role (e.g., "for a non-technical product manager") and compare the result

---

## Deliverable

Submit:
1. Your final system prompt
2. The model and any parameter settings you used
3. The documentation output generated from the engineering notes above
