# Triage Copilot — generative AI triage for ServiceNow

Hackathon demo for the **Generative AI SNOW Initiative**: Claude reads the Data Engineering team's ServiceNow queue and summarizes, groups duplicates, prioritizes, and routes every ticket — so on-call reads 22 clear issues instead of 38 raw tickets.

All tickets, people and ticket numbers are **fictional**.

## Quick start

```bash
pip install -r requirements.txt
streamlit run app.py              # works with no key: shows the hand-written sample + offline rules
```

### Turn on the AI

1. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and add a Claude API key (or Bedrock settings). The file is git-ignored.
2. Have Claude triage the 38 dummy tickets once:
   ```bash
   python scripts/precompute.py --limit 5   # smoke test first
   python scripts/precompute.py             # full run → data/tickets_llm.json
   ```
3. `streamlit run app.py` — the sidebar now shows **✨ Claude-generated** results and **Live AI on**.
4. Commit `data/tickets_llm.json` so teammates see the same results without a key.

## Where the generative AI is

| What Claude does | Where you see it |
|---|---|
| Rewrites messy email/portal text into a one-line summary | Every card in tab ② |
| Scores impact 0–100 against a rubric and explains why ("filed as Low but affects the bed huddle") | Score box + "Why this score & route" |
| Picks the queue and owner, with a confidence level | Right side of each card, tab ④ |
| Spots incidents that are really requests, and tickets that aren't Data Engineering work | ↻ / ✕ badges, KPI strip |
| Cites who fixed something similar before, from `data/history.json` | "Who's handled this before" |
| Reads the whole queue at once to find tickets with the same root cause, explains the cause, recommends one fix | Tab ③ |
| Drafts the status update for every affected team | Tab ③ draft box |
| Does all of the above live for a brand-new ticket, including spotting that it duplicates an open issue | Tab ⑤ |

Tab ⑤ has a **"See exactly what the model is told"** expander showing the full prompt and output schema.

### How it's built

- `triage/llm.py` — prompts, tool schemas, model calls and validation. Claude answers by calling a tool whose schema lists the only valid queues, categories and owners; the app re-checks every field (clamps scores, rejects unknown queues) before anything reaches the screen.
- `scripts/precompute.py` — one grouping call over the whole queue, then one triage call per ticket (6 in parallel). A ticket whose call fails falls back to offline rules and is labeled as such.
- Live mode (tab ⑤) uses the fastest model and falls back to offline rules within a couple of seconds if the API is unreachable — the demo can't break on stage.

### Models and providers

| Setting | Claude API (default) | Amazon Bedrock |
|---|---|---|
| Enable | `ANTHROPIC_API_KEY` | `LLM_PROVIDER=bedrock`, `AWS_REGION`, AWS credentials |
| Precompute model (`TRIAGE_MODEL`) | `claude-sonnet-5-5` | `anthropic.claude-sonnet-5-5` |
| Live model (`LIVE_MODEL`) | `claude-haiku-5-5` | `anthropic.claude-haiku-5-5` |

On Bedrock, check model access for your account in the AWS console first.

**Real ticket data contains PHI.** This demo uses only dummy tickets. Before pointing it at real ServiceNow data, confirm with your security/compliance team which provider and account are approved (e.g. Bedrock inside your organization's AWS account).

## Tabs

| Tab | Shows |
|---|---|
| ① Before: raw queue | Today's firehose — 38 unassigned tickets; the most urgent one is buried and filed as Low |
| ② Triage queue | One card per issue: summary, score, P1–P4 color, route, owner, confidence, rationale, history; accept or reroute |
| ③ Duplicate groups | 38 tickets → 22 issues; root cause, fix, linked tickets, drafted team update |
| ④ Routing | Tickets per team before/after, routing decisions, AI-route acceptance rate |
| ⑤ Triage a new ticket | Live Claude triage + duplicate check against the open queue |
| ⑥ Data table | The single queryable table the BI team asked for, CSV download, proposed Redshift DDL |

## Project layout

```
app.py                       Streamlit dashboard
triage/llm.py                Claude prompts, schemas, calls, validation
triage/offline_engine.py     Keyword + TF-IDF fallback (no key / API down)
scripts/precompute.py        Runs all tickets through Claude → data/tickets_llm.json
data/generate_tickets.py     Builds the dummy tickets (+ hand-written sample answers)
data/history.json            Fictional resolved tickets for "who handled this before"
tests/test_llm.py            Tests with a fake client — no key needed (pytest -q)
docs/DEMO_SCRIPT.md          5-minute walkthrough
```

## Going to production

Pull tickets from the ServiceNow Table API instead of `tickets.json`, run `triage_ticket` on each new ticket as it arrives, re-run grouping on a schedule, and write results to `de_triage.ticket_scores` in Redshift (DDL in tab ⑥).
