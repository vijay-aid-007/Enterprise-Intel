# Churn risk report: 5248-YGIJN

Report status: **no_recommendations**

## 1. Risk prediction (ML model, real Telco data)

- Churn probability: 0.0116 (predicted label: no_churn)
- Risk tier: Low
- Contract: Two year; internet service: DSL; tenure: 72 months; monthly charges: 90.25; payment method: Credit card (automatic)

| Feature | Customer value | Effect | Contribution |
|---|---|---|---|
| tenure | 72.0 | lowers churn risk | -1.6842 |
| Contract_Month-to-month | Two year | lowers churn risk | -0.7667 |
| Contract_Two year | Two year | lowers churn risk | -0.4915 |
| OnlineSecurity_No | Yes | lowers churn risk | -0.3222 |
| TotalCharges | 6369.45 | lowers churn risk | -0.319 |

## 2. Recommended retention actions (from documents)

No recommendation passed validation. See notes below.

## 3. Withheld by validation (unsupported, omitted from section 2)

Nothing was withheld.

## 4. Evidence shown to the model

| chunk_id | source | location | retrieval score |
|---|---|---|---|

## 5. Notes and limitations

- Tier thresholds are applied directly to the model's churn probability. That is an assumption about what the policy's 'risk score' means.
- Excluded 5 retrieved chunk(s) written for other tiers or contract types: retention_policy-0014, retention_policy-0015, retention_policy-0013, retention_policy-0017, retention_policy-0018.
- No retrieved chunk states the playbook for the Low tier and Two year contract, so no recommendations were generated.
- predict_customer works only for customer ids present in the Telco CSV.
- Recommendations are model-drafted. Code checks that cited ids exist and that every number appears in a cited chunk (a text match). It does not check that the wording is right.
- Only evidence for this customer's tier and contract type is shown to the model. That filter relies on the wording of the documents.
