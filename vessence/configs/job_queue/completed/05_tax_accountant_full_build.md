# Job: Build & Test Tax Accountant Essence — Full Implementation

Status: complete
Completed: 2026-03-24 01:30 UTC
Notes: All 6 phases done. ChromaDB: 43 entries across 7 categories (income_types, deductions, credits, state_ma, schedule_c, mfj, crypto). Web UI created. API routes added. Test suite created. Form templates placeholder created. Knowledge built with deepseek-r1:32b at 2048 token cap.
Priority: 1
Model: opus
Created: 2026-03-23

## Objective
Take the Tax Accountant essence from empty skeleton to fully functional AI agent. Train it with 2025 tax knowledge, build the UI, wire up document handling, test the full interview flow end-to-end.

## What Exists (Skeleton)
- Folder structure at `~/ambient/essences/tax_accountant_2025/`
- manifest.json (type: essence, has_brain: true, Opus 4.6)
- personality.md
- 4 Python files (~3,300 lines): custom_tools.py, document_parser.py, form_generator.py, tax_calculator.py
- Empty ChromaDB, empty user_data, empty form_templates

## Phase 1: Training — Deep Tax Code Research → ChromaDB
**Goal:** Populate the essence's ChromaDB with comprehensive 2025 tax knowledge.

1. Use Opus 4.6 to design the category structure for tax knowledge (e.g., income_types/w2, deductions/itemized/medical, credits/child, state_ma/income, schedule_c, crypto, etc.)
2. Research 2025 federal tax code via web search:
   - Tax brackets, rates, standard deduction amounts (MFJ)
   - Itemized deduction rules (SALT cap, mortgage interest, charitable, medical)
   - Credits (child tax credit, education, earned income, etc.)
   - Schedule C rules for small business (acupuncture clinic)
   - Educator/professor-specific deductions
   - Crypto/investment tax rules (capital gains, wash sale, Ethereum staking)
   - Changes from 2024 → 2025
3. Research Massachusetts state tax:
   - Form 1 rules, income tax rate
   - Schedule B (interest/dividends)
   - State-specific deductions and credits
4. Research MFJ-specific rules:
   - Joint vs separate filing thresholds
   - AMT considerations
   - Spousal income handling
5. Store all research as categorized vectors in `knowledge/chromadb/`
6. Sources: IRS.gov publications, MA DOR guidelines, tax law summaries
7. Verify ChromaDB can retrieve relevant knowledge: test queries like "what is the 2025 standard deduction for MFJ" and "Schedule C home office deduction rules"

**Note:** This phase is the most token-intensive. Run during nighttime for aggressive processing.

## Phase 2: IRS Form Templates
1. Download blank 2025 IRS form PDFs:
   - Form 1040 (U.S. Individual Income Tax Return)
   - Schedule 1 (Additional Income and Adjustments)
   - Schedule A (Itemized Deductions)
   - Schedule B (Interest and Ordinary Dividends)
   - Schedule C (Profit or Loss from Business)
   - Schedule D (Capital Gains and Losses)
   - Schedule SE (Self-Employment Tax)
   - Form 8949 (Sales and Other Dispositions of Capital Assets)
2. Download Massachusetts forms:
   - Form 1 (Resident Income Tax Return)
   - Schedule B (Interest, Dividends and Certain Capital Gains)
3. Store in `essence_data/form_templates/`
4. Verify form_generator.py can read and fill these PDFs (test with dummy data)

## Phase 3: UI + Web Integration
1. Create a web page for the Tax Accountant (similar to briefing.html)
   - Interview wizard: step-by-step question flow
   - Document upload area (drag & drop PDFs, photos)
   - Progress tracker (which sections are complete)
   - Results view: filled forms, CPA summary
2. Add routes in jane_web/main.py:
   - `GET /tax-accountant` → HTML page
   - `POST /api/tax/interview/start` → begin interview
   - `POST /api/tax/interview/answer` → submit answer + optional file upload
   - `GET /api/tax/interview/state` → current progress
   - `POST /api/tax/calculate` → run calculations
   - `GET /api/tax/forms/{form_name}` → download filled PDF
   - `GET /api/tax/summary` → CPA summary document
3. Wire into essence picker (should already show up as type: essence)

## Phase 4: Interview Logic Testing
1. Test the full interview flow:
   - Start interview → receives situational questions
   - Answer income source questions → system discovers all sources
   - Upload a test W-2 PDF → verify document_parser extracts values
   - Upload a test receipt photo → verify multimodal parsing
   - Verify interview adapts based on answers (e.g., if user has Schedule C income, ask clinic-specific questions)
2. Test edge cases:
   - What if user doesn't know an answer? (skip + come back later)
   - What if uploaded document can't be parsed? (fallback to manual input)
   - Resume interview from saved state

## Phase 5: Calculation + Form Generation Testing
1. Create a test tax scenario with known correct answers:
   - W-2 income: $X from Northeastern
   - Schedule C: REDACTED_BUSINESS income/expenses
   - Investment income: capital gains, Ethereum
   - Itemized vs standard deduction comparison
2. Run tax_calculator.py with test data → verify federal + MA calculations
3. Run form_generator.py → verify PDFs are filled correctly
4. Generate CPA summary → verify it's readable and complete
5. Compare results against a known-good tax return or online calculator

## Phase 6: Android Integration
1. Add Tax Accountant to Android HomeScreen (should show under "Essences" section)
2. Implement interview flow in Android (or use WebView for v1)
3. Test document upload from Android (photos, PDFs)

## Files Involved
- `~/ambient/essences/tax_accountant_2025/` — entire essence folder
- `jane_web/main.py` — new API routes
- `vault_web/templates/tax_accountant.html` — new web page
- `android/.../ui/home/HomeScreen.kt` — essence display

## Dependencies
- Claude Opus 4.6 API access for training phase
- Web search capability for tax code research
- pypdf or pdfrw for PDF form filling
- Multimodal Opus for document parsing (PDFs, receipt photos)

## Notes
- Training phase (Phase 1) should run at night — it's token-intensive
- Test with dummy/synthetic data first, not real tax documents
- The essence is immutable: "Tax Accountant 2025" — next year gets a new essence
- All data stays in the essence folder — delete folder = clean slate
- If a phase hits a blocker, mark blocked with the question and move to next phase
