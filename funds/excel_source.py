"""Read the dashboard data straight from "Main data file.xlsx".

The workbook's "main data" sheet holds two tables, each starting with a header row whose
first cell is "Country":

  1st table  real estate fund total assets, EUR million (rows like "Austria (AT)")
  2nd table  GDP at current prices, EUR million     (rows like "Austria")

Column headers are years ("2008" ... "2025") or a latest-quarter column such as "Jun 2026",
"Q2 2026" or "2026-Q2". Any further "Country" tables (e.g. a ratio table) are ignored: the
share of GDP is calculated here.

Only the Python standard library is used. Values are the ones Excel saved with the file, so
the dashboard picks up a change as soon as the workbook is saved (Ctrl+S).
"""

import re
import threading
import xml.etree.ElementTree as ET
import zipfile
from datetime import date, timedelta
from pathlib import Path

from django.conf import settings

SHEET_NAME = "main data"
START_YEAR = 2008  # timeline starts here; earlier columns are ignored

NS = {
    "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pr": "http://schemas.openxmlformats.org/package/2006/relationships",
}

# Fallback when a country row has no "(XX)" code.
NAME_TO_ISO = {
    "austria": "AT", "belgium": "BE", "bulgaria": "BG", "croatia": "HR", "cyprus": "CY",
    "czechia": "CZ", "czech republic": "CZ", "denmark": "DK", "estonia": "EE", "finland": "FI",
    "france": "FR", "germany": "DE", "greece": "GR", "hungary": "HU", "ireland": "IE",
    "italy": "IT", "latvia": "LV", "lithuania": "LT", "luxembourg": "LU", "malta": "MT",
    "netherlands": "NL", "norway": "NO", "poland": "PL", "portugal": "PT", "romania": "RO",
    "slovakia": "SK", "slovenia": "SI", "spain": "ES", "sweden": "SE", "switzerland": "CH",
    "united kingdom": "GB", "iceland": "IS", "euro area": "U2",
}
CODE_FIX = {"EL": "GR", "UK": "GB"}

# Euro area line: year each country adopted the euro (changing composition, as in the ECB's U2).
EURO_ADOPTION = {
    "AT": 1999, "BE": 1999, "DE": 1999, "ES": 1999, "FI": 1999, "FR": 1999, "IE": 1999,
    "IT": 1999, "LU": 1999, "NL": 1999, "PT": 1999, "GR": 2001, "SI": 2007, "CY": 2008,
    "MT": 2008, "SK": 2009, "EE": 2011, "LV": 2014, "LT": 2015, "HR": 2023, "BG": 2026,
}
EURO_AREA_EXCLUDE = {"LU"}  # left out of the average, as on the map
EURO_AREA_CODE = "U2"
MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def data_file():
    return Path(getattr(settings, "MAIN_DATA_FILE", Path(settings.BASE_DIR) / "Main data file.xlsx"))


# --- Minimal xlsx reader ------------------------------------------------------------

def _col_index(ref):
    n = 0
    for ch in re.match(r"[A-Z]+", ref).group():
        n = n * 26 + ord(ch) - 64
    return n - 1


def read_sheet(path, sheet_name):
    """Return the sheet as a list of rows (lists of str/float/None), using cached values."""
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.findall("m:si", NS):
                shared.append("".join(t.text or "" for t in si.iter(f"{{{NS['m']}}}t")))

        wb = ET.fromstring(z.read("xl/workbook.xml"))
        rid = None
        for s in wb.find("m:sheets", NS):
            if s.get("name", "").strip().lower() == sheet_name.lower():
                rid = s.get(f"{{{NS['r']}}}id")
        if rid is None:
            raise ValueError(f'Sheet "{sheet_name}" not found in {path.name}')
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        target = next(r.get("Target") for r in rels if r.get("Id") == rid)
        target = target.lstrip("/")
        if not target.startswith("xl/"):
            target = "xl/" + target

        root = ET.fromstring(z.read(target))
        rows = {}
        for row in root.iter(f"{{{NS['m']}}}row"):
            r = int(row.get("r")) - 1
            cells = rows.setdefault(r, {})
            for c in row.findall("m:c", NS):
                t = c.get("t")
                v = c.find("m:v", NS)
                if t == "inlineStr":
                    val = "".join(x.text or "" for x in c.iter(f"{{{NS['m']}}}t"))
                elif v is None or v.text is None:
                    val = None
                elif t == "s":
                    val = shared[int(v.text)]
                elif t in ("str", "e"):
                    val = v.text
                elif t == "b":
                    val = v.text == "1"
                else:
                    val = float(v.text)
                cells[_col_index(c.get("r"))] = val
        if not rows:
            return []
        width = max((max(c) + 1 for c in rows.values() if c), default=0)
        return [[rows.get(i, {}).get(j) for j in range(width)] for i in range(max(rows) + 1)]


# --- Interpreting the sheet ------------------------------------------------------------

def to_number(v):
    """'308167' / 308167.0 -> float; '', ':', '#VALUE!' -> None."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(" ", "").replace(" ", "")
    if not s:
        return None
    if "," in s and "." not in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def parse_period(h):
    """Column header -> (year, quarter) or None. 2008 / '2008' -> (2008, 4)."""
    if h is None:
        return None
    if isinstance(h, float):
        if 1900 <= h <= 2100:
            return int(h), 4
        if 20000 < h < 80000:  # Excel date serial, e.g. a header typed as a date
            d = date(1899, 12, 30) + timedelta(days=int(h))
            return d.year, (d.month - 1) // 3 + 1
        return None
    s = str(h).strip()
    if re.fullmatch(r"(19|20)\d\d", s):
        return int(s), 4
    m = re.fullmatch(r"([A-Za-z]{3})[a-z]*\.?\s+((?:19|20)\d\d)", s)  # Jun 2026 / June 2026
    if m and m.group(1).lower() in MONTHS:
        return int(m.group(2)), (MONTHS[m.group(1).lower()] - 1) // 3 + 1
    m = re.fullmatch(r"Q([1-4])\s*[-/ ]?\s*((?:19|20)\d\d)", s, re.I) or None
    if m:
        return int(m.group(2)), int(m.group(1))
    m = re.fullmatch(r"((?:19|20)\d\d)\s*[-/ ]?\s*Q([1-4])", s, re.I)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None


def split_name(label):
    """'Austria (AT)' -> ('Austria', 'AT'); 'Austria' -> ('Austria', 'AT' via lookup)."""
    s = str(label).strip()
    m = re.fullmatch(r"(.*?)\s*\(([A-Za-z]{2})\)", s)
    if m:
        name, code = m.group(1).strip(), m.group(2).upper()
    else:
        name, code = s, NAME_TO_ISO.get(s.lower())
    return name, CODE_FIX.get(code, code)


def classify(rows, header_index):
    """Name a table from the text in the few rows above its 'Country' header."""
    text = " ".join(str(c or "") for k in range(max(0, header_index - 5), header_index)
                    for c in rows[k][:3]).lower()
    if "combined" in text:
        return "combined"
    if "listed" in text and "eur million" in text:
        return "listed"
    if "usd" in text:
        return "listed_usd"
    if "share of gdp" in text:
        return "ratio"
    if "gross domestic product" in text:
        return "gdp"
    if "total assets of real estate funds" in text:
        return "funds"
    return None


def find_tables(rows):
    """Return [(kind, columns, data_rows)] for every block whose header cell in column A is 'Country'."""
    tables = []
    i = 0
    while i < len(rows):
        if str(rows[i][0] or "").strip().lower() == "country":
            kind = classify(rows, i)
            header = rows[i]
            cols = {}
            for j, h in enumerate(header):
                p = parse_period(h)
                if p and p[0] >= START_YEAR:
                    cols[j] = p
            body = []
            i += 1
            while i < len(rows) and rows[i] and str(rows[i][0] or "").strip():
                if str(rows[i][0]).strip().lower() == "country":
                    break
                body.append(rows[i])
                i += 1
            tables.append((kind, cols, body))
            continue
        i += 1
    return tables


def table_values(cols, body):
    """-> {code: {"name", "source", "values": {(year, q): number}}}"""
    out = {}
    for row in body:
        name, code = split_name(row[0])
        if not code:
            continue
        vals = {}
        for j, p in cols.items():
            n = to_number(row[j] if j < len(row) else None)
            if n is not None:
                vals[p] = n
        source = str(row[1]).strip() if len(row) > 1 and row[1] else ""
        out[code] = {"name": name, "source": source, "values": vals}
    return out


def build(rows):
    tables = find_tables(rows)
    if len(tables) < 2:
        raise ValueError('Expected two tables with a "Country" header (assets, then GDP) on the sheet')
    by_kind = {}
    for kind, cols, body in tables:
        if kind and kind not in by_kind:
            by_kind[kind] = (cols, body)
    # Fall back to sheet order (funds first, GDP second) when titles are missing.
    funds_t = by_kind.get("funds") or tables[0][1:]
    gdp_t = by_kind.get("gdp") or tables[1][1:]
    assets = table_values(*funds_t)
    gdp = table_values(*gdp_t)
    listed = table_values(*by_kind["listed"]) if "listed" in by_kind else {}
    combined_tbl = table_values(*by_kind["combined"]) if "combined" in by_kind else {}

    countries, years = {}, set()
    for code, a in assets.items():
        g = gdp.get(code, {"values": {}, "source": ""})
        # GDP is annual: keep the full-year (Q4-keyed) figure per year.
        gdp_by_year = {y: v for (y, q), v in g["values"].items()}

        # For each year keep the latest period: the Q4 (year-end) column if there is one,
        # otherwise the latest quarter (partial year).
        per_year = {}
        for (y, q), v in a["values"].items():
            if y not in per_year or q > per_year[y][0]:
                per_year[y] = (q, v)

        values = {}
        for y, (q, v) in sorted(per_year.items()):
            partial = q != 4
            gdp_year = y if y in gdp_by_year else None
            # Only a partial (current) year may borrow GDP, and only the previous year's.
            if gdp_year is None and partial and (y - 1) in gdp_by_year:
                gdp_year = y - 1
            gdp_val = gdp_by_year.get(gdp_year) if gdp_year else None
            share = round(v / gdp_val * 100, 3) if gdp_val else None
            values[str(y)] = {
                "share": share, "assets": round(v, 1),
                "gdp": round(gdp_val, 1) if gdp_val else None, "gdp_year": gdp_year,
                "period": f"{y}-Q{q}", "partial": partial,
            }
            years.add(y)
        countries[code] = {
            "name": a["name"], "values": values,
            "asset_source": a["source"], "gdp_source": g["source"],
        }
    countries[EURO_AREA_CODE] = euro_area(countries, sorted(years))
    out = {"years": sorted(years), "countries": countries}
    if listed:
        out["combined"] = build_combined(assets, listed, combined_tbl, gdp)
    return out


def build_combined(assets, listed, combined_tbl, gdp):
    """Funds (total assets) + listed real estate (EPRA, EUR m), % of GDP.

    Only years with a listed real estate figure are included. The combined value comes from the
    workbook's combined table when present (so edits there show up), otherwise it is calculated.
    """
    countries, years = {}, set()
    for code, l in listed.items():
        g = {y: v for (y, q), v in gdp.get(code, {"values": {}})["values"].items()}
        f_vals = assets.get(code, {"values": {}})["values"]
        c_vals = combined_tbl.get(code, {"values": {}})["values"]
        values = {}
        for (y, q), lv in sorted(l["values"].items()):
            fv = f_vals.get((y, q))
            total = c_vals.get((y, q), (fv or 0.0) + lv)
            gv = g.get(y)
            values[str(y)] = {
                "share": round(total / gv * 100, 3) if gv else None,
                "assets": round(total, 1), "funds": round(fv, 1) if fv is not None else None,
                "listed": round(lv, 1), "gdp": round(gv, 1) if gv else None, "gdp_year": y if gv else None,
                "period": f"{y}-Q{q}", "partial": q != 4,
            }
            years.add(y)
        if values:
            a = assets.get(code, {})
            countries[code] = {"name": l["name"], "values": values,
                               "asset_source": a.get("source", ""), "listed_source": l["source"]}
    countries[EURO_AREA_CODE] = euro_area(countries, sorted(years))
    return {"years": sorted(years), "countries": countries}


def euro_area(countries, years):
    """Weighted euro area average: sum of fund assets / sum of GDP of the members that year.

    Only members with both an asset value and a GDP value that year are counted; the others are
    listed in "missing" so the page can say so.
    """
    values = {}
    for y in years:
        members = sorted(c for c, since in EURO_ADOPTION.items() if since <= y and c not in EURO_AREA_EXCLUDE)
        used, missing, a_sum, g_sum, partial, period = [], [], 0.0, 0.0, False, f"{y}-Q4"
        for code in members:
            v = countries.get(code, {}).get("values", {}).get(str(y))
            if v and v["gdp"]:
                used.append(code)
                a_sum += v["assets"]
                g_sum += v["gdp"]
                if v["partial"]:
                    partial, period = True, v["period"]
            else:
                missing.append(code)
        if not used:
            continue
        values[str(y)] = {
            "share": round(a_sum / g_sum * 100, 3), "assets": round(a_sum, 1), "gdp": round(g_sum, 1),
            "gdp_year": y - 1 if partial else y, "period": period, "partial": partial,
            "members": used, "missing": missing,
        }
    return {"name": "Euro area (excl. LU)", "values": values,
            "asset_source": "Calculated: sum of assets / sum of GDP", "gdp_source": ""}


# --- Cached loader -------------------------------------------------------------------------

_lock = threading.Lock()
_cache = {"stamp": None, "data": None, "error": None}


def file_stamp(path):
    st = path.stat()
    return f"{st.st_mtime_ns}-{st.st_size}"


def load():
    """Return (data, stamp, error). Re-reads the workbook only when it has changed.

    If the file cannot be read (e.g. mid-save), the last good data is returned with an error.
    """
    path = data_file()
    with _lock:
        try:
            stamp = file_stamp(path)
        except OSError as exc:
            _cache["error"] = f"Cannot open {path.name}: {exc.strerror or exc}"
            return _cache["data"], _cache["stamp"], _cache["error"]
        if stamp != _cache["stamp"]:
            try:
                data = build(read_sheet(path, SHEET_NAME))
                data["file"] = path.name
                _cache.update(stamp=stamp, data=data, error=None)
            except Exception as exc:  # noqa: BLE001 - keep serving the last good version
                _cache["error"] = f"Could not read {path.name}: {exc}"
        return _cache["data"], _cache["stamp"], _cache["error"]
