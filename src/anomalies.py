"""
Anomaly injection engine.
Systematically injects required edge cases and captures ground truth labels
without corrupting feature columns.
"""
from datetime import timedelta
import numpy as np
import pandas as pd

from src.config import CONFIG


def inject_anomalies(
    df_orders: pd.DataFrame,
    df_order_lines: pd.DataFrame,
    df_rmas: pd.DataFrame,
    df_rmals: pd.DataFrame,
    df_inspections: pd.DataFrame,
    df_dispositions: pd.DataFrame,
    df_refunds: pd.DataFrame,
    config=CONFIG
) -> tuple[
    pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame,
    pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame
]:
    """
    Injects 5 labelled anomaly types and outputs ground_truth table.
    """
    rng = np.random.default_rng(config.RANDOM_SEED + 7)

    # Work on copies to preserve clean state references
    rmas = df_rmas.copy()
    rmals = df_rmals.copy()
    inspections = df_inspections.copy()
    dispositions = df_dispositions.copy()
    refunds = df_refunds.copy()

    ground_truth_records = []

    # 1. Anomaly: RETURN_QTY_EXCEEDS_PURCHASED (Inject on 50 ReturnLines)
    line_lookup = df_order_lines.set_index("order_line_id")["quantity"].to_dict()
    target_rmals_idx = rng.choice(rmals.index, size=50, replace=False)

    for idx in target_rmals_idx:
        o_line_id = rmals.loc[idx, "order_line_id"]
        purchased_q = line_lookup.get(o_line_id, 1)
        illegal_q = purchased_q + int(rng.integers(2, 6))

        rmals.loc[idx, "requested_quantity"] = illegal_q

        ground_truth_records.append({
            "entity_name": "ReturnLine",
            "record_id": rmals.loc[idx, "return_line_id"],
            "parent_id": rmals.loc[idx, "return_request_id"],
            "issue_type": "RETURN_QTY_EXCEEDS_PURCHASED",
            "expected_decision": "REJECT_EXCESS_QUANTITY",
            "description": f"Requested quantity {illegal_q} exceeds purchased quantity {purchased_q}."
        })

    # 2. Anomaly: RETURN_AFTER_WINDOW_UNAPPROVED (Inject on 50 RMAs)
    late_rmas = rmas[rmas["days_since_delivery"] > config.RETURN_WINDOW_DAYS]
    target_late_idx = rng.choice(late_rmas.index, size=min(50, len(late_rmas)), replace=False)

    for idx in target_late_idx:
        rmas.loc[idx, "request_status"] = "APPROVED"

        ground_truth_records.append({
            "entity_name": "ReturnRequest",
            "record_id": rmas.loc[idx, "return_request_id"],
            "parent_id": rmas.loc[idx, "order_id"],
            "issue_type": "RETURN_AFTER_WINDOW_UNAPPROVED",
            "expected_decision": "REJECT_EXPIRED_POLICY_WINDOW",
            "description": f"Return requested at day {rmas.loc[idx, 'days_since_delivery']} but approved without policy override."
        })

    # 3. Anomaly: RESTOCK_BEFORE_INSPECTION (Inject on 40 Dispositions)
    insp_date_lookup = inspections.set_index("inspection_id")["inspection_date"].to_dict()
    target_disp_idx = rng.choice(dispositions.index, size=40, replace=False)

    for idx in target_disp_idx:
        ins_id = dispositions.loc[idx, "inspection_id"]
        insp_dt = insp_date_lookup[ins_id]
        # Move disposition 1 to 3 days prior to inspection
        illegal_disp_date = insp_dt - timedelta(days=int(rng.integers(1, 4)))

        dispositions.loc[idx, "disposition_date"] = illegal_disp_date
        dispositions.loc[idx, "disposition_action"] = "RESTOCK"

        ground_truth_records.append({
            "entity_name": "InventoryDisposition",
            "record_id": dispositions.loc[idx, "disposition_id"],
            "parent_id": ins_id,
            "issue_type": "RESTOCK_BEFORE_INSPECTION",
            "expected_decision": "BLOCK_PREMATURE_RESTOCK",
            "description": f"Disposition recorded at {illegal_disp_date} before inspection date {insp_dt}."
        })

    # 4. Anomaly: REFUND_EXCEEDS_PAID_AMOUNT (Inject on 40 Refunds)
    target_ref_idx = rng.choice(refunds.index, size=40, replace=False)

    for idx in target_ref_idx:
        original_net = refunds.loc[idx, "net_refund_amount"]
        illegal_net = round(original_net + float(rng.uniform(150.0, 500.0)), 2)

        refunds.loc[idx, "net_refund_amount"] = illegal_net

        ground_truth_records.append({
            "entity_name": "Refund",
            "record_id": refunds.loc[idx, "refund_id"],
            "parent_id": refunds.loc[idx, "return_request_id"],
            "issue_type": "REFUND_EXCEEDS_PAID_AMOUNT",
            "expected_decision": "BLOCK_OVERPAYMENT",
            "description": f"Net refund increased from ${original_net} to ${illegal_net}, exceeding line purchase amount."
        })

    # 5. Anomaly: DUPLICATE_REFUND (Inject on 30 duplicate refund attempts)
    target_dupe_rows = refunds.sample(n=30, random_state=int(rng.integers(1, 1000000))).copy()
    duplicate_rows = []

    last_ref_id_num = int(refunds["refund_id"].iloc[-1].split("-")[-1])

    for _, row in target_dupe_rows.iterrows():
        last_ref_id_num += 1
        new_ref_id = f"REF-2026-{last_ref_id_num:06d}"

        dupe_entry = row.to_dict()
        dupe_entry["refund_id"] = new_ref_id
        dupe_entry["refund_date"] = row["refund_date"] + timedelta(hours=int(rng.integers(1, 12)))
        dupe_entry["refund_status"] = "PROCESSED"  # The intentional anomaly to catch

        duplicate_rows.append(dupe_entry)

        ground_truth_records.append({
            "entity_name": "Refund",
            "record_id": new_ref_id,
            "parent_id": row["inspection_id"],
            "issue_type": "DUPLICATE_REFUND",
            "expected_decision": "BLOCK_DUPLICATE_PAYOUT",
            "description": f"Duplicate payout attempted for already-refunded Inspection ID {row['inspection_id']}."
        })

    # Append duplicate rows to refunds
    refunds = pd.concat([refunds, pd.DataFrame(duplicate_rows)], ignore_index=True)

    df_ground_truth = pd.DataFrame(ground_truth_records)

    return (
        df_orders, df_order_lines, rmas, rmals,
        inspections, dispositions, refunds, df_ground_truth
    )


if __name__ == "__main__":
    from src.master_data import generate_customers, generate_products
    from src.orders import generate_orders_and_lines
    from src.returns import generate_returns
    from src.shipments import generate_authorizations_and_shipments
    from src.inspections import generate_inspections_and_dispositions
    from src.refunds import generate_refunds

    customers = generate_customers()
    products = generate_products()
    orders, order_lines = generate_orders_and_lines(customers, products)
    rmas, rmals = generate_returns(orders, order_lines)
    ras, shipments = generate_authorizations_and_shipments(rmas)
    inspections, dispositions = generate_inspections_and_dispositions(rmals, ras, shipments)
    refunds = generate_refunds(inspections, rmals, order_lines)

    (
        orders, order_lines, rmas, rmals,
        inspections, dispositions, refunds, ground_truth
    ) = inject_anomalies(
        orders, order_lines, rmas, rmals,
        inspections, dispositions, refunds
    )

    print(f"Total Ground Truth Anomalies Injected: {len(ground_truth):,}")
    print("\nAnomaly breakdown by issue_type:")
    print(ground_truth["issue_type"].value_counts().to_string())