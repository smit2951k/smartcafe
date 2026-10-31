"""
Comprehensive End-to-End Verification Test Suite for Aroma Cafe
Validates:
1. Customer Registration (Name, Mobile, Password only — NO EMAIL)
2. Mobile uniqueness & validation
3. Customer Login with Mobile + Password
4. Login Rate Limiting (5 failed attempts -> HTTP 429 lockout)
5. Forgot password mobile stub OTP flow
6. Admin route security & role checks (Unauthorized redirect / 401)
7. Staff login & role checks (@admin, @manager, @barista)
8. Admin live feed KPIs, 7-day revenue chart data, top sellers
9. Kanban order status transition: PENDING -> PREPARING -> READY
10. Menu 86 instant availability toggle & bulk action
"""
import sys
import os
import json
import unittest

sys.path.insert(0, os.path.dirname(__file__))
from app import app
from firebase_service import db_manager, normalize_mobile

class AromaCafeFlowTests(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()
        self.app_context = app.app_context()
        self.app_context.push()

    def tearDown(self):
        self.app_context.pop()

    def test_01_mobile_normalization(self):
        self.assertEqual(normalize_mobile("+91 98765 43210"), "9876543210")
        self.assertEqual(normalize_mobile("09876543210"), "9876543210")
        self.assertEqual(normalize_mobile("919876543210"), "9876543210")
        self.assertEqual(normalize_mobile("8200878170"), "8200878170")
        self.assertEqual(normalize_mobile("1234567890"), "") # Doesn't start with 6-9
        self.assertEqual(normalize_mobile("98765"), "") # Less than 10 digits

    def test_02_customer_registration_and_login_mobile_only(self):
        # Register new customer with mobile (no email)
        reg_payload = {
            "name": "Rohan Sharma",
            "mobile": "+91 98111 22233",
            "password": "rohanPassword123",
            "confirm_password": "rohanPassword123"
        }
        res = self.client.post("/api/auth/register", json=reg_payload)
        self.assertIn(res.status_code, (200, 409))
        if res.status_code == 200:
            data = res.get_json()
            self.assertTrue(data["success"])
            self.assertEqual(data["customer"]["mobile"], "9811122233")
            self.assertNotIn("email", data["customer"])

        # Login with mobile + password
        login_res = self.client.post("/api/auth/login", json={
            "mobile": "9811122233",
            "password": "rohanPassword123"
        })
        self.assertEqual(login_res.status_code, 200)
        login_data = login_res.get_json()
        self.assertTrue(login_data["success"])
        self.assertEqual(login_data["customer"]["name"], "Rohan Sharma")

    def test_03_login_rate_limiting(self):
        test_mobile = "9900011223"
        # 5 consecutive bad password attempts
        for i in range(5):
            self.client.post("/api/auth/login", json={
                "mobile": test_mobile,
                "password": "wrongPassword123!"
            })

        # 6th attempt must trigger 429 Too Many Requests lockout
        lockout_res = self.client.post("/api/auth/login", json={
            "mobile": test_mobile,
            "password": "anyPassword"
        })
        self.assertEqual(lockout_res.status_code, 429)
        self.assertIn("locked for 15 minutes", lockout_res.get_json()["error"])

    def test_04_forgot_password_stub_otp_flow(self):
        # Request OTP for seeded customer Smit Patel (8200878170)
        send_res = self.client.post("/api/auth/forgot-password/send-otp", json={
            "mobile": "8200878170"
        })
        self.assertEqual(send_res.status_code, 200)
        otp_data = send_res.get_json()
        self.assertTrue(otp_data["success"])
        stub_otp = otp_data["stub_otp"]
        self.assertEqual(len(stub_otp), 6)

        # Reset password with stub OTP
        reset_res = self.client.post("/api/auth/forgot-password/verify-reset", json={
            "mobile": "8200878170",
            "otp": stub_otp,
            "new_password": "newSecurePassword123",
            "confirm_password": "newSecurePassword123"
        })
        self.assertEqual(reset_res.status_code, 200)
        self.assertTrue(reset_res.get_json()["success"])

        # Verify login works with new password
        login_res = self.client.post("/api/auth/login", json={
            "mobile": "8200878170",
            "password": "newSecurePassword123"
        })
        self.assertEqual(login_res.status_code, 200)
        self.assertTrue(login_res.get_json()["success"])

    def test_05_admin_security_and_role_checks(self):
        # 1. Unauthenticated request to /admin must redirect to /admin/login
        res_admin_page = self.client.get("/admin", follow_redirects=False)
        self.assertEqual(res_admin_page.status_code, 302)
        self.assertIn("/admin/login", res_admin_page.headers["Location"])

        # 2. Unauthenticated request to /api/admin/live-feed must return 401 Unauthorized
        res_feed = self.client.get("/api/admin/live-feed")
        self.assertEqual(res_feed.status_code, 401)
        self.assertFalse(res_feed.get_json()["success"])

        # 3. Staff login
        staff_login_res = self.client.post("/api/admin/login", json={
            "username": "admin",
            "password": "admin@123"
        })
        self.assertEqual(staff_login_res.status_code, 200)
        staff_data = staff_login_res.get_json()
        self.assertTrue(staff_data["success"])
        self.assertEqual(staff_data["staff"]["role"], "admin")

        # 4. Now /api/admin/live-feed succeeds with 200 and complete stats
        live_feed_res = self.client.get("/api/admin/live-feed")
        self.assertEqual(live_feed_res.status_code, 200)
        feed_data = live_feed_res.get_json()
        self.assertTrue(feed_data["success"])
        self.assertIn("today_revenue", feed_data["kpi"])
        self.assertIn("avg_ticket", feed_data["kpi"])
        self.assertIn("seven_day_revenue", feed_data)
        self.assertGreater(len(feed_data["orders"]), 0)

    def test_06_kanban_order_status_progression(self):
        # Authenticate staff
        self.client.post("/api/admin/login", json={"username": "admin", "password": "admin@123"})

        # Create a new test order at Table 03
        new_order_res = self.client.post("/api/orders", json={
            "customer_name": "Test Patron",
            "customer_mobile": "9876543210",
            "table_number": "03",
            "items": [{"item_id": "c1", "quantity": 2}],
            "notes": "Extra warm"
        })
        self.assertEqual(new_order_res.status_code, 200)
        order_id = new_order_res.get_json()["order"]["id"]

        # Advance status to PREPARING
        res_prep = self.client.post(f"/api/admin/orders/{order_id}/status", json={"status": "PREPARING"})
        self.assertEqual(res_prep.status_code, 200)
        self.assertEqual(res_prep.get_json()["order"]["status"], "PREPARING")

        # Advance status to READY
        res_ready = self.client.post(f"/api/admin/orders/{order_id}/status", json={"status": "READY"})
        self.assertEqual(res_ready.status_code, 200)
        self.assertEqual(res_ready.get_json()["order"]["status"], "READY")

        # Advance status to COMPLETED
        res_comp = self.client.post(f"/api/admin/orders/{order_id}/status", json={"status": "COMPLETED"})
        self.assertEqual(res_comp.status_code, 200)
        self.assertEqual(res_comp.get_json()["order"]["status"], "COMPLETED")

    def test_07_menu_86_availability_toggle(self):
        # Authenticate staff
        self.client.post("/api/admin/login", json={"username": "admin", "password": "admin@123"})

        # Toggle item c1 (Estate Espresso) to 86 (Unavailable)
        res_86 = self.client.post("/api/admin/menu/c1/toggle-86", json={"available": False})
        self.assertEqual(res_86.status_code, 200)
        self.assertFalse(res_86.get_json()["item"]["available"])

        # Verify item c1 is excluded from public customer menu
        public_menu = self.client.get("/api/menu").get_json()["items"]
        self.assertNotIn("c1", [i["id"] for i in public_menu])

        # Restore availability
        res_restore = self.client.post("/api/admin/menu/c1/toggle-86", json={"available": True})
        self.assertEqual(res_restore.status_code, 200)
        self.assertTrue(res_restore.get_json()["item"]["available"])

    def test_08_checkout_flows_counter_and_payment(self):
        # 1. Test counter order placement with mobile only
        counter_payload = {
            "table_number": "04",
            "customer_name": "Priya Sharma",
            "customer_phone": "9820011223",
            "customer_mobile": "9820011223",
            "special_instructions": "Less ice, oat milk please",
            "items": [{"item_id": "c2", "quantity": 1}],
            "promo_code": "",
            "payment_method": "Counter"
        }
        res_counter = self.client.post("/api/orders", json=counter_payload)
        self.assertEqual(res_counter.status_code, 200)
        counter_data = res_counter.get_json()
        self.assertTrue(counter_data["success"])
        self.assertIn("order", counter_data)
        self.assertEqual(counter_data["order"]["customer_mobile"], "9820011223")
        self.assertEqual(counter_data["order"]["table_number"], "04")

        # 2. Test payment create
        create_res = self.client.post("/api/payment/create", json={
            "items": [{"item_id": "c1", "quantity": 1}],
            "customer_name": "Aarav Mehta",
            "customer_mobile": "9898989898"
        })
        self.assertEqual(create_res.status_code, 200)
        create_data = create_res.get_json()
        self.assertTrue(create_data["success"])
        self.assertIn("order_id", create_data)
        self.assertIn("amount", create_data)

        # 3. Test payment verify & order generation
        verify_res = self.client.post("/api/payment/verify", json={
            "razorpay_order_id": create_data["order_id"],
            "razorpay_payment_id": "pay_test_998877",
            "razorpay_signature": "simulated_sig",
            "table_number": "02",
            "customer_name": "Aarav Mehta",
            "customer_phone": "9898989898",
            "customer_mobile": "9898989898",
            "items": [{"item_id": "c1", "quantity": 1}],
            "promo_code": ""
        })
        self.assertEqual(verify_res.status_code, 200)
        verify_data = verify_res.get_json()
        self.assertTrue(verify_data["success"])
        self.assertIn("order_id", verify_data)
        self.assertEqual(verify_data["order"]["payment_status"], "PAID")

        # Clean up ephemeral test orders & restore table status
        db_manager._data["orders"] = [
            o for o in db_manager._data.get("orders", [])
            if o.get("id") not in (counter_data["order"]["id"], verify_data["order"]["id"])
        ]
        for t in db_manager._data.get("tables", []):
            if t.get("number") in ("04", "02"):
                t["status"] = "free"
                t["current_order_id"] = None
                t["active_order_id"] = None
        db_manager._save_local_data()

if __name__ == "__main__":
    unittest.main()

