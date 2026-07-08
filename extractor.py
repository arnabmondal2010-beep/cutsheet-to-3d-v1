"""
extractor.py - Turns a Bell & Gossett-style pump cutsheet into a clean DataFrame.
Uses pdfplumber's table detection + a small parser for inches like 8-5/8".
"""

import re
from dataclasses import dataclass, asdict

import pdfplumber
import pandas as pd


# ---------- regex helpers ----------

_MM_PAREN = re.compile(r"\((\d+(?:\.\d+)?)\)")
_FRAC     = re.compile(r"^\s*(\d+)?[\s-]*(\d+)/(\d+)")
_HP_FRAC  = re.compile(r"(\d+)\s*/\s*(\d+)\s*th?", re.I)
MODEL_RX  = re.compile(r"^PL-\d+[A-Z]?(?:/\s*\d+\")?$")


def parse_inches_to_mm(cell):
    """Prefer the (mm) value in parentheses; else parse the fractional inches."""
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
    """'1/12th' -> 0.0833, '2/5th' -> 0.4"""
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


def _weight_kg(cell):
    m = re.search(r"\(([\d.]+)\)", cell or "")
    return float(m.group(1)) if m else None


# ---------- data model ----------

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


# ---------- main extractor ----------

def extract_pumps(pdf_bytes):
    """Read every page, find spec rows starting with 'PL-xx', return list of PumpSpec."""
    rows = []
    with pdfplumber.open(pdf_bytes) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables() or []:
                for row in table:
                    row = [(c or "").strip() for c in row]
                    if not row:
                        continue
                    first = row[0].replace(" ", "")
                    if not MODEL_RX.match(first):
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


def as_dataframe(pumps):
    return pd.DataFrame([asdict(p) for p in pumps])
