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
    return "█" * filled + "░" * (width - filled)


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
    print("\n" + "=" * 70)
    print("  FABRIC CAPACITY METRICS SUMMARY")
    print("=" * 70)

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
        print(f"\n  ┌─────────────────────────────────────────────────┐")
        print(f"  │  Total CU (s):     {_fmt_cu(total_cu):>12}                │")
        print(f"  │  Total Operations:  {_fmt_num(total_ops):>11}                │")
        print(f"  │  Total Failures:    {_fmt_num(total_fail):>11}  ({_pct(total_fail, total_ops):.1f}%)       │")
        print(f"  │  Throttling (min):  {total_throttle:>11.1f}                │")
        print("  └─────────────────────────────────────────────────┘")


def show_all(token: str):
    show_capacity_summary(token)
