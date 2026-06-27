#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright (C) Open Astro Technologies, USA.
# Modified by Sundar Sundaresan, USA. carnaticmusicguru2015@comcast.net
# Downloaded from https://github.com/naturalstupid/PyJHora

# This file is part of the "PyJHora" Python library
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
import csv
import os
import pickle
import re
import sqlite3
import sys
import time
import traceback
import unicodedata

import pandas as pd

from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QLineEdit,
    QVBoxLayout, QHBoxLayout, QFileDialog, QComboBox, QMessageBox,
    QPlainTextEdit, QCheckBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QTextCursor


# ============================================================
# GLOBAL CONSTANTS / DEFAULTS
# Only BASE_DIR, POPULATION_MIN, ALLOW_ZERO_POP_COUNTRIES,
# and OUTPUT_FILE are set from UI.
# Everything else remains hardcoded.
# ============================================================
BASE_DIR = r"C:\LaptopBackup\Local\Personal\GitHub\JHora_World_Data"

ALLCOUNTRIES_FILE = ""
ADMIN1_FILE = ""
COUNTRYINFO_FILE = ""
TIMEZONES_FILE = ""
OUTPUT_FILE = ""

ONLY_POPULATED_PLACES = True
POPULATION_MIN = 500

# UI will set this from country field: e.g. {"IN", "US"}
ALLOW_ZERO_POP_COUNTRIES = {"IN"}

INCLUDE_ASCII_NAME = True
INCLUDE_ALTERNATE_NAMES = True
USE_ASCII_NAME_AS_PLACE_NAME = True
INCLUDE_ONLY_ASCII_ALTERNATE_NAMES = True

ALT_NAME_SEPARATOR = "|"
USE_IDS_FOR_STATE_COUNTRY = False
CHUNK_SIZE = 200000


# ============================================================
# SQLITE CONFIG
# ============================================================
RECREATE_DB = True
SQLITE_PROGRESS_EVERY = 10000


# ============================================================
# PICKLE CONFIG
# ============================================================
PICKLE_DEBUG = True
PICKLE_PROGRESS_EVERY = 5000
USE_ALT_NAMES_IN_UI_INDEX = True


# ============================================================
# PRINT REDIRECTOR
# Redirect print() output into read-only log area
# Always appends at the end, even if user clicked in middle.
# ============================================================
class PrintLogger:
    def __init__(self, text_edit: QPlainTextEdit):
        self.text_edit = text_edit

    def write(self, text):
        if text:
            self.text_edit.moveCursor(QTextCursor.MoveOperation.End)
            self.text_edit.insertPlainText(text)
            self.text_edit.moveCursor(QTextCursor.MoveOperation.End)
            self.text_edit.ensureCursorVisible()
            QApplication.processEvents()

    def flush(self):
        pass


# ============================================================
# ORIGINAL HELPERS
# ============================================================
def choose_output_place_name(name, asciiname, use_ascii_as_place_name=False):
    """
    Return the place name to write into output.

    If use_ascii_as_place_name=True and asciiname is present,
    use asciiname; otherwise use name.
    """
    name = "" if name is None else str(name).strip()
    asciiname = "" if asciiname is None else str(asciiname).strip()

    if use_ascii_as_place_name and asciiname:
        return asciiname

    return name


def is_ascii_text(text: str) -> bool:
    """
    Return True only if text contains ASCII characters only.
    """
    if not text:
        return False
    try:
        text.encode("ascii")
        return True
    except UnicodeEncodeError:
        return False


def normalize_alternate_names(value, sep="|", ascii_only=False):
    """
    GeoNames alternatenames are comma-separated in the source data.
    Convert them into a single string using the preferred separator,
    remove blanks, remove duplicates case-insensitively while preserving
    the first encountered original spelling, and optionally keep only
    ASCII alternate names.
    """
    seen_keys = set()
    items = []

    for name in str(value).split(","):
        clean = name.strip()
        if not clean:
            continue

        if ascii_only and not is_ascii_text(clean):
            continue

        # Case-insensitive dedupe key
        key = clean.casefold()

        if key not in seen_keys:
            seen_keys.add(key)
            items.append(clean)

    return sep.join(items)


# ============================================================
# ORIGINAL LOOKUP LOADERS
# ============================================================
def load_admin1_lookup(admin1_file):
    """
    admin1CodesASCII.txt columns:
    code, name, asciiname, geonameid
    """
    admin1 = pd.read_csv(
        admin1_file,
        sep="\t",
        header=None,
        names=["admin1_key", "state_name", "state_ascii", "admin1_geonameid"],
        dtype=str,
        encoding="utf-8-sig",
        keep_default_na=False
    )

    admin1["state"] = admin1["state_name"].where(
        admin1["state_name"] != "",
        admin1["state_ascii"]
    )

    return dict(zip(admin1["admin1_key"], admin1["state"]))


def load_country_lookup(countryinfo_file):
    """
    countryInfo.txt has comment lines starting with '#'
    """
    country_cols = [
        "ISO", "ISO3", "ISONumeric", "fips", "Country", "Capital",
        "AreaSqKm", "Population", "Continent", "tld", "CurrencyCode",
        "CurrencyName", "Phone", "PostalCodeFormat", "PostalCodeRegex",
        "Languages", "geonameid", "neighbours", "EquivalentFipsCode"
    ]

    country = pd.read_csv(
        countryinfo_file,
        sep="\t",
        comment="#",
        header=None,
        names=country_cols,
        dtype=str,
        encoding="utf-8-sig",
        keep_default_na=False
    )

    return dict(zip(country["ISO"], country["Country"]))


def load_timezone_lookup(timezones_file):
    """
    timeZones.txt columns:
      countryCode, timezoneId, gmtOffsetJan, dstOffsetJul, rawOffset
    """
    tz = pd.read_csv(
        timezones_file,
        sep="\t",
        comment="#",
        header=None,
        names=["countryCode", "timezoneId", "gmtOffsetJan", "dstOffsetJul", "rawOffset"],
        dtype=str,
        encoding="utf-8-sig",
        keep_default_na=False
    )

    tz["timezone_hours"] = pd.to_numeric(tz["rawOffset"], errors="coerce").fillna(0.0)

    return dict(zip(tz["timezoneId"], tz["timezone_hours"]))


# ============================================================
# ORIGINAL MAIN CSV PROCESSOR
# ============================================================
def build_output_csv(
    allcountries_file,
    admin1_lookup,
    country_lookup,
    timezone_lookup,
    output_file,
    only_populated_places=False,
    population_min=None,
    include_ascii_name=True,
    include_alternate_names=True,
    use_ascii_name_as_place_name=False,
    use_ids_for_state_country=False,
    alt_name_separator="|",
    chunk_size=200000
):
    """
    Reads allCountries.txt in chunks and creates output CSV.
    """

    geonames_cols = [
        "geonameid", "name", "asciiname", "alternatenames",
        "latitude", "longitude",
        "feature_class", "feature_code",
        "country_code", "cc2",
        "admin1_code", "admin2_code", "admin3_code", "admin4_code",
        "population", "elevation", "dem", "timezone", "modification_date"
    ]

    if os.path.exists(output_file):
        os.remove(output_file)

    chunk_iter = pd.read_csv(
        allcountries_file,
        sep="\t",
        header=None,
        names=geonames_cols,
        dtype=str,
        encoding="utf-8-sig",
        keep_default_na=False,
        chunksize=chunk_size,
        on_bad_lines="skip"
    )

    first_chunk = True
    total_written = 0

    for i, chunk in enumerate(chunk_iter, start=1):
        # Optional filter: only populated places
        if only_populated_places:
            chunk = chunk[chunk["feature_class"] == "P"].copy()

        # Convert population to numeric
        chunk["population_num"] = pd.to_numeric(
            chunk["population"].replace("", pd.NA),
            errors="coerce"
        ).fillna(0)

        # Optional filter: population threshold
        if population_min is not None:
            zero_pop_country_mask = (
                (chunk["population_num"] == 0) &
                (chunk["country_code"].isin(ALLOW_ZERO_POP_COUNTRIES))
            )

            normal_pop_mask = chunk["population_num"] >= population_min

            chunk = chunk[normal_pop_mask | zero_pop_country_mask].copy()

        # Build lookup key for state/province
        chunk["admin1_key"] = chunk["country_code"].fillna("") + "." + chunk["admin1_code"].fillna("")

        # Only resolve full names if we are NOT using compact IDs
        if not use_ids_for_state_country:
            chunk["state"] = chunk["admin1_key"].map(admin1_lookup).fillna("")
            chunk["country"] = chunk["country_code"].map(country_lookup).fillna("")

        chunk["timezone_hours"] = chunk["timezone"].map(timezone_lookup).fillna(0.0)

        # altitude/elevation logic:
        elev = pd.to_numeric(chunk["elevation"].replace("", pd.NA), errors="coerce")
        dem = pd.to_numeric(chunk["dem"].replace("", pd.NA), errors="coerce")
        chunk["altitude/elevation"] = elev.fillna(dem).fillna(0.0)

        # Clean / normalize optional search fields
        chunk["asciiname"] = chunk["asciiname"].fillna("").astype(str)

        if include_alternate_names:
            chunk["alternatenames"] = chunk["alternatenames"].fillna("").astype(str)
            chunk["alternatenames"] = chunk["alternatenames"].apply(
                lambda x: normalize_alternate_names(
                    x,
                    alt_name_separator,
                    ascii_only=INCLUDE_ONLY_ASCII_ALTERNATE_NAMES
                )
            )

        # Decide what goes into output place_name
        chunk["output_place_name"] = chunk.apply(
            lambda r: choose_output_place_name(
                r.get("name", ""),
                r.get("asciiname", ""),
                use_ascii_as_place_name=use_ascii_name_as_place_name
            ),
            axis=1
        )

        # Select final columns
        selected_cols = ["output_place_name"]

        # Only include ascii_name separately if we are NOT already using it as place_name
        if include_ascii_name and not use_ascii_name_as_place_name:
            selected_cols.append("asciiname")

        if include_alternate_names:
            selected_cols.append("alternatenames")

        # State/Country choice
        if use_ids_for_state_country:
            selected_cols.extend(["admin1_code", "country_code"])
        else:
            selected_cols.extend(["state", "country"])

        # Numeric columns
        selected_cols.extend([
            "latitude",
            "longitude",
            "timezone_hours",
            "altitude/elevation"
        ])

        out = chunk[selected_cols].copy()

        # Rename output columns
        rename_map = {
            "output_place_name": "place_name",
            "asciiname": "ascii_name",
            "alternatenames": "alternate_names",
            "admin1_code": "state_id",
            "country_code": "country_id"
        }
        out.rename(columns=rename_map, inplace=True)

        # Clean numeric columns
        out["latitude"] = pd.to_numeric(out["latitude"], errors="coerce")
        out["longitude"] = pd.to_numeric(out["longitude"], errors="coerce")
        out["timezone_hours"] = pd.to_numeric(out["timezone_hours"], errors="coerce").fillna(0.0)
        out["altitude/elevation"] = pd.to_numeric(out["altitude/elevation"], errors="coerce").fillna(0.0)

        # Drop rows with missing coordinates
        out = out.dropna(subset=["latitude", "longitude"])

        # Write output
        out.to_csv(
            output_file,
            mode="w" if first_chunk else "a",
            index=False,
            header=first_chunk,
            encoding="utf-8-sig"
        )

        rows_written = len(out)
        total_written += rows_written
        print(f"Chunk {i}: wrote {rows_written:,} rows (total so far: {total_written:,})")

        first_chunk = False

    print("\nDone!")
    print(f"Output file created: {output_file}")
    print(f"Total rows written: {total_written:,}")


# ============================================================
# SQLITE CONVERSION HELPERS
# ============================================================
def normalize_text(text: str) -> str:
    """Normalize text for exact/prefix searching."""
    if not text:
        return ""

    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def split_alt_names(value, sep=ALT_NAME_SEPARATOR):
    """Split alternate_names safely."""
    if value is None:
        return []
    value = str(value).strip()
    if not value:
        return []
    return [x.strip() for x in value.split(sep) if x.strip()]


def build_display_label(place_name: str, state: str, country: str) -> str:
    """Build canonical label like 'Pune, Maharashtra, India'."""
    parts = []
    if place_name:
        parts.append(place_name.strip())
    if state:
        parts.append(state.strip())
    if country:
        parts.append(country.strip())
    return ", ".join(parts)


def build_aliases(place_name: str, ascii_name: str, alternate_names: str):
    """
    Return deduplicated aliases preserving order.
    Output: list of tuples -> [(alias, alias_norm), ...]
    """
    aliases = []
    seen = set()

    def add_alias(a):
        if not a:
            return
        a = str(a).strip()
        if not a:
            return
        norm = normalize_text(a)
        if not norm:
            return
        if norm in seen:
            return
        seen.add(norm)
        aliases.append((a, norm))

    add_alias(place_name)
    add_alias(ascii_name)

    for alt in split_alt_names(alternate_names):
        add_alias(alt)

    return aliases


def create_tables(conn):
    cur = conn.cursor()

    if RECREATE_DB:
        cur.execute("DROP TABLE IF EXISTS aliases;")
        cur.execute("DROP TABLE IF EXISTS places;")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS places (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            place_name TEXT NOT NULL,
            ascii_name TEXT,
            state TEXT,
            country TEXT,
            display_label TEXT NOT NULL,
            display_label_norm TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            timezone_hours REAL NOT NULL,
            elevation REAL NOT NULL
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS aliases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            place_id INTEGER NOT NULL,
            alias TEXT NOT NULL,
            alias_norm TEXT NOT NULL,
            is_primary INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(place_id) REFERENCES places(id) ON DELETE CASCADE
        );
    """)

    conn.commit()


def create_indexes(conn):
    cur = conn.cursor()

    cur.execute("CREATE INDEX IF NOT EXISTS idx_places_display_label_norm ON places(display_label_norm);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_aliases_alias_norm ON aliases(alias_norm);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_aliases_place_id ON aliases(place_id);")

    cur.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_aliases_place_alias
        ON aliases(place_id, alias_norm);
    """)

    conn.commit()


def optimize_for_build(conn):
    """
    Build-time pragmas for faster inserts.
    Safe for one-time DB generation.
    """
    cur = conn.cursor()
    cur.execute("PRAGMA foreign_keys = ON;")
    cur.execute("PRAGMA journal_mode = MEMORY;")
    cur.execute("PRAGMA synchronous = OFF;")
    cur.execute("PRAGMA temp_store = MEMORY;")
    cur.execute("PRAGMA cache_size = -200000;")
    conn.commit()


def finalize_db(conn):
    cur = conn.cursor()
    cur.execute("ANALYZE;")
    conn.commit()


def build_sqlite_from_csv(csv_file, db_file):
    if not os.path.exists(csv_file):
        raise FileNotFoundError(f"CSV file not found: {csv_file}")

    os.makedirs(os.path.dirname(db_file), exist_ok=True)

    start = time.time()

    conn = sqlite3.connect(db_file)
    try:
        optimize_for_build(conn)
        create_tables(conn)

        cur = conn.cursor()

        place_insert_sql = """
            INSERT INTO places (
                place_name,
                ascii_name,
                state,
                country,
                display_label,
                display_label_norm,
                latitude,
                longitude,
                timezone_hours,
                elevation
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        alias_insert_sql = """
            INSERT OR IGNORE INTO aliases (
                place_id,
                alias,
                alias_norm,
                is_primary
            )
            VALUES (?, ?, ?, ?)
        """

        row_count = 0
        alias_count = 0

        with open(csv_file, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)

            for row in reader:
                row_count += 1

                place_name = (row.get("place_name") or "").strip()
                ascii_name = (row.get("ascii_name") or "").strip()
                alternate_names = (row.get("alternate_names") or "").strip()
                state = (row.get("state") or "").strip()
                country = (row.get("country") or "").strip()

                try:
                    latitude = float(row.get("latitude", 0.0))
                except Exception:
                    latitude = 0.0

                try:
                    longitude = float(row.get("longitude", 0.0))
                except Exception:
                    longitude = 0.0

                try:
                    timezone_hours = float(row.get("timezone_hours", 0.0))
                except Exception:
                    timezone_hours = 0.0

                try:
                    elevation = float(row.get("altitude/elevation", 0.0))
                except Exception:
                    elevation = 0.0

                display_label = build_display_label(place_name, state, country)
                display_label_norm = normalize_text(display_label)

                cur.execute(
                    place_insert_sql,
                    (
                        place_name,
                        ascii_name,
                        state,
                        country,
                        display_label,
                        display_label_norm,
                        latitude,
                        longitude,
                        timezone_hours,
                        elevation,
                    )
                )
                place_id = cur.lastrowid

                aliases = build_aliases(place_name, ascii_name, alternate_names)

                primary_norms = {
                    normalize_text(place_name),
                    normalize_text(ascii_name),
                }

                for alias, alias_norm in aliases:
                    is_primary = 1 if alias_norm in primary_norms else 0
                    cur.execute(alias_insert_sql, (place_id, alias, alias_norm, is_primary))
                    alias_count += 1

                if row_count % SQLITE_PROGRESS_EVERY == 0:
                    conn.commit()
                    elapsed = time.time() - start
                    print(
                        f"Processed {row_count:,} rows | "
                        f"aliases inserted: ~{alias_count:,} | "
                        f"elapsed: {elapsed:.2f}s",
                        flush=True
                    )

        conn.commit()

        print("Creating indexes...", flush=True)
        create_indexes(conn)
        finalize_db(conn)

        elapsed = time.time() - start
        print("\nDone!", flush=True)
        print(f"SQLite DB created: {db_file}", flush=True)
        print(f"Rows inserted into places: {row_count:,}", flush=True)
        print(f"Alias rows inserted: ~{alias_count:,}", flush=True)
        print(f"Elapsed time: {elapsed:.2f} seconds", flush=True)

    finally:
        conn.close()


# ============================================================
# PICKLE CONVERSION HELPERS
# ============================================================
def debug_print(*args):
    if PICKLE_DEBUG:
        print(*args, flush=True)


def _split_alt_names(value, sep=ALT_NAME_SEPARATOR):
    """Split alternate_names column safely."""
    if value is None:
        return []
    value = str(value).strip()
    if not value:
        return []
    return [x.strip() for x in value.split(sep) if x.strip()]


def _build_aliases_for_row(row, include_alt_names=False):
    """
    Build all searchable aliases for a CSV row:
      - place_name
      - ascii_name
      - optional alternate_names
    """
    aliases = []

    place_name = (row.get("place_name") or "").strip()
    ascii_name = (row.get("ascii_name") or "").strip()

    if place_name:
        aliases.append(place_name)

    if ascii_name and normalize_text(ascii_name) != normalize_text(place_name):
        aliases.append(ascii_name)

    if include_alt_names:
        alternate_names = _split_alt_names(row.get("alternate_names"))
        seen = {normalize_text(a) for a in aliases}
        for alt in alternate_names:
            norm_alt = normalize_text(alt)
            if alt and norm_alt not in seen:
                aliases.append(alt)
                seen.add(norm_alt)

    return aliases


def _make_location_record_from_csv_row(row):
    """
    Parse one CSV row into the compact record structure
    used by the pickle engine.
    """
    city = (row.get("place_name") or "").strip()
    state = (row.get("state") or "").strip()
    country = (row.get("country") or "").strip()

    try:
        latitude = round(float(row.get("latitude", 0.0)), 4)
    except Exception:
        latitude = 0.0

    try:
        longitude = round(float(row.get("longitude", 0.0)), 4)
    except Exception:
        longitude = 0.0

    try:
        timezone_hours = round(float(row.get("timezone_hours", 0.0)), 2)
    except Exception:
        timezone_hours = 0.0

    elevation = 0.0
    elev_value = row.get("altitude/elevation", row.get("elevation", 0.0))
    if elev_value not in (None, "", "None"):
        try:
            elevation = float(elev_value)
        except Exception:
            elevation = 0.0

    label_parts = []
    if city:
        label_parts.append(city)
    if state:
        label_parts.append(state)
    if country:
        label_parts.append(country)

    display_label = ", ".join(label_parts) if label_parts else city

    return {
        "name": display_label,
        "city_name": city,
        "state": state,
        "country": country,
        "display_label": display_label,
        "latitude": latitude,
        "longitude": longitude,
        "timezone": timezone_hours,
        "elevation": elevation,
        "source": "pickle",
    }


def build_pickle_from_csv(csv_file, pickle_file, include_alt_names=True):
    if not os.path.exists(csv_file):
        raise FileNotFoundError(f"CSV file not found: {csv_file}")

    start = time.time()

    world_cities_dict = {}
    world_cities_label_dict = {}
    world_city_records = []
    world_cities_list = []
    world_cities_search = []

    seen_display_labels = set()
    seen_search_pairs = set()

    debug_print("Opening CSV:", csv_file)

    with open(csv_file, "r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        row_count = 0
        alias_link_count = 0

        for row in reader:
            row_count += 1

            record = _make_location_record_from_csv_row(row)
            record_id = len(world_city_records)
            world_city_records.append(record)

            display_label = record["display_label"]
            norm_label = normalize_text(display_label)

            if norm_label not in world_cities_label_dict:
                world_cities_label_dict[norm_label] = record_id

            if display_label not in seen_display_labels:
                world_cities_list.append(display_label)
                seen_display_labels.add(display_label)

            aliases = _build_aliases_for_row(row, include_alt_names=include_alt_names)

            for alias in aliases:
                norm_alias = normalize_text(alias)
                if not norm_alias:
                    continue

                world_cities_dict.setdefault(norm_alias, [])

                if record_id not in world_cities_dict[norm_alias]:
                    world_cities_dict[norm_alias].append(record_id)
                    alias_link_count += 1

                pair = (norm_alias, display_label, record_id)
                if pair not in seen_search_pairs:
                    world_cities_search.append(pair)
                    seen_search_pairs.add(pair)

            if row_count % PICKLE_PROGRESS_EVERY == 0:
                elapsed = time.time() - start
                debug_print(
                    f"Processed {row_count:,} rows "
                    f"(records: {len(world_city_records):,}, "
                    f"alias links: {alias_link_count:,}, "
                    f"display labels: {len(world_cities_list):,}, "
                    f"search entries: {len(world_cities_search):,}) "
                    f"in {elapsed:.2f}s"
                )

    data = {
        "world_cities_dict": world_cities_dict,
        "world_cities_label_dict": world_cities_label_dict,
        "world_city_records": world_city_records,
        "world_cities_list": world_cities_list,
        "world_cities_search": world_cities_search,
    }

    debug_print("Saving pickle:", pickle_file)
    with open(pickle_file, "wb") as f:
        pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)

    elapsed = time.time() - start
    debug_print("\nDone!")
    debug_print(f"Pickle created: {pickle_file}")
    debug_print(f"Rows processed: {row_count:,}")
    debug_print(f"Alias links: {alias_link_count:,}")
    debug_print(f"Elapsed time: {elapsed:.2f}s")


# ============================================================
# ORIGINAL MAIN LOGIC (UNCHANGED, JUST MOVED INTO FUNCTION)
# ============================================================
def run_original_logic():
    print("Loading lookup files...")

    # Only load name lookups if we need full text state/country output
    if USE_IDS_FOR_STATE_COUNTRY:
        admin1_lookup = {}
        country_lookup = {}
    else:
        admin1_lookup = load_admin1_lookup(ADMIN1_FILE)
        country_lookup = load_country_lookup(COUNTRYINFO_FILE)

    timezone_lookup = load_timezone_lookup(TIMEZONES_FILE)

    print("Building final CSV...")
    build_output_csv(
        allcountries_file=ALLCOUNTRIES_FILE,
        admin1_lookup=admin1_lookup,
        country_lookup=country_lookup,
        timezone_lookup=timezone_lookup,
        output_file=OUTPUT_FILE,
        only_populated_places=ONLY_POPULATED_PLACES,
        population_min=POPULATION_MIN,
        include_ascii_name=INCLUDE_ASCII_NAME,
        include_alternate_names=INCLUDE_ALTERNATE_NAMES,
        use_ascii_name_as_place_name=USE_ASCII_NAME_AS_PLACE_NAME,
        use_ids_for_state_country=USE_IDS_FOR_STATE_COUNTRY,
        alt_name_separator=ALT_NAME_SEPARATOR,
        chunk_size=CHUNK_SIZE
    )


# ============================================================
# UI
# ============================================================
class GeoNamesUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GeoNames CSV Builder")
        self.resize(950, 700)
        self.stdout_backup = sys.stdout
        self.stderr_backup = sys.stderr
        self.init_ui()
        self.base_dir_edit.setText(BASE_DIR)
        self.update_output_label()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Base folder
        row1 = QHBoxLayout()
        self.base_dir_edit = QLineEdit()
        self.base_dir_edit.textChanged.connect(self.update_output_label)

        self.base_dir_btn = QPushButton("Select GeoNames Folder")
        self.base_dir_btn.clicked.connect(self.select_folder)

        row1.addWidget(QLabel("Base Folder"))
        row1.addWidget(self.base_dir_edit)
        row1.addWidget(self.base_dir_btn)
        layout.addLayout(row1)

        # Population
        row2 = QHBoxLayout()
        self.population_combo = QComboBox()
        self.population_combo.addItems(["None", "500", "1000", "5000", "10000"])
        self.population_combo.setCurrentText("500")
        self.population_combo.currentTextChanged.connect(self.update_output_label)

        row2.addWidget(QLabel("Population ≥"))
        row2.addWidget(self.population_combo)
        row2.addStretch()
        layout.addLayout(row2)

        # Countries
        row3 = QHBoxLayout()
        self.country_edit = QLineEdit("IN")
        self.country_edit.textChanged.connect(self.update_output_label)

        row3.addWidget(QLabel("Countries"))
        row3.addWidget(self.country_edit)
        layout.addLayout(row3)

        # Output file label
        self.output_file_label = QLabel("Output file: ")
        self.output_file_label.setWordWrap(True)
        layout.addWidget(self.output_file_label)

        # New row: extra output formats
        row4 = QHBoxLayout()
        row4.addWidget(QLabel('From output CSV file also create'))
        self.sqlite_cb = QCheckBox("SQLITE")
        self.pickle_cb = QCheckBox("PICKLE")
        self.sqlite_cb.setChecked(False)
        self.pickle_cb.setChecked(False)
        row4.addWidget(self.sqlite_cb)
        row4.addWidget(self.pickle_cb)
        row4.addStretch()
        layout.addLayout(row4)

        # Build button
        self.build_btn = QPushButton("Build CSV")
        self.build_btn.clicked.connect(self.run_build)
        layout.addWidget(self.build_btn)

        # Log area
        layout.addWidget(QLabel("Status Log"))
        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.log_output)

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select GeoNames Base Folder")
        if folder:
            self.base_dir_edit.setText(folder)
            self.update_output_label()

    def population_label(self):
        pop_text = self.population_combo.currentText().strip()
        if pop_text == "None":
            return "all"
        if pop_text == "1000":
            return "1K"
        if pop_text == "5000":
            return "5K"
        if pop_text == "10000":
            return "10K"
        return pop_text

    def get_country_list(self):
        return [
            c.strip().upper()
            for c in self.country_edit.text().split(",")
            if c.strip()
        ]

    def get_output_filename(self):
        base_dir = self.base_dir_edit.text().strip()
        if not base_dir:
            return ""

        pop_label = self.population_label()
        countries = self.get_country_list()

        if countries:
            filename = f"geonames_places_{pop_label}_{'_'.join(countries)}.csv"
        else:
            filename = f"geonames_places_{pop_label}.csv"

        return os.path.join(base_dir, filename)

    def update_output_label(self):
        output_file = self.get_output_filename()
        if output_file:
            self.output_file_label.setText(f"Output file: {output_file}")
        else:
            self.output_file_label.setText("Output file: ")

    def apply_ui_to_globals(self):
        global BASE_DIR, ALLCOUNTRIES_FILE, ADMIN1_FILE, COUNTRYINFO_FILE, TIMEZONES_FILE, OUTPUT_FILE
        global POPULATION_MIN, ALLOW_ZERO_POP_COUNTRIES

        BASE_DIR = self.base_dir_edit.text().strip()

        ALLCOUNTRIES_FILE = os.path.join(BASE_DIR, "allCountries.txt")
        ADMIN1_FILE = os.path.join(BASE_DIR, "admin1CodesASCII.txt")
        COUNTRYINFO_FILE = os.path.join(BASE_DIR, "countryInfo.txt")
        TIMEZONES_FILE = os.path.join(BASE_DIR, "timeZones.txt")

        pop_text = self.population_combo.currentText().strip()
        POPULATION_MIN = None if pop_text == "None" else int(pop_text)

        countries = set(self.get_country_list())
        ALLOW_ZERO_POP_COUNTRIES = countries if countries else {"IN"}

        OUTPUT_FILE = self.get_output_filename()

    def validate_inputs(self):
        base_dir = self.base_dir_edit.text().strip()
        if not base_dir:
            QMessageBox.warning(self, "Missing Folder", "Please select the GeoNames base folder.")
            return False

        required_files = [
            os.path.join(base_dir, "allCountries.txt"),
            os.path.join(base_dir, "admin1CodesASCII.txt"),
            os.path.join(base_dir, "countryInfo.txt"),
            os.path.join(base_dir, "timeZones.txt"),
        ]

        missing = [f for f in required_files if not os.path.exists(f)]
        if missing:
            QMessageBox.critical(
                self,
                "Missing Files",
                "These required files were not found:\n\n" + "\n".join(missing)
            )
            return False

        return True

    def run_build(self):
        if not self.validate_inputs():
            return

        self.apply_ui_to_globals()
        self.log_output.clear()
        self.build_btn.setEnabled(False)

        logger = PrintLogger(self.log_output)
        sys.stdout = logger
        sys.stderr = logger

        try:
            print("Starting build...\n")
            run_original_logic()

            base_no_ext = os.path.splitext(OUTPUT_FILE)[0]

            if self.sqlite_cb.isChecked():
                db_file = base_no_ext + ".db"
                print("\nStarting SQLITE conversion...")
                build_sqlite_from_csv(OUTPUT_FILE, db_file)

            if self.pickle_cb.isChecked():
                pickle_file = base_no_ext + ".pkl"
                print("\nStarting PICKLE conversion...")
                build_pickle_from_csv(
                    csv_file=OUTPUT_FILE,
                    pickle_file=pickle_file,
                    include_alt_names=USE_ALT_NAMES_IN_UI_INDEX
                )

            print("\nFinished successfully.")
            QMessageBox.information(self, "Done", f"Build completed.\n\nCSV:\n{OUTPUT_FILE}")

        except Exception:
            traceback.print_exc()
            QMessageBox.critical(self, "Error", "Build failed. See log for details.")

        finally:
            sys.stdout = self.stdout_backup
            sys.stderr = self.stderr_backup
            self.build_btn.setEnabled(True)


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GeoNamesUI()
    window.show()
    sys.exit(app.exec())