# E-Commerce Order & Returns Synthetic Data Dictionary

## 1. Core Entities & Cardinality
- **Customer** (1 : N) **Order**
- **Order** (1 : N) **OrderLine**
- **Order** (1 : N) **ReturnRequest** (RMA)
- **ReturnRequest** (1 : N) **ReturnLine** (RMAL)
- **ReturnRequest** (1 : 1) **ReturnAuthorization** (RA)
- **ReturnAuthorization** (1 : 1) **ReturnShipment** (RTS)
- **ReturnShipment** (1 : N) **Inspection** (INS)
- **ReturnRequest** (1 : N) **Refund** (REF)
- **Inspection** (1 : 1) **InventoryDisposition** (DISP)

---

## 2. Field Specifications

### 2.1 Customer
| Field Name | Type | Req/Opt | Allowed Values | Units | Uniqueness | Validation Rule |
|---|---|---|---|---|---|---|
| `customer_id` | String | Required | Regex: `^CUST-\d{6}$` | Dimension | Unique (PK) | Must match zero-padded 6 digits |
| `customer_name` | String | Required | Valid Full Name | Dimension | Non-unique | Length between 2 and 100 characters |
| `email` | String | Required | RFC 5322 Email Format | Dimension | Unique | Must contain `@` and valid domain |
| `account_created_at` | DateTime | Required | ISO 8601 UTC | Timestamp | Non-unique | Must be before first order date |
| `customer_tier` | Enum | Required | `['STANDARD', 'GOLD', 'PLATINUM']` | Dimension | Non-unique | Must match allowed enum |

### 2.2 Order
| Field Name | Type | Req/Opt | Allowed Values | Units | Uniqueness | Validation Rule |
|---|---|---|---|---|---|---|
| `order_id` | String | Required | Regex: `^ORD-2026-\d{6}$` | Dimension | Unique (PK) | Deterministic ID sequence |
| `customer_id` | String | Required | References `Customer.customer_id` | Dimension | Non-unique (FK) | Must exist in Customer table |
| `order_date` | DateTime | Required | ISO 8601 UTC | Timestamp | Non-unique | Must be after customer creation |
| `order_status` | Enum | Required | `['COMPLETED', 'CANCELLED', 'DELIVERED']` | Dimension | Non-unique | Lifecycle state |
| `currency` | Enum | Required | `['USD']` | Currency | Non-unique | Static USD |
| `subtotal_amount` | Decimal | Required | Positive real (2 decimal places) | USD ($) | Non-unique | Sum of `OrderLine.line_total` |
| `discount_amount` | Decimal | Required | Non-negative real (2 decimal places) | USD ($) | Non-unique | Cannot exceed `subtotal_amount` |
| `tax_amount` | Decimal | Required | Non-negative real (2 decimal places) | USD ($) | Non-unique | Exactly 8% of taxable subtotal |
| `total_paid_amount` | Decimal | Required | Positive real (2 decimal places) | USD ($) | Non-unique | `subtotal - discount + tax` |
| `delivery_date` | DateTime | Optional | ISO 8601 UTC | Timestamp | Non-unique | Required if DELIVERED; `order_date + 2..7 days` |

### 2.3 OrderLine
| Field Name | Type | Req/Opt | Allowed Values | Units | Uniqueness | Validation Rule |
|---|---|---|---|---|---|---|
| `order_line_id` | String | Required | `ORDL-<order_id>-<01..99>` | Dimension | Unique (PK) | Compound key |
| `order_id` | String | Required | References `Order.order_id` | Dimension | Non-unique (FK) | Must exist in Order table |
| `line_number` | Integer | Required | `1..99` | Sequence | Non-unique | 1-indexed sequential per order |
| `sku_id` | String | Required | Regex: `^SKU-\d{6}$` | Dimension | Non-unique | From product catalog |
| `category` | Enum | Required | `['APPAREL', 'ELECTRONICS', 'HOME', 'HYGIENE_PERSONAL_CARE', 'FINAL_SALE']` | Dimension | Non-unique | Product category |
| `unit_price` | Decimal | Required | Positive real (2 decimal places) | USD ($) | Non-unique | `> 0.00` |
| `quantity` | Integer | Required | $\ge 1$ | Units | Non-unique | Purchased units |
| `line_discount` | Decimal | Required | Non-negative real (2 decimal places) | USD ($) | Non-unique | Cannot exceed `unit_price * quantity` |
| `line_total` | Decimal | Required | Positive real (2 decimal places) | USD ($) | Non-unique | `(unit_price * quantity) - line_discount` |
| `returnable` | Boolean | Required | `True` / `False` | Flag | Non-unique | `False` if HYGIENE_PERSONAL_CARE or FINAL_SALE |

### 2.4 ReturnRequest (RMA)
| Field Name | Type | Req/Opt | Allowed Values | Units | Uniqueness | Validation Rule |
|---|---|---|---|---|---|---|
| `return_request_id` | String | Required | Regex: `^RMA-2026-\d{6}$` | Dimension | Unique (PK) | Deterministic ID sequence |
| `order_id` | String | Required | References `Order.order_id` | Dimension | Non-unique (FK) | Parent order must be DELIVERED |
| `customer_id` | String | Required | References `Customer.customer_id` | Dimension | Non-unique (FK) | Must match `Order.customer_id` |
| `request_date` | DateTime | Required | ISO 8601 UTC | Timestamp | Non-unique | Must be after `Order.delivery_date` |
| `policy_window_days` | Integer | Required | `30` | Days | Non-unique | Standard return policy window |
| `days_since_delivery` | Integer | Required | $\ge 0$ | Days | Non-unique | `(request_date - delivery_date).days` |
| `request_status` | Enum | Required | `['SUBMITTED', 'APPROVED', 'REJECTED', 'COMPLETED', 'CANCELLED']` | Dimension | Non-unique | State machine status |

### 2.5 ReturnLine
| Field Name | Type | Req/Opt | Allowed Values | Units | Uniqueness | Validation Rule |
|---|---|---|---|---|---|---|
| `return_line_id` | String | Required | `RMAL-<return_request_id>-<01..99>` | Dimension | Unique (PK) | Compound key |
| `return_request_id` | String | Required | References `ReturnRequest.return_request_id` | Dimension | Non-unique (FK) | Must exist in ReturnRequest |
| `order_line_id` | String | Required | References `OrderLine.order_line_id` | Dimension | Non-unique (FK) | Must belong to parent order |
| `return_reason` | Enum | Required | `['DEFECTIVE', 'WRONG_ITEM', 'DOES_NOT_FIT', 'CHANGED_MIND', 'NOT_AS_DESCRIBED']` | Dimension | Non-unique | Customer provided reason |
| `requested_quantity` | Integer | Required | $\ge 1$ | Units | Non-unique | Baseline $\le$ `OrderLine.quantity` |
| `approved_quantity` | Integer | Required | $\ge 0$ | Units | Non-unique | Baseline $\le$ `requested_quantity` |
| `line_status` | Enum | Required | `['PENDING', 'APPROVED', 'REJECTED']` | Dimension | Non-unique | Line-level approval status |

### 2.6 ReturnAuthorization (RA)
| Field Name | Type | Req/Opt | Allowed Values | Units | Uniqueness | Validation Rule |
|---|---|---|---|---|---|---|
| `ra_id` | String | Required | Regex: `^RA-2026-\d{6}$` | Dimension | Unique (PK) | Deterministic ID sequence |
| `return_request_id` | String | Required | References `ReturnRequest.return_request_id` | Dimension | Unique (FK) | 1:1 relationship with RMA |
| `authorized_date` | DateTime | Required | ISO 8601 UTC | Timestamp | Non-unique | $\ge$ `request_date` |
| `expires_at` | DateTime | Required | ISO 8601 UTC | Timestamp | Non-unique | Exactly `authorized_date + 14 days` |
| `status` | Enum | Required | `['ACTIVE', 'EXPIRED', 'FULFILLED', 'VOID']` | Dimension | Non-unique | Authorization status |

### 2.7 ReturnShipment
| Field Name | Type | Req/Opt | Allowed Values | Units | Uniqueness | Validation Rule |
|---|---|---|---|---|---|---|
| `shipment_id` | String | Required | Regex: `^RTS-2026-\d{6}$` | Dimension | Unique (PK) | Deterministic ID sequence |
| `ra_id` | String | Required | References `ReturnAuthorization.ra_id` | Dimension | Unique (FK) | 1:1 relationship with RA |
| `carrier` | Enum | Required | `['UPS', 'FEDEX', 'USPS', 'DHL']` | Dimension | Non-unique | Logistics carrier |
| `tracking_number` | String | Required | Carrier Tracking String | Dimension | Unique | Non-empty alphanumeric |
| `shipped_date` | DateTime | Required | ISO 8601 UTC | Timestamp | Non-unique | $\ge$ `authorized_date` |
| `delivered_to_wh_date` | DateTime | Optional | ISO 8601 UTC | Timestamp | Non-unique | $\ge$ `shipped_date`; null if lost/in-transit |
| `shipment_status` | Enum | Required | `['LABEL_CREATED', 'IN_TRANSIT', 'DELIVERED', 'LOST_IN_TRANSIT']` | Dimension | Non-unique | Shipping lifecycle state |

### 2.8 Inspection
| Field Name | Type | Req/Opt | Allowed Values | Units | Uniqueness | Validation Rule |
|---|---|---|---|---|---|---|
| `inspection_id` | String | Required | Regex: `^INS-2026-\d{6}$` | Dimension | Unique (PK) | Deterministic ID sequence |
| `shipment_id` | String | Required | References `ReturnShipment.shipment_id` | Dimension | Non-unique (FK) | Parent shipment must be DELIVERED |
| `return_line_id` | String | Required | References `ReturnLine.return_line_id` | Dimension | Unique (FK) | 1:1 with approved ReturnLine |
| `inspection_date` | DateTime | Required | ISO 8601 UTC | Timestamp | Non-unique | $\ge$ `delivered_to_wh_date` |
| `item_condition` | Enum | Required | `['UNOPENED_PERFECT', 'OPENED_INTACT', 'DAMAGED_REPAIRABLE', 'SCRAP_UNSALVAGEABLE', 'WRONG_ITEM_RECEIVED']` | Dimension | Non-unique | Physical inspection outcome |
| `inspector_id` | String | Required | Regex: `^INSP-\d{2}$` | Dimension | Non-unique | Assigned warehouse staff ID |
| `passed_inspection` | Boolean | Required | `True` / `False` | Flag | Non-unique | `True` if condition eligible for refund |

### 2.9 Refund
| Field Name | Type | Req/Opt | Allowed Values | Units | Uniqueness | Validation Rule |
|---|---|---|---|---|---|---|
| `refund_id` | String | Required | Regex: `^REF-2026-\d{6}$` | Dimension | Unique (PK) | Deterministic ID sequence |
| `return_request_id` | String | Required | References `ReturnRequest.return_request_id` | Dimension | Non-unique (FK) | Parent RMA |
| `inspection_id` | String | Required | References `Inspection.inspection_id` | Dimension | Unique (FK) | 1:1 with valid Inspection |
| `refund_date` | DateTime | Required | ISO 8601 UTC | Timestamp | Non-unique | $\ge$ `inspection_date` |
| `gross_refund_amount` | Decimal | Required | Non-negative real (2 decimal places) | USD ($) | Non-unique | Based on line paid price $\times$ quantity |
| `restocking_fee` | Decimal | Required | Non-negative real (2 decimal places) | USD ($) | Non-unique | Category or condition penalty |
| `return_shipping_fee` | Decimal | Required | Non-negative real (2 decimal places) | USD ($) | Non-unique | Standard deduction (e.g. $5.99) or $0.00 |
| `net_refund_amount` | Decimal | Required | Non-negative real (2 decimal places) | USD ($) | Non-unique | `gross - restocking_fee - shipping_fee` |
| `refund_status` | Enum | Required | `['PROCESSED', 'FAILED', 'DUPLICATE_BLOCKED']` | Dimension | Non-unique | Financial transaction status |

### 2.10 InventoryDisposition
| Field Name | Type | Req/Opt | Allowed Values | Units | Uniqueness | Validation Rule |
|---|---|---|---|---|---|---|
| `disposition_id` | String | Required | Regex: `^DISP-2026-\d{6}$` | Dimension | Unique (PK) | Deterministic ID sequence |
| `inspection_id` | String | Required | References `Inspection.inspection_id` | Dimension | Unique (FK) | 1:1 with Inspection |
| `disposition_action` | Enum | Required | `['RESTOCK', 'REFURBISH', 'QUARANTINE', 'SCRAP']` | Dimension | Non-unique | Destination action |
| `disposition_date` | DateTime | Required | ISO 8601 UTC | Timestamp | Non-unique | $\ge$ `inspection_date` |
| `warehouse_location` | String | Required | Regex: `^[A-Z]{2}-[0-9]{2}-[0-9]{2}$` | Dimension | Non-unique | Bin/shelf location |