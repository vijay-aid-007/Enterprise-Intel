# Churn risk report: 8091-TTVAX

Report status: **complete**

## 1. Risk prediction (ML model, real Telco data)

- Churn probability: 0.4422 (predicted label: no_churn)
- Risk tier: Medium
- Contract: One year; internet service: Fiber optic; tenure: 58 months; monthly charges: 100.35; payment method: Credit card (automatic)

| Feature | Customer value | Effect | Contribution |
|---|---|---|---|
| Contract_Month-to-month | One year | lowers churn risk | -0.6509 |
| TotalCharges | 5681.1 | lowers churn risk | -0.3697 |
| tenure | 58.0 | lowers churn risk | -0.3089 |
| MonthlyCharges | 100.35 | raises churn risk | 0.3047 |
| PaperlessBilling_Yes | No | lowers churn risk | -0.2291 |

## 2. Recommended retention actions (from documents)

1. Offer a retention discount of 10% off the internet plan list price for 3 months, which is within the allowed retention discount for a Medium-tier, one-year customer.
   - Source `retention_policy-0011`: retention_policy.pdf (section: Appendix A. Playbook by tier and contract > Medium tier, One year customer, page: 2)
2. Note that the combined discount ceiling for this tier and contract is 15% (5% contract discount plus the 10% retention discount).
   - Source `facts_sheet-0071`: facts_sheet.md (section: Brightline Telecom - Facts Sheet > Lookup C. Combined discount ceilings > Discount ceiling: Medium tier, one year contract)
3. If the customer agrees to renew for two years, provide a one-time $75 bill credit as an additional incentive.
   - Source `retention_policy-0011`: retention_policy.pdf (section: Appendix A. Playbook by tier and contract > Medium tier, One year customer, page: 2)

## 3. Withheld by validation (unsupported, omitted from section 2)

Nothing was withheld.

## 4. Evidence shown to the model

| chunk_id | source | location | retrieval score |
|---|---|---|---|
| retention_policy-0011 | retention_policy.pdf | section: Appendix A. Playbook by tier and contract > Medium tier, One year customer, page: 2 | 0.032 |
| facts_sheet-0071 | facts_sheet.md | section: Brightline Telecom - Facts Sheet > Lookup C. Combined discount ceilings > Discount ceiling: Medium tier, one year contract | 0.033 |
| retention_policy-0006 | retention_policy.pdf | section: Appendix A. Playbook by tier and contract, page: 1 | 0.032 |

## 5. Notes and limitations

- Tier thresholds are applied directly to the model's churn probability. That is an assumption about what the policy's 'risk score' means.
- Policy, plan and price statements come from SYNTHETIC documents (LLM-generated). They are not facts about the real Telco dataset.
- Excluded 9 retrieved chunk(s) written for other tiers or contract types: retention_policy-0012, retention_policy-0014, retention_policy-0010, retention_policy-0013, retention_policy-0008, facts_sheet-0072, facts_sheet-0074, facts_sheet-0068, facts_sheet-0077.
- predict_customer works only for customer ids present in the Telco CSV.
- Recommendations are model-drafted. Code checks that cited ids exist and that every number appears in a cited chunk (a text match). It does not check that the wording is right.
- Only evidence for this customer's tier and contract type is shown to the model. That filter relies on the wording of the documents.
