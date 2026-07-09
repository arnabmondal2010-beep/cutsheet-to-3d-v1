"""
extractor.py — Universal cutsheet extractor.
Supports:
  1. Bell & Gossett Series PL inline circulators (pumps)
  2. Trane CLCA Series Flexible Air Handling Units (AHUs)

Handles both ruled AND unruled tables (Trane uses text-positioned columns
without visible grid lines, so we need a text-line fallback).
"""

import re
from dataclasses import dataclass, asdict

import pdfplumber
import pandas as pd


# ============================================================
#  Shared helpers
# ============================================================

_MM_PAREN = re.compile(r"\((\d+(?:\.\d+)?)\)")
_FRAC     = re.compile(r"^\s*(\d+)?[\s-]*(\d+)/(\d+)")
_HP_FRAC  = re.compile(r"(\d+)\s*/\s*(\d+)\s*th?", re.I)


def parse_inches_to_mm(cell):
    """'8-5/8' or '(219)' -> mm."""
    if not cell:
        return None
    m = _MM_PAREN.search(cell)
    if m:
        return float(m.group(1))
    s = cell.strip().replace('"', "").replace("\u201d", "").replace("\u201c", "")
    m = _FRAC.match(s)
    if m:
        whole = int(m.group(1)) if m.group(1) else 0
        inches = whole + int(m.group(2)) / int(m.group(3))
        return round(inches * 25.4, 2)
    try:
        return round(float(s) * 25.4, 2)
    except ValueError:
        return None


def parse_hp(cell):
    """'1/12th' -> 0.0833 ; '2/5th' -> 0.4"""
    if not cell:
        return None
    m = _HP_FRAC.search(cell)
    if m:
        return round(int(m.group(1)) / int(m.group(2)), 4)
    try:
        return float(cell)
    except ValueError:
        return None


def _first_int(cell):
    m = re.search(r"\d+", cell or "")
    return int(m.group()) if m else None


def _try_float(cell):
    if not cell:
        return None
    s = str(cell).replace(",", "").replace(" ", "")
    try:
        return float(s)
    except ValueError:
        return None


def _weight_kg(cell):
    m = re.search(r"\(([\d.]+)\)", cell or "")
    return float(m.group(1)) if m else None


# ============================================================
#  PUMPS — Bell & Gossett Series PL
# ============================================================

PUMP_MODEL_RX = re.compile(r"^PL-\d+[A-Z]?(?:/\s*\d+\")?$")


@dataclass
class PumpSpec:
    model: str
    part_number: str
    flange_sizes: str
    hp: float
    voltage: int
    rpm: int
    A_mm: float
    B_mm: float
    C_mm: float
    D_mm: float
    E_mm: float
    weight_kg: float


def extract_pumps(pdf_bytes):
    """Scan all pages for rows starting with 'PL-xx'; return list of PumpSpec."""
    rows = []
    with pdfplumber.open(pdf_bytes) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables() or []:
                for row in table:
                    row = [(c or "").strip() for c in row]
                    if not row:
                        continue
                    first = row[0].replace(" ", "")
                    if not PUMP_MODEL_RX.match(first):
                        continue
                    cols = row + [""] * (16 - len(row))
                    try:
                        rows.append(PumpSpec(
                            model=cols[0].strip(),
                            part_number=cols[1],
                            flange_sizes=cols[4],
                            hp=parse_hp(cols[5]),
                            voltage=_first_int(cols[7]) or 115,
                            rpm=_first_int(cols[8]),
                            A_mm=parse_inches_to_mm(cols[9]),
                            B_mm=parse_inches_to_mm(cols[10]),
                            C_mm=parse_inches_to_mm(cols[11]),
                            D_mm=parse_inches_to_mm(cols[12]),
                            E_mm=parse_inches_to_mm(cols[13]),
                            weight_kg=_weight_kg(cols[14]),
                        ))
                    except Exception:
                        continue

    # de-duplicate on model
    seen = set()
    unique = []
    for p in rows:
        if p.model in seen:
            continue
        seen.add(p.model)
        unique.append(p)
    return unique


def pumps_to_df(pumps):
    return pd.DataFrame([asdict(p) for p in pumps])


# ============================================================
#  AHUs — Trane CLCA Series
# ============================================================

AHU_MODEL_RX = re.compile(r"^(0\d{2}|100)$")


@dataclass
class AhuSpec:
    model: str
    nominal_airflow_cmh: float
    coil_face_area_m2: float
    width_25mm: float
    width_50mm: float
    height_25mm: float
    height_50mm: float


def _parse_ahu_row_cells(model, row):
    """Given a structured table row, try to build an AhuSpec."""
    nums = [_try_float(c) for c in row[1:]]
    nums = [n for n in nums if n is not None]
    if len(nums) < 6:
        return None
    airflow = nums[0]
    coil_area = nums[1] if nums[1] < 20 else 0.0
    dims = [n for n in nums if 500 <= n <= 6000]
    if len(dims) < 4:
        return None
    w25, w50, h25, h50 = dims[-4], dims[-3], dims[-2], dims[-1]
    if airflow < 500:
        return None
    return AhuSpec(
        model=model,
        nominal_airflow_cmh=airflow,
        coil_face_area_m2=coil_area,
        width_25mm=w25,
        width_50mm=w50,
        height_25mm=h25,
        height_50mm=h50,
    )


# Text-line regex — for PDFs where pdfplumber returns no tables (unruled tables).
# Example line from Trane CLCA:
#   "003 2300 0.23 1656 1863 2070 2277 2484 689 739 789 839"
_AHU_LINE_RX = re.compile(
    r"^\s*(0\d{2}|100)\s+"
    r"(\d{3,6})\s+"
    r"(\d+(?:\.\d+)?)\s+"
    r"(?:\d+(?:\.\d+)?\s+){4,6}"
    r"(\d{3,4})\s+(\d{3,4})\s+(\d{3,4})\s+(\d{3,4})\s*$"
)


def _parse_ahu_row_text(line):
    """Parse an unruled text line into an AhuSpec (or None)."""
    line = re.sub(r"\s+", " ", line.strip())
    m = _AHU_LINE_RX.match(line)
    if not m:
        return None
    model = m.group(1)
    airflow = float(m.group(2))
    coil_area = float(m.group(3))
    w25 = float(m.group(4))
    w50 = float(m.group(5))
    h25 = float(m.group(6))
    h50 = float(m.group(7))
    if airflow < 500:
        return None
    return AhuSpec(
        model=model,
        nominal_airflow_cmh=airflow,
        coil_face_area_m2=coil_area,
        width_25mm=w25,
        width_50mm=w50,
        height_25mm=h25,
        height_50mm=h50,
    )


def extract_ahus(pdf_bytes):
    """Extract Trane CLCA AHU specs. Tries structured tables first, then text lines."""
    rows = []

    # Attempt 1: structured tables (ruled PDFs)
    try:
        with pdfplumber.open(pdf_bytes) as pdf:
            for page in pdf.pages:
                for table in page.extract_tables() or []:
                    for row in table:
                        row = [(c or "").strip() for c in row]
                        if len(row) < 9:
                            continue
                        first = row[0].replace(" ", "")
                        if not AHU_MODEL_RX.match(first):
                            continue
                        parsed = _parse_ahu_row_cells(first, row)
                        if parsed:
                            rows.append(parsed)
    except Exception:
        pass

    # Attempt 2: text-line fallback (unruled PDFs like Trane's)
    if not rows:
        try:
            pdf_bytes.seek(0)
        except Exception:
            pass
        try:
            with pdfplumber.open(pdf_bytes) as pdf:
                for page in pdf.pages:
                    text = page.extract_text() or ""
                    for line in text.split("\n"):
                        parsed = _parse_ahu_row_text(line)
                        if parsed:
                            rows.append(parsed)
        except Exception:
            pass

    # de-duplicate on model
    seen = set()
    unique = []
    for a in rows:
        if a.model in seen:
            continue
        seen.add(a.model)
        unique.append(a)
    return unique


def ahus_to_df(ahus):
    return pd.DataFrame([asdict(a) for a in ahus])


# ------------------------------------------------------------
#  AHU section catalog (lengths from Trane CLCA page 6)
# ------------------------------------------------------------

def _model_to_int(model_str):
    try:
        return int(model_str)
    except Exception:
        return 20


def get_section_length(section_key, model_str):
    """Return section length in mm for a given AHU model size."""
    m = _model_to_int(model_str)

    # Mixing box & supply airflow lengths depend on model size
    if section_key in ("mixing", "supply"):
        if 3 <= m <= 20: return 310
        if 25 <= m <= 35: return 465
        if 40 <= m <= 50: return 620
        if 60 <= m <= 80: return 775
        return 930

    fixed = {
        "prefilter":             155,
        "secondary_filter":      465,
        "flat_bag_filter":       620,
        "cool_coil_2row":        310,
        "cool_coil_4row":        465,
        "cool_coil_6row":        465,
        "cool_coil_8_12row":     620,
        "hot_coil_1_2row":       310,
        "hot_coil_4row":         465,
        "steam_coil":            310,
        "electric_heater":       465,
        "steam_humidifier":      775,
        "film_humidifier":       310,
        "fan":                   1240,
        "sound_attenuator":      620,
        "access":                465,
        "heat_wheel":            620,
        "high_press_humidifier": 1240,
    }
    return fixed.get(section_key, 465)


AHU_SECTION_CATALOG = [
    ("mixing",           "Mixing Box / Intake",         True),
    ("prefilter",        "Pre-filter (flat)",           True),
    ("secondary_filter", "Secondary Filter (bag)",      True),
    ("cool_coil_6row",   "Cooling Coil (6-row)",        True),
    ("hot_coil_1_2row",  "Hot Water Coil (1-2 row)",    False),
    ("electric_heater",  "Electric Heater",             False),
    ("steam_humidifier", "Steam Humidifier",            False),
    ("film_humidifier",  "Film Humidifier",             False),
    ("fan",              "Fan Section",                 True),
    ("sound_attenuator", "Sound Attenuator",            False),
    ("access",           "Access Section",              True),
    ("heat_wheel",       "Heat Recovery Wheel",         False),
    ("supply",           "Supply Airflow / Discharge",  True),
]


# ============================================================
#  Auto-detection
# ============================================================

def detect_and_extract(pdf_bytes):
    """Return (equipment_type, list_of_specs).
    equipment_type is 'pump', 'ahu', or 'unknown'."""

    # Try pump first
    try:
        pdf_bytes.seek(0)
    except Exception:
        pass
    try:
        pumps = extract_pumps(pdf_bytes)
    except Exception:
        pumps = []
    if pumps:
        return "pump", pumps

    # Then AHU
    try:
        pdf_bytes.seek(0)
    except Exception:
        pass
    try:
        ahus = extract_ahus(pdf_bytes)
    except Exception:
        ahus = []
    if ahus:
        return "ahu", ahus

    return "unknown", []
