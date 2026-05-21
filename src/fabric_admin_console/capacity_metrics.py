"""
Fabric Capacity Metrics helpers.

Queries the Fabric Capacity Metrics semantic model through the Power BI Execute
Queries API and formats results for CLI usage.
"""

from __future__ import annotations

from datetime import datetime

import requests

CAPACITY_METRICS_DATASET_ID = "d3062af2-fbb1-42e0-9850-eada9c500aa6"
PBI_EXECUTE_QUERIES_URL = (
    f"https://api.powerbi.com/v1.0/myorg/datasets/{CAPACITY_METRICS_DATASET_ID}/executeQueries"
)

DAX_CAPACITY_INFO = "EVALUATE TOPN(1, Capacities)"
DAX_ALL_ITEMS = """
EVALUATE
SELECTCOLUMNS(
    Items,
    "ItemId", Items[ItemId],
    "ItemName", Items[ItemName],
    "ItemKind", Items[ItemKind],
    "Workspace", Items[WorkspaceName]
)
"""
DAX_CU_BY_WORKSPACE = """
EVALUATE
ADDCOLUMNS(
    SUMMARIZE(MetricsByItem, MetricsByItem[WorkspaceId]),
    "TotalCU", CALCULATE(SUM(MetricsByItem[sum_CU])),
    "TotalOps", CALCULATE(SUM(MetricsByItem[count_operations])),
    "Failures", CALCULATE(SUM(MetricsByItem[count_failure_operations])),
    "Throttling", CALCULATE(SUM(MetricsByItem[Throttling (min)])),
    "Workspace", LOOKUPVALUE(Items[WorkspaceName], Items[WorkspaceId], MetricsByItem[WorkspaceId])
)
"""
DAX_CU_BY_ITEM_KIND = """
EVALUATE
ADDCOLUMNS(
    SUMMARIZE(MetricsByItem, MetricsByItem[ArtifactKind]),
    "TotalCU", CALCULATE(SUM(MetricsByItem[sum_CU])),
    "TotalOps", CALCULATE(SUM(MetricsByItem[count_operations])),
    "Failures", CALCULATE(SUM(MetricsByItem[count_failure_operations])),
    "Throttling", CALCULATE(SUM(MetricsByItem[Throttling (min)]))
)
"""
DAX_TOP_ITEMS_BY_CU = """
EVALUATE
TOPN({limit},
    MetricsByItem,
    MetricsByItem[sum_CU], DESC
)
"""


def _execute_dax(token: str, query: str):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = {"queries": [{"query": query}], "serializerSettings": {"includeNulls": True}}
    try:
        response = requests.post(PBI_EXECUTE_QUERIES_URL, headers=headers, json=body, timeout=30)
        data = response.json()
        if "results" in data:
            return data["results"][0]["tables"][0].get("rows", [])
        return None
    except Exception:
        return None


def _col(row: dict, col_name: str):
    for key, value in row.items():
        if f"[{col_name}]" in key:
            return value
    return None


def _fmt_cu(value):
    if value is None:
        return "N/A"
    numeric = float(value)
    if numeric >= 1_000_000:
        return f"{numeric / 1_000_000:,.2f}M"
    if numeric >= 1_000:
        return f"{numeric / 1_000:,.1f}K"
    return f"{numeric:,.1f}"


def _fmt_num(value):
    if value is None:
        return "N/A"
    return f"{int(float(value)):,}"


def _pct(part, total):
    if not total or float(total) == 0:
        return 0.0
    return (float(part) / float(total)) * 100


def _bar(pct_val, width: int = 20):
    filled = int(round(pct_val / 100 * width))
    return "#" * filled + "-" * (width - filled)


def _summary_box_lines(total_cu, total_ops, total_fail, total_throttle):
    return [
        "  +-------------------------------------------------+",
        f"  |  Total CU (s):     {_fmt_cu(total_cu):>12}               |",
        f"  |  Total Operations: {_fmt_num(total_ops):>12}               |",
        f"  |  Total Failures:   {_fmt_num(total_fail):>12}  ({_pct(total_fail, total_ops):.1f}%)     |",
        f"  |  Throttling (min): {total_throttle:>12.1f}               |",
        "  +-------------------------------------------------+",
    ]


def _section(title: str):
    return "\n" + "=" * 70 + f"\n  {title}\n" + "=" * 70


def _build_item_lookup(token: str):
    rows = _execute_dax(token, DAX_ALL_ITEMS)
    if not rows:
        return {}
    lookup = {}
    for row in rows:
        item_id = _col(row, "ItemId")
        name = _col(row, "ItemName")
        kind = _col(row, "ItemKind")
        workspace = _col(row, "Workspace")
        if item_id and name:
            if item_id not in lookup or (not lookup[item_id]["name"] and name):
                lookup[item_id] = {"name": name, "kind": kind, "workspace": workspace}
    return lookup


def show_capacity_summary(token: str):
    print(_section("FABRIC CAPACITY METRICS SUMMARY"))

    cap_rows = _execute_dax(token, DAX_CAPACITY_INFO)
    if cap_rows:
        cap = cap_rows[0]
        sku = _col(cap, "sku") or _col(cap, "capacityPlan")
        region = _col(cap, "region")
        name = _col(cap, "Capacity Name")
        owners = _col(cap, "Owners")
        print(f"\n  Capacity:  {name} ({sku})")
        print(f"  Region:    {region}")
        print(f"  Owners:    {owners}")
        print(f"  Queried:   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    kind_rows = _execute_dax(token, DAX_CU_BY_ITEM_KIND)
    if kind_rows:
        total_cu = sum(float(_col(r, "TotalCU") or 0) for r in kind_rows)
        total_ops = sum(int(float(_col(r, "TotalOps") or 0)) for r in kind_rows)
        total_fail = sum(int(float(_col(r, "Failures") or 0)) for r in kind_rows)
        total_throttle = sum(float(_col(r, "Throttling") or 0) for r in kind_rows)
        for line in _summary_box_lines(total_cu, total_ops, total_fail, total_throttle):
            print(line)


def show_cu_by_workspace(token: str):
    print(_section("CAPACITY BY WORKSPACE"))
    rows = _execute_dax(token, DAX_CU_BY_WORKSPACE)
    if not rows:
        print("\n  No workspace usage rows returned.")
        return

    total_cu = sum(float(_col(r, "TotalCU") or 0) for r in rows)
    print("\n  Workspace             CU (s)         %      Ops   Fail   Usage")
    print("  ------------------------------------------------------------------")
    rows.sort(key=lambda r: float(_col(r, "TotalCU") or 0), reverse=True)
    for row in rows:
        workspace = _col(row, "Workspace") or "(unknown)"
        cu = float(_col(row, "TotalCU") or 0)
        ops = int(float(_col(row, "TotalOps") or 0))
        fail = int(float(_col(row, "Failures") or 0))
        pct = _pct(cu, total_cu)
        print(
            f"  {workspace:<20} {_fmt_cu(cu):>10}  {pct:>6.1f}%  {_fmt_num(ops):>7}  {_fmt_num(fail):>5}  {_bar(pct)}"
        )


def show_cu_by_item_kind(token: str):
    print(_section("CAPACITY BY ITEM TYPE"))
    rows = _execute_dax(token, DAX_CU_BY_ITEM_KIND)
    if not rows:
        print("\n  No item-type usage rows returned.")
        return

    total_cu = sum(float(_col(r, "TotalCU") or 0) for r in rows)
    print("\n  Item Type            CU (s)         %      Ops   Fail   Usage")
    print("  ------------------------------------------------------------------")
    rows.sort(key=lambda r: float(_col(r, "TotalCU") or 0), reverse=True)
    for row in rows:
        kind = _col(row, "ArtifactKind") or "(unknown)"
        cu = float(_col(row, "TotalCU") or 0)
        ops = int(float(_col(row, "TotalOps") or 0))
        fail = int(float(_col(r, "Failures") or 0)) if (r := row) else 0
        pct = _pct(cu, total_cu)
        print(
            f"  {kind:<20} {_fmt_cu(cu):>10}  {pct:>6.1f}%  {_fmt_num(ops):>7}  {_fmt_num(fail):>5}  {_bar(pct)}"
        )


def show_top_items(token: str, limit: int = 10):
    print(_section(f"TOP {limit} ITEMS BY CU"))
    item_lookup = _build_item_lookup(token)
    rows = _execute_dax(token, DAX_TOP_ITEMS_BY_CU.format(limit=limit))
    if not rows:
        print("\n  No top-item rows returned.")
        return

    rows.sort(key=lambda r: float(_col(r, "sum_CU") or 0), reverse=True)
    print("\n   #  Item Name                                Kind            CU (s)      Ops   Workspace")
    print("  ------------------------------------------------------------------------------------------")
    for index, row in enumerate(rows, 1):
        item_id = _col(row, "ItemId")
        kind = _col(row, "ArtifactKind") or "?"
        cu = float(_col(row, "sum_CU") or 0)
        ops = int(float(_col(row, "count_operations") or 0))
        info = item_lookup.get(item_id, {})
        name = info.get("name", item_id or "?")
        workspace = info.get("workspace", "?")
        if len(name) > 38:
            name = name[:35] + "..."
        print(f"  {index:>3}  {name:<38} {kind:<14} {_fmt_cu(cu):>8}  {_fmt_num(ops):>7}  {workspace}")


def show_all(token: str):
    show_capacity_summary(token)
    show_cu_by_workspace(token)
    show_cu_by_item_kind(token)
    show_top_items(token, limit=10)
