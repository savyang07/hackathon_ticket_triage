# Triage Copilot

Agentic AI demo for ServiceNow ticket triage — built for the **Keck Medicine of USC Agentic AI in Healthcare Hackathon**.

Runs entirely offline on synthetic data. No API key or ServiceNow instance needed.

---

## What it does

The demo shows a Data Engineering on-call queue before and after an AI triage agent:

| Before | After |
|---|---|
| 38 raw, unsorted tickets | 22 unique issues (16 duplicates collapsed) |
| No priority scores | AI priority score 0–100 with per-factor breakdown |
| PHI-exposure ticket buried at row 19 | Critical ticket surfaced to top automatically |
| 8 mistyped incidents (wrong SLA clock) | Type/team flagged for review |
| ~3.8 hrs estimated manual triage | ~33 min estimated AI-assisted review |

Five agent modules make the story visible as real code:

```
Minimizer → Summarizer → Priority Scorer → Router → Grouper
```

Two tabs show how it stays accountable and useful beyond triage:

| Tab | What it shows |
|---|---|
| 🧾 Audit Trail | Every AI suggestion and every human approval, override (reason required), reroute and info request, with who, when and why. Agreement rate between AI and reviewers; CSV export. |
| 📈 Weekly Digest | Leadership summary: headline numbers, what needs attention, patient-care issues, recurring problems, 8-week trends (synthetic history), Markdown download. |

---

## Quick start

```bash
cd hackathon_ticket_triage
pip install -r requirements.txt
streamlit run app.py
```

Opens at `http://localhost:8501`.

---

## Folder map

```
hackathon_ticket_triage/
├── app.py                  # Thin router: page config, load data, two tabs
├── config/
│   └── scoring.json        # Priority weights, thresholds, colors — edit here
├── agents/
│   ├── pipeline.py         # Runs every agent in order; the app's only entry point to them
│   ├── minimizer.py        # Ticket → only the fields triage needs (text unchanged)
│   ├── audit.py            # Audit entries + AI/reviewer agreement stats
│   ├── digest.py           # Queue + history → weekly leadership digest
│   ├── summarizer.py       # Ticket → plain-English summary
│   ├── grouper.py          # Tickets → duplicate groups
│   ├── scorer.py           # Ticket + config → 0-100 score with breakdown
│   └── router.py           # Ticket → queue + owner + confidence
├── tools/
│   └── servicenow_mock.py  # Mock MCP layer (mirrors real ServiceNow Table API)
├── ui/
│   ├── components.py       # Shared CSS, helpers, color constants
│   ├── state.py            # Shared session state, reviewer, audit logging
│   ├── before_tab.py       # "Before" tab: raw inbox, pain-point callouts
│   ├── after_tab.py        # "After" tab: Run Triage animation, results, human review
│   ├── audit_tab.py        # "Audit Trail" tab
│   └── digest_tab.py       # "Weekly Digest" tab
├── triage/
│   └── offline_engine.py   # Keyword rules + TF-IDF for live new-ticket input
├── data/
│   ├── tickets.json        # 38 precomputed synthetic tickets
│   ├── weekly_history.json # 8 weeks of SYNTHETIC history for the digest
│   └── generate_history.py # Rebuilds weekly_history.json
├── tests/
│   ├── test_scorer.py      # Unit tests for priority scorer
│   ├── test_grouper.py     # Unit tests for duplicate grouper
│   ├── test_pipeline.py    # Agents called in order; app shows what they return
│   └── test_audit_digest.py# Unit tests for audit stats and the digest
└── docs/
    └── DEMO_GUIDE.md       # Full demo script, Q&A, Mermaid diagram
```

---

## What's mocked vs real

| Component | Demo | Production path |
|---|---|---|
| Ticket data | 38 synthetic tickets in `data/tickets.json` | ServiceNow Table API via MCP (scoped, read-only account) |
| Patient data | Synthetic tickets, no PHI. The model gets the full text of the triage fields only (`agents/minimizer.py`) | Azure OpenAI in Keck's Microsoft tenant under Keck's HIPAA BAA; full ticket text, minimum-necessary fields; reviewers see everything in ServiceNow |
| Human review | Approve / override / reroute in the session, logged to the Audit Trail tab | Reviewer from single sign-on; append-only audit table + ServiceNow work notes |
| Weekly digest | Assembled offline from the numbers; 8 weeks of synthetic history | LLM writes the narrative from the same numbers; manager reviews before sending |
| Summaries | Precomputed `ai_summary` field | Azure OpenAI call |
| Duplicate grouping | Precomputed `group_id` field | Embedding similarity + LLM cluster labels |
| Priority scores | Precomputed `ai_priority_score` | Weighted rule engine or fine-tuned model |
| Routing | Precomputed `ai_queue` / `ai_owner` | Team load + calendar lookup + LLM |
| ServiceNow writes | No-op (logs `[MOCK MCP]` to console) | PATCH `/api/now/table/incident/<sys_id>` |

See `tools/servicenow_mock.py` for the exact endpoint each mock function would call.

---

## Scoring config

Edit `config/scoring.json` to tune the priority model:

```json
{
  "factors": [
    {"name": "patient_care_criticality", "weight": 30},
    {"name": "users_affected",           "weight": 25},
    ...
  ],
  "thresholds": {"p1_min": 85, "p2_min": 65, "p3_min": 40}
}
```

All weights are **placeholders** — replace with values validated against your historical ticket data before going live.

---

## Running tests

```bash
pytest tests/ -v
```

41 tests: agent pipeline (including a headless run of the app), scorer, grouper,
data integrity, audit and digest.

---

## Swapping in a real model

To replace precomputed outputs with live LLM calls:

The app already gets every AI column from the agents through `agents/pipeline.py`, so no UI
changes are needed:

1. Set `DEMO_MODE = False` in `agents/summarizer.py` and `agents/router.py`.
2. Fill in `_call_llm(payload)` in each with a call to Azure OpenAI in Keck's Microsoft tenant
   (covered by Keck's HIPAA BAA). It receives the minimized payload from `minimize_ticket()`:
   the triage fields with their full text; the agents refuse to run live without it.
3. Point `tools/servicenow_mock.py` functions at your live ServiceNow MCP server.
4. Replace `ai_*` fields in `tickets.json` with live reads from ServiceNow.

---

## Data sources

All ticket data is **100% synthetic** — generated for this demo. No real patient, employee, or Keck Medicine data is used anywhere. No PHI. The scoring weights are placeholder values and have not been validated against production data.

See `docs/DEMO_GUIDE.md` for the full responsible-AI disclosure and next-steps roadmap.
