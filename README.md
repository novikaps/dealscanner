# Local Deal Screener

Reads a CIM (PDF) and drafts a **2–3 page first-screen memo** in Word:

1. About the company + investment highlights
2. Revenue mix
3. Customer mix
4. Financial snapshot, with growth and margins computed in Python
5. Comparable valuation, using your own comps CSV
6. Synergy hypotheses, using your acquirer profile
7. Risks and challenges, ranked by severity
8. Key diligence questions

The memo also gives an initial view (Proceed / Proceed with caution / Pass) and flags data gaps and conflicting figures.

## Why it is confidential by design

| What | Where it happens |
|---|---|
| Reading the PDF | `pdfplumber`, on your computer |
| AI analysis | A model running in **Ollama on localhost**. No API, no cloud |
| Arithmetic and valuation | Plain Python |
| Output | A `.docx` in `reports/` on your computer |

Guard rails in the code:
- `local_llm.py` refuses any model address that isn't `localhost`.
- It also refuses Ollama `-cloud` models, which run on remote servers.
- It ignores system proxy settings.
- Streamlit is bound to localhost, with telemetry off and the Deploy button hidden.

**Prove it to yourself:** after setup, turn off Wi-Fi and run a CIM. It still works.

You should still follow your NDA and your firm's policy on where deal documents may be stored.

## Setup (about 20 minutes, one time)

1. **Install Ollama:** download it from ollama.com and open the app.
2. **Download a model** in Terminal or PowerShell. Pick one that fits your RAM:
   ```
   ollama pull qwen3:8b      # 16 GB RAM laptop (default)
   ollama pull qwen3:14b     # 24-32 GB RAM, better quality
   ```
   Any model you've pulled shows up in the app's dropdown.
3. **Install Python packages** (Python 3.10+) from inside this folder:
   ```
   pip install -r requirements.txt
   ```
4. **Optional:** edit `acquirer_profile.txt` to describe the buyer, which gives sharper synergies.

## Run

**Web app:**
```
streamlit run app.py
```
This opens http://localhost:8501. Upload the CIM, optionally add a comps CSV, and click **Run first screen**.

**Command line:**
```
python screen.py "Project X CIM.pdf" --acquirer acquirer_profile.txt --comps comps.csv
```

Speed: expect about 30–60 seconds per ~9,000 characters of CIM on a laptop, so a 60–100 page CIM takes 10–20 minutes. A GPU or Apple Silicon Mac is much faster.

## Comps file

Copy `comps_template.csv` and fill in real peers and multiples from Capital IQ, Bloomberg or PitchBook:

```
company,ev_revenue,ev_ebitda,notes
```

The tool applies the 25th percentile, median and 75th percentile to the target's latest revenue and EBITDA. If the CIM states an asking price, the tool shows the multiple it implies. The model never makes up multiples. Without a CSV, it lists suggested peers, marked unverified.

## How it works (for explaining it)

```
PDF → pages (with page numbers) → ~9k-character chunks
    → local model extracts facts as JSON, each with a page number   (prompts.EXTRACT_*)
    → Python merges chunks, converts units to millions, flags
      conflicting figures, computes growth/margins/CAGR             (extractor.py)
    → Python applies comps multiples                                 (valuation.py)
    → local model writes each section from the fact sheet only       (prompts.SECTION_PROMPTS)
    → Word report + an audit file (.facts.json)                      (report_writer.py)
```

Design choices worth talking about:
- **Extract, then write.** The model never writes from the raw PDF. It writes only from a verified fact sheet, which cuts hallucination.
- **Numbers never come from the model's arithmetic.** Growth, margins and valuation are computed in Python, so they are reproducible.
- **Every figure carries a page cite.** Conflicting numbers in the CIM (e.g. revenue stated two ways) are flagged, not silently picked.
- **Fully local.** The trade-off is that a small local model is less capable than a frontier cloud model. The output is therefore a *first screen for an analyst to verify*, not a final memo.

## Files

| File | Role |
|---|---|
| `config.py` | Settings (model, chunk size, localhost address) |
| `local_llm.py` | Talks to Ollama, with the privacy guard rails |
| `pdf_reader.py` | Reads PDF text and tables page by page; detects scanned PDFs |
| `prompts.py` | All prompts |
| `extractor.py` | Chunk extraction, merging, unit normalisation, metrics |
| `valuation.py` | Comps valuation and asking-price multiples |
| `report_writer.py` | Builds the Word memo |
| `screen.py` | The pipeline (also the command-line entry point) |
| `app.py` | Streamlit web page |
| `tests/` | Sample fictional CIM plus a fake Ollama server for testing without a model |

## Limits and tips

- **Scanned PDFs** have no text layer. OCR them locally first (`ocrmypdf in.pdf out.pdf`).
- **Units:** check the currency and units line at the top of the financial table. Mixed-unit CIMs can confuse extraction.
- **Housekeeping:** reports and `.facts.json` files contain CIM data. Delete `reports/` when the deal is closed or dropped.
- **Quality:** a bigger model gives noticeably better synergy and risk writing, if your laptop can run one.
