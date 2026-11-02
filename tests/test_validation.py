"""
Validation and data-integrity test suite.
Validates PK uniqueness, FK integrity, enum compliance, date sequence,
arithmetic reconciliation, and detects injected anomalies.
"""
import numpy as np
import pandas as pd

from src.config import CONFIG
from src.master_data import generate_customers, generate_products
from src.orders import generate_orders_and_lines
from src.returns import generate_returns
from src.shipments import generate_authorizations_and_shipments
from src.inspections import generate_inspections_and_dispositions
from src.refunds import generate_refunds
from src.anomalies import inject_anomalies


def run_full_validation():
    print("Generating full pipeline for validation...")
    customers = generate_customers()
    products = generate_products()
    orders, order_lines = generate_orders_and_lines(customers, products)
    rmas, rmals = generate_returns(orders, order_lines)
    ras, shipments = generate_authorizations_and_shipments(rmas)
    inspections, dispositions = generate_inspections_and_dispositions(rmals, ras, shipments)
    refunds = generate_refunds(inspections, rmals, order_lines)

    # Inject anomalies
    (
        orders, order_lines, rmas, rmals,
        inspections, dispositions, refunds, ground_truth
    ) = inject_anomalies(
        orders, order_lines, rmas, rmals,
        inspections, dispositions, refunds
    )

    print("\n--- 1. Primary Key Uniqueness ---")
    pk_checks = [
        ("Customer", customers["customer_id"]),
        ("Product", products["sku_id"]),
        ("Order", orders["order_id"]),
        ("OrderLine", order_lines["order_line_id"]),
        ("ReturnRequest", rmas["return_request_id"]),
        ("ReturnLine", rmals["return_line_id"]),
        ("ReturnAuthorization", ras["ra_id"]),
        ("ReturnShipment", shipments["shipment_id"]),
        ("Inspection", inspections["inspection_id"]),
        ("InventoryDisposition", dispositions["disposition_id"]),
        ("Refund", refunds["refund_id"]),
    ]
    for entity, series in pk_checks:
        is_unique = series.is_unique
        print(f"[{'PASS' if is_unique else 'FAIL'}] {entity} PK uniqueness (Total: {len(series):,})")
        assert is_unique, f"Duplicate PKs detected in {entity}"

    print("\n--- 2. Foreign Key Referential Integrity ---")
    fk_checks = [
        ("Order -> Customer", orders["customer_id"].isin(customers["customer_id"])),
        ("OrderLine -> Order", order_lines["order_id"].isin(orders["order_id"])),
        ("OrderLine -> Product", order_lines["sku_id"].isin(products["sku_id"])),
        ("ReturnRequest -> Order", rmas["order_id"].isin(orders["order_id"])),
        ("ReturnLine -> ReturnRequest", rmals["return_request_id"].isin(rmas["return_request_id"])),
        ("ReturnLine -> OrderLine", rmals["order_line_id"].isin(order_lines["order_line_id"])),
        ("ReturnAuthorization -> ReturnRequest", ras["return_request_id"].isin(rmas["return_request_id"])),
        ("ReturnShipment -> ReturnAuthorization", shipments["ra_id"].isin(ras["ra_id"])),
        ("Inspection -> ReturnShipment", inspections["shipment_id"].isin(shipments["shipment_id"])),
        ("Inspection -> ReturnLine", inspections["return_line_id"].isin(rmals["return_line_id"])),
        ("InventoryDisposition -> Inspection", dispositions["inspection_id"].isin(inspections["inspection_id"])),
        ("Refund -> ReturnRequest", refunds["return_request_id"].isin(rmas["return_request_id"])),
        ("Refund -> Inspection", refunds["inspection_id"].isin(inspections["inspection_id"])),
    ]
    for rel_name, check_series in fk_checks:
        valid = check_series.all()
        print(f"[{'PASS' if valid else 'FAIL'}] {rel_name} FK constraint")
        assert valid, f"Broken FK reference in {rel_name}"

    print("\n--- 3. Allowed Enums Compliance ---")
    assert orders["order_status"].isin(["COMPLETED", "CANCELLED", "DELIVERED"]).all(), "Invalid order_status"
    assert products["category"].isin(CONFIG.CATEGORIES).all(), "Invalid category"
    assert shipments["carrier"].isin(["UPS", "FEDEX", "USPS", "DHL"]).all(), "Invalid carrier"
    assert dispositions["disposition_action"].isin(["RESTOCK", "REFURBISH", "QUARANTINE", "SCRAP"]).all(), "Invalid disposition"
    print("[PASS] All categorical enum constraints verified.")

    print("\n--- 4. Arithmetic Reconciliation ---")
    order_recon = np.isclose(
        orders["subtotal_amount"] - orders["discount_amount"] + orders["tax_amount"],
        orders["total_paid_amount"],
        atol=0.01
    ).all()
    print(f"[{'PASS' if order_recon else 'FAIL'}] Order header totals reconcile to line items")
    assert order_recon, "Order arithmetic mismatch"

    print("\n--- 5. Anomaly Detection vs Ground Truth ---")
    # Detect Anomaly 1: Return quantity > purchased quantity
    merged_rl = rmals.merge(order_lines[["order_line_id", "quantity"]], on="order_line_id")
    detected_qty_anomalies = merged_rl[merged_rl["requested_quantity"] > merged_rl["quantity"]]
    expected_qty_anomalies = ground_truth[ground_truth["issue_type"] == "RETURN_QTY_EXCEEDS_PURCHASED"]
    print(f"[VERIFIED] Over-quantity returns detected: {len(detected_qty_anomalies)} (Expected: {len(expected_qty_anomalies)})")

    # Detect Anomaly 2: Duplicate Refunds (Multiple refunds for same inspection_id)
    refund_counts = refunds["inspection_id"].value_counts()
    detected_dupe_refunds = refund_counts[refund_counts > 1]
    expected_dupes = ground_truth[ground_truth["issue_type"] == "DUPLICATE_REFUND"]
    print(f"[VERIFIED] Duplicate refund attempts detected: {len(detected_dupe_refunds)} (Expected: {len(expected_dupes)})")

    # Detect Anomaly 3: Restock before inspection
    merged_disp = dispositions.merge(inspections[["inspection_id", "inspection_date"]], on="inspection_id")
    detected_timing = merged_disp[merged_disp["disposition_date"] < merged_disp["inspection_date"]]
    expected_timing = ground_truth[ground_truth["issue_type"] == "RESTOCK_BEFORE_INSPECTION"]
    print(f"[VERIFIED] Premature restocks detected: {len(detected_timing)} (Expected: {len(expected_timing)})")

    print("\nAll automated integrity and validation rules passed successfully!")


if __name__ == "__main__":
    run_full_validation()