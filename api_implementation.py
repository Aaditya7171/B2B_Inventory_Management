# Part 3: API Implementation - Low Stock Alert Endpoint
from flask import Flask, request, jsonify
from datetime import datetime, timedelta
import sqlite3
import logging
from decimal import Decimal

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class InventoryAPI:
    """
    Main API class for inventory management operations.
    Handles low stock alerts with business logic and edge cases.
    """
    
    def __init__(self, db_path='inventory.db'):
        self.db_path = db_path
    
    def get_db_connection(self):
        """Get database connection with row factory for easier data access."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

@app.route('/api/v1/inventory/low-stock-alerts/<company_id>', methods=['GET'])
def get_low_stock_alerts(company_id):
    """
    Get low stock alerts for a company with sales velocity analysis.
    
    Business Logic:
    - Products with current_stock <= low_stock_threshold
    - Include recent sales activity (last 30 days configurable)
    - Calculate days until stockout based on sales velocity
    - Include supplier information for reordering
    
    Query Parameters:
    - days_lookback: Days to analyze for sales velocity (default: 30)
    - include_zero_stock: Include products with zero stock (default: true)
    - warehouse_id: Filter by specific warehouse (optional)
    """
    
    try:
        # Input validation
        if not company_id:
            return jsonify({'error': 'Company ID is required'}), 400
        
        # Get query parameters with defaults
        days_lookback = int(request.args.get('days_lookback', 30))
        include_zero_stock = request.args.get('include_zero_stock', 'true').lower() == 'true'
        warehouse_id = request.args.get('warehouse_id')
        
        # Validate parameters
        if days_lookback <= 0 or days_lookback > 365:
            return jsonify({'error': 'days_lookback must be between 1 and 365'}), 400
        
        conn = InventoryAPI().get_db_connection()
        cursor = conn.cursor()
        
        # Verify company exists
        cursor.execute('SELECT id FROM companies WHERE id = ? AND is_active = TRUE', (company_id,))
        if not cursor.fetchone():
            return jsonify({'error': 'Company not found or inactive'}), 404
        
        # Build dynamic query based on parameters
        base_query = '''
        SELECT 
            p.id as product_id,
            p.sku,
            p.name as product_name,
            p.price,
            p.low_stock_threshold,
            w.id as warehouse_id,
            w.name as warehouse_name,
            i.current_stock,
            i.reserved_stock,
            i.available_stock,
            s.id as supplier_id,
            s.name as supplier_name,
            s.email as supplier_email,
            s.phone as supplier_phone,
            -- Calculate average daily sales over the lookback period
            COALESCE(
                (SELECT AVG(daily_sales.total_sold) 
                 FROM (
                    SELECT DATE(sale_date) as sale_day, SUM(quantity_sold) as total_sold
                    FROM sales_transactions st
                    WHERE st.product_id = p.id 
                    AND st.warehouse_id = w.id
                    AND st.sale_date >= DATE('now', '-' || ? || ' days')
                    GROUP BY DATE(sale_date)
                 ) daily_sales), 
                0
            ) as avg_daily_sales,
            -- Total sales in lookback period
            COALESCE(
                (SELECT SUM(quantity_sold)
                 FROM sales_transactions st
                 WHERE st.product_id = p.id 
                 AND st.warehouse_id = w.id
                 AND st.sale_date >= DATE('now', '-' || ? || ' days')), 
                0
            ) as total_recent_sales
        FROM products p
        JOIN inventory i ON p.id = i.product_id
        JOIN warehouses w ON i.warehouse_id = w.id
        LEFT JOIN suppliers s ON p.supplier_id = s.id
        WHERE p.company_id = ?
        AND p.is_active = TRUE
        AND w.is_active = TRUE
        AND i.current_stock <= p.low_stock_threshold
        '''
        
        params = [days_lookback, days_lookback, company_id]
        
        # Add optional filters
        if not include_zero_stock:
            base_query += ' AND i.current_stock > 0'
        
        if warehouse_id:
            base_query += ' AND w.id = ?'
            params.append(warehouse_id)
        
        # Add ordering for consistent results
        base_query += '''
        ORDER BY 
            CASE WHEN i.current_stock = 0 THEN 0 ELSE 1 END,  -- Zero stock first
            (i.current_stock::FLOAT / NULLIF(p.low_stock_threshold, 0)) ASC,  -- Most critical first
            p.name ASC
        '''
        
        logger.info(f'Executing low stock query for company {company_id} with {days_lookback} days lookback')
        cursor.execute(base_query, params)
        results = cursor.fetchall()
        
        # Process results and add calculated fields
        alerts = []
        for row in results:
            # Calculate days until stockout
            avg_daily_sales = float(row['avg_daily_sales'])
            current_stock = int(row['current_stock'])
            
            # Handle edge cases for stockout calculation
            if current_stock == 0:
                days_until_stockout = 0
                urgency_level = 'CRITICAL'
            elif avg_daily_sales <= 0:
                # No recent sales data - use conservative estimate
                days_until_stockout = None
                urgency_level = 'LOW' if current_stock > row['low_stock_threshold'] * 0.5 else 'MEDIUM'
            else:
                days_until_stockout = int(current_stock / avg_daily_sales)
                # Determine urgency based on days until stockout
                if days_until_stockout <= 7:
                    urgency_level = 'CRITICAL'
                elif days_until_stockout <= 14:
                    urgency_level = 'HIGH'
                elif days_until_stockout <= 30:
                    urgency_level = 'MEDIUM'
                else:
                    urgency_level = 'LOW'
            
            # Calculate stock coverage ratio
            stock_coverage_ratio = (current_stock / max(row['low_stock_threshold'], 1)) * 100
            
            alert = {
                'product_id': row['product_id'],
                'sku': row['sku'],
                'product_name': row['product_name'],
                'price': str(row['price']) if row['price'] else None,
                'warehouse': {
                    'id': row['warehouse_id'],
                    'name': row['warehouse_name']
                },
                'stock_info': {
                    'current_stock': current_stock,
                    'reserved_stock': int(row['reserved_stock']),
                    'available_stock': int(row['available_stock']),
                    'low_stock_threshold': int(row['low_stock_threshold']),
                    'stock_coverage_ratio': round(stock_coverage_ratio, 1)
                },
                'sales_analysis': {
                    'avg_daily_sales': round(avg_daily_sales, 2),
                    'total_recent_sales': int(row['total_recent_sales']),
                    'analysis_period_days': days_lookback,
                    'days_until_stockout': days_until_stockout
                },
                'supplier': {
                    'id': row['supplier_id'],
                    'name': row['supplier_name'],
                    'email': row['supplier_email'],
                    'phone': row['supplier_phone']
                } if row['supplier_id'] else None,
                'urgency_level': urgency_level,
                'generated_at': datetime.utcnow().isoformat()
            }
            alerts.append(alert)
        
        # Generate summary statistics
        summary = {
            'total_alerts': len(alerts),
            'critical_alerts': len([a for a in alerts if a['urgency_level'] == 'CRITICAL']),
            'high_priority_alerts': len([a for a in alerts if a['urgency_level'] == 'HIGH']),
            'zero_stock_products': len([a for a in alerts if a['stock_info']['current_stock'] == 0]),
            'products_without_supplier': len([a for a in alerts if a['supplier'] is None])
        }
        
        logger.info(f'Generated {len(alerts)} low stock alerts for company {company_id}')
        
        return jsonify({
            'success': True,
            'company_id': company_id,
            'summary': summary,
            'alerts': alerts,
            'generated_at': datetime.utcnow().isoformat(),
            'parameters': {
                'days_lookback': days_lookback,
                'include_zero_stock': include_zero_stock,
                'warehouse_filter': warehouse_id
            }
        }), 200
    
    except ValueError as e:
        logger.warning(f'Invalid parameter: {e}')
        return jsonify({'error': f'Invalid parameter: {str(e)}'}), 400
    
    except sqlite3.Error as e:
        logger.error(f'Database error: {e}')
        return jsonify({'error': 'Database error occurred'}), 500
    
    except Exception as e:
        logger.error(f'Unexpected error in low stock alerts: {e}')
        return jsonify({'error': 'Internal server error'}), 500
    
    finally:
        if 'conn' in locals():
            conn.close()

@app.route('/api/v1/inventory/reorder-suggestions/<company_id>', methods=['GET'])
def get_reorder_suggestions(company_id):
    """
    Get intelligent reorder suggestions based on sales velocity and lead times.
    
    Additional endpoint to complement low stock alerts with actionable recommendations.
    """
    try:
        conn = InventoryAPI().get_db_connection()
        cursor = conn.cursor()
        
        # Query for products that need reordering with suggested quantities
        cursor.execute('''
        SELECT 
            p.id, p.sku, p.name, p.reorder_quantity,
            i.current_stock, i.warehouse_id, w.name as warehouse_name,
            s.name as supplier_name, s.email as supplier_email,
            -- Calculate suggested order quantity based on sales velocity
            CASE 
                WHEN avg_sales.daily_avg > 0 
                THEN CAST(avg_sales.daily_avg * 30 AS INTEGER)  -- 30 days supply
                ELSE p.reorder_quantity 
            END as suggested_quantity
        FROM products p
        JOIN inventory i ON p.id = i.product_id
        JOIN warehouses w ON i.warehouse_id = w.id
        LEFT JOIN suppliers s ON p.supplier_id = s.id
        LEFT JOIN (
            SELECT 
                product_id, 
                warehouse_id,
                AVG(quantity_sold) as daily_avg
            FROM sales_transactions 
            WHERE sale_date >= DATE('now', '-30 days')
            GROUP BY product_id, warehouse_id
        ) avg_sales ON p.id = avg_sales.product_id AND i.warehouse_id = avg_sales.warehouse_id
        WHERE p.company_id = ?
        AND i.current_stock <= p.low_stock_threshold
        AND p.is_active = TRUE
        AND s.is_active = TRUE
        ORDER BY i.current_stock ASC, avg_sales.daily_avg DESC
        ''', (company_id,))
        
        suggestions = []
        for row in cursor.fetchall():
            suggestions.append({
                'product_id': row['id'],
                'sku': row['sku'],
                'product_name': row['name'],
                'current_stock': row['current_stock'],
                'warehouse': row['warehouse_name'],
                'supplier': row['supplier_name'],
                'supplier_email': row['supplier_email'],
                'suggested_order_quantity': row['suggested_quantity'],
                'default_reorder_quantity': row['reorder_quantity']
            })
        
        return jsonify({
            'success': True,
            'reorder_suggestions': suggestions,
            'generated_at': datetime.utcnow().isoformat()
        }), 200
    
    except Exception as e:
        logger.error(f'Error generating reorder suggestions: {e}')
        return jsonify({'error': 'Internal server error'}), 500
    
    finally:
        if 'conn' in locals():
            conn.close()

# Health check endpoint
@app.route('/api/v1/health', methods=['GET'])
def health_check():
    """Simple health check endpoint for monitoring."""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'version': '1.0.0'
    }), 200

if __name__ == '__main__':
    # Production considerations:
    # - Use proper WSGI server (gunicorn, uwsgi)
    # - Enable SSL/TLS
    # - Add rate limiting
    # - Implement JWT authentication
    # - Add request/response logging
    # - Use environment variables for configuration
    app.run(host='0.0.0.0', port=5000, debug=False)
