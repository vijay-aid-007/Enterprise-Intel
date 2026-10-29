# Generation evaluation: dev split

14 questions. Gold questions come from SYNTHETIC documents, so these scores are optimistic. Fact matching is automatic and a lower bound; check the answers listed at the end by hand.

## Answerable questions

| n | correct | answered_incomplete | refused | rejected | error |
|---|---|---|---|---|---|
| 8 | 5 | 2 | 1 | 0 | 0 |

## Out-of-scope and gap questions (refusal)

| type | n | refused | withheld | answered | error |
|---|---|---|---|---|---|
| out_of_scope | 4 | 4 | 0 | 0 | 0 |
| gap | 2 | 2 | 0 | 0 | 0 |

'answered' in this table is a failure: an unsupported question got an answer. 'withheld' means the model drafted something and the validators blocked it.

Validator rejection rate: 0/10 of the questions that reached the model (0.0). Rejected drafts are never shown; some rejections are correct answers with a derived number.

## Per question

| id | type | status | outcome |
|---|---|---|---|
| g01 | answerable | answered | correct |
| g02 | answerable | answered | correct |
| g03 | answerable | answered | answered_incomplete |
| g04 | answerable | answered | correct |
| g05 | answerable | refused_model | refused |
| g06 | answerable | answered | correct |
| g07 | out_of_scope | refused_insufficient_evidence | refused |
| g08 | out_of_scope | refused_insufficient_evidence | refused |
| g09 | gap | refused_model | refused |
| g10 | gap | refused_model | refused |
| g29 | answerable | answered | correct |
| g30 | answerable | answered | answered_incomplete |
| g31 | out_of_scope | refused_insufficient_evidence | refused |
| g32 | out_of_scope | refused_insufficient_evidence | refused |

## Hand check: every answer a user would see

For each, mark whether every claim is supported by the cited text (yes or no).

### g01 (answerable, correct)
Question: What is the absolute cap on any retention discount?
Answer: The absolute cap on any retention discount is 30 percent.
- `retention_policy-0002`: [2. Risk tiers and maximum discounts] Retention discounts apply to the internet plan charge only, never to add-ons or phone lines. The absolute cap on any retention discount is 30 percent. Only one retention offer may be active on an account at a time.
- `retention_policy-0038`: [Appendix C. Common situations > Situation 2] Situation: A customer asks for more than the tier maximum. Handling: Decline. No retention discount may exceed the tier maximum, and none may ever exceed the 30 percent cap, even with approval.
Supported by the cited text (hand): ____
Answers the question (hand): ____

### g02 (answerable, correct)
Question: What is the maximum retention discount for a Critical tier customer on a month-to-month contract, and who has to approve it?
Answer: The maximum retention discount is 30% of the internet plan list price for 6 months, and it must be approved by the retention manager.
- `retention_policy-0016`: [Appendix A. Playbook by tier and contract > Critical tier, Month-to-month customer] A customer on a month-to-month contract with a risk score of 0.80 and above is in the Critical tier and may receive the executive offer. The maximum retention discount is 30% of the internet plan list price for 6 months and needs approval from the retention manager. With the 0% contract discount that is 30% off, against the 40% combined cap. The agent may also offer a one-time $50 bill credit if the customer moves to a one-year contract. Log the ticket ID, tier, discount and duration. Also record the approver's name, because the discount is above 20%.
Supported by the cited text (hand): ____
Answers the question (hand): ____

### g03 (answerable, answered_incomplete)
Question: What combined discount ceiling applies to a Medium tier customer on a one year contract?
Answer: The combined discount ceiling is 15%.
- `facts_sheet-0071`: [Brightline Telecom - Facts Sheet > Lookup C. Combined discount ceilings > Discount ceiling: Medium tier, one year contract] A customer on a one year contract in the Medium tier has a combined discount ceiling of 15% (5% contract plus 10% retention). On Fiber optic that is $42.50 per month before add-ons, phone lines and the automatic payment credit.
Supported by the cited text (hand): ____
Answers the question (hand): ____

### g04 (answerable, correct)
Question: What is the combined discount ceiling for a Low tier customer on a month-to-month contract?
Answer: The combined discount ceiling is 0%.
- `facts_sheet-0067`: [Brightline Telecom - Facts Sheet > Lookup C. Combined discount ceilings > Discount ceiling: Low tier, month-to-month contract] A customer on a month-to-month contract in the Low tier has a combined discount ceiling of 0% (0% contract plus 0% retention). On Fiber optic that is $50 per month before add-ons, phone lines and the automatic payment credit.
Supported by the cited text (hand): ____
Answers the question (hand): ____

### g06 (answerable, correct)
Question: How many days after the invoice date is payment due?
Answer: Payment is due 15 days after the invoice date.
- `service_terms-0001`: [1. Billing] Invoices are issued monthly. Payment is due 15 days after the invoice date. A late fee of $5 applies to payments received more than 10 days after the due date. Billing disputes must be raised within 60 days of the invoice date.
Supported by the cited text (hand): ____
Answers the question (hand): ____

### g29 (answerable, correct)
Question: How much written notice do I have to give to cancel?
Answer: You must give 30 days written notice to cancel.
- `service_terms-0002`: [2. Cancellation and early termination] Customers must give 30 days written notice to cancel. Customers who cancel before the end of a fixed contract pay an early termination fee equal to the monthly fee in the table times the months remaining, up to the maximum. Month-to-month customers pay no fee.
- `service_terms-0102`: [Appendix F. Notice period dates] Thirty days of written notice are required to cancel.
Supported by the cited text (hand): ____
Answers the question (hand): ____

### g30 (answerable, answered_incomplete)
Question: How long do I have to send back my rented router after I cancel?
Answer: You must return the rented router within 14 days of cancelling your service.
- `service_terms-0089`: [Appendix E. Equipment return scenarios] Rented routers must be returned within 14 days of cancellation.
- `service_terms-0004`: [4. Equipment, refunds and records] Rented equipment must be returned within 14 days of cancellation. Equipment not returned in that time is charged at $100 per router. Eligible overpayments are refunded within 30 days. Brightline keeps account and billing records for 24 months after an account closes.
Supported by the cited text (hand): ____
Answers the question (hand): ____

Cache: 10 replayed, 0 new model calls.
