"""
Shared UI helpers and CSS for the Implementation Demo.
"""
import html
import json
from pathlib import Path

_CONFIG_PATH = Path(__file__).parent.parent / "config" / "scoring.json"
_CFG = json.loads(_CONFIG_PATH.read_text())

PCOLOR = {k: v["fg"] for k, v in _CFG["colors"].items()}
PBG    = {k: v["bg"] for k, v in _CFG["colors"].items()}
LABELS = _CFG["labels"]
THRESH = _CFG["thresholds"]

CSS = """
<style>
.block-container {padding-top: 1.6rem; max-width: 1400px;}

/* Header */
.hdr {display:flex; justify-content:space-between; align-items:flex-end; margin-bottom:.4rem;}
.hdr h1 {font-size:1.9rem; margin:0; letter-spacing:-.02em;}
.hdr .sub {color:#5A6573; font-size:.92rem; margin-top:.15rem;}
.clock {background:#fff; border:1px solid #E1E5EA; border-radius:10px; padding:.45rem .8rem;
        font-size:.85rem; color:#3A4552; white-space:nowrap;}

/* KPI strip */
.kpis {display:grid; gap:.7rem; margin:.8rem 0 1rem;}
.kpi {background:#fff; border:1px solid #E1E5EA; border-radius:12px; padding:.75rem .9rem;}
.kpi .lbl {font-size:.74rem; text-transform:uppercase; letter-spacing:.05em; color:#6B7684;}
.kpi .val {font-size:1.6rem; font-weight:700; margin-top:.1rem; color:#1C2430;}
.kpi .val small {font-size:.9rem; font-weight:500; color:#6B7684;}
.kpi .delta {font-size:.8rem; color:#0F6E6E; margin-top:.1rem;}

/* Pills / badges */
.pill {display:inline-block; padding:.12rem .5rem; border-radius:999px; font-size:.72rem;
       font-weight:600; margin-right:.3rem; white-space:nowrap;}

/* Score box */
.score {width:58px; height:58px; border-radius:12px; display:flex; flex-direction:column;
        align-items:center; justify-content:center; font-weight:700; line-height:1.05;}
.score .n {font-size:1.35rem;}
.score .p {font-size:.68rem; font-weight:600;}

/* Issue card text */
.summ {font-size:1.0rem; font-weight:600; color:#1C2430; margin-bottom:.15rem;}
.orig {font-size:.82rem; color:#6B7684; margin-bottom:.3rem;}
.route {font-size:.88rem;}
.route b {color:#0F6E6E;}
.conf {height:6px; background:#E8ECF0; border-radius:4px; margin-top:.35rem; overflow:hidden;}
.conf > div {height:100%; background:#0F6E6E;}
.muted {color:#6B7684; font-size:.8rem;}

/* Group card */
.gcard-h {font-size:1.05rem; font-weight:700;}

/* Agent step */
.agent-step {background:#fff; border:1px solid #D4E8E8; border-radius:10px; padding:.6rem .9rem;
             margin:.3rem 0; font-size:.9rem; color:#0F6E6E;}
.agent-step .done {color:#0F6E6E; font-weight:600;}
.agent-step .running {color:#E07B24; font-weight:600;}

/* API trace terminal */
.api-trace {
  background:#0D1117; color:#C9D1D9; font-family:'Courier New',monospace;
  font-size:.78rem; border-radius:10px; padding:1rem 1.2rem;
  line-height:1.6; max-height:420px; overflow-y:auto;
  border:1px solid #30363D;
}
.api-trace .ts {color:#6E7681;}
.api-trace .mcp {color:#58A6FF; font-weight:600;}
.api-trace .az  {color:#3FB950; font-weight:600;}
.api-trace .ok  {color:#58A6FF;}
.api-trace .warn{color:#F0883E;}
.api-trace .dim {color:#6E7681;}

/* Architecture diagram */
.arch-box {
  border-radius:12px; padding:1.1rem 1.2rem; text-align:center;
  font-size:.9rem; font-weight:600;
}
.arch-arrow {
  display:flex; align-items:center; justify-content:center;
  font-size:1.4rem; color:#6B7684; margin:0 .5rem;
}

/* Connection cards in sidebar */
.conn-card {
  border-radius:8px; padding:.5rem .75rem; margin-bottom:.5rem;
}
.conn-green {background:#E8F5E9; border:1px solid #A5D6A7;}
.conn-green .conn-title {font-weight:600; color:#1B5E20; font-size:.85rem;}
.conn-green .conn-sub {font-size:.75rem; color:#2E7D32;}
.conn-blue {background:#E3F2FD; border:1px solid #90CAF9;}
.conn-blue .conn-title {font-weight:600; color:#0D47A1; font-size:.85rem;}
.conn-blue .conn-sub {font-size:.75rem; color:#1565C0;}
.conn-purple {background:#EDE7F6; border:1px solid #B39DDB;}
.conn-purple .conn-title {font-weight:600; color:#311B92; font-size:.85rem;}
.conn-purple .conn-sub {font-size:.75rem; color:#4527A0;}

/* Sidebar note */
.sidebar-note {
  background:#F0F4F8; border:1px solid #D1DAE3; border-radius:8px;
  padding:.6rem .8rem; font-size:.78rem; color:#3A4552;
}

/* Needs info */
.needs-info {background:#FFF8E6; border:1px solid #F5D88A; border-radius:10px; padding:.7rem .9rem;
             color:#7A5E00; font-size:.9rem; margin:.4rem 0 .8rem;}

/* Source badge */
.src-badge {
  display:inline-block; background:#E3F2FD; color:#0D47A1;
  border:1px solid #90CAF9; border-radius:6px; padding:.1rem .45rem;
  font-size:.7rem; font-weight:600; margin-left:.4rem;
}

/* Step flow (architecture) */
.step-card {
  border:1px solid #E1E5EA; border-radius:12px; padding:1rem 1.2rem;
  background:#fff; height:100%;
}
.step-num {
  width:28px; height:28px; border-radius:50%; background:#0F6E6E; color:#fff;
  display:inline-flex; align-items:center; justify-content:center;
  font-size:.85rem; font-weight:700; margin-bottom:.5rem;
}
</style>
"""


def pkey(label: str) -> str:
    return label


def pill(text: str, fg: str, bg: str) -> str:
    return (
        f'<span class="pill" style="color:{fg};background:{bg};">'
        f'{html.escape(text)}</span>'
    )


def priority_pill(label: str) -> str:
    return pill(label, PCOLOR.get(label, "#3A4552"), PBG.get(label, "#EEF1F4"))


def plabel_for(score: int) -> str:
    t = THRESH
    if score >= t["critical_min"]:
        return "Critical"
    if score >= t["high_min"]:
        return "High"
    if score >= t["medium_min"]:
        return "Medium"
    return "Low"


def score_box(score: int, label: str) -> str:
    fg  = PCOLOR.get(label, "#3A4552")
    bg  = PBG.get(label, "#EEF1F4")
    return (
        f'<div class="score" style="background:{bg};color:{fg};">'
        f'<span class="n">{score}</span>'
        f'<span class="p">{html.escape(label)}</span>'
        f'</div>'
    )


def age(hrs: float) -> str:
    if hrs < 1:
        return f"{int(hrs * 60)}m"
    if hrs < 24:
        return f"{hrs:.1f}h"
    return f"{hrs / 24:.1f}d"
