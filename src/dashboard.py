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

    # Dynamic column parsing to avoid any schema KeyErrors
    if "order_date" in orders.columns:
        orders["order_date"] = pd.to_datetime(orders["order_date"])

    for col in ["request_date", "created_at", "created_date"]:
        if col in returns.columns:
            returns[col] = pd.to_datetime(returns[col])
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

segments = ["ALL"] + sorted(raw_data["customers"]["customer_segment"].dropna().unique().tolist())
selected_segment = st.sidebar.selectbox("Customer Segment", segments)

filtered_customers = raw_data["customers"].copy()
if selected_segment != "ALL":
    filtered_customers = filtered_customers[filtered_customers["customer_segment"] == selected_segment]

valid_customer_ids = set(filtered_customers["customer_id"])

filtered_orders = raw_data["orders"][
    (raw_data["orders"]["order_date"].dt.date >= start_date)
    & (raw_data["orders"]["order_date"].dt.date <= end_date)
    & (raw_data["orders"]["customer_id"].isin(valid_customer_ids))
]
valid_order_ids = set(filtered_orders["order_id"])

filtered_order_lines = raw_data["order_lines"][
    raw_data["order_lines"]["order_id"].isin(valid_order_ids)
]

filtered_returns = raw_data["returns"][
    raw_data["returns"]["order_id"].isin(valid_order_ids)
]

# Identify return request ID column dynamically
rma_id_col = "return_request_id" if "return_request_id" in filtered_returns.columns else "return_id"
valid_rma_ids = set(filtered_returns[rma_id_col])

# Filter return lines
rl_col = "return_request_id" if "return_request_id" in raw_data["return_lines"].columns else "return_id"
filtered_return_lines = raw_data["return_lines"][
    raw_data["return_lines"][rl_col].isin(valid_rma_ids)
]

# Filter refunds
rf_col = "return_request_id" if "return_request_id" in raw_data["refunds"].columns else "return_id"
filtered_refunds = raw_data["refunds"][
    raw_data["refunds"][rf_col].isin(valid_rma_ids)
]

# ----------------- Header & KPIs -----------------
st.title("📦 E-Commerce Returns & Anomaly Analytics")
st.caption(f"Connected to `{DB_PATH.name}` | Seed: `{RANDOM_SEED}`")

total_orders_val = len(filtered_orders)
total_sales_val = filtered_orders["total_amount"].sum()
total_returns_val = len(filtered_returns)
total_refunded_val = filtered_refunds["net_refund_amount"].sum() if "net_refund_amount" in filtered_refunds.columns else 0.0
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
    if len(filtered_order_lines) > 0 and len(filtered_return_lines) > 0:
        merged_cat = filtered_order_lines.merge(
            filtered_return_lines[["order_line_id", "return_line_id"]],
            on="order_line_id",
            how="left",
        )
        cat_summary = merged_cat.groupby("category").agg(
            total_sold=("order_line_id", "count"),
            total_returned=("return_line_id", "count"),
            total_sales=("line_total", "sum"),
        ).reset_index()

        cat_summary["return_rate_pct"] = (
            (cat_summary["total_returned"] / cat_summary["total_sold"].replace(0, 1)) * 100
        ).round(2)

        c1, c2 = st.columns([3, 2])
        with c1:
            fig_cat = px.bar(
                cat_summary,
                x="category",
                y="return_rate_pct",
                text="return_rate_pct",
                title="Return Rate (%) by Category",
                labels={"return_rate_pct": "Return Rate (%)", "category": "Category"},
                color="category",
            )
            fig_cat.update_traces(texttemplate="%{text:.2f}%", textposition="outside")
            st.plotly_chart(fig_cat, use_container_width=True)

        with c2:
            st.write("### Category Sales & Returns Summary")
            st.dataframe(
                cat_summary.rename(columns={
                    "category": "Category",
                    "total_sold": "Sold Lines",
                    "total_returned": "Returned Lines",
                    "return_rate_pct": "Return Rate (%)",
                    "total_sales": "Gross Sales ($)",
                }),
                hide_index=True,
                use_container_width=True,
            )
    else:
        st.info("No order line records match the selected filter criteria.")

with tab2:
    st.subheader("Warehouse Inspection & Disposition Flow")
    c1, c2 = st.columns(2)

    with c1:
        grade_counts = raw_data["inspections"]["condition_grade"].value_counts().reset_index()
        grade_counts.columns = ["condition_grade", "count"]
        fig_grade = px.pie(
            grade_counts,
            names="condition_grade",
            values="count",
            title="Inspected Condition Grades",
            hole=0.4,
        )
        st.plotly_chart(fig_grade, use_container_width=True)

    with c2:
        disp_counts = raw_data["dispositions"]["disposition_action"].value_counts().reset_index()
        disp_counts.columns = ["disposition_action", "count"]
        fig_disp = px.bar(
            disp_counts,
            x="disposition_action",
            y="count",
            text="count",
            title="Inventory Disposition Actions",
            labels={"disposition_action": "Action", "count": "Processed Units"},
            color="disposition_action",
        )
        fig_disp.update_traces(textposition="outside")
        st.plotly_chart(fig_disp, use_container_width=True)

with tab3:
    st.subheader("Injected Operational Anomalies")
    gt = raw_data["ground_truth"]

    c1, c2 = st.columns([2, 3])
    with c1:
        anomaly_dist = gt["issue_type"].value_counts().reset_index()
        anomaly_dist.columns = ["issue_type", "count"]
        fig_anomaly = px.pie(
            anomaly_dist,
            names="issue_type",
            values="count",
            title="Anomaly Breakdown (210 Total)",
        )
        st.plotly_chart(fig_anomaly, use_container_width=True)

    with c2:
        st.write("### Filter Ground Truth Records")
        selected_issue = st.selectbox(
            "Filter by Anomaly Type:",
            options=["ALL"] + sorted(gt["issue_type"].unique().tolist()),
        )
        filtered_gt = gt if selected_issue == "ALL" else gt[gt["issue_type"] == selected_issue]
        st.dataframe(
            filtered_gt[[
                "entity_name", "record_id", "issue_type",
                "expected_decision", "description"
            ]],
            hide_index=True,
            use_container_width=True,
        )