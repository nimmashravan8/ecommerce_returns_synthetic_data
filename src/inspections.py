"""
Warehouse Inspection and Inventory Disposition generation module.
Enforces physical condition classification and disposition destination logic.
"""
from datetime import timedelta
import numpy as np
import pandas as pd

from src.config import CONFIG
from src.master_data import generate_customers, generate_products
from src.orders import generate_orders_and_lines
from src.returns import generate_returns
from src.shipments import generate_authorizations_and_shipments


def generate_inspections_and_dispositions(
    df_return_lines: pd.DataFrame,
    df_ras: pd.DataFrame,
    df_shipments: pd.DataFrame,
    config=CONFIG
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Generate Inspection and InventoryDisposition tables.
    Returns: (df_inspections, df_dispositions)
    """
    rng = np.random.default_rng(config.RANDOM_SEED + 5)

    # 1. Join Delivered Shipments back to Return Authorizations to get RMA IDs
    delivered_ships = df_shipments[df_shipments["shipment_status"] == "DELIVERED"].copy()
    ship_auth_merge = delivered_ships.merge(df_ras[["ra_id", "return_request_id"]], on="ra_id", how="inner")

    # 2. Get approved ReturnLines for those RMAs
    approved_lines = df_return_lines[df_return_lines["line_status"] == "APPROVED"].copy()
    lines_to_inspect = approved_lines.merge(
        ship_auth_merge[["return_request_id", "shipment_id", "delivered_to_wh_date"]],
        on="return_request_id",
        how="inner"
    )

    inspections_list = []
    dispositions_list = []

    conditions = [
        "UNOPENED_PERFECT",
        "OPENED_INTACT",
        "DAMAGED_REPAIRABLE",
        "SCRAP_UNSALVAGEABLE",
        "WRONG_ITEM_RECEIVED"
    ]
    condition_probs = [0.60, 0.22, 0.08, 0.06, 0.04]

    # Map conditions to business disposition actions
    condition_to_disposition = {
        "UNOPENED_PERFECT": "RESTOCK",
        "OPENED_INTACT": "REFURBISH",
        "DAMAGED_REPAIRABLE": "REFURBISH",
        "SCRAP_UNSALVAGEABLE": "SCRAP",
        "WRONG_ITEM_RECEIVED": "QUARANTINE"
    }

    ins_counter = 1
    disp_counter = 1

    for _, row in lines_to_inspect.iterrows():
        ins_id = f"INS-2026-{ins_counter:06d}"
        ins_counter += 1

        deliv_date = row["delivered_to_wh_date"]
        # Inspection happens within 1 to 48 hours of delivery
        insp_date = deliv_date + timedelta(hours=int(rng.integers(1, 48)), minutes=int(rng.integers(0, 59)))

        condition = rng.choice(conditions, p=condition_probs)
        inspector = f"INSP-{rng.integers(1, 21):02d}"

        # Passed inspection if condition is returnable/eligible for payout
        passed = condition in ["UNOPENED_PERFECT", "OPENED_INTACT", "DAMAGED_REPAIRABLE"]

        inspections_list.append({
            "inspection_id": ins_id,
            "shipment_id": row["shipment_id"],
            "return_line_id": row["return_line_id"],
            "return_request_id": row["return_request_id"],
            "inspection_date": insp_date,
            "item_condition": condition,
            "inspector_id": inspector,
            "passed_inspection": passed,
        })

        # Inventory disposition mapping
        disp_id = f"DISP-2026-{disp_counter:06d}"
        disp_counter += 1
        disp_action = condition_to_disposition[condition]
        disp_date = insp_date + timedelta(hours=int(rng.integers(1, 12)))

        bay = f"{rng.choice(['WH-A', 'WH-B', 'WH-C'])}-{rng.integers(1, 50):02d}-{rng.integers(1, 20):02d}"

        dispositions_list.append({
            "disposition_id": disp_id,
            "inspection_id": ins_id,
            "disposition_action": disp_action,
            "disposition_date": disp_date,
            "warehouse_location": bay,
        })

    df_inspections = pd.DataFrame(inspections_list)
    df_dispositions = pd.DataFrame(dispositions_list)
    return df_inspections, df_dispositions


if __name__ == "__main__":
    customers = generate_customers()
    products = generate_products()
    orders, order_lines = generate_orders_and_lines(customers, products)
    rmas, rmals = generate_returns(orders, order_lines)
    ras, shipments = generate_authorizations_and_shipments(rmas)
    inspections, dispositions = generate_inspections_and_dispositions(rmals, ras, shipments)

    print(f"Generated {len(inspections):,} Inspections. First ID: {inspections['inspection_id'].iloc[0]}")
    print(f"Generated {len(dispositions):,} Dispositions. First ID: {dispositions['disposition_id'].iloc[0]}")
    print("Item condition breakdown:")
    print(inspections["item_condition"].value_counts().to_string())
    print("Disposition breakdown:")
    print(dispositions["disposition_action"].value_counts().to_string())