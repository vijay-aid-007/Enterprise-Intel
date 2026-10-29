# Generation evaluation: heldout split

18 questions. Gold questions come from SYNTHETIC documents, so these scores are optimistic. Fact matching is automatic and a lower bound; check the answers listed at the end by hand.

## Answerable questions

| n | correct | answered_incomplete | refused | rejected | error |
|---|---|---|---|---|---|
| 14 | 10 | 3 | 1 | 0 | 0 |

## Out-of-scope and gap questions (refusal)

| type | n | refused | withheld | answered | error |
|---|---|---|---|---|---|
| out_of_scope | 2 | 2 | 0 | 0 | 0 |
| gap | 2 | 2 | 0 | 0 | 0 |

'answered' in this table is a failure: an unsupported question got an answer. 'withheld' means the model drafted something and the validators blocked it.

Validator rejection rate: 0/16 of the questions that reached the model (0.0). Rejected drafts are never shown; some rejections are correct answers with a derived number.

## Per question

| id | type | status | outcome |
|---|---|---|---|
| g11 | answerable | refused_model | refused |
| g12 | answerable | answered | correct |
| g13 | answerable | answered | correct |
| g14 | answerable | answered | correct |
| g15 | answerable | answered | answered_incomplete |
| g16 | answerable | answered | correct |
| g17 | answerable | answered | correct |
| g18 | answerable | answered | correct |
| g19 | answerable | answered | correct |
| g20 | answerable | answered | answered_incomplete |
| g21 | answerable | answered | correct |
| g22 | answerable | answered | answered_incomplete |
| g23 | answerable | answered | correct |
| g24 | answerable | answered | correct |
| g25 | out_of_scope | refused_insufficient_evidence | refused |
| g26 | out_of_scope | refused_insufficient_evidence | refused |
| g27 | gap | refused_model | refused |
| g28 | gap | refused_model | refused |

## Hand check: every answer a user would see

For each, mark whether every claim is supported by the cited text (yes or no).

### g12 (answerable, correct)
Question: What is the total monthly price for DSL with 1 phone line on a month-to-month contract without automatic payment?
Answer: The total monthly price is $45 per month.
- `facts_sheet-0005`: [Brightline Telecom - Facts Sheet > Lookup A. Internet and phone bundle totals > Bundle total: DSL, 1 phone line, month-to-month, without automatic payment] DSL with 1 phone line on a month-to-month contract, without automatic payment: internet $25, phone $20, total $45 per month before add-ons and taxes.
Supported by the cited text (hand): ____
Answers the question (hand): ____

### g13 (answerable, correct)
Question: How much do Online Security and Online Backup cost together per month and per year?
Answer: Online Security and Online Backup together cost $10 per month and $120 per year.
- `facts_sheet-0051`: [Brightline Telecom - Facts Sheet > Lookup B. Add-on pairs > Add-on pair: Online Security and Online Backup] Online Security ($5) and Online Backup ($5) together cost $10 per month, or $120 per year.
Supported by the cited text (hand): ____
Answers the question (hand): ____

### g14 (answerable, correct)
Question: A High tier customer is up to date on payments but accepted a retention discount 6 months ago. Can they get another one?
Answer: No. The retention policy states that a High tier customer who is up to date on payments and accepted a retention discount 6 months ago is not eligible for another retention discount, though a 12‑month price lock may still be offered.
- `retention_policy-0051`: [Appendix D. Eligibility cases for High tier customers > Case 6: High tier, 0 days overdue] A High tier customer is up to date on payments, accepted a retention discount 6 months ago and is on a two-year contract with 3 months remaining. Result: the customer is not eligible for another retention discount, although a 12-month price lock may still be offered, because a retention discount was accepted in the last 12 months. If an offer is made, the agent logs the ticket ID, tier, discount and duration.
- `retention_policy-0049`: [Appendix D. Eligibility cases for High tier customers > Case 4: High tier, 0 days overdue] A High tier customer is up to date on payments, accepted a retention discount 6 months ago and is on a month-to-month contract. Result: the customer is not eligible for another retention discount, although a 12-month price lock may still be offered, because a retention discount was accepted in the last 12 months. If an offer is made, the agent logs the ticket ID, tier, discount and duration.
- `retention_policy-0050`: [Appendix D. Eligibility cases for High tier customers > Case 5: High tier, 0 days overdue] A High tier customer is up to date on payments, accepted a retention discount 6 months ago and is on a two-year contract with 8 months remaining. Result: the customer is not eligible for another retention discount, although a 12-month price lock may still be offered, because a retention discount was accepted in the last 12 months. If an offer is made, the agent logs the ticket ID, tier, discount and duration.
Supported by the cited text (hand): ____
Answers the question (hand): ____

### g15 (answerable, answered_incomplete)
Question: Does a Low tier customer on a one year contract qualify for any retention discount?
Answer: No. The facts sheet states that a Low tier customer on a one‑year contract has a combined discount ceiling of 5% (5% contract plus 0% retention), meaning they receive no retention discount.
- `facts_sheet-0068`: [Brightline Telecom - Facts Sheet > Lookup C. Combined discount ceilings > Discount ceiling: Low tier, one year contract] A customer on a one year contract in the Low tier has a combined discount ceiling of 5% (5% contract plus 0% retention). On Fiber optic that is $47.50 per month before add-ons, phone lines and the automatic payment credit.
Supported by the cited text (hand): ____
Answers the question (hand): ____

### g16 (answerable, correct)
Question: What should an agent do when a customer asks for more than the tier maximum discount?
Answer: The agent should decline the request—no retention discount may exceed the tier‑maximum discount (or the overall 30 % cap), even with approval.
- `retention_policy-0038`: [Appendix C. Common situations > Situation 2] Situation: A customer asks for more than the tier maximum. Handling: Decline. No retention discount may exceed the tier maximum, and none may ever exceed the 30 percent cap, even with approval.
Supported by the cited text (hand): ____
Answers the question (hand): ____

### g17 (answerable, correct)
Question: How many outbound retention calls per day can a retention team of 2 agents make?
Answer: A retention team of 2 agents can make at most 50 outbound retention calls per day.
- `facts_sheet-0081`: [Brightline Telecom - Facts Sheet > Lookup D. Retention team capacity > Retention capacity: 2 agents] A retention team of 2 agents can make at most 50 outbound retention calls per day.
Supported by the cited text (hand): ____
Answers the question (hand): ____

### g18 (answerable, correct)
Question: On Fiber optic, what does a High tier customer on a month-to-month contract pay per month at the combined discount ceiling?
Answer: $40 per month.
- `facts_sheet-0073`: [Brightline Telecom - Facts Sheet > Lookup C. Combined discount ceilings > Discount ceiling: High tier, month-to-month contract] A customer on a month-to-month contract in the High tier has a combined discount ceiling of 20% (0% contract plus 20% retention). On Fiber optic that is $40 per month before add-ons, phone lines and the automatic payment credit.
Supported by the cited text (hand): ____
Answers the question (hand): ____

### g19 (answerable, correct)
Question: How much does each additional phone line cost after the first one?
Answer: Each additional phone line costs $5 per month after the first line.
- `plans_pricing_guide-0003`: [Phone service] The first phone line costs $20 per month. Each additional line costs $5 per month.
Supported by the cited text (hand): ____
Answers the question (hand): ____

### g20 (answerable, answered_incomplete)
Question: Can the new customer promotion be offered to existing customers to keep them?
Answer: No. The new customer promotion is limited to new sign‑ups only and cannot be used as a retention offer for existing customers.
- `plans_pricing_guide-0007`: [New customer promotion] New customers get 15% off the internet plan list price for the first 3 months. This promotion is for new sign-ups only and cannot be given to existing customers as a retention offer.
- `retention_policy-0039`: [Appendix C. Common situations > Situation 3] Situation: A customer asks to combine a retention discount with the new customer promotion. Handling: Refuse. The promotion is for new sign-ups only, and retention discounts do not stack with it.
- `retention_policy-0003`: [3. Eligibility exclusions] - A customer who accepted a retention discount in the last 12 months is not eligible for another. - Accounts more than 60 days overdue are not eligible for any discount. - Two-year contract customers with more than 6 months remaining get a 12-month price lock, not a discount. - The new customer promotion is for new sign-ups only and can never be used as a retention offer. A price lock is not a discount, so the first two exclusions do not stop an agent from offering one.
Supported by the cited text (hand): ____
Answers the question (hand): ____

### g21 (answerable, correct)
Question: What is the monthly total for Fiber optic on a two year contract with Device Protection, Streaming TV and Streaming Movies?
Answer: The monthly total is $70 per month.
- `plans_pricing_guide-0139`: [Appendix E. Plan plus three add-ons > Trio: Fiber optic, two year, Device Protection, Streaming TV and Streaming Movies] Fiber optic on a two year contract with Device Protection, Streaming TV and Streaming Movies: internet $45, add-ons $25, total $70 per month before phone lines, the automatic payment credit and taxes.
Supported by the cited text (hand): ____
Answers the question (hand): ____

### g22 (answerable, answered_incomplete)
Question: What is the early termination fee for a two year contract cancelled with 5 months remaining?
Answer: The early termination fee is $100.
- `service_terms-0017`: [Appendix A. Early termination examples > Early termination: two year contract, 5 months remaining] A customer on a two year contract cancels with 5 months remaining. The fee is 5 x $20 = $100, which is within the $300 maximum, so $100 is charged. The customer must still give 30 days written notice and pay the final invoice.
Supported by the cited text (hand): ____
Answers the question (hand): ____

### g23 (answerable, correct)
Question: By when must an Urgent ticket opened at 8:00 get its first response?
Answer: An Urgent ticket opened at 8:00 must have its first response by 9:00 the same day.
- `facts_sheet-0101`: [Brightline Telecom - Facts Sheet > Lookup E. First response deadlines > Deadline: Urgent ticket opened at 8:00] An Urgent ticket opened at 8:00 must have a first response by 9:00 the same day. Support hours count only between 8:00 and 22:00.
Supported by the cited text (hand): ____
Answers the question (hand): ____

### g24 (answerable, correct)
Question: What is the total per month for DSL on a month-to-month contract with Online Security and Online Backup?
Answer: The plans pricing guide states the total is $35 per month for DSL on a month-to-month contract with Online Security and Online Backup.
- `plans_pricing_guide-0012`: [Appendix A. Monthly price examples > DSL, month-to-month, Secure bundle, without automatic payment] DSL on a month-to-month contract with Online Security and Online Backup, without automatic payment: the internet plan is $25 less 0%, which is $25; add-ons cost $10; the total is $35 per month. Prices exclude phone lines and taxes.
- `plans_pricing_guide-0013`: [Appendix A. Monthly price examples > DSL, month-to-month, Secure bundle, paid by automatic payment] DSL on a month-to-month contract with Online Security and Online Backup, paid by automatic payment: the internet plan is $25 less 0%, which is $25; add-ons cost $10; the total is $35 per month, and the $5 automatic payment credit brings it to $30. Prices exclude phone lines and taxes.
Supported by the cited text (hand): ____
Answers the question (hand): ____

Cache: 16 replayed, 0 new model calls.
