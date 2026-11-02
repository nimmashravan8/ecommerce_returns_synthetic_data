# 📦 Synthetic E-Commerce Returns & Operational Anomaly Dataset

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://ecommercereturnssyntheticdata-46jvmwalp4wujeokp7bvkk.streamlit.app/)

> **Live Interactive Dashboard:** [Access the Cloud Dashboard Here](https://ecommercereturnssyntheticdata-46jvmwalp4wujeokp7bvkk.streamlit.app/)

A deterministic, high-fidelity synthetic data generator, ETL pipeline, and evaluation suite simulating the complete end-to-end e-commerce order, return, logistics tracking, warehouse inspection, inventory disposition, and refund lifecycle.

---

## 🏛️ Project Architecture

```text
ecommerce_returns_synthetic_data/
├── docs/
│   └── data_dictionary.md       # Schema definitions, nullability, enums & foreign keys
├── output/
│   ├── customers.csv            # 10,000 customer profiles
│   ├── products.csv             # 500 SKU catalog entries
│   ├── orders.csv               # 30,000 order headers
│   ├── order_lines.csv          # 52,632 line items
│   ├── return_requests.csv      # 5,000 RMAs (3,862 approved, 1,138 rejected)
│   ├── return_lines.csv         # 8,000 RMALs
│   ├── return_authorizations.csv# 3,862 RAs
│   ├── return_shipments.csv     # 3,862 logistics events
│   ├── inspections.csv          # 4,576 condition grading records
│   ├── inventory_dispositions.csv# 4,576 warehouse disposition routings
│   ├── refunds.csv              # 4,139 financial payouts
│   ├── ground_truth.csv         # 210 isolated anomalies with expected decisions
│   ├── manifest.json            # Run metadata and schema signatures
│   └── ecommerce_returns.db     # Relational SQLite database (~15.7 MB)
├── src/
│   ├── config.py                # Deterministic seed (20261022) & business constants
│   ├── master_data.py           # Customer & Product generators
│   ├── orders.py                # Orders generator with price & tax arithmetic
│   ├── returns.py               # Policy-compliant RMA & ReturnLine generator
│   ├── shipments.py             # RA & ReturnShipment lifecycle generator
│   ├── inspections.py           # QA condition grading & disposition engine
│   ├── refunds.py               # Payout calculations, restocking fees & deductions
│   ├── anomalies.py             # Target edge-case injection engine
│   ├── export.py                # Master CLI orchestration & CSV serializer
│   ├── evaluate.py              # Anomaly detection baseline evaluator (1.0000 F1)
│   ├── load_sqlite.py           # SQLite ETL & analytics reporting pipeline
│   └── dashboard.py            # Streamlit interactive analytics UI
├── tests/
│   ├── test_validation.py       #
