"""
Anomaly detection baseline and evaluation engine.
Detects operational edge cases using business heuristics and evaluates
Precision, Recall, and F1-Score against ground_truth.csv.
"""
from pathlib import Path
import pandas as pd

from src.config import CONFIG


def run_baseline_detection(output_dir: Path) -> pd.DataFrame:
    """
    Runs rule-based anomaly detection directly on operational tables.
    Returns a unified DataFrame of detected anomalies: [record_id, predicted_issue_type].
    """
    detections = []

    # Load tables
    df_ol = pd.read_csv(output_dir / "order_lines.csv")
    df_rmas = pd.read_csv(output_dir / "return_requests.csv")
    df_rmals = pd.read_csv(output_dir / "return_lines.csv")
    df_ins = pd.read_csv(output_dir / "inspections.csv")
    df_disp = pd.read_csv(output_dir / "inventory_dispositions.csv")
    df_ref = pd.read_csv(output_dir / "refunds.csv")

    # 1. Detect: RETURN_QTY_EXCEEDS_PURCHASED
    merged_lines = df_rmals.merge(
        df_ol[["order_line_id", "quantity"]],
        on="order_line_id",
        how="inner"
    )
    over_qty = merged_lines[merged_lines["requested_quantity"] > merged_lines["quantity"]]
    for rec_id in over_qty["return_line_id"]:
        detections.append({
            "record_id": rec_id,
            "predicted_issue_type": "RETURN_QTY_EXCEEDS_PURCHASED"
        })

    # 2. Detect: RETURN_AFTER_WINDOW_UNAPPROVED
    late_approved = df_rmas[
        (df_rmas["days_since_delivery"] > CONFIG.RETURN_WINDOW_DAYS) &
        (df_rmas["request_status"] == "APPROVED")
    ]
    for rec_id in late_approved["return_request_id"]:
        detections.append({
            "record_id": rec_id,
            "predicted_issue_type": "RETURN_AFTER_WINDOW_UNAPPROVED"
        })

    # 3. Detect: RESTOCK_BEFORE_INSPECTION
    merged_disp = df_disp.merge(
        df_ins[["inspection_id", "inspection_date"]],
        on="inspection_id",
        how="inner"
    )
    premature_disp = merged_disp[
        pd.to_datetime(merged_disp["disposition_date"]) < pd.to_datetime(merged_disp["inspection_date"])
    ]
    for rec_id in premature_disp["disposition_id"]:
        detections.append({
            "record_id": rec_id,
            "predicted_issue_type": "RESTOCK_BEFORE_INSPECTION"
        })

   # 4. Detect: REFUND_EXCEEDS_PAID_AMOUNT
    ref_merged = df_ref.merge(
        df_ins[["inspection_id", "return_line_id"]],
        on="inspection_id",
        how="inner"
    ).merge(
        df_rmals[["return_line_id", "order_line_id", "approved_quantity"]],
        on="return_line_id",
        how="inner"
    ).merge(
        df_ol[["order_line_id", "line_total", "quantity"]],
        on="order_line_id",
        how="inner"
    )
    unit_paid = ref_merged["line_total"] / ref_merged["quantity"]
    prorated_paid = unit_paid * ref_merged["approved_quantity"]
    over_refunds = ref_merged[ref_merged["net_refund_amount"] > (prorated_paid + 0.01)]
    for rec_id in over_refunds["refund_id"]:
        detections.append({
            "record_id": rec_id,
            "predicted_issue_type": "REFUND_EXCEEDS_PAID_AMOUNT"
        })
    # 5. Detect: DUPLICATE_REFUND (subsequent refunds for same inspection_id)
    sorted_ref = df_ref.sort_values(by="refund_date")
    duplicate_mask = sorted_ref.duplicated(subset=["inspection_id"], keep="first")
    dupe_refunds = sorted_ref[duplicate_mask]
    for rec_id in dupe_refunds["refund_id"]:
        detections.append({
            "record_id": rec_id,
            "predicted_issue_type": "DUPLICATE_REFUND"
        })

    return pd.DataFrame(detections)


def evaluate_detections(df_pred: pd.DataFrame, ground_truth_path: Path):
    """
    Evaluates detections against ground_truth.csv, calculating TP, FP, FN,
    Precision, Recall, and F1 per anomaly category and overall.
    """
    df_gt = pd.read_csv(ground_truth_path)

    # Key by (record_id, issue_type)
    gt_pairs = set(zip(df_gt["record_id"], df_gt["issue_type"]))
    pred_pairs = set(zip(df_pred["record_id"], df_pred["predicted_issue_type"]))

    categories = list(df_gt["issue_type"].unique())
    metrics_summary = []

    total_tp = 0
    total_fp = 0
    total_fn = 0

    for cat in sorted(categories):
        cat_gt = {rec for rec, issue in gt_pairs if issue == cat}
        cat_pred = {rec for rec, issue in pred_pairs if issue == cat}

        tp = len(cat_gt & cat_pred)
        fp = len(cat_pred - cat_gt)
        fn = len(cat_gt - cat_pred)

        total_tp += tp
        total_fp += fp
        total_fn += fn

        precision = (tp / (tp + fp)) if (tp + fp) > 0 else 0.0
        recall = (tp / (tp + fn)) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

        metrics_summary.append({
            "Anomaly Type": cat,
            "Ground Truth": len(cat_gt),
            "Detected": len(cat_pred),
            "TP": tp,
            "FP": fp,
            "FN": fn,
            "Precision": f"{precision:.4f}",
            "Recall": f"{recall:.4f}",
            "F1-Score": f"{f1:.4f}",
        })

    macro_precision = (total_tp / (total_tp + total_fp)) if (total_tp + total_fp) > 0 else 0.0
    macro_recall = (total_tp / (total_tp + total_fn)) if (total_tp + total_fn) > 0 else 0.0
    macro_f1 = (
        (2 * macro_precision * macro_recall / (macro_precision + macro_recall))
        if (macro_precision + macro_recall) > 0 else 0.0
    )

    metrics_df = pd.DataFrame(metrics_summary)
    print("\n=================== ANOMALY DETECTION EVALUATION REPORT ===================")
    print(metrics_df.to_string(index=False))
    print("---------------------------------------------------------------------------")
    print(
        f"OVERALL METRICS: "
        f"TP={total_tp} | FP={total_fp} | FN={total_fn} | "
        f"Precision={macro_precision:.4f} | Recall={macro_recall:.4f} | F1-Score={macro_f1:.4f}"
    )
    print("===========================================================================\n")


if __name__ == "__main__":
    output_directory = CONFIG.OUTPUT_DIR
    ground_truth_file = output_directory / "ground_truth.csv"

    print("Running baseline heuristic detection on operational CSVs...")
    predictions = run_baseline_detection(output_directory)
    print(f"Total anomalies flagged by baseline detector: {len(predictions):,}")

    evaluate_detections(predictions, ground_truth_file)