# # scripts/synth_docs.py
# """Hand-written cores plus computed appendix families for the retention policy,
# service terms and plans guide. Every family item is distinct (different numbers
# and outcomes); assemble() adds items until a document reaches TARGET words."""
# from __future__ import annotations

# from datetime import date, timedelta
# from itertools import permutations, product

# from scripts.synth_rules import (
#     ADDONS, AUTOPAY, COMBINED_CAP, CONTRACTS, CREDIT_1Y, CREDIT_2Y, LATE_FEE, PHONE_EXTRA,
#     PHONE_FIRST, PLANS, RETENTION_CAP, ROUTER_FEE, TIERS, Sec, assemble, cents, eligibility,
#     etf, internet_cents, outage_credit_cents, outage_days, phone_dollars, plural, usd)

# Fam = tuple[Sec, list[Sec]]


# def item(heading: str, text: str) -> Sec:
#     """A level-2 appendix entry."""
#     return Sec(heading, [text], level=2)


# def fam(title: str, intro: str, items: list[Sec]) -> Fam:
#     """An appendix: heading with intro, plus its candidate items."""
#     return Sec(title, [intro]), items


# def retention() -> list[Sec]:
#     """Retention policy: core sections plus appendices A-D."""
#     table = [["Tier", "Risk score", "Offer", "Max discount", "Duration", "Approval"]] + [
#         [t, sc, o.capitalize(), f"{p}%", f"{m} months" if m else "n/a", a.capitalize()]
#         for t, sc, o, p, m, a in TIERS]
#     core = [
#         Sec("1. Purpose and scope", [
#             "This policy tells Brightline Telecom retention agents which offers they may make to customers who are at risk of leaving. It applies to residential customers only.",
#             "Risk tiers use the churn risk score from the churn model. The score ranks customers by risk. It is not a calibrated probability, and agents must not quote it to customers."]),
#         Sec("2. Risk tiers and maximum discounts", [
#             f"Retention discounts apply to the internet plan charge only, never to add-ons or phone lines. The absolute cap on any retention discount is {RETENTION_CAP} percent. Only one retention offer may be active on an account at a time."], table),
#         Sec("3. Eligibility exclusions", [
#             "- A customer who accepted a retention discount in the last 12 months is not eligible for another.",
#             "- Accounts more than 60 days overdue are not eligible for any discount.",
#             "- Two-year contract customers with more than 6 months remaining get a 12-month price lock, not a discount.",
#             "- The new customer promotion is for new sign-ups only and can never be used as a retention offer.",
#             "A price lock is not a discount, so the first two exclusions do not stop an agent from offering one."]),
#         Sec("4. Contract offers, price locks and documentation", [
#             f"A month-to-month customer who accepts a one-year contract receives a one-time bill credit of {usd(CREDIT_1Y)}. A one-year customer who renews for two years receives a one-time bill credit of {usd(CREDIT_2Y)}.",
#             "A price lock guarantees the internet plan price for 12 months. Agents may offer it at any tier and it needs no approval.",
#             "Every offer must be logged with the ticket ID, tier, discount and duration. Offers above 20 percent must also record the approver's name."]),
#         Sec("5. How retention discounts combine with other discounts", [
#             f"Contract discounts (5 percent for a one-year contract, 10 percent for a two-year contract) and the {usd(AUTOPAY)} automatic payment credit are standing entitlements and still apply when a retention discount is given. Percentages are added together, not multiplied, and are taken from the list price of the internet plan.",
#             f"The combined percentage discount on the internet plan may never exceed {COMBINED_CAP} percent. The automatic payment credit is taken off the total monthly bill after percentage discounts. A retention discount does not stack with another retention discount or with the new customer promotion."])]

#     play = []
#     for tier, score, offer, pct, months, appr in TIERS:
#         for contract, (cpct, _, _) in CONTRACTS.items():
#             apv = "can be approved by the agent" if appr == "agent" else f"needs approval from the {appr}"
#             disc = ("No retention discount is available at this tier. The agent makes a courtesy call and may offer a 12-month price lock."
#                     if not pct else
#                     f"The maximum retention discount is {pct}% of the internet plan list price for {months} months and {apv}. With the {cpct}% contract discount that is {pct + cpct}% off, against the {COMBINED_CAP}% combined cap.")
#             ctr = {"Two year": "If more than 6 months remain, the agent may offer only a 12-month price lock; with 6 months or fewer remaining the tier discount applies.",
#                    "One year": f"The agent may also offer a one-time {usd(CREDIT_2Y)} bill credit if the customer renews for two years.",
#                    "Month-to-month": f"The agent may also offer a one-time {usd(CREDIT_1Y)} bill credit if the customer moves to a one-year contract."}[contract]
#             log = "Log the ticket ID, tier, discount and duration." + (
#                 " Also record the approver's name, because the discount is above 20%." if pct > 20 else "")
#             play.append(item(f"{tier} tier, {contract} customer",
#                              f"A customer on a {contract.lower()} contract with a risk score of {score} is in the {tier} tier and may receive the {offer}. {disc} {ctr} {log}"))

#     ex, i = [], 0
#     for tier, _, _, pct, months, _ in TIERS:
#         for plan, (speed, price, _) in PLANS.items():
#             for auto in (False, True):
#                 contract = list(CONTRACTS)[i % 3]
#                 i += 1
#                 cpct = CONTRACTS[contract][0]
#                 left = " and 4 months remaining" if contract == "Two year" else ""
#                 pay = "pays by automatic payment" if auto else "does not use automatic payment"
#                 base = internet_cents(plan, contract, 0, auto)
#                 head = (f"A customer on {plan} ({speed}, list price {usd(price)}) with a {contract.lower()} contract{left} "
#                         f"is in the {tier} tier and {pay}. The contract discount is {cpct}%")
#                 if pct:
#                     now = internet_cents(plan, contract, pct, auto)
#                     res = (f", less the {usd(AUTOPAY)} automatic payment credit, giving {cents(now)}" if auto
#                            else f", giving {cents(now)}")
#                     body = (f" and the maximum retention discount is {pct}%, so the combined discount is {cpct + pct}%. "
#                             f"The internet charge is {usd(price)} x (100% - {cpct + pct}%) = {cents(price * (100 - cpct - pct))}{res} "
#                             f"per month for {months} months. Afterwards the customer pays {cents(base)} per month.")
#                 else:
#                     body = (f". There is no retention discount at this tier, so the internet charge stays at {cents(base)} per month"
#                             + (f" after the {usd(AUTOPAY)} automatic payment credit." if auto else "."))
#                 ex.append(item(f"Example {i}: {tier} tier on {plan}", head + body))

#     sit = [
#         ("A customer says a competitor is cheaper and asks to cancel.", "Check the risk tier. Because the customer raised cancellation, the agent may present the tier offer. At the Low tier there is no discount, so the agent offers a courtesy call and may offer a 12-month price lock."),
#         ("A customer asks for more than the tier maximum.", f"Decline. No retention discount may exceed the tier maximum, and none may ever exceed the {RETENTION_CAP} percent cap, even with approval."),
#         ("A customer asks to combine a retention discount with the new customer promotion.", "Refuse. The promotion is for new sign-ups only, and retention discounts do not stack with it."),
#         ("A customer accepted a retention discount 8 months ago and calls again.", "The customer is not eligible for another discount, because 8 months is inside the 12-month window. A price lock may still be offered."),
#         ("A customer wants the discount applied to Streaming TV.", "Retention discounts apply to the internet plan charge only, never to add-ons."),
#         ("A customer on a two-year contract with 10 months left threatens to leave.", "Offer only the 12-month price lock, because more than 6 months remain. If the customer cancels anyway, the early termination fee in the service terms applies."),
#         ("A Critical tier offer is ready to close but the approver is not recorded.", "The offer is incomplete. Offers above 20 percent must record the approver's name, so add it before the ticket is closed."),
#         ("A customer asks the agent to quote their churn score.", "Do not quote it. The score is an internal ranking signal and not a probability.")]
#     sits = [item(f"Situation {n}", f"Situation: {a} Handling: {b}") for n, (a, b) in enumerate(sit, 1)]

#     cases = []
#     grid = product((0, 60, 61, 90), (None, 6, 18), (("Month-to-month", 0), ("Two year", 8), ("Two year", 3)))
#     for n, (od, last, (contract, rem)) in enumerate(grid, 1):
#         outcome, reason = eligibility(od, last, contract, rem)
#         pay = "is up to date on payments" if od == 0 else f"is {od} days overdue"
#         hist = "has never accepted a retention discount" if last is None else f"accepted a retention discount {last} months ago"
#         ctr = ("is on a month-to-month contract" if contract == "Month-to-month"
#                else f"is on a two-year contract with {rem} months remaining")
#         cases.append(item(f"Case {n}: High tier, {od} days overdue",
#                           f"A High tier customer {pay}, {hist} and {ctr}. Result: the customer is {outcome}, because {reason}. If an offer is made, the agent logs the ticket ID, tier, discount and duration."))
#     return assemble(core, [
#         fam("Appendix A. Playbook by tier and contract", "These entries restate sections 2 to 5 for each tier and contract type.", play),
#         fam("Appendix B. Worked pricing examples", "Each example shows the internet plan charge. Percentages add; the automatic payment credit is taken off last.", ex),
#         fam("Appendix C. Common situations", "How to handle situations agents meet often.", sits),
#         fam("Appendix D. Eligibility cases for High tier customers", "Exclusions are checked in this order: overdue, recent discount, contract remaining.", cases)])


# def terms() -> list[Sec]:
#     """Service terms: core sections plus appendices A-F."""
#     tbl = [["Contract", "Fee per remaining month", "Maximum fee"]] + [
#         [c, usd(f), usd(m)] for c, (_, f, m) in CONTRACTS.items()]
#     core = [
#         Sec("1. Billing", [
#             f"Invoices are issued monthly. Payment is due 15 days after the invoice date. A late fee of {usd(LATE_FEE)} applies to payments received more than 10 days after the due date.",
#             "Billing disputes must be raised within 60 days of the invoice date."]),
#         Sec("2. Cancellation and early termination", [
#             "Customers must give 30 days written notice to cancel. Customers who cancel before the end of a fixed contract pay an early termination fee equal to the monthly fee in the table times the months remaining, up to the maximum. Month-to-month customers pay no fee."], tbl),
#         Sec("3. Service levels", [
#             "Monthly availability targets are 99.5 percent for Fiber optic plans and 99.0 percent for DSL.",
#             "For an outage longer than 4 hours, the customer receives a credit for each 24 hours of outage or part of 24 hours. One day of credit is 1/30 of the list price of the customer's internet plan, rounded to the nearest cent."]),
#         Sec("4. Equipment, refunds and records", [
#             f"Rented equipment must be returned within 14 days of cancellation. Equipment not returned in that time is charged at {usd(ROUTER_FEE)} per router.",
#             "Eligible overpayments are refunded within 30 days. Brightline keeps account and billing records for 24 months after an account closes."])]

#     fees = []
#     for contract, ms in (("One year", (1, 2, 3, 4, 6, 8, 10, 11, 12)), ("Two year", (1, 3, 5, 7, 9, 10, 12, 15, 18, 20, 22, 24))):
#         _, per, cap = CONTRACTS[contract]
#         for m in ms:
#             note = (f"which is above the {usd(cap)} maximum, so the fee is capped at {usd(cap)}" if per * m > cap
#                     else f"which is within the {usd(cap)} maximum, so {usd(etf(contract, m))} is charged")
#             fees.append(item(f"Early termination: {contract.lower()} contract, {m} months remaining",
#                              f"A customer on a {contract.lower()} contract cancels with {m} months remaining. The fee is {m} x {usd(per)} = {usd(per * m)}, {note}. The customer must still give 30 days written notice and pay the final invoice."))
#     late = []
#     for d in (10, 15, 16, 20, 24, 25, 26, 30, 35, 40, 45, 60):
#         res = ("The payment was on time, so no fee applies." if d <= 15 else
#                f"The payment was {d - 15} days after the due date. That is not more than 10 days late, so no late fee applies." if d <= 25 else
#                f"The payment was {d - 15} days after the due date, which is more than 10 days late, so the {usd(LATE_FEE)} late fee applies.")
#         late.append(item(f"Late fee: payment received {d} days after the invoice date",
#                          f"An invoice is issued on day 0 and payment is due on day 15. Payment arrives on day {d}. {res}"))
#     disp = [item(f"Billing dispute raised {d} days after the invoice date",
#                  f"A customer raises a billing dispute {d} days after the invoice date. Disputes must be raised within 60 days, so the dispute is " + ("accepted for review." if d <= 60 else "too late and is declined."))
#             for d in (5, 30, 59, 60, 61, 75, 90)]
#     out = []
#     for plan, h in product(PLANS, (1, 2, 3, 4, 5, 6, 8, 12, 18, 23, 24, 25, 30, 36, 47, 48, 49, 72, 96, 120)):
#         price, d = PLANS[plan][1], outage_days(h)
#         res = (f"The outage is longer than 4 hours, so a credit applies for {d} day{plural(d)} ({h} hours is {d} period{plural(d)} of 24 hours or part of one). The credit is {d} x 1/30 of {usd(price)}, which is {cents(outage_credit_cents(plan, h))} rounded to the nearest cent."
#                if d else "The outage is not longer than 4 hours, so no credit applies.")
#         out.append(item(f"Outage credit: {h} hours on {plan}", f"An outage lasting {h} hours affects a customer on {plan}, list price {usd(price)}. {res}"))
#     eq = []
#     for r, day in product((1, 2, 3), (14, 15, 30, None)):
#         when = "never returns them" if day is None else f"returns them {day} days after cancellation"
#         tag = "not returned" if day is None else f"returned on day {day}"
#         res = (f"The equipment was returned late, so {r} x {usd(ROUTER_FEE)} = {usd(r * ROUTER_FEE)} is charged."
#                if day is None or day > 14 else "The equipment was returned within 14 days, so no charge applies.")
#         eq.append(item(f"Equipment return: {r} router{plural(r)}, {tag}", f"A customer who rents {r} router{plural(r)} cancels service and {when}. {res}"))
#     notice = []
#     for mth in range(1, 13):
#         given = date(2025, mth, 3)
#         end = given + timedelta(days=30)
#         notice.append(item(f"Notice period: notice given on {given:%B} 3",
#                            f"A customer gives written notice to cancel on {given:%B} 3. Thirty days of notice are required, so service can end on {end:%B} {end.day} at the earliest. A customer who wants a later end date chooses it and pays until then."))
#     return assemble(core, [
#         fam("Appendix A. Early termination examples", "Fees are the monthly fee times the months remaining, capped at the maximum.", fees),
#         fam("Appendix B. Late fee scenarios", "Days are counted from the invoice date.", late),
#         fam("Appendix C. Billing dispute window", "The window is 60 days from the invoice date.", disp),
#         fam("Appendix D. Outage credit scenarios", "Credit is per 24 hours of outage or part of 24 hours, for outages longer than 4 hours.", out),
#         fam("Appendix E. Equipment return scenarios", "Rented routers must be returned within 14 days of cancellation.", eq),
#         fam("Appendix F. Notice period dates", "Thirty days of written notice are required to cancel.", notice)])


# BUNDLES = {"Basic": ("no add-ons", ()),
#            "Secure": ("Online Security and Online Backup", ("Online Security", "Online Backup")),
#            "Entertainment": ("Streaming TV and Streaming Movies", ("Streaming TV", "Streaming Movies")),
#            "Everything": ("all six add-ons", tuple(ADDONS))}
# ADDON_INFO = {"Online Security": "Blocks known malicious sites and scans downloads.",
#               "Online Backup": "Stores copies of customer files online.",
#               "Device Protection": "Covers repair or replacement of listed devices.",
#               "Tech Support": "Gives priority access to technical support agents.",
#               "Streaming TV": "Adds live and on-demand TV channels.",
#               "Streaming Movies": "Adds an on-demand movie library."}


# def plans() -> list[Sec]:
#     """Plans and pricing guide: core sections plus appendices A-D."""
#     core = [
#         Sec("Internet plans", ["Internet service is priced per month. Prices exclude add-ons, phone lines and taxes."],
#             [["Plan", "Speed", "Monthly price"]] + [[p, s, usd(pr)] for p, (s, pr, _) in PLANS.items()]),
#         Sec("Phone service", [f"The first phone line costs {usd(PHONE_FIRST)} per month. Each additional line costs {usd(PHONE_EXTRA)} per month."]),
#         Sec("Add-ons", ["All add-ons need an internet plan. Add-on prices are never discounted."],
#             [["Add-on", "Monthly price"]] + [[a, usd(p)] for a, p in ADDONS.items()]),
#         Sec("Contract and payment discounts", [
#             "- One-year contract: 5% off the internet plan list price.",
#             "- Two-year contract: 10% off the internet plan list price.",
#             f"- Automatic payment (bank transfer or credit card): {usd(AUTOPAY)} off the total monthly bill.",
#             "- Paperless billing is free. Paper statements cost $3 per month.",
#             "Contract discounts apply to the internet plan only, never to phone lines or add-ons."]),
#         Sec("New customer promotion", ["New customers get 15% off the internet plan list price for the first 3 months. This promotion is for new sign-ups only and cannot be given to existing customers as a retention offer."]),
#         Sec("How the monthly bill is calculated", [
#             f"Start with the internet plan list price and subtract the contract discount percentage. Add phone lines and add-ons, which are not discounted. Subtract the {usd(AUTOPAY)} automatic payment credit. Taxes are added last.",
#             f"When a retention discount is given, its percentage is added to the contract discount percentage. The combined percentage may never exceed {COMBINED_CAP} percent."])]

#     bun = []
#     for plan, contract, (bname, (desc, adds)), auto in product(PLANS, CONTRACTS, BUNDLES.items(), (False, True)):
#         price, cpct = PLANS[plan][1], CONTRACTS[contract][0]
#         net, extra = internet_cents(plan, contract), sum(ADDONS[a] for a in adds)
#         total = net + extra * 100
#         pay = "paid by automatic payment" if auto else "without automatic payment"
#         tail = f", and the {usd(AUTOPAY)} automatic payment credit brings it to {cents(total - AUTOPAY * 100)}" if auto else ""
#         bun.append(item(f"{plan}, {contract.lower()}, {bname} bundle, {pay}",
#                         f"{plan} on a {contract.lower()} contract with {desc}, {pay}: the internet plan is {usd(price)} less {cpct}%, which is {cents(net)}; add-ons cost {usd(extra)}; the total is {cents(total)} per month{tail}. Prices exclude phone lines and taxes."))
#     sw = []
#     for (a, b), contract in product(permutations(PLANS, 2), CONTRACTS):
#         na, nb = internet_cents(a, contract), internet_cents(b, contract)
#         more = "more" if nb > na else "less"
#         sw.append(item(f"Switching from {a} to {b}, {contract.lower()} contract",
#                        f"A customer on a {contract.lower()} contract switches from {a} to {b}. The list price changes from {usd(PLANS[a][1])} to {usd(PLANS[b][1])}. After the {CONTRACTS[contract][0]}% contract discount the internet charge changes from {cents(na)} to {cents(nb)}, which is {cents(abs(nb - na))} {more} per month. The contract discount percentage carries over, and the change starts on the next billing date."))
#     ad = [item(f"Add-on: {a}", f"{a}: {usd(p)} per month, {usd(12 * p)} per year. {ADDON_INFO[a]} It needs an internet plan and its price is never discounted.")
#           for a, p in ADDONS.items()]
#     ph = [item(f"Phone lines: {n} line{plural(n)}",
#                f"{n} phone line{plural(n)} cost {usd(phone_dollars(n))} per month: {usd(PHONE_FIRST)} for the first line"
#                + (f" plus {n - 1} x {usd(PHONE_EXTRA)} for the additional line{plural(n - 1)}." if n > 1 else "."))
#           for n in range(1, 7)]
#     return assemble(core, [
#         fam("Appendix A. Monthly price examples", "Each example uses list prices, the contract discount, add-ons and the automatic payment credit.", bun),
#         fam("Appendix B. Switching plans", "The contract discount percentage carries over to the new plan.", sw),
#         fam("Appendix C. Add-on details", "All add-ons need an internet plan.", ad),
#         fam("Appendix D. Phone line pricing", "Phone prices are not discounted.", ph)])





"""Hand-written cores plus computed appendix families for the retention policy,
service terms and plans guide. Every family item is distinct (different numbers
and outcomes); assemble() adds items until a document reaches TARGET words."""
from __future__ import annotations

from datetime import date, timedelta
from itertools import combinations, permutations, product

from scripts.synth_rules import (
    ADDONS, AUTOPAY, COMBINED_CAP, CONTRACTS, CREDIT_1Y, CREDIT_2Y, LATE_FEE, PHONE_EXTRA,
    PHONE_FIRST, PLANS, RETENTION_CAP, ROUTER_FEE, TIERS, Sec, assemble, cents, eligibility,
    etf, internet_cents, outage_credit_cents, outage_days, phone_dollars, plural, usd)

Fam = tuple[Sec, list[Sec]]


def item(heading: str, text: str) -> Sec:
    """A level-2 appendix entry."""
    return Sec(heading, [text], level=2)


def fam(title: str, intro: str, items: list[Sec]) -> Fam:
    """An appendix: heading with intro, plus its candidate items."""
    return Sec(title, [intro]), items


def retention() -> list[Sec]:
    """Retention policy: core sections plus appendices A-D."""
    table = [["Tier", "Risk score", "Offer", "Max discount", "Duration", "Approval"]] + [
        [t, sc, o.capitalize(), f"{p}%", f"{m} months" if m else "n/a", a.capitalize()]
        for t, sc, o, p, m, a in TIERS]
    core = [
        Sec("1. Purpose and scope", [
            "This policy tells Brightline Telecom retention agents which offers they may make to customers who are at risk of leaving. It applies to residential customers only.",
            "Risk tiers use the churn risk score from the churn model. The score ranks customers by risk. It is not a calibrated probability, and agents must not quote it to customers."]),
        Sec("2. Risk tiers and maximum discounts", [
            f"Retention discounts apply to the internet plan charge only, never to add-ons or phone lines. The absolute cap on any retention discount is {RETENTION_CAP} percent. Only one retention offer may be active on an account at a time."], table),
        Sec("3. Eligibility exclusions", [
            "- A customer who accepted a retention discount in the last 12 months is not eligible for another.",
            "- Accounts more than 60 days overdue are not eligible for any discount.",
            "- Two-year contract customers with more than 6 months remaining get a 12-month price lock, not a discount.",
            "- The new customer promotion is for new sign-ups only and can never be used as a retention offer.",
            "A price lock is not a discount, so the first two exclusions do not stop an agent from offering one."]),
        Sec("4. Contract offers, price locks and documentation", [
            f"A month-to-month customer who accepts a one-year contract receives a one-time bill credit of {usd(CREDIT_1Y)}. A one-year customer who renews for two years receives a one-time bill credit of {usd(CREDIT_2Y)}.",
            "A price lock guarantees the internet plan price for 12 months. Agents may offer it at any tier and it needs no approval.",
            "Every offer must be logged with the ticket ID, tier, discount and duration. Offers above 20 percent must also record the approver's name."]),
        Sec("5. How retention discounts combine with other discounts", [
            f"Contract discounts (5 percent for a one-year contract, 10 percent for a two-year contract) and the {usd(AUTOPAY)} automatic payment credit are standing entitlements and still apply when a retention discount is given. Percentages are added together, not multiplied, and are taken from the list price of the internet plan.",
            f"The combined percentage discount on the internet plan may never exceed {COMBINED_CAP} percent. The automatic payment credit is taken off the total monthly bill after percentage discounts. A retention discount does not stack with another retention discount or with the new customer promotion."])]

    play = []
    for tier, score, offer, pct, months, appr in TIERS:
        for contract, (cpct, _, _) in CONTRACTS.items():
            apv = "can be approved by the agent" if appr == "agent" else f"needs approval from the {appr}"
            disc = ("No retention discount is available at this tier. The agent makes a courtesy call and may offer a 12-month price lock."
                    if not pct else
                    f"The maximum retention discount is {pct}% of the internet plan list price for {months} months and {apv}. With the {cpct}% contract discount that is {pct + cpct}% off, against the {COMBINED_CAP}% combined cap.")
            ctr = {"Two year": "If more than 6 months remain, the agent may offer only a 12-month price lock; with 6 months or fewer remaining the tier discount applies.",
                   "One year": f"The agent may also offer a one-time {usd(CREDIT_2Y)} bill credit if the customer renews for two years.",
                   "Month-to-month": f"The agent may also offer a one-time {usd(CREDIT_1Y)} bill credit if the customer moves to a one-year contract."}[contract]
            log = "Log the ticket ID, tier, discount and duration." + (
                " Also record the approver's name, because the discount is above 20%." if pct > 20 else "")
            play.append(item(f"{tier} tier, {contract} customer",
                             f"A customer on a {contract.lower()} contract with a risk score of {score} is in the {tier} tier and may receive the {offer}. {disc} {ctr} {log}"))

    ex, i = [], 0
    for tier, _, _, pct, months, _ in TIERS:
        for plan, (speed, price, _) in PLANS.items():
            for auto in (False, True):
                contract = list(CONTRACTS)[i % 3]
                i += 1
                cpct = CONTRACTS[contract][0]
                left = " and 4 months remaining" if contract == "Two year" else ""
                pay = "pays by automatic payment" if auto else "does not use automatic payment"
                base = internet_cents(plan, contract, 0, auto)
                head = (f"A customer on {plan} ({speed}, list price {usd(price)}) with a {contract.lower()} contract{left} "
                        f"is in the {tier} tier and {pay}. The contract discount is {cpct}%")
                if pct:
                    now = internet_cents(plan, contract, pct, auto)
                    res = (f", less the {usd(AUTOPAY)} automatic payment credit, giving {cents(now)}" if auto
                           else f", giving {cents(now)}")
                    body = (f" and the maximum retention discount is {pct}%, so the combined discount is {cpct + pct}%. "
                            f"The internet charge is {usd(price)} x (100% - {cpct + pct}%) = {cents(price * (100 - cpct - pct))}{res} "
                            f"per month for {months} months. Afterwards the customer pays {cents(base)} per month.")
                else:
                    body = (f". There is no retention discount at this tier, so the internet charge stays at {cents(base)} per month"
                            + (f" after the {usd(AUTOPAY)} automatic payment credit." if auto else "."))
                ex.append(item(f"Example {i}: {tier} tier on {plan}", head + body))

    sit = [
        ("A customer says a competitor is cheaper and asks to cancel.", "Check the risk tier. Because the customer raised cancellation, the agent may present the tier offer. At the Low tier there is no discount, so the agent offers a courtesy call and may offer a 12-month price lock."),
        ("A customer asks for more than the tier maximum.", f"Decline. No retention discount may exceed the tier maximum, and none may ever exceed the {RETENTION_CAP} percent cap, even with approval."),
        ("A customer asks to combine a retention discount with the new customer promotion.", "Refuse. The promotion is for new sign-ups only, and retention discounts do not stack with it."),
        ("A customer accepted a retention discount 8 months ago and calls again.", "The customer is not eligible for another discount, because 8 months is inside the 12-month window. A price lock may still be offered."),
        ("A customer wants the discount applied to Streaming TV.", "Retention discounts apply to the internet plan charge only, never to add-ons."),
        ("A customer on a two-year contract with 10 months left threatens to leave.", "Offer only the 12-month price lock, because more than 6 months remain. If the customer cancels anyway, the early termination fee in the service terms applies."),
        ("A Critical tier offer is ready to close but the approver is not recorded.", "The offer is incomplete. Offers above 20 percent must record the approver's name, so add it before the ticket is closed."),
        ("A customer asks the agent to quote their churn score.", "Do not quote it. The score is an internal ranking signal and not a probability.")]
    sits = [item(f"Situation {n}", f"Situation: {a} Handling: {b}") for n, (a, b) in enumerate(sit, 1)]

    cases = []
    grid = product((0, 60, 61, 90), (None, 6, 18), (("Month-to-month", 0), ("Two year", 8), ("Two year", 3)))
    for n, (od, last, (contract, rem)) in enumerate(grid, 1):
        outcome, reason = eligibility(od, last, contract, rem)
        pay = "is up to date on payments" if od == 0 else f"is {od} days overdue"
        hist = "has never accepted a retention discount" if last is None else f"accepted a retention discount {last} months ago"
        ctr = ("is on a month-to-month contract" if contract == "Month-to-month"
               else f"is on a two-year contract with {rem} months remaining")
        cases.append(item(f"Case {n}: High tier, {od} days overdue",
                          f"A High tier customer {pay}, {hist} and {ctr}. Result: the customer is {outcome}, because {reason}. If an offer is made, the agent logs the ticket ID, tier, discount and duration."))
    return assemble(core, [
        fam("Appendix A. Playbook by tier and contract", "These entries restate sections 2 to 5 for each tier and contract type.", play),
        fam("Appendix B. Worked pricing examples", "Each example shows the internet plan charge. Percentages add; the automatic payment credit is taken off last.", ex),
        fam("Appendix C. Common situations", "How to handle situations agents meet often.", sits),
        fam("Appendix D. Eligibility cases for High tier customers", "Exclusions are checked in this order: overdue, recent discount, contract remaining.", cases)])


def terms() -> list[Sec]:
    """Service terms: core sections plus appendices A-F."""
    tbl = [["Contract", "Fee per remaining month", "Maximum fee"]] + [
        [c, usd(f), usd(m)] for c, (_, f, m) in CONTRACTS.items()]
    core = [
        Sec("1. Billing", [
            f"Invoices are issued monthly. Payment is due 15 days after the invoice date. A late fee of {usd(LATE_FEE)} applies to payments received more than 10 days after the due date.",
            "Billing disputes must be raised within 60 days of the invoice date."]),
        Sec("2. Cancellation and early termination", [
            "Customers must give 30 days written notice to cancel. Customers who cancel before the end of a fixed contract pay an early termination fee equal to the monthly fee in the table times the months remaining, up to the maximum. Month-to-month customers pay no fee."], tbl),
        Sec("3. Service levels", [
            "Monthly availability targets are 99.5 percent for Fiber optic plans and 99.0 percent for DSL.",
            "For an outage longer than 4 hours, the customer receives a credit for each 24 hours of outage or part of 24 hours. One day of credit is 1/30 of the list price of the customer's internet plan, rounded to the nearest cent."]),
        Sec("4. Equipment, refunds and records", [
            f"Rented equipment must be returned within 14 days of cancellation. Equipment not returned in that time is charged at {usd(ROUTER_FEE)} per router.",
            "Eligible overpayments are refunded within 30 days. Brightline keeps account and billing records for 24 months after an account closes."])]

    fees = []
    for contract, ms in (("One year", (1, 2, 3, 4, 6, 8, 10, 11, 12)), ("Two year", (1, 3, 5, 7, 9, 10, 12, 15, 18, 20, 22, 24))):
        _, per, cap = CONTRACTS[contract]
        for m in ms:
            note = (f"which is above the {usd(cap)} maximum, so the fee is capped at {usd(cap)}" if per * m > cap
                    else f"which is within the {usd(cap)} maximum, so {usd(etf(contract, m))} is charged")
            fees.append(item(f"Early termination: {contract.lower()} contract, {m} months remaining",
                             f"A customer on a {contract.lower()} contract cancels with {m} months remaining. The fee is {m} x {usd(per)} = {usd(per * m)}, {note}. The customer must still give 30 days written notice and pay the final invoice."))
    late = []
    for d in (10, 15, 16, 20, 24, 25, 26, 30, 35, 40, 45, 60):
        res = ("The payment was on time, so no fee applies." if d <= 15 else
               f"The payment was {d - 15} days after the due date. That is not more than 10 days late, so no late fee applies." if d <= 25 else
               f"The payment was {d - 15} days after the due date, which is more than 10 days late, so the {usd(LATE_FEE)} late fee applies.")
        late.append(item(f"Late fee: payment received {d} days after the invoice date",
                         f"An invoice is issued on day 0 and payment is due on day 15. Payment arrives on day {d}. {res}"))
    disp = [item(f"Billing dispute raised {d} days after the invoice date",
                 f"A customer raises a billing dispute {d} days after the invoice date. Disputes must be raised within 60 days, so the dispute is " + ("accepted for review." if d <= 60 else "too late and is declined."))
            for d in (5, 30, 59, 60, 61, 75, 90)]
    out = []
    for plan, h in product(PLANS, (1, 2, 3, 4, 5, 6, 8, 12, 18, 23, 24, 25, 30, 36, 47, 48, 49, 72, 96, 120)):
        price, d = PLANS[plan][1], outage_days(h)
        res = (f"The outage is longer than 4 hours, so a credit applies for {d} day{plural(d)} ({h} hours is {d} period{plural(d)} of 24 hours or part of one). The credit is {d} x 1/30 of {usd(price)}, which is {cents(outage_credit_cents(plan, h))} rounded to the nearest cent."
               if d else "The outage is not longer than 4 hours, so no credit applies.")
        out.append(item(f"Outage credit: {h} hours on {plan}", f"An outage lasting {h} hours affects a customer on {plan}, list price {usd(price)}. {res}"))
    eq = []
    for r, day in product((1, 2, 3), (14, 15, 30, None)):
        when = "never returns them" if day is None else f"returns them {day} days after cancellation"
        tag = "not returned" if day is None else f"returned on day {day}"
        res = (f"The equipment was returned late, so {r} x {usd(ROUTER_FEE)} = {usd(r * ROUTER_FEE)} is charged."
               if day is None or day > 14 else "The equipment was returned within 14 days, so no charge applies.")
        eq.append(item(f"Equipment return: {r} router{plural(r)}, {tag}", f"A customer who rents {r} router{plural(r)} cancels service and {when}. {res}"))
    notice = []
    for mth in range(1, 13):
        given = date(2025, mth, 3)
        end = given + timedelta(days=30)
        notice.append(item(f"Notice period: notice given on {given:%B} 3",
                           f"A customer gives written notice to cancel on {given:%B} 3. Thirty days of notice are required, so service can end on {end:%B} {end.day} at the earliest. A customer who wants a later end date chooses it and pays until then."))
    return assemble(core, [
        fam("Appendix A. Early termination examples", "Fees are the monthly fee times the months remaining, capped at the maximum.", fees),
        fam("Appendix B. Late fee scenarios", "Days are counted from the invoice date.", late),
        fam("Appendix C. Billing dispute window", "The window is 60 days from the invoice date.", disp),
        fam("Appendix D. Outage credit scenarios", "Credit is per 24 hours of outage or part of 24 hours, for outages longer than 4 hours.", out),
        fam("Appendix E. Equipment return scenarios", "Rented routers must be returned within 14 days of cancellation.", eq),
        fam("Appendix F. Notice period dates", "Thirty days of written notice are required to cancel.", notice)])


BUNDLES = {"Basic": ("no add-ons", ()),
           "Secure": ("Online Security and Online Backup", ("Online Security", "Online Backup")),
           "Entertainment": ("Streaming TV and Streaming Movies", ("Streaming TV", "Streaming Movies")),
           "Everything": ("all six add-ons", tuple(ADDONS))}
ADDON_INFO = {"Online Security": "Blocks known malicious sites and scans downloads.",
              "Online Backup": "Stores copies of customer files online.",
              "Device Protection": "Covers repair or replacement of listed devices.",
              "Tech Support": "Gives priority access to technical support agents.",
              "Streaming TV": "Adds live and on-demand TV channels.",
              "Streaming Movies": "Adds an on-demand movie library."}


def plans() -> list[Sec]:
    """Plans and pricing guide: core sections plus appendices A-D."""
    core = [
        Sec("Internet plans", ["Internet service is priced per month. Prices exclude add-ons, phone lines and taxes."],
            [["Plan", "Speed", "Monthly price"]] + [[p, s, usd(pr)] for p, (s, pr, _) in PLANS.items()]),
        Sec("Phone service", [f"The first phone line costs {usd(PHONE_FIRST)} per month. Each additional line costs {usd(PHONE_EXTRA)} per month."]),
        Sec("Add-ons", ["All add-ons need an internet plan. Add-on prices are never discounted."],
            [["Add-on", "Monthly price"]] + [[a, usd(p)] for a, p in ADDONS.items()]),
        Sec("Contract and payment discounts", [
            "- One-year contract: 5% off the internet plan list price.",
            "- Two-year contract: 10% off the internet plan list price.",
            f"- Automatic payment (bank transfer or credit card): {usd(AUTOPAY)} off the total monthly bill.",
            "- Paperless billing is free. Paper statements cost $3 per month.",
            "Contract discounts apply to the internet plan only, never to phone lines or add-ons."]),
        Sec("New customer promotion", ["New customers get 15% off the internet plan list price for the first 3 months. This promotion is for new sign-ups only and cannot be given to existing customers as a retention offer."]),
        Sec("How the monthly bill is calculated", [
            f"Start with the internet plan list price and subtract the contract discount percentage. Add phone lines and add-ons, which are not discounted. Subtract the {usd(AUTOPAY)} automatic payment credit. Taxes are added last.",
            f"When a retention discount is given, its percentage is added to the contract discount percentage. The combined percentage may never exceed {COMBINED_CAP} percent."])]

    bun = []
    for plan, contract, (bname, (desc, adds)), auto in product(PLANS, CONTRACTS, BUNDLES.items(), (False, True)):
        price, cpct = PLANS[plan][1], CONTRACTS[contract][0]
        net, extra = internet_cents(plan, contract), sum(ADDONS[a] for a in adds)
        total = net + extra * 100
        pay = "paid by automatic payment" if auto else "without automatic payment"
        tail = f", and the {usd(AUTOPAY)} automatic payment credit brings it to {cents(total - AUTOPAY * 100)}" if auto else ""
        bun.append(item(f"{plan}, {contract.lower()}, {bname} bundle, {pay}",
                        f"{plan} on a {contract.lower()} contract with {desc}, {pay}: the internet plan is {usd(price)} less {cpct}%, which is {cents(net)}; add-ons cost {usd(extra)}; the total is {cents(total)} per month{tail}. Prices exclude phone lines and taxes."))
    sw = []
    for (a, b), contract in product(permutations(PLANS, 2), CONTRACTS):
        na, nb = internet_cents(a, contract), internet_cents(b, contract)
        more = "more" if nb > na else "less"
        sw.append(item(f"Switching from {a} to {b}, {contract.lower()} contract",
                       f"A customer on a {contract.lower()} contract switches from {a} to {b}. The list price changes from {usd(PLANS[a][1])} to {usd(PLANS[b][1])}. After the {CONTRACTS[contract][0]}% contract discount the internet charge changes from {cents(na)} to {cents(nb)}, which is {cents(abs(nb - na))} {more} per month. The contract discount percentage carries over, and the change starts on the next billing date."))
    ad = [item(f"Add-on: {a}", f"{a}: {usd(p)} per month, {usd(12 * p)} per year. {ADDON_INFO[a]} It needs an internet plan and its price is never discounted.")
          for a, p in ADDONS.items()]
    ph = [item(f"Phone lines: {n} line{plural(n)}",
               f"{n} phone line{plural(n)} cost {usd(phone_dollars(n))} per month: {usd(PHONE_FIRST)} for the first line"
               + (f" plus {n - 1} x {usd(PHONE_EXTRA)} for the additional line{plural(n - 1)}." if n > 1 else "."))
          for n in range(1, 7)]
    tri = []
    for plan, contract, (a, b, third) in product(PLANS, CONTRACTS, combinations(ADDONS, 3)):
        net, extra = internet_cents(plan, contract), ADDONS[a] + ADDONS[b] + ADDONS[third]
        tri.append(item(f"Trio: {plan}, {contract.lower()}, {a}, {b} and {third}",
                        f"{plan} on a {contract.lower()} contract with {a}, {b} and {third}: internet {cents(net)}, add-ons {usd(extra)}, total {cents(net + 100 * extra)} per month before phone lines, the automatic payment credit and taxes."))
    return assemble(core, [
        fam("Appendix A. Monthly price examples", "Each example uses list prices, the contract discount, add-ons and the automatic payment credit.", bun),
        fam("Appendix B. Switching plans", "The contract discount percentage carries over to the new plan.", sw),
        fam("Appendix C. Add-on details", "All add-ons need an internet plan.", ad),
        fam("Appendix D. Phone line pricing", "Phone prices are not discounted.", ph),
        fam("Appendix E. Plan plus three add-ons", "Totals use list prices and the contract discount.", tri)])