# =========================
# app/ui.py  (UPDATED)
# =========================
from __future__ import annotations

import html
import streamlit as st
import sys


def inject_theme() -> None:
    st.markdown(
        """
<style>
/* ============================================================
   MedCore / Hospital-grade theme (matches screenshots)
   - Dark navy sidebar
   - Light canvas + white cards
   - Teal accent
   - Risk pills (low/mod/high)
   ============================================================ */

/* Hide Streamlit built-in multipage nav (since we have our own router) */
[data-testid="stSidebarNav"] { display: none !important; }

:root{
  /* Screenshot-like palette */
  --primary: 212 72% 20%;          /* deep clinical navy */
  --primary-2: 212 72% 16%;        /* darker sidebar */
  --accent: 177 60% 38%;           /* teal */
  --sidebar-text: 210 40% 92%;

  --canvas: #F6F8FB;
  --card: #FFFFFF;
  --border: rgba(15,23,42,0.10);
  --muted: rgba(15,23,42,0.55);
  --text: rgba(15,23,42,0.92);

  /* Risk tokens */
  --risk-low: 142 70% 33%;
  --risk-low-bg: 142 70% 95%;
  --risk-mod: 38 92% 45%;
  --risk-mod-bg: 38 92% 95%;
  --risk-high: 0 72% 45%;
  --risk-high-bg: 0 72% 95%;
}

/* App background */
.stApp { background: var(--canvas); }

/* Make main-page text always readable on the light canvas */
.stApp, .stMarkdown, .stMarkdown p, .stCaption, .stText, .stAlert, label,
h1, h2, h3, h4, h5, h6, div[data-testid="stMarkdownContainer"] {
  color: var(--text) !important;
}

/* Prevent page from looking cut */
div.block-container {
  padding-top: 2.2rem;
  padding-bottom: 2.2rem;
}

/* Typography feel */
html, body, [class*="css"] { letter-spacing: -0.01em; }

/* =========================
   Inputs (light themed)
   ========================= */
div[data-testid="stTextInput"] input,
div[data-testid="stTextArea"] textarea {
  background: #FFFFFF !important;
  color: var(--text) !important;
  border: 1px solid var(--border) !important;
  border-radius: 12px !important;
}

/* =========================
   Sidebar (dark navy)
   ========================= */
section[data-testid="stSidebar"]{
  background: hsl(var(--primary-2)) !important;
  border-right: 1px solid rgba(255,255,255,0.07);
  position: relative;
}

/* subtle top "tech line" like screenshot */
section[data-testid="stSidebar"]::before{
  content:"";
  position:absolute;
  left:0; top:0;
  width:100%; height:80px;
  background: linear-gradient(
    90deg,
    rgba(255,255,255,0.06),
    rgba(255,255,255,0.02),
    rgba(255,255,255,0.00)
  );
  opacity: 0.6;
  pointer-events:none;
}

section[data-testid="stSidebar"] *{
  color: hsl(var(--sidebar-text)) !important;
}
section[data-testid="stSidebar"] hr{
  border-color: rgba(255,255,255,0.10) !important;
}

/* Sidebar radio items */
section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] > label{
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 14px;
  padding: 10px 12px;
  margin-bottom: 8px;
}
section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] > label:hover{
  border-color: hsla(var(--accent), 0.55);
}

/* =========================
   Buttons
   ========================= */
.stButton>button{
  border-radius: 12px;
  border: 1px solid rgba(15,23,42,0.14);
}

/* Primary */
.stButton>button[kind="primary"]{
  background: hsl(var(--accent)) !important;
  border: 1px solid hsl(var(--accent)) !important;
  color: white !important;
}
.stButton>button[kind="primary"]:hover{
  filter: brightness(0.98);
}

/* Secondary */
.stButton>button[kind="secondary"]{
  background: #FFFFFF !important;
  color: var(--text) !important;
  border: 1px solid rgba(15,23,42,0.14) !important;
}
.stButton>button[kind="secondary"]:hover{
  background: rgba(15,23,42,0.04) !important;
}

/* Tertiary */
.stButton>button[kind="tertiary"]{
  color: var(--text) !important;
}

/* =========================
   Cards
   ========================= */
.mc-card{
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 16px 16px;
  box-shadow: none;
}
.mc-title{ font-weight: 800; font-size: 16px; margin-bottom: 2px; color: var(--text); }
.mc-sub{ color: var(--muted); font-size: 13px; margin-bottom: 0px; }

/* Metric layout */
.mc-metric-label{ color: var(--muted); font-size: 13px; margin-bottom: 6px; }
.mc-metric-value{ font-size: 30px; font-weight: 900; color: var(--text); line-height: 1.0; }
.mc-metric-foot{ margin-top: 6px; color: var(--muted); font-size: 12px; }
.mc-metric-row{ display:flex; justify-content:space-between; gap:12px; align-items:flex-start; }

/* =========================
   Pills / badges
   ========================= */
.risk-badge{
  display:inline-block;
  padding: 6px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 800;
  border: 1px solid rgba(15,23,42,0.08);
}
.risk-low{ background: hsl(var(--risk-low-bg)); color: hsl(var(--risk-low)); }
.risk-moderate{ background: hsl(var(--risk-mod-bg)); color: hsl(var(--risk-mod)); }
.risk-high{ background: hsl(var(--risk-high-bg)); color: hsl(var(--risk-high)); }

/* =========================
   Portal cards (Auth)
   ========================= */
.mc-portal{
  display:flex; gap:14px; align-items:center;
  padding:16px;
  border-radius:16px;
  border:1px solid var(--border);
  background:#FFFFFF;
}
.mc-portal:hover{ border-color: hsla(var(--accent), 0.55); }
.mc-portal-ico{
  width:42px; height:42px; border-radius:12px;
  background: hsla(var(--accent),0.12);
  display:flex; align-items:center; justify-content:center;
  font-weight: 900;
  color: hsl(var(--accent));
}
.mc-portal-title{ font-weight: 900; color: var(--text); }
.mc-portal-sub{ color: var(--muted); font-size: 13px; }

/* ============================================================
   File uploader fixes:
   - Keep dropzone instructions readable (dark bar)
   - Keep filename readable (white row)
   - Make browse button WHITE
   ============================================================ */

/* Uploaded file row */
div[data-testid="stFileUploaderFile"]{
  background: #FFFFFF !important;
  border: 1px solid rgba(15,23,42,0.10) !important;
  border-radius: 12px !important;
  opacity: 1 !important;
}
div[data-testid="stFileUploaderFileName"],
div[data-testid="stFileUploaderFileName"] *{
  color: rgba(15,23,42,0.92) !important;
  opacity: 1 !important;
}

/* Dropzone instructions text ("Drag and drop file here", limits, etc.) */
div[data-testid="stFileUploaderDropzoneInstructions"] * ,
div[data-testid="stFileUploaderDropzoneInstructions"] small{
  color: rgba(255,255,255,0.92) !important;
  opacity: 1 !important;
}

/* Browse button inside uploader (force white) */
div[data-testid="stFileUploader"] button{
  background: #FFFFFF !important;
  color: rgba(15,23,42,0.92) !important;
  border: 1px solid rgba(15,23,42,0.15) !important;
  border-radius: 10px !important;
}
div[data-testid="stFileUploader"] button:hover{
  background: #F3F4F6 !important;
}
</style>
        """,
        unsafe_allow_html=True,
    )


def _esc(x: str) -> str:
    """Escape any user/DB-provided strings before injecting into HTML."""
    return html.escape(str(x or ""), quote=True)


def card_open(title: str, subtitle: str = "") -> None:
    sub = f'<div class="mc-sub">{_esc(subtitle)}</div>' if subtitle else ""
    st.markdown(
        f'<div class="mc-card"><div class="mc-title">{_esc(title)}</div>{sub}',
        unsafe_allow_html=True,
    )


def card_close() -> None:
    st.markdown("</div>", unsafe_allow_html=True)


def risk_badge(level: str) -> str:
    lvl = (level or "").lower()
    if "high" in lvl:
        cls, txt = "risk-high", "High Risk"
    elif "mod" in lvl or "urgent" in lvl:
        cls, txt = "risk-moderate", "Moderate Risk"
    else:
        cls, txt = "risk-low", "Low Risk"
    return f'<span class="risk-badge {cls}">{txt}</span>'


def metric_card(label: str, value: str, foot: str | None = None) -> None:
    """
    IMPORTANT: metric_card renders plain text only (escaped).
    If you need HTML (e.g., risk_badge), render it *outside* the metric_card
    with st.markdown(..., unsafe_allow_html=True).
    """
    foot_html = f'<div class="mc-metric-foot">{_esc(foot)}</div>' if foot else ""
    st.markdown(
        f"""
<div class="mc-card">
  <div class="mc-metric-row">
    <div>
      <div class="mc-metric-label">{_esc(label)}</div>
      <div class="mc-metric-value">{_esc(value)}</div>
      {foot_html}
    </div>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )


def portal_choice(title: str, subtitle: str, icon_text: str = "•") -> None:
    st.markdown(
        f"""
<div class="mc-portal">
  <div class="mc-portal-ico">{_esc(icon_text)}</div>
  <div>
    <div class="mc-portal-title">{_esc(title)}</div>
    <div class="mc-portal-sub">{_esc(subtitle)}</div>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )

# -------------------------------------------------------------------
# Import unifier: force any `import ui` / `from ui import ...`
# to resolve to THIS module (app.ui), avoiding stale duplicate ui.py files.
# -------------------------------------------------------------------
sys.modules["ui"] = sys.modules[__name__]

