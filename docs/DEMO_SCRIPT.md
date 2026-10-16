# 5-minute demo script

**Setup (before you present)**
- `.streamlit/secrets.toml` has a working key, and `data/tickets_llm.json` exists (`python scripts/precompute.py`).
- `streamlit run app.py`, browser full screen. Sidebar should say **✨ Claude-generated** and **🟢 Live AI on**.
- Click **Reset demo state**. Do one practice run of tab ⑤ so the first live call isn't on stage.
- No key or no Wi-Fi? Everything still runs: tab ⑤ falls back to offline rules and says so.

---

**0:00 — The problem (Tab ① Before)**
"It's 9 AM and you're on call. This is your ServiceNow queue: 38 unassigned tickets, newest first, no summaries."
Point at the red row: "Somewhere in here is a possible PHI exposure. It came in by email, so it was auto-filed as Low, and it's been sitting for 11 hours."

**0:45 — Claude triaged the same queue (Tab ② Triage queue)**
"We gave these same 38 raw tickets to Claude. It wrote every summary, scored every ticket against our rubric, and routed it." The PHI ticket is now #1, flagged **Filed as Low**.
Open **Why this score & route**: read Claude's rationale, point at **Who's handled this before** (pulled from past tickets, not guessed) and **Scored by** (shows the model).
Click **Accept route**. Point at the KPIs: **38 tickets → 22 issues**, triage time **~33 min vs 3.8 hrs**.

**1:45 — Claude read the whole queue at once (Tab ③ Duplicate groups)**
"Six of these tickets are one problem. Claude connected three monitoring alerts with three nurses and managers saying their reports are stale, and worked out the root cause."
Show the root cause and fix. Show the **draft update** Claude wrote: "one message to every affected team instead of six replies." Click **Link** and **Send update**.
Scroll to the access-request group: "Five people emailed for dashboard access; that opens incidents. Claude flags them as requests before they breach SLA."

**2:45 — Routing (Tab ④)**
"Everything used to land in one shared queue. Now each issue goes to the team that owns it, with a suggested owner. The accept rate here is how we'd measure routing accuracy."

**3:15 — Live (Tab ⑤ Triage a new ticket)** — the moment that proves it's real
Pick **Duplicate of an open issue (bed census)** → **Triage it**. Point at "✨ Generated live by …" and the time: "Claude just read it, scored it, and recognized it's the same failed load. No new investigation."
Pick **Possible PHI exposure** → **Triage it**: no keyword list could catch every way someone describes this.
If time allows, let a judge type a ticket.
Open **See exactly what the model is told**: "here's the prompt: our queue definitions, our scoring rubric, our history."

**4:15 — Data access (Tab ⑥)**
"And the BI team gets the one table they asked for, ready to land in Redshift."

**4:30 — Close**
KPIs: time spent triaging, time to resolution, routing accuracy, duplicate volume.
Next: connect to the ServiceNow API, run on every new ticket as it arrives, then auto-assign by schedule, expertise and load.
Data safety: production would run in an approved environment (e.g. Bedrock in our own AWS account), with compliance sign-off before touching real tickets.
