# Churn risk report: 7469-LKBCI

Report status: **complete**

## 1. Risk prediction (ML model, real Telco data)

- Churn probability: 0.0044 (predicted label: no_churn)
- Risk tier: Low
- Contract: Two year; internet service: No; tenure: 16 months; monthly charges: 18.95; payment method: Credit card (automatic)

| Feature | Customer value | Effect | Contribution |
|---|---|---|---|
| MonthlyCharges | 18.95 | lowers churn risk | -1.6461 |
| Contract_Month-to-month | Two year | lowers churn risk | -0.9901 |
| Contract_Two year | Two year | lowers churn risk | -0.5945 |
| PaperlessBilling_Yes | No | lowers churn risk | -0.3052 |
| OnlineSecurity_No | No internet service | lowers churn risk | -0.3026 |

## 2. Recommended retention actions (from documents)

1. Offer a contract discount of up to 10% on a new fiber optic service, noting that the retention discount component is 0% for a Low tier two-year contract.
   - Source `facts_sheet-0069`: facts_sheet.md (section: Brightline Telecom - Facts Sheet > Lookup C. Combined discount ceilings > Discount ceiling: Low tier, two year contract)

## 3. Withheld by validation (unsupported, omitted from section 2)

Nothing was withheld.

## 4. Evidence shown to the model

| chunk_id | source | location | retrieval score |
|---|---|---|---|
| facts_sheet-0069 | facts_sheet.md | section: Brightline Telecom - Facts Sheet > Lookup C. Combined discount ceilings > Discount ceiling: Low tier, two year contract | 0.033 |

## 5. Notes and limitations

- Tier thresholds are applied directly to the model's churn probability. That is an assumption about what the policy's 'risk score' means.
- Policy, plan and price statements come from SYNTHETIC documents (LLM-generated). They are not facts about the real Telco dataset.
- Excluded 9 retrieved chunk(s) written for other tiers or contract types: retention_policy-0014, retention_policy-0015, retention_policy-0013, retention_policy-0017, retention_policy-0018, facts_sheet-0072, facts_sheet-0078, facts_sheet-0075, facts_sheet-0067.
- predict_customer works only for customer ids present in the Telco CSV.
- Recommendations are model-drafted. Code checks that cited ids exist and that every number appears in a cited chunk (a text match). It does not check that the wording is right.
- Only evidence for this customer's tier and contract type is shown to the model. That filter relies on the wording of the documents.
