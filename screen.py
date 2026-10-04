"""
The end-to-end pipeline, usable from the command line or from app.py.

    python screen.py path/to/CIM.pdf --acquirer acquirer_profile.txt --comps comps.csv

Steps:
  1. Read the PDF locally            (pdf_reader.py)
  2. Extract facts chunk by chunk     (extractor.py + local model)
  3. Merge facts, compute metrics     (extractor.py, plain Python)
  4. Value against your comps         (valuation.py, plain Python)
  5. Write each memo section          (local model, from the fact sheet only)
  6. Build the Word report            (report_writer.py)
"""
import argparse
import json
import time
from pathlib import Path

import config
import extractor
import local_llm
import pdf_reader
import prompts
import report_writer
import valuation


def compact_facts(facts: dict, val: dict | None) -> str:
    """The fact sheet the writing prompts see: short, numeric, with page refs."""
    cur = facts["currency"]
    fin = {
        m: {p: f"{c['value']:,.1f} {cur} mn [p. {c['page']}]" for p, c in cells.items()}
        for m, cells in facts["fin_table"].items()
    }
    sheet = {
        "company": facts["company"],
        "products_services": facts["products_services"],
        "revenue_mix": facts["revenue_mix"],
        "customer_mix": facts["customer_mix"],
        "financials_in_millions": fin,
        "computed_metrics": {k: v for k, v in facts["derived"].items()
                             if k not in ("latest_revenue", "latest_ebitda")},
        "data_conflicts": facts["fin_conflicts"],
        "growth_drivers": facts["growth_drivers"],
        "risks_from_cim": facts["risks"],
        "deal_info": facts["deal_info"],
    }
    if val and val.get("rows"):
        sheet["valuation_from_comps"] = [
            {"method": r["method"], "median_multiple": round(r["multiples"][1], 1),
             "implied_ev_range_mn": [round(x) for x in r["implied"]] if r["implied"] else None}
            for r in val["rows"]]
    return json.dumps(sheet, ensure_ascii=False, indent=1)[:28000]


def write_sections(fact_text: str, acquirer: str, model: str, progress=None) -> dict:
    sections = {}
    names = list(prompts.SECTION_PROMPTS)
    for i, name in enumerate(names, start=1):
        if progress:
            progress(i, len(names), name)
        prompt = prompts.SECTION_PROMPTS[name].format(
            facts=fact_text, acquirer=acquirer.strip() or "(not provided)")
        try:
            sections[name] = local_llm.chat_json(prompts.WRITE_SYSTEM, prompt, model)
        except local_llm.LocalLLMError as e:
            sections[name] = {"_error": str(e)}
    return sections


def run_screen(pdf_path, model=config.DEFAULT_MODEL, acquirer="", comps_csv=None,
               out_dir=config.OUTPUT_DIR, progress=print) -> dict:
    t0 = time.time()
    say = progress or (lambda *_: None)

    pages = pdf_reader.read_pdf(pdf_path)
    chunks = pdf_reader.chunk_pages(pages)
    say(f"Read {len(pages)} pages -> {len(chunks)} chunks")

    raw = extractor.extract_all(
        chunks, model, progress=lambda i, n: say(f"Extracting facts: chunk {i}/{n}"))
    if all("_error" in r for r in raw):
        raise local_llm.LocalLLMError(
            "The local model failed on every chunk. Is Ollama running? First error: "
            + raw[0]["_error"])
    facts = extractor.merge(raw)
    d = facts["derived"]

    val = None
    if comps_csv:
        comps = valuation.load_comps(comps_csv)
        val = valuation.value_target(comps, d["latest_revenue"], d["latest_ebitda"])
    asking = valuation.asking_price_multiples(
        facts["deal_info"], d["latest_revenue"], d["latest_ebitda"])

    sections = write_sections(
        compact_facts(facts, val), acquirer, model,
        progress=lambda i, n, name: say(f"Writing section {i}/{n}: {name}"))

    Path(out_dir).mkdir(parents=True, exist_ok=True)
    name = (facts["company"].get("name") or Path(pdf_path).stem)
    safe = "".join(ch if ch.isalnum() else "_" for ch in name)[:40]
    out = Path(out_dir) / f"First_Screen_{safe}_{time.strftime('%Y%m%d_%H%M')}.docx"
    report_writer.build_report(out, facts, sections, val, asking,
                               source_name=Path(pdf_path).name, model=model,
                               pages=len(pages))
    # keep the raw extraction next to the report so every figure can be audited
    out.with_suffix(".facts.json").write_text(
        json.dumps({"facts": facts, "sections": sections}, indent=1, ensure_ascii=False))
    say(f"Done in {time.time() - t0:.0f}s -> {out}")
    return {"report": str(out), "facts": facts, "sections": sections,
            "valuation": val, "asking": asking}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Local, offline first screen of a CIM")
    ap.add_argument("pdf")
    ap.add_argument("--model", default=config.DEFAULT_MODEL)
    ap.add_argument("--acquirer", help="text file describing the buyer (for synergies)")
    ap.add_argument("--comps", help="CSV of comparable companies and multiples")
    a = ap.parse_args()
    acq = Path(a.acquirer).read_text() if a.acquirer else ""
    comps = Path(a.comps).read_text() if a.comps else None
    run_screen(a.pdf, a.model, acq, comps)
