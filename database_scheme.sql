-- Part 2: Database Design - B2B SaaS Inventory Management System
-- Comprehensive schema with proper relationships, constraints, and indexing

-- Companies table (multi-tenant support)
CREATE TABLE companies (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    phone VARCHAR(50),
    address TEXT,
    subscription_tier VARCHAR(50) DEFAULT 'basic',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- Users table (for authentication and audit trails)
CREATE TABLE users (
    id VARCHAR(36) PRIMARY KEY,
    company_id VARCHAR(36) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    role VARCHAR(50) DEFAULT 'user', -- admin, manager, user, viewer
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
);

-- Suppliers table
CREATE TABLE suppliers (
    id VARCHAR(36) PRIMARY KEY,
    company_id VARCHAR(36) NOT NULL,
    name VARCHAR(255) NOT NULL,
    contact_person VARCHAR(255),
    email VARCHAR(255),
    phone VARCHAR(50),
    address TEXT,
    payment_terms VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
);

-- Warehouses table
CREATE TABLE warehouses (
    id VARCHAR(36) PRIMARY KEY,
    company_id VARCHAR(36) NOT NULL,
    name VARCHAR(255) NOT NULL,
    location VARCHAR(255),
    address TEXT,
    manager_id VARCHAR(36),
    capacity_limit INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
    FOREIGN KEY (manager_id) REFERENCES users(id) ON SET NULL
);

-- Product categories table
CREATE TABLE product_categories (
    id VARCHAR(36) PRIMARY KEY,
    company_id VARCHAR(36) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    parent_category_id VARCHAR(36), -- For hierarchical categories
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_category_id) REFERENCES product_categories(id) ON SET NULL
);

-- Products table (core entity)
CREATE TABLE products (
    id VARCHAR(36) PRIMARY KEY,
    company_id VARCHAR(36) NOT NULL,
    sku VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    category_id VARCHAR(36),
    supplier_id VARCHAR(36),
    price DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    cost DECIMAL(12,2) DEFAULT 0.00,
    weight DECIMAL(8,3),
    dimensions VARCHAR(100), -- "L x W x H"
    low_stock_threshold INTEGER DEFAULT 10,
    reorder_quantity INTEGER DEFAULT 50,
    is_bundle BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_by VARCHAR(36) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES product_categories(id) ON SET NULL,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON SET NULL,
    FOREIGN KEY (created_by) REFERENCES users(id),
    UNIQUE(company_id, sku) -- SKU unique per company
);

-- Product bundles mapping (for bundle products)
CREATE TABLE product_bundles (
    id VARCHAR(36) PRIMARY KEY,
    parent_product_id VARCHAR(36) NOT NULL,
    child_product_id VARCHAR(36) NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_product_id) REFERENCES products(id) ON DELETE CASCADE,
    FOREIGN KEY (child_product_id) REFERENCES products(id) ON DELETE CASCADE,
    UNIQUE(parent_product_id, child_product_id)
);

-- Inventory table (current stock levels)
CREATE TABLE inventory (
    id VARCHAR(36) PRIMARY KEY,
    product_id VARCHAR(36) NOT NULL,
    warehouse_id VARCHAR(36) NOT NULL,
    current_stock INTEGER NOT NULL DEFAULT 0,
    reserved_stock INTEGER DEFAULT 0, -- For pending orders
    available_stock INTEGER GENERATED ALWAYS AS (current_stock - reserved_stock) STORED,
    last_counted_at TIMESTAMP,
    created_by VARCHAR(36) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
    FOREIGN KEY (warehouse_id) REFERENCES warehouses(id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES users(id),
    UNIQUE(product_id, warehouse_id), -- One inventory record per product per warehouse
    CHECK (current_stock >= 0),
    CHECK (reserved_stock >= 0),
    CHECK (reserved_stock <= current_stock)
);

-- Inventory transactions (audit trail for all stock movements)
CREATE TABLE inventory_transactions (
    id VARCHAR(36) PRIMARY KEY,
    product_id VARCHAR(36) NOT NULL,
    warehouse_id VARCHAR(36) NOT NULL,
    transaction_type VARCHAR(50) NOT NULL, -- PURCHASE, SALE, ADJUSTMENT, TRANSFER, INITIAL_STOCK
    quantity INTEGER NOT NULL, -- Positive for inbound, negative for outbound
    unit_cost DECIMAL(12,2),
    reference_id VARCHAR(36), -- Order ID, Transfer ID, etc.
    reason VARCHAR(255),
    notes TEXT,
    created_by VARCHAR(36) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
    FOREIGN KEY (warehouse_id) REFERENCES warehouses(id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES users(id)
);

-- Sales data for analytics and reorder calculations
CREATE TABLE sales_transactions (
    id VARCHAR(36) PRIMARY KEY,
    product_id VARCHAR(36) NOT NULL,
    warehouse_id VARCHAR(36) NOT NULL,
    quantity_sold INTEGER NOT NULL,
    unit_price DECIMAL(12,2) NOT NULL,
    total_amount DECIMAL(12,2) NOT NULL,
    customer_id VARCHAR(36),
    order_id VARCHAR(36),
    sale_date DATE NOT NULL,
    created_by VARCHAR(36) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
    FOREIGN KEY (warehouse_id) REFERENCES warehouses(id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES users(id)
);

-- Indexes for performance optimization
CREATE INDEX idx_products_company_sku ON products(company_id, sku);
CREATE INDEX idx_products_supplier ON products(supplier_id);
CREATE INDEX idx_products_category ON products(category_id);
CREATE INDEX idx_inventory_warehouse_product ON inventory(warehouse_id, product_id);
CREATE INDEX idx_inventory_low_stock ON inventory(warehouse_id, current_stock, product_id);
CREATE INDEX idx_inventory_transactions_product_date ON inventory_transactions(product_id, created_at);
CREATE INDEX idx_inventory_transactions_warehouse_date ON inventory_transactions(warehouse_id, created_at);
CREATE INDEX idx_sales_transactions_product_date ON sales_transactions(product_id, sale_date);
CREATE INDEX idx_sales_transactions_warehouse_date ON sales_transactions(warehouse_id, sale_date);
CREATE INDEX idx_users_company ON users(company_id);
CREATE INDEX idx_warehouses_company ON warehouses(company_id);
CREATE INDEX idx_suppliers_company ON suppliers(company_id);

-- Views for common queries
CREATE VIEW low_stock_products AS
SELECT 
    p.id,
    p.company_id,
    p.sku,
    p.name,
    w.name as warehouse_name,
    i.current_stock,
    p.low_stock_threshold,
    s.name as supplier_name,
    s.email as supplier_email
FROM products p
JOIN inventory i ON p.id = i.product_id
JOIN warehouses w ON i.warehouse_id = w.id
LEFT JOIN suppliers s ON p.supplier_id = s.id
WHERE i.current_stock <= p.low_stock_threshold
AND p.is_active = TRUE
AND w.is_active = TRUE;

-- Triggers for automatic timestamp updates
CREATE TRIGGER update_products_timestamp 
    BEFORE UPDATE ON products 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_inventory_timestamp 
    BEFORE UPDATE ON inventory 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Function for timestamp updates (PostgreSQL syntax)
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';
