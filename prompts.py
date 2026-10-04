"""
All prompts in one place, so they are easy to read, show and tweak.

Two stages:
  1. EXTRACT: run on each chunk of the CIM. Pulls facts out as JSON, each with
     the page number it came from. No opinions at this stage.
  2. WRITE: run once per report section on the merged fact sheet. Writes short
     analyst prose. Numbers are computed in Python beforehand and passed in,
     so the model does not do arithmetic.
"""

EXTRACT_SYSTEM = """You are a meticulous M&A analyst extracting facts from a
Confidential Information Memorandum (CIM). Rules:
- Use ONLY the text provided. Never use outside knowledge. Never guess.
- Every item must carry the page number shown in the nearest '=== PAGE n ===' marker.
- Copy numbers exactly as written, with their unit and currency (e.g. "USD mn", "INR crore", "%").
- If something is not in the text, leave the list empty or the field null.
- Output a single JSON object and nothing else."""

EXTRACT_USER = """Extract facts from this part of the CIM into exactly this JSON shape:

{{
  "company": {{"name": null, "headquarters": null, "founded": null, "employees": null,
              "description": null, "business_model": null, "page": null}},
  "products_services": [{{"name": "", "description": "", "page": 0}}],
  "revenue_mix": [{{"dimension": "segment|geography|product|channel|recurring vs one-off",
                   "item": "", "value": "", "year": "", "page": 0}}],
  "customer_mix": [{{"metric": "e.g. number of customers, top-10 share, largest customer share, retention, customer segments, contract length",
                    "value": "", "page": 0}}],
  "financials": [{{"metric": "Revenue|Gross profit|EBITDA|Adjusted EBITDA|EBIT|PAT|Capex|Free cash flow|Net debt",
                  "period": "e.g. FY2024 or LTM Jun-2025", "value": 0, "unit": "e.g. USD mn",
                  "type": "actual|projected", "page": 0}}],
  "growth_drivers": [{{"point": "", "page": 0}}],
  "risks": [{{"risk": "", "evidence": "short quote or fact", "page": 0}}],
  "deal_info": [{{"item": "e.g. transaction type, stake offered, asking price, reason for sale, process timeline",
                 "value": "", "page": 0}}]
}}

Notes:
- 'value' in financials must be a plain number (no commas, no units). Negative numbers for losses.
- Mark forecasts/budgets/projections as type "projected".
- Include risks the CIM states AND concrete warning signs visible in the facts
  (e.g. customer concentration, falling margins, key-person dependence, debt).

CIM TEXT:
{chunk}"""


WRITE_SYSTEM = """You are a senior corporate development analyst writing a
first-screen investment memo for an internal deal committee. Rules:
- Base every statement on the FACT SHEET provided. Do not invent facts or numbers.
- Use only numbers that appear in the fact sheet. Do not calculate new ones.
- Cite pages inline like [p. 12] when the fact sheet gives a page.
- Be crisp and specific. No filler, no marketing language.
- If information is missing, say so plainly - gaps matter in a screen.
- Output a single JSON object and nothing else."""

SECTION_PROMPTS = {
    "overview": """Using the fact sheet, return:
{{"about": "what the company does, for whom, how it makes money, scale - max 110 words, with page cites",
  "investment_highlights": ["3-4 bullets, max 20 words each, with page cites"]}}

FACT SHEET:
{facts}""",

    "mix": """Using the fact sheet, return:
{{"revenue_mix_commentary": "what the revenue mix says about quality, diversification and growth - max 70 words",
  "customer_mix_commentary": "concentration, stickiness, segments - max 70 words; flag missing data"}}

FACT SHEET:
{facts}""",

    "financials": """The financial table and derived metrics below were computed from the CIM.
Return:
{{"financial_commentary": "growth trajectory, margin trend, cash conversion, credibility of projections vs history - max 90 words"}}

FACT SHEET:
{facts}""",

    "risks": """Using the fact sheet, identify the most important risks and challenges for an acquirer.
Return up to 6, most severe first:
{{"risks": [{{"title": "max 6 words", "detail": "max 30 words, specific to this company",
              "severity": "High|Medium|Low", "page": 0}}]}}

FACT SHEET:
{facts}""",

    "synergies": """ACQUIRER PROFILE (who is considering buying the company):
{acquirer}

Using the fact sheet and the acquirer profile, return hypotheses to test in diligence:
{{"revenue_synergies": ["up to 3, max 25 words each"],
  "cost_synergies": ["up to 3, max 25 words each"],
  "strategic_fit": "max 50 words on why this does or does not fit the acquirer"}}
If the acquirer profile is empty, give generic synergy hypotheses for a strategic buyer in the same industry.

FACT SHEET:
{facts}""",

    "verdict": """Using the fact sheet, give the first-screen view.
Return:
{{"recommendation": "Proceed to next stage|Proceed with caution|Pass",
  "rationale": "max 60 words",
  "diligence_questions": ["5-6 sharp questions for management, max 20 words each"],
  "suggested_peers": ["up to 6 listed companies that could serve as valuation comparables"]}}

FACT SHEET:
{facts}""",
}
