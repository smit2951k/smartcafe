import os
import sys
import unittest
import json
import re

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'smartcafe')))

from app import app
from firebase_service import db_manager

class SmartCafeQRScannerTests(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()

    def test_01_physical_qr_files_exist(self):
        """Verify real physical PNG QR codes are generated in qrcode/"""
        qr_dir = os.path.join(self.app.root_path, "qrcode")
        self.assertTrue(os.path.isdir(qr_dir), "qrcode directory should exist")
        
        for i in range(1, 9):
            filename = f"table-0{i}.png"
            filepath = os.path.join(qr_dir, filename)
            self.assertTrue(os.path.isfile(filepath), f"Physical QR file {filename} must exist")
            self.assertGreater(os.path.getsize(filepath), 100, f"{filename} must be a valid PNG file")

    def test_02_method_a_phone_camera_direct_url(self):
        """Customer scans physical QR with phone camera -> /table/03"""
        with self.client as c:
            res = c.get('/table/03')
            self.assertEqual(res.status_code, 200)
            html = res.data.decode('utf-8')
            self.assertIn("Table 03 Detected", html)
            self.assertIn("/menu", html)
            
            # Check server-side session
            with c.session_transaction() as sess:
                self.assertEqual(sess.get('table_id'), '03')
                self.assertEqual(sess.get('table_number'), '03')

    def test_03_invalid_table_url(self):
        """Customer scans unknown or invalid table QR -> 404 Table Not Found"""
        with self.client as c:
            res = c.get('/table/999')
            self.assertEqual(res.status_code, 404)
            html = res.data.decode('utf-8')
            self.assertIn("Table Not Found", html)
            self.assertIn("Scan Table QR", html)

    def test_04_dedicated_scan_table_route(self):
        """Verify /scan-table route loads clean camera scanner experience"""
        with self.client as c:
            res = c.get('/scan-table')
            self.assertEqual(res.status_code, 200)
            html = res.data.decode('utf-8')
            self.assertIn("Scan your table QR", html)
            self.assertIn("Point your camera at the QR code", html)
            self.assertIn("CANCEL", html)
            self.assertIn("pageScannerViewport", html)

    def test_05_method_b_api_table_validation(self):
        """Website camera scanner detects QR and calls /api/table/validate/03"""
        with self.client as c:
            res = c.post('/api/table/validate/03')
            self.assertEqual(res.status_code, 200)
            data = json.loads(res.data.decode('utf-8'))
            self.assertTrue(data.get('success'))
            self.assertEqual(data.get('table_id'), '03')
            self.assertEqual(data.get('table_number'), '03')
            
            with c.session_transaction() as sess:
                self.assertEqual(sess.get('table_id'), '03')
                self.assertEqual(sess.get('table_number'), '03')

    def test_06_api_table_validation_invalid(self):
        """Validation API returns 404 for nonexistent table"""
        with self.client as c:
            res = c.post('/api/table/validate/invalid_table')
            self.assertEqual(res.status_code, 404)
            data = json.loads(res.data.decode('utf-8'))
            self.assertFalse(data.get('success'))
            self.assertEqual(data.get('error'), 'Table not found.')

    def test_07_api_active_table(self):
        """Check /api/table/active retrieves session table"""
        with self.client as c:
            # Initially no table
            res = c.get('/api/table/active')
            self.assertEqual(res.status_code, 200)
            data = json.loads(res.data.decode('utf-8'))
            self.assertFalse(data.get('active'))

            # Set table
            c.post('/api/table/validate/05')
            res2 = c.get('/api/table/active')
            data2 = json.loads(res2.data.decode('utf-8'))
            self.assertTrue(data2.get('active'))
            self.assertEqual(data2.get('table_id'), '05')

    def test_08_reservations_page_is_clean_of_qr_preview(self):
        """Verify reservation page contains NO QR code display panel or table preview buttons"""
        with self.client as c:
            res = c.get('/reservations')
            self.assertEqual(res.status_code, 200)
            html = res.data.decode('utf-8')
            
            # Must NOT contain old station identification or QR previews
            self.assertNotIn("previewTableQr", html)
            self.assertNotIn("table-qr-sidebar", html)
            self.assertNotIn("Select Station to Preview QR", html)
            self.assertNotIn("Station Identification", html)
            self.assertNotIn("SMARTCAFE FLAGSHIP", html.replace("Flagship", "FLAGSHIP") if "Preview QR" in html else "")
            
            # Must contain clean reservation elements
            self.assertIn("Reserve Your Table", html)
            self.assertIn("Atmosphere & Seating Room", html)
            self.assertIn("Guest Information", html)

    def test_09_table_change_preserves_tray(self):
        """Changing table must NOT clear tray or create an order"""
        with self.client as c:
            # Establish Table 03
            c.get('/table/03')
            
            # Put item in cart
            items = [{"item_id": "item_espresso_01", "name": "Estate Espresso", "price": 280, "quantity": 2}]
            res = c.post('/api/cart/sync', json={"items": items})
            self.assertEqual(res.status_code, 200)
            
            # Customer moves to Table 05
            c.get('/table/05')
            with c.session_transaction() as sess:
                self.assertEqual(sess.get('table_id'), '05')
                # Cart must be preserved!
                cart = sess.get('cart', [])
                self.assertEqual(len(cart), 1)
                self.assertEqual(cart[0]['item_id'], 'item_espresso_01')

    def test_10_qr_scan_never_creates_order(self):
        """Scanning QR must NEVER create an order, reservation, or payment"""
        with self.client as c:
            orders_before = len(db_manager.get_orders())
            
            c.get('/table/02')
            c.post('/api/table/validate/04')
            c.get('/table/07')
            
            orders_after = len(db_manager.get_orders())
            self.assertEqual(orders_before, orders_after, "Scanning QR must NEVER create orders")

    def test_11_order_contains_validated_session_table_id(self):
        """Order creation strictly takes table_id from validated session"""
        with self.client as c:
            # Set Table 03 in session
            c.get('/table/03')
            
            # Create order
            order_data = {
                "items": [{"item_id": "item_espresso_01", "name": "Estate Espresso", "price": 280, "quantity": 1}],
                "customer_name": "Test Patron",
                "customer_email": "test@smartcafe.internal"
            }
            res = c.post('/api/orders', json=order_data)
            self.assertEqual(res.status_code, 200)
            data = json.loads(res.data.decode('utf-8'))
            order = data.get('order')
            self.assertIsNotNone(order)
            self.assertEqual(order.get('table_id'), '03')
            self.assertEqual(order.get('table_number'), '03')

    def test_12_nav_and_modals_exist_in_base(self):
        """Verify Camera Scanner Modal, Table Status Modal, and nav badges exist in base"""
        with self.client as c:
            res = c.get('/')
            html = res.data.decode('utf-8')
            self.assertIn('cameraScannerModal', html)
            self.assertIn('tableStatusModal', html)
            self.assertIn('activeTableBadge', html)
            self.assertIn('mobileScanTableBtn', html)
            self.assertIn('qr_scanner.js', html)
            self.assertIn('html5-qrcode.min.js', html)

if __name__ == '__main__':
    unittest.main()
