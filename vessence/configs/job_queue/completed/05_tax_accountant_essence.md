# Job: Build Tax Accountant Essence — First True AI Essence

Status: completed
Priority: 1
Created: 2026-03-23

## Objective
Build the first true Vessence essence: a Tax Accountant AI agent that deeply understands US tax code, conducts guided interviews, processes uploaded documents, and produces filled tax forms.

## Spec Summary

- **Type:** essence (has_brain: true)
- **LLM:** Claude Opus 4.6
- **Tax Year:** 2025 (filing due April 2026)
- **Filing Status:** Married Filing Jointly
- **Jurisdiction:** Federal + Massachusetts state
- **Output:** Filled PDF forms (1040, Schedule C, MA Form 1, etc.) + CPA summary

## Phases

### Training Phase: Deep Tax Code Research (Build-Time, runs once)
Train the accountant with the most up-to-date tax information before it ever talks to a user.
1. Research 2025 federal tax code: brackets, rates, deductions, credits, changes from 2024
2. Research Massachusetts state tax rules (Form 1, Schedule B, etc.)
3. Research MFJ-specific rules: joint vs separate thresholds, SALT cap, AMT, phaseouts
4. Research Schedule C rules (small business — acupuncture clinic)
5. Research educator/professor-specific deductions and exclusions
6. Research crypto/investment tax rules (Ethereum, capital gains, wash sale)
7. LLM designs a category structure for the knowledge base (e.g., "income_types/w2", "income_types/schedule_c", "deductions/itemized/medical", "credits/child", "state_ma/income", etc.)
8. All research stored as categorized vectors in the essence's own ChromaDB
9. Sources: IRS.gov publications, MA DOR guidelines, tax law summaries, web research
10. This phase is token-intensive — runs once at essence build time, not at runtime

### Operation Part 1: Income Source Discovery (Iterative)
The accountant keeps asking until it fully understands ALL sources of income.
1. Accept upload of prior year returns (2024, 2023 PDFs) — extract known income sources as baseline
2. Ask probing questions to discover additional income sources the user may not think to mention
3. Categories to probe: employment (W-2), self-employment (Schedule C), investments, crypto, rental, consulting, freelance, grants, fellowships, interest, dividends, side income, spousal income
4. For each discovered source, record: type, estimated amount, frequency, documentation available
5. **Loop condition:** Accountant keeps iterating until it is confident no income sources remain undiscovered
6. Output: complete income source inventory stored in `user_data/income_sources.json`

### Operation Part 2: Document Collection (Iterative)
The accountant guides the user through uploading all necessary documents.
1. Based on the income inventory from Part 1, generate a complete document checklist
2. For each required document:
   a. Tell the user exactly what's needed and why
   b. Accept upload (PDF, photo, QuickBooks export) — Opus reads and extracts values
   c. OR accept a URL/link — accountant fetches and reads the content
   d. OR if neither works — ask user to input values manually
3. Process each uploaded document: extract relevant figures, categorize, store in working files
4. Cross-reference extracted data against income sources — flag any mismatches or gaps
5. **Loop condition:** Iterate until all documents on the checklist are collected and validated
6. Output: all extracted data organized in `working_files/calculations/`

### Operation Part 3: Tax Form Generation
1. Calculate both itemized and standard deduction — recommend whichever saves more
2. Compute federal tax (1040 + all applicable schedules)
3. Compute Massachusetts state tax (Form 1 + schedules)
4. Generate filled PDF forms ready for CPA review or direct filing
5. Generate CPA summary document (narrative + key figures + recommendations)
6. Present results to user for review — allow corrections before final output
7. Store all working data in essence's own folder (self-contained, deletable)

## Essence Folder Structure
```
~/ambient/essences/tax_accountant_2025/
├── manifest.json                    # type: "essence", has_brain: true, preferred_model: claude-opus-4-6
├── personality.md                   # Tax professional persona, interview style
├── knowledge/
│   └── chromadb/                    # Pre-filled with tax code research (Phase 1)
├── functions/
│   ├── custom_tools.py              # interview_step(), upload_document(), calculate_tax(), generate_forms()
│   ├── document_parser.py           # PDF/image extraction using Opus multimodal
│   ├── tax_calculator.py            # Federal + MA tax computation engine
│   └── form_generator.py            # Fill PDF tax forms (pdfrw or reportlab)
├── ui/
│   └── layout.json                  # Interview flow UI (step-by-step wizard)
├── user_data/
│   ├── interview_state.json         # Current interview progress
│   ├── income_sources.json          # Discovered income sources
│   ├── deductions.json              # All deductions tracked
│   └── uploads/                     # User-uploaded documents
├── working_files/
│   ├── prior_returns/               # Parsed prior year data
│   ├── calculations/                # Intermediate computation results
│   └── output/                      # Generated forms + CPA summary
└── essence_data/
    └── form_templates/              # Blank IRS/MA form PDFs for filling
```

## Document Handling
- PDF bank statements → Opus reads, extracts transactions
- QuickBooks exports → parse CSV/QBX for income/expense categorization
- Receipt photos → Opus multimodal extracts vendor, amount, date, category
- Prior tax returns (PDF) → Opus extracts all line items as baseline
- If parsing fails → fallback to manual input prompt

## Key Design Decisions
- Essence is immutable: "Tax Accountant 2025". Next year = new essence.
- All data lives inside the essence folder. Delete folder = clean slate.
- Interview state is persistent — user can resume across sessions.
- Accountant never files directly — produces forms for user/CPA to review and file.
- Knowledge base is pre-built during essence construction (not at runtime).

## Dependencies
- Job #18 (Tools vs Essences Phase 2) should complete first — folder rename + architecture
- Claude Opus 4.6 API access (user's subscription)
- PDF form filling library (pdfrw, reportlab, or pypdf)
- IRS form templates (downloadable from IRS.gov)

## Files Involved
- New essence folder: `~/ambient/essences/tax_accountant_2025/`
- Essence loader: `agent_skills/essence_loader.py` (already type-aware)
- Web UI: `vault_web/templates/jane.html` (essence picker)
- API: `jane_web/main.py` (essence routes)

## Notes
- This is the proof-of-concept that validates the entire essence architecture
- The research phase (Phase 1) is the most token-intensive — runs once at build time
- Interview design is the critical path — quality of questions determines quality of output
- Opus 4.6 multimodal handles PDFs, images, and text natively
