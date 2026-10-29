# Retrieval evaluation: heldout split

18 questions. Gold questions come from SYNTHETIC documents, so these scores are optimistic. Relevance labels are not exhaustive.

## Ablation (answerable questions only)

| mode | n | hit@1 | hit@3 | hit@5 | MRR |
|---|---|---|---|---|---|
| dense | 14 | 3/14 | 9/14 | 9/14 | 0.429 |
| bm25 | 14 | 11/14 | 14/14 | 14/14 | 0.881 |
| hybrid | 14 | 8/14 | 12/14 | 12/14 | 0.711 |

## Refusal at the configured threshold (0.3)

| question type | refused / n |
|---|---|
| answerable | 0/14 |
| out_of_scope | 2/2 |
| gap | 0/2 |

Target: no answerable question refused, every out_of_scope question refused. Gap questions look in-scope to retrieval, so the model has to refuse them (generation eval).

## Threshold sweep (refuse when top dense similarity < threshold)

| threshold | answerable refused | out_of_scope refused | gap refused |
|---|---|---|---|
| 0.15 | 0/14 | 2/2 | 0/2 |
| 0.2 | 0/14 | 2/2 | 0/2 |
| 0.25 | 0/14 | 2/2 | 0/2 |
| 0.3 | 0/14 | 2/2 | 0/2 |
| 0.35 | 0/14 | 2/2 | 0/2 |
| 0.4 | 0/14 | 2/2 | 0/2 |
| 0.45 | 0/14 | 2/2 | 0/2 |
| 0.5 | 0/14 | 2/2 | 0/2 |
| 0.55 | 0/14 | 2/2 | 1/2 |
| 0.6 | 1/14 | 2/2 | 1/2 |
| 0.65 | 1/14 | 2/2 | 2/2 |
| 0.7 | 1/14 | 2/2 | 2/2 |

Suggested threshold (midpoint of the best out-of-scope and worst answerable score): 0.328
Sufficiency is dense-only at the configured threshold: True

## Per question

| id | type | top dense sim | rank dense | rank bm25 | rank hybrid | refused |
|---|---|---|---|---|---|---|
| g11 | answerable | 0.762 | miss | 1 | 7 | False |
| g12 | answerable | 0.813 | miss | 1 | 3 | False |
| g13 | answerable | 0.754 | 1 | 1 | 1 | False |
| g14 | answerable | 0.820 | 3 | 2 | 2 | False |
| g15 | answerable | 0.789 | miss | 2 | 7 | False |
| g16 | answerable | 0.706 | 1 | 1 | 1 | False |
| g17 | answerable | 0.778 | 3 | 1 | 1 | False |
| g18 | answerable | 0.819 | 2 | 1 | 1 | False |
| g19 | answerable | 0.800 | 6 | 1 | 3 | False |
| g20 | answerable | 0.551 | 2 | 1 | 1 | False |
| g21 | answerable | 0.750 | 2 | 1 | 1 | False |
| g22 | answerable | 0.823 | 2 | 1 | 1 | False |
| g23 | answerable | 0.724 | 6 | 1 | 1 | False |
| g24 | answerable | 0.766 | 1 | 3 | 2 | False |
| g25 | out_of_scope | 0.063 | n/a | n/a | n/a | True |
| g26 | out_of_scope | 0.105 | n/a | n/a | n/a | True |
| g27 | gap | 0.539 | n/a | n/a | n/a | False |
| g28 | gap | 0.623 | n/a | n/a | n/a | False |
