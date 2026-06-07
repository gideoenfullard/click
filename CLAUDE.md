# ClickAI — Working Rules (Claude Code)


## Project

ClickAI is an AI-powered business management platform for South African SMEs.
Python/Flask, deployed on Fly.io, Supabase (PostgreSQL) as the database.
Modular: `clickai.py` (main) plus route modules (`clickai_payroll.py`,
`clickai_banking.py`, `clickai_pos.py`, etc.), each using a `register_*_routes` pattern.
The owner (Deon) does not edit code himself — deliver complete, ready-to-deploy files.

## 1. Think before coding
State assumptions explicitly before writing any code. If a request is ambiguous,
present the interpretations and ask — do not guess. Surface tradeoffs upfront.
Never hide confusion.

## 2. Always work from the live file
Never assume a previously opened file is current after a deployment.
Always confirm the latest live file before making any change.

## 3. Surgical changes only
Touch ONLY what was explicitly asked. Every changed line must trace directly
to the request. Do not touch adjacent code, comments, or formatting.
Do not add unrequested features, abstractions, or "improvements".
Match the existing code style.

## 4. Simplicity first
Write the minimum code that solves what was asked. No speculative features,
no extra error handling beyond what is needed.

## 5. Fix everything that was reported
If multiple problems are raised in one request, fix all of them — not just one.

## 6. Verify before delivering — RUN THE TESTS
Run `python3 test_clickai.py` after every change. It must print
"All good — safe to deploy" (exit 0) before anything is deployed.
If it says "DO NOT DEPLOY", fix the failures first.
Never deliver snippets, diffs, or patch instructions — always a complete,
deployable file. Show a diff of what changed so the change is visible.

## 7. Goal-driven execution
Turn a vague task into a verifiable success check before starting.
Example: "the PAYE is wrong" becomes "calculate PAYE for a known employee
and confirm it matches the Sage payslip to the cent."

## Project-specific rules
- Communication with the owner is in Afrikaans; all ClickAI user-facing UI
  must be English only (labels, alerts, activity feed, hardcoded strings).
- Balances are always calculated from source documents, never stored as a flat value.
- Every transaction must be allocated to a specific GL code — no "General Expenses"
  catch-all. Fallback is 7900 (Sundry Expenses), never 7999.
- Use the business's imported chart of accounts via `build_gl_map()`; fall back to
  BOOKING_CATEGORIES only for businesses without a COA.
- Sage-imported GL codes are preserved exactly.
- Duplicate detection must be airtight — bank, stock, and customer/supplier imports
  all require merge-by-code/fingerprint logic (signed amounts), not bare saves.
- Database changes (new columns) must be flagged with the exact ALTER TABLE SQL
  for the owner to run in Supabase. Use straight quotes in SQL, not curly quotes.
- Multi-tenant: every feature works via `business_id` for any tenant — never
  Fulltech-specific hardcoding in the general codebase.
- Work one module per session where possible.
- For accounting behaviour, Sage Pastel is the reference benchmark.
- No emoji or decorative icons in navigation — professional product positioning.

## Tradeoff note
These rules bias toward caution over speed. For trivial tasks, use judgment.
When in doubt: don't assume, don't hide confusion, ask.
