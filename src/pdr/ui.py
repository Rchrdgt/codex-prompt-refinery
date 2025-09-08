"""Streamlit UI per PRD."""

from __future__ import annotations

# Ensure 'pdr' is importable when executed directly via streamlit on script path.
import os
import sys

_THIS_DIR = os.path.dirname(__file__)
_SRC_DIR = os.path.abspath(os.path.join(_THIS_DIR, "..", ".."))
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

import streamlit as st  # noqa: E402

from pdr.db import connect, create_schema  # noqa: E402
from pdr.search import hybrid_search  # noqa: E402


def main() -> None:
    """Render Streamlit app."""
    st.set_page_config(page_title="codex-prompt-refinery", layout="wide")
    db_path = os.environ.get("PDR_DB", os.path.expanduser("~/.pdr.sqlite"))
    conn = connect(db_path)
    create_schema(conn)

    st.title("codex-prompt-refinery")
    query = st.text_input("Search", placeholder="keywords or natural language")

    tabs = st.tabs(["Raw", "Optimized"])
    results = {"raw": [], "optimized": []}
    if query:
        results = hybrid_search(conn, query, topn_fts=20, topk_vec=20)

    with tabs[0]:
        for r in results["raw"]:
            with st.container(border=True):
                st.markdown(f"**Raw #{r['id']}**")
                st.code(r["text"])
                _copy_and_download(r["text"], f"raw-{r['id']}.md")

    with tabs[1]:
        for r in results["optimized"]:
            with st.container(border=True):
                st.markdown(f"**Optimized #{r['id']}**")
                text = r["text"]
                st.code(text, language="markdown")
                spec = st.text_area(
                    "Specialize", key=f"spec-{r['id']}", placeholder="Add context or variables..."
                )
                preview = text + ("\n\n" + spec if spec else "")
                st.markdown("**Preview**")
                st.code(preview, language="markdown")
                _copy_and_download(preview, f"optimized-{r['id']}.md")


def _copy_and_download(text: str, filename: str) -> None:
    """Show copy and download controls."""
    try:
        from st_copy_to_clipboard import st_copy_to_clipboard  # type: ignore  # noqa: PLC0415

        st_copy_to_clipboard(text)
    except Exception:
        pass
    st.download_button(
        "Download .md", data=text.encode("utf-8"), file_name=filename, mime="text/markdown"
    )


if __name__ == "__main__":
    main()
