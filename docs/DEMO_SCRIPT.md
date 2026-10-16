# 5-minute demo script

**Setup:** `streamlit run app.py`, browser full screen, sidebar collapsed. Click **Reset demo state** in the sidebar before you start.

---

**0:00 — The problem (Tab ① Before)**
"It's 9 AM Thursday and you're on call. This is your ServiceNow queue: 38 unassigned tickets, newest first, no summaries."
Point at the red row: "Somewhere in here is a possible PHI exposure — patient names visible to all staff. It came in by email, so it was auto-filed as 4-Low, and it's been sitting for 11 hours."

**0:45 — Same queue, triaged (Tab ② Triage queue)**
"Same 38 tickets after Triage Copilot. The PHI ticket is now #1 with a score of 97, flagged 'Filed as Low', routed to Data Access & Security."
Open **Why this score & route** → read the rationale, point at *Scored by* (answers "who scored it?").
Click **Accept route**. Note the counter: "1 routed so far."
Point at the KPIs: **38 tickets → 22 issues**, triage time **~33 min vs 3.8 hrs**.

**1:45 — Duplicates (Tab ③ Duplicate groups)**
"Six tickets were really one problem: the overnight Cerner ADT load failed. Three monitoring alerts plus three nurses and managers saying their bed census is stale."
Show root cause + "Do this". Click **Link 5 to parent**, then **Send update** — "one message to Nursing, Capacity and the ED instead of six separate replies."
Scroll to GRP-03: "Five managers emailed for dashboard access — those auto-opened as Incidents. Copilot flags them as Requests so they get converted before they breach SLA."

**2:45 — Routing (Tab ④)**
"Before, everything lands in one shared queue. After, each issue goes to the team that owns it — and suggests an owner based on who fixed similar tickets. Three tickets go straight back to the IT Service Desk."

**3:15 — Live input (Tab ⑤ Triage a new ticket)**
Pick **Duplicate of an open issue (bed census)** → **Triage it**: "A seventh bed census complaint just came in — it's recognized as part of the existing ADT incident, so nobody starts a new investigation."
Pick **Not Data Engineering** → **Triage it**: routed to the Service Desk.
(Optional) type your own ticket live.

**4:00 — Data access (Tab ⑥)**
"The BI team asked for one table they can query. Here it is — and in production it lands in Redshift." Expand the DDL.

**4:30 — Close**
KPIs we'd track: time spent triaging, time to resolution, routing accuracy (accept rate in Tab ④), duplicate volume.
Next: swap the precomputed results for a live model call on the ServiceNow Table API; then auto-assignment by schedule, expertise and load.
