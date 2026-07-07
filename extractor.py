"""
extractor.py — Turns a Bell & Gossett-style pump cutsheet into a clean DataFrame.
Uses pdfplumber's table detection + a small parser for inches like 8-5/8".
"""

import re
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional

import pdfplumber
import pandas as pd


# ---------- helpers ----------

_MM_PAREN = re.compile(r"\((\d+(?:\.\d+)?)\)")           # e.g. "(219)"
_FRAC     = re.compile(r"^\s*(\d+)?[\s-]*(\d+)/(\d+)")   # 8-5/8  or  5/8
_HP_FRAC  = re.compile(r"(\d+)\s*/\s*(\d+)\s*th?", re.I) # 1/12th, 1/6th, 2/5th


def parse_inches_to_mm(cell: str) -> Optional[float]:
     (mm) value in parentheses; else parse the fractional inches."""
    if not cell:
        return None
    m = _MM_PAREN.search(cell)
    if m:
        return float(m.group(1))
    s = cell.strip().replace('"', "").replace("”", "").replace("“", "")
    m = _FRAC.match(s)
    if m:
        whole = int(m.group(1)) if m.group(1) else 0
        inches = whole + int(m.group(2)) / int(m.group(3))
        return round(inches * 25.4, 2)
    try:
        return round(float(s) * 25.4, 2)
    except ValueError:
        return None


def parse_hp(cell: str) -> Optional"""'1/12th' -> 0.0833, '2/5th' -> 0.4"""
    if not cell:
        return None
    m = _HP_FRAC.search(cell)
    if m:
        return round(int(m.group(1)) / int(m.group(2)), 4)
    try:
        return float(cell)
    except ValueError:
        return None


# ---------- data model ----------

@dataclass
class PumpSpec:
    model: str
    part_number: str
    flange_sizes: str
    hp: Optional[float]
    voltage: Optional[int]
    rpm: Optional[int]
    A_mm: Optional[float]   # overall length (flange-to-flange)
    B_mm: Optional[float]   # overall height (incl. motor)
    C_mm: Optional[float]   # motor length
    D_mm: Optional[float]   # motor diameter
    E_mm: Optional[float]   # flange OD
    weight_kg: Optional[float]


# ---------- main extractor ----------

MODEL_RX = re.compile(r"^PL-\d+[A-Z]?(?:/\s*\d+\")?$")

def extract_pumps(pdf_bytes: bytes) -> List"""Read every page, find spec rows starting with 'PL-xx', return PumpSpec list."""
    rows: List[PumpSpec] = []
    with pdfplumber.open(pdf_bytes) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables() or []:
                for row in table:
                    row = [(c or "").strip() for c in row]
                    if not row or not MODEL_RX.match(row[0].replace(" ", "")):
                        continue
                    # Heuristic column mapping — resilient to blank cells
                    cols = row + [""] * (16 - len(row))
                    try:
                        rows.append(PumpSpec(
                            model        = cols[0],
                            part_number  = cols[1],
                            flange_sizes = cols[4],
                            hp           = parse_hp(cols[5]),
                            voltage      = _first_int(cols[7]) or 115,
                            rpm          = _first_int(cols[8]),
                            A_mm         = parse_inches_to_mm(cols[9]),
                            B_mm        = parse_inches_to_mm(cols[10]),
                            C_mm         = parse_inches_to_mm(cols[11]),
                            D_mm         = parse_inches_to_mm(cols[12]),
                            E_mm         = parse_inches_to_mm(cols[13]),
                            weight_kg    = _weight_kg(cols[14]),
                        ))
                    except Exception:
                        continue
    # de-duplicate on model
    seen, unique = set(), []
    for p in rows:
        if p.model in seen:
            continue
        seen.add(p.model)
        unique.append(p)
    return unique


def _first_int(cell: str) -> Optional[int]:
    m = re.search(r"\d+", cell or "")
    return int(m.group()) if m else None


def _weight_kg(cell: str) -> Optional[float]:
    m = re.search(r"\(([\d.]+)\)", cell or "")
    return float(m.group(1)) if m else None


def as_dataframe(pumps: List[PumpSpec]) -> pd.DataFrame:
    return pd.DataFrame([asdict(p) for p in pumps])
