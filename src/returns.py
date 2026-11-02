"""
Return Request (RMA) and ReturnLine generation module.
Enforces policy windows, category exclusions, and quantity validation.
"""
from datetime import timedelta
import numpy as np
import pandas as pd

from src.config import CONFIG
from src.master_data import generate_customers, generate_products
from src.orders import generate_orders_and_lines


def generate_returns(
    df_orders: pd.DataFrame,
    df_order_lines: pd.DataFrame,
    config=CONFIG
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Generate ReturnRequest and ReturnLine tables.
    Returns exactly config.NUM_RETURN_REQUESTS and config.NUM_RETURN_LINES.
    """
    rng = np.random.default_rng(config.RANDOM_SEED + 3)

    # 1. Filter orders eligible for returns (DELIVERED only)
    delivered_orders = df_orders[df_orders["order_status"] == "DELIVERED"].copy()
    
    # Pre-index order lines by order_id
    lines_by_order = df_order_lines.groupby("order_id")
    order_line_counts = lines_by_order.size()

    # Find delivered orders with at least 1 line and with >= 2 lines
    multi_line_order_ids = order_line_counts[
        (order_line_counts >= 2) & order_line_counts.index.isin(delivered_orders["order_id"])
    ].index.values

    # Target: 5,000 RMAs with a total of 8,000 lines (3,000 2-line RMAs, 2,000 1-line RMAs)
    num_multi = config.NUM_RETURN_LINES - config.NUM_RETURN_REQUESTS  # 3,000
    num_single = config.NUM_RETURN_REQUESTS - num_multi              # 2,000

    chosen_multi_orders = rng.choice(multi_line_order_ids, size=num_multi, replace=False)
    
    remaining_delivered = delivered_orders[~delivered_orders["order_id"].isin(chosen_multi_orders)]["order_id"].values
    chosen_single_orders = rng.choice(remaining_delivered, size=num_single, replace=False)

    chosen_order_ids = np.concatenate([chosen_multi_orders, chosen_single_orders])
    rng.shuffle(chosen_order_ids)

    order_lookup = delivered_orders.set_index("order_id").to_dict(orient="index")

    return_requests = []
    return_lines = []

    return_reasons = [
        "DEFECTIVE",
        "WRONG_ITEM",
        "DOES_NOT_FIT",
        "CHANGED_MIND",
        "NOT_AS_DESCRIBED"
    ]

    for i, order_id in enumerate(chosen_order_ids):
        rma_num = i + 1
        rma_id = f"RMA-2026-{rma_num:06d}"
        ord_info = order_lookup[order_id]
        customer_id = ord_info["customer_id"]
        delivery_dt = ord_info["delivery_date"]

        # Request timing: 88% within 30-day policy window, 12% late requests
        is_late_request = rng.random() < 0.12
        if is_late_request:
            days_delta = int(rng.integers(31, 65))
        else:
            days_delta = int(rng.integers(1, 30))

        request_dt = delivery_dt + timedelta(
            days=days_delta,
            hours=int(rng.integers(1, 20)),
            minutes=int(rng.integers(0, 59))
        )
        days_since_delivery = (request_dt - delivery_dt).days

        # Determine number of lines to return from this order
        available_lines = lines_by_order.get_group(order_id)
        num_to_sample = 2 if (order_id in chosen_multi_orders and len(available_lines) >= 2) else 1

        sampled_lines = available_lines.sample(n=num_to_sample, random_state=int(rng.integers(1, 1000000)))

        rma_has_approved_line = False

        for line_idx, (_, o_line) in enumerate(sampled_lines.iterrows(), start=1):
            rmal_id = f"RMAL-{rma_id}-{line_idx:02d}"
            reason = rng.choice(return_reasons)
            purchased_qty = int(o_line["quantity"])

            # Customer requests return: 1 up to purchased quantity
            requested_qty = int(rng.integers(1, purchased_qty + 1)) if purchased_qty > 1 else 1

            # Business eligibility check
            is_within_window = days_since_delivery <= config.RETURN_WINDOW_DAYS
            is_returnable_cat = bool(o_line["returnable"])

            if is_within_window and is_returnable_cat:
                approved_qty = requested_qty
                line_status = "APPROVED"
                rma_has_approved_line = True
            else:
                approved_qty = 0
                line_status = "REJECTED"

            return_lines.append({
                "return_line_id": rmal_id,
                "return_request_id": rma_id,
                "order_line_id": o_line["order_line_id"],
                "return_reason": reason,
                "requested_quantity": requested_qty,
                "approved_quantity": approved_qty,
                "line_status": line_status,
            })

        req_status = "APPROVED" if rma_has_approved_line else "REJECTED"

        return_requests.append({
            "return_request_id": rma_id,
            "order_id": order_id,
            "customer_id": customer_id,
            "request_date": request_dt,
            "policy_window_days": config.RETURN_WINDOW_DAYS,
            "days_since_delivery": days_since_delivery,
            "request_status": req_status,
        })

    df_rmas = pd.DataFrame(return_requests)
    df_rmals = pd.DataFrame(return_lines)
    return df_rmas, df_rmals


if __name__ == "__main__":
    customers = generate_customers()
    products = generate_products()
    orders, order_lines = generate_orders_and_lines(customers, products)
    rmas, rmals = generate_returns(orders, order_lines)
    
    print(f"Generated {len(rmas):,} ReturnRequests. First ID: {rmas['return_request_id'].iloc[0]}")
    print(f"Generated {len(rmals):,} ReturnLines. First ID: {rmals['return_line_id'].iloc[0]}")
    print("Return Request status breakdown:")
    print(rmas["request_status"].value_counts().to_string())