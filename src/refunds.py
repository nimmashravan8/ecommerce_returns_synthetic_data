"""
Refund generation and financial reconciliation module.
Derives gross amounts, restocking fees, and shipping deductions directly from line purchases.
"""
from datetime import timedelta
import numpy as np
import pandas as pd

from src.config import CONFIG
from src.master_data import generate_customers, generate_products
from src.orders import generate_orders_and_lines
from src.returns import generate_returns
from src.shipments import generate_authorizations_and_shipments
from src.inspections import generate_inspections_and_dispositions


def generate_refunds(
    df_inspections: pd.DataFrame,
    df_return_lines: pd.DataFrame,
    df_order_lines: pd.DataFrame,
    config=CONFIG
) -> pd.DataFrame:
    """
    Generate baseline valid Refund records.
    Returns: df_refunds
    """
    rng = np.random.default_rng(config.RANDOM_SEED + 6)

    # 1. Join inspections to return_lines and order_lines for pricing
    passed_inspections = df_inspections[df_inspections["passed_inspection"]].copy()

    merged = passed_inspections.merge(
        df_return_lines[["return_line_id", "order_line_id", "return_reason", "approved_quantity"]],
        on="return_line_id",
        how="inner"
    ).merge(
        df_order_lines[["order_line_id", "unit_price", "line_discount", "quantity"]],
        on="order_line_id",
        how="inner"
    )

    refunds_list = []
    ref_counter = 1

    for _, row in merged.iterrows():
        ref_id = f"REF-2026-{ref_counter:06d}"
        ref_counter += 1

        insp_date = row["inspection_date"]
        # Refund processed within 1 to 24 hours of inspection
        refund_date = insp_date + timedelta(hours=int(rng.integers(1, 24)), minutes=int(rng.integers(0, 59)))

        purchased_qty = row["quantity"]
        unit_discount = row["line_discount"] / purchased_qty
        effective_unit_price = row["unit_price"] - unit_discount

        approved_qty = row["approved_quantity"]
        gross_refund = round(effective_unit_price * approved_qty, 2)

        # Restocking fee rule: 15% if opened or damaged
        condition = row["item_condition"]
        if condition in ["OPENED_INTACT", "DAMAGED_REPAIRABLE"]:
            restocking_fee = round(gross_refund * config.RESTOCKING_FEE_RATE, 2)
        else:
            restocking_fee = 0.0

        # Shipping fee rule: Free return shipping if merchant defect/error
        reason = row["return_reason"]
        if reason in ["DEFECTIVE", "WRONG_ITEM"]:
            shipping_fee = 0.0
        else:
            shipping_fee = config.STANDARD_SHIPPING_FEE

        net_refund = round(max(0.0, gross_refund - restocking_fee - shipping_fee), 2)

        refunds_list.append({
            "refund_id": ref_id,
            "return_request_id": row["return_request_id"],
            "inspection_id": row["inspection_id"],
            "refund_date": refund_date,
            "gross_refund_amount": gross_refund,
            "restocking_fee": restocking_fee,
            "return_shipping_fee": shipping_fee,
            "net_refund_amount": net_refund,
            "refund_status": "PROCESSED",
        })

    df_refunds = pd.DataFrame(refunds_list)
    return df_refunds


if __name__ == "__main__":
    customers = generate_customers()
    products = generate_products()
    orders, order_lines = generate_orders_and_lines(customers, products)
    rmas, rmals = generate_returns(orders, order_lines)
    ras, shipments = generate_authorizations_and_shipments(rmas)
    inspections, dispositions = generate_inspections_and_dispositions(rmals, ras, shipments)
    refunds = generate_refunds(inspections, rmals, order_lines)

    print(f"Generated {len(refunds):,} Refunds. First ID: {refunds['refund_id'].iloc[0]}")
    
    # Financial reconciliation verification
    reconciled = np.isclose(
        refunds["net_refund_amount"],
        np.maximum(0.0, refunds["gross_refund_amount"] - refunds["restocking_fee"] - refunds["return_shipping_fee"]),
        atol=0.01
    ).all()
    print(f"Refund net arithmetic fully reconciled: {reconciled}")
    print(f"Total Gross Refunded: ${refunds['gross_refund_amount'].sum():,.2f}")
    print(f"Total Net Refunded: ${refunds['net_refund_amount'].sum():,.2f}")