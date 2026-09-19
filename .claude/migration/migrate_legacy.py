"""One-off migration of the legacy (Flask-era) component database into Onyks Bloodstone.

Categories, manufacturers and the LCSC supplier are created through the REST API, so the
backend rebuilds its views and applies its own validation. Elements are inserted with
SQL in a single transaction, because the API cannot preserve the original UUIDs (the
datasheet PDFs are named after them) nor the original creation dates.

Usage: python3 migrate.py <backup_data.sql> <api base url> [--dry-run]
Prints the SQL for elements to stdout; the caller pipes it into psql.
"""
import json
import re
import sys
import urllib.request
from collections import Counter

dump_path, api, *flags = sys.argv[1:]
dry_run = "--dry-run" in flags

# Legacy manufacturer_part_name held LCSC order codes, never real MPNs.
SUPPLIER = "LCSC"

# Typos / inconsistent casing in the legacy data, applied after stripping whitespace.
MANUFACTURER_FIXES = {
    "STMicroeletronics": "STMicroelectronics",
    "texas Instruments": "Texas Instruments",
}

TIMEZONE = "Europe/Warsaw"  # legacy created_at was stored without a time zone


def log(*args):
    print(*args, file=sys.stderr)


def unescape_copy(value):
    """Decodes a field of PostgreSQL's COPY text format."""
    if value == r"\N":
        return None
    return re.sub(r"\\(.)", lambda m: {"t": "\t", "n": "\n", "r": "\r", "\\": "\\"}.get(m.group(1), m.group(1)), value)


def read_dump(path):
    rows, table, columns = [], None, None
    for line in open(path, encoding="utf-8"):
        line = line.rstrip("\n")
        match = re.match(r'COPY public\."([^"]+)" \((.*)\) FROM stdin;', line)
        if match:
            table, columns = match.group(1), [c.strip() for c in match.group(2).split(",")]
            continue
        if line == r"\.":
            table = None
            continue
        if table is not None:
            rows.append((table, dict(zip(columns, map(unescape_copy, line.split("\t"))))))
    tables = re.findall(r'^CREATE TABLE public\."([^"]+)"', open(path, encoding="utf-8").read(), re.M)
    return tables, rows


def clean(value):
    """Blank -> NULL, the way the web GUI stores an unfilled field."""
    if value is None:
        return None
    value = value.strip()
    return value or None


def manufacturer_name(raw):
    name = clean(raw)
    return MANUFACTURER_FIXES.get(name, name) if name else None


def call(method, path, body=None):
    request = urllib.request.Request(
        api + path, method=method,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read() or "null")


def sql(value):
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "true" if value else "false"
    return "'" + str(value).replace("'", "''") + "'"


tables, rows = read_dump(dump_path)
log(f"dump: {len(tables)} categories, {len(rows)} elements")

# Checks mirroring schemas.ElementBase, so that every migrated element can later be
# opened and saved in the GUI without a validation error.
problems = []
for table, row in rows:
    part = clean(row["part_name"]) or ""
    if not 3 <= len(part) <= 256:
        problems.append(f"{table}/{part!r}: part_name length {len(part)}")
    for field in ("description", "value", "availability"):
        if len(clean(row[field]) or "") > 256:
            problems.append(f"{table}/{part!r}: {field} longer than 256")
if problems:
    log("VALIDATION PROBLEMS:", *problems, sep="\n  ")
    sys.exit(1)

manufacturers = sorted({m for m in (manufacturer_name(r["manufacturer"]) for _, r in rows) if m}, key=str.lower)
raw = Counter(r["manufacturer"] for _, r in rows if clean(r["manufacturer"]))
merged = {name: sorted({k for k in raw if manufacturer_name(k) == name}) for name in manufacturers}
for name, sources in merged.items():
    if sources != [name]:
        log(f"  manufacturer {name!r} <- {sources}")
log(f"manufacturers: {len(raw)} raw spellings -> {len(manufacturers)} entries")

if dry_run:
    sys.exit(0)

for name in tables:
    call("POST", "/table/create", {"name": name})
for name in manufacturers:
    call("POST", "/manufacturer/create", {"name": name})
supplier_id = call("POST", "/supplier/create", {"name": SUPPLIER})["id"]
log(f"created {len(tables)} categories, {len(manufacturers)} manufacturers, supplier {SUPPLIER} id={supplier_id}")

print("BEGIN;")
for table, row in rows:
    code = clean(row["manufacturer_part_name"])
    suppliers = {str(supplier_id): code} if code else {}
    values = [
        row["uuid"], clean(row["part_name"]), manufacturer_name(row["manufacturer"]), table,
        clean(row["description"]), clean(row["value"]), clean(row["availability"]),
        row["datasheet"] == "t",
        clean(row["library_ref"]), clean(row["library_path"]),
        clean(row["footprint_ref_1"]), clean(row["footprint_path_1"]),
        clean(row["footprint_ref_2"]), clean(row["footprint_path_2"]),
        clean(row["footprint_ref_3"]), clean(row["footprint_path_3"]),
    ]
    print(
        "INSERT INTO private.elements (uuid, part_name, manufacturer, \"table\", description, value, "
        "availability, datasheet, library_ref, library_path, footprint_reference_1, footprint_path_1, "
        "footprint_reference_2, footprint_path_2, footprint_reference_3, footprint_path_3, suppliers, "
        "docs_count, created_at) VALUES ("
        + ", ".join(sql(v) for v in values)
        + f", {sql(json.dumps(suppliers))}::jsonb, 0, "
        + f"{sql(row['created_at'])}::timestamp AT TIME ZONE '{TIMEZONE}');"
    )
print("COMMIT;")
log(f"generated SQL for {len(rows)} elements")
