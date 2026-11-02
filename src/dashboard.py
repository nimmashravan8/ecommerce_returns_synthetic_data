"""
Interactive Streamlit Dashboard for Synthetic E-Commerce Returns Analytics.
Includes dynamic Date Range filtering, Customer Segment drill-downs, and CSV exports.
"""
from pathlib import Path
import sqlite3
import pandas as pd
import plotly.express as px
import streamlit as st

# Locate the project directories robustly
BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "output"
DB_PATH = OUTPUT_DIR / "ecommerce_returns.db"
RANDOM_SEED = 20261022

st.set_page_config(
    page_title="E-Commerce Returns & Anomaly Dashboard",
    page_icon="📦",
    layout="wide",
)


@st.cache_data
def load_data():
    if not DB_PATH.exists():
        st.error(
            f"Database file not found at: {DB_PATH}\n\n"
            f"Ensure output/ecommerce_returns.db is committed and pushed to GitHub."
        )
        st.stop()

    conn = sqlite3.connect(DB_PATH)

    customers = pd.read_sql_query("SELECT * FROM customers", conn)
    orders = pd.read_sql_query("SELECT * FROM orders", conn)
    order_lines = pd.read_sql_query("SELECT * FROM order_lines", conn)
    returns = pd.read_sql_query("SELECT * FROM return_requests", conn)
    return_lines = pd.read_sql_query("SELECT * FROM return_lines", conn)
    inspections = pd.read_sql_query("SELECT * FROM inspections", conn)
    dispositions = pd.read_sql_query("SELECT * FROM inventory_dispositions", conn)
    refunds = pd.read_sql_query("SELECT * FROM refunds", conn)
    ground_truth = pd.read_sql_query("SELECT * FROM ground_truth", conn)

    # Ensure datetime conversions
    date_col = next((c for c in ["order_date", "created_at", "order_timestamp"] if c in orders.columns), None)
    if date_col:
        orders["parsed_order_date"] = pd.to_datetime(orders[date_col]).dt.date

    # Optional catalog join if category is not already in order_lines
    if "category" not in order_lines.columns:
        products = pd.read_sql_query("SELECT sku_id, category FROM products", conn)
        order_lines = order_lines.merge(products, on="sku_id", how="left")

    conn.close()
    return {
        "customers": customers,
        "orders": orders,
        "order_lines": order_lines,
        "returns": returns,
        "return_lines": return_lines,
        "inspections": inspections,
        "dispositions": dispositions,
        "refunds": refunds,
        "ground_truth": ground_truth,
    }


raw_data = load_data()

# ----------------- Sidebar Filters -----------------
st.sidebar.header("🔍 Global Analytics Filters")

# 1. Date Range Filter
if "parsed_order_date" in raw_data["orders"].columns:
    min_date = raw_data["orders"]["parsed_order_date"].min()
    max_date = raw_data["orders"]["parsed_order_date"].max()
    selected_date_range = st.sidebar.date_input(
        "Order Date Range:",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )
else:
    selected_date_range = None

# 2. Customer Segment Drill-down
segment_col = next((c for c in ["customer_segment", "segment", "loyalty_tier", "tier"] if c in raw_data["customers"].columns), None)
if segment_col:
    all_segments = ["ALL"] + sorted(list(raw_data["customers"][segment_col].dropna().unique()))
    selected_segment = st.sidebar.selectbox("Customer Segment:", options=all_segments)
else:
    selected_segment = "ALL"

# ----------------- Filter Application -----------------
# Filter Orders by Customer Segment
if segment_col and selected_segment != "ALL":
    valid_customer_ids = raw_data["customers"][raw_data["customers"][segment_col] == selected_segment]["customer_id"]
    filtered_orders = raw_data["orders"][raw_data["orders"]["customer_id"].isin(valid_customer_ids)]
else:
    filtered_orders = raw_data["orders"].copy()

# Filter Orders by Date Range
if selected_date_range and len(selected_date_range) == 2:
    start_d, end_d = selected_date_range
    filtered_orders = filtered_orders[
        (filtered_orders["parsed_order_date"] >= start_d) & 
        (filtered_orders["parsed_order_date"] <= end_d)
    ]

# Downstream Cascading Filters
valid_order_ids = set(filtered_orders["order_id"])
filtered_order_lines = raw_data["order_lines"][raw_data["order_lines"]["order_id"].isin(valid_order_ids)]
filtered_returns = raw_data["returns"][raw_data["returns"]["order_id"].isin(valid_order_ids)]
valid_rma_ids = set(filtered_returns["return_id"])
filtered_return_lines = raw_data["return_lines"][raw_data["return_lines"]["return_id"].isin(valid_rma_ids)]
valid_rmal_ids = set(filtered_return_lines["return_line_id"])
filtered_inspections = raw_data["inspections"][raw_data["inspections"]["return_line_id"].isin(valid_rmal_ids)]
filtered_dispositions = raw_data["dispositions"][raw_data["dispositions"]["return_line_id"].isin(valid_rmal_ids)]
filtered_refunds = raw_data["refunds"][raw_data["refunds"]["return_id"].isin(valid_rma_ids)]

# ----------------- Header & KPIs -----------------
st.title("📦 E-Commerce Returns & Anomaly Analytics")
st.caption(f"Connected to `{DB_PATH.name}` | Deterministic Seed: `{RANDOM_SEED}`")

total_orders = len(filtered_orders)

sales_candidates = ["order_total", "total_amount", "total_amount_usd", "total", "grand_total", "order_value"]
sales_col = next((c for c in sales_candidates if c in filtered_orders.columns), None)
if sales_col:
    total_sales = float(filtered_orders[sales_col].sum())
elif "line_total" in filtered_order_lines.columns:
    total_sales = float(filtered_order_lines["line_total"].sum())
else:
    total_sales = 0.0

total_returns = len(filtered_returns)

refund_candidates = ["net_refund_amount", "refund_amount", "net_amount", "total_refund"]
refund_col = next((c for c in refund_candidates if c in filtered_refunds.columns), None)
total_refunded = float(filtered_refunds[refund_col].sum()) if refund_col else 0.0

total_anomalies = len(raw_data["ground_truth"])

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Filtered Orders", f"{total_orders:,}")
col2.metric("Gross Sales", f"${total_sales:,.2f}")
col3.metric("Return Requests", f"{total_returns:,}")
col4.metric("Net Refunds", f"${total_refunded:,.2f}")
col5.metric("Anomalies Injected", f"{total_anomalies:,}")

st.divider()

# ----------------- Tabbed Views -----------------
tab1, tab2, tab3 = st.tabs([
    "📊 Category & Return Trends",
    "🏭 Warehouse & Disposition",
    "🚨 Anomaly Detection (Ground Truth)",
])

with tab1:
    st.subheader("Return Rate by Product Category")

    merged_cat = filtered_order_lines.merge(
        filtered_return_lines[["order_line_id", "return_line_id"]],
        on="order_line_id",
        how="left",
    )

    cat_col = "category" if "category" in merged_cat.columns else merged_cat.columns[1]

    cat_summary = merged_cat.groupby(cat_col).agg(
        total_sold=("order_line_id", "count"),
        total_returned=("return_line_id", "count"),
        total_sales=("line_total", "sum") if "line_total" in merged_cat.columns else ("order_line_id", "count"),
    ).reset_index()

    cat_summary["return_rate_pct"] = (
        (cat_summary["total_returned"] / cat_summary["total_sold"].replace(0, 1)) * 100
    ).round(2)

    c1, c2 = st.columns([3, 2])
    with c1:
        fig_cat = px.bar(
            cat_summary,
            x=cat_col,
            y="return_rate_pct",
            text="return_rate_pct",
            title="Return Rate (%) by Category",
            labels={"return_rate_pct": "Return Rate (%)", cat_col: "Category"},
            color=cat_col,
        )
        fig_cat.update_traces(texttemplate="%{text:.2f}%", textposition="outside")
        st.plotly_chart(fig_cat, use_container_width=True)

    with c2:
        st.write("### Category Sales & Returns Summary")
        renamed_summary = cat_summary.rename(
            columns={
                cat_col: "Category",
                "total_sold": "Sold Lines",
                "total_returned": "Returned Lines",
                "return_rate_pct": "Return Rate (%)",
                "total_sales": "Gross Sales ($)",
            }
        )
        st.dataframe(renamed_summary, hide_index=True, use_container_width=True)

with tab2:
    st.subheader("Warehouse Inspection & Disposition Flow")
    c1, c2 = st.columns(2)

    with c1:
        cond_col = next(
            (c for c in ["item_condition", "condition_grade", "condition", "grade"] if c in filtered_inspections.columns),
            None,
        )
        if cond_col and len(filtered_inspections) > 0:
            grade_counts = filtered_inspections[cond_col].value_counts().reset_index()
            grade_counts.columns = [cond_col, "count"]
            fig_grade = px.pie(
                grade_counts,
                names=cond_col,
                values="count",
                title="Inspected Condition Grades",
                hole=0.4,
            )
            st.plotly_chart(fig_grade, use_container_width=True)
        else:
            st.info("No inspection records found for the selected filter.")

    with c2:
        disp_col = next(
            (c for c in ["disposition_action", "action", "disposition"] if c in filtered_dispositions.columns),
            None,
        )
        if disp_col and len(filtered_dispositions) > 0:
            disp_counts = filtered_dispositions[disp_col].value_counts().reset_index()
            disp_counts.columns = [disp_col, "count"]
            fig_disp = px.bar(
                disp_counts,
                x=disp_col,
                y="count",
                text="count",
                title="Inventory Disposition Actions",
                labels={disp_col: "Action", "count": "Processed Units"},
                color=disp_col,
            )
            fig_disp.update_traces(textposition="outside")
            st.plotly_chart(fig_disp, use_container_width=True)
        else:
            st.info("No disposition records found for the selected filter.")

with tab3:
    st.subheader("Injected Operational Anomalies")
    gt = raw_data["ground_truth"]

    c1, c2 = st.columns([2, 3])
    with c1:
        issue_col = next((c for c in ["issue_type", "anomaly_type", "type"] if c in gt.columns), None)
        if issue_col:
            anomaly_dist = gt[issue_col].value_counts().reset_index()
            anomaly_dist.columns = [issue_col, "count"]
            fig_anomaly = px.pie(
                anomaly_dist,
                names=issue_col,
                values="count",
                title=f"Anomaly Breakdown ({len(gt)} Total)",
            )
            st.plotly_chart(fig_anomaly, use_container_width=True)

    with c2:
        st.write("### Filter Ground Truth Records")
        if issue_col:
            selected_issue = st.selectbox(
                "Filter by Anomaly Type:",
                options=["ALL"] + list(gt[issue_col].unique()),
            )
            filtered_gt = gt if selected_issue == "ALL" else gt[gt[issue_col] == selected_issue]
        else:
            filtered_gt = gt

        desired_cols = ["entity_name", "record_id", "issue_type", "expected_decision", "description"]
        display_columns = [c for c in desired_cols if c in filtered_gt.columns]
        st.dataframe(filtered_gt[display_columns], hide_index=True, use_container_width=True)