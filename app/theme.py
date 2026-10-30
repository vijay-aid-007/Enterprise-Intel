"""Design system for the Streamlit app: palette, CSS and small HTML components.

Light and dark are both CSS-variable palettes. Every component colours itself with var(--...), so switching
Streamlit's theme restyles the custom HTML without touching Python. The active mode is read from
st.context.theme.type (Streamlit 1.46+); if it is unavailable the CSS follows the OS setting instead.

Text that comes from the model or the documents is untrusted. Every helper that puts caller-supplied text into
HTML escapes it first, and nothing else reaches st.markdown(..., unsafe_allow_html=True).
"""
from __future__ import annotations

from html import escape
from typing import Any

import streamlit as st

from src import config

# Light values, kept under the original names because other modules import them.
TONES: dict[str, tuple[str, str, str]] = {  # tone -> (text, background, border)
    "success": ("#0E6B43", "#E7F5EE", "#B7E1CB"),
    "info": ("#1D4ED8", "#E8F0FE", "#C3D5FB"),
    "warning": ("#8A5A00", "#FFF4D6", "#F2D98B"),
    "orange": ("#9A3412", "#FFEDD5", "#FDBA74"),
    "danger": ("#A3231A", "#FDECEA", "#F4C1BC"),
    "neutral": ("#475467", "#EEF1F5", "#D5DBE3"),
}
TONES_DARK: dict[str, tuple[str, str, str]] = {
    "success": ("#5FD3A0", "#0F2A1E", "#1E5A3F"),
    "info": ("#8FB0FF", "#14213F", "#2A4584"),
    "warning": ("#F2C25B", "#2E2410", "#6B5318"),
    "orange": ("#FFA66B", "#34190B", "#7A3B16"),
    "danger": ("#FF8A80", "#3A1512", "#7A2B25"),
    "neutral": ("#A9B3C1", "#1D232C", "#323B48"),
}
PALETTE_LIGHT = {
    "ink": "#111827", "muted": "#5B6472", "line": "#E3E6EB", "surface": "#FFFFFF", "bg": "#F6F7F9",
    "accent": "#2B4BC7", "track": "#F1F4F8", "tick": "#CBD5E1", "num": "#344054",
}
PALETTE_DARK = {
    "ink": "#E6E9EF", "muted": "#98A2B3", "line": "#2A313C", "surface": "#161B22", "bg": "#0E1218",
    "accent": "#6C8AF5", "track": "#232A35", "tick": "#475467", "num": "#CBD2DC",
}
TIER_TONE = {"Low": "success", "Medium": "warning", "High": "orange", "Critical": "danger"}
TIER_COLOR = {"Low": "#34A874", "Medium": "#F2B63D", "High": "#EE7A2F", "Critical": "#D64545"}
STATUS_DISPLAY: dict[str, tuple[str, str]] = {  # API status -> (label, tone)
    "answered": ("Answered", "success"),
    "refused_insufficient_evidence": ("Not covered by the documents", "neutral"),
    "refused_model": ("Not answerable from the documents", "neutral"),
    "rejected_validation": ("Withheld by automatic checks", "warning"),
    "llm_error": ("Language model unavailable", "danger"),
    "no_final_answer": ("No final answer", "danger"),
    "complete": ("Complete", "success"),
    "partial": ("Partial: some drafts withheld", "warning"),
    "all_withheld": ("All drafts withheld", "warning"),
    "no_recommendations": ("No recommendations", "neutral"),
    "no_playbook_evidence": ("Playbook not retrieved", "neutral"),
    "no_internet_service": ("No internet service", "neutral"),
}
TOOL_NAMES = {
    "search_documents": "Document search", "analyze_data": "Customer data analysis",
    "calculate": "Calculator", "generate_report": "Report generation",
}

BASE_CSS = """
:root{--radius:8px}
.stApp{background:var(--bg)}
.block-container{padding:4.25rem 2rem 3rem;max-width:1180px}
#MainMenu,footer{visibility:hidden}
html,body,.stApp,[data-testid="stMarkdownContainer"],[data-testid="stMetric"],label,input,textarea,button{
  font-family:Inter,"Segoe UI",-apple-system,BlinkMacSystemFont,Roboto,"Helvetica Neue",Arial,sans-serif}

/* Headings: Streamlit's defaults are far too large for a data tool */
.stApp h2{font-size:22px;font-weight:600;letter-spacing:-.01em;color:var(--ink);padding:.25rem 0 .5rem}
.stApp h3{font-size:18px;font-weight:600;letter-spacing:-.01em;color:var(--ink)}
.stApp h4,.stApp h5{font-size:15px;font-weight:600;color:var(--ink)}
[data-testid="stCaptionContainer"]{color:var(--muted)}

/* Sidebar */
[data-testid="stSidebar"]{background:var(--surface);border-right:1px solid var(--line)}

/* Native components */
[data-testid="stMetric"]{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);padding:12px 16px;box-shadow:none}
[data-testid="stMetricLabel"] p{font-size:13px;font-weight:500;color:var(--muted)}
[data-testid="stMetricValue"]{font-size:26px;font-weight:600;letter-spacing:-.01em;font-variant-numeric:tabular-nums}
[data-testid="stVerticalBlockBorderWrapper"],[data-testid="stExpander"],[data-testid="stAlert"]{border-radius:var(--radius)}
[data-testid="stDataFrame"]{border:1px solid var(--line);border-radius:var(--radius);overflow:hidden}
button[data-baseweb="tab"]{font-size:14px;font-weight:500;padding:8px 16px;color:var(--muted)}
button[data-baseweb="tab"][aria-selected="true"]{color:var(--ink);font-weight:600}
[data-baseweb="tab-list"]{gap:4px}
[data-baseweb="tab-border"]{background:var(--line)}
[data-baseweb="tab-highlight"]{background:var(--accent);height:2px}
[data-testid="stBaseButton-primary"],[data-testid="stBaseButton-secondary"]{border-radius:6px;font-weight:500;min-height:2.5rem}
[data-baseweb="input"],[data-baseweb="select"]>div,[data-baseweb="textarea"]{border-radius:6px}

/* Header */
.ei-top{display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap;padding-bottom:14px;border-bottom:1px solid var(--line)}
.ei-title{font-size:18px;font-weight:650;letter-spacing:-.01em;color:var(--ink)}
.ei-sub{font-size:13px;color:var(--muted);margin-top:2px}
.ei-pill{display:inline-flex;align-items:center;gap:8px;padding:4px 10px;border-radius:6px;border:1px solid;font-size:12.5px;font-weight:600}
.ei-dot{display:inline-block;width:8px;height:8px;border-radius:50%;flex:none}
.ei-chip{display:inline-block;padding:2px 8px;margin:0 6px 4px 0;border-radius:6px;border:1px solid;font-size:12px;font-weight:600;white-space:nowrap}
.ei-prov{margin:12px 0 6px}

/* Sections and rows */
.ei-section{font-size:14px;font-weight:600;color:var(--ink);margin:4px 0 8px}
.ei-cust{display:flex;align-items:center;flex-wrap:wrap;gap:6px;margin-bottom:4px}
.ei-cid{font-size:20px;font-weight:700;margin-right:8px;color:var(--ink)}
.ei-row{display:flex;align-items:center;gap:8px;font-size:13px;margin:6px 0}
.ei-row-val{margin-left:auto;font-size:12.5px;font-weight:500}

/* KPI strip: one bordered block, cells split by hairlines */
.ei-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);margin:8px 0}
.ei-kpi{padding:14px 18px;border-left:1px solid var(--line)}
.ei-kpi:first-child{border-left:0}
.ei-kpi-label{font-size:13px;font-weight:500;color:var(--muted)}
.ei-kpi-value{font-size:26px;font-weight:600;letter-spacing:-.01em;margin-top:2px;font-variant-numeric:tabular-nums;color:var(--ink)}
.ei-kpi-cap{font-size:12px;color:var(--muted);margin-top:2px}

/* Risk gauge and driver bars */
.ei-gauge-wrap{position:relative;margin:20px 0 6px}
.ei-gauge{display:flex;height:12px;border-radius:999px;overflow:hidden}
.ei-marker{position:absolute;top:-5px;width:4px;height:22px;margin-left:-2px;background:var(--ink);border:1px solid var(--surface);border-radius:2px}
.ei-gauge-labels{display:flex;font-size:11px;color:var(--muted);margin-top:6px}
.ei-legend,.ei-drv{display:grid;grid-template-columns:minmax(180px,1.2fr) 2fr 64px;gap:12px;align-items:center}
.ei-legend{font-size:11px;color:var(--muted);margin-bottom:2px}
.ei-legend-mid{display:flex;justify-content:space-between}
.ei-drv{font-size:13px;margin:8px 0}
.ei-drv small{color:var(--muted)}
.ei-track{position:relative;height:10px;background:var(--track);border-radius:6px}
.ei-track::after{content:"";position:absolute;left:50%;top:-3px;width:1px;height:16px;background:var(--tick)}
.ei-bar{position:absolute;top:0;height:10px;border-radius:6px}
.ei-num{text-align:right;font-variant-numeric:tabular-nums;color:var(--num)}

/* Empty state */
.ei-empty{border:1px solid var(--line);border-radius:var(--radius);padding:36px 24px;text-align:center;background:var(--surface)}
.ei-empty-title{font-size:14px;font-weight:600;color:var(--ink)}
.ei-empty-hint{font-size:13px;color:var(--muted);margin-top:4px}
"""


def _block(palette: dict[str, str], tones: dict[str, tuple[str, str, str]], scheme: str) -> str:
    parts = [f"color-scheme:{scheme}"] + [f"--{key}:{value}" for key, value in palette.items()]
    for name, (fg, bg, border) in tones.items():
        parts += [f"--t-{name}-fg:{fg}", f"--t-{name}-bg:{bg}", f"--t-{name}-bd:{border}"]
    return ";".join(parts)


def build_css(mode: str | None) -> str:
    """CSS for one mode. With mode None (undetectable) the OS preference decides."""
    light = _block(PALETTE_LIGHT, TONES, "light")
    dark = _block(PALETTE_DARK, TONES_DARK, "dark")
    if mode == "dark":
        root = f":root{{{dark}}}"
    elif mode == "light":
        root = f":root{{{light}}}"
    else:
        root = f":root{{{light}}}@media (prefers-color-scheme: dark){{:root{{{dark}}}}}"
    return f"<style>{root}{BASE_CSS}</style>"


CSS = build_css(None)


def current_mode() -> str | None:
    """'light' or 'dark' as Streamlit is currently rendering, or None if this version cannot say."""
    try:
        value = st.context.theme.type
    except Exception:
        return None
    return value if value in ("light", "dark") else None


def inject_css() -> None:
    st.markdown(build_css(current_mode()), unsafe_allow_html=True)


def _tone(tone: str) -> str:
    return tone if tone in TONES else "neutral"


def _tone_style(tone: str) -> str:
    t = _tone(tone)
    return f"color:var(--t-{t}-fg);background:var(--t-{t}-bg);border-color:var(--t-{t}-bd)"


def status_label(status: str) -> tuple[str, str]:
    """(label, tone) for any API status; unknown statuses are shown as plain text, never hidden."""
    return STATUS_DISPLAY.get(status, (status.replace("_", " "), "neutral"))


def tier_for(prob: float) -> str:
    """Risk tier for a score from config.TIER_BANDS (the same rule as src.llm.report_evidence.risk_tier)."""
    tier = config.TIER_BANDS[0][0]
    for name, lower in config.TIER_BANDS:
        if prob >= lower:
            tier = name
    return tier


def chip(text: Any, tone: str = "neutral", title: str = "") -> str:
    tip = f' title="{escape(title, quote=True)}"' if title else ""
    return f'<span class="ei-chip" style="{_tone_style(tone)}"{tip}>{escape(str(text))}</span>'


def header(title: str, subtitle: str, status_text: str, tone: str) -> None:
    """Page header: product name on the left, API status on the right, a hairline underneath."""
    t = _tone(tone)
    pill = (
        f'<span class="ei-pill" style="{_tone_style(t)}">'
        f'<span class="ei-dot" style="background:var(--t-{t}-fg)"></span>{escape(status_text)}</span>'
    )
    st.markdown(
        f'<div class="ei-top"><div><div class="ei-title">{escape(title)}</div>'
        f'<div class="ei-sub">{escape(subtitle)}</div></div>{pill}</div>',
        unsafe_allow_html=True,
    )


hero = header  # kept so existing callers do not break


def provenance() -> None:
    st.markdown(
        '<div class="ei-prov">'
        + chip("Real data: Telco customers and churn labels", "success")
        + chip("Synthetic: policy, pricing, terms and tickets", "warning")
        + "</div>",
        unsafe_allow_html=True,
    )


def section(title: str, caption: str = "") -> None:
    st.markdown(f'<div class="ei-section">{escape(title)}</div>', unsafe_allow_html=True)
    if caption:
        st.caption(caption)


def empty_state(text: str, hint: str = "") -> None:
    hint_html = f'<div class="ei-empty-hint">{escape(hint)}</div>' if hint else ""
    st.markdown(
        f'<div class="ei-empty"><div class="ei-empty-title">{escape(text)}</div>{hint_html}</div>',
        unsafe_allow_html=True,
    )


def status_rows(items: list[tuple[str, bool]]) -> str:
    """Sidebar health rows: a coloured dot, the component name and Ready or Missing."""
    rows = []
    for label, ok in items:
        dot = "var(--t-success-fg)" if ok else "var(--t-danger-fg)"
        value_color = "var(--muted)" if ok else "var(--t-danger-fg)"
        rows.append(
            f'<div class="ei-row"><span class="ei-dot" style="background:{dot}"></span>{escape(label)}'
            f'<span class="ei-row-val" style="color:{value_color}">{"Ready" if ok else "Missing"}</span></div>'
        )
    return "".join(rows)


def kpi_strip(items: list[tuple[str, str, str, str]]) -> str:
    """One bordered block of figures. Each item is (label, value, caption, tone); tone "" keeps the value neutral."""
    cells = []
    for label, value, caption, tone in items:
        color = f' style="color:var(--t-{tone}-fg)"' if tone in TONES else ""
        cap = f'<div class="ei-kpi-cap">{escape(caption)}</div>' if caption else ""
        cells.append(
            f'<div class="ei-kpi"><div class="ei-kpi-label">{escape(label)}</div>'
            f'<div class="ei-kpi-value"{color}>{escape(value)}</div>{cap}</div>'
        )
    return f'<div class="ei-kpis">{"".join(cells)}</div>'


def gauge(prob: float) -> str:
    """Tier bar built from config.TIER_BANDS, with a marker at the score."""
    bands = list(config.TIER_BANDS)
    edges = [lower for _, lower in bands] + [1.0]
    widths = [(edges[i + 1] - edges[i]) * 100 for i in range(len(bands))]
    segments = "".join(
        f'<div style="width:{w:.1f}%;background:{TIER_COLOR.get(name, "#94A3B8")}"></div>'
        for (name, _), w in zip(bands, widths)
    )
    labels = "".join(
        f'<span style="width:{w:.1f}%">{escape(name)} from {lower:.2f}</span>' for (name, lower), w in zip(bands, widths)
    )
    position = min(max(float(prob), 0.0), 1.0) * 100
    return (
        f'<div class="ei-gauge-wrap"><div class="ei-gauge">{segments}</div>'
        f'<div class="ei-marker" style="left:{position:.1f}%"></div><div class="ei-gauge-labels">{labels}</div></div>'
    )


def driver_bars(drivers: list[dict[str, Any]]) -> str:
    """SHAP drivers as diverging bars: left of the centre line lowers risk (green), right raises it (red)."""
    if not drivers:
        return ""
    peak = max(abs(float(d["contribution"])) for d in drivers) or 1.0
    rows = ['<div class="ei-legend"><div></div><div class="ei-legend-mid"><span>&larr; lowers churn risk</span><span>raises churn risk &rarr;</span></div><div></div></div>']
    for d in drivers:
        value = float(d["contribution"])
        width = abs(value) / peak * 50
        side, color = ("left:50%", "#D64545") if value > 0 else ("right:50%", "#34A874")
        name = str(d["feature"]).replace("_", ": ", 1)
        rows.append(
            f'<div class="ei-drv"><div><b>{escape(name)}</b><br><small>customer value: {escape(str(d["customer_value"]))}</small></div>'
            f'<div class="ei-track"><div class="ei-bar" style="{side};width:{width:.1f}%;background:{color}"></div></div>'
            f'<div class="ei-num">{value:+.3f}</div></div>'
        )
    return "".join(rows)