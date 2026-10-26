# Churn risk report: 5575-GNVDE

Report status: **complete**

## 1. Risk prediction (ML model, real Telco data)

- Churn probability: 0.0573 (predicted label: no_churn)
- Risk tier: Low
- Contract: One year; internet service: DSL; tenure: 34 months; monthly charges: 56.95; payment method: Mailed check

| Feature | Customer value | Effect | Contribution |
|---|---|---|---|
| Contract_Month-to-month | One year | lowers churn risk | -0.7909 |
| tenure | 34.0 | lowers churn risk | -0.4909 |
| TotalCharges | 1889.5 | lowers churn risk | -0.2833 |
| OnlineSecurity_No | Yes | lowers churn risk | -0.2297 |
| MonthlyCharges | 56.95 | lowers churn risk | -0.2243 |

## 2. Recommended retention actions (from documents)

1. Make a courtesy call and offer a 12-month price lock.
   - Source `retention_policy-0008`: retention_policy.pdf (section: Appendix A. Playbook by tier and contract > Low tier, One year customer, page: 2)
2. If the customer agrees to a two-year renewal, offer a one-time $75 bill credit.
   - Source `retention_policy-0008`: retention_policy.pdf (section: Appendix A. Playbook by tier and contract > Low tier, One year customer, page: 2)
3. Any discount provided must stay within the combined discount ceiling of 5% for Low tier, one-year contracts.
   - Source `facts_sheet-0068`: facts_sheet.md (section: Brightline Telecom - Facts Sheet > Lookup C. Combined discount ceilings > Discount ceiling: Low tier, one year contract)

## 3. Withheld by validation (unsupported, omitted from section 2)

Nothing was withheld.

## 4. Evidence shown to the model

| chunk_id | source | location | retrieval score |
|---|---|---|---|
| retention_policy-0008 | retention_policy.pdf | section: Appendix A. Playbook by tier and contract > Low tier, One year customer, page: 2 | 0.033 |
| facts_sheet-0068 | facts_sheet.md | section: Brightline Telecom - Facts Sheet > Lookup C. Combined discount ceilings > Discount ceiling: Low tier, one year contract | 0.032 |
| retention_policy-0006 | retention_policy.pdf | section: Appendix A. Playbook by tier and contract, page: 1 | 0.031 |

## 5. Notes and limitations

- Tier thresholds are applied directly to the model's churn probability. That is an assumption about what the policy's 'risk score' means.
- Policy, plan and price statements come from SYNTHETIC documents (LLM-generated). They are not facts about the real Telco dataset.
- Excluded 12 retrieved chunk(s) written for other tiers or contract types: retention_policy-0014, retention_policy-0013, retention_policy-0017, retention_policy-0015, retention_policy-0016, retention_policy-0007, retention_policy-0009, retention_policy-0011, facts_sheet-0069, facts_sheet-0071, facts_sheet-0072, facts_sheet-0067.
- predict_customer works only for customer ids present in the Telco CSV.
- Recommendations are model-drafted. Code checks that cited ids exist and that every number appears in a cited chunk (a text match). It does not check that the wording is right.
- Only evidence for this customer's tier and contract type is shown to the model. That filter relies on the wording of the documents.
