# Autonomous Enterprise Intelligence Platform (ML + GenAI)

An end-to-end prototype that predicts customer churn, retrieves evidence from policy documents, and has an LLM draft cited answers and retention recommendations. The checks that decide what a user sees run in code, not on the model's confidence. Built for a hiring assignment on the Kaggle Telco customer-churn data and a fictional company, Brightline Telecom.

> **Real versus synthetic.** `data/raw/telco-customer-churn.csv` is real (Kaggle). The five documents the system retrieves from (`facts_sheet.md`, `retention_policy.pdf`, `plans_pricing_guide.docx`, `service_terms.pdf`, `support_tickets.csv`) are **synthetic**, generated for this assignment by `scripts/make_synthetic_docs.py`. Their prices, discounts and rules are not facts about the real dataset or any real company. See [data/README.md](data/README.md).

## Results at a glance

<!-- RESULTS:START -->
| Measure | Result |
|---|---|
| Retrieval hit@5, held-out | dense 9/14, bm25 14/14, hybrid 12/14 |
| Retrieval MRR, held-out | dense 0.429, bm25 0.881, hybrid 0.711 |
| Retrieval hit@5, dev | dense 7/8, bm25 7/8, hybrid 7/8 |
| Answers to answerable questions, held-out | 10 correct, 3 incomplete, 1 refused of 14 (automatic fact matching, a lower bound) |
| Refusals, held-out | out-of-scope 2/2, unsupported but in-scope-looking 2/2 |
| Validator rejections, held-out | 0 of 16 drafts that reached the model |
| Agent routing (first tool) | 9/9 (prompts not used in development: 4/4) |
| Prompt injection, one case | model complied: False, shown to the user: False |
| Churn model, test split (n = 1409) | PR-AUC 0.663, ROC-AUC 0.8446, precision 0.5481, recall 0.7166 at threshold 0.5783 |

Generated from `eval/results` by `scripts/make_results_md.py`. Gold questions come from SYNTHETIC documents, so scores are optimistic; samples are small and there are no confidence intervals. Full tables: [docs/RESULTS.md](docs/RESULTS.md).
<!-- RESULTS:END -->

## What it does

| Part | Where | What it does |
|---|---|---|
| Churn model | `src/ml` | Logistic regression and XGBoost compared by 5-fold CV on a stratified train split, with class weights for the churn imbalance. The decision threshold is chosen on out-of-fold predictions, the test split is scored once, and SHAP gives each customer's top drivers. |
| Document intelligence | `src/docs` | Loaders for PDF, DOCX, Markdown and CSV. The chunker never crosses a section boundary, keeps tables in their own chunks and records page, section or row for every chunk. |
| Retrieval (RAG) | `src/rag` | MiniLM embeddings in Chroma, BM25, and reciprocal rank fusion. Selectable `dense`, `bm25` or `hybrid`. Every result is `{chunk_id, text, source, score, location}`. In hybrid mode `score` is a rank-fusion score, not a similarity. |
| Grounded answers | `src/llm/answer.py` | The LLM drafts a JSON answer with citations through a forced function call, and code validates it. |
| Retention reports | `src/llm/report*.py` | Predict, assign a risk tier, retrieve the matching playbook, draft recommendations, validate, write markdown. The ML section is rendered by code; the model only drafts recommendations. |
| Agent | `src/agent` | A plain loop, no framework. Tools: `search_documents`, `analyze_data` (allow-listed pandas operations), `calculate` (arithmetic only, AST whitelist) and `generate_report`, plus `final_answer` to finish. Limits: 5 tool calls, 3 document searches, a per-call timeout, errors returned to the model as messages, full trace. |
| API and UI | `src/api`, `app` | FastAPI (`/health /predict /ask /agent /report`) and a Streamlit app that talks only to the API. |

```text
data/raw ──► src/docs ──► chunks.jsonl ──► src/rag.index ──► Chroma (indexes/, rebuilt locally)
Telco CSV ─► src/ml ──► model + SHAP drivers ──────────────┐
                                                           ▼
 question / customer id ──► retrieve ──► LLM (Groq, function calling) ──► validators in code ──► answer / report
                                │
        src/agent (4 tools) ────┘          src/api (FastAPI) ──► app (Streamlit)
```

## What is checked in code

| Check | Where |
|---|---|
| Too little evidence: the top dense similarity is below `DENSE_MIN_SIM`, so the model is never called | `src/rag/retriever.py`, `src/config.py` |
| Every cited id must be among the chunks actually retrieved | `validate_answer` in `src/llm/answer.py` |
| Every number in an answer must appear in a cited chunk (agent: or in a code-computed tool result) | `validate_answer`, `validate_final` |
| An answer must not name a document that no cited chunk comes from | `check_attribution` |
| A rejected draft is withheld and never leaves the server | `src/api/schemas.py` has no field for it |
| Reports skip the model when the customer has no internet service or the playbook chunk was not retrieved | `src/llm/report.py` |
| Tools take validated arguments, never use `eval` or `exec`, and chunk text is escaped and labelled untrusted | `src/agent`, `src/llm/answer.py` |

## Setup

Requires [uv](https://docs.astral.sh/uv/). The lock is built for Python 3.11, which uv selects.

```bash
uv sync
# activate the environment: .venv\Scripts\Activate.ps1 (Windows PowerShell) or: source .venv/bin/activate
cp .env.example .env              # Windows: Copy-Item .env.example .env
# edit .env: set GROQ_API_KEY (the model is LLM_MODEL, default openai/gpt-oss-120b)
python -m src.rag.index           # builds the Chroma index from data/processed/chunks.jsonl (not committed)
python -m pytest tests -q
```

Notes:
- The first index build downloads the embedding model from Hugging Face. After that, `HF_HUB_OFFLINE=1` skips the network. `HF_TOKEN` silences the unauthenticated-request warning.
- Without uv: `python -m venv .venv`, activate it, then `pip install -r requirements.txt`. That file is generated by `uv export` from `uv.lock`; change dependencies in `pyproject.toml`, then run `uv lock` and `uv export --no-hashes --no-emit-project -o requirements.txt`.
- On Linux the lock pulls CUDA builds of `torch`, which are large. A CPU-only install is not configured.
- Tests: 161 passed and 6 skipped when last run. The skips are the live-LLM tests; set `RUN_LIVE_LLM=1` to run them.

## Run

```bash
python -m src.api.main                        # API on http://127.0.0.1:8000, docs at /docs
python -m streamlit run app/streamlit_app.py  # UI; start the API first; run from the repo root
```

| Endpoint | Body | Returns |
|---|---|---|
| `GET /health` | | readiness: model, chunks, index, API key present |
| `POST /predict` | `{customer_id}` | churn score, label, top SHAP drivers (ids in the CSV only) |
| `POST /ask` | `{question, k?, mode?}` | status, answer, citations with source text, issues |
| `POST /agent` | `{question}` | status, answer, citations, full tool trace |
| `POST /report` | `{customer_id}` | tier, cited recommendations, withheld drafts, evidence, notes, markdown |

Command line: `python -m src.llm.answer "question"`, `python -m src.llm.report CUSTOMER_ID`, `python -m src.agent.agent "question"`. A walk-through is in [docs/DEMO.md](docs/DEMO.md).

## Rebuild from raw data (optional)

The committed model, `metrics.json`, `chunks.jsonl` and split are enough to run everything. To rebuild:

```bash
python -m scripts.audit_data
python -m src.ml.train                 # CV on the train split only; saves the model
python -m src.ml.train --final         # scores the test split ONCE and writes models/metrics.json
python -m src.docs.chunker             # writes data/processed/chunks.jsonl
python -m src.rag.index
```

Rebuilding changes the model and chunk ids, which makes `eval/results`, the gold labels and the LLM cache stale. Regenerating the synthetic documents (`uv sync --group synth`, then `python -m scripts.make_synthetic_docs`) has the same effect.

## Evaluation

Retrieval, generation, agent and ML evaluation are in `eval/`. Full tables: [docs/RESULTS.md](docs/RESULTS.md), generated from `eval/results`.

```bash
python -m eval.retrieval_eval --split dev                  # needs the index; no model calls
python -m eval.generation_eval --split dev --offline       # replays the committed cache; no API key
python -m eval.generation_eval --split agent --offline
python -m eval.ml_eval
python -m scripts.make_results_md --readme README.md
```

- **Gold questions:** 32 in `eval/gold_questions.json`, written from the synthetic documents. `tests/test_eval_gold.py` checks every label against `chunks.jsonl`.
- **Protocol:** the dev split was used to tune `DENSE_MIN_SIM`, fix prompts and check outputs. The held-out split was then run once, after prompts, threshold and retrieval mode were frozen. Published held-out numbers come from the `*_FROZEN` files.
- **LLM cache:** `eval/cache/llm_cache.jsonl` is keyed by prompt, messages and tool schemas. Changing a prompt misses the cache and calls the model, paced to fit Groq's token-per-minute limit. A "replayed" run reproduces recorded replies. It does not show that another model or another day would answer the same way.

## Limitations

- **Synthetic documents, synthetic questions.** The gold questions were written from the same synthetic text, so retrieval and answer scores are optimistic. Samples are small and there are no confidence intervals.
- **Retrieval has no reranker or de-duplication.** Near-identical chunks (lookup tables, tier-and-contract playbooks) crowd the rankings. On the held-out set BM25 ranked the right chunk higher than the hybrid mode (see the table). Hybrid was fixed before the held-out run, per the assignment, and is reported as is.
- **Refusal rests on two layers.** A dense-similarity threshold, tuned on four near-domain dev questions, stops questions far from the corpus. In-scope-looking questions the documents cannot answer pass retrieval, so only the model's `can_answer` and the validators stop them.
- **The validators check ids, digits and four document names, not meaning.** Numbers written as words are not checked, and answers can drop qualifiers such as "before add-ons and taxes". On the evaluation questions the validators rejected nothing. Their behaviour is shown by unit tests only.
- **The churn score is not a probability.** Class weights inflate it (the calibration table shows over-prediction in every bin). The tier boundaries come from the synthetic policy and are applied to this score, which is an assumption.
- **Model choice is not evidence.** The CV difference between the compared models is within fold-to-fold noise.
- **Customers.** `/predict` and reports work only for ids in the Telco CSV. Customers in the training split get in-sample scores, so use test-split ids for demos.
- **Support tickets** are indexed but excluded from answers, and they have no customer id, so they cannot be joined to customers.
- **One LLM provider.** Groq on the on-demand tier is limited to a few thousand tokens per minute, so quick repeat clicks can wait on retries. The first request after startup loads the embedding model.
- **Agent.** The tool timeout stops waiting but cannot kill a hung thread. The final answer is checked for ids and numbers but not for document attribution. Prompt injection was tested with one poisoned chunk on one model.
- **Hand checks.** Automatic fact matching is a lower bound. The hand-check lists in `eval/results/generation_*.md` are unmarked and left for a reviewer.
- **UI.** There is no browser-level test. Behaviour is covered by Streamlit's `AppTest` and a mocked-API client test.
- **`DOC_NAMES`**, the list the attribution check uses, is hard-coded for the four documents.

## Layout

```text
src/{config.py, ml, docs, rag, llm, agent, api}   app/   eval/   scripts/   tests/
data/{raw, processed}   models/   indexes/ (not committed)   docs/RESULTS.md, docs/DEMO.md
```