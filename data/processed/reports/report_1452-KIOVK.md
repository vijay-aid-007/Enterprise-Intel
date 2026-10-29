# Churn risk report: 1452-KIOVK

Report status: **complete**

## 1. Risk prediction (ML model, real Telco data)

- Churn probability: 0.6239 (predicted label: churn)
- Risk tier: High
- Contract: Month-to-month; internet service: Fiber optic; tenure: 22 months; monthly charges: 89.1; payment method: Credit card (automatic)

| Feature | Customer value | Effect | Contribution |
|---|---|---|---|
| Contract_Month-to-month | Month-to-month | raises churn risk | 0.4892 |
| TotalCharges | 1949.4 | lowers churn risk | -0.2476 |
| InternetService_Fiber optic | Fiber optic | raises churn risk | 0.223 |
| PaymentMethod_Electronic check | Credit card (automatic) | lowers churn risk | -0.2122 |
| OnlineSecurity_No | No | raises churn risk | 0.1751 |

## 2. Recommended retention actions (from documents)

1. Offer a retention discount of 20% off the internet plan list price for 6 months, which requires team lead approval.
   - Source `retention_policy-0013`: retention_policy.pdf (section: Appendix A. Playbook by tier and contract > High tier, Month-to-month customer, page: 2)
2. Offer a one-time $50 bill credit if the customer agrees to switch to a one-year contract.
   - Source `retention_policy-0013`: retention_policy.pdf (section: Appendix A. Playbook by tier and contract > High tier, Month-to-month customer, page: 2)

## 3. Withheld by validation (unsupported, omitted from section 2)

Nothing was withheld.

## 4. Evidence shown to the model

| chunk_id | source | location | retrieval score |
|---|---|---|---|
| retention_policy-0013 | retention_policy.pdf | section: Appendix A. Playbook by tier and contract > High tier, Month-to-month customer, page: 2 | 0.033 |
| facts_sheet-0073 | facts_sheet.md | section: Brightline Telecom - Facts Sheet > Lookup C. Combined discount ceilings > Discount ceiling: High tier, month-to-month contract | 0.033 |
| retention_policy-0006 | retention_policy.pdf | section: Appendix A. Playbook by tier and contract, page: 1 | 0.032 |

## 5. Notes and limitations

- Tier thresholds are applied directly to the model's churn probability. That is an assumption about what the policy's 'risk score' means.
- Policy, plan and price statements come from SYNTHETIC documents (LLM-generated). They are not facts about the real Telco dataset.
- Excluded 10 retrieved chunk(s) written for other tiers or contract types: retention_policy-0015, retention_policy-0016, retention_policy-0014, retention_policy-0010, retention_policy-0007, retention_policy-0009, facts_sheet-0067, facts_sheet-0070, facts_sheet-0074, facts_sheet-0075.
- predict_customer works only for customer ids present in the Telco CSV.
- Recommendations are model-drafted. Code checks that cited ids exist and that every number appears in a cited chunk (a text match). It does not check that the wording is right.
- Only evidence for this customer's tier and contract type is shown to the model. That filter relies on the wording of the documents.
