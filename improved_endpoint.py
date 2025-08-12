# Improved Inventory Management Endpoint with Best Practices
from flask import Flask, request, jsonify
from decimal import Decimal, InvalidOperation
import sqlite3
import logging
from datetime import datetime
import uuid

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ValidationError(Exception):
    pass

class DatabaseError(Exception):
    pass

@app.route('/add_product', methods=['POST'])
def add_product():
    """
    Add a new product with inventory to the system.
    Includes proper validation, transaction handling, and error responses.
    """
    try:
        data = request.get_json()
        
        # Input validation with proper error messages
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        # Validate required fields
        required_fields = ['sku', 'name', 'price', 'warehouse_id', 'quantity']
        for field in required_fields:
            if field not in data or data[field] is None:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Extract and validate data
        sku = str(data['sku']).strip()
        name = str(data['name']).strip()
        warehouse_id = int(data['warehouse_id'])
        quantity = int(data['quantity'])
        
        # Validate business rules
        if not sku:
            raise ValidationError('SKU cannot be empty')
        if not name:
            raise ValidationError('Product name cannot be empty')
        if quantity < 0:
            raise ValidationError('Quantity cannot be negative')
        
        # Handle decimal price properly
        try:
            price = Decimal(str(data['price']))
            if price < 0:
                raise ValidationError('Price cannot be negative')
        except (InvalidOperation, ValueError):
            raise ValidationError('Invalid price format')
        
        # Optional fields with defaults
        description = data.get('description', '')
        supplier_id = data.get('supplier_id')
        low_stock_threshold = data.get('low_stock_threshold', 10)
        created_by = data.get('created_by', 'system')  # In real app, get from JWT token
        
        conn = sqlite3.connect('inventory.db')
        conn.row_factory = sqlite3.Row  # Enable column access by name
        
        try:
            # Start transaction
            conn.execute('BEGIN TRANSACTION')
            cursor = conn.cursor()
            
            # Check if warehouse exists
            cursor.execute('SELECT id FROM warehouses WHERE id = ?', (warehouse_id,))
            if not cursor.fetchone():
                raise ValidationError(f'Warehouse {warehouse_id} does not exist')
            
            # Check SKU uniqueness with proper constraint handling
            cursor.execute('SELECT id FROM products WHERE sku = ?', (sku,))
            if cursor.fetchone():
                raise ValidationError(f'Product with SKU {sku} already exists')
            
            # Insert product with all fields
            product_id = str(uuid.uuid4())
            cursor.execute('''
                INSERT INTO products (id, sku, name, description, price, supplier_id, 
                                    low_stock_threshold, created_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (product_id, sku, name, description, str(price), supplier_id,
                  low_stock_threshold, created_by, datetime.utcnow().isoformat()))
            
            # Insert inventory record
            inventory_id = str(uuid.uuid4())
            cursor.execute('''
                INSERT INTO inventory (id, product_id, warehouse_id, current_stock, 
                                     created_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (inventory_id, product_id, warehouse_id, quantity, created_by,
                  datetime.utcnow().isoformat()))
            
            # Log inventory transaction for audit trail
            transaction_id = str(uuid.uuid4())
            cursor.execute('''
                INSERT INTO inventory_transactions (id, product_id, warehouse_id, 
                                                  transaction_type, quantity, reason, 
                                                  created_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (transaction_id, product_id, warehouse_id, 'INITIAL_STOCK', 
                  quantity, 'Product creation', created_by, datetime.utcnow().isoformat()))
            
            # Commit transaction
            conn.commit()
            
            # Log successful creation
            logger.info(f'Product created successfully: SKU={sku}, ID={product_id}, User={created_by}')
            
            # Return comprehensive response with created data
            return jsonify({
                'success': True,
                'message': 'Product and inventory created successfully',
                'data': {
                    'product_id': product_id,
                    'sku': sku,
                    'name': name,
                    'price': str(price),
                    'warehouse_id': warehouse_id,
                    'initial_stock': quantity,
                    'created_at': datetime.utcnow().isoformat()
                }
            }), 201
            
        except sqlite3.IntegrityError as e:
            conn.rollback()
            # Handle race condition where SKU was inserted between check and insert
            if 'UNIQUE constraint failed' in str(e):
                logger.warning(f'Race condition detected for SKU: {sku}')
                return jsonify({'error': f'Product with SKU {sku} already exists'}), 409
            else:
                logger.error(f'Database integrity error: {e}')
                return jsonify({'error': 'Database integrity violation'}), 500
        
        except Exception as e:
            conn.rollback()
            logger.error(f'Transaction failed: {e}')
            raise DatabaseError(f'Failed to create product: {str(e)}')
        
        finally:
            conn.close()
    
    except ValidationError as e:
        logger.warning(f'Validation error: {e}')
        return jsonify({'error': str(e)}), 400
    
    except DatabaseError as e:
        logger.error(f'Database error: {e}')
        return jsonify({'error': 'Internal server error'}), 500
    
    except Exception as e:
        logger.error(f'Unexpected error: {e}')
        return jsonify({'error': 'Internal server error'}), 500

# Additional improvements for production readiness
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f'Internal server error: {error}')
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    app.run(debug=False)  # Never run debug=True in production
