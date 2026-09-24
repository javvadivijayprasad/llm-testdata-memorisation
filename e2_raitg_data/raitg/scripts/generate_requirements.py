"""Deterministically generate the 312-requirement dataset.

Produces:
  datasets/commercial_web.json      (112 reqs)
  datasets/financial_services.json  (98 reqs)
  datasets/healthcare.json          (102 reqs)
  datasets/combined.json            (all 312)

Requirements are modelled after the functional surface of permissively
licensed open-source projects (Gitea / Ghost / Supabase / FHIR) but are
authored independently — no text is copied from any upstream project.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DATASETS = ROOT / "datasets"

# Deterministic seed
random.seed(20260101)

LAYERS = ["UI", "API", "INTEGRATION"]
CATEGORIES = ["auth", "validation", "transaction", "reporting", "integration"]


# ---------------------------------------------------------------------------
# Domain 1: Commercial Web (HR management app)
# ---------------------------------------------------------------------------
HR_ENTITIES = [
    ("employee", "employees"), ("department", "departments"),
    ("team", "teams"), ("leave-request", "leave-requests"),
    ("timesheet", "timesheets"), ("performance-review", "performance-reviews"),
    ("onboarding-task", "onboarding-tasks"), ("document", "documents"),
    ("benefit", "benefits"), ("payroll-run", "payroll-runs"),
    ("expense-claim", "expense-claims"), ("training-course", "training-courses"),
    ("org-announcement", "org-announcements"), ("policy-document", "policy-documents"),
]

HR_VERBS = [
    ("create", "creates", "created"),
    ("update", "updates", "updated"),
    ("delete", "deletes", "deleted"),
    ("view", "views", "viewed"),
    ("list", "lists", "listed"),
    ("approve", "approves", "approved"),
    ("reject", "rejects", "rejected"),
    ("export", "exports", "exported"),
]

HR_ACTORS = [
    ("employee", ["authenticated"]),
    ("manager", ["authenticated", "role:manager"]),
    ("hr-admin", ["authenticated", "role:hr-admin"]),
    ("system-admin", ["authenticated", "role:admin"]),
]


def hr_requirements() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    idx = 1

    # CRUD surface (4 verbs x 14 entities = 56)
    for entity, plural in HR_ENTITIES:
        for verb, pres, past in [("create", "creates", "created"),
                                 ("update", "updates", "updated"),
                                 ("delete", "deletes", "deleted"),
                                 ("view", "views", "viewed")]:
            actor_name, actor_preconds = random.choice(HR_ACTORS[1:])  # not plain employee for CRUD
            layer = "UI" if idx % 3 != 0 else "API"
            category = "validation" if verb in ("create", "update") else ("auth" if verb == "delete" else "reporting")
            out.append({
                "id": f"R-WEB-{idx:03d}",
                "domain": "commercial_web",
                "layer": layer,
                "category": category,
                "title": f"{actor_name.title()} {verb}s {entity}",
                "statement": (
                    f"An authenticated {actor_name} shall be able to {verb} a {entity} "
                    f"through the {'UI form' if layer == 'UI' else 'REST API'}. "
                    f"Mandatory fields must be validated and an audit record must be written on success."
                ),
                "actors": [actor_name],
                "preconditions": actor_preconds + [f"{entity} module is enabled"],
                "triggers": [f"{actor_name} {pres} a {entity}"],
                "expected_outcomes": [
                    f"{entity} is {past}",
                    "audit record written",
                    "response 200 or 201 with entity id",
                ],
                "error_pathways": [
                    "400 on validation error",
                    "401 if unauthenticated",
                    "403 if role forbidden",
                ],
                "target_app": "hr-app",
                "target_endpoint_or_screen": f"/api/{plural}" if layer == "API" else f"/{plural}",
            })
            idx += 1

    # Domain-specific workflow requirements
    workflows = [
        ("Submit leave request", "A full-time employee shall be able to submit a leave request for between 1 and 30 business days; requests spanning more than 30 days require hr-admin approval.",
         "UI", "transaction", "hr-app", "/leave-requests/new",
         ["authenticated", "employment_type:full_time"],
         ["employee submits form"],
         ["request created", "manager notified", "notification email sent"],
         ["400 when start_date > end_date", "409 when overlapping existing leave", "422 when request exceeds 30 days without hr-admin"]),
        ("Approve leave request", "A manager shall approve or reject leave requests assigned to them within 5 business days; unactioned requests auto-escalate to hr-admin.",
         "UI", "transaction", "hr-app", "/leave-requests/{id}/approve",
         ["role:manager", "request assigned to manager"],
         ["manager clicks approve"],
         ["request state=approved", "employee notified", "audit entry"],
         ["403 if manager not the assignee", "409 if already actioned"]),
        ("Submit timesheet", "An employee shall submit a weekly timesheet where each day has hours between 0 and 24 and total week hours are between 0 and 80.",
         "UI", "validation", "hr-app", "/timesheets/submit",
         ["authenticated"],
         ["employee submits weekly timesheet"],
         ["timesheet state=submitted"],
         ["422 when per-day hours outside 0-24", "422 when weekly total outside 0-80"]),
        ("Run payroll", "An hr-admin shall run a monthly payroll that computes gross pay, deductions, and net pay for each active employee; a failed run shall not partially commit.",
         "API", "transaction", "hr-app", "/api/payroll-runs",
         ["role:hr-admin"],
         ["admin triggers payroll run"],
         ["payroll-run state=completed", "pay-stub records created", "audit entry"],
         ["409 if another run is in progress", "500 rolled back atomically on failure"]),
        ("Upload onboarding document", "An employee shall upload onboarding documents up to 10MB in PDF, PNG, or JPG format; files outside this must be rejected.",
         "UI", "validation", "hr-app", "/documents/upload",
         ["authenticated"],
         ["employee uploads file"],
         ["document stored", "virus scan queued"],
         ["413 when size > 10MB", "415 when mime not in allow-list"]),
        ("Export employee directory", "An hr-admin shall export the employee directory as CSV with PII redacted for employees who opted out of public directory.",
         "API", "reporting", "hr-app", "/api/employees/export.csv",
         ["role:hr-admin"],
         ["admin requests export"],
         ["CSV streamed", "PII redacted per opt-out"],
         ["403 if not hr-admin", "429 if rate-limited"]),
        ("Announcement rollout", "A system-admin shall publish an org-wide announcement to employees in chosen departments; publishing without any department selection shall be rejected.",
         "UI", "validation", "hr-app", "/org-announcements/new",
         ["role:admin"],
         ["admin publishes announcement"],
         ["announcement created", "target employees notified"],
         ["422 when no departments selected"]),
        ("Schedule performance review", "A manager shall schedule a performance review with the reviewee at least 7 days in advance; past or sub-7-day dates shall be rejected.",
         "UI", "validation", "hr-app", "/performance-reviews/schedule",
         ["role:manager"],
         ["manager schedules review"],
         ["review scheduled", "participants notified"],
         ["422 when scheduled_at < now + 7d"]),
        ("Bulk import employees", "An hr-admin shall bulk-import employees via CSV; the import shall validate each row and commit only rows that pass validation, reporting errors per row.",
         "UI", "integration", "hr-app", "/employees/import",
         ["role:hr-admin"],
         ["admin uploads CSV"],
         ["valid rows imported", "error report generated"],
         ["415 when file not CSV", "422 when header missing required columns"]),
        ("Reset employee password", "An employee shall reset their password via an email link that expires after 30 minutes; expired links must be rejected.",
         "UI", "auth", "hr-app", "/password/reset",
         ["valid reset token"],
         ["employee submits new password"],
         ["password updated", "all sessions invalidated"],
         ["410 when token expired", "422 when password fails policy"]),
    ]

    # Extra domain-specific requirements to reach 112
    extras = [
        ("List employees pagination", "The employee list shall be paginated at 50 per page with cursor-based pagination.",
         "API", "reporting", "hr-app", "/api/employees",
         ["authenticated"], ["caller lists"], ["page returned"],
         ["422 when limit > 200"]),
        ("Timezone handling", "Timestamps stored shall be UTC; UI shall render in user's configured timezone.",
         "UI", "integration", "hr-app", "/*",
         ["authenticated"], ["user views timestamp"],
         ["rendered in user tz"], ["default to UTC when tz missing"]),
        ("Feature flag rollout", "An admin shall toggle feature flags per environment; toggles shall be audit-logged.",
         "UI", "auth", "hr-app", "/feature-flags",
         ["role:admin"], ["admin toggles flag"],
         ["flag state changed", "audit entry"],
         ["403 when not admin"]),
        ("Webhook delivery", "Outbound webhooks shall retry on 5xx with exponential backoff up to 5 times; permanent failures shall be DLQ'd.",
         "INTEGRATION", "integration", "hr-app", "/hooks/*",
         ["webhook configured"], ["event fires"],
         ["delivered or DLQ'd"],
         ["5 retries on 5xx"]),
        ("Session management", "A user session shall expire after 30 minutes of inactivity; expired sessions shall redirect to login.",
         "UI", "auth", "hr-app", "/*",
         ["authenticated"], ["idle timer reached"],
         ["session invalidated", "redirect to login"],
         ["401 on next request"]),
        ("Accessibility compliance", "All UI screens shall be keyboard-navigable and meet WCAG 2.1 AA contrast ratios.",
         "UI", "validation", "hr-app", "/*",
         ["rendering"], ["a11y scan"],
         ["contrast passes", "keyboard path exists"],
         ["violations reported"]),
    ]

    for (title, stmt, layer, cat, app, endpoint, preconds, triggers,
         outcomes, errors) in workflows:
        for seq in range(1, 6):  # expand each workflow into 5 related requirements
            suffix = f" — variant {seq}" if seq > 1 else ""
            out.append({
                "id": f"R-WEB-{idx:03d}",
                "domain": "commercial_web",
                "layer": layer,
                "category": cat,
                "title": title + suffix,
                "statement": stmt + (
                    ["", " Additionally, the action must be idempotent under retry.",
                     " Additionally, the action must emit a webhook event for external consumers.",
                     " Additionally, the operation must be rate-limited per user.",
                     " Additionally, the action requires two-factor authentication confirmation."][seq-1]
                ),
                "actors": [preconds[0].replace("role:", "")],
                "preconditions": preconds,
                "triggers": triggers,
                "expected_outcomes": outcomes + ([] if seq == 1 else ["additional variant semantics honoured"]),
                "error_pathways": errors,
                "target_app": app,
                "target_endpoint_or_screen": endpoint,
            })
            idx += 1
    # Append extras to reach 112
    for (title, stmt, layer, cat, app, endpoint, preconds, triggers,
         outcomes, errors) in extras:
        out.append({
            "id": f"R-WEB-{idx:03d}",
            "domain": "commercial_web",
            "layer": layer,
            "category": cat,
            "title": title,
            "statement": stmt,
            "actors": ["user"],
            "preconditions": preconds,
            "triggers": triggers,
            "expected_outcomes": outcomes,
            "error_pathways": errors,
            "target_app": app,
            "target_endpoint_or_screen": endpoint,
        })
        idx += 1
    # Ensure exactly 112
    out = out[:112]
    return out


# ---------------------------------------------------------------------------
# Domain 2: Financial Services (retail account API)
# ---------------------------------------------------------------------------
BANK_TEMPLATES = [
    ("Open checking account", "A verified customer shall be able to open a checking account with an initial deposit between $25 and $50,000; deposits outside this range shall be rejected.",
     "API", "validation", "banking-api", "/accounts/checking",
     ["customer.verified=true"], ["customer opens account"],
     ["account created", "welcome-notification dispatched"],
     ["422 when deposit < 25 or > 50000", "403 when customer not verified"]),
    ("Open savings account", "A verified customer shall open a savings account with a minimum balance of $100 and tiered interest rates applied automatically.",
     "API", "validation", "banking-api", "/accounts/savings",
     ["customer.verified=true"], ["customer opens account"],
     ["account created", "tier assigned"],
     ["422 when initial < 100"]),
    ("Transfer funds between own accounts", "A customer shall transfer up to $25,000 per day between their own accounts; transfers above this shall be declined.",
     "API", "transaction", "banking-api", "/transfers/internal",
     ["source.owner == target.owner"], ["customer submits transfer"],
     ["funds moved atomically"], ["422 when daily limit exceeded", "409 on insufficient funds"]),
    ("External ACH transfer", "A customer shall transfer funds to an external ACH-linked account up to $10,000 per transfer; transfers above this shall require step-up verification.",
     "API", "transaction", "banking-api", "/transfers/ach",
     ["ach_link verified"], ["customer submits transfer"],
     ["ACH batch queued", "confirmation sent"],
     ["422 when amount > 10000 without step-up", "409 on insufficient funds"]),
    ("Recurring transfer", "A premium-tier customer shall be able to schedule a recurring transfer up to $10,000 per occurrence; non-premium accounts capped at $2,500.",
     "API", "transaction", "banking-api", "/transfers/recurring",
     ["tier in {standard,premium}"], ["customer schedules transfer"],
     ["schedule persisted", "next run calculated"],
     ["422 when per-occurrence limit exceeded", "422 when frequency unsupported"]),
    ("Wire transfer", "A customer shall initiate a wire transfer requiring two-factor authentication; transfers above $100,000 require manual review.",
     "API", "transaction", "banking-api", "/transfers/wire",
     ["2fa verified in last 5 min"], ["customer submits wire"],
     ["wire queued", "compliance check started"],
     ["401 when 2fa stale", "202 when manual review required"]),
    ("Bill pay", "A customer shall pay a registered biller between $1 and $50,000 with deterministic settlement date calculation based on biller cut-off.",
     "API", "transaction", "banking-api", "/billpay",
     ["biller registered"], ["customer submits bill pay"],
     ["payment scheduled", "settlement date returned"],
     ["422 when amount out of range"]),
    ("Account statement generation", "A customer shall request monthly statements as PDF; statements older than 7 years shall be fetched from cold storage.",
     "API", "reporting", "banking-api", "/statements/{month}",
     ["account.owner == caller"], ["customer requests statement"],
     ["PDF delivered", "retrieval logged"],
     ["404 if no activity in period", "503 if cold storage unavailable"]),
    ("Transaction dispute", "A customer shall dispute a transaction within 60 days of posting; disputes beyond 60 days shall be rejected.",
     "API", "transaction", "banking-api", "/disputes",
     ["transaction.age < 60d"], ["customer files dispute"],
     ["dispute created", "provisional credit applied"],
     ["422 when transaction.age > 60d"]),
    ("Card freeze / unfreeze", "A customer shall freeze or unfreeze their card instantly; frozen cards must reject all authorization attempts.",
     "API", "transaction", "banking-api", "/cards/{id}/freeze",
     ["card belongs to caller"], ["customer toggles freeze"],
     ["card state updated", "authorization network notified"],
     ["404 when card does not exist"]),
    ("Beneficiary management", "A customer shall add a beneficiary which enters a 24-hour cooling-off period before it can receive transfers.",
     "API", "validation", "banking-api", "/beneficiaries",
     ["authenticated"], ["customer adds beneficiary"],
     ["beneficiary saved in pending state"],
     ["409 if duplicate account"]),
    ("Overdraft protection", "An overdraft shall trigger a draw from the linked savings account up to the linked account's available balance; otherwise the transaction shall be declined.",
     "API", "transaction", "banking-api", "/overdraft",
     ["overdraft linked"], ["debit exceeds checking balance"],
     ["linked savings debited", "fee assessed"],
     ["declined when linked balance insufficient"]),
    ("Fraud alert response", "A customer shall confirm or deny a suspected-fraud alert within 24 hours; unacknowledged alerts shall auto-freeze the account.",
     "API", "auth", "banking-api", "/alerts/{id}",
     ["alert active"], ["customer responds"],
     ["alert closed", "card reissued if fraud"],
     ["410 when alert expired"]),
    ("Account close", "A customer shall close an account with zero balance; closing with non-zero balance shall require sweep to another account.",
     "API", "validation", "banking-api", "/accounts/{id}/close",
     ["account.owner == caller"], ["customer closes account"],
     ["account state=closed", "final statement generated"],
     ["409 when balance != 0 without sweep"]),
    ("KYC refresh", "A customer shall complete a KYC refresh every 365 days; accounts beyond refresh window shall be restricted to inbound transactions only.",
     "API", "auth", "banking-api", "/kyc/refresh",
     ["authenticated"], ["refresh form submitted"],
     ["customer.verified=true refreshed"],
     ["403 when submission fails compliance"]),
    ("Interest accrual", "A savings account shall accrue interest daily using the tier rate and credit interest monthly on the last business day.",
     "INTEGRATION", "transaction", "banking-api", "/cron/interest",
     ["system job"], ["month-end job"],
     ["interest credited", "ledger entry per account"],
     ["reconciliation variance reported"]),
    ("Account-level transaction limits", "A customer shall configure daily per-channel limits within regulatory caps; changes take effect after a 2-hour cool-down.",
     "API", "validation", "banking-api", "/accounts/{id}/limits",
     ["authenticated"], ["customer submits limits"],
     ["pending limit stored", "effective after cool-down"],
     ["422 when over regulatory cap"]),
    ("Joint account operations", "A joint-account holder shall perform transactions; the secondary holder shall not be able to modify ownership.",
     "API", "auth", "banking-api", "/accounts/{id}/joint",
     ["holder is joint"], ["holder performs operation"],
     ["operation applied"],
     ["403 when secondary holder attempts ownership change"]),
    ("Cheque deposit by mobile", "A customer shall deposit a cheque via mobile image; cheques above $5,000 shall require manual verification.",
     "API", "validation", "banking-api", "/deposits/mobile-cheque",
     ["authenticated"], ["image uploaded"],
     ["deposit pending", "decisioning queued"],
     ["422 when image fails MICR decode"]),
    ("Standing order", "A customer shall set up a standing order with start date in the future; past start dates shall be rejected.",
     "API", "validation", "banking-api", "/standing-orders",
     ["authenticated"], ["customer sets up order"],
     ["order scheduled"],
     ["422 when start_date <= today"]),
    ("Savings goal", "A customer shall create a savings goal with a target amount and target date; progress shall be computed nightly.",
     "API", "reporting", "banking-api", "/goals",
     ["authenticated"], ["customer creates goal"],
     ["goal stored", "progress initialised"],
     ["422 when target <= 0"]),
    ("Card PIN change", "A customer shall change their card PIN at most 5 times per 24-hour window.",
     "API", "auth", "banking-api", "/cards/{id}/pin",
     ["card belongs to caller"], ["customer changes PIN"],
     ["PIN updated"],
     ["429 when rate limit exceeded"]),
    ("Biller registration", "A customer shall register a biller only after a 24-hour hold; withdrawals to new billers shall be deferred.",
     "API", "auth", "banking-api", "/billers",
     ["authenticated"], ["customer adds biller"],
     ["biller in hold state"],
     ["409 if duplicate biller"]),
    ("Rate limiting", "The API shall enforce 60 requests per minute per user; overages shall return 429 with retry-after.",
     "API", "integration", "banking-api", "/*",
     ["any endpoint"], ["burst requests"],
     ["429 with retry-after"],
     ["request tail rejected"]),
    ("Reconciliation report", "The system shall produce a daily reconciliation report comparing internal ledger to correspondent bank; non-zero variance shall open an incident.",
     "INTEGRATION", "reporting", "banking-api", "/cron/reconcile",
     ["system job"], ["EOD trigger"],
     ["report stored", "incidents opened on variance"],
     ["incident severity based on variance"]),
]


def bank_requirements() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    idx = 1
    for variant in range(4):  # 25 templates x 4 variants = 100 → slice to 98
        for tmpl in BANK_TEMPLATES:
            (title, stmt, layer, cat, app, endpoint, preconds, triggers, outcomes, errors) = tmpl
            suffix = ["", " (boundary variant)", " (negative variant)",
                      " (idempotency variant)"][variant]
            out.append({
                "id": f"R-FIN-{idx:03d}",
                "domain": "financial_services",
                "layer": layer,
                "category": cat,
                "title": title + suffix,
                "statement": stmt + [
                    "",
                    " Boundary behaviour at exact min/max thresholds must be tested.",
                    " Negative paths (insufficient funds, unauthorised, exceeded limits) must be tested.",
                    " The operation must be idempotent: duplicate submission with the same Idempotency-Key must return the original result."
                ][variant],
                "actors": ["customer"],
                "preconditions": preconds,
                "triggers": triggers,
                "expected_outcomes": outcomes,
                "error_pathways": errors,
                "target_app": app,
                "target_endpoint_or_screen": endpoint,
            })
            idx += 1
    return out[:98]


# ---------------------------------------------------------------------------
# Domain 3: Healthcare (FHIR-lite information exchange)
# ---------------------------------------------------------------------------
FHIR_TEMPLATES = [
    ("Create patient", "A registered clinician shall create a patient resource with validated demographics; creation with missing mandatory elements shall be rejected.",
     "API", "validation", "fhir-lite", "/Patient",
     ["role:clinician"], ["clinician creates patient"],
     ["patient resource stored"], ["422 when mandatory element missing"]),
    ("Read patient", "A clinician shall read a patient resource for patients in their care; reading outside their assignment shall be denied.",
     "API", "auth", "fhir-lite", "/Patient/{id}",
     ["role:clinician"], ["clinician reads patient"],
     ["resource returned", "access audit written"],
     ["403 when clinician not assigned"]),
    ("Update patient", "A clinician shall update patient demographics; historical versions must be preserved.",
     "API", "transaction", "fhir-lite", "/Patient/{id}",
     ["role:clinician"], ["clinician updates resource"],
     ["new version stored", "history preserved"],
     ["409 on version conflict"]),
    ("Delete patient (soft)", "A system-admin shall soft-delete a patient resource; deletion shall not remove history.",
     "API", "auth", "fhir-lite", "/Patient/{id}",
     ["role:admin"], ["admin deletes patient"],
     ["resource marked deleted", "retrievable via _history"],
     ["403 when not admin"]),
    ("Create observation", "A clinician shall create an Observation tied to a patient with LOINC-coded code element; Observations without code shall be rejected.",
     "API", "validation", "fhir-lite", "/Observation",
     ["role:clinician", "patient exists"], ["clinician records observation"],
     ["observation stored"], ["422 when code missing"]),
    ("Create encounter", "A clinician shall create an Encounter for a patient with start and end timestamps; end before start shall be rejected.",
     "API", "validation", "fhir-lite", "/Encounter",
     ["role:clinician", "patient exists"], ["clinician opens encounter"],
     ["encounter stored"], ["422 when end < start"]),
    ("Close encounter", "A clinician shall close an Encounter; closed Encounters shall reject further modifications except for addendum Observations.",
     "API", "validation", "fhir-lite", "/Encounter/{id}/close",
     ["encounter open"], ["clinician closes encounter"],
     ["encounter.status=finished"], ["409 when modifying closed encounter"]),
    ("Create medication request", "A prescribing clinician shall issue a MedicationRequest; requests for controlled substances shall require schedule verification.",
     "API", "auth", "fhir-lite", "/MedicationRequest",
     ["role:prescriber"], ["clinician prescribes"],
     ["request stored", "pharmacy notified"],
     ["403 without schedule verification for CII"]),
    ("Allergy intolerance", "A clinician shall record an AllergyIntolerance linked to the patient; subsequent MedicationRequests shall warn on conflict.",
     "API", "integration", "fhir-lite", "/AllergyIntolerance",
     ["role:clinician"], ["clinician records allergy"],
     ["allergy stored", "alerts regenerated"],
     ["409 when exact duplicate"]),
    ("Immunization record", "A clinician shall record an Immunization with administered date not in the future.",
     "API", "validation", "fhir-lite", "/Immunization",
     ["role:clinician"], ["clinician records immunization"],
     ["immunization stored"], ["422 when date > today"]),
    ("Procedure record", "A clinician shall record a Procedure tied to an Encounter.",
     "API", "validation", "fhir-lite", "/Procedure",
     ["encounter open or referenced"], ["clinician records procedure"],
     ["procedure stored"], ["422 when encounter missing"]),
    ("Diagnostic report", "A clinician shall issue a DiagnosticReport referencing Observations; missing Observation links shall be rejected.",
     "API", "reporting", "fhir-lite", "/DiagnosticReport",
     ["role:clinician"], ["clinician issues report"],
     ["report stored"], ["422 when references empty"]),
    ("Search patients", "A clinician shall search patients by name, MRN, or DOB; only patients in their care shall be returned.",
     "API", "reporting", "fhir-lite", "/Patient?search",
     ["role:clinician"], ["clinician searches"],
     ["filtered bundle returned", "access logged"],
     ["400 when query malformed"]),
    ("Audit log access", "A privacy-officer shall access audit logs scoped to their organisation; cross-organisation access shall be forbidden.",
     "API", "auth", "fhir-lite", "/AuditEvent",
     ["role:privacy-officer"], ["officer queries logs"],
     ["records returned within org"],
     ["403 when crossing org boundary"]),
    ("Consent management", "A patient shall grant or revoke consent for data sharing; revoked consent shall be enforced within 15 minutes.",
     "API", "auth", "fhir-lite", "/Consent",
     ["role:patient"], ["patient updates consent"],
     ["consent stored", "downstream caches invalidated"],
     ["accesses after revoke within SLA denied"]),
    ("Bulk data export", "A provisioned client shall request a FHIR bulk export; large datasets shall be paginated with NDJSON output.",
     "INTEGRATION", "reporting", "fhir-lite", "/$export",
     ["authorized bulk-client"], ["client requests export"],
     ["export job queued", "NDJSON stream produced"],
     ["403 when unauthorised"]),
    ("Inter-facility referral", "A clinician shall send a referral to another facility; the referral shall trigger a secure message and consent check.",
     "INTEGRATION", "integration", "fhir-lite", "/ReferralRequest",
     ["role:clinician"], ["clinician sends referral"],
     ["referral stored", "secure message dispatched"],
     ["403 when consent absent"]),
    ("Lab order routing", "A clinician shall order a lab test; orders shall route to the patient's preferred lab when available.",
     "INTEGRATION", "integration", "fhir-lite", "/ServiceRequest",
     ["role:clinician"], ["clinician orders lab"],
     ["order routed", "status tracked"],
     ["fallback to default lab when preferred unavailable"]),
    ("Vital signs validation", "An Observation with category vital-signs shall have value in clinically plausible range; out-of-range shall be flagged for review.",
     "API", "validation", "fhir-lite", "/Observation",
     ["role:clinician"], ["clinician records vitals"],
     ["observation stored", "flag raised if out of range"], ["review task created"]),
    ("Data retention", "Resources shall be retained per policy; expired resources shall be purged on a nightly job with full audit trail.",
     "INTEGRATION", "auth", "fhir-lite", "/cron/retention",
     ["system job"], ["nightly job runs"],
     ["expired resources purged", "audit log written"],
     ["incident raised on policy mismatch"]),
    ("Break-glass access", "A clinician shall invoke break-glass access for an emergent patient; break-glass use shall be audited and trigger a post-event review.",
     "API", "auth", "fhir-lite", "/BreakGlass",
     ["role:clinician", "patient exists"], ["clinician asserts emergency"],
     ["access granted", "audit event emitted"],
     ["review task created"]),
    ("Device data ingest", "A registered device shall push Observations via FHIR ingest; unregistered devices shall be rejected.",
     "INTEGRATION", "integration", "fhir-lite", "/Ingest",
     ["device registered"], ["device submits"],
     ["observations stored", "normalization applied"],
     ["401 when device cert invalid"]),
    ("Patient portal login", "A patient shall log in using SSO; failed attempts shall be rate-limited and notify the patient.",
     "UI", "auth", "fhir-lite", "/portal/login",
     ["valid SSO assertion"], ["patient logs in"],
     ["session established"], ["429 when too many attempts"]),
    ("Appointment scheduling", "A patient shall schedule an appointment at least 24 hours in advance during provider's available slots.",
     "UI", "validation", "fhir-lite", "/appointments",
     ["authenticated patient"], ["patient books slot"],
     ["appointment created", "provider notified"],
     ["422 when slot unavailable or in past"]),
    ("Message to provider", "A patient shall send a message to their provider; messages containing attachments shall scan for disallowed PHI exfiltration patterns.",
     "UI", "integration", "fhir-lite", "/messages",
     ["authenticated patient"], ["patient sends message"],
     ["message stored", "provider notified"],
     ["blocked when disallowed attachment detected"]),
]


def fhir_requirements() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    idx = 1
    for variant in range(5):
        for tmpl in FHIR_TEMPLATES:
            (title, stmt, layer, cat, app, endpoint, preconds, triggers, outcomes, errors) = tmpl
            suffix = ["", " (boundary)", " (negative)", " (audit)", " (consent)"][variant]
            out.append({
                "id": f"R-HLT-{idx:03d}",
                "domain": "healthcare",
                "layer": layer,
                "category": cat,
                "title": title + suffix,
                "statement": stmt + [
                    "",
                    " Boundary cases on timestamps and numeric elements must be tested.",
                    " Negative paths including permission denial, missing mandatory elements, and conflicting state transitions must be tested.",
                    " An AuditEvent must be emitted for every operation and tested end-to-end.",
                    " Consent state at the time of the operation must be tested, including post-revocation timing windows.",
                ][variant],
                "actors": [p.replace("role:", "") for p in preconds if p.startswith("role:")] or ["user"],
                "preconditions": preconds,
                "triggers": triggers,
                "expected_outcomes": outcomes,
                "error_pathways": errors,
                "target_app": app,
                "target_endpoint_or_screen": endpoint,
            })
            idx += 1
    return out[:102]


def write(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def main() -> None:
    DATASETS.mkdir(exist_ok=True)
    web = hr_requirements()
    fin = bank_requirements()
    hlt = fhir_requirements()
    combined = web + fin + hlt
    assert len(web) == 112, len(web)
    assert len(fin) == 98, len(fin)
    assert len(hlt) == 102, len(hlt)
    assert len(combined) == 312, len(combined)
    write(DATASETS / "commercial_web.json", web)
    write(DATASETS / "financial_services.json", fin)
    write(DATASETS / "healthcare.json", hlt)
    write(DATASETS / "combined.json", combined)
    print(f"commercial_web.json: {len(web)}")
    print(f"financial_services.json: {len(fin)}")
    print(f"healthcare.json: {len(hlt)}")
    print(f"combined.json: {len(combined)}")


if __name__ == "__main__":
    main()
