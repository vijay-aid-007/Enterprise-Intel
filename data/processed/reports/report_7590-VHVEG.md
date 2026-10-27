# Churn risk report: 7590-VHVEG

Report status: **complete**

## 1. Risk prediction (ML model, real Telco data)

- Churn probability: 0.8537 (predicted label: churn)
- Risk tier: Critical
- Contract: Month-to-month; internet service: DSL; tenure: 1 months; monthly charges: 29.85; payment method: Electronic check

| Feature | Customer value | Effect | Contribution |
|---|---|---|---|
| tenure | 1.0 | raises churn risk | 0.8531 |
| Contract_Month-to-month | Month-to-month | raises churn risk | 0.5103 |
| InternetService_Fiber optic | DSL | lowers churn risk | -0.2884 |
| MonthlyCharges | 29.85 | lowers churn risk | -0.2829 |
| PaymentMethod_Electronic check | Electronic check | raises churn risk | 0.2024 |

## 2. Recommended retention actions (from documents)

1. Offer a retention discount of up to 30% of the internet plan list price for 6 months, which requires approval from the retention manager and logging the approver's name because the discount exceeds 20%.
   - Source `retention_policy-0016`: retention_policy.pdf (section: Appendix A. Playbook by tier and contract > Critical tier, Month-to-month customer, page: 3)
2. Provide a one-time $50 bill credit if the customer agrees to move to a one-year contract.
   - Source `retention_policy-0016`: retention_policy.pdf (section: Appendix A. Playbook by tier and contract > Critical tier, Month-to-month customer, page: 3)
3. Ensure that any combined discounts applied do not exceed the combined discount ceiling of 30% for a Critical tier month-to-month customer.
   - Source `facts_sheet-0076`: facts_sheet.md (section: Brightline Telecom - Facts Sheet > Lookup C. Combined discount ceilings > Discount ceiling: Critical tier, month-to-month contract)

## 3. Withheld by validation (unsupported, omitted from section 2)

Nothing was withheld.

## 4. Evidence shown to the model

| chunk_id | source | location | retrieval score |
|---|---|---|---|
| retention_policy-0016 | retention_policy.pdf | section: Appendix A. Playbook by tier and contract > Critical tier, Month-to-month customer, page: 3 | 0.032 |
| facts_sheet-0076 | facts_sheet.md | section: Brightline Telecom - Facts Sheet > Lookup C. Combined discount ceilings > Discount ceiling: Critical tier, month-to-month contract | 0.033 |
| retention_policy-0006 | retention_policy.pdf | section: Appendix A. Playbook by tier and contract, page: 1 | 0.031 |

## 5. Notes and limitations

- Tier thresholds are applied directly to the model's churn probability. That is an assumption about what the policy's 'risk score' means.
- Policy, plan and price statements come from SYNTHETIC documents (LLM-generated). They are not facts about the real Telco dataset.
- Excluded 10 retrieved chunk(s) written for other tiers or contract types: retention_policy-0013, retention_policy-0018, retention_policy-0017, retention_policy-0015, retention_policy-0007, retention_policy-0010, facts_sheet-0078, facts_sheet-0077, facts_sheet-0067, facts_sheet-0070.
- predict_customer works only for customer ids present in the Telco CSV.
- Recommendations are model-drafted. Code checks that cited ids exist and that every number appears in a cited chunk (a text match). It does not check that the wording is right.
- Only evidence for this customer's tier and contract type is shown to the model. That filter relies on the wording of the documents.
