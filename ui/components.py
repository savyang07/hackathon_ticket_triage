"""
Shared UI helpers and styling for both tabs.

All color constants, CSS, and small rendering helpers live here so the Before
and After tabs always look consistent.
"""
import html
import json
from pathlib import Path

# ---------------------------------------------------------------------------
# Load scoring config once (colors, labels, thresholds)
# ---------------------------------------------------------------------------
_CONFIG_PATH = Path(__file__).parent.parent / "config" / "scoring.json"
_CFG = json.loads(_CONFIG_PATH.read_text())

PCOLOR = {k: v["fg"] for k, v in _CFG["colors"].items()}
PBG    = {k: v["bg"] for k, v in _CFG["colors"].items()}
LABELS = _CFG["labels"]   # {"Critical": "Critical", "High": "High", ...}
THRESH = _CFG["thresholds"]  # {"critical_min": 70, "high_min": 50, "medium_min": 30}

# ---------------------------------------------------------------------------
# Keck Medicine of USC brand colors (sampled from the official logo)
# ---------------------------------------------------------------------------
CARDINAL      = "#991B1E"   # Keck / USC cardinal
CARDINAL_DARK = "#7A1518"
CARDINAL_TINT = "#F7E9E9"
GOLD          = "#FFCC00"   # USC gold (accents only: low contrast on white)
GOLD_DARK     = "#B38600"   # gold for text and chart marks on white
GOLD_TINT     = "#FFF4CC"

# ---------------------------------------------------------------------------
# Global CSS injected once from the main app
# ---------------------------------------------------------------------------
CSS = """
<style>
.block-container {padding-top: 1.6rem; max-width: 1400px;}
.hdr {display:flex; justify-content:space-between; align-items:flex-end; margin-bottom:.4rem;}
.brand {display:flex; align-items:center; gap:1.1rem; background:#991B1E; border-bottom:4px solid #FFCC00;
        border-radius:12px; padding:.85rem 1.2rem; margin-bottom:1rem;}
.brand img {height:34px; display:block;}
.brand .divider {width:1px; align-self:stretch; background:rgba(255,255,255,.35);}
.brand h1 {font-size:1.75rem; margin:0; color:#fff; letter-spacing:-.01em; line-height:1.1;}
.brand .sub {color:#F3DADA; font-size:.9rem; margin-top:.15rem;}
.brand .sub b {color:#FFCC00; font-weight:600;}
h1, h2, h3, h4 {color:#1C2430;}
.stTabs [aria-selected="true"] p {color:#991B1E !important; font-weight:600;}
.hdr h1 {font-size:1.9rem; margin:0; letter-spacing:-.02em;}
.hdr .sub {color:#5A6573; font-size:.92rem; margin-top:.15rem;}
.clock {background:#fff; border:1px solid #E1E5EA; border-radius:10px; padding:.45rem .8rem;
        font-size:.85rem; color:#3A4552; white-space:nowrap;}
.kpis {display:grid; grid-template-columns:repeat(5,1fr); gap:.7rem; margin:.8rem 0 1rem;}
.kpi {background:#fff; border:1px solid #E1E5EA; border-radius:12px; padding:.75rem .9rem;}
.kpi .lbl {font-size:.74rem; text-transform:uppercase; letter-spacing:.05em; color:#6B7684;}
.kpi .val {font-size:1.6rem; font-weight:700; margin-top:.1rem; color:#1C2430;}
.kpi .val small {font-size:.9rem; font-weight:500; color:#6B7684;}
.kpi {border-top:3px solid #991B1E;}
.kpi .delta {font-size:.8rem; color:#991B1E; margin-top:.1rem;}
.pill {display:inline-block; padding:.12rem .5rem; border-radius:999px; font-size:.72rem;
       font-weight:600; margin-right:.3rem; white-space:nowrap;}
.score {width:58px; height:58px; border-radius:12px; display:flex; flex-direction:column;
        align-items:center; justify-content:center; font-weight:700; line-height:1.05;}
.score .n {font-size:1.35rem;} .score .p {font-size:.68rem; font-weight:600;}
.summ {font-size:1.0rem; font-weight:600; color:#1C2430; margin-bottom:.15rem;}
.orig {font-size:.82rem; color:#6B7684; margin-bottom:.3rem;}
.route {font-size:.88rem;} .route b {color:#991B1E;}
.conf {height:6px; background:#E8ECF0; border-radius:4px; margin-top:.35rem; overflow:hidden;}
.conf > div {height:100%; background:#991B1E;}
.muted {color:#6B7684; font-size:.8rem;}
.callout {background:#FCE9E8; border:1px solid #F2C4C2; border-radius:10px; padding:.7rem .9rem;
          color:#7A1F1D; font-size:.9rem; margin:.4rem 0 .8rem;}
.callout-warn {background:#FDF0E4; border:1px solid #F5D0A9; border-radius:10px; padding:.7rem .9rem;
               color:#7A4B00; font-size:.9rem; margin:.4rem 0 .8rem;}
.callout-info {background:#EDF2F5; border:1px solid #C8D6E0; border-radius:10px; padding:.7rem .9rem;
               color:#2A4255; font-size:.9rem; margin:.4rem 0 .8rem;}
.needs-info {background:#FFF8E6; border:1px solid #F5D88A; border-radius:10px; padding:.7rem .9rem;
             color:#7A5E00; font-size:.9rem; margin:.4rem 0 .8rem;}
.gcard-h {font-size:1.05rem; font-weight:700;}
.mini td, .mini th {font-size:.82rem;}
.before-header {background:#F6F7F9; border:1px solid #E1E5EA; border-radius:10px;
                padding:.7rem .9rem; margin-bottom:.8rem; font-size:.88rem; color:#3A4552;}
.agent-step {background:#fff; border:1px solid #EBD3D3; border-left:4px solid #991B1E; border-radius:10px;
             padding:.6rem .9rem; margin:.3rem 0; font-size:.9rem; color:#1C2430;}
.agent-step .done {color:#991B1E; font-weight:600;}
.agent-step .running {color:#E07B24; font-weight:600;}

/* API trace terminal (Run Triage and Triage a new ticket) */
.api-trace {background:#16110F; color:#E6DFD8; font-family:'Courier New',monospace; font-size:.78rem;
            border-radius:10px; padding:1rem 1.2rem; line-height:1.6; max-height:440px; overflow-y:auto;
            border:1px solid #3A2A26; border-left:4px solid #991B1E;}
.api-trace .ts {color:#8C7F78;}
.api-trace .mcp {color:#FF8A80; font-weight:700;}
.api-trace .az {color:#FFCC00; font-weight:700;}
.api-trace .loc {color:#B7C4CF; font-weight:700;}
.api-trace .ok {color:#9CCC65;}
.api-trace .hold {color:#FFB74D; font-weight:700;}
.api-trace .dim {color:#B3A79F;}
.api-trace .done {color:#9CCC65; font-weight:700;}

/* Integration cards in the sidebar */
.conn-card {background:#fff; border:1px solid #E5D8D8; border-left:4px solid #991B1E; border-radius:8px;
            padding:.45rem .7rem; margin-bottom:.45rem;}
.conn-card .conn-title {font-weight:600; color:#1C2430; font-size:.85rem;}
.conn-card .conn-sub {font-size:.74rem; color:#6B7684;}
.conn-card.gold {border-left-color:#FFCC00;}
.conn-card.slate {border-left-color:#52606D;}
.sim-tag {display:inline-block; font-size:.66rem; font-weight:700; color:#7A5E00; background:#FFF4CC;
          border:1px solid #F0D98A; border-radius:999px; padding:0 .4rem; margin-left:.3rem; vertical-align:1px;}
.sidebar-note {background:#F7E9E9; border:1px solid #EBD3D3; border-radius:8px; padding:.6rem .8rem;
               font-size:.78rem; color:#3A2A2A;}

/* Source badge on ticket cards */
.src-badge {display:inline-block; background:#F7E9E9; color:#7A1518; border:1px solid #EBD3D3; border-radius:6px;
            padding:.1rem .45rem; font-size:.7rem; font-weight:600; margin-right:.3rem;}

/* Architecture tab */
.arch-col {border-radius:14px; padding:1rem 1.1rem; height:100%; background:#fff; border:1px solid #E5D8D8;}
.arch-col.cardinal {border-top:5px solid #991B1E;}
.arch-col.gold {border-top:5px solid #FFCC00;}
.arch-col.slate {border-top:5px solid #52606D;}
.arch-col .t {font-weight:700; font-size:1rem; color:#1C2430; margin:.2rem 0 .45rem;}
.arch-col .b {font-size:.84rem; color:#3A4552; line-height:1.5;}
.arch-col code {background:#F7E9E9; color:#7A1518; padding:.05rem .3rem; border-radius:4px; font-size:.78rem;}
.arch-arrow {display:flex; align-items:center; justify-content:center; height:100%; font-size:1.9rem; color:#991B1E;}
.agent-grid {margin-top:.55rem; display:grid; grid-template-columns:1fr 1fr; gap:.4rem;}
.agent-grid div {background:#FFFBEA; border:1px solid #F0D98A; border-radius:8px; padding:.4rem .6rem;
                 font-size:.78rem; color:#3A2F00;}
.step-card {border:1px solid #E5D8D8; border-radius:12px; padding:1rem 1.1rem; background:#fff; height:100%;}
.step-card .h {font-weight:700; color:#1C2430; margin:.35rem 0 .35rem; font-size:.9rem;}
.step-card .b {font-size:.8rem; color:#5A6573; line-height:1.5;}
.step-num {width:28px; height:28px; border-radius:50%; background:#991B1E; color:#fff; display:inline-flex;
           align-items:center; justify-content:center; font-size:.85rem; font-weight:700;}
</style>
"""


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def pkey(label: str) -> str:
    """'Critical' → 'Critical'  (key into PCOLOR/PBG/LABELS)"""
    return label  # labels are now single words matching config keys directly


def pill(text: str, fg: str, bg: str) -> str:
    """Render a colored badge/pill as HTML."""
    return f'<span class="pill" style="color:{fg};background:{bg}">{html.escape(str(text))}</span>'


def priority_pill(label: str) -> str:
    """Render a priority pill using config colors for Critical/High/Medium/Low."""
    k = pkey(label)
    fg = PCOLOR.get(k, "#6B7684")
    bg = PBG.get(k, "#F0F2F5")
    return pill(label, fg, bg)


def score_box(score: int, plabel: str) -> str:
    """Render the square priority score badge."""
    k = pkey(plabel)
    fg = PCOLOR.get(k, "#6B7684")
    bg = PBG.get(k, "#F0F2F5")
    return (
        f'<div class="score" style="background:{bg};color:{fg};'
        f'border:1.5px solid {fg}">'
        f'<span class="n">{score}</span>'
        f'<span class="p">{k[:4]}</span></div>'
    )


def age(hrs: float) -> str:
    """Convert a float hours value to a human-readable age string."""
    if hrs < 1:
        return f"{int(hrs * 60)}m"
    if hrs < 48:
        return f"{hrs:.0f}h"
    return f"{hrs / 24:.1f}d"


def plabel_for(score: int) -> str:
    """Return the priority label string for a given 0-100 ERWG score."""
    if score >= THRESH["critical_min"]:
        return LABELS["Critical"]
    if score >= THRESH["high_min"]:
        return LABELS["High"]
    if score >= THRESH["medium_min"]:
        return LABELS["Medium"]
    return LABELS["Low"]
