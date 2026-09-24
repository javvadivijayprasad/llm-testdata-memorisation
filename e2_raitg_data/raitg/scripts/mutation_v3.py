"""All-in-one executable mutation testing for Paper E.

Single self-contained script — tests and runner in one file, no external
imports of baseline_tests (which keeps getting truncated by the
Windows-mount filesystem). Boundary-rich tests for each app.
"""
from __future__ import annotations
import ast
import copy
import json
import time
from collections import defaultdict
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
APPS = ["banking-api", "fhir-lite", "hr-app", "logistics-app"]


# =================== TESTS (inline, comprehensive) ===================

BANKING_TEST = """
api = BankingAPI()
c1 = api.create_customer(verified=True, tier="standard")
assert c1.id > 0 and c1.verified is True
c2 = api.create_customer(verified=False, tier="premium")
assert c2.tier == "premium"
cP = api.create_customer(verified=True, tier="premium")
try:
    api.create_customer(verified=True, tier="invalid_tier")
    raise AssertionError("E1")
except ValueError: pass
# open_checking
try:
    api.open_checking(owner_id=c2.id, initial_deposit_cents=10000)
    raise AssertionError("E2")
except PermissionError: pass
try:
    api.open_checking(owner_id=99999, initial_deposit_cents=10000)
    raise AssertionError("E3")
except PermissionError: pass
try:
    api.open_checking(owner_id=c1.id, initial_deposit_cents=2499)
    raise AssertionError("E4")
except ValueError: pass
a_min = api.open_checking(owner_id=c1.id, initial_deposit_cents=2500)
assert a_min.balance == 2500
a_max = api.open_checking(owner_id=c1.id, initial_deposit_cents=5_000_000)
assert a_max.balance == 5_000_000
try:
    api.open_checking(owner_id=c1.id, initial_deposit_cents=5_000_001)
    raise AssertionError("E5")
except ValueError: pass
a1 = api.open_checking(owner_id=c1.id, initial_deposit_cents=100_000)
# open_savings boundaries
try:
    api.open_savings(owner_id=c1.id, initial_deposit_cents=9_999)
    raise AssertionError("E6")
except ValueError: pass
a_sav = api.open_savings(owner_id=c1.id, initial_deposit_cents=10_000)
assert a_sav.balance == 10_000
try:
    api.open_savings(owner_id=c2.id, initial_deposit_cents=10_000)
    raise AssertionError("E7")
except PermissionError: pass
try:
    api.open_savings(owner_id=99999, initial_deposit_cents=10_000)
    raise AssertionError("E8")
except PermissionError: pass
# transfer_internal boundaries
a3 = api.open_checking(owner_id=c1.id, initial_deposit_cents=200_000)
try:
    api.transfer_internal(source_id=a1.id, target_id=a3.id, amount_cents=-1)
    raise AssertionError("E9")
except ValueError: pass
try:
    api.transfer_internal(source_id=a1.id, target_id=a3.id, amount_cents=0)
    raise AssertionError("E10")
except ValueError: pass
s, t = api.transfer_internal(source_id=a1.id, target_id=a3.id, amount_cents=50_000)
assert s.balance == 50_000 and t.balance == 250_000
# Daily limit boundary
cD = api.create_customer(verified=True, tier="standard")
aD1 = api.open_checking(owner_id=cD.id, initial_deposit_cents=5_000_000)
aD2 = api.open_checking(owner_id=cD.id, initial_deposit_cents=2500)
api.transfer_internal(source_id=aD1.id, target_id=aD2.id, amount_cents=2_500_000)
try:
    api.transfer_internal(source_id=aD1.id, target_id=aD2.id, amount_cents=1)
    raise AssertionError("E11")
except ValueError: pass
# Cross-owner
cE = api.create_customer(verified=True, tier="standard")
aE = api.open_checking(owner_id=cE.id, initial_deposit_cents=10000)
try:
    api.transfer_internal(source_id=a3.id, target_id=aE.id, amount_cents=100)
    raise AssertionError("E12")
except PermissionError: pass
try:
    api.transfer_internal(source_id=99999, target_id=a3.id, amount_cents=100)
    raise AssertionError("E13")
except KeyError: pass
# close_account
try:
    api.close_account(account_id=a3.id)
    raise AssertionError("E14")
except ValueError: pass
try:
    api.close_account(account_id=99999)
    raise AssertionError("E15")
except KeyError: pass
a_zero = api.open_checking(owner_id=c1.id, initial_deposit_cents=2500)
a_dest = api.open_checking(owner_id=c1.id, initial_deposit_cents=100_000)
api.transfer_internal(source_id=a_zero.id, target_id=a_dest.id, amount_cents=2500)
closed = api.close_account(account_id=a_zero.id)
assert closed.status == "closed"
# savings_tier_rate_bps boundaries
assert BankingAPI.savings_tier_rate_bps(99_999) == 10
assert BankingAPI.savings_tier_rate_bps(100_000) == 50
assert BankingAPI.savings_tier_rate_bps(999_999) == 50
assert BankingAPI.savings_tier_rate_bps(1_000_000) == 150
assert BankingAPI.savings_tier_rate_bps(9_999_999) == 150
assert BankingAPI.savings_tier_rate_bps(10_000_000) == 250
assert BankingAPI.savings_tier_rate_bps(50_000) == 10
assert BankingAPI.savings_tier_rate_bps(500_000) == 50
assert BankingAPI.savings_tier_rate_bps(5_000_000) == 150
assert BankingAPI.savings_tier_rate_bps(50_000_000) == 250
# recurring boundaries
sched = api.transfer_recurring_schedule(customer_id=c1.id, amount_cents=100_000, frequency="monthly")
assert sched["status"] == "scheduled"
sched_cap = api.transfer_recurring_schedule(customer_id=c1.id, amount_cents=250_000, frequency="weekly")
assert sched_cap["amount_cents"] == 250_000
try:
    api.transfer_recurring_schedule(customer_id=c1.id, amount_cents=250_001, frequency="weekly")
    raise AssertionError("E16")
except ValueError: pass
try:
    api.transfer_recurring_schedule(customer_id=c1.id, amount_cents=0, frequency="weekly")
    raise AssertionError("E17")
except ValueError: pass
sp = api.transfer_recurring_schedule(customer_id=cP.id, amount_cents=1_000_000, frequency="biweekly")
assert sp["amount_cents"] == 1_000_000
try:
    api.transfer_recurring_schedule(customer_id=cP.id, amount_cents=1_000_001, frequency="biweekly")
    raise AssertionError("E18")
except ValueError: pass
for fq in ("weekly", "biweekly", "monthly"):
    sf = api.transfer_recurring_schedule(customer_id=c1.id, amount_cents=1_000, frequency=fq)
    assert sf["frequency"] == fq
try:
    api.transfer_recurring_schedule(customer_id=c1.id, amount_cents=10_000, frequency="annually")
    raise AssertionError("E19")
except ValueError: pass
try:
    api.transfer_recurring_schedule(customer_id=99999, amount_cents=1_000, frequency="weekly")
    raise AssertionError("E20")
except KeyError: pass
"""

FHIR_TEST = """
api = FHIRLite()
p = api.create_patient(family_name="Smith", given_name="Jane", birth_date="1990-01-15", role="clinician")
assert p.id > 0 and p.family_name == "Smith"
try:
    api.create_patient(family_name="X", given_name="Y", birth_date="2000-01-01", role="patient")
    raise AssertionError("F1")
except PermissionError: pass
try:
    api.create_patient(family_name="", given_name="Y", birth_date="2000-01-01", role="admin")
    raise AssertionError("F2")
except ValueError: pass
try:
    api.create_patient(family_name="X", given_name="", birth_date="2000-01-01", role="admin")
    raise AssertionError("F3")
except ValueError: pass
try:
    api.create_patient(family_name="A", given_name="B", birth_date="not-a-date", role="admin")
    raise AssertionError("F4")
except ValueError: pass
p2 = api.create_patient(family_name="Doe", given_name="John", birth_date="1985-05-10", role="admin")
got = api.read_patient(patient_id=p2.id, role="clinician", assigned_patient_ids={p2.id})
assert got.id == p2.id
try:
    api.read_patient(patient_id=p2.id, role="admin", assigned_patient_ids={p2.id})
    raise AssertionError("F5")
except PermissionError: pass
try:
    api.read_patient(patient_id=p2.id, role="clinician", assigned_patient_ids=set())
    raise AssertionError("F6")
except PermissionError: pass
api.soft_delete_patient(patient_id=p2.id, role="admin")
try:
    api.read_patient(patient_id=p2.id, role="clinician", assigned_patient_ids={p2.id})
    raise AssertionError("F7")
except KeyError: pass
try:
    api.soft_delete_patient(patient_id=p.id, role="clinician")
    raise AssertionError("F8")
except PermissionError: pass
assert api.soft_delete_patient(patient_id=99999, role="admin") is False
e = api.create_encounter(patient_id=p.id, start_iso="2026-01-01T10:00:00", end_iso="2026-01-01T11:00:00", role="clinician")
assert e.status == "in-progress"
try:
    api.create_encounter(patient_id=p.id, start_iso="2026-01-02T10:00:00", end_iso="2026-01-01T10:00:00", role="clinician")
    raise AssertionError("F9")
except ValueError: pass
e_open = api.create_encounter(patient_id=p.id, start_iso="2026-01-03T10:00:00", end_iso=None, role="clinician")
assert e_open.end_iso is None
try:
    api.create_encounter(patient_id=99999, start_iso="2026-01-01T10:00:00", end_iso=None, role="clinician")
    raise AssertionError("F10")
except KeyError: pass
try:
    api.create_encounter(patient_id=p.id, start_iso="2026-01-01T10:00:00", end_iso=None, role="admin")
    raise AssertionError("F11")
except PermissionError: pass
e2 = api.close_encounter(encounter_id=e.id)
assert e2.status == "finished"
try:
    api.close_encounter(encounter_id=e.id)
    raise AssertionError("F12")
except ValueError: pass
try:
    api.close_encounter(encounter_id=99999)
    raise AssertionError("F13")
except KeyError: pass
o = api.create_observation(patient_id=p.id, code="8867-4", value=80.0, role="clinician")
assert o.flagged is False
o2 = api.create_observation(patient_id=p.id, code="8867-4", value=250.0, role="clinician")
assert o2.flagged is True
try:
    api.create_observation(patient_id=p.id, code="", value=80.0, role="clinician")
    raise AssertionError("F14")
except ValueError: pass
try:
    api.create_observation(patient_id=99999, code="8867-4", value=80.0, role="clinician")
    raise AssertionError("F15")
except KeyError: pass
try:
    api.create_observation(patient_id=p.id, code="8867-4", value=80.0, role="admin")
    raise AssertionError("F16")
except PermissionError: pass
# _is_out_of_range exact boundaries
assert FHIRLite._is_out_of_range("8867-4", 30.0) is False
assert FHIRLite._is_out_of_range("8867-4", 220.0) is False
assert FHIRLite._is_out_of_range("8867-4", 29.9) is True
assert FHIRLite._is_out_of_range("8867-4", 220.1) is True
assert FHIRLite._is_out_of_range("8480-6", 70.0) is False
assert FHIRLite._is_out_of_range("8480-6", 200.0) is False
assert FHIRLite._is_out_of_range("8480-6", 69.9) is True
assert FHIRLite._is_out_of_range("8480-6", 200.1) is True
assert FHIRLite._is_out_of_range("8462-4", 40.0) is False
assert FHIRLite._is_out_of_range("8462-4", 130.0) is False
assert FHIRLite._is_out_of_range("8462-4", 39.9) is True
assert FHIRLite._is_out_of_range("8462-4", 130.1) is True
assert FHIRLite._is_out_of_range("29463-7", 1.0) is False
assert FHIRLite._is_out_of_range("29463-7", 400.0) is False
assert FHIRLite._is_out_of_range("29463-7", 0.9) is True
assert FHIRLite._is_out_of_range("29463-7", 400.1) is True
assert FHIRLite._is_out_of_range("8310-5", 32.0) is False
assert FHIRLite._is_out_of_range("8310-5", 42.0) is False
assert FHIRLite._is_out_of_range("8310-5", 31.9) is True
assert FHIRLite._is_out_of_range("8310-5", 42.1) is True
assert FHIRLite._is_out_of_range("unknown-code", 999.0) is False
"""

HR_TEST = """
e = Employee(id=1, email="x@y.com", full_name="A B")
assert e.id == 1 and e.role == "employee"
app = HRApp()
emp = app.create_employee(email="alice@example.com", full_name="Alice")
assert emp.id > 0
try:
    app.create_employee(email="no-at", full_name="X")
    raise AssertionError("H1")
except ValueError: pass
try:
    app.create_employee(email="", full_name="X")
    raise AssertionError("H2")
except ValueError: pass
try:
    app.create_employee(email="x@y.com", full_name="")
    raise AssertionError("H3")
except ValueError: pass
try:
    app.create_employee(email="x@y.com", full_name="Y", employment_type="freelance")
    raise AssertionError("H4")
except ValueError: pass
for et in ("full_time", "part_time", "contractor"):
    e_et = app.create_employee(email=f"u_{et}@y.com", full_name=f"U {et}", employment_type=et)
    assert e_et.employment_type == et
try:
    app.delete_employee(employee_id=emp.id, actor_role="employee")
    raise AssertionError("H5")
except PermissionError: pass
e_to_del = app.create_employee(email="del@y.com", full_name="ToDel")
assert app.delete_employee(employee_id=e_to_del.id, actor_role="admin") is True
assert app.delete_employee(employee_id=99999, actor_role="admin") is False
e_hr = app.create_employee(email="hrdel@y.com", full_name="HRDel")
assert app.delete_employee(employee_id=e_hr.id, actor_role="hr-admin") is True
lr1 = app.submit_leave(employee_id=emp.id, start_date="2026-02-01", end_date="2026-02-03", days=3)
try:
    app.submit_leave(employee_id=emp.id, start_date="2026-02-02", end_date="2026-02-04", days=3)
    raise AssertionError("H6")
except ValueError: pass
try:
    app.submit_leave(employee_id=emp.id, start_date="2026-05-10", end_date="2026-05-05", days=2)
    raise AssertionError("H7")
except ValueError: pass
try:
    app.submit_leave(employee_id=emp.id, start_date="2026-06-01", end_date="2026-06-01", days=0)
    raise AssertionError("H8")
except ValueError: pass
lr_min = app.submit_leave(employee_id=emp.id, start_date="2026-07-01", end_date="2026-07-01", days=1)
assert lr_min.days == 1
lr30 = app.submit_leave(employee_id=emp.id, start_date="2026-08-01", end_date="2026-08-30", days=30)
assert lr30.days == 30
try:
    app.submit_leave(employee_id=emp.id, start_date="2026-09-01", end_date="2026-10-01", days=31)
    raise AssertionError("H9")
except ValueError: pass
try:
    app.submit_leave(employee_id=99999, start_date="2026-11-01", end_date="2026-11-02", days=2)
    raise AssertionError("H10")
except ValueError: pass
lr_pending = app.submit_leave(employee_id=emp.id, start_date="2026-12-01", end_date="2026-12-02", days=2)
lr2 = app.approve_leave(request_id=lr_pending.id, manager_id=99)
assert lr2.state == "approved"
try:
    app.approve_leave(request_id=lr_pending.id, manager_id=99)
    raise AssertionError("H11")
except ValueError: pass
try:
    app.approve_leave(request_id=99999, manager_id=99)
    raise AssertionError("H12")
except KeyError: pass
try:
    app.submit_timesheet(employee_id=emp.id, week_start="2026-01-01", per_day_hours=[8.0]*6)
    raise AssertionError("H13")
except ValueError: pass
try:
    app.submit_timesheet(employee_id=emp.id, week_start="2026-01-01", per_day_hours=[8.0]*8)
    raise AssertionError("H14")
except ValueError: pass
ts24 = app.submit_timesheet(employee_id=emp.id, week_start="2026-04-01", per_day_hours=[24.0] + [0.0]*6)
assert ts24.state == "submitted"
ts0 = app.submit_timesheet(employee_id=emp.id, week_start="2026-04-08", per_day_hours=[0.0]*7)
assert ts0.state == "submitted"
try:
    app.submit_timesheet(employee_id=emp.id, week_start="2026-01-01", per_day_hours=[8.0]*6 + [25.0])
    raise AssertionError("H15")
except ValueError: pass
try:
    app.submit_timesheet(employee_id=emp.id, week_start="2026-01-01", per_day_hours=[8.0]*6 + [-1.0])
    raise AssertionError("H16")
except ValueError: pass
ts80 = app.submit_timesheet(employee_id=emp.id, week_start="2026-05-01", per_day_hours=[80.0/7]*7)
assert ts80.state == "submitted"
try:
    app.submit_timesheet(employee_id=emp.id, week_start="2026-01-01", per_day_hours=[15.0]*7)
    raise AssertionError("H17")
except ValueError: pass
ts2 = app.submit_timesheet(employee_id=emp.id, week_start="2026-01-01", per_day_hours=[8.0]*5 + [0.0, 0.0])
assert ts2.state == "submitted"
assert HRApp.password_ok("Short1!Pw") is False
assert HRApp.password_ok("Exact10P1!") is True
assert HRApp.password_ok("longenoughpw1!") is False
assert HRApp.password_ok("LongEnoughPwNoSym1") is False
assert HRApp.password_ok("LongEnoughPwNoDigit!") is False
assert HRApp.password_ok("ValidPassword1!") is True
for s in "!@#$%^&*()_-+=[]{}":
    assert HRApp.password_ok(f"ValidPwd12{s}") is True
"""

LOGISTICS_TEST = """
# Hand-authored logistics-app baseline (added 2026-08-06 to close Threat T10).
# Import Shipment for the dataclass-default test; falls back to __init__.__globals__
# lookup when app.py was exec'd into a bare dict (the mutation harness case).
_Shipment = globals().get("Shipment") or LogisticsApp.__init__.__globals__.get("Shipment")

# --- create_shipment happy: exact id==1, hazmat default False, audit content
la = LogisticsApp()
sh = la.create_shipment("A", "B", 5.0, 30, 20, 15)
assert sh.id == 1 and sh.status == "created" and sh.hazmat is False
assert sh.driver_id is None
assert la.audit[-1] == {"action": "shipment.create", "id": sh.id}

# --- _next_id strictly increments by 1 (shared shipment/driver counter)
a = la.create_shipment("A", "B", 1.0, 10, 10, 10)
b = la.create_shipment("A", "B", 1.0, 10, 10, 10)
assert b.id == a.id + 1
d = la.register_driver("Alex", "C", 100.0)
e = la.register_driver("Bea",  "C", 100.0)
assert d.id == b.id + 1
assert e.id == d.id + 1

# --- create_shipment weight boundaries
try: la.create_shipment("A", "B", 0, 10, 10, 10); raise AssertionError("L1")
except ValueError: pass
la.create_shipment("A", "B", 0.01, 10, 10, 10)
la.create_shipment("A", "B", 50.0, 10, 10, 10)
try: la.create_shipment("A", "B", 50.1, 10, 10, 10); raise AssertionError("L2")
except ValueError: pass
try: la.create_shipment("A", "B", -1.0, 10, 10, 10); raise AssertionError("L3")
except ValueError: pass

# --- create_shipment dimension boundaries (each axis)
la.create_shipment("A", "B", 1.0, 200, 200, 200)
la.create_shipment("A", "B", 1.0, 1, 1, 1)
la.create_shipment("A", "B", 1.0, 0.01, 0.01, 0.01)
for bad in [(201,10,10),(10,201,10),(10,10,201),(0,10,10),(10,0,10),(10,10,0)]:
    try: la.create_shipment("A", "B", 1.0, *bad); raise AssertionError("L4")
    except ValueError: pass

# --- origin/destination
try: la.create_shipment("", "B", 1.0, 10, 10, 10); raise AssertionError("L5")
except ValueError: pass
try: la.create_shipment("A", "", 1.0, 10, 10, 10); raise AssertionError("L6")
except ValueError: pass
try: la.create_shipment("A", "A", 1.0, 10, 10, 10); raise AssertionError("L7")
except ValueError: pass

# --- register_driver boundaries
try: la.register_driver("Zero", "C", 0); raise AssertionError("L8")
except ValueError: pass
dr_tiny = la.register_driver("Tiny", "C", 1.0)
assert dr_tiny.capacity_kg == 1.0
la.register_driver("Big", "C", 1000.0)
try: la.register_driver("Huge", "C", 1000.01); raise AssertionError("L9")
except ValueError: pass
try: la.register_driver("Neg", "C", -1.0); raise AssertionError("L10")
except ValueError: pass
for lc in ("B", "C", "C+haz"):
    dd = la.register_driver(f"D_{lc}", lc, 100.0)
    assert dd.license_class == lc and dd.status == "available"
try: la.register_driver("Bad", "A", 100.0); raise AssertionError("L11")
except ValueError: pass
try: la.register_driver("Bad2", "D", 100.0); raise AssertionError("L12")
except ValueError: pass
try: la.register_driver("", "C", 100.0); raise AssertionError("L13")
except ValueError: pass

# --- assign_driver return value + state
la2 = LogisticsApp()
sh1 = la2.create_shipment("X", "Y", 5.0, 20, 20, 20)
dr1 = la2.register_driver("Alex", "C", 100.0)
ret = la2.assign_driver(sh1.id, dr1.id)
assert ret is not None and ret is sh1
assert ret.driver_id == dr1.id and ret.status == "assigned"
assert la2.drivers[dr1.id].status == "engaged"
assert la2.audit[-1] == {"action": "shipment.assign", "id": sh1.id, "driver": dr1.id}
dr1b = la2.register_driver("Bea", "C", 100.0)
try: la2.assign_driver(sh1.id, dr1b.id); raise AssertionError("L14")
except ValueError: pass

# --- capacity: weight==capacity OK, > fails
dr_s = la2.register_driver("Ed", "C", 25.0)
sh_eq = la2.create_shipment("X", "Y", 25.0, 20, 20, 20)
la2.assign_driver(sh_eq.id, dr_s.id)
dr_s2 = la2.register_driver("Ed2", "C", 25.0)
sh_ov = la2.create_shipment("X", "Y", 30.0, 20, 20, 20)
try: la2.assign_driver(sh_ov.id, dr_s2.id); raise AssertionError("L15")
except ValueError: pass
sh2 = la2.create_shipment("X", "Y", 5.0, 10, 10, 10)
try: la2.assign_driver(sh2.id, dr_s.id); raise AssertionError("L16")
except ValueError: pass

# --- hazmat license
la3 = LogisticsApp()
dr_c = la3.register_driver("PlainC", "C", 100.0)
dr_b = la3.register_driver("PlainB", "B", 100.0)
dr_h = la3.register_driver("HazC", "C+haz", 100.0)
sh_h1 = la3.create_shipment("X", "Y", 5.0, 10, 10, 10, hazmat=True)
try: la3.assign_driver(sh_h1.id, dr_c.id); raise AssertionError("L17")
except ValueError: pass
sh_h2 = la3.create_shipment("X", "Y", 5.0, 10, 10, 10, hazmat=True)
try: la3.assign_driver(sh_h2.id, dr_b.id); raise AssertionError("L18")
except ValueError: pass
la3.assign_driver(sh_h1.id, dr_h.id)
assert la3.shipments[sh_h1.id].driver_id == dr_h.id

# --- assign unknown ids
la4 = LogisticsApp()
dr_u = la4.register_driver("Alex", "C", 100.0)
sh_u = la4.create_shipment("X", "Y", 5.0, 10, 10, 10)
try: la4.assign_driver(99999, dr_u.id); raise AssertionError("L19")
except KeyError: pass
try: la4.assign_driver(sh_u.id, 99999); raise AssertionError("L20")
except KeyError: pass

# --- cancel_shipment role + state
la5 = LogisticsApp()
sh_ca = la5.create_shipment("X", "Y", 1.0, 10, 10, 10)
assert la5.cancel_shipment(sh_ca.id, "dispatcher") is True
assert la5.shipments[sh_ca.id].status == "cancelled"
assert la5.audit[-1] == {"action": "shipment.cancel", "id": sh_ca.id}
sh_cb = la5.create_shipment("X", "Y", 1.0, 10, 10, 10)
dr_ca = la5.register_driver("Alex", "C", 100.0)
la5.assign_driver(sh_cb.id, dr_ca.id)
assert la5.cancel_shipment(sh_cb.id, "admin") is True
sh_cc = la5.create_shipment("X", "Y", 1.0, 10, 10, 10)
for role in ("driver", "customer", "", "clerk"):
    try: la5.cancel_shipment(sh_cc.id, role); raise AssertionError("L21_"+role)
    except PermissionError: pass
assert la5.cancel_shipment(99999, "admin") is False
sh_cd = la5.create_shipment("X", "Y", 1.0, 10, 10, 10)
la5.shipments[sh_cd.id].status = "in_transit"
try: la5.cancel_shipment(sh_cd.id, "dispatcher"); raise AssertionError("L22")
except ValueError: pass

# --- confirm_delivery full flow
la6 = LogisticsApp()
shd = la6.create_shipment("P", "Q", 5.0, 20, 20, 20)
drd = la6.register_driver("Fi", "C", 100.0)
la6.assign_driver(shd.id, drd.id)
la6.shipments[shd.id].status = "in_transit"
id_before = la6._next_id
att = la6.confirm_delivery(shd.id, "2026-06-17T10:00:00", "AB")
assert att is not None
assert att.outcome == "delivered" and att.signature == "AB"
assert att.shipment_id == shd.id and att.timestamp == "2026-06-17T10:00:00"
assert la6.shipments[shd.id].status == "delivered"
assert la6.drivers[drd.id].status == "available"
assert att.id == id_before
assert la6._next_id == id_before + 1
assert la6.audit[-1] == {"action": "delivery.confirm", "id": att.id}

# --- confirm_delivery signature boundary + preconditions
la7 = LogisticsApp()
sh_sig = la7.create_shipment("P", "Q", 1.0, 10, 10, 10)
la7.shipments[sh_sig.id].status = "in_transit"
try: la7.confirm_delivery(sh_sig.id, "t", ""); raise AssertionError("L23")
except ValueError: pass
try: la7.confirm_delivery(sh_sig.id, "t", "A"); raise AssertionError("L24")
except ValueError: pass
att_ok = la7.confirm_delivery(sh_sig.id, "t", "AB")
assert att_ok.signature == "AB"
sh_ni = la7.create_shipment("P", "Q", 1.0, 10, 10, 10)
try: la7.confirm_delivery(sh_ni.id, "t", "OK"); raise AssertionError("L25")
except ValueError: pass
try: la7.confirm_delivery(99999, "t", "OK"); raise AssertionError("L26")
except KeyError: pass

# --- report_exception all 4 outcomes + counter increments + driver freed
for out in ("refused", "damaged", "wrong_address", "no_response"):
    la_e = LogisticsApp()
    sh_e = la_e.create_shipment("R", "S", 1.0, 10, 10, 10)
    dr_e = la_e.register_driver("D", "C", 100.0)
    la_e.assign_driver(sh_e.id, dr_e.id)
    la_e.shipments[sh_e.id].status = "in_transit"
    ib = la_e._next_id
    at = la_e.report_exception(sh_e.id, "t", out)
    assert at is not None and at.outcome == out and at.signature is None
    assert at.shipment_id == sh_e.id
    assert la_e.shipments[sh_e.id].status == "failed"
    assert la_e.drivers[dr_e.id].status == "available"
    assert at.id == ib and la_e._next_id == ib + 1
    assert la_e.audit[-1] == {"action": "delivery.exception", "id": at.id, "outcome": out}

# --- report_exception invalid + preconditions
la8 = LogisticsApp()
sh_re = la8.create_shipment("R", "S", 1.0, 10, 10, 10)
la8.shipments[sh_re.id].status = "in_transit"
for bad in ("delivered", "bogus", "", "REFUSED"):
    try: la8.report_exception(sh_re.id, "t", bad); raise AssertionError("L27_"+bad)
    except ValueError: pass
sh_ni2 = la8.create_shipment("R", "S", 1.0, 10, 10, 10)
try: la8.report_exception(sh_ni2.id, "t", "damaged"); raise AssertionError("L28")
except ValueError: pass
try: la8.report_exception(99999, "t", "refused"); raise AssertionError("L29")
except KeyError: pass

# --- forward-only state machine
la9 = LogisticsApp()
sh_st = la9.create_shipment("P", "Q", 5.0, 20, 20, 20)
assert sh_st.status == "created"
dr_st = la9.register_driver("Alex", "C", 100.0)
la9.assign_driver(sh_st.id, dr_st.id)
assert la9.shipments[sh_st.id].status == "assigned"
la9.shipments[sh_st.id].status = "in_transit"
la9.confirm_delivery(sh_st.id, "t", "OK")
assert la9.shipments[sh_st.id].status == "delivered"
try: la9.confirm_delivery(sh_st.id, "t", "OK"); raise AssertionError("L30")
except ValueError: pass
try: la9.report_exception(sh_st.id, "t", "refused"); raise AssertionError("L31")
except ValueError: pass

# --- is_dimension_ok exact boundaries
assert LogisticsApp.is_dimension_ok(1, 1, 1) is True
assert LogisticsApp.is_dimension_ok(0.01, 0.01, 0.01) is True
assert LogisticsApp.is_dimension_ok(200, 200, 200) is True
assert LogisticsApp.is_dimension_ok(201, 1, 1) is False
assert LogisticsApp.is_dimension_ok(1, 201, 1) is False
assert LogisticsApp.is_dimension_ok(1, 1, 201) is False
assert LogisticsApp.is_dimension_ok(0, 1, 1) is False
assert LogisticsApp.is_dimension_ok(1, 0, 1) is False
assert LogisticsApp.is_dimension_ok(1, 1, 0) is False
assert LogisticsApp.is_dimension_ok(-1, 1, 1) is False

# --- shipping_fee formula + rounding
assert LogisticsApp.shipping_fee(1.0) == 7.5
assert LogisticsApp.shipping_fee(2.0) == 10.0
assert LogisticsApp.shipping_fee(10.0) == 30.0
assert LogisticsApp.shipping_fee(1.0, hazmat=True) == 22.5
assert LogisticsApp.shipping_fee(10.0, hazmat=True) == 45.0
# 5 + 2.5*0.049 = 5.1225 -> round(x,2)=5.12 (kills const:2->1 and 2->3 on round)
assert LogisticsApp.shipping_fee(0.049) == 5.12
try: LogisticsApp.shipping_fee(0); raise AssertionError("L32")
except ValueError: pass
try: LogisticsApp.shipping_fee(-0.01); raise AssertionError("L33")
except ValueError: pass

# --- audit log order
la10 = LogisticsApp()
assert la10.audit == []
sh_al = la10.create_shipment("A", "B", 1.0, 10, 10, 10)
dr_al = la10.register_driver("Alex", "C", 100.0)
la10.assign_driver(sh_al.id, dr_al.id)
la10.shipments[sh_al.id].status = "in_transit"
la10.confirm_delivery(sh_al.id, "t", "OK")
assert [a["action"] for a in la10.audit] == ["shipment.create", "driver.register",
                                              "shipment.assign", "delivery.confirm"]
sh_al2 = la10.create_shipment("A", "B", 1.0, 10, 10, 10)
la10.shipments[sh_al2.id].status = "in_transit"
la10.report_exception(sh_al2.id, "t", "refused")
assert la10.audit[-1]["action"] == "delivery.exception"
assert la10.audit[-1]["outcome"] == "refused"
"""

TESTS = {"banking-api": BANKING_TEST, "fhir-lite": FHIR_TEST, "hr-app": HR_TEST,
         "logistics-app": LOGISTICS_TEST}


def run_app(app_name: str, src_text: str) -> bool:
    namespace = {}
    try:
        compile(src_text, "app.py", "exec")
    except SyntaxError:
        return False
    try:
        exec(src_text, namespace)
    except Exception:
        return False
    try:
        exec(TESTS[app_name], namespace)
        return True
    except Exception:
        return False


# =================== Mutation operators (same as v2) ===================
COMPARE_SWAPS = {ast.Lt: ast.Gt, ast.Gt: ast.Lt, ast.LtE: ast.GtE,
                  ast.GtE: ast.LtE, ast.Eq: ast.NotEq, ast.NotEq: ast.Eq}
BOOLOP_SWAPS = {ast.And: ast.Or, ast.Or: ast.And}


def generate_mutants(src: str) -> list:
    tree = ast.parse(src)
    mutants = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            for i, op in enumerate(node.ops):
                for old, new in COMPARE_SWAPS.items():
                    if isinstance(op, old):
                        t = copy.deepcopy(tree)
                        for c in ast.walk(t):
                            if (isinstance(c, ast.Compare)
                                    and getattr(c, "lineno", None) == node.lineno
                                    and getattr(c, "col_offset", None) == node.col_offset):
                                c.ops[i] = new()
                                break
                        try:
                            mutants.append((f"cmp:{old.__name__}->{new.__name__}",
                                             node.lineno, ast.unparse(t)))
                        except Exception: pass
    for node in ast.walk(tree):
        if isinstance(node, ast.BoolOp):
            for old, new in BOOLOP_SWAPS.items():
                if isinstance(node.op, old):
                    t = copy.deepcopy(tree)
                    for c in ast.walk(t):
                        if (isinstance(c, ast.BoolOp)
                                and getattr(c, "lineno", None) == node.lineno):
                            c.op = new()
                            break
                    try:
                        mutants.append((f"bool:{old.__name__}->{new.__name__}",
                                         node.lineno, ast.unparse(t)))
                    except Exception: pass
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            if isinstance(node.value, bool): continue
            for delta in (1, -1):
                t = copy.deepcopy(tree)
                for c in ast.walk(t):
                    if (isinstance(c, ast.Constant)
                            and getattr(c, "lineno", None) == node.lineno
                            and getattr(c, "col_offset", None) == node.col_offset
                            and not isinstance(c.value, bool)
                            and isinstance(c.value, (int, float))):
                        c.value = node.value + delta
                        break
                try:
                    mutants.append((f"const:{node.value}->{node.value + delta}",
                                     node.lineno, ast.unparse(t)))
                except Exception: pass
    for node in ast.walk(tree):
        if isinstance(node, ast.Return) and node.value is not None:
            t = copy.deepcopy(tree)
            for c in ast.walk(t):
                if (isinstance(c, ast.Return)
                        and getattr(c, "lineno", None) == node.lineno):
                    c.value = None
                    break
            try:
                mutants.append((f"ret-none", node.lineno, ast.unparse(t)))
            except Exception: pass
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, bool):
            t = copy.deepcopy(tree)
            for c in ast.walk(t):
                if (isinstance(c, ast.Constant)
                        and getattr(c, "lineno", None) == node.lineno
                        and getattr(c, "col_offset", None) == node.col_offset
                        and isinstance(c.value, bool)):
                    c.value = not node.value
                    break
            try:
                mutants.append((f"bool_const:{node.value}->{not node.value}",
                                 node.lineno, ast.unparse(t)))
            except Exception: pass
    return mutants


def score_app(app: str) -> dict:
    src = (ROOT / "repo" / app / "app.py").read_text()
    if not run_app(app, src):
        return {"app": app, "error": "baseline failed"}
    print(f"  [{app}] baseline PASS", flush=True)
    mutants = generate_mutants(src)
    print(f"  [{app}] {len(mutants)} mutants", flush=True)
    killed = 0
    survived_list = []
    by_op = defaultdict(lambda: {"killed": 0, "survived": 0})
    for i, (op, lineno, mut_src) in enumerate(mutants):
        try:
            passes = run_app(app, mut_src)
        except Exception:
            passes = False
        if passes:
            survived_list.append((op, lineno))
            by_op[op.split(":")[0]]["survived"] += 1
        else:
            killed += 1
            by_op[op.split(":")[0]]["killed"] += 1
    return {
        "app": app,
        "mutants": len(mutants),
        "killed": killed,
        "survived": len(mutants) - killed,
        "mutation_score": round(killed / max(1, len(mutants)), 4),
        "by_op": {k: dict(v) for k, v in by_op.items()},
        "survivors_sample": survived_list[:10],
    }


def main():
    t0 = time.time()
    print(f"=== mutation_v3 (inline tests) ===", flush=True)
    results = []
    for app in APPS:
        print(f"\n[{time.strftime('%H:%M:%S')}] {app}", flush=True)
        r = score_app(app)
        results.append(r)
        print(f"  score = {r.get('mutation_score', 'ERR')}", flush=True)

    total_mut = sum(r["mutants"] for r in results if "mutants" in r)
    total_killed = sum(r["killed"] for r in results if "killed" in r)
    aggregate = round(total_killed / max(1, total_mut), 4)
    out = {"aggregate": aggregate, "total_mutants": total_mut,
           "total_killed": total_killed, "per_app": results}
    (ROOT / "results" / "mutation_v3.json").write_text(json.dumps(out, indent=2))

    # Tables
    import csv
    with open(ROOT / "tables" / "executable_mutation_per_app.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["app","mutants","killed","survived","mutation_score"])
        for r in results:
            if "mutants" in r:
                w.writerow([r["app"], r["mutants"], r["killed"], r["survived"], r["mutation_score"]])
    with open(ROOT / "tables" / "executable_mutation_by_operator.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["app","operator","killed","survived","kill_rate"])
        for r in results:
            for op, c in r.get("by_op", {}).items():
                total = c["killed"] + c["survived"]
                w.writerow([r["app"], op, c["killed"], c["survived"],
                              round(c["killed"]/max(1,total), 4)])

    print(f"\n[{time.time()-t0:.1f}s] DONE")
    print(f"Aggregate: {total_killed}/{total_mut} = {aggregate*100:.2f}%")
    for r in results:
        if "mutation_score" in r:
            print(f"  {r['app']:14s} {r['killed']:>3}/{r['mutants']:<3} = {r['mutation_score']*100:.2f}%")
            for op, c in r["by_op"].items():
                total = c["killed"] + c["survived"]
                print(f"    {op:10s} {c['killed']:>3}/{total:<3} ({c['killed']/max(1,total)*100:.1f}%)")


if __name__ == "__main__":
    main()
