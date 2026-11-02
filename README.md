# ?? Synthetic E-Commerce Returns & Operational Anomaly Dataset

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://ecommercereturnssyntheticdata-46jvmwalp4wujeokp7bvkk.streamlit.app/#warehouse-inspection-and-disposition-flow)

> **Live Interactive Dashboard:** [Access the Cloud Dashboard Here](https://ecommercereturnssyntheticdata-46jvmwalp4wujeokp7bvkk.streamlit.app/#warehouse-inspection-and-disposition-flow)

---
# E-Commerce Returns Synthetic Data Generator

A deterministic, high-fidelity synthetic data generator simulating the complete end-to-end e-commerce order, return, warehouse inspection, inventory disposition, and refund lifecycle.

---

## 1. Project Architecture & File Structure

```text
ecommerce_returns_synthetic_data/
├── docs/
│   └── data_dictionary.md       # Full schema & validation rules for all 10 entities
├── output/
│   ├── customers.csv            # 10,000 customer profiles
│   ├── products.csv             # 500 SKU catalog entries
│   ├── orders.csv               # 30,000 order headers
│   ├── order_lines.csv          # 52,632 line items
│   ├── return_requests.csv      # 5,000 return requests (RMAs)
│   ├── return_lines.csv         # 8,000 return line items (RMALs)
│   ├── return_authorizations.csv# 3,862 approved return authorizations
│   ├── return_shipments.csv     # 3,862 tracking and carrier events
│   ├── inspections.csv          # 4,576 physical condition grading records
│   ├── inventory_dispositions.csv# 4,576 restocking/quarantine routing records
│   ├── refunds.csv              # 4,139 financial payout entries
│   ├── ground_truth.csv         # 210 labelled anomalies and expected decisions
│   └── manifest.json            # Run metadata, row counts, and schema signatures
├── src/
│   ├── config.py                # Global parameters, seed, and business constants
│   ├── master_data.py           # Customer and product catalog generators
│   ├── orders.py                # Order and order line generator with price math
│   ├── returns.py               # RMA and return line generator with policy rules
│   ├── shipments.py             # RA and shipment event generator
│   ├── inspections.py           # Warehouse QA grading and disposition routing
│   ├── refunds.py               # Fee calculations and financial reconciliation
│   ├── anomalies.py             # Labelled edge-case injection engine
│   └── export.py                # Master CLI pipeline and CSV exporter
├── tests/
│   ├── test_validation.py       # PK, FK, enum, date, and math reconciliation test suite
│   └── test_reproducibility.py  # Dual-run SHA-256 hash comparison test
├── requirements.txt
└── README.md
