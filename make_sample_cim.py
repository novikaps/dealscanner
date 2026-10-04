"""Creates tests/sample_cim.pdf: a short CIM for a FICTIONAL company, for testing."""
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table

S = getSampleStyleSheet()
P = lambda t: Paragraph(t, S["BodyText"])
H = lambda t: Paragraph(t, S["Heading2"])

pages = [
    [Paragraph("Project Falcon - Confidential Information Memorandum", S["Title"]),
     P("Northwind Analytics Pvt. Ltd. (fictional company for testing). Strictly confidential. "
       "Prepared by the sell-side advisor for a limited set of prospective buyers.")],
    [H("1. Company overview"),
     P("Northwind Analytics is a Pune-headquartered provider of AI-enabled data annotation and model "
       "evaluation services for life-sciences and publishing clients. Founded in 2014, the company "
       "employs 640 people across Pune, Manila and Boston. It sells multi-year managed-service contracts "
       "priced per annotated unit, plus a SaaS quality-review platform (Northwind QA) on annual subscriptions."),
     P("Business model: managed services (per-unit pricing) and SaaS subscriptions.")],
    [H("2. Revenue mix"),
     Table([["Segment", "FY2024 share"], ["Managed annotation services", "68%"],
            ["Model evaluation services", "20%"], ["Northwind QA SaaS", "12%"]]),
     Spacer(1, 10),
     Table([["Geography", "FY2024 share"], ["North America", "61%"], ["Europe", "27%"], ["India & APAC", "12%"]]),
     P("Recurring revenue (SaaS plus multi-year contracts) was 74% of FY2024 revenue.")],
    [H("3. Customers"),
     P("Northwind serves 85 active customers. The top 10 customers contributed 58% of FY2024 revenue, "
       "and the largest customer, a global pharmaceutical company, contributed 22%. Average customer "
       "tenure is 5.1 years; gross revenue retention was 93% in FY2024.")],
    [H("4. Historical and projected financials (USD mn)"),
     Table([["USD mn", "FY2022", "FY2023", "FY2024", "FY2025E", "FY2026E"],
            ["Revenue", "31.0", "38.5", "46.2", "58.0", "72.5"],
            ["Gross profit", "13.3", "16.9", "20.8", "26.7", "34.1"],
            ["Adjusted EBITDA", "5.3", "7.3", "9.7", "13.3", "17.4"],
            ["PAT", "2.4", "3.6", "5.1", "7.6", "10.4"],
            ["Capex", "1.1", "1.5", "2.0", "2.6", "3.0"]]),
     P("Net debt as of March 2024 was USD 4.0 mn.")],
    [H("5. Growth strategy and investment highlights"),
     P("Growth drivers: expansion of model-evaluation services for foundation-model developers; upsell of "
       "Northwind QA SaaS to the managed-services base; opening a delivery centre in Kraków."),
     P("Note: revenue for FY2024 of USD 47.9 mn in the management presentation includes a one-off "
       "pass-through billing of USD 1.7 mn.")],
    [H("6. Key considerations"),
     P("Founder and CEO Ravi Menon leads all top-5 client relationships. Attrition among annotators was 31% "
       "in FY2024. Pricing pressure is expected as clients adopt automated labelling. The largest customer "
       "contract comes up for renewal in December 2025.")],
    [H("7. Transaction"),
     P("The shareholders are inviting proposals for a 100% stake. Indicative valuation expectation: "
       "USD 180 mn enterprise value. Reason for sale: private-equity investor exit after a 7-year hold. "
       "Non-binding offers due by 15 November 2026.")],
]


def main():
    out = Path(__file__).with_name("sample_cim.pdf")
    story = []
    for i, p in enumerate(pages):
        story += p + ([PageBreak()] if i < len(pages) - 1 else [])
    SimpleDocTemplate(str(out), pagesize=A4).build(story)
    print(out)


if __name__ == "__main__":
    main()
