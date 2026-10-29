# Data

Everything in `data/raw/` is read-only: no code in this repo modifies it.

## Real versus synthetic

| File | Real or synthetic | What it is |
|---|---|---|
| `telco-customer-churn.csv` | **Real** (Kaggle Telco customer churn) | 7,043 customers with services, contract, charges and the `Churn` label |
| `facts_sheet.md` | **Synthetic** | Fictional company facts and lookup tables: bundle totals, add-on pairs, combined discount ceilings, retention team capacity, response deadlines, plan-plus-add-on totals |
| `retention_policy.pdf` | **Synthetic** | Fictional retention policy: tiers and caps, eligibility exclusions, a playbook per tier and contract, worked pricing examples, common situations, eligibility cases |
| `plans_pricing_guide.docx` | **Synthetic** | Fictional plans, phone lines, add-ons, discounts and price examples |
| `service_terms.pdf` | **Synthetic** | Fictional billing, cancellation, service-level and equipment terms, with worked examples |
| `support_tickets.csv` | **Synthetic** | Fictional tickets. Columns: `ticket_id, created_date, category, channel, contract, internet_service, priority, status, customer_message, agent_notes` |

The five synthetic files were generated for this assignment by `scripts/make_synthetic_docs.py`, with prices and rules defined in `scripts/synth_rules.py` and templates in `scripts/synth_docs.py`. Every chunk made from them is marked `"synthetic": true` in `data/processed/chunks.jsonl`.

**Never read a synthetic price, discount or rule as a fact about the real dataset.** The documents describe Brightline Telecom, a fictional company. `scripts/check_doc_sync.py` is a read-only comparison of the synthetic price list with the real `MonthlyCharges`. The documents make no claim that the two agree.

## Real data notes

- 11 rows have a blank `TotalCharges` and `tenure` 0. Preprocessing sets them to 0 and logs it.
- `SeniorCitizen` is coded 0 or 1, unlike the other yes/no columns.
- About 26.5% of training customers churn. The split is stratified (80% train, 20% test, seed 42) and stored in `data/processed/split_ids.json`. `customer_split(id)` in `src/ml/explain.py` returns `train` or `test`.
- The Kaggle dataset has its own terms of use. They are not reproduced here, so check them before redistributing the CSV.

## Derived files in `data/processed/`

| File | Written by | Notes |
|---|---|---|
| `chunks.jsonl` | `python -m src.docs.chunker` | 616 chunks: facts sheet 175, retention policy 83, pricing guide 140, service terms 116, tickets 102. Fields: `chunk_id, text, source, location, doc_type, synthetic, n_chars`. Location holds whichever of page, section or row exists. |
| `split_ids.json` | `python -m src.ml.train` | train and test customer ids |
| `audit.json` | `python -m scripts.audit_data` | data audit |
| `dataset_facts.md` | `scripts/dataset_facts.py` | facts about the Telco data |
| `reports/` | `python -m src.llm.report ID` | example reports. They were produced during development and may carry older note wording. Regenerate to refresh. |

## Support tickets

The ticket CSV has no customer id, so tickets cannot be joined to Telco customers. Its chunks are indexed (`doc_type: csv`), but generation uses only the Markdown, PDF and DOCX chunks (`GEN_DOC_TYPES` in `src/config.py`), so tickets never appear in an answer.