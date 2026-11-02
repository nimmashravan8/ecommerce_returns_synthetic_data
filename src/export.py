"""
Master export runner.
Orchestrates generation, anomaly injection, CSV serialization, and manifest creation.
"""
import json
import time
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

from src.config import CONFIG
from src.master_data import generate_customers, generate_products
from src.orders import generate_orders_and_lines
from src.returns import generate_returns
from src.shipments import generate_authorizations_and_shipments
from src.inspections import generate_inspections_and_dispositions
from src.refunds import generate_refunds
from src.anomalies import inject_anomalies


def run_pipeline_and_export(config=CONFIG):
    start_time = time.time()
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Running full synthetic returns data generation pipeline...")

    # 1. Master entities
    df_customers = generate_customers(config)
    df_products = generate_products(config)

    # 2. Transaction entities
    df_orders, df_order_lines = generate_orders_and_lines(df_customers, df_products, config)

    # 3. Return lifecycle
    df_rmas, df_rmals = generate_returns(df_orders, df_order_lines, config)
    df_ras, df_shipments = generate_authorizations_and_shipments(df_rmas, config)
    df_inspections, df_dispositions = generate_inspections_and_dispositions(df_rmals, df_ras, df_shipments, config)
    df_refunds = generate_refunds(df_inspections, df_rmals, df_order_lines, config)

    # 4. Inject anomalies and extract separate ground truth
    (
        df_orders, df_order_lines, df_rmas, df_rmals,
        df_inspections, df_dispositions, df_refunds, df_ground_truth
    ) = inject_anomalies(
        df_orders, df_order_lines, df_rmas, df_rmals,
        df_inspections, df_dispositions, df_refunds, config
    )

    tables = {
        "customers.csv": df_customers,
        "products.csv": df_products,
        "orders.csv": df_orders,
        "order_lines.csv": df_order_lines,
        "return_requests.csv": df_rmas,
        "return_lines.csv": df_rmals,
        "return_authorizations.csv": df_ras,
        "return_shipments.csv": df_shipments,
        "inspections.csv": df_inspections,
        "inventory_dispositions.csv": df_dispositions,
        "refunds.csv": df_refunds,
        "ground_truth.csv": df_ground_truth,
    }

    manifest_files = {}

    print("\nExporting CSV datasets to output/ directory:")
    for filename, df in tables.items():
        file_path = config.OUTPUT_DIR / filename
        df.to_csv(file_path, index=False)
        size_bytes = file_path.stat().st_size
        manifest_files[filename] = {
            "row_count": len(df),
            "column_count": len(df.columns),
            "columns": list(df.columns),
            "size_kb": round(size_bytes / 1024, 2),
        }
        print(f"  -> {filename:28s} | {len(df):>7,d} rows | {round(size_bytes/1024, 1):>8.1f} KB")

    elapsed_seconds = round(time.time() - start_time, 2)

    manifest = {
        "dataset_name": "synthetic_ecommerce_orders_and_returns",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "random_seed": config.RANDOM_SEED,
        "generation_time_seconds": elapsed_seconds,
        "total_files": len(tables),
        "files": manifest_files,
    }

    manifest_path = config.OUTPUT_DIR / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"\nManifest saved to {manifest_path.name}")
    print(f"Pipeline completed in {elapsed_seconds} seconds.")


if __name__ == "__main__":
    run_pipeline_and_export()