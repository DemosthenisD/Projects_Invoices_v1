"""
Page — How to Use.

Renders docs/USER_MANUAL.md inside the app so there is a single source of truth.
Edit the manual, not this page. Supports search across every section.
"""
import sys
import os
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
from shared.ui import require_auth

require_auth()

st.title("How to Use")

_docs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "docs")
_manual_path = os.path.join(_docs_dir, "USER_MANUAL.md")


# ------------------------------------------------------------------
# Parse the manual into sections
# ------------------------------------------------------------------

def _split(text: str, marker: str) -> list[tuple[str, str]]:
    """Split text on lines starting with `marker` -> [(title, body)]."""
    parts: list[tuple[str, str]] = []
    title, buf = None, []
    for line in text.splitlines():
        if line.startswith(marker):
            if title is not None:
                parts.append((title, "\n".join(buf).strip()))
            title, buf = line[len(marker):].strip(), []
        elif title is not None:
            buf.append(line)
    if title is not None:
        parts.append((title, "\n".join(buf).strip()))
    return parts


def _clean(body: str) -> str:
    """Drop the '---' separators used between items in the manual."""
    return "\n".join(l for l in body.splitlines() if l.strip() != "---").strip()


def _page_order(title: str) -> float:
    m = re.match(r"(\d+)\.", title)
    if m:
        return int(m.group(1))
    return -2 if title.startswith("Home") else -1  # Home, then Generate Invoice, then 1..n


def _faq_items(body: str) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    q, ans = None, []
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("**") and s.endswith("**") and s.count("**") == 2:
            if q:
                items.append((q, "\n".join(ans).strip()))
            q, ans = s.strip("*"), []
        elif q:
            ans.append(line)
    if q:
        items.append((q, "\n".join(ans).strip()))
    return items


@st.cache_data
def _load(mtime: float):
    with open(_manual_path, encoding="utf-8") as f:
        text = f.read()
    top = dict(_split(text, "## "))
    how_to = [(t, _clean(b)) for t, b in _split(top.get("How To", ""), "### ")]
    pages = sorted(((t, _clean(b)) for t, b in _split(top.get("Pages", ""), "### ")),
                   key=lambda x: _page_order(x[0]))
    return {
        "intro": top.get("What This App Is For", ""),
        "How To": how_to,
        "Pages": pages,
        "FAQ": _faq_items(top.get("Frequently Asked Questions", "")),
        "Where to go": top.get("Where to Go for Each Edit", ""),
        "Key concepts": top.get("Key Concepts", ""),
    }


if not os.path.exists(_manual_path):
    st.error(f"User manual not found at {_manual_path}")
    st.stop()

doc = _load(os.path.getmtime(_manual_path))

# ------------------------------------------------------------------
# Downloads
# ------------------------------------------------------------------

_files = [("📄 User Manual", "USER_MANUAL.md"), ("📋 Release Notes", "RELEASE_NOTES.md"),
          ("⚙️ Technical Reference", "TECHNICAL.md")]
_cols = st.columns(3)
for _col, (_label, _name) in zip(_cols, _files):
    _p = os.path.join(_docs_dir, _name)
    if os.path.exists(_p):
        with open(_p, "rb") as _f:
            _col.download_button(_label, data=_f.read(), file_name=_name,
                                 mime="text/markdown", use_container_width=True)

st.caption("This page shows the User Manual. Download the files above for offline reading.")

query = st.text_input("🔎 Search the manual", placeholder="e.g. credit note, partial payment, backup, recurring…",
                      key="htu_search").strip().lower()


def _table_rows_matching(table_md: str, q: str) -> str:
    lines = table_md.strip().splitlines()
    head, rows = lines[:2], lines[2:]
    hits = [r for r in rows if q in r.lower()]
    return "\n".join(head + hits) if hits else ""


# ------------------------------------------------------------------
# Search results (flat, across all sections)
# ------------------------------------------------------------------

if query:
    n = 0
    for section in ("How To", "Pages", "FAQ"):
        hits = [(t, b) for t, b in doc[section] if query in t.lower() or query in b.lower()]
        for t, b in hits:
            n += 1
            with st.expander(f"**{t}**  ·  {section}", expanded=len(hits) <= 3):
                st.markdown(b)
    for label, key in (("Where to go", "Where to go"), ("Key concepts", "Key concepts")):
        rows = _table_rows_matching(doc[key], query)
        if rows:
            n += 1
            st.markdown(f"**{label}**")
            st.markdown(rows)
    if not n:
        st.info("No matches. Try a shorter or different word.")
    st.stop()

# ------------------------------------------------------------------
# Normal view
# ------------------------------------------------------------------

with st.expander("What this app is for", expanded=False):
    st.markdown(doc["intro"])

tab_how, tab_pages, tab_where, tab_terms, tab_faq = st.tabs(
    ["How To", "Pages", "Where to go", "Key concepts", "FAQ"]
)

with tab_how:
    st.caption("Step-by-step guides for common tasks. Click a guide to expand it.")
    for title, body in doc["How To"]:
        with st.expander(f"**{title}**"):
            st.markdown(body)

with tab_pages:
    st.caption("What each page does, in sidebar order.")
    for title, body in doc["Pages"]:
        with st.expander(f"**{title}**"):
            st.markdown(body)

with tab_where:
    st.markdown(doc["Where to go"])

with tab_terms:
    st.markdown(doc["Key concepts"])

with tab_faq:
    for q, a in doc["FAQ"]:
        with st.expander(f"**{q}**"):
            st.markdown(a)
