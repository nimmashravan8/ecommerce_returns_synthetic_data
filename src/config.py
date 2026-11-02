"""
Configuration and constants for synthetic e-commerce returns dataset generation.
"""
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class GeneratorConfig:
    # Deterministic Seed
    RANDOM_SEED: int = 20261022

    # Scale Configuration (Full Dataset Targets)
    NUM_CUSTOMERS: int = 10_000
    NUM_PRODUCTS: int = 500
    NUM_ORDERS: int = 30_000
    NUM_RETURN_REQUESTS: int = 5_000
    NUM_RETURN_LINES: int = 8_000

    # Business Rules & Windows
    RETURN_WINDOW_DAYS: int = 30
    RA_EXPIRATION_DAYS: int = 14
    SALES_TAX_RATE: float = 0.08  # 8%
    STANDARD_SHIPPING_FEE: float = 5.99
    RESTOCKING_FEE_RATE: float = 0.15  # 15% on opened goods

    # Date Boundaries
    START_DATE: datetime = datetime(2026, 1, 1, 0, 0, 0)
    END_DATE: datetime = datetime(2026, 10, 31, 23, 59, 59)

    # Categories
    CATEGORIES: tuple = (
        "APPAREL",
        "ELECTRONICS",
        "HOME",
        "HYGIENE_PERSONAL_CARE",  # Non-returnable policy
        "FINAL_SALE",             # Non-returnable policy
    )

    NON_RETURNABLE_CATEGORIES: tuple = (
        "HYGIENE_PERSONAL_CARE",
        "FINAL_SALE",
    )

    # Directory Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    OUTPUT_DIR: Path = BASE_DIR / "output"
    DOCS_DIR: Path = BASE_DIR / "docs"


# Default global instance
CONFIG = GeneratorConfig()