# ML evaluation

Churn data and labels are the REAL Telco dataset. The risk-tier boundaries come from the SYNTHETIC retention policy.

## Model comparison (5-fold CV on the training split)

| model | engineered features | CV PR-AUC (mean +/- std) | CV ROC-AUC | out-of-fold Brier |
|---|---|---|---|---|
| logreg | True | 0.6583 +/- 0.0219 | 0.8455 | 0.1654 |
| xgboost | True | 0.6606 +/- 0.0226 | 0.8449 | 0.1599 |
| logreg | False | 0.66 +/- 0.0218 | 0.846 | 0.1653 |
| xgboost | False | 0.6681 +/- 0.0241 | 0.8474 | 0.1599 |

Selected: xgboost (engineered features: False) by mean 5-fold PR-AUC on train. The spread of CV PR-AUC across the rows (0.0098) is smaller than the largest CV standard deviation (0.0241), so the choice follows the declared criterion and is not evidence that one model is better.

## Test split (n = 1409, decision threshold 0.5783 chosen on out-of-fold train predictions, evaluated once)

| PR-AUC | ROC-AUC | precision | recall | F1 | accuracy | Brier |
|---|---|---|---|---|---|---|
| 0.663 | 0.8446 | 0.5481 | 0.7166 | 0.6211 | 0.7679 | 0.1622 |

Confusion matrix on test: TN 814, FP 221, FN 106, TP 268. Training churn rate 0.2654, positive class weight 2.7686.

Note from train.py: Class weights inflate probabilities: prob is a risk score, not calibrated.
Note from train.py: cv_oof_at_threshold is optimistic: the threshold was tuned on the same predictions.

## Tiers on the test split (n = 1409, observed churn rate 0.2654, mean predicted 0.4004, Brier 0.1622)

| tier | customers | churned | observed churn rate | mean predicted probability |
|---|---|---|---|---|
| Low | 701 | 48 | 0.0685 | 0.1225 |
| Medium | 241 | 63 | 0.2614 | 0.4788 |
| High | 269 | 120 | 0.4461 | 0.7041 |
| Critical | 198 | 143 | 0.7222 | 0.8764 |

## Calibration on the test split

| probability bin | customers | churned | observed rate | mean predicted |
|---|---|---|---|---|
| 0.0 to 0.1 | 377 | 8 | 0.0212 | 0.0408 |
| 0.1 to 0.2 | 144 | 12 | 0.0833 | 0.1485 |
| 0.2 to 0.3 | 118 | 12 | 0.1017 | 0.2469 |
| 0.3 to 0.4 | 106 | 26 | 0.2453 | 0.344 |
| 0.4 to 0.5 | 98 | 21 | 0.2143 | 0.4497 |
| 0.5 to 0.6 | 99 | 32 | 0.3232 | 0.554 |
| 0.6 to 0.7 | 124 | 45 | 0.3629 | 0.6539 |
| 0.7 to 0.8 | 145 | 75 | 0.5172 | 0.7469 |
| 0.8 to 0.9 | 130 | 88 | 0.6769 | 0.8466 |
| 0.9 to 1.0 | 68 | 55 | 0.8088 | 0.9333 |

Consistency with models/metrics.json: n_matches_metrics_json: True, brier_matches_metrics_json: True.

The churn label uses the decision threshold above; the report tiers use the policy boundaries (Low from 0.0, Medium from 0.35, High from 0.6, Critical from 0.8). They are different cut-offs.
