"""
Trading-comps valuation, done in plain Python.

You supply the comparable companies and their multiples in a CSV (from your
own terminal: Capital IQ, Bloomberg, PitchBook, etc.). The model never makes
up multiples. We take the 25th percentile, median and 75th percentile and
apply them to the target's latest revenue and EBITDA.
"""
import csv
import io
import re
import statistics


def load_comps(file_or_text) -> list[dict]:
    """Read comps CSV with columns: company, ev_revenue, ev_ebitda (optional: notes)."""
    text = file_or_text if isinstance(file_or_text, str) else file_or_text.read().decode("utf-8-sig")
    rows = []
    for r in csv.DictReader(io.StringIO(text)):
        r = {k.strip().lower(): (v or "").strip() for k, v in r.items() if k}
        if not r.get("company"):
            continue
        rows.append({
            "company": r["company"],
            "ev_revenue": _num(r.get("ev_revenue")),
            "ev_ebitda": _num(r.get("ev_ebitda")),
            "notes": r.get("notes", ""),
        })
    return rows


def _num(x):
    try:
        return float(re.sub(r"[x,\s]", "", x or "", flags=re.I))
    except ValueError:
        return None


def _quartiles(values):
    v = sorted(x for x in values if x is not None and x > 0)
    if not v:
        return None
    if len(v) < 4:  # too few peers for quartiles: use min / median / max
        return {"low": v[0], "median": statistics.median(v), "high": v[-1], "n": len(v)}
    q = statistics.quantiles(v, n=4)
    return {"low": q[0], "median": q[1], "high": q[2], "n": len(v)}


def value_target(comps, revenue, ebitda) -> dict:
    """Implied enterprise value range for the target (same units as inputs)."""
    out = {"comps": comps, "rows": []}
    for label, key, metric in [("EV / Revenue", "ev_revenue", revenue),
                               ("EV / EBITDA", "ev_ebitda", ebitda)]:
        q = _quartiles(c[key] for c in comps)
        if not q:
            continue
        row = {"method": label, "n": q["n"],
               "multiples": (q["low"], q["median"], q["high"]), "implied": None}
        if metric and metric > 0:
            row["implied"] = tuple(m * metric for m in row["multiples"])
        out["rows"].append(row)
    return out


def asking_price_multiples(deal_info, revenue, ebitda):
    """If the CIM states an asking price / valuation, show what multiple it implies.
    Returns None when no clear price is found; the analyst should check by hand."""
    for d in deal_info:
        item = str(d.get("item", "")).lower()
        if any(w in item for w in ["asking", "valuation", "price", "consideration"]):
            # require a unit so "8.5x EBITDA" is not mistaken for a price
            m = re.search(r"(\d[\d,.]*)\s*(mn|million|m|bn|billion|crore|cr)\b",
                          str(d.get("value", "")), re.I)
            if not m:
                continue
            v = float(m.group(1).replace(",", "").rstrip("."))
            scale = {"bn": 1000, "billion": 1000, "crore": 10, "cr": 10}.get(m.group(2).lower(), 1)
            price = v * scale
            return {"price": price, "page": d.get("page"), "text": d.get("value"),
                    "ev_revenue": price / revenue if revenue else None,
                    "ev_ebitda": price / ebitda if ebitda and ebitda > 0 else None}
    return None
