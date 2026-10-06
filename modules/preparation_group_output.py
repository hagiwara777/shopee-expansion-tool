"""Shared CSV/TXT formatting only; callers retain market-specific eligibility."""

import csv
from io import StringIO


PREPARATION_GROUP_COLUMNS = (
    "marketplace", "group_key", "category_id", "category_path", "brand_id", "brand_name",
    "mandatory_attribute_count", "verification_status", "listing_ready", "asin_count", "asin",
)


def format_preparation_groups(rows, *, extra_columns=(), unknown_attribute_text="0"):
    """Preserve insertion order and one ASIN per CSV row; never decide readiness."""
    groups = {}
    for row in rows:
        groups.setdefault(row["group_key"], []).append(row)
    columns = (*PREPARATION_GROUP_COLUMNS, *extra_columns)
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=columns, lineterminator="\n", extrasaction="ignore")
    writer.writeheader()
    blocks = []
    for items in groups.values():
        first = items[0]
        for row in items:
            values = {**row, "asin_count": len(items), "verification_status": first["verification_status"]}
            safe = {}
            for column in columns:
                value = values.get(column, "")
                text = "" if value is None else str(value)
                safe[column] = f"'{text}" if text.startswith(("=", "+", "-", "@")) else text
            writer.writerow(safe)
        count = first["mandatory_attribute_count"]
        blocks.append("\n".join((
            f"［{first['marketplace']} / {first['category_path']} / {first['brand_name']}］",
            f"Category ID: {first['category_id']}",
            f"Brand ID: {first['brand_id']}",
            f"Mandatory attributes: {unknown_attribute_text if count is None else count}",
            f"ASIN count: {len(items)}", "", *(row["asin"] for row in items),
        )))
    return output.getvalue().encode("utf-8-sig"), "\n\n".join(blocks)
