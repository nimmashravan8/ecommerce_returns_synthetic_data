"""
Return Authorization (RA) and Return Shipment (RTS) generation module.
Enforces authorization windows, shipping milestones, and lost shipment scenarios.
"""
from datetime import timedelta
import numpy as np
import pandas as pd

from src.config import CONFIG
from src.master_data import generate_customers, generate_products
from src.orders import generate_orders_and_lines
from src.returns import generate_returns


def generate_authorizations_and_shipments(
    df_return_requests: pd.DataFrame,
    config=CONFIG
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Generate ReturnAuthorization and ReturnShipment tables.
    Returns: (df_ras, df_shipments)
    """
    rng = np.random.default_rng(config.RANDOM_SEED + 4)

    # Only approved RMAs receive a Return Authorization
    approved_rmas = df_return_requests[df_return_requests["request_status"] == "APPROVED"].copy()

    ras_list = []
    shipments_list = []

    carriers = ["UPS", "FEDEX", "USPS", "DHL"]
    shipment_status_choices = ["DELIVERED", "IN_TRANSIT", "LOST_IN_TRANSIT", "LABEL_CREATED"]
    shipment_status_probs = [0.85, 0.08, 0.05, 0.02]

    ra_counter = 1
    shipment_counter = 1

    for _, rma in approved_rmas.iterrows():
        rma_id = rma["return_request_id"]
        req_date = rma["request_date"]

        ra_id = f"RA-2026-{ra_counter:06d}"
        ra_counter += 1

        auth_date = req_date + timedelta(hours=int(rng.integers(1, 24)))
        expires_at = auth_date + timedelta(days=config.RA_EXPIRATION_DAYS)

        # Shipping process
        carrier = rng.choice(carriers)
        tracking_num = f"TRK{carrier[:2]}{rng.integers(100000000, 999999999)}"
        ship_status = rng.choice(shipment_status_choices, p=shipment_status_probs)

        shipped_date = auth_date + timedelta(days=int(rng.integers(1, 6)), hours=int(rng.integers(1, 12)))

        delivered_date = None
        if ship_status == "DELIVERED":
            delivered_date = shipped_date + timedelta(days=int(rng.integers(2, 6)), hours=int(rng.integers(1, 12)))
            ra_status = "FULFILLED"
        elif ship_status in ["IN_TRANSIT", "LOST_IN_TRANSIT"]:
            ra_status = "ACTIVE"
        else:  # LABEL_CREATED
            ra_status = "EXPIRED" if auth_date + timedelta(days=20) < config.END_DATE else "ACTIVE"

        shipment_id = f"RTS-2026-{shipment_counter:06d}"
        shipment_counter += 1

        ras_list.append({
            "ra_id": ra_id,
            "return_request_id": rma_id,
            "authorized_date": auth_date,
            "expires_at": expires_at,
            "status": ra_status,
        })

        shipments_list.append({
            "shipment_id": shipment_id,
            "ra_id": ra_id,
            "carrier": carrier,
            "tracking_number": tracking_num,
            "shipped_date": shipped_date,
            "delivered_to_wh_date": delivered_date,
            "shipment_status": ship_status,
        })

    df_ras = pd.DataFrame(ras_list)
    df_shipments = pd.DataFrame(shipments_list)
    return df_ras, df_shipments


if __name__ == "__main__":
    customers = generate_customers()
    products = generate_products()
    orders, order_lines = generate_orders_and_lines(customers, products)
    rmas, rmals = generate_returns(orders, order_lines)
    ras, shipments = generate_authorizations_and_shipments(rmas)

    print(f"Generated {len(ras):,} ReturnAuthorizations. First ID: {ras['ra_id'].iloc[0]}")
    print(f"Generated {len(shipments):,} ReturnShipments. First ID: {shipments['shipment_id'].iloc[0]}")
    print("Shipment status breakdown:")
    print(shipments["shipment_status"].value_counts().to_string())