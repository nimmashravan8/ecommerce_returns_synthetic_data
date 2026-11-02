"""
Master data generation: Customers and Products.
Deterministic generation using Faker and NumPy seeded with CONFIG.RANDOM_SEED.
"""
from datetime import timedelta
import numpy as np
import pandas as pd
from faker import Faker

from src.config import CONFIG


def generate_customers(config=CONFIG) -> pd.DataFrame:
    """Generate master Customer table."""
    fake = Faker()
    Faker.seed(config.RANDOM_SEED)
    rng = np.random.default_rng(config.RANDOM_SEED)

    customer_ids = [f"CUST-{i:06d}" for i in range(1, config.NUM_CUSTOMERS + 1)]
    tiers = rng.choice(["STANDARD", "GOLD", "PLATINUM"], size=config.NUM_CUSTOMERS, p=[0.70, 0.20, 0.10])

    # Account creation between 2024-01-01 and 2025-12-31 (prior to 2026 order dates)
    start_ts = pd.Timestamp("2024-01-01").timestamp()
    end_ts = pd.Timestamp("2025-12-31").timestamp()
    random_timestamps = rng.uniform(start_ts, end_ts, size=config.NUM_CUSTOMERS)
    created_at = [pd.to_datetime(ts, unit="s").floor("s") for ts in random_timestamps]

    names = [fake.name() for _ in range(config.NUM_CUSTOMERS)]
    emails = [f"user_{i:06d}@{fake.free_email_domain()}" for i in range(1, config.NUM_CUSTOMERS + 1)]

    df_customers = pd.DataFrame({
        "customer_id": customer_ids,
        "customer_name": names,
        "email": emails,
        "account_created_at": created_at,
        "customer_tier": tiers,
    })
    return df_customers


def generate_products(config=CONFIG) -> pd.DataFrame:
    """Generate master Product Catalog."""
    rng = np.random.default_rng(config.RANDOM_SEED + 1)

    sku_ids = [f"SKU-{i:06d}" for i in range(1, config.NUM_PRODUCTS + 1)]
    categories = rng.choice(
        list(config.CATEGORIES),
        size=config.NUM_PRODUCTS,
        p=[0.35, 0.25, 0.20, 0.10, 0.10]
    )

    # Base price tiers per category
    price_ranges = {
        "APPAREL": (19.99, 149.99),
        "ELECTRONICS": (49.99, 899.99),
        "HOME": (15.99, 299.99),
        "HYGIENE_PERSONAL_CARE": (9.99, 69.99),
        "FINAL_SALE": (12.99, 89.99),
    }

    unit_prices = []
    returnable_flags = []

    for cat in categories:
        low, high = price_ranges[cat]
        price = round(rng.uniform(low, high), 2)
        unit_prices.append(price)
        returnable_flags.append(cat not in config.NON_RETURNABLE_CATEGORIES)

    df_products = pd.DataFrame({
        "sku_id": sku_ids,
        "category": categories,
        "unit_price": unit_prices,
        "is_returnable": returnable_flags,
    })
    return df_products


if __name__ == "__main__":
    customers = generate_customers()
    products = generate_products()
    print(f"Generated {len(customers):,} Customers. First ID: {customers['customer_id'].iloc[0]}")
    print(f"Generated {len(products):,} Products. First SKU: {products['sku_id'].iloc[0]}")