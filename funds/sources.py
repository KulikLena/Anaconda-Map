"""Download and parse the three external sources used by the funds dashboard.

1. ECB Data Portal, dataset IVF (investment fund balance sheets): real estate fund total assets.
2. Eurostat, dataset nama_10_gdp: GDP at current prices, EUR million.
3. Eurostat GISCO: country boundaries (GeoJSON).

Only the standard library is used, so nothing extra needs installing.
"""

import csv
import io
import json
import urllib.request

# --- Series definitions ------------------------------------------------------
# ECB IVF key: FREQ.REF_AREA.ADJUSTMENT.FUND_TYPE.ITEM.MATURITY.DATA_TYPE.COUNTERPART_AREA.
#              COUNTERPART_SECTOR.CURRENCY.VALUATION
#   Q   = quarterly
#   (blank REF_AREA) = every country the ECB publishes
#   40  = real estate funds
#   T00 = total assets / liabilities
#   1   = outstanding amounts (stocks)
# Check in the portal that the Lithuanian series (IVF.Q.LT.N.40.T00.A.1.Z5.0000.Z01.E)
# shows the figure you expect before relying on the numbers.
ECB_SERIES_KEY = "Q..N.40.T00.A.1.Z5.0000.Z01.E"
ECB_URL = "https://data-api.ecb.europa.eu/service/data/IVF/{key}?format=csvdata&startPeriod=2005"

EUROSTAT_GDP_URL = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/nama_10_gdp"
    "?format=JSON&unit=CP_MEUR&na_item=B1GQ&sinceTimePeriod=2005"
)

GISCO_URL = "https://gisco-services.ec.europa.eu/distribution/v2/countries/geojson/CNTR_RG_20M_2020_4326.geojson"

# Countries drawn on the map (EU + EEA + neighbours, so the map has no holes).
EUROPE = {
    "AL", "AT", "BA", "BE", "BG", "BY", "CH", "CY", "CZ", "DE", "DK", "EE", "ES", "FI", "FR",
    "GR", "HR", "HU", "IE", "IS", "IT", "LI", "LT", "LU", "LV", "MD", "ME", "MK", "MT", "NL",
    "NO", "PL", "PT", "RO", "RS", "SE", "SI", "SK", "UA", "UK", "XK", "TR", "RU", "AD", "MC",
    "SM", "VA",
}

# Eurostat/GISCO use EL for Greece and UK for the United Kingdom; ECB uses GR / GB.
EU_TO_ISO = {"EL": "GR", "UK": "GB"}

AGGREGATES = {"U2": "Euro area"}

# ECB aggregate code -> Eurostat GDP code (both "changing composition" euro area).
GDP_ALIASES = {"U2": "EA"}

NAMES = {
    "AT": "Austria", "BE": "Belgium", "BG": "Bulgaria", "CY": "Cyprus", "CZ": "Czechia",
    "DE": "Germany", "DK": "Denmark", "EE": "Estonia", "ES": "Spain", "FI": "Finland",
    "FR": "France", "GR": "Greece", "HR": "Croatia", "HU": "Hungary", "IE": "Ireland",
    "IT": "Italy", "LT": "Lithuania", "LU": "Luxembourg", "LV": "Latvia", "MT": "Malta",
    "NL": "Netherlands", "PL": "Poland", "PT": "Portugal", "RO": "Romania", "SE": "Sweden",
    "SI": "Slovenia", "SK": "Slovakia", "U2": "Euro area",
}

USER_AGENT = "AnacondaMap/1.0 (Django; funds dashboard)"


def to_iso(code):
    return EU_TO_ISO.get(code, code)


def http_get(url, timeout=120):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8-sig")


# --- ECB ---------------------------------------------------------------------

def quarter_key(period):
    """'2025-Q4' -> (2025, 4)."""
    year, q = period.split("-Q")
    return int(year), int(q)


def parse_ecb_csv(text):
    """Return {country: {year: (period, value_meur)}} keeping the latest quarter of each year.

    For complete years that is Q4 (end-of-year stock); for the current year it is the latest
    quarter published, flagged later as partial.
    """
    out = {}
    for row in csv.DictReader(io.StringIO(text)):
        value = (row.get("OBS_VALUE") or "").strip()
        if not value:
            continue
        country = row["REF_AREA"]
        period = row["TIME_PERIOD"]
        year, q = quarter_key(period)
        # IVF stocks are published in EUR millions (UNIT_MULT = 6). Convert defensively.
        mult = int(row.get("UNIT_MULT") or 6)
        meur = float(value) * 10 ** (mult - 6)
        current = out.setdefault(country, {}).get(year)
        if current is None or quarter_key(current[0])[1] < q:
            out[country][year] = (period, meur)
    return out


def fetch_ecb(key=ECB_SERIES_KEY):
    return parse_ecb_csv(http_get(ECB_URL.format(key=key)))


# --- Eurostat GDP --------------------------------------------------------------

def parse_jsonstat(payload):
    """Parse a Eurostat JSON-stat 2.0 response into {geo: {year: value}}.

    Works for any dimension order: the flat index is decoded from 'id' and 'size'.
    """
    data = json.loads(payload) if isinstance(payload, str) else payload
    ids, sizes = data["id"], data["size"]
    labels = []
    for dim in ids:
        index = data["dimension"][dim]["category"]["index"]
        if isinstance(index, list):
            index = {k: i for i, k in enumerate(index)}
        labels.append({pos: code for code, pos in index.items()})

    geo_i, time_i = ids.index("geo"), ids.index("time")
    values = data["value"]
    items = values.items() if isinstance(values, dict) else enumerate(values)
    out = {}
    for flat, val in items:
        if val is None:
            continue
        flat = int(flat)
        coords = []
        for size in reversed(sizes):
            coords.append(flat % size)
            flat //= size
        coords.reverse()
        geo = to_iso(labels[geo_i][coords[geo_i]])
        year = int(labels[time_i][coords[time_i]])
        out.setdefault(geo, {})[year] = float(val)
    return out


def fetch_gdp():
    return parse_jsonstat(http_get(EUROSTAT_GDP_URL))


# --- Boundaries ------------------------------------------------------------------

def simplify_boundaries(geojson):
    """Keep European countries only and a minimal set of properties."""
    data = json.loads(geojson) if isinstance(geojson, str) else geojson
    features = []
    for f in data["features"]:
        props = f.get("properties", {})
        code = props.get("CNTR_ID") or props.get("id")
        if code not in EUROPE:
            continue
        features.append({
            "type": "Feature",
            "properties": {"iso": to_iso(code), "name": props.get("NAME_ENGL") or props.get("CNTR_NAME") or code},
            "geometry": f["geometry"],
        })
    return {"type": "FeatureCollection", "features": features}


def fetch_boundaries():
    return simplify_boundaries(http_get(GISCO_URL, timeout=300))


# --- Combine -------------------------------------------------------------------

def compute_rows(assets, gdp):
    """Join assets and GDP. Returns a list of dicts ready for Observation.

    If GDP for the year is not published yet (usually the current year), the latest
    available GDP is used and gdp_year records which year it is.
    """
    rows = []
    for country, years in assets.items():
        country_gdp = gdp.get(GDP_ALIASES.get(country, country), {})
        for year, (period, meur) in sorted(years.items()):
            gdp_year = year if year in country_gdp else max((y for y in country_gdp if y < year), default=None)
            gdp_val = country_gdp.get(gdp_year) if gdp_year else None
            share = round(meur / gdp_val * 100, 3) if gdp_val else None
            rows.append({
                "country": country, "year": year, "period": period, "assets_meur": meur,
                "gdp_meur": gdp_val, "gdp_year": gdp_year, "share_pct": share,
            })
    return rows
