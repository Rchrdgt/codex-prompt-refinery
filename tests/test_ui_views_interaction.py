"""UI interaction tests for saved Views selection."""

import os

import pytest
from streamlit.testing.v1 import AppTest

from pdr.db import connect, create_schema, view_insert


@pytest.mark.skipif(AppTest is None, reason="streamlit testing API unavailable")
def test_select_saved_view_hydrates_filters(tmp_path):
    """Selecting a saved view from the sidebar should hydrate filters in session state.

    This verifies the fix where choosing a view updates `ui_filters_preload` and
    `ui_current_view_id` so that subsequent reruns render filters from that view.
    """
    # Prepare DB with one saved view
    db_path = tmp_path / "ui_views.sqlite"
    os.environ["PDR_DB"] = str(db_path)
    db = connect(str(db_path))
    create_schema(db)
    filters_json = '{"version": 1, "where": {"roles": ["assistant"]}}'
    vid = view_insert(
        db, name="MyView", scope="both", filters_json=filters_json, grid_state_json=None
    )

    # Launch app
    at = AppTest.from_file("src/pdr/ui.py").run(timeout=15)
    assert not at.exception

    # Find the "Load view" selectbox in the sidebar
    load_boxes = [sb for sb in at.sidebar.selectbox if getattr(sb, "label", "") == "Load view"]
    assert load_boxes, "Expected a 'Load view' selectbox in the sidebar"
    load_box = load_boxes[0]

    # Build expected option string and select it
    expected_option = f"{vid}: MyView (both)"
    assert expected_option in load_box.options
    load_box.select(expected_option).run(timeout=15)

    # After selection + rerun, the app should have hydrated session state
    assert at.session_state["ui_current_view_id"] == vid
    assert at.session_state["ui_filters_preload"] == {
        "version": 1,
        "where": {"roles": ["assistant"]},
    }
