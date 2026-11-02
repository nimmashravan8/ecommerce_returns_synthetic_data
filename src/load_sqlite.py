"""
Loads generated synthetic e-commerce returns CSV files into an SQLite database
and executes analytical SQL queries to demonstrate reporting workflows.
"""
import sqlite3
from pathlib import Path
import pandas as pd

from src.config import CONFIG

DB_PATH = CONFIG.OUTPUT_DIR / "ecommerce_returns.db"


def load_csvs_to_sqlite(output_dir: Path, db_path: Path):
    """Iterate through all CSV files in output/ and load into SQLite tables."""
    csv_files = list(output_dir.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {output_dir}")

    # Remove existing database file for a clean rebuild
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)

    print(f"Loading {len(csv_files)} tables into SQLite ({db_path.name})...")
    for csv_file in sorted(csv_files):
        table_name = csv_file.stem
        df = pd.read_csv(csv_file)
        df.to_sql(table_name, conn, if_exists="replace", index=False)
        print(f"  -> {table_name:25s} | {len(df):>7,d} rows loaded")

    # Add indexes on high-cardinality join keys
    print("\nCreating relational indexes...")
    index_queries = [
        "CREATE INDEX idx_orders_cust ON orders(customer_id);",
        "CREATE INDEX idx_order_lines_ord ON order_lines(order_id);",
        "CREATE INDEX idx_order_lines_sku ON order_lines(sku_id);",
        "CREATE INDEX idx_rmas_order ON return_requests(order_id);",
        "CREATE INDEX idx_rmals_rma ON return_lines(return_request_id);",
        "CREATE INDEX idx_rmals_ol ON return_lines(order_line_id);",
        "CREATE INDEX idx_inspections_rts ON inspections(shipment_id);",
        "CREATE INDEX idx_dispositions_ins ON inventory_dispositions(inspection_id);",
        "CREATE INDEX idx_refunds_rma ON refunds(return_request_id);",
    ]
    with conn:
        for idx_sql in index_queries:
            conn.execute(idx_sql)
    print("Relational indexes created successfully.")

    conn.close()


def run_analytical_queries(db_path: Path):
    """Executes cross-table analytics using SQL and pandas."""
    conn = sqlite3.connect(db_path)

    print("\n========================= ANALYTICS REPORT 1 =========================")
    print("Return Rate & Total Return Volume by Product Category:\n")
    query_category_returns = """
    SELECT 
        ol.category,
        COUNT(DISTINCT ol.order_line_id) AS total_lines_sold,
        COUNT(DISTINCT rl.return_line_id) AS total_lines_returned,
        ROUND(100.0 * COUNT(DISTINCT rl.return_line_id) / COUNT(DISTINCT ol.order_line_id), 2) AS return_rate_pct,
        ROUND(SUM(ol.line_total), 2) AS gross_sales_usd
    FROM order_lines ol
    LEFT JOIN return_lines rl ON ol.order_line_id = rl.order_line_id
    GROUP BY ol.category
    ORDER BY total_lines_returned DESC;
    """
    df_cat = pd.read_sql_query(query_category_returns, conn)
    print(df_cat.to_string(index=False))

    print("\n========================= ANALYTICS REPORT 2 =========================")
    print("Warehouse Disposition Breakdown & Total Net Refund Impact:\n")
    query_disp_refunds = """
    SELECT 
        disp.disposition_action,
        COUNT(disp.disposition_id) AS items_processed,
        ROUND(AVG(ref.gross_refund_amount), 2) AS avg_gross_refund,
        ROUND(SUM(ref.restocking_fee), 2) AS total_restocking_fees_collected,
        ROUND(SUM(ref.net_refund_amount), 2) AS total_net_payout_usd
    FROM inventory_dispositions disp
    JOIN inspections ins ON disp.inspection_id = ins.inspection_id
    JOIN refunds ref ON ins.inspection_id = ref.inspection_id
    GROUP BY disp.disposition_action
    ORDER BY items_processed DESC;
    """
    df_disp = pd.read_sql_query(query_disp_refunds, conn)
    print(df_disp.to_string(index=False))

    conn.close()


if __name__ == "__main__":
    load_csvs_to_sqlite(CONFIG.OUTPUT_DIR, DB_PATH)
    run_analytical_queries(DB_PATH)