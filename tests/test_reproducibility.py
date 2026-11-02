"""
Reproducibility and Determinism Verification.
Executes two independent generation runs with seed 20261022 and validates
identical row counts and SHA-256 hash parity across all tables.
"""
import hashlib
import pandas as pd

from src.config import CONFIG
from src.master_data import generate_customers, generate_products
from src.orders import generate_orders_and_lines
from src.returns import generate_returns
from src.shipments import generate_authorizations_and_shipments
from src.inspections import generate_inspections_and_dispositions
from src.refunds import generate_refunds
from src.anomalies import inject_anomalies


def generate_pipeline_in_memory():
    cust = generate_customers(CONFIG)
    prod = generate_products(CONFIG)
    ord_h, ord_l = generate_orders_and_lines(cust, prod, CONFIG)
    rma, rmal = generate_returns(ord_h, ord_l, CONFIG)
    ra, rts = generate_authorizations_and_shipments(rma, CONFIG)
    ins, disp = generate_inspections_and_dispositions(rmal, ra, rts, CONFIG)
    ref = generate_refunds(ins, rmal, ord_l, CONFIG)
    ord_h, ord_l, rma, rmal, ins, disp, ref, gt = inject_anomalies(
        ord_h, ord_l, rma, rmal, ins, disp, ref, CONFIG
    )
    return {
        "customers": cust,
        "products": prod,
        "orders": ord_h,
        "order_lines": ord_l,
        "return_requests": rma,
        "return_lines": rmal,
        "return_authorizations": ra,
        "return_shipments": rts,
        "inspections": ins,
        "inventory_dispositions": disp,
        "refunds": ref,
        "ground_truth": gt,
    }


def compute_table_hash(df: pd.DataFrame) -> str:
    """Compute deterministic SHA-256 hash of DataFrame contents."""
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    return hashlib.sha256(csv_bytes).hexdigest()


def test_reproducibility():
    print("Executing Run 1 (Seed: 20261022)...")
    run1 = generate_pipeline_in_memory()

    print("Executing Run 2 (Seed: 20261022)...")
    run2 = generate_pipeline_in_memory()

    print("\nComparing SHA-256 hashes and row counts across both runs:\n")
    all_matched = True

    for name in run1:
        rows1, rows2 = len(run1[name]), len(run2[name])
        hash1 = compute_table_hash(run1[name])
        hash2 = compute_table_hash(run2[name])

        match = (rows1 == rows2) and (hash1 == hash2)
        if not match:
            all_matched = False

        status = "MATCH" if match else "MISMATCH"
        print(f"[{status}] {name:24s} | Rows: {rows1:,} | SHA-256: {hash1[:12]}...")

    assert all_matched, "Determinism failure: Checksums between runs did not match."
    print("\n100% Reproducibility Confirmed: Both runs are bit-for-bit identical.")


if __name__ == "__main__":
    test_reproducibility()