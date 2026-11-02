"""
Order and OrderLine generation module.
Ensures strict foreign-key integrity and exact arithmetic reconciliation.
"""
from datetime import timedelta
import numpy as np
import pandas as pd

from src.config import CONFIG
from src.master_data import generate_customers, generate_products


def generate_orders_and_lines(
    df_customers: pd.DataFrame,
    df_products: pd.DataFrame,
    config=CONFIG
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Generate Order and OrderLine tables.
    Returns: (df_orders, df_order_lines)
    """
    rng = np.random.default_rng(config.RANDOM_SEED + 2)

    # 1. Select customer IDs for all 30,000 orders
    cust_ids = df_customers["customer_id"].values
    order_cust_ids = rng.choice(cust_ids, size=config.NUM_ORDERS, replace=True)

    # 2. Assign order dates across Jan 1, 2026 - Aug 31, 2026
    start_ts = pd.Timestamp("2026-01-01").timestamp()
    end_ts = pd.Timestamp("2026-08-31 23:59:59").timestamp()
    order_timestamps = rng.uniform(start_ts, end_ts, size=config.NUM_ORDERS)
    order_dates = [pd.to_datetime(ts, unit="s").floor("s") for ts in order_timestamps]

    # Order lifecycle statuses: 90% DELIVERED, 7% COMPLETED (in-transit/pickup), 3% CANCELLED
    statuses = rng.choice(
        ["DELIVERED", "COMPLETED", "CANCELLED"],
        size=config.NUM_ORDERS,
        p=[0.90, 0.07, 0.03]
    )

    # Fast product catalog lookup dictionary
    product_dict = df_products.set_index("sku_id").to_dict(orient="index")
    sku_list = df_products["sku_id"].values

    orders_list = []
    lines_list = []

    # Number of lines per order: 1 to 4 lines
    lines_per_order = rng.choice([1, 2, 3, 4], size=config.NUM_ORDERS, p=[0.50, 0.30, 0.15, 0.05])

    for i in range(config.NUM_ORDERS):
        order_num = i + 1
        order_id = f"ORD-2026-{order_num:06d}"
        cust_id = order_cust_ids[i]
        o_date = order_dates[i]
        status = statuses[i]

        delivery_date = None
        if status == "DELIVERED":
            delivery_date = o_date + timedelta(
                days=int(rng.integers(2, 8)),
                hours=int(rng.integers(1, 12))
            )

        num_lines = lines_per_order[i]
        chosen_skus = rng.choice(sku_list, size=num_lines, replace=False)

        order_subtotal = 0.0

        for line_idx, sku in enumerate(chosen_skus, start=1):
            line_id = f"ORDL-{order_id}-{line_idx:02d}"
            prod_info = product_dict[sku]
            unit_price = float(prod_info["unit_price"])
            quantity = int(rng.choice([1, 2, 3], p=[0.75, 0.20, 0.05]))

            # Occasional line discount (0%, 5%, 10%, 15%)
            discount_pct = float(rng.choice([0.0, 0.05, 0.10, 0.15], p=[0.70, 0.15, 0.10, 0.05]))
            line_disc = round(unit_price * quantity * discount_pct, 2)
            line_total = round((unit_price * quantity) - line_disc, 2)

            order_subtotal += line_total

            lines_list.append({
                "order_line_id": line_id,
                "order_id": order_id,
                "line_number": line_idx,
                "sku_id": sku,
                "category": prod_info["category"],
                "unit_price": unit_price,
                "quantity": quantity,
                "line_discount": line_disc,
                "line_total": line_total,
                "returnable": prod_info["is_returnable"],
            })

        order_subtotal = round(order_subtotal, 2)

        # Order-level promotional discount: 20% chance of $5 or $10 off (if subtotal > $40)
        order_discount = 0.0
        if order_subtotal > 40.0 and rng.random() < 0.20:
            order_discount = float(rng.choice([5.0, 10.0]))

        taxable_base = max(0.0, order_subtotal - order_discount)
        tax_amount = round(taxable_base * config.SALES_TAX_RATE, 2)
        total_paid = round(taxable_base + tax_amount, 2)

        orders_list.append({
            "order_id": order_id,
            "customer_id": cust_id,
            "order_date": o_date,
            "order_status": status,
            "currency": "USD",
            "subtotal_amount": order_subtotal,
            "discount_amount": order_discount,
            "tax_amount": tax_amount,
            "total_paid_amount": total_paid,
            "delivery_date": delivery_date,
        })

    df_orders = pd.DataFrame(orders_list)
    df_order_lines = pd.DataFrame(lines_list)
    return df_orders, df_order_lines


if __name__ == "__main__":
    customers = generate_customers()
    products = generate_products()
    orders, order_lines = generate_orders_and_lines(customers, products)
    print(f"Generated {len(orders):,} Orders. First ID: {orders['order_id'].iloc[0]}")
    print(f"Generated {len(order_lines):,} OrderLines. First ID: {order_lines['order_line_id'].iloc[0]}")
    
    # Quick sanity check on arithmetic
    reconciled = np.isclose(
        orders["subtotal_amount"] - orders["discount_amount"] + orders["tax_amount"],
        orders["total_paid_amount"],
        atol=0.01
    ).all()
    print(f"Order total arithmetic fully reconciled: {reconciled}")