from fabric_admin_console.capacity_metrics import (
    _bar,
    _build_item_lookup,
    _col,
    _fmt_cu,
    _fmt_num,
    _pct,
    _summary_box_lines,
    show_capacity_summary,
)


def test_fmt_cu_formats_ranges():
    assert _fmt_cu(None) == "N/A"
    assert _fmt_cu(500) == "500.0"
    assert _fmt_cu(12_500) == "12.5K"
    assert _fmt_cu(2_500_000) == "2.50M"


def test_fmt_num_and_pct():
    assert _fmt_num(1200) == "1,200"
    assert _pct(25, 100) == 25.0
    assert _pct(10, 0) == 0.0


def test_bar_and_column_lookup():
    assert _bar(50, width=10) == "#####-----"
    row = {"Items[ItemName]": "Pipeline A", "Foo[Bar]": 3}
    assert _col(row, "ItemName") == "Pipeline A"
    assert _col(row, "Missing") is None


def test_summary_box_lines_use_safe_ascii_rendering():
    lines = _summary_box_lines(1000, 10, 1, 0.0)
    assert lines[0].startswith("  +")
    assert "Total Operations" in lines[2]
    assert lines[-1].startswith("  +")


def test_build_item_lookup_uses_execute_dax(monkeypatch):
    monkeypatch.setattr(
        "fabric_admin_console.capacity_metrics._execute_dax",
        lambda token, query: [
            {
                "Items[ItemId]": "abc",
                "Items[ItemName]": "Dataset One",
                "Items[ItemKind]": "SemanticModel",
                "Items[WorkspaceName]": "Pilot",
            }
        ],
    )
    lookup = _build_item_lookup("token")
    assert lookup["abc"]["name"] == "Dataset One"


def test_show_capacity_summary_prints_capacity_overview(monkeypatch, capsys):
    def fake_execute(_token, query):
        if "TOPN(1, Capacities)" in query:
            return [
                {
                    "Capacities[Capacity Name]": "F64 Demo",
                    "Capacities[sku]": "F64",
                    "Capacities[region]": "Central US",
                    "Capacities[Owners]": "Ops Team",
                }
            ]
        return [
            {
                "MetricsByItem[ArtifactKind]": "Pipeline",
                "TotalCU": 1000,
                "TotalOps": 10,
                "Failures": 1,
                "Throttling": 0,
            }
        ]

    monkeypatch.setattr("fabric_admin_console.capacity_metrics._execute_dax", fake_execute)
    show_capacity_summary("token")
    out = capsys.readouterr().out
    assert "FABRIC CAPACITY METRICS SUMMARY" in out
    assert "F64 Demo" in out
