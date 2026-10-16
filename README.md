# Triage Copilot — ServiceNow triage demo

Hackathon demo for the **Generative AI SNOW Initiative**: automate ServiceNow ticket triage for the Data Engineering team by summarizing, grouping duplicates, prioritizing, and routing tickets to the right queue and owner.

Runs fully offline on **38 dummy tickets** (all people and ticket numbers are fictional). The AI triage output is precomputed, so no API key or network is needed on demo day.

## Run it

```bash
pip install -r requirements.txt
streamlit run app.py
```

Opens at http://localhost:8501.

## What's in the demo

| Tab | Shows | Pain point it answers |
|---|---|---|
| ① Before: raw queue | The firehose on-call sees today — 38 unassigned tickets, no summaries. The PHI exposure is buried and filed as Low. | Missed high-priority items |
| ② Triage queue | One row per issue: AI summary, 0–100 priority score, color-coded P1–P4, suggested queue + owner, confidence, rationale, "who handled this before". Accept or reroute. | On-call can't tell what's scored / by whom / whether it's theirs |
| ③ Duplicate groups | 38 tickets → 22 issues. Each group: root cause, recommended action, linked tickets, and a drafted update for every affected team. | Duplicate volume, cross-team communication |
| ④ Routing | Before (one shared queue) vs after (per-team queues), routing decisions and acceptance rate. | Routing accuracy |
| ⑤ Triage a new ticket | Paste any ticket text; it is summarized, scored, routed, and matched against the open queue for duplicates. | Shows it works on new input |
| ⑥ Data table | The single queryable table the BI team asked for, CSV download, proposed Redshift DDL. | Poor visibility into ticket data |

## Project layout

```
app.py                     Streamlit dashboard
data/generate_tickets.py   Builds the dummy tickets + precomputed AI fields (edit here)
data/tickets.json / .csv   Generated data the app reads
triage/offline_engine.py   Keyword routing + TF-IDF duplicate matching for tab ⑤
                           (the drop-in point for a real LLM call later)
docs/DEMO_SCRIPT.md        5-minute walkthrough
```

## Changing the data

Edit `data/generate_tickets.py`, then re-run `python data/generate_tickets.py`. Each ticket carries the raw ServiceNow fields plus `ai_*` fields (summary, score, queue, owner, confidence, rationale, should-be-request flag) and an optional `group_id`.

## Going live later

Swap the precomputed `ai_*` fields for a model call that returns the same JSON shape per ticket, pull tickets from the ServiceNow Table API instead of `tickets.json`, and write results to `de_triage.ticket_scores` in Redshift (DDL is in tab ⑥).
