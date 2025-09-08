"""Streamlit UI per PRD."""
# ruff: noqa: PLR0915, PLR0912
# pylint: disable=too-many-statements

from __future__ import annotations

# Ensure 'pdr' is importable when executed directly via streamlit on script path.
import os
import sys

_THIS_DIR = os.path.dirname(__file__)
_SRC_DIR = os.path.abspath(os.path.join(_THIS_DIR, "..", ".."))
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

import json  # noqa: E402
from datetime import date, timedelta  # noqa: E402

import streamlit as st  # noqa: E402

from pdr.config import default_llm_model, get_settings, llm_client  # noqa: E402
from pdr.db import (  # noqa: E402
    connect,
    create_schema,
    view_delete,
    view_get,
    view_insert,
    view_list,
)
from pdr.search import hybrid_search  # noqa: E402


def main() -> None:  # pylint: disable=too-many-statements
    """Render Streamlit app."""
    st.set_page_config(page_title="codex-prompt-refinery", layout="wide")
    db_path = os.environ.get("PDR_DB", os.path.expanduser("~/.pdr.sqlite"))
    conn = connect(db_path)
    create_schema(conn)

    st.title("codex-prompt-refinery")
    _model_selector()
    # Saved Views + Filters
    view_id_from_url = _get_view_id_from_url()
    if view_id_from_url:
        _hydrate_filters_from_view(conn, view_id_from_url)

    query = st.text_input("Search", placeholder="keywords or natural language")
    filters = _filters_sidebar(conn)
    _views_sidebar(conn, filters)

    # Put Optimized first so it's the default active tab
    tabs = st.tabs(["Optimized", "Raw", "Table", "Charts"])
    results = {"raw": [], "optimized": []}
    if query.strip():
        results = hybrid_search(conn, query.strip(), topn_fts=20, topk_vec=20, filters=filters)
    else:
        # Recent items honoring filters
        results = _recent_filtered(conn, filters, limit=20)

    # Optimized tab first (default active)
    with tabs[0]:
        for r in results["optimized"]:
            with st.container(border=True):
                oid = int(r["id"])
                st.markdown(f"**Optimized #{oid}**")
                base_text = r["text"]
                st.code(base_text, language="markdown")
                _inline_copy_and_download(base_text, f"optimized-{oid}.md")

                # Specialize controls
                spec_key = f"spec-input-{oid}"
                out_key = f"spec-output-{oid}"
                c1, c2 = st.columns([3, 1])
                with c1:
                    spec = st.text_input(
                        "Specialize",
                        key=spec_key,
                        placeholder="Add context or variables to tailor this prompt...",
                    )
                with c2:
                    b1, b2 = st.columns([1, 1])
                    with b1:
                        gen_clicked = st.button("Generate", key=f"spec-generate-{oid}")
                    with b2:
                        reset_clicked = st.button("Reset", key=f"spec-reset-{oid}")
                    if reset_clicked:
                        st.session_state[out_key] = ""
                        st.session_state[spec_key] = ""
                    if gen_clicked:
                        if spec.strip():
                            with st.spinner("Specializing…"):
                                try:
                                    model_override = st.session_state.get("ui_model_override")
                                    specialized = _specialize_prompt(
                                        base_text, spec.strip(), model_override=model_override
                                    )
                                except Exception as exc:  # best-effort UI surface
                                    specialized = f"Error specializing prompt: {exc}"
                                st.session_state[out_key] = specialized
                        else:
                            st.session_state[out_key] = ""

                # Show specialized output only when present
                specialized = st.session_state.get(out_key, "")
                if specialized:
                    st.markdown("**Specialized**")
                    st.code(specialized, language="markdown")
                    _inline_copy_and_download(specialized, f"optimized-{oid}-specialized.md")

    # Raw tab second
    with tabs[1]:
        for r in results["raw"]:
            with st.container(border=True):
                rid = int(r["id"])
                st.markdown(f"**Raw #{rid}**")
                st.code(r["text"])  # quick plain-text view
                # Metadata + expandable raw record viewer
                details = _get_raw_details(conn, rid)
                meta = (
                    f"ts: {details.get('ts') or '-'} | session: {details.get('session_id') or '-'}"
                )
                st.caption(meta)

                with st.expander("Raw JSON", expanded=False):
                    raw_val = details.get("raw_json") or ""
                    # Pretty-print when JSON, otherwise show wrapped text
                    try:
                        parsed = json.loads(raw_val)
                        pretty = json.dumps(parsed, indent=2, ensure_ascii=False)
                        st.json(parsed)
                        _inline_copy_and_download(pretty, f"raw-{rid}.json")
                    except Exception:
                        st.text_area("Raw line", raw_val, height=200, disabled=True)
                        _inline_copy_and_download(raw_val, f"raw-{rid}.txt")

    # Table tab
    with tabs[2]:
        rows = []
        for r in results["optimized"]:
            rows.append({"id": int(r["id"]), "source": "optimized", "text": r["text"]})
        for r in results["raw"]:
            rows.append({"id": int(r["id"]), "source": "raw", "text": r["text"]})
        if rows:
            use_ag = os.environ.get("ENABLE_AGGRID") == "1"
            df_built = False
            if use_ag:
                try:
                    # Soft dependency: only used if available
                    import pandas as pd  # type: ignore  # noqa: PLC0415
                    from st_aggrid import (  # type: ignore  # noqa: PLC0415
                        AgGrid,
                        GridOptionsBuilder,
                    )

                    df = pd.DataFrame(rows)
                    gb = GridOptionsBuilder.from_dataframe(df)
                    gb.configure_pagination(enabled=True, paginationAutoPageSize=True)
                    AgGrid(df, gridOptions=gb.build())
                    df_built = True
                except Exception:
                    df_built = False
            if not df_built:
                # Native fallback
                # Minimal pretty print; avoid pandas dependency
                st.write(rows)
        else:
            st.caption("No rows to display.")

    # Charts tab (minimal, dependency-free)
    with tabs[3]:
        _charts_minimal(results)


def _inline_copy_and_download(text: str, filename: str) -> None:
    """Inline copy + download buttons to save vertical space."""
    c1, c2 = st.columns([1, 1])
    with c1:
        try:
            from st_copy_to_clipboard import st_copy_to_clipboard  # type: ignore  # noqa: PLC0415

            st_copy_to_clipboard(text)
        except Exception:
            st.button("Copy", key=f"copy-{hash(text) % 10_000_000}")
    with c2:
        st.download_button(
            "Download .md", data=text.encode("utf-8"), file_name=filename, mime="text/markdown"
        )


def _filters_sidebar(conn) -> dict:
    """Render sidebar filter controls and return a filter JSON-like dict (version 1).

    Defaults to last 30 days; empty lists mean no filter on that facet.
    """
    st.sidebar.markdown("### Filters")
    today = date.today()
    default_from = today - timedelta(days=30)
    preload = st.session_state.get("ui_filters_preload") or {}
    p_where = preload.get("where") or {}
    p_ts = p_where.get("ts") or {}
    try:
        p_from = date.fromisoformat(p_ts.get("from", "")) if p_ts.get("from") else default_from
        p_to = date.fromisoformat(p_ts.get("to", "")) if p_ts.get("to") else today
    except Exception:
        p_from, p_to = default_from, today
    dr = st.sidebar.date_input("Date range", (p_from, p_to))
    # Populate sessions (recent)
    sess_rows = conn.execute(
        "SELECT DISTINCT session_id FROM prompt_raw "
        "WHERE session_id IS NOT NULL ORDER BY id DESC LIMIT 200"
    ).fetchall()
    sessions_all = [r["session_id"] for r in sess_rows if r["session_id"]]
    sessions_default = p_where.get("sessions") or []
    sessions = st.sidebar.multiselect("Sessions", options=sessions_all, default=sessions_default)
    roles_default = p_where.get("roles") or ["user"]
    kinds_default = p_where.get("kind") or []
    roles = st.sidebar.multiselect(
        "Roles", options=["user", "assistant", "system"], default=roles_default
    )
    kinds = st.sidebar.multiselect(
        "Kind (optimized)", options=["atomic", "workflow"], default=kinds_default
    )

    _PAIR_LEN = 2
    f: dict = {
        "version": 1,
        "tab": "both",
        "query": "",
        "where": {
            "ts": {
                "from": dr[0].isoformat()
                if isinstance(dr, tuple) and len(dr) == _PAIR_LEN
                else default_from.isoformat(),
                "to": dr[1].isoformat()
                if isinstance(dr, tuple) and len(dr) == _PAIR_LEN
                else today.isoformat(),
            },
            "roles": roles,
            "sessions": sessions,
            "kind": kinds,
        },
        "sort": [{"field": "ts", "dir": "desc"}],
        "columns": ["id", "ts", "session_id"],
    }
    return f


def _views_sidebar(conn, filters: dict) -> int | None:  # returns current view id or None
    st.sidebar.markdown("### Views")
    views = view_list(conn)
    options = [f"{v['id']}: {v['name']} ({v['scope']})" for v in views]
    current = st.session_state.get("ui_current_view_id")
    index = 0
    if current:
        for i, v in enumerate(views):
            if int(v["id"]) == int(current):
                index = i
                break
    choice = st.sidebar.selectbox(
        "Load view", options=options or ["-"], index=index if options else 0
    )
    if options:
        chosen_id = int(choice.split(":", 1)[0])
        if chosen_id != current:
            st.session_state["ui_current_view_id"] = chosen_id
    # Save
    name = st.sidebar.text_input("View name")
    cols = st.sidebar.columns(3)
    with cols[0]:
        if st.button("Save") and name.strip():
            try:
                view_id = view_insert(conn, name.strip(), "both", json.dumps(filters), None)
                st.session_state["ui_current_view_id"] = view_id
                _set_query_param_view(view_id)
                st.sidebar.success("Saved")
            except Exception as exc:  # pragma: no cover - UI surface
                st.sidebar.error(f"Save failed: {exc}")
    with cols[1]:
        if st.button("Delete") and options:
            vid = st.session_state.get("ui_current_view_id")
            if vid:
                view_delete(conn, int(vid))
                st.session_state["ui_current_view_id"] = None
                _set_query_param_view(None)
                st.sidebar.success("Deleted")
    with cols[2]:
        if st.button("Share"):
            vid = st.session_state.get("ui_current_view_id")
            if vid:
                st.sidebar.code(_encode_view_url(int(vid)))
            else:
                st.sidebar.info("Save a view first")
    return st.session_state.get("ui_current_view_id")


def _get_view_id_from_url() -> int | None:
    params = st.experimental_get_query_params()
    val = params.get("view", [None])[0]
    try:
        return int(val) if val is not None else None
    except Exception:
        return None


def _set_query_param_view(view_id: int | None) -> None:
    if view_id is None:
        st.experimental_set_query_params()
    else:
        st.experimental_set_query_params(view=str(view_id))


def _encode_view_url(view_id: int) -> str:
    base = os.environ.get("PUBLIC_BASE_URL", "")
    if base:
        sep = "&" if "?" in base else "?"
        return f"{base}{sep}view={view_id}"
    # Fallback: relative URL
    return f"?view={view_id}"


def _hydrate_filters_from_view(conn, view_id: int) -> None:
    data = view_get(conn, view_id)
    if not data:
        return
    try:
        filters = json.loads(data["filters_json"]) if data.get("filters_json") else {}
    except Exception:
        filters = {}
    # Best-effort: store in session for sidebar to display defaults next rerun
    st.session_state["ui_filters_preload"] = filters
    st.session_state["ui_current_view_id"] = view_id


def _recent_filtered(conn, filters: dict, limit: int = 20) -> dict[str, list[dict]]:
    """Return recent rows honoring filters for both raw and optimized."""
    out = {"raw": [], "optimized": []}
    w = (filters or {}).get("where") or {}
    ts = w.get("ts") or {}
    roles = w.get("roles") or []
    sessions = w.get("sessions") or []
    kinds = w.get("kind") or []

    # Raw
    where = ["1=1"]
    params: list = []
    if ts.get("from"):
        where.append("ts >= ?")
        params.append(ts["from"])
    if ts.get("to"):
        where.append("ts <= ?")
        params.append(ts["to"])
    if roles:
        where.append("role IN (" + ",".join(["?"] * len(roles)) + ")")
        params.extend(list(roles))
    if sessions:
        where.append("session_id IN (" + ",".join(["?"] * len(sessions)) + ")")
        params.extend(list(sessions))
    sql = (
        "SELECT id, text FROM prompt_raw WHERE " + " AND ".join(where) + " ORDER BY id DESC LIMIT ?"
    )
    rows = conn.execute(sql, (*params, limit)).fetchall()
    out["raw"] = [{"id": int(r["id"]), "text": r["text"], "score": 1.0} for r in rows]

    # Optimized
    where_o = ["1=1"]
    params_o: list = []
    if ts.get("from"):
        where_o.append("created_at >= ?")
        params_o.append(ts["from"])
    if ts.get("to"):
        where_o.append("created_at <= ?")
        params_o.append(ts["to"])
    if kinds:
        where_o.append("kind IN (" + ",".join(["?"] * len(kinds)) + ")")
        params_o.extend(list(kinds))
    sql_o = (
        "SELECT id, text_md AS text FROM prompt_optimized WHERE "
        + " AND ".join(where_o)
        + " ORDER BY id DESC LIMIT ?"
    )
    rows_o = conn.execute(sql_o, (*params_o, limit)).fetchall()
    out["optimized"] = [{"id": int(r["id"]), "text": r["text"], "score": 1.0} for r in rows_o]
    return out


def _charts_minimal(results: dict[str, list[dict]]) -> None:
    """Render minimal charts without external deps.

    Shows simple counts by source and a naive per-20 items line for recency.
    """
    counts = {"optimized": len(results.get("optimized", [])), "raw": len(results.get("raw", []))}
    st.write("Counts by source:", counts)


def _get_raw_details(conn, rid: int) -> dict:
    r = conn.execute(
        """
        SELECT id, role, ts, session_id, conversation_id, source_path, raw_json
        FROM prompt_raw WHERE id=?
        """,
        (rid,),
    ).fetchone()
    if not r:
        return {}
    return dict(r)


def _specialize_prompt(
    base_markdown: str, specialization: str, model_override: str | None = None
) -> str:
    """Call the configured LLM to specialize an optimized prompt with context.

    Returns a markdown string. Keeps variables and intended IO where possible.
    """
    settings = get_settings()
    client = llm_client(settings)
    model = model_override or default_llm_model(settings)
    system = (
        "You are a senior prompt engineer. Take the optimized prompt and the user's"
        " specialization notes, and produce a refined, specialized prompt in Markdown."
        " Preserve the original structure, variables, and IO contract where applicable."
    )
    user = (
        "<optimized_prompt>\n"
        + base_markdown
        + "\n</optimized_prompt>\n"
        + "<specialization>\n"
        + specialization
        + "\n</specialization>\n"
        + "Return only the specialized prompt Markdown, nothing else."
    )
    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
        )
    except Exception:
        # Provider/model mismatch fallback for Cerebras envs accidentally set to OpenAI models
        if settings.llm_provider == "cerebras":
            fallback_model = "qwen-3-coder-480b"
            completion = client.chat.completions.create(
                model=fallback_model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.2,
            )
        else:
            raise
    return completion.choices[0].message.content or ""


def _model_selector() -> None:
    """Global model selector for specialization calls.

    Stores selection in st.session_state['ui_model_override'].
    """
    settings = get_settings()
    default_model = default_llm_model(settings)
    st.sidebar.markdown("### Model")
    options = [
        f"Auto ({default_model})",
        "gpt-5-mini",
        "gpt-5",
        "qwen-3-coder-480b",
    ]
    current = st.session_state.get("ui_model_override")
    initial = 0 if current is None else options.index(current) if current in options else 0
    choice = st.sidebar.selectbox("Specialize with model", options, index=initial)
    if choice.startswith("Auto ("):
        st.session_state["ui_model_override"] = None
    else:
        st.session_state["ui_model_override"] = choice
    custom = st.sidebar.text_input("Custom model id (optional)")
    if custom.strip():
        st.session_state["ui_model_override"] = custom.strip()


if __name__ == "__main__":
    main()
