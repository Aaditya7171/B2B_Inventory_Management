# 📦 StockFlow – Inventory Management System (B2B SaaS)

> **Take‑Home Assignment Submission** for the *Inventory Management System for B2B SaaS* case study.  
> **StockFlow** is a B2B inventory management platform that helps small businesses track products, warehouses, and supplier relationships.

---

## 📋 Table of Contents
- [Overview](#-overview)
- [Repository Structure](#-repository-structure)
- [Part 1 – Code Review & Fixes](#-part-1--code-review--fixes)
- [Part 2 – Database Design](#-part-2--database-design)
- [Part 3 – Low Stock Alerts API](#-part-3--low-stock-alerts-api)
- [Assumptions](#-assumptions)
- [How to Run](#-how-to-run)
---

## 💡 Overview

**Assignment Requirements:**
1. **Code Review & Debugging** of a `create_product` API endpoint.  
2. **Database Design** based on partial requirements.  
3. **API Implementation** for `low-stock alerts` with business rules.

---


---

## 🛠 Part 1 – Code Review & Fixes

**Original Issues Found:**
- ❌ No input validation or error handling.  
- ❌ SKU uniqueness not enforced.  
- ❌ Multiple commits → possible partial data commits.  
- ❌ No transaction rollback.  
- ❌ No audit trail for inventory changes.  

**My Fixes & Enhancements:**
- ✅ Added strict field validation.  
- ✅ Enforced SKU uniqueness per company.  
- ✅ Used atomic DB transactions with rollback.  
- ✅ Handled decimals with `Decimal` for accuracy.  
- ✅ Added inventory audit logging (`INITIAL_STOCK` entry).  
- ✅ Supported optional fields (`description`, `supplier_id`, `low_stock_threshold`).  
- ✅ Added UUID primary keys for global uniqueness.  
- ✅ Logging for debug, warnings, and race condition handling.  

---

## 🗄 Part 2 – Database Design

**Highlights:**
- **Multi‑tenant architecture** with `company_id` foreign key on all main entities.
- **Stock integrity** using `CHECK` constraints.
- **Bundle products** support via `product_bundles`.
- **Audit trail** in `inventory_transactions`.
- **Reserved stock** + computed available stock.
- **Views** (e.g., `low_stock_products`) for faster reporting.
- **Indexes** on all frequent query patterns for performance.

**Key Tables:**
- `companies`, `warehouses`, `suppliers`, `users`
- `products`, `product_categories`, `product_bundles`
- `inventory`, `inventory_transactions`, `sales_transactions`

---

## 📊 Part 3 – Low Stock Alerts API

**Features Implemented:**
- Filter by `days_lookback`, `include_zero_stock`, `warehouse_id`.
- Urgency classification (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`).
- Sales velocity analysis → predicts `days_until_stockout`.
- Summary stats: alert counts, zero‑stock count, missing supplier count.
- Supplier details included for reordering.
- **Bonus:** `/reorder-suggestions` endpoint that computes replenishment quantities.

---

## 📌 Assumptions

- SKU uniqueness is **per company** (multi‑tenant behavior).
- Recent sales = last **30 days** by default.
- Low stock threshold controlled at product level.
- `created_by` would come from **authenticated user** (mocked here).
- UUIDs used for PKs for easy scaling and merging.
- In production use **PostgreSQL** (schema uses PG features; for demo SQLite used in code).

---

## 🚀 How to Run

### 1️⃣ Clone repo
git clone https://github.com/Aaditya7171/B2B_Inventory_Management.git
cd stockflow-assignment

### 2️⃣ Setup Python env
python -m venv venv
source venv/bin/activate   # macOS/Linux
venv\Scripts\activate      # Windows

### 3️⃣ Install dependencies
pip install flask

### 4️⃣ Run Part 1 endpoint
python part1_corrected_code.py

### 5️⃣ Run Part 3 endpoints
python part3_low_stock_api.py

### 6️⃣ Test endpoints
Use Postman or cURL as per docstring notes.
