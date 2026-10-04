"""
Simple local web page for the screener:  streamlit run app.py
Streamlit serves the page on localhost only (see .streamlit/config.toml).
"""
import tempfile
from pathlib import Path

import streamlit as st

import config
import local_llm
import screen

st.set_page_config(page_title="Local Deal Screener", layout="centered")
st.title("Local Deal Screener")
st.caption("Reads a CIM and drafts a 2–3 page first screen. The PDF and the AI model "
           "both stay on this computer. Nothing is uploaded anywhere.")

# --- model picker: only models already downloaded into Ollama ---
try:
    models = local_llm.list_local_models()
except local_llm.LocalLLMError as e:
    st.error(str(e))
    st.stop()
if not models:
    st.error(f"No local models found. In a terminal run:  ollama pull {config.DEFAULT_MODEL}")
    st.stop()
default = models.index(config.DEFAULT_MODEL) if config.DEFAULT_MODEL in models else 0
model = st.selectbox("Local model", models, index=default)

# --- inputs ---
cim = st.file_uploader("CIM (PDF)", type=["pdf"])
profile_file = Path("acquirer_profile.txt")
acquirer = st.text_area(
    "Acquirer profile (used for synergies)",
    value=profile_file.read_text() if profile_file.exists() else "",
    height=120,
    help="Who is buying: products, customers, geographies, capabilities. Saved nowhere but this file.")
comps_file = st.file_uploader("Comps CSV (optional): company, ev_revenue, ev_ebitda, notes", type=["csv"])

if st.button("Run first screen", type="primary", disabled=cim is None):
    # Streamlit keeps uploads in memory; write to a temp file for pdfplumber, delete after.
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(cim.getbuffer())
        pdf_path = tmp.name
    comps = comps_file.getvalue().decode("utf-8-sig") if comps_file else None

    status = st.status("Screening… (a long CIM can take 10–20 minutes on a laptop)", expanded=True)
    try:
        result = screen.run_screen(pdf_path, model, acquirer, comps,
                                   progress=lambda msg: status.write(msg))
        status.update(label="Done", state="complete")
    except Exception as e:  # show any failure plainly
        status.update(label="Failed", state="error")
        st.error(str(e))
        st.stop()
    finally:
        Path(pdf_path).unlink(missing_ok=True)

    report = Path(result["report"])
    st.download_button("Download Word report", report.read_bytes(), file_name=report.name,
                       mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    st.caption(f"Also saved to {report.resolve()}")

    v = result["sections"].get("verdict", {})
    st.subheader(f"Initial view: {v.get('recommendation', 'n/a')}")
    st.write(v.get("rationale", ""))
    f = result["facts"]
    if f["fin_conflicts"]:
        st.warning("Conflicting figures found in the CIM:\n\n- " + "\n- ".join(f["fin_conflicts"]))
    with st.expander("Extracted fact sheet (audit trail)"):
        st.json(f)
