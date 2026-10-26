# Churn risk report: 7469-LKBCI

Report status: **no_internet_service**

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

Not applicable: the customer has no internet service. See notes below.

## 3. Withheld by validation (unsupported, omitted from section 2)

Nothing was withheld.

## 4. Evidence shown to the model

| chunk_id | source | location | retrieval score |
|---|---|---|---|

## 5. Notes and limitations

- Tier thresholds are applied directly to the model's churn probability. That is an assumption about what the policy's 'risk score' means.
- The customer has no internet service in the dataset. The synthetic retention policy ties retention discounts to the internet plan charge (see retention_policy-0002), so no recommendation was generated. Other offers, such as contract-switch bill credits, were not evaluated for this customer.
- predict_customer works only for customer ids present in the Telco CSV.
- Recommendations are model-drafted. Code checks that cited ids exist and that every number appears in a cited chunk (a text match). It does not check that the wording is right.
- Only evidence for this customer's tier and contract type is shown to the model. That filter relies on the wording of the documents.
