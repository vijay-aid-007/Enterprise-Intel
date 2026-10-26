# Churn risk report: 3668-QPYBK

Report status: **complete**

## 1. Risk prediction (ML model, real Telco data)

- Churn probability: 0.5706 (predicted label: no_churn)
- Risk tier: Medium
- Contract: Month-to-month; internet service: DSL; tenure: 2 months; monthly charges: 53.85; payment method: Mailed check

| Feature | Customer value | Effect | Contribution |
|---|---|---|---|
| tenure | 2.0 | raises churn risk | 0.5599 |
| Contract_Month-to-month | Month-to-month | raises churn risk | 0.5047 |
| OnlineSecurity_No | Yes | lowers churn risk | -0.3632 |
| InternetService_Fiber optic | DSL | lowers churn risk | -0.2934 |
| TechSupport_No | No | raises churn risk | 0.1557 |

## 2. Recommended retention actions (from documents)

1. Offer a retention discount of up to 10% off the DSL plan list price for three months, which is the maximum retention discount allowed for a Medium tier month-to-month customer.
   - Source `retention_policy-0010`: retention_policy.pdf (section: Appendix A. Playbook by tier and contract > Medium tier, Month-to-month customer, page: 2)
2. Inform the customer that the combined discount ceiling for a Medium tier month-to-month account is 10% (0% contract discount plus up to 10% retention discount).
   - Source `facts_sheet-0070`: facts_sheet.md (section: Brightline Telecom - Facts Sheet > Lookup C. Combined discount ceilings > Discount ceiling: Medium tier, month-to-month contract)
3. If the customer agrees to switch to a one-year contract, provide a one-time $50 bill credit as an additional incentive.
   - Source `retention_policy-0010`: retention_policy.pdf (section: Appendix A. Playbook by tier and contract > Medium tier, Month-to-month customer, page: 2)

## 3. Withheld by validation (unsupported, omitted from section 2)

Nothing was withheld.

## 4. Evidence shown to the model

| chunk_id | source | location | retrieval score |
|---|---|---|---|
| retention_policy-0010 | retention_policy.pdf | section: Appendix A. Playbook by tier and contract > Medium tier, Month-to-month customer, page: 2 | 0.032 |
| facts_sheet-0070 | facts_sheet.md | section: Brightline Telecom - Facts Sheet > Lookup C. Combined discount ceilings > Discount ceiling: Medium tier, month-to-month contract | 0.033 |

## 5. Notes and limitations

- Tier thresholds are applied directly to the model's churn probability. That is an assumption about what the policy's 'risk score' means.
- Policy, plan and price statements come from SYNTHETIC documents (LLM-generated). They are not facts about the real Telco dataset.
- Excluded 16 retrieved chunk(s) written for other tiers or contract types: retention_policy-0012, retention_policy-0013, retention_policy-0016, retention_policy-0011, facts_sheet-0072, facts_sheet-0073, facts_sheet-0067, facts_sheet-0071, retention_policy-0049, retention_policy-0046, retention_policy-0058, retention_policy-0052, retention_policy-0051, retention_policy-0047, retention_policy-0048, retention_policy-0050.
- predict_customer works only for customer ids present in the Telco CSV.
- Recommendations are model-drafted. Code checks that cited ids exist and that every number appears in a cited chunk (a text match). It does not check that the wording is right.
- Only evidence for this customer's tier and contract type is shown to the model. That filter relies on the wording of the documents.
