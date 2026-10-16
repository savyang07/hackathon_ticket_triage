"""
Run every dummy ticket through Claude and save the results for the demo.

    python scripts/precompute.py            # writes data/tickets_llm.json
    python scripts/precompute.py --limit 5  # quick smoke test on 5 tickets

Needs ANTHROPIC_API_KEY (or LLM_PROVIDER=bedrock + AWS credentials) in the environment
or in .streamlit/secrets.toml. The app picks up data/tickets_llm.json automatically,
so on demo day nothing calls the API unless you use the live tab.

Steps
  1. Claude reads the whole queue once and finds duplicate groups (root cause, fix, comms draft).
  2. Claude triages each ticket (summary, score, queue, owner, confidence, rationale,
     request-vs-incident, similar history), knowing which group it belongs to.
  3. Anything that fails after retries falls back to the offline rules and is labeled as such.
"""
import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from triage import llm  # noqa: E402
from triage.offline_engine import SimilarityIndex, triage as offline_triage  # noqa: E402

RAW_FIELDS = ["number", "type", "channel", "opened_at", "caller", "caller_dept", "snow_priority",
              "state", "assignment_group", "assigned_to", "short_description", "description"]


def run(client=None, cfg=None, limit=None, workers=6, out_path=None, log=print):
    src = json.loads((ROOT / "data" / "tickets.json").read_text())
    queues, now = src["queues"], src["demo_now"]
    raw = [{k: t[k] for k in RAW_FIELDS} for t in src["tickets"]]   # model never sees the hand-written answers
    if limit:
        raw = raw[:limit]
    history = llm.load_history()

    cfg = cfg or llm.get_config("precompute")
    if cfg is None:
        sys.exit("No model configured. Set ANTHROPIC_API_KEY (or LLM_PROVIDER=bedrock + AWS creds), "
                 "or add them to .streamlit/secrets.toml.")
    client = client or llm.make_client(cfg, timeout=120)
    log(f"Model: {cfg.label} · {len(raw)} tickets")
    usage = {"input_tokens": 0, "output_tokens": 0, "calls": 0}

    def add_usage(meta):
        usage["calls"] += 1
        for k in ("input_tokens", "output_tokens"):
            usage[k] += meta.get(k) or 0

    # 1) grouping ---------------------------------------------------------------
    t0 = time.time()
    try:
        groups, meta = llm.group_tickets(client, cfg, raw)
        add_usage(meta)
    except Exception as e:  # keep going without groups rather than fail the run
        log(f"  ! grouping failed ({e}); continuing with no groups")
        groups = []
    log(f"  grouped in {time.time() - t0:.1f}s → {len(groups)} groups")

    membership = {n: g for g in groups for n in g["members"]}

    # 2) per-ticket triage ------------------------------------------------------
    index = SimilarityIndex(src["tickets"])
    results, failures = {}, []

    def one(t):
        g = membership.get(t["number"])
        ctx = ""
        if g:
            others = [m for m in g["members"] if m != t["number"]]
            ctx = (f"This ticket is part of duplicate group '{g['title']}' with {', '.join(others)}. "
                   f"Likely root cause: {g['root_cause']}")
        last = None
        for attempt in range(3):
            try:
                res, meta = llm.triage_ticket(client, cfg, t, queues, now, history, group_context=ctx)
                return t["number"], res, meta, None
            except Exception as e:  # noqa: BLE001
                last = e
                time.sleep(1.5 * (attempt + 1))
        return t["number"], None, None, last

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(one, t) for t in raw]
        for i, f in enumerate(as_completed(futs), 1):
            num, res, meta, err = f.result()
            if err:
                failures.append(num)
                log(f"  ! {num} failed: {err}")
            else:
                results[num] = res
                add_usage(meta)
            if i % 10 == 0 or i == len(raw):
                log(f"  triaged {i}/{len(raw)}")
    log(f"  triage took {time.time() - t0:.1f}s")

    # 3) assemble ---------------------------------------------------------------
    # Number groups by urgency so GRP-01 is always the most critical one.
    groups.sort(key=lambda g: -max((results[n]["score"] for n in g["members"] if n in results), default=0))
    for i, g in enumerate(groups, 1):
        g["_id"] = f"GRP-{i:02d}"
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    tickets = []
    for t in raw:
        res = results.get(t["number"])
        if res is None:   # fallback keeps the demo whole
            o = offline_triage(t["short_description"] + ". " + t["description"], index, queues)
            res = {**o, "similar_history": "", "score": o["score"]}
            scored_by = "Offline rules (model call failed)"
        else:
            scored_by = f"{cfg.model} · {stamp}"
        g = membership.get(t["number"])
        tickets.append({
            **t,
            "ai_summary": res["summary"], "ai_category": res["category"],
            "ai_priority_score": res["score"], "ai_priority": llm.priority_label(res["score"]),
            "ai_route_queue": res["queue"], "ai_route_owner": res["owner"],
            "ai_confidence": res["confidence"], "ai_rationale": res["rationale"],
            "ai_should_be_request": res["should_be_request"],
            "ai_similar_history": res.get("similar_history", ""),
            "group_id": g["_id"] if g else "", "group_role": ("parent" if g and g["parent"] == t["number"]
                                                               else "child" if g else ""),
            "scored_by": scored_by,
        })

    # A group routes where its parent routes, so all its tickets land in one queue.
    by_num = {t["number"]: t for t in tickets}
    for g in groups:
        p = by_num[g["parent"]]
        for n in g["members"]:
            by_num[n]["ai_route_queue"], by_num[n]["ai_route_owner"] = p["ai_route_queue"], p["ai_route_owner"]

    payload = {
        "demo_now": now,
        "generated_by": cfg.label,
        "generated_at": stamp,
        "usage": usage,
        "failures": failures,
        "queues": queues,
        "groups": {g["_id"]: {k: g[k] for k in ("title", "root_cause", "recommended_action", "notify",
                                                "comms_draft")} for g in groups},
        "tickets": tickets,
    }
    out = Path(out_path) if out_path else ROOT / "data" / "tickets_llm.json"
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    log(f"Wrote {out} · {usage['calls']} calls · {usage['input_tokens']:,} in / "
        f"{usage['output_tokens']:,} out tokens · {len(failures)} failures")
    return payload


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, help="only the first N tickets (smoke test)")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--out", help="output path (default data/tickets_llm.json)")
    a = ap.parse_args()
    run(limit=a.limit, workers=a.workers, out_path=a.out)
