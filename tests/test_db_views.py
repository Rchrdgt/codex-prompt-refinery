from pdr.db import connect, create_schema, view_delete, view_get, view_insert, view_list


def test_ui_view_crud_ordering():
    """Saved views can be inserted, listed (most recent first), fetched, and deleted."""
    db = connect(":memory:")
    create_schema(db)

    v1 = view_insert(db, name="Alpha", scope="both", filters_json="{}", grid_state_json=None)
    v2 = view_insert(db, name="Beta", scope="raw", filters_json="{}", grid_state_json=None)
    assert isinstance(v1, int) and isinstance(v2, int)

    listed = view_list(db)
    assert listed and listed[0]["name"] in {"Alpha", "Beta"}

    got = view_get(db, v1)
    assert got and got["name"] == "Alpha" and got["scope"] == "both"

    view_delete(db, v1)
    assert view_get(db, v1) is None
