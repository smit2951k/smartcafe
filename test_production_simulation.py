import os
import sys
import unittest

# Simulate Vercel Production
os.environ["VERCEL"] = "1"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "smartcafe"))

from app import app
from firebase_service import db_manager, is_firebase_live, is_production

class VercelProductionFirestoreTests(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()

    def test_01_environment_check(self):
        self.assertTrue(is_production(), "Environment must detect Vercel production")
        self.assertTrue(is_firebase_live, "Firebase must be connected via credentials")

    def test_02_no_local_json_write_allowed(self):
        with self.assertRaises(RuntimeError) as ctx:
            db_manager._save_local_data()
        self.assertIn("Local JSON persistence is disabled in production", str(ctx.exception))

    def test_03_settings_from_firestore(self):
        settings = db_manager.get_settings()
        self.assertEqual(settings.get("cafe_name"), "Aroma Cafe")

    def test_04_menu_items_and_86_toggle(self):
        items = db_manager.get_menu_items(only_available=False)
        self.assertGreaterEqual(len(items), 12)
        # Test 86 toggle on c2
        toggled = db_manager.toggle_menu_item_86("c2", available=False)
        self.assertFalse(toggled["available"])
        # Restore c2
        restored = db_manager.toggle_menu_item_86("c2", available=True)
        self.assertTrue(restored["available"])

    def test_05_customer_auth_in_firestore(self):
        test_mobile = "9870000001"
        # Cleanup if existed
        existing = db_manager.get_user_by_mobile(test_mobile)
        if existing:
            db_manager.db.collection("users").document(existing["id"]).delete()

        # Register
        cust = db_manager.create_customer("Prod Test Patron", test_mobile, "SecurePass1234!")
        self.assertEqual(cust["mobile"], test_mobile)

        # Verify login
        verified = db_manager.verify_customer(test_mobile, "SecurePass1234!")
        self.assertIsNotNone(verified)
        self.assertEqual(verified["name"], "Prod Test Patron")

        # Wrong password
        wrong = db_manager.verify_customer(test_mobile, "WrongPassword!")
        self.assertIsNone(wrong)

        # Cleanup
        db_manager.db.collection("users").document(cust["id"]).delete()

    def test_06_staff_auth_in_firestore(self):
        admin = db_manager.verify_staff("admin", "admin@123")
        self.assertIsNotNone(admin)
        self.assertEqual(admin["role"], "admin")

    def test_07_order_flow_in_firestore(self):
        order_dict = {
            "id": "ORD-PROD-TEST-999",
            "table_number": "03",
            "table_section": "Architectural Library",
            "customer_name": "Prod Order Tester",
            "customer_mobile": "9870000002",
            "items": [{"item_id": "c1", "name": "Estate Espresso", "quantity": 1, "unit_price": 160, "item_total": 160}],
            "subtotal": 160,
            "discount": 0,
            "tax": 8,
            "total": 168,
            "status": "PENDING",
            "payment_status": "PENDING",
            "payment_method": "Counter Pay"
        }
        created = db_manager.create_order(order_dict)
        self.assertEqual(created["id"], "ORD-PROD-TEST-999")

        # Fetch
        fetched = db_manager.get_order_by_id("ORD-PROD-TEST-999")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["status"], "PENDING")

        # Update status
        updated = db_manager.update_order_status("ORD-PROD-TEST-999", "PREPARING")
        self.assertEqual(updated["status"], "PREPARING")

        # Completed
        comp = db_manager.update_order_status("ORD-PROD-TEST-999", "COMPLETED")
        self.assertEqual(comp["status"], "COMPLETED")

        # Cleanup
        db_manager.db.collection("orders").document("ORD-PROD-TEST-999").delete()
        db_manager.update_table_status("03", "free")

    def test_08_reservation_flow_in_firestore(self):
        res_dict = {
            "id": "RES-PROD-TEST-999",
            "name": "Prod Reservation Guest",
            "mobile": "9870000003",
            "party_size": 2,
            "date": "2026-11-05",
            "time": "18:00",
            "zone": "Courtyard Garden",
            "table_number": "04",
            "status": "CONFIRMED"
        }
        created = db_manager.create_reservation(res_dict)
        self.assertEqual(created["id"], "RES-PROD-TEST-999")

        # Update status
        updated = db_manager.update_reservation_status("RES-PROD-TEST-999", "SEATED")
        self.assertEqual(updated["status"], "SEATED")

        # Cleanup
        db_manager.db.collection("reservations").document("RES-PROD-TEST-999").delete()

    def test_09_production_otp_exposure_shield(self):
        # Register temporary user
        test_mob = "9870000004"
        existing = db_manager.get_user_by_mobile(test_mob)
        if existing:
            db_manager.db.collection("users").document(existing["id"]).delete()
        cust = db_manager.create_customer("Shield User", test_mob, "PassWord1234!")

        # Request OTP
        res = self.client.post("/api/auth/forgot-password/send-otp", json={"mobile": test_mob})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        # In production, stub_otp MUST NOT be returned!
        self.assertNotIn("stub_otp", data, "stub_otp must NEVER be exposed in production API response!")

        # Cleanup
        db_manager.db.collection("users").document(cust["id"]).delete()

if __name__ == "__main__":
    unittest.main()
