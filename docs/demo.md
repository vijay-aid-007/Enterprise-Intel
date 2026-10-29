# Demo script (about 10 minutes)

All customer ids below are in the **test** split, so their scores are not in-sample. Do not use `6713-OKOMC`: its score (0.354) is 0.004 above the Medium boundary, so a rounding change would flip its tier.

## Before you start

1. Terminal 1: `python -m src.api.main`. Terminal 2: `python -m streamlit run app/streamlit_app.py`. The sidebar should say "API ready".
2. **Run every step below once beforehand** and read the output. If an answer looks wrong, skip that step. These steps are checked against what the evaluation showed, not against your screen.
3. Groq's free tier allows a few thousand tokens per minute, and each model call uses about 4,000. Wait about 20 seconds between clicks that call the model, and don't double-click.

## 1. Framing (30 seconds)

Real: the Telco CSV and the churn model. Synthetic: every policy, price and terms document. Three layers: ML, retrieval, and an LLM whose output is checked in code.

## 2. Customer report: the normal case

Report tab, `1452-KIOVK` (month-to-month, Fiber optic, High tier), then **Full report**.
- In the earlier evaluation: score 0.6239, High tier, a 20% retention discount for 6 months needing team-lead approval, and a $50 credit for moving to a one-year contract.
- Point at the drivers table (SHAP), the "Sources" line under each action, the "Withheld by validation" expander, and the evidence table.
- Say: the ML section is rendered by code. The model only drafts the recommendations.

## 3. Customer report: a refusal by design

`3930-ZGWVE` (High tier, month-to-month, **no internet service**), then **Full report**. Expect status `no_internet_service` and no actions.
- Say: the policy applies retention discounts to the internet plan charge only (`retention_policy-0002`), so the code does not ask the model. The note cites that chunk.

## 4. Another tier

`6322-HRPFA` (Low tier, month-to-month, DSL), then **Full report**. Expect Low-tier playbook content, not a discount. Check each action against its source chunk before presenting it.

## 5. Ask the documents

Ask tab:
1. "What is the absolute cap on any retention discount?" Expect 30 percent, with two sources.
2. "What is the maximum retention discount for Platinum tier customers?" Expect a refusal. The documents have no Platinum tier, so retrieval passes it and the model refuses. Say that this layer is the weaker one.
3. "What is the capital of France?" Expect a refusal before any model call. The caption shows the similarity that fell below the threshold.

**Known weakness, shown openly.** Ask: "What is the maximum retention discount for a Medium tier customer on a month-to-month contract, and for how long does it last?" In the held-out retrieval run, BM25 ranked the right chunk first, dense missed the top 10, and hybrid ranked it seventh. In the generation run it was refused in hybrid mode. Switch the retrieval mode to `bm25` and ask again. Only the retrieval ranks were measured. The answer in the UI has not been checked, so read it before you rely on it.

## 6. Agent

Agent tab:
1. "What is the churn rate for each contract type?" Expect the trace to show `analyze_data`, with rates 0.4271, 0.1127 and 0.0283.
2. "Create a retention report for customer 1452-KIOVK." Expect `generate_report`.
3. "What is 73 * (100 - 40) / 100?" Expect `calculate`, 43.8.

Point at the trace table: the model chooses tools, and code runs them with validation, limits and timeouts.

## 7. Failure mode

Stop the API (Ctrl+C in terminal 1) and reload the page. Expect a red message naming `python -m src.api.main`, not a traceback.

## Questions you should expect

- **Why XGBoost?** It won on the declared criterion, mean CV PR-AUC on the train split. The difference from logistic regression is within fold-to-fold noise, so it is a rule-following choice, not a win.
- **Is the score a probability?** No. Class weights inflate it, and the calibration table shows over-prediction in every bin. Tiers are risk bands, and their boundaries come from the synthetic policy.
- **How do you stop the model inventing numbers?** Cited ids must exist, every number must appear in a cited chunk, and an answer must not name a document that was not cited. A failing draft is withheld, and the API has no field to return it. These checks do not test meaning, and qualifiers can be dropped.
- **What about questions the documents cannot answer?** Two layers: a similarity threshold before the model, then the model's `can_answer`. In-scope-looking questions rely on the second.
- **Why hybrid when BM25 did better on held-out?** The mode was fixed before the held-out run, as the assignment asks. Choosing after seeing held-out would remove the clean test, so it is reported as a finding.
- **Prompt injection?** Chunk text is escaped and labelled untrusted, and the code validators sit behind the model. It was tested with one poisoned chunk on one model, and the model did not comply. That is one case, not a guarantee.