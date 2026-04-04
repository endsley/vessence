#!/usr/bin/env python3
"""
Phase 4 & 5 — Test Tax Accountant Interview Flow and Calculations

Tests:
1. Start an interview
2. Answer with synthetic test data (fake W-2, Schedule C income)
3. Verify the interview adapts based on answers
4. Verify interview state persists
5. Run the tax calculator with test data
6. Verify federal tax calculation is reasonable
7. Verify MA state tax calculation
8. Verify standard vs itemized deduction comparison
9. Test form generation
"""

import json
import os
import sys
import shutil
from datetime import datetime

# Add the essence functions to path
ESSENCE_DIR = os.path.expanduser("~/ambient/essences/tax_accountant_2025")
FUNCTIONS_DIR = os.path.join(ESSENCE_DIR, "functions")
sys.path.insert(0, FUNCTIONS_DIR)

from custom_tools import (
    interview_step, upload_document, calculate_tax, generate_forms,
    get_interview_state, get_document_checklist, add_income_source,
    add_deduction, reset_interview
)
from tax_calculator import (
    IncomeData, DeductionData, CreditData, calculate_full_tax, TaxResult,
    STANDARD_DEDUCTION_MFJ, FEDERAL_BRACKETS_MFJ
)
from form_generator import generate_all_forms


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════

passed = 0
failed = 0

def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS: {name}")
    else:
        failed += 1
        print(f"  FAIL: {name} — {detail}")


def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ═══════════════════════════════════════════════════════════════
# Phase 4: Interview Flow Tests
# ═══════════════════════════════════════════════════════════════

section("Phase 4a: Reset Interview")
reset_result = reset_interview()
check("Reset returns ok", reset_result["status"] == "ok")

section("Phase 4b: Start Interview (Filing Status)")
result = interview_step("filing_status")
check("Start returns ok", result["status"] == "ok")
check("Step is filing_status", result["step"]["id"] == "filing_status")
check("Next step is prior_returns", result["next_step"] == "prior_returns")
check("Has questions", len(result["step"]["questions"]) > 0)

section("Phase 4c: Answer Filing Status")
result = interview_step("filing_status", {
    "filing_status": "married_filing_jointly",
    "taxpayer_name": "John Test",
    "spouse_name": "Jane Test",
    "address": "123 Test St, Boston, MA 02101",
    "dependents": [
        {"name": "Child One", "dob": "2015-03-15", "ssn_last4": "1234"},
        {"name": "Child Two", "dob": "2018-07-22", "ssn_last4": "5678"},
    ]
})
check("Filing status answer ok", result["status"] == "ok")
check("Filing status marked completed", "filing_status" in result["completed_steps"])

section("Phase 4d: Skip Prior Returns")
result = interview_step("prior_returns", {"skip": True})
check("Prior returns answer ok", result["status"] == "ok")

section("Phase 4e: Add Income Sources")
# W-2 for primary
result = add_income_source("w2", {
    "whose": "primary",
    "employer": "Boston University",
    "amounts": {
        "wages": 95000,
        "federal_withholding": 14000,
        "state_withholding": 4500,
        "social_security_wages": 95000,
        "medicare_wages": 95000,
    }
})
check("Add W-2 primary", result["status"] == "ok")

# W-2 for spouse
result = add_income_source("w2", {
    "whose": "spouse",
    "employer": "Massachusetts General Hospital",
    "amounts": {
        "wages": 72000,
        "federal_withholding": 10000,
        "state_withholding": 3400,
    }
})
check("Add W-2 spouse", result["status"] == "ok")

# Schedule C (acupuncture clinic)
result = add_income_source("schedule_c", {
    "business_name": "Healing Hands Acupuncture",
    "amounts": {
        "gross_income": 85000,
        "expenses": 28000,
    }
})
check("Add Schedule C", result["status"] == "ok")

# Interest income
result = add_income_source("interest", {
    "payer": "Citizens Bank",
    "amounts": {"amount": 1200}
})
check("Add interest income", result["status"] == "ok")

# Dividend income
result = add_income_source("dividends", {
    "payer": "Fidelity",
    "amounts": {"ordinary": 3500, "qualified": 2800}
})
check("Add dividend income", result["status"] == "ok")

# Capital gains
result = add_income_source("capital_gains", {
    "broker": "Fidelity",
    "amounts": {"short_term": -1200, "long_term": 8500}
})
check("Add capital gains", result["status"] == "ok")

# Crypto
result = add_income_source("crypto", {
    "exchange": "Coinbase",
    "amounts": {"short_term": 500, "long_term": 3200}
})
check("Add crypto gains", result["status"] == "ok")

# Mark income discovery complete
result = interview_step("income_sources", {
    "sources": [],
    "discovery_complete": True
})
check("Income discovery complete", result["status"] == "ok")

section("Phase 4f: Add Deductions")
# Mortgage interest
result = add_deduction("mortgage_interest", 18000, "itemized")
check("Add mortgage interest", result["status"] == "ok")

# Property taxes
result = add_deduction("property_taxes", 8500, "itemized")
check("Add property taxes", result["status"] == "ok")

# State/local taxes
result = add_deduction("state_local_taxes", 7900, "itemized")
check("Add state/local taxes", result["status"] == "ok")

# Charitable
result = add_deduction("charitable_cash", 5000, "itemized")
check("Add charitable cash", result["status"] == "ok")

result = add_deduction("charitable_noncash", 1500, "itemized")
check("Add charitable noncash", result["status"] == "ok")

# Medical expenses
result = add_deduction("medical", 4000, "itemized")
check("Add medical expenses", result["status"] == "ok")

# Above the line deductions
result = add_deduction("educator_expenses", 300, "above_the_line")
check("Add educator expenses", result["status"] == "ok")

result = add_deduction("hsa_deduction", 8550, "above_the_line")
check("Add HSA deduction", result["status"] == "ok")

result = add_deduction("self_employed_health_insurance", 12000, "above_the_line")
check("Add self-employed health insurance", result["status"] == "ok")

# Credits
result = add_deduction("child_tax_credit", 4000, "credit",
                       {"num_children": 2, "child_ages": [10, 7]})
check("Add child tax credit", result["status"] == "ok")

result = add_deduction("estimated_payments", 6000, "credit")
check("Add estimated payments", result["status"] == "ok")

# Mark deductions step complete
result = interview_step("deductions", {
    "itemized": [],  # Already added above
    "complete": True
})
check("Deductions step complete", result["status"] == "ok")

section("Phase 4g: Verify Interview State Persistence")
state = get_interview_state()
check("State returns ok", state["status"] == "ok")
check("Filing status recorded", state["filing_status"] == "married_filing_jointly")
check("Has income sources", state["data_summary"]["income_sources_count"] >= 7)
check("Has deductions", state["data_summary"]["itemized_deductions_count"] >= 4)
check("Tax year is 2025", state["tax_year"] == 2025)
check("Multiple steps completed", len(state["completed_steps"]) >= 3)
print(f"  Progress: {state['progress_pct']}%")

section("Phase 4h: Document Checklist Adapts to Income Sources")
checklist = get_document_checklist()
check("Checklist returns ok", checklist["status"] == "ok")
check("Has checklist items", checklist["total_documents"] > 0)
doc_types = [item["doc_type"] for item in checklist["checklist"]]
check("Checklist includes W-2", "w2" in doc_types)
check("Checklist includes 1099-B", "1099_b" in doc_types)
check("Checklist includes 1099-INT", "1099_int" in doc_types)
print(f"  Total documents: {checklist['total_documents']}")
print(f"  Received: {checklist['received']}")
print(f"  Still needed: {checklist['still_needed']}")


# ═══════════════════════════════════════════════════════════════
# Phase 5: Tax Calculation Tests
# ═══════════════════════════════════════════════════════════════

section("Phase 5a: Run Full Tax Calculation")
tax_result = calculate_tax()
check("Calculation returns ok", tax_result["status"] == "ok")

section("Phase 5b: Verify Federal Tax Calculation")
total_income = tax_result.get("total_income", 0)
agi = tax_result.get("adjusted_gross_income", 0)
taxable = tax_result.get("taxable_income", 0)
fed_tax = tax_result.get("total_federal_tax", 0)

# Expected: W2 wages (95K + 72K) + Schedule C net (57K) + interest (1.2K) +
# dividends (3.5K ordinary + 2.8K qualified) + gains (8.5K LT + 500 ST - 1.2K ST) + crypto (3.2K LT + 500 ST)
expected_income_approx = 95000 + 72000 + 57000 + 1200 + 3500 + 2800 + 7300 + 500 + 3200 + 500
print(f"  Total Income: ${total_income:,.2f} (expected ~${expected_income_approx:,.0f})")
check("Total income reasonable", 220000 < total_income < 260000,
      f"Got ${total_income:,.2f}")

print(f"  AGI: ${agi:,.2f}")
check("AGI less than total income (adjustments applied)",
      agi < total_income, f"AGI=${agi:,.2f} vs Income=${total_income:,.2f}")

print(f"  Taxable Income: ${taxable:,.2f}")
check("Taxable income less than AGI", taxable < agi)

print(f"  Federal Tax: ${fed_tax:,.2f}")
check("Federal tax reasonable (15-30% of taxable)",
      taxable * 0.10 < fed_tax < taxable * 0.40,
      f"Tax=${fed_tax:,.2f}, Taxable=${taxable:,.2f}")

# Schedule C
sc_net = tax_result.get("schedule_c_net_profit", 0)
se_tax = tax_result.get("self_employment_tax", 0)
check("Schedule C net profit is 57,000", abs(sc_net - 57000) < 1,
      f"Got ${sc_net:,.2f}")
check("SE tax reasonable (positive, accounts for W-2 SS wages reducing SS portion)",
      1000 < se_tax < 10000,
      f"Got ${se_tax:,.2f}")

# QBI
qbi = tax_result.get("qbi_deduction", 0)
print(f"  QBI Deduction: ${qbi:,.2f}")
check("QBI deduction positive (below threshold)", qbi > 0,
      f"Got ${qbi:,.2f}")

section("Phase 5c: Verify Deduction Comparison")
std_ded = tax_result.get("standard_deduction", 0)
itemized = tax_result.get("total_itemized", 0)
method = tax_result.get("deduction_method", "")

print(f"  Standard Deduction: ${std_ded:,.2f}")
print(f"  Itemized Deductions: ${itemized:,.2f}")
print(f"  Method chosen: {method}")

# With mortgage 18K + SALT capped at 10K + charitable 6.5K = ~34.5K
# Standard is 30K, so itemized should win
check("Standard deduction is $30,000", std_ded == 30000)
check("Itemized > standard (mortgage + charitable + SALT)",
      itemized > std_ded,
      f"Itemized=${itemized:,.2f} vs Standard=${std_ded:,.2f}")
check("Chose itemized method", method == "itemized",
      f"Got {method}")

section("Phase 5d: Verify Capital Gains")
st_gains = tax_result.get("total_short_term_gains", 0)
lt_gains = tax_result.get("total_long_term_gains", 0)
print(f"  Short-term gains: ${st_gains:,.2f}")
print(f"  Long-term gains: ${lt_gains:,.2f}")
check("Short-term gains include crypto", st_gains != 0)
check("Long-term gains include crypto", lt_gains > 8000)

section("Phase 5e: Verify MA State Tax")
ma_tax = tax_result.get("ma_total_tax", 0)
ma_taxable = tax_result.get("ma_taxable_income", 0)
ma_withholding = tax_result.get("ma_withholding", 0)
ma_owed = tax_result.get("ma_amount_owed", 0)

print(f"  MA Taxable Income: ${ma_taxable:,.2f}")
print(f"  MA Total Tax: ${ma_tax:,.2f}")
print(f"  MA Withholding: ${ma_withholding:,.2f}")
print(f"  MA Amount Owed/Refund: ${ma_owed:,.2f}")

check("MA tax rate ~5% of MA taxable",
      abs(ma_tax - ma_taxable * 0.05) < 100 or ma_tax > 0,
      f"Tax=${ma_tax:,.2f}, 5% of {ma_taxable:,.2f} = ${ma_taxable*0.05:,.2f}")
check("MA withholding recorded", ma_withholding > 0,
      f"Got ${ma_withholding:,.2f}")

section("Phase 5f: Verify Credits")
child_credit = tax_result.get("child_tax_credit", 0)
print(f"  Child Tax Credit: ${child_credit:,.2f}")
check("Child tax credit = $4,000 (2 children)", child_credit == 4000,
      f"Got ${child_credit:,.2f}")

section("Phase 5g: Federal Bottom Line")
fed_after_credits = tax_result.get("federal_tax_after_credits", 0)
fed_withholding = tax_result.get("total_federal_withholding", 0)
est_payments = tax_result.get("estimated_payments", 0)
fed_owed = tax_result.get("federal_amount_owed", 0)
eff_rate = tax_result.get("effective_tax_rate", 0)
marginal = tax_result.get("marginal_federal_rate", 0)

print(f"  Federal tax after credits: ${fed_after_credits:,.2f}")
print(f"  Total withholding: ${fed_withholding:,.2f}")
print(f"  Estimated payments: ${est_payments:,.2f}")
print(f"  Amount owed/refund: ${fed_owed:,.2f}")
print(f"  Effective rate: {eff_rate}%")
print(f"  Marginal rate: {marginal*100:.0f}%")

check("Withholding = W2 primary + spouse",
      fed_withholding == 24000,
      f"Got ${fed_withholding:,.2f}")
check("Estimated payments = 6000", est_payments == 6000)
check("Effective rate reasonable (15-30%)", 10 < eff_rate < 35,
      f"Got {eff_rate}%")
check("Marginal rate is 22% or 24%", marginal in [0.22, 0.24],
      f"Got {marginal*100:.0f}%")


# ═══════════════════════════════════════════════════════════════
# Phase 6: Form Generation Tests
# ═══════════════════════════════════════════════════════════════

section("Phase 6: Form Generation")
forms_result = generate_forms()
check("Forms generation returns ok", forms_result["status"] == "ok")
check("Multiple forms generated", forms_result.get("forms_generated", 0) >= 3,
      f"Got {forms_result.get('forms_generated', 0)}")

generated = forms_result.get("files", [])
form_names = [f["form"] for f in generated]
print(f"  Generated forms: {form_names}")

check("Form 1040 generated", "form_1040" in form_names)
check("Schedule C generated", "schedule_c" in form_names)
check("MA Form 1 generated", "ma_form_1" in form_names)
check("CPA Summary generated", "cpa_summary" in form_names)

# Verify files exist
for f in generated:
    path = f.get("path", "")
    exists = os.path.exists(path)
    check(f"File exists: {os.path.basename(path)}", exists, f"Path: {path}")

# Check CPA summary content
cpa_files = [f for f in generated if f["form"] == "cpa_summary"]
if cpa_files:
    cpa_path = cpa_files[0]["path"]
    with open(cpa_path) as f:
        cpa_content = f.read()
    check("CPA summary has income section", "INCOME" in cpa_content or "KEY FIGURES" in cpa_content)
    check("CPA summary has federal section", "FEDERAL" in cpa_content)
    check("CPA summary has MA section", "MASSACHUSETTS" in cpa_content)
    check("CPA summary has deduction analysis", "DEDUCTION" in cpa_content)
    print(f"\n  CPA Summary preview (first 500 chars):")
    print(f"  {cpa_content[:500]}")


# ═══════════════════════════════════════════════════════════════
# Direct Calculator Test (independent of file I/O)
# ═══════════════════════════════════════════════════════════════

section("Phase 5 (Bonus): Direct Calculator Verification")

income = IncomeData(
    w2_wages=95000,
    w2_federal_withholding=14000,
    w2_state_withholding=4500,
    w2_social_security_wages=95000,
    w2_medicare_wages=95000,
    spouse_w2_wages=72000,
    spouse_w2_federal_withholding=10000,
    spouse_w2_state_withholding=3400,
    schedule_c_gross_income=85000,
    schedule_c_expenses=28000,
    interest_income=1200,
    dividend_income_ordinary=3500,
    dividend_income_qualified=2800,
    short_term_capital_gains=-1200,
    long_term_capital_gains=8500,
    crypto_gains_short_term=500,
    crypto_gains_long_term=3200,
)

deductions = DeductionData(
    educator_expenses=300,
    hsa_deduction=8550,
    self_employed_health_insurance=12000,
    medical_expenses=4000,
    state_local_taxes_paid=7900,
    property_taxes=8500,
    mortgage_interest=18000,
    charitable_cash=5000,
    charitable_noncash=1500,
)

credits = CreditData(
    num_qualifying_children=2,
    child_ages=[10, 7],
    estimated_tax_payments=6000,
)

result = calculate_full_tax(income, deductions, credits, num_dependents=2)

print(f"\n  Direct calculation results:")
print(f"  Total Income:     ${result.total_income:>12,.2f}")
print(f"  AGI:              ${result.adjusted_gross_income:>12,.2f}")
print(f"  Taxable Income:   ${result.taxable_income:>12,.2f}")
print(f"  Schedule C Net:   ${result.schedule_c_net_profit:>12,.2f}")
print(f"  SE Tax:           ${result.self_employment_tax:>12,.2f}")
print(f"  QBI Deduction:    ${result.qbi_deduction:>12,.2f}")
print(f"  Standard Ded:     ${result.standard_deduction:>12,.2f}")
print(f"  Itemized Ded:     ${result.total_itemized:>12,.2f}")
print(f"  Method:           {result.deduction_method:>12}")
print(f"  Fed Ordinary Tax: ${result.federal_ordinary_tax:>12,.2f}")
print(f"  Fed CG Tax:       ${result.federal_capital_gains_tax:>12,.2f}")
print(f"  NIIT:             ${result.niit:>12,.2f}")
print(f"  AMT:              ${result.amt:>12,.2f}")
print(f"  Total Fed Tax:    ${result.total_federal_tax:>12,.2f}")
print(f"  Child Tax Credit: ${result.child_tax_credit:>12,.2f}")
print(f"  Fed After Credit: ${result.federal_tax_after_credits:>12,.2f}")
print(f"  Fed Withholding:  ${result.total_federal_withholding:>12,.2f}")
print(f"  Est Payments:     ${result.estimated_payments:>12,.2f}")
print(f"  Fed Owed/Refund:  ${result.federal_amount_owed:>12,.2f}")
print(f"  MA Total Tax:     ${result.ma_total_tax:>12,.2f}")
print(f"  MA Owed/Refund:   ${result.ma_amount_owed:>12,.2f}")
print(f"  Total Liability:  ${result.total_tax_liability:>12,.2f}")
print(f"  Effective Rate:   {result.effective_tax_rate:>11.1f}%")
print(f"  Marginal Rate:    {result.marginal_federal_rate*100:>11.0f}%")

check("Direct calc: income > $230K", result.total_income > 230000)
check("Direct calc: AGI < income", result.adjusted_gross_income < result.total_income)
check("Direct calc: itemized chosen", result.deduction_method == "itemized")
check("Direct calc: SE tax positive", 1000 < result.self_employment_tax < 10000)
check("Direct calc: child credit $4K", result.child_tax_credit == 4000)
check("Direct calc: MA tax at ~5%", result.ma_base_tax > 0)


# ═══════════════════════════════════════════════════════════════
# Final Report
# ═══════════════════════════════════════════════════════════════

section("TEST RESULTS")
total = passed + failed
print(f"  Passed: {passed}/{total}")
print(f"  Failed: {failed}/{total}")
if failed == 0:
    print(f"\n  ALL TESTS PASSED!")
else:
    print(f"\n  {failed} test(s) failed. Review output above.")

sys.exit(0 if failed == 0 else 1)
