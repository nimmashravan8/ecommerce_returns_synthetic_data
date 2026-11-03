"""
Interactive Streamlit Dashboard for Synthetic E-Commerce Returns Analytics.
Reads from output/ecommerce_returns.db to display operational KPIs,
return lifecycle distributions, and ground truth anomaly breakdowns.
"""
import sys
from pathlib import Path
import sqlite3
import streamlit as st
import pandas as pd
import plotly.express as px

# Resolve root directory path dynamically
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from src.config import CONFIG
    DB_PATH = CONFIG.OUTPUT_DIR / "ecommerce_returns.db"
    RANDOM_SEED = CONFIG.RANDOM_SEED
except Exception:
    DB_PATH = ROOT_DIR / "output" / "ecommerce_returns.db"
    RANDOM_SEED = 20261022

st.set_page_config(
    page_title="E-Commerce Returns & Anomaly Dashboard",
    page_icon="📦",
    layout="wide",
)


@st.cache_data
def load_data():
    if not DB_PATH.exists():
        st.error(f"Database not found at {DB_PATH}. Ensure 'output/ecommerce_returns.db' is committed.")
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

    conn.close()

    # Dynamic column parsing for orders
    for col in ["order_date", "created_at", "order_timestamp"]:
        if col in orders.columns:
            orders["order_date"] = pd.to_datetime(orders[col])
            break

    # Dynamic column parsing for returns
    for col in ["request_date", "created_at", "created_date", "return_date"]:
        if col in returns.columns:
            returns["request_date"] = pd.to_datetime(returns[col])
            break

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
st.sidebar.header("🔍 Filters")

# Safe Date Filter
if "order_date" in raw_data["orders"].columns and not raw_data["orders"]["order_date"].isna().all():
    min_date = raw_data["orders"]["order_date"].dt.date.min()
    max_date = raw_data["orders"]["order_date"].dt.date.max()

    date_range = st.sidebar.date_input(
        "Order Date Range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )

    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date, end_date = min_date, max_date
else:
    start_date, end_date = None, None

# Find customer segment column dynamically
cust_df = raw_data["customers"]
segment_col = next((c for c in ["customer_segment", "segment", "tier", "account_tier"] if c in cust_df.columns), None)

if segment_col:
    segments = ["ALL"] + sorted(cust_df[segment_col].dropna().unique().tolist())
    selected_segment = st.sidebar.selectbox("Customer Segment", segments)
    if selected_segment != "ALL":
        filtered_customers = cust_df[cust_df[segment_col] == selected_segment]
    else:
        filtered_customers = cust_df.copy()
else:
    filtered_customers = cust_df.copy()

cust_id_col = next((c for c in ["customer_id", "id"] if c in filtered_customers.columns), None)
valid_customer_ids = set(filtered_customers[cust_id_col]) if cust_id_col else set()

# Filter orders
orders_df = raw_data["orders"].copy()
if start_date and end_date and "order_date" in orders_df.columns:
    orders_df = orders_df[
        (orders_df["order_date"].dt.date >= start_date)
        & (orders_df["order_date"].dt.date <= end_date)
    ]
if cust_id_col and cust_id_col in orders_df.columns:
    orders_df = orders_df[orders_df[cust_id_col].isin(valid_customer_ids)]

filtered_orders = orders_df
order_id_col = next((c for c in ["order_id", "id"] if c in filtered_orders.columns), "order_id")
valid_order_ids = set(filtered_orders[order_id_col]) if order_id_col in filtered_orders.columns else set()

# Filter order lines
ol_order_id = next((c for c in ["order_id", "order_fk"] if c in raw_data["order_lines"].columns), None)
filtered_order_lines = raw_data["order_lines"][
    raw_data["order_lines"][ol_order_id].isin(valid_order_ids)
] if ol_order_id else raw_data["order_lines"]

# Filter returns
ret_order_id = next((c for c in ["order_id", "order_fk"] if c in raw_data["returns"].columns), None)
filtered_returns = raw_data["returns"][
    raw_data["returns"][ret_order_id].isin(valid_order_ids)
] if ret_order_id else raw_data["returns"]

# Dynamic RMA ID column detection
rma_id_col = next((c for c in ["return_request_id", "return_id", "id"] if c in filtered_returns.columns), None)
valid_rma_ids = set(filtered_returns[rma_id_col]) if rma_id_col else set()

# Filter return lines
rl_rma_col = next((c for c in ["return_request_id", "return_id", "return_fk"] if c in raw_data["return_lines"].columns), None)
filtered_return_lines = raw_data["return_lines"][
    raw_data["return_lines"][rl_rma_col].isin(valid_rma_ids)
] if rl_rma_col else raw_data["return_lines"]

# Filter refunds
rf_rma_col = next((c for c in ["return_request_id", "return_id", "return_fk"] if c in raw_data["refunds"].columns), None)
filtered_refunds = raw_data["refunds"][
    raw_data["refunds"][rf_rma_col].isin(valid_rma_ids)
] if rf_rma_col else raw_data["refunds"]

# ----------------- Header & KPIs -----------------
st.title("📦 E-Commerce Returns & Anomaly Analytics")
st.caption(f"Connected to `{DB_PATH.name}` | Seed: `{RANDOM_SEED}`")

total_orders_val = len(filtered_orders)
sales_col = next((c for c in ["total_amount", "order_total", "total", "subtotal"] if c in filtered_orders.columns), None)
total_sales_val = filtered_orders[sales_col].sum() if sales_col else 0.0

total_returns_val = len(filtered_returns)
refund_col = next((c for c in ["net_refund_amount", "refund_amount", "amount"] if c in filtered_refunds.columns), None)
total_refunded_val = filtered_refunds[refund_col].sum() if refund_col else 0.0

total_anomalies_val = len(raw_data["ground_truth"])

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Total Orders", f"{total_orders_val:,}")
col2.metric("Gross Sales", f"${total_sales_val:,.2f}")
col3.metric("Return Requests", f"{total_returns_val:,}")
col4.metric("Net Refunds", f"${total_refunded_val:,.2f}")
col5.metric("Anomalies Injected", f"{total_anomalies_val:,}")

st.divider()

# ----------------- Tabbed Views -----------------
tab1, tab2, tab3 = st.tabs([
    "📊 Category & Return Trends",
    "🏭 Warehouse & Disposition",
    "🚨 Anomaly Detection (Ground Truth)",
])

with tab1:
    st.subheader("Return Rate by Product Category")
    cat_col = next((c for c in ["category", "product_category"] if c in filtered_order_lines.columns), None)
    ol_id_col = next((c for c in ["order_line_id", "line_id", "id"] if c in filtered_order_lines.columns), None)

    if cat_col and ol_id_col and len(filtered_order_lines) > 0:
        rl_match_col = next((c for c in ["order_line_id", "line_id"] if c in filtered_return_lines.columns), None)
        ret_pk = next((c for c in ["return_line_id", "id"] if c in filtered_return_lines.columns), None)

        if rl_match_col and ret_pk:
            merged_cat = filtered_order_lines.merge(
                filtered_return_lines[[rl_match_col, ret_pk]],
                left_on=ol_id_col,
                right_on=rl_match_col,
                how="left",
            )
            line_tot_col = next((c for c in ["line_total", "total", "price"] if c in merged_cat.columns), None)
            
            agg_dict = {
                "total_sold": (ol_id_col, "count"),
                "total_returned": (ret_pk, "count"),
            }
            if line_tot_col:
                agg_dict["total_sales"] = (line_tot_col, "sum")

            cat_summary = merged_cat.groupby(cat_col).agg(**agg_dict).reset_index()
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
                st.dataframe(cat_summary, hide_index=True, use_container_width=True)
        else:
            st.info("Return line join keys not found in schema.")
    else:
        st.info("No order line records match the selected filter criteria.")

with tab2:
    st.subheader("Warehouse Inspection & Disposition Flow")
    c1, c2 = st.columns(2)

    with c1:
        grade_col = next((c for c in ["condition_grade", "grade", "condition"] if c in raw_data["inspections"].columns), None)
        if grade_col:
            grade_counts = raw_data["inspections"][grade_col].value_counts().reset_index()
            grade_counts.columns = [grade_col, "count"]
            fig_grade = px.pie(
                grade_counts,
                names=grade_col,
                values="count",
                title="Inspected Condition Grades",
                hole=0.4,
            )
            st.plotly_chart(fig_grade, use_container_width=True)
        else:
            st.info("Inspection grade column not found.")

    with c2:
        disp_col = next((c for c in ["disposition_action", "action", "disposition"] if c in raw_data["dispositions"].columns), None)
        if disp_col:
            disp_counts = raw_data["dispositions"][disp_col].value_counts().reset_index()
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
            st.info("Disposition action column not found.")

with tab3:
    st.subheader("Injected Operational Anomalies")
    gt = raw_data["ground_truth"]

    issue_col = next((c for c in ["issue_type", "anomaly_type", "type"] if c in gt.columns), None)

    if issue_col:
        c1, c2 = st.columns([2, 3])
        with c1:
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
            selected_issue = st.selectbox(
                "Filter by Anomaly Type:",
                options=["ALL"] + sorted(gt[issue_col].unique().tolist()),
            )
            filtered_gt = gt if selected_issue == "ALL" else gt[gt[issue_col] == selected_issue]
            st.dataframe(filtered_gt, hide_index=True, use_container_width=True)
    else:
        st.dataframe(gt, hide_index=True, use_container_width=True)