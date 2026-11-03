# 📦 Synthetic E-Commerce Returns & Operational Anomaly Dataset

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://ecommercereturnssyntheticdata-46jvmwalp4wujeokp7bvkk.streamlit.app/)
[![GitHub Repo](https://img.shields.io/badge/GitHub-Repository-181717?logo=github)](https://github.com/nimmashravan8/ecommerce_returns_synthetic_data)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)

> 🚀 **Live Interactive Dashboard:** [Access the Cloud Dashboard Here](https://ecommercereturnssyntheticdata-ujqf5zkwhpausv4iynkm2i.streamlit.app/)

A deterministic, high-fidelity synthetic data generator, ETL pipeline, and evaluation suite simulating the complete end-to-end e-commerce order, return, logistics tracking, warehouse inspection, inventory disposition, and refund lifecycle.

---

## 🏛️ Project Architecture

```text
ecommerce_returns_synthetic_data/
├── docs/
│   └── data_dictionary.md          # Schema definitions, nullability, enums & foreign keys
├── output/
│   ├── customers.csv               # 10,000 customer profiles
│   ├── products.csv                # 500 SKU catalog entries
│   ├── orders.csv                  # 30,000 order headers
│   ├── order_lines.csv             # 52,632 line items
│   ├── return_requests.csv         # 5,000 RMAs (3,862 approved, 1,138 rejected)
│   ├── return_lines.csv            # 8,000 RMALs
│   ├── return_authorizations.csv   # 3,862 RAs
│   ├── shipments.csv               # Forward and return shipments
│   ├── tracking_events.csv         # Carrier scan milestones
│   ├── warehouse_receipts.csv      # Inbound dock scan logs
│   ├── inspections.csv             # Physical quality inspection & grade scoring
│   ├── inventory_dispositions.csv  # Restock, refurbish, scrap, liquidate routing
│   ├── refunds.csv                 # Financial reversals and restocking deductions
│   ├── ground_truth.csv            # 210 injected operational anomalies
│   ├── ecommerce_returns.db        # Fully relational SQLite database
│   └── manifest.json               # Row counts, SHA-256 integrity hashes & metadata
├── src/
│   ├── config.py                   # Global configuration & seed setup
│   ├── generator.py                # Synthetic data generation logic
│   ├── load_sqlite.py              # SQLite ingestion and index building
│   └── dashboard.py                # Streamlit analytics application
├── tests/
│   ├── test_generator.py           # Integrity, uniqueness & foreign key tests
│   └── test_anomalies.py           # Anomaly verification tests
├── requirements.txt
└── README.md