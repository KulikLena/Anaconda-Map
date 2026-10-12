"""Download real estate fund assets (ECB) and GDP (Eurostat), compute % of GDP, save to the DB.

    python manage.py fetch_funds                     # data only (boundaries downloaded once)
    python manage.py fetch_funds --refresh-boundaries
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from funds import sources
from funds.models import Country, Observation

BOUNDARIES = Path(__file__).resolve().parents[2] / "static" / "funds" / "eu_countries.geojson"


class Command(BaseCommand):
    help = "Fetch ECB real estate fund assets and Eurostat GDP, compute share of GDP."

    def add_arguments(self, parser):
        parser.add_argument("--refresh-boundaries", action="store_true",
                            help="Download the GISCO country boundaries again.")
        parser.add_argument("--key", default=sources.ECB_SERIES_KEY,
                            help="ECB IVF series key (default: %(default)s).")

    def handle(self, *args, **opts):
        if opts["refresh_boundaries"] or not BOUNDARIES.exists():
            self.stdout.write("Downloading country boundaries (GISCO)...")
            geo = sources.fetch_boundaries()
            BOUNDARIES.parent.mkdir(parents=True, exist_ok=True)
            BOUNDARIES.write_text(json.dumps(geo, separators=(",", ":")), encoding="utf-8")
            self.stdout.write(f"  {len(geo['features'])} countries -> {BOUNDARIES}")

        self.stdout.write(f"Downloading ECB IVF {opts['key']} ...")
        try:
            assets = sources.fetch_ecb(opts["key"])
        except Exception as exc:  # noqa: BLE001
            raise CommandError(f"ECB download failed: {exc}") from exc
        if not assets:
            raise CommandError("ECB returned no observations. Check the series key in the portal.")
        for code in sorted(assets):
            yrs = sorted(assets[code])
            self.stdout.write(f"  {code}: {yrs[0]}-{yrs[-1]} ({assets[code][yrs[-1]][0]} latest)")

        self.stdout.write("Downloading Eurostat GDP (nama_10_gdp, CP_MEUR)...")
        try:
            gdp = sources.fetch_gdp()
        except Exception as exc:  # noqa: BLE001
            raise CommandError(f"Eurostat download failed: {exc}") from exc

        rows = sources.compute_rows(assets, gdp)
        with transaction.atomic():
            Observation.objects.all().delete()
            for code in assets:
                Country.objects.update_or_create(code=code, defaults={"name": sources.NAMES.get(code, code)})
            Observation.objects.bulk_create(
                Observation(country_id=r["country"], **{k: v for k, v in r.items() if k != "country"})
                for r in rows
            )

        missing = [r for r in rows if r["share_pct"] is None]
        self.stdout.write(self.style.SUCCESS(f"Saved {len(rows)} country-years."))
        if missing:
            self.stdout.write(self.style.WARNING(
                f"{len(missing)} rows have no GDP match: " + ", ".join(sorted({r['country'] for r in missing}))
            ))
