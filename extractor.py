"""
Stage 1: pull facts out of every chunk of the CIM, then merge them into one
fact sheet. Merging, unit conversion and all arithmetic (growth, margins) are
done here in plain Python, not by the model, so the numbers are reproducible.
"""
import re
from collections import Counter, defaultdict

import local_llm
import prompts

# ---------- 1. Extraction ----------

LIST_KEYS = ["products_services", "revenue_mix", "customer_mix", "financials",
             "growth_drivers", "risks", "deal_info"]


def extract_all(chunks, model, progress=None) -> list[dict]:
    """Run the extraction prompt on each chunk. progress(i, n) reports status."""
    results = []
    for i, chunk in enumerate(chunks, start=1):
        if progress:
            progress(i, len(chunks))
        try:
            results.append(local_llm.chat_json(
                prompts.EXTRACT_SYSTEM, prompts.EXTRACT_USER.format(chunk=chunk), model))
        except local_llm.LocalLLMError as e:
            results.append({"_error": f"chunk {i}: {e}"})
    return results


# ---------- 2. Normalising financial figures ----------

METRIC_ALIASES = [  # (pattern, standard name) - order matters
    (r"adj\w*\.?\s*ebitda", "Adj. EBITDA"),
    (r"ebitda", "EBITDA"),
    (r"gross (profit|margin)", "Gross profit"),
    (r"^ebit\b|operating (profit|income)", "EBIT"),
    (r"pat|net (income|profit)|profit after tax", "PAT"),
    (r"free cash|fcf", "Free cash flow"),
    (r"capex|capital expenditure", "Capex"),
    (r"net debt", "Net debt"),
    (r"revenue|sales|turnover", "Revenue"),
]
METRIC_ORDER = ["Revenue", "Gross profit", "EBITDA", "Adj. EBITDA", "EBIT", "PAT",
                "Capex", "Free cash flow", "Net debt"]

# unit word -> multiplier to convert into millions
SCALES = [(r"thousand|'000|\bk\b", 0.001), (r"crore|\bcr\b", 10.0), (r"lakh", 0.1),
          (r"billion|\bbn\b", 1000.0), (r"million|\bmn\b|\bmm\b|\bm\b", 1.0)]
CURRENCIES = [(r"usd|\$|us\$", "USD"), (r"inr|₹|\brs\.?\b", "INR"), (r"eur|€", "EUR"),
              (r"gbp|£", "GBP"), (r"sgd", "SGD"), (r"aud", "AUD")]


def std_metric(name: str):
    n = (name or "").lower()
    for pattern, std in METRIC_ALIASES:
        if re.search(pattern, n):
            return std
    return None


def std_period(period: str, kind: str) -> str:
    p = (period or "").upper()
    if "LTM" in p or "TTM" in p:
        return "LTM"
    m = re.search(r"(20\d\d)", p) or re.search(r"FY\s?'?(\d\d)\b", p)
    if not m:
        return p.strip() or "?"
    year = m.group(1)
    year = year if len(year) == 4 else "20" + year
    return f"FY{year}" + ("E" if kind == "projected" else "")


def to_millions(value, unit: str):
    """Return (value in millions, currency) or (None, None) if not a number."""
    try:
        v = float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None, None
    u = (unit or "").lower()
    scale = next((s for pat, s in SCALES if re.search(pat, u)), 1.0)
    cur = next((c for pat, c in CURRENCIES if re.search(pat, u)), None)
    return v * scale, cur


# ---------- 3. Merging ----------

def _first(results, key):
    for r in results:
        v = (r.get("company") or {}).get(key)
        if v not in (None, "", "null"):
            return v
    return None


def _dedupe(items, key):
    seen, out = set(), []
    for it in items:
        k = str(it.get(key, "")).strip().lower()[:80]
        if k and k not in seen:
            seen.add(k)
            out.append(it)
    return out


def merge(results: list[dict]) -> dict:
    """Combine per-chunk JSON into one fact sheet."""
    ok = [r for r in results if "_error" not in r]
    facts = {
        "company": {k: _first(ok, k) for k in
                    ["name", "headquarters", "founded", "employees",
                     "description", "business_model", "page"]},
        "errors": [r["_error"] for r in results if "_error" in r],
    }
    lists = defaultdict(list)
    for r in ok:
        for k in LIST_KEYS:
            lists[k].extend(x for x in (r.get(k) or []) if isinstance(x, dict))

    facts["products_services"] = _dedupe(lists["products_services"], "name")[:8]
    facts["revenue_mix"] = _dedupe(
        [dict(x, _k=f"{x.get('dimension')}|{x.get('item')}|{x.get('year')}")
         for x in lists["revenue_mix"]], "_k")[:15]
    facts["customer_mix"] = _dedupe(lists["customer_mix"], "metric")[:10]
    facts["growth_drivers"] = _dedupe(lists["growth_drivers"], "point")[:8]
    facts["risks"] = _dedupe(lists["risks"], "risk")[:12]
    facts["deal_info"] = _dedupe(lists["deal_info"], "item")[:8]
    for x in facts["revenue_mix"]:
        x.pop("_k", None)

    facts.update(merge_financials(lists["financials"]))
    return facts


def merge_financials(rows: list[dict]) -> dict:
    """Build a clean metric x period table in one currency, in millions.
    Where the CIM gives different numbers for the same cell, keep the value
    cited most often and record the conflict for the analyst to check."""
    cells = defaultdict(list)          # (metric, period) -> [(value_mn, page)]
    currencies = Counter()
    for r in rows:
        metric = std_metric(r.get("metric"))
        value, cur = to_millions(r.get("value"), r.get("unit"))
        if not metric or value is None:
            continue
        period = std_period(str(r.get("period")), r.get("type", "actual"))
        cells[(metric, period)].append((value, r.get("page")))
        if cur:
            currencies[cur] += 1

    table, conflicts = {}, []
    for (metric, period), vals in cells.items():
        groups = []                     # cluster values within 1% of each other
        for v, pg in vals:
            for g in groups:
                if abs(g[0][0] - v) <= 0.01 * max(abs(v), 1e-9):
                    g.append((v, pg))
                    break
            else:
                groups.append([(v, pg)])
        groups.sort(key=len, reverse=True)
        best = groups[0][0]
        table.setdefault(metric, {})[period] = {"value": round(best[0], 2), "page": best[1]}
        if len(groups) > 1:
            conflicts.append(
                f"{metric} {period}: " + " vs ".join(
                    f"{g[0][0]:,.1f} (p. {g[0][1]})" for g in groups[:3]))

    periods = sorted({p for m in table.values() for p in m},
                     key=lambda p: (1 if p == "LTM" else 2 if p.endswith("E") else 0, p))
    currency = currencies.most_common(1)[0][0] if currencies else "?"
    return {"fin_table": table, "fin_periods": periods,
            "currency": currency, "fin_conflicts": conflicts,
            "derived": derived_metrics(table, periods)}


def derived_metrics(table, periods) -> dict:
    """Growth and margins, computed in Python (not by the model)."""
    rev = {p: c["value"] for p, c in table.get("Revenue", {}).items()}
    ebitda_key = "Adj. EBITDA" if "Adj. EBITDA" in table else "EBITDA"
    ebitda = {p: c["value"] for p, c in table.get(ebitda_key, {}).items()}
    gp = {p: c["value"] for p, c in table.get("Gross profit", {}).items()}
    out = {"ebitda_basis": ebitda_key, "growth": {}, "ebitda_margin": {}, "gross_margin": {}}

    yearly = [p for p in periods if p.startswith("FY")]
    for prev, cur in zip(yearly, yearly[1:]):
        if rev.get(prev) and cur in rev:
            out["growth"][cur] = round(100 * (rev[cur] / rev[prev] - 1), 1)
    for p in periods:
        if rev.get(p):
            if p in ebitda:
                out["ebitda_margin"][p] = round(100 * ebitda[p] / rev[p], 1)
            if p in gp:
                out["gross_margin"][p] = round(100 * gp[p] / rev[p], 1)

    actual = [p for p in yearly if not p.endswith("E") and p in rev]
    if len(actual) >= 2 and rev[actual[0]] > 0:
        n = int(actual[-1][2:6]) - int(actual[0][2:6])
        if n > 0:
            out["historical_cagr"] = {
                "from": actual[0], "to": actual[-1],
                "pct": round(100 * ((rev[actual[-1]] / rev[actual[0]]) ** (1 / n) - 1), 1)}
    proj = [p for p in yearly if p.endswith("E") and p in rev]
    if actual and proj:
        n = int(proj[-1][2:6]) - int(actual[-1][2:6])
        if n > 0 and rev[actual[-1]] > 0:
            out["projected_cagr"] = {
                "from": actual[-1], "to": proj[-1],
                "pct": round(100 * ((rev[proj[-1]] / rev[actual[-1]]) ** (1 / n) - 1), 1)}

    # latest actual figures, used for valuation
    latest = "LTM" if "LTM" in rev else (actual[-1] if actual else None)
    out["latest_period"] = latest
    out["latest_revenue"] = rev.get(latest) if latest else None
    out["latest_ebitda"] = ebitda.get(latest) if latest else None
    return out
