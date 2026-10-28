# Retrieval evaluation: dev split

14 questions. Gold questions come from SYNTHETIC documents, so these scores are optimistic. Relevance labels are not exhaustive.

## Ablation (answerable questions only)

| mode | n | hit@1 | hit@3 | hit@5 | MRR |
|---|---|---|---|---|---|
| dense | 8 | 6/8 | 7/8 | 7/8 | 0.812 |
| bm25 | 8 | 6/8 | 6/8 | 7/8 | 0.781 |
| hybrid | 8 | 6/8 | 7/8 | 7/8 | 0.812 |

## Refusal at the configured threshold (0.3)

| question type | refused / n |
|---|---|
| answerable | 0/8 |
| out_of_scope | 4/4 |
| gap | 0/2 |

Target: no answerable question refused, every out_of_scope question refused. Gap questions look in-scope to retrieval, so the model has to refuse them (generation eval).

## Threshold sweep (refuse when top dense similarity < threshold)

| threshold | answerable refused | out_of_scope refused | gap refused |
|---|---|---|---|
| 0.15 | 0/8 | 2/4 | 0/2 |
| 0.2 | 0/8 | 2/4 | 0/2 |
| 0.25 | 0/8 | 2/4 | 0/2 |
| 0.3 | 0/8 | 4/4 | 0/2 |
| 0.35 | 0/8 | 4/4 | 0/2 |
| 0.4 | 0/8 | 4/4 | 0/2 |
| 0.45 | 0/8 | 4/4 | 0/2 |
| 0.5 | 0/8 | 4/4 | 0/2 |
| 0.55 | 0/8 | 4/4 | 0/2 |
| 0.6 | 0/8 | 4/4 | 0/2 |
| 0.65 | 0/8 | 4/4 | 0/2 |
| 0.7 | 0/8 | 4/4 | 0/2 |

Suggested threshold (midpoint of the best out-of-scope and worst answerable score): 0.514
Sufficiency is dense-only at the configured threshold: True

## Per question

| id | type | top dense sim | rank dense | rank bm25 | rank hybrid | refused |
|---|---|---|---|---|---|---|
| g01 | answerable | 0.739 | 1 | 1 | 1 | False |
| g02 | answerable | 0.774 | 1 | 4 | 1 | False |
| g03 | answerable | 0.761 | 2 | 1 | 1 | False |
| g04 | answerable | 0.784 | 1 | 1 | 1 | False |
| g05 | answerable | 0.766 | miss | miss | miss | False |
| g06 | answerable | 0.780 | 1 | 1 | 1 | False |
| g07 | out_of_scope | 0.122 | n/a | n/a | n/a | True |
| g08 | out_of_scope | 0.127 | n/a | n/a | n/a | True |
| g09 | gap | 0.720 | n/a | n/a | n/a | False |
| g10 | gap | 0.787 | n/a | n/a | n/a | False |
| g29 | answerable | 0.747 | 1 | 1 | 1 | False |
| g30 | answerable | 0.812 | 1 | 1 | 2 | False |
| g31 | out_of_scope | 0.268 | n/a | n/a | n/a | True |
| g32 | out_of_scope | 0.290 | n/a | n/a | n/a | True |
