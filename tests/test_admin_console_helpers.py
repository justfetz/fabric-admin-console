from fabric_admin_console.admin_console import (
    extract_folder_fields,
    normalize_path,
    pick_from_list,
    resolve_best_path,
    safe_values,
)


def test_safe_values_handles_dict_and_list():
    assert safe_values({"value": [1, 2]}) == [1, 2]
    assert safe_values([3, 4]) == [3, 4]
    assert safe_values("bad") == []


def test_normalize_path_collapses_slashes_and_case():
    assert normalize_path(r" /Folder\\Sub//Path ") == "/folder/sub/path"


def test_extract_folder_fields_finds_nested_metadata():
    item = {
        "displayName": "Example",
        "metadata": {"folder": {"id": "abc", "path": "/Ops/Shared"}},
    }
    fields = extract_folder_fields(item)
    assert fields["metadata.folder.id"] == "abc"
    assert resolve_best_path(fields) == "/Ops/Shared"


def test_pick_from_list_selects_expected_item(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "2")
    result = pick_from_list(
        [{"name": "alpha"}, {"name": "beta"}],
        lambda item: item["name"],
        "Choose item",
    )
    assert result == {"name": "beta"}
