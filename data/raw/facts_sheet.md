# Vantage Telecom: Company Facts Sheet

> **SYNTHETIC DOCUMENT.** Vantage Telecom is a fictional company. Every price, discount, rule, date and support hour in this sheet was invented for a software assignment. None of it is a fact about any real company or about the Kaggle dataset. The only exception is Section 8, whose statistics were computed directly from the real file `telco-customer-churn.csv`.

Version 1.0 | Effective date: 2026-01-01 | Owner: Customer Operations (fictional)

## 1. Purpose and how to use this sheet

This sheet is the single source of truth for the numbers used across the Vantage Telecom document set. The Retention Policy (`retention_policy.pdf`), the Plans and Pricing Guide (`plans_pricing_guide.docx`), the Service Terms (`service_terms.pdf`) and the support ticket export (`support_tickets.csv`) repeat or refine these facts. Where they add detail, they do not contradict this sheet.

Agents, analysts and automated assistants should quote figures exactly as written here. All money amounts are in US dollars and are monthly unless stated otherwise. Percentages are percentages of the list price total, which is defined in Section 4. Prices exclude taxes and regulatory fees, which are added to the invoice separately.

If a question is not answered by this sheet or by the other documents in the set, the correct response is to say that the documents do not cover it. Staff must not guess or fill gaps from general telecom knowledge.

## 2. Services and list prices

Vantage Telecom sells phone service and internet service, plus optional add-on services. The names below match the field names used in the customer data export so that analysts can map a customer record to the services described here.

### 2.1 Phone service

The base phone line (field `PhoneService`) costs $20.00 per month. A customer may add extra lines (field `MultipleLines`). Each additional line costs $5.00 per month. An account can have at most 4 lines in total, which means at most 3 additional lines. A customer without phone service has the value "No phone service" in the `MultipleLines` field.

### 2.2 Internet service

Internet service (field `InternetService`) comes in two types. A customer with no internet has the value "No".

- **DSL** costs $30.00 per month and offers speeds of up to 50 Mbps.
- **Fiber optic** costs $55.00 per month and offers speeds of up to 1000 Mbps (1 Gbps).

Actual speeds depend on the customer's location and equipment. Internet service can be bought with or without phone service.

### 2.3 Add-on services

Add-ons are only available to customers who have DSL or Fiber optic internet. A customer with no internet has the value "No internet service" in every add-on field. Each add-on is a separate monthly charge.

| Add-on | Data field | Price per month | What it includes |
| --- | --- | --- | --- |
| Online Security | `OnlineSecurity` | $5.00 | Security software for up to 3 devices |
| Online Backup | `OnlineBackup` | $5.00 | 100 GB of cloud storage |
| Device Protection | `DeviceProtection` | $5.00 | One replacement of the Vantage-supplied router or modem per rolling 12 months, with a $25.00 deductible |
| Tech Support | `TechSupport` | $5.00 | Priority support line and priority ticket response (see Section 6) |
| Streaming TV | `StreamingTV` | $10.00 | A package of 60 live channels |
| Streaming Movies | `StreamingMovies` | $10.00 | An on-demand movie library with up to 2 simultaneous streams |

### 2.4 List price summary

| Item | Monthly list price |
| --- | --- |
| Phone line (base) | $20.00 |
| Additional phone line | $5.00 each |
| DSL internet | $30.00 |
| Fiber optic internet | $55.00 |
| Online Security | $5.00 |
| Online Backup | $5.00 |
| Device Protection | $5.00 |
| Tech Support | $5.00 |
| Streaming TV | $10.00 |
| Streaming Movies | $10.00 |

The list price total is the sum of the list prices of everything on the account. A fully loaded account (phone, 3 additional lines, Fiber optic and all six add-ons) has a list price total of $130.00. These list prices are synthetic and are not claimed to reproduce the monthly charges in the real dataset.

## 3. Contracts

Every account is on one of three contract types (field `Contract`).

| Contract | Term | Contract discount | Early termination fee |
| --- | --- | --- | --- |
| Month-to-month | None, renews monthly | 0% | None |
| One year | 12 months | 5% | Yes, see below |
| Two year | 24 months | 10% | Yes, see below |

The contract discount is a percentage taken off the list price total for as long as the contract is active.

**Early termination fee.** A customer on a One year or Two year contract who cancels before the term ends pays an early termination fee of $12.00 for each full month remaining in the term. The fee is capped at $250.00. For example, a customer cancelling with 7 full months remaining pays $84.00, and a customer cancelling with 22 full months remaining would owe $264.00 before the cap, so pays $250.00. Month-to-month accounts never pay an early termination fee.

**End of term.** When a One year or Two year term ends, the account automatically becomes a Month-to-month account and loses its contract discount unless the customer signs a new term. Customers receive a reminder 30 days before the term ends.

**Cancellation timing.** A cancellation takes effect at the end of the current billing cycle. No refund is given for a partial month.

## 4. How the monthly bill is calculated

The monthly bill is calculated in this fixed order.

1. Add up the list prices of every service and add-on on the account. This is the **list price total**.
2. Add the contract discount percentage and any retention discount percentage. This is the **combined percentage discount**.
3. If the combined percentage discount is more than 25%, reduce it to 25%. **The maximum total percentage discount on any account is 25%.**
4. Multiply the list price total by (1 minus the combined percentage discount).
5. Subtract any fixed credits. The only fixed credit is the autopay credit of $5.00 per month, given to accounts that pay by Bank transfer (automatic) or Credit card (automatic).
6. If the result is below $15.00, the bill is $15.00. **The minimum monthly bill is $15.00.**

Fixed credits are never counted toward the 25% cap, because they are not percentages.

### Worked examples

**Example 1.** Phone and DSL, Month-to-month, paying by Electronic check. List price total is $20.00 + $30.00 = $50.00. The contract discount is 0%, there is no autopay credit, so the bill is **$50.00**.

**Example 2.** Phone, Fiber optic, Tech Support and Streaming TV on a One year contract, paying by Credit card (automatic). List price total is $20.00 + $55.00 + $5.00 + $10.00 = $90.00. The contract discount is 5%, so $90.00 x 0.95 = $85.50. After the $5.00 autopay credit the bill is **$80.50**.

**Example 3.** Phone, 1 additional line, Fiber optic and all six add-ons, on a Two year contract with a Win-back retention offer of 20%. List price total is $20.00 + $5.00 + $55.00 + $5.00 + $5.00 + $5.00 + $5.00 + $10.00 + $10.00 = $120.00. The combined percentage discount is 10% + 20% = 30%, which is reduced to the 25% cap. So $120.00 x 0.75 = $90.00. The customer pays by Bank transfer (automatic), so after the $5.00 credit the bill is **$85.00**.

**Example 4.** Phone only (one line) on a Two year contract, paying by Bank transfer (automatic). The list price total is $20.00. The contract discount is 10%, so $20.00 x 0.90 = $18.00. After the $5.00 autopay credit the result is $13.00, which is below the minimum, so the bill is **$15.00**.

## 5. Billing, payment and late payment

Customers can pay by four methods (field `PaymentMethod`): Electronic check, Mailed check, Bank transfer (automatic) and Credit card (automatic). The two automatic methods qualify for the $5.00 autopay credit. Customers can choose paperless billing (field `PaperlessBilling`) or paper statements. Paperless billing has no price difference and no credit.

Invoices are issued on the first day of each billing cycle and payment is due 15 days after the invoice date. A payment that arrives after the due date incurs a late fee of $7.50. The late fee is charged once per invoice and is not charged again if the invoice stays unpaid.

An account is **overdue** from the day after the due date. The number of days overdue is counted from that day. An account that is more than 45 days overdue is suspended. Suspended accounts can be reconnected once the balance is paid and a reconnection fee of $25.00 is paid.

If a customer disputes a charge, the disputed amount is not suspended for non-payment while the dispute is open, and the dispute must be raised within 60 days of the invoice date.

## 6. Support and service levels

Standard customer support is available Monday to Saturday from 08:00 to 20:00 local time and is closed on Sundays. Customers can contact support by phone or by raising a ticket.

**Standard tickets** receive a first response within 2 business days.

**Tech Support add-on customers** can use a priority phone line that is open 24 hours a day, 7 days a week. Their tickets receive a first response within 4 hours.

**Technician visits.** A visit to a customer's premises normally costs $60.00. Customers with the Tech Support add-on get one visit free in each rolling 12 months, and further visits in the same period cost $60.00.

**Device replacement.** Customers with Device Protection can have the Vantage-supplied router or modem replaced once in each rolling 12 months, paying a deductible of $25.00. Customers without Device Protection pay the full replacement price listed in the Service Terms.

## 7. Retention program summary

The retention program gives eligible customers a limited-time offer when they are at risk of leaving. This section summarizes the program. The Retention Policy (`retention_policy.pdf`) contains the full rules, and where it adds detail it does not change the figures here.

| Offer | Name | Benefit | Duration | Who qualifies |
| --- | --- | --- | --- | --- |
| A | Loyalty credit | 10% retention discount | 3 billing months | Any account with a tenure of 6 months or more |
| B | Upgrade incentive | 15% retention discount | 6 billing months | Month-to-month accounts that commit to a One year or Two year contract |
| C | Service review | Free Tech Support add-on (worth $5.00 per month) | 3 billing months | Accounts that have internet service but no Tech Support |
| D | Win-back | 20% retention discount | 6 billing months | Former customers who return within 30 days of cancelling and choose any contract |

**Rules that apply to every offer.**

- An account can receive at most one retention offer in any rolling 12 months.
- The maximum retention discount is 20%. Retention discounts are added to the contract discount, and the combined percentage discount is capped at 25% as described in Section 4.
- Any offer above 15% needs approval from a team lead. In practice this applies to Offer D only.
- An account that is more than 30 days overdue is not eligible for any retention offer.
- Percentage discounts last for at most 6 billing months. After that, the account reverts to its normal bill.
- Offer C is not a percentage discount, so it does not count toward the 25% cap.

Accounts that the analytics team's churn model flags as high risk should be reviewed for an offer. A risk flag prompts a review but does not oblige an agent to make an offer, and the final decision is made by the agent handling the customer.

## 8. Observed customer base statistics (real data, computed)

> **These statistics are real.** They were computed by a script from `telco-customer-churn.csv`, the Kaggle customer churn dataset, and are the only real figures in this sheet. They describe a historical sample. They show associations, not causes. The rules in Sections 3 and 7 were not derived from them, and no reader should conclude that a contract type, payment method or service makes customers leave.

The file contains 7,043 customers. The overall churn rate is 26.5%. Monthly charges range from 18.25 to 118.75, with a median of 70.35. Tenure ranges from 0 to 72 months, with a median of 29 months.

**Churn rate by contract type**

| Contract | Customers | Churn rate |
| --- | --- | --- |
| Month-to-month | 3,875 | 42.7% |
| One year | 1,473 | 11.3% |
| Two year | 1,695 | 2.8% |

**Churn rate by internet service**

| InternetService | Customers | Churn rate |
| --- | --- | --- |
| DSL | 2,421 | 19.0% |
| Fiber optic | 3,096 | 41.9% |
| No | 1,526 | 7.4% |

**Churn rate by payment method**

| PaymentMethod | Customers | Churn rate |
| --- | --- | --- |
| Bank transfer (automatic) | 1,544 | 16.7% |
| Credit card (automatic) | 1,522 | 15.2% |
| Electronic check | 2,365 | 45.3% |
| Mailed check | 1,612 | 19.1% |

**Churn rate by paperless billing**

| PaperlessBilling | Customers | Churn rate |
| --- | --- | --- |
| No | 2,872 | 16.3% |
| Yes | 4,171 | 33.6% |

**Churn rate by tech support**

| TechSupport | Customers | Churn rate |
| --- | --- | --- |
| No | 3,473 | 41.6% |
| No internet service | 1,526 | 7.4% |
| Yes | 2,044 | 15.2% |

**Churn rate by senior citizen flag**

| SeniorCitizen | Customers | Churn rate |
| --- | --- | --- |
| 0 | 5,901 | 23.6% |
| 1 | 1,142 | 41.7% |

**Churn rate by tenure band**

| Tenure band (months) | Customers | Churn rate |
| --- | --- | --- |
| 0 to 12 | 2,186 | 47.4% |
| 13 to 24 | 1,024 | 28.7% |
| 25 to 48 | 1,594 | 20.4% |
| 49 to 72 | 2,239 | 9.5% |

Two points help readers avoid mistakes. First, the 1,526 customers with no internet service are the same customers in both the "No" row of the internet table and the "No internet service" row of the tech support table, which is why both show 7.4%. Second, the dataset describes customers who had left within the last month as churned, so the churn rate is a snapshot and not a yearly figure.

## 9. Glossary and field definitions

- **customerID**: the unique customer identifier. It has the format of four digits, a hyphen, and five uppercase letters.
- **Churn**: "Yes" if the customer left within the last month, otherwise "No".
- **tenure**: the number of months the customer has been with the company.
- **MonthlyCharges**: the amount currently charged to the customer each month.
- **TotalCharges**: the total amount charged to the customer so far. In the raw file this value is blank for brand-new accounts with a tenure of 0.
- **SeniorCitizen**: whether the customer is a senior citizen, stored as 0 for no and 1 for yes.
- **List price total**: the sum of the list prices on an account before any discount (Section 4).
- **Combined percentage discount**: the contract discount plus any retention discount, capped at 25% (Section 4).
- **Overdue**: the state of an account that has not paid by the due date, counted in days from the day after the due date (Section 5).
- **Rolling 12 months**: the 12 months immediately before the date in question, not the calendar year.
- **Retention offer**: one of Offers A to D in Section 7.

## 10. Document control

This is version 1.0 of the sheet, effective 2026-01-01. Changes to any price, discount or rule must be made in this sheet first and then copied into the other documents in the set. A change takes effect on the first day of the next billing cycle after it is published, and customers are notified at least 30 days before a price increase takes effect.
