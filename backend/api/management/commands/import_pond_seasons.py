"""
Import real pond Excel seasons into Django DB as s1, s2, s3.

Only imports batches that have:
  - stocking date
  - harvest kg
Missing optional fields are skipped (not invented).

Usage:
  python manage.py import_pond_seasons
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from api.models import HarvestEntry, Season


POND_DIR = Path(__file__).resolve().parents[4] / "dataset" / "shrimpDataFromTheActualPond"
# fallback if layout differs
if not POND_DIR.exists():
    POND_DIR = Path(__file__).resolve().parents[3].parent / "dataset" / "shrimpDataFromTheActualPond"


def _num(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, (int, float)):
        return float(val)
    m = re.search(r"-?\d+(?:\.\d+)?", str(val).replace(",", ""))
    return float(m.group()) if m else None


def _parse_date(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if hasattr(val, "to_pydatetime"):
        val = val.to_pydatetime()
    if hasattr(val, "date") and not isinstance(val, str):
        try:
            return val.date()
        except Exception:
            pass
    s = str(val).strip()
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%m/%d/%y",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%d/%m/%y",
    ):
        try:
            return datetime.strptime(s[:19], fmt).date()
        except ValueError:
            continue
    return None


def extract_batch(path: Path) -> dict | None:
    df = pd.read_excel(path, header=None)
    stock = close = harvest = doc = abw = surv = stocks = density = feed = fcr = None

    for _, row in df.iterrows():
        cells = list(row.tolist())
        for i, c in enumerate(cells):
            if pd.isna(c):
                continue
            k = str(c).strip().lower()
            nxt = None
            for j in range(i + 1, len(cells)):
                if pd.notna(cells[j]):
                    nxt = cells[j]
                    break
            if "stocking date" in k:
                stock = _parse_date(nxt)
            elif "close harvest" in k:
                close = _parse_date(nxt)
            elif "actual harvest" in k or k.startswith("harvest:"):
                harvest = _num(nxt)
            elif k == "doc":
                doc = _num(nxt)
            elif k == "abw":
                abw = _num(nxt)
            elif "survival" in k:
                surv = _num(nxt)
            elif "actual stocks" in k:
                stocks = _num(nxt)
            elif "pcs per sq" in k:
                density = _num(nxt)
            elif k == "feeds":
                feed = _num(nxt)
            elif k == "fcr":
                fcr = _num(nxt)

    # Required for import: stocking date + harvest kg
    if stock is None or harvest is None:
        return None

    # Fix obviously bad end date (before start)
    if close is not None and close < stock:
        close = None
    if close is None and doc:
        close = stock + timedelta(days=int(doc))

    if surv is not None and surv <= 1.5:
        surv = surv * 100.0

    return {
        "file": path.name,
        "start_date": stock,
        "end_date": close,
        "harvest_kg": harvest,
        "doc": doc,
        "abw_g": abw,
        "survival_pct": surv,
        "stocks": int(stocks) if stocks else None,
        "density": int(density) if density else None,
        "feed_kg": feed,
        "fcr": fcr,
    }


def pick_unique_batches() -> list[dict]:
    """Prefer complete distinct seasons; skip incomplete / duplicates."""
    batches = []
    seen = set()
    preferred = [
        "Actual Cost for Batch 12.xlsx",
        "Cost of  Batch 13.xlsx",
        "Production Cost and Output (2).xlsx",
        "Production Cost and Output.xlsx",
        "Production Cost and Output (1).xlsx",
    ]
    files = []
    for name in preferred:
        p = POND_DIR / name
        if p.exists():
            files.append(p)
    for p in sorted(POND_DIR.glob("*.xlsx")):
        if p not in files:
            files.append(p)

    for p in files:
        b = extract_batch(p)
        if not b:
            continue
        key = (b["start_date"], round(b["harvest_kg"], 1), b.get("stocks"))
        if key in seen:
            continue
        seen.add(key)
        batches.append(b)

    # Keep up to 3 real seasons
    return batches[:3]


class Command(BaseCommand):
    help = "Import actual pond Excel batches as seasons s1/s2/s3"

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            default=None,
            help="Import for one user only (default: all users)",
        )
        parser.add_argument(
            "--replace-empty-s1",
            action="store_true",
            default=True,
            help="Delete empty placeholder s1 seasons before import",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if not POND_DIR.exists():
            self.stderr.write(self.style.ERROR(f"Pond folder not found: {POND_DIR}"))
            return

        batches = pick_unique_batches()
        if not batches:
            self.stderr.write(self.style.ERROR("No complete pond batches found (need stocking date + harvest kg)."))
            return

        self.stdout.write(f"Found {len(batches)} importable season(s):")
        for i, b in enumerate(batches, 1):
            self.stdout.write(
                f"  s{i}: {b['file']} | {b['start_date']} -> {b['end_date']} | harvest={b['harvest_kg']} kg"
            )

        User = get_user_model()
        users = User.objects.all()
        if options["username"]:
            users = users.filter(username=options["username"])
        if not users.exists():
            self.stderr.write(self.style.ERROR("No users found"))
            return

        names = [f"s{i}" for i in range(1, len(batches) + 1)]

        for user in users:
            self.stdout.write(f"\nImporting for user={user.username}")

            # Remove empty placeholder s1 (0 harvest / 0 entries) if present
            if options["replace_empty_s1"]:
                empty = Season.objects.filter(user=user, name__iexact="s1", total_harvest_kg=0, entry_count=0)
                deleted, _ = empty.delete()
                if deleted:
                    self.stdout.write(f"  removed empty placeholder s1")

            # If s1/s2/s3 already exist with data, skip that name
            for name, batch in zip(names, batches):
                existing = Season.objects.filter(user=user, name__iexact=name).first()
                if existing and (existing.total_harvest_kg > 0 or existing.entry_count > 0):
                    self.stdout.write(self.style.WARNING(f"  skip {name}: already has data"))
                    continue
                if existing:
                    existing.delete()

                notes_parts = [f"Imported from {batch['file']}"]
                if batch.get("doc") is not None:
                    notes_parts.append(f"DOC={batch['doc']}")
                if batch.get("fcr") is not None:
                    notes_parts.append(f"FCR={batch['fcr']}")
                if batch.get("abw_g") is not None:
                    notes_parts.append(f"ABW={batch['abw_g']}g")
                if batch.get("survival_pct") is not None:
                    notes_parts.append(f"Survival={batch['survival_pct']:.1f}%")
                if batch.get("feed_kg") is not None:
                    notes_parts.append(f"Feed={batch['feed_kg']}kg")

                season = Season.objects.create(
                    user=user,
                    name=name,
                    start_date=batch["start_date"],
                    end_date=batch["end_date"],
                    is_active=False,
                    stocking_density=batch.get("density") or 0,
                    initial_shrimp_quantity=batch.get("stocks") or 0,
                    current_shrimp_quantity=batch.get("stocks") or 0,
                    average_shrimp_weight_grams=batch.get("abw_g") or 0.0,
                    notes="; ".join(notes_parts),
                )

                # One harvest-all entry with real harvest kg
                HarvestEntry.objects.create(
                    season=season,
                    date=batch["end_date"] or batch["start_date"],
                    amount=batch["harvest_kg"],
                    unit="kg",
                    note="Actual harvest (imported from pond Excel)",
                    is_all=True,
                )
                season.recompute_totals()
                season.refresh_from_db()
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  created {name}: harvest={season.total_harvest_kg} kg, "
                        f"stocks={season.current_shrimp_quantity}, end={season.end_date}"
                    )
                )

        self.stdout.write(self.style.SUCCESS("\nDone."))
