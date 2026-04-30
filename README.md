# Basket Craft — Merchandising Dashboard

**Live app:** <!-- PASTE YOUR STREAMLIT CLOUD URL HERE AFTER DEPLOYING -->

A Streamlit dashboard backed by Snowflake that answers Maya (Head of Merchandising) two core questions:
- Which products drove the most revenue?
- Which products get bought together — and should we bundle them?

## Dashboard sections

| Section | Type | What it shows |
|---|---|---|
| Key Metrics | Descriptive | Revenue, orders, AOV, items sold with MoM delta |
| Revenue Trend | Descriptive | Monthly revenue over time; filterable by date |
| Top Products by Revenue | Diagnostic | Bar chart of products ranked by revenue |
| Bundle Finder | Diagnostic + Act | Co-purchase partners for any product; CSV export |

## Run locally

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Requires a `.env` file with your Snowflake credentials (see `.env.example`).
