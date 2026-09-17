"""
Import the full pond harvest history from dataset/harvests into Django DB
as chronological seasons s1..sN (lowest stocking date = s1).

Each file's spreadsheet content gives us stocks/ABW/harvest_kg/DOC/density/
FCR/survival/feed, but 3 of the 10 source files have a day/month digit swap
baked into their date cells (e.g. a close-harvest cell literally stores
2026-07-01 when the real date is 2026-01-07). The filename itself was typed
directly by the pond operator and matches the spreadsheet content exactly on
the 7 files that don't have this bug, so we use filename dates as the single
source of truth for start_date/end_date across all files instead of trusting
the (sometimes corrupted) date cells.

This REPLACES all existing seasons for the target user(s) -- the old
`import_pond_seasons` command only ever imported the 3 most recent of these
same seasons (with the same corrupted end dates), so this command supersedes
it.

Usage:
  python manage.py import_harvest_history
  python manage.py import_harvest_history --username=someone
  python manage.py import_harvest_history --dry-run
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from api.models import DailyGrowthMetric, HarvestEntry, Season
from .import_pond_seasons import extract_batch

HARVEST_DIR = Path(__file__).resolve().parents[4] / "dataset" / "harvests"
if not HARVEST_DIR.exists():
    HARVEST_DIR = Path(__file__).resolve().parents[3].parent / "dataset" / "harvests"

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "march": 3, "apr": 4, "april": 4, "may": 5,
    "jun": 6, "june": 6, "jul": 7, "july": 7, "aug": 8, "sep": 9, "sept": 9,
    "oct": 10, "nov": 11, "dec": 12,
}

FILENAME_RE = re.compile(
    r"(?P<m1>[a-zA-Z]+)\s*(?P<d1>\d{1,2}),\s*(?P<y1>\d{4})"
    r"\s*-\s*"
    r"(?P<m2>[a-zA-Z]+)\s*(?P<d2>\d{1,2}),\s*(?P<y2>\d{4})",
)


def _month_num(name: str) -> int | None:
    return MONTHS.get(name.strip().lower())


def parse_filename_dates(filename: str) -> tuple[date, date] | None:
    m = FILENAME_RE.search(filename)
    if not m:
        return None
    m1 = _month_num(m.group("m1"))
    m2 = _month_num(m.group("m2"))
    if not m1 or not m2:
        return None
    try:
        start = date(int(m.group("y1")), m1, int(m.group("d1")))
        end = date(int(m.group("y2")), m2, int(m.group("d2")))
    except ValueError:
        return None
    if end < start:
        return None
    return start, end


def collect_batches() -> list[dict]:
    batches = []
    for path in sorted(HARVEST_DIR.glob("*.xlsx")):
        filename_dates = parse_filename_dates(path.name)
        if not filename_dates:
            continue
        b = extract_batch(path)
        if not b:
            continue
        start, end = filename_dates
        if b["start_date"] != start or b["end_date"] != end:
            b["date_source_note"] = (
                f"corrected dates from filename (sheet had {b['start_date']} -> {b['end_date']})"
            )
        b["start_date"] = start
        b["end_date"] = end
        batches.append(b)
    batches.sort(key=lambda b: b["start_date"])
    return batches


class Command(BaseCommand):
    help = "Replace existing seasons with the full chronological harvest history from dataset/harvests"

    def add_arguments(self, parser):
        parser.add_argument("--username", default=None, help="Import for one user only (default: all users)")
        parser.add_argument("--dry-run", action="store_true", default=False, help="Show what would be imported without writing")

    @transaction.atomic
    def handle(self, *args, **options):
        if not HARVEST_DIR.exists():
            self.stderr.write(self.style.ERROR(f"Harvest folder not found: {HARVEST_DIR}"))
            return

        batches = collect_batches()
        if not batches:
            self.stderr.write(self.style.ERROR("No importable harvest files found (need stocking date + harvest kg)."))
            return

        self.stdout.write(f"Found {len(batches)} season(s) in chronological order:")
        for i, b in enumerate(batches, 1):
            note = f" [{b['date_source_note']}]" if b.get("date_source_note") else ""
            self.stdout.write(
                f"  s{i}: {b['start_date']} -> {b['end_date']} | stocks={b['stocks']} "
                f"abw={b['abw_g']}g harvest={b['harvest_kg']}kg (from {b['file']}){note}"
            )

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("\nDry run only -- nothing written."))
            return

        User = get_user_model()
        users = User.objects.all()
        if options["username"]:
            users = users.filter(username=options["username"])
        if not users.exists():
            self.stderr.write(self.style.ERROR("No users found"))
            return

        for user in users:
            self.stdout.write(f"\nImporting for user={user.username}")

            old_seasons = Season.objects.filter(user=user)
            removed_names = list(old_seasons.values_list("name", flat=True))
            old_metrics = DailyGrowthMetric.objects.filter(season__user=user).count()
            if old_metrics:
                self.stdout.write(self.style.WARNING(
                    f"  WARNING: deleting {old_metrics} growth metric row(s) attached to existing seasons"
                ))
            old_seasons.delete()
            if removed_names:
                self.stdout.write(f"  removed existing seasons: {', '.join(removed_names)}")

            for i, batch in enumerate(batches, 1):
                name = f"s{i}"
                notes_parts = [f"Imported from {batch['file']}"]
                if batch.get("date_source_note"):
                    notes_parts.append(batch["date_source_note"])
                if batch.get("doc") is not None:
                    notes_parts.append(f"DOC={batch['doc']}")
                if batch.get("fcr") is not None:
                    notes_parts.append(f"FCR={batch['fcr']}")
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

                HarvestEntry.objects.create(
                    season=season,
                    date=batch["end_date"],
                    amount=batch["harvest_kg"],
                    unit="kg",
                    note="Actual harvest (imported from pond Excel)",
                    is_all=True,
                )
                season.recompute_totals()
                season.refresh_from_db()
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  created {name}: {season.start_date} -> {season.end_date}, "
                        f"harvest={season.total_harvest_kg}kg, stocks={season.current_shrimp_quantity}"
                    )
                )

        self.stdout.write(self.style.SUCCESS("\nDone."))
