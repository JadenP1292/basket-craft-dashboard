import os
from datetime import date

import pandas as pd
import snowflake.connector
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Basket Craft — Merchandising Dashboard", layout="wide")


# ── Snowflake connection ───────────────────────────────────────────────────────

def _sf(key: str) -> str:
    """Read from st.secrets (Streamlit Cloud) then fall back to env var (local)."""
    try:
        val = st.secrets.get(key)
    except Exception:
        val = None
    return val or os.getenv(key, "")


@st.cache_resource
def get_connection():
    return snowflake.connector.connect(
        account=_sf("SNOWFLAKE_ACCOUNT"),
        user=_sf("SNOWFLAKE_USER"),
        password=_sf("SNOWFLAKE_PASSWORD"),
        role=_sf("SNOWFLAKE_ROLE"),
        warehouse=_sf("SNOWFLAKE_WAREHOUSE"),
        database=_sf("SNOWFLAKE_DATABASE"),
        schema=_sf("SNOWFLAKE_SCHEMA"),
    )


@st.cache_data(ttl=600)
def run_query(sql: str, params: tuple = ()) -> pd.DataFrame:
    conn = get_connection()
    cs = conn.cursor()
    cs.execute(sql, params)
    cols = [d[0].lower() for d in cs.description]
    df = pd.DataFrame(cs.fetchall(), columns=cols)
    cs.close()
    return df


# ── Queries ───────────────────────────────────────────────────────────────────

@st.cache_data(ttl=600)
def load_kpis() -> pd.DataFrame:
    return run_query("""
        WITH monthly AS (
            SELECT
                DATE_TRUNC('MONTH', o.order_date)                                  AS month,
                SUM(oi.line_total)                                                  AS revenue,
                COUNT(DISTINCT o.order_id)                                          AS orders,
                SUM(oi.quantity)                                                    AS items_sold,
                ROUND(SUM(oi.line_total) / NULLIF(COUNT(DISTINCT o.order_id), 0), 2) AS aov
            FROM orders o
            JOIN order_items oi ON o.order_id = oi.order_id
            GROUP BY 1
            ORDER BY 1 DESC
            LIMIT 2
        )
        SELECT * FROM monthly ORDER BY month DESC
    """)


@st.cache_data(ttl=600)
def load_trend(start: str, end: str) -> pd.DataFrame:
    return run_query("""
        SELECT
            DATE_TRUNC('MONTH', o.order_date) AS month,
            SUM(oi.line_total)                AS revenue
        FROM orders o
        JOIN order_items oi ON o.order_id = oi.order_id
        WHERE o.order_date BETWEEN %s AND %s
        GROUP BY 1
        ORDER BY 1
    """, (start, end))


@st.cache_data(ttl=600)
def load_top_products(start: str, end: str) -> pd.DataFrame:
    return run_query("""
        SELECT
            p.product_name,
            SUM(oi.line_total) AS revenue
        FROM order_items oi
        JOIN products p ON oi.product_id = p.product_id
        JOIN orders   o ON oi.order_id   = o.order_id
        WHERE o.order_date BETWEEN %s AND %s
        GROUP BY 1
        ORDER BY 2 DESC
    """, (start, end))


@st.cache_data(ttl=600)
def load_products() -> pd.DataFrame:
    return run_query("SELECT product_id, product_name FROM products ORDER BY product_name")


@st.cache_data(ttl=600)
def load_bundles(product_id: int) -> pd.DataFrame:
    return run_query("""
        SELECT
            p.product_name             AS also_bought,
            COUNT(DISTINCT a.order_id) AS co_order_count
        FROM order_items a
        JOIN order_items b ON a.order_id   = b.order_id
                          AND a.product_id != b.product_id
        JOIN products    p ON a.product_id = p.product_id
        WHERE b.product_id = %s
        GROUP BY 1
        ORDER BY 2 DESC
    """, (product_id,))


# ── Sidebar date filter ───────────────────────────────────────────────────────

st.sidebar.header("Filters")
date_range = st.sidebar.date_input(
    "Date range",
    value=(date(2023, 1, 1), date.today()),
    min_value=date(2020, 1, 1),
    max_value=date.today(),
)
if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    start_date, end_date = str(date_range[0]), str(date_range[1])
else:
    start_date = end_date = str(date_range[0] if isinstance(date_range, (list, tuple)) else date_range)

# ── Title ─────────────────────────────────────────────────────────────────────

st.title("Basket Craft — Merchandising Dashboard")

# ── Section 1: KPI Scorecards ─────────────────────────────────────────────────

st.subheader("Key Metrics")
kpis = load_kpis()

if not kpis.empty:
    cur  = kpis.iloc[0]
    prev = kpis.iloc[1] if len(kpis) >= 2 else None

    def mom_delta(cur_val, prev_val):
        if prev_val is not None and prev_val != 0:
            return f"{(cur_val - prev_val) / prev_val * 100:.1f}%"
        return None

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Revenue",         f"${cur['revenue']:,.0f}",   mom_delta(cur['revenue'],    prev['revenue']    if prev is not None else None))
    c2.metric("Orders",          f"{int(cur['orders']):,}",   mom_delta(cur['orders'],     prev['orders']     if prev is not None else None))
    c3.metric("Avg Order Value", f"${cur['aov']:,.2f}",       mom_delta(cur['aov'],        prev['aov']        if prev is not None else None))
    c4.metric("Items Sold",      f"{int(cur['items_sold']):,}", mom_delta(cur['items_sold'], prev['items_sold'] if prev is not None else None))

# ── Section 2: Revenue Trend ──────────────────────────────────────────────────

st.subheader("Revenue Trend")
trend = load_trend(start_date, end_date)
if not trend.empty:
    trend["month"] = pd.to_datetime(trend["month"])
    st.line_chart(trend.set_index("month")["revenue"])
else:
    st.info("No data for the selected date range.")

# ── Section 3: Top Products by Revenue ───────────────────────────────────────

st.subheader("Top Products by Revenue")
top = load_top_products(start_date, end_date)
if not top.empty:
    st.bar_chart(top.set_index("product_name")["revenue"])
else:
    st.info("No data for the selected date range.")

# ── Section 4: Bundle Finder ──────────────────────────────────────────────────

st.subheader("Bundle Finder: Bought With…")
products = load_products()
if not products.empty:
    product_map = dict(zip(products["product_name"], products["product_id"]))
    selected = st.selectbox("Pick a product", list(product_map.keys()))
    bundles = load_bundles(int(product_map[selected]))
    if not bundles.empty:
        bundles.columns = ["Also Bought", "# of Orders"]
        st.dataframe(bundles, use_container_width=True, hide_index=True)
        csv_bytes = bundles.to_csv(index=False).encode()
        st.download_button("Download CSV", csv_bytes, "bundles.csv", "text/csv")
    else:
        st.info("No co-purchase data found for this product.")
