"""
A fake Ollama server for testing the pipeline without downloading a model.
It answers on localhost:11434 with canned JSON matched to the sample CIM pages.
Run:  python tests/mock_ollama.py   (then run screen.py with --model mock:latest)
"""
import json
import re
from http.server import BaseHTTPRequestHandler, HTTPServer

PAGE_FACTS = {
    2: {"company": {"name": "Northwind Analytics Pvt. Ltd.", "headquarters": "Pune, India",
                    "founded": "2014", "employees": "640",
                    "description": "AI-enabled data annotation and model evaluation services for life-sciences and publishing clients.",
                    "business_model": "Managed services (per-unit) + SaaS subscriptions", "page": 2},
        "products_services": [{"name": "Managed annotation", "description": "per-unit pricing", "page": 2},
                              {"name": "Northwind QA", "description": "SaaS quality-review platform", "page": 2}]},
    3: {"revenue_mix": [
        {"dimension": "segment", "item": "Managed annotation services", "value": "68%", "year": "FY2024", "page": 3},
        {"dimension": "segment", "item": "Model evaluation services", "value": "20%", "year": "FY2024", "page": 3},
        {"dimension": "segment", "item": "Northwind QA SaaS", "value": "12%", "year": "FY2024", "page": 3},
        {"dimension": "geography", "item": "North America", "value": "61%", "year": "FY2024", "page": 3},
        {"dimension": "geography", "item": "Europe", "value": "27%", "year": "FY2024", "page": 3},
        {"dimension": "geography", "item": "India & APAC", "value": "12%", "year": "FY2024", "page": 3},
        {"dimension": "recurring vs one-off", "item": "Recurring", "value": "74%", "year": "FY2024", "page": 3}]},
    4: {"customer_mix": [
        {"metric": "Active customers", "value": "85", "page": 4},
        {"metric": "Top-10 customer share", "value": "58% of FY2024 revenue", "page": 4},
        {"metric": "Largest customer share", "value": "22% (global pharma)", "page": 4},
        {"metric": "Average tenure", "value": "5.1 years", "page": 4},
        {"metric": "Gross revenue retention", "value": "93% (FY2024)", "page": 4}]},
    5: {"financials": [
        {"metric": m, "period": p, "value": v, "unit": "USD mn",
         "type": "projected" if p.endswith("E") else "actual", "page": 5}
        for m, vals in {"Revenue": [31.0, 38.5, 46.2, 58.0, 72.5],
                        "Gross profit": [13.3, 16.9, 20.8, 26.7, 34.1],
                        "Adjusted EBITDA": [5.3, 7.3, 9.7, 13.3, 17.4],
                        "PAT": [2.4, 3.6, 5.1, 7.6, 10.4],
                        "Capex": [1.1, 1.5, 2.0, 2.6, 3.0]}.items()
        for p, v in zip(["FY2022", "FY2023", "FY2024", "FY2025E", "FY2026E"], vals)]
        + [{"metric": "Net debt", "period": "FY2024", "value": 4.0, "unit": "USD mn", "type": "actual", "page": 5}]},
    6: {"growth_drivers": [{"point": "Model-evaluation services for foundation-model developers", "page": 6},
                           {"point": "Upsell Northwind QA SaaS to services base", "page": 6}],
        "financials": [{"metric": "Revenue", "period": "FY2024", "value": 47.9, "unit": "USD mn",
                        "type": "actual", "page": 6}]},
    7: {"risks": [{"risk": "Key-person dependence on founder", "evidence": "CEO leads all top-5 relationships", "page": 7},
                  {"risk": "High annotator attrition", "evidence": "31% in FY2024", "page": 7},
                  {"risk": "Largest contract renewal Dec 2025", "evidence": "22% customer renews Dec 2025", "page": 7}]},
    8: {"deal_info": [{"item": "Transaction type", "value": "100% stake sale", "page": 8},
                      {"item": "Asking valuation", "value": "USD 180 mn enterprise value", "page": 8},
                      {"item": "Reason for sale", "value": "PE investor exit after 7-year hold", "page": 8}]},
}

SECTIONS = {
    "investment_highlights": {"about": "Northwind is a Pune-based provider of AI data annotation and model-evaluation services to life-sciences and publishing clients, with 640 staff across three delivery centres [p. 2]. Revenue is 74% recurring, driven by multi-year managed-service contracts and a SaaS QA platform [p. 3].",
                              "investment_highlights": ["74% recurring revenue [p. 3]", "Revenue grew from 31.0 to 46.2 USD mn FY2022-24 [p. 5]", "Exposure to foundation-model evaluation demand [p. 6]"]},
    "revenue_mix_commentary": {"revenue_mix_commentary": "Heavily weighted to labour-intensive managed annotation (68%) [p. 3]; SaaS is only 12%. North America dominates at 61%.",
                               "customer_mix_commentary": "Concentrated: top-10 are 58% and the largest client 22% of revenue [p. 4]. Retention of 93% is solid."},
    "financial_commentary": {"financial_commentary": "Revenue CAGR of ~22% with Adj. EBITDA margin expanding to 21.0% in FY2024. Projections assume acceleration to 25% growth, above history."},
    "most severe first": {"risks": [
        {"title": "Customer concentration", "detail": "Largest client is 22% of revenue and renews Dec 2025.", "severity": "High", "page": 4},
        {"title": "Key-person dependence", "detail": "Founder-CEO holds all top-5 relationships.", "severity": "High", "page": 7},
        {"title": "Automation pricing pressure", "detail": "Auto-labelling may compress per-unit prices.", "severity": "Medium", "page": 7},
        {"title": "Revenue figure inconsistency", "detail": "FY2024 revenue 46.2 vs 47.9 incl. one-off pass-through.", "severity": "Medium", "page": 6},
        {"title": "Talent attrition", "detail": "31% annotator attrition raises delivery cost.", "severity": "Low", "page": 7}]},
    "revenue_synergies": {"revenue_synergies": ["Cross-sell evaluation services to acquirer's customer base", "Bundle QA SaaS with existing products"],
                          "cost_synergies": ["Consolidate delivery centres", "Shared sales and G&A"],
                          "strategic_fit": "Adds AI evaluation capability; fit depends on acquirer's life-sciences exposure."},
    "diligence_questions": {"recommendation": "Proceed with caution",
                            "rationale": "Attractive growth and recurring mix, but 22% single-client exposure and founder dependence need testing; asking price of USD 180 mn is ~18.6x FY2024 Adj. EBITDA.",
                            "diligence_questions": ["What are the renewal terms and status of the largest contract?", "What is the one-off USD 1.7 mn pass-through?", "How are prices trending per annotated unit?", "Which relationships sit with non-founder staff?", "What drives the FY2025E growth acceleration?"],
                            "suggested_peers": ["Peer A", "Peer B"]},
}


class Handler(BaseHTTPRequestHandler):
    def _send(self, obj):
        body = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._send({"models": [{"name": "mock:latest"}, {"name": "gpt-oss:120b-cloud"}]})

    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        prompt = req["messages"][-1]["content"]
        if "Extract facts" in prompt:
            out = {}
            for pg in map(int, re.findall(r"=== PAGE (\d+) ===", prompt)):
                for k, v in PAGE_FACTS.get(pg, {}).items():
                    if isinstance(v, list):
                        out.setdefault(k, []).extend(v)
                    else:
                        out.setdefault(k, v)
        else:
            out = next((v for key, v in SECTIONS.items() if key in prompt), {})
        self._send({"message": {"role": "assistant", "content": "<think>x</think>" + json.dumps(out)}})

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", 11434), Handler).serve_forever()
