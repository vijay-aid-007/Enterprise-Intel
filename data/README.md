# Data

## Real data (data/raw)
- `telco-customer-churn.csv`: Telco customer churn dataset as downloaded from Kaggle. Never modified.

## Synthetic data (data/raw): LLM-generated for this assignment
- `facts_sheet.md`
- `retention_policy.pdf`
- `plans_pricing_guide.docx`
- `service_terms.pdf`
- `support_tickets.csv`

All prices, discounts, rules, dates and ticket contents in these five files are
invented. They are NOT facts about the real dataset or about any real company.
RAG answers built on them demonstrate the pipeline, not real business policy.
Gold questions are written from these documents, so retrieval scores are optimistic.

## Generated (data/processed)
Outputs of the code (audit, split ids, chunks, dataset facts). Safe to delete and regenerate.