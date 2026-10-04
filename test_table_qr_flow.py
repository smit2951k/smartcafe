import os
import requests
from PIL import Image

BASE_URL = "http://127.0.0.1:5000"

def run_table_qr_tests():
    print("=" * 65)
    print("SMARTCAFE: TABLE QR CODE & RESERVATION INTEGRATION TEST SUITE")
    print("=" * 65)

    session = requests.Session()

    # 1. Verify QR Directory and Image Files
    print("\n[TEST 1] Verify qrcode/ directory and generated PNG images")
    qr_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qrcode")
    assert os.path.exists(qr_dir), "qrcode/ folder does not exist"
    
    expected_tables = ["01", "02", "03", "04", "05", "06", "07", "08", "takeaway"]
    for t in expected_tables:
        file_path = os.path.join(qr_dir, f"table-{t}.png")
        assert os.path.exists(file_path), f"Missing QR file: {file_path}"
        with Image.open(file_path) as img:
            assert img.format == "PNG", f"{file_path} is not PNG format"
            assert img.size[0] >= 100 and img.size[1] >= 100, f"{file_path} resolution too small"
    print(f"  --> PASS: All 9 QR code images exist with valid PNG format and high print resolution.")

    # 2. Verify Serving of QR Images via Flask Route
    print("\n[TEST 2] Verify /qrcode/<filename> endpoint")
    qr_resp = session.get(f"{BASE_URL}/qrcode/table-03.png")
    assert qr_resp.status_code == 200, f"/qrcode/table-03.png returned status {qr_resp.status_code}"
    assert "image/png" in qr_resp.headers.get("Content-Type", ""), "Response is not image/png"
    print("  --> PASS: /qrcode/table-03.png successfully served.")

    # 3. Verify Reservation Page Layout has NO QR display panel (Clean Figma focus)
    print("\n[TEST 3] Verify Reservation Page (/reservations) has NO QR display panel")
    res_resp = session.get(f"{BASE_URL}/reservations")
    assert res_resp.status_code == 200, "Reservations page failed to load"
    html = res_resp.text
    assert "table-qr-sidebar" not in html, "FAIL: table-qr-sidebar must NOT be on reservations page"
    assert "qrPreviewImg" not in html, "FAIL: qrPreviewImg must NOT be on reservations page"
    assert "Select Station to Preview QR" not in html, "FAIL: QR preview selector must NOT be on reservations page"
    assert "Reserve Your Table" in html, "Reservation title missing"
    print("  --> PASS: Reservation page is clean and focused. Zero QR display panels on website.")

    # 3b. Verify Dedicated /scan-table Route and Camera Scanner Modal
    print("\n[TEST 3b] Verify /scan-table route and Camera Scanner components")
    scan_resp = session.get(f"{BASE_URL}/scan-table")
    assert scan_resp.status_code == 200, "/scan-table route failed to load"
    assert "Scan your table QR" in scan_resp.text, "Scanner heading missing"
    assert "pageScannerViewport" in scan_resp.text, "Scanner viewport missing"
    print("  --> PASS: Dedicated /scan-table camera scanner route is live.")

    # Helper: Check total orders in system
    def get_order_count():
        r = session.get(f"{BASE_URL}/api/orders")
        return len(r.json().get("orders", [])) if r.status_code == 200 else 0

    initial_orders = get_order_count()

    # 4. Table Detection: Scan Table 03 (/table/03)
    print("\n[TEST 4] Scan Table 03 QR code (/table/03)")
    t3_resp = session.get(f"{BASE_URL}/table/03")
    assert t3_resp.status_code == 200, f"Table 03 detection failed: {t3_resp.status_code}"
    assert "Table 03" in t3_resp.text, "'Table 03' not found in detected page"
    assert "Architectural Library" in t3_resp.text, "Table section not displayed"
    assert "You are ordering from this table." in t3_resp.text, "Confirmation message missing"
    assert "Continue to Menu" in t3_resp.text, "Continue to Menu link missing"
    
    # Verify scanning did NOT create an order
    assert get_order_count() == initial_orders, "FAIL: Scanning a QR code created an order!"
    print("  --> PASS: Table 03 identified. Zero orders created.")

    # 5. Navbar Shows Detected Table 03
    print("\n[TEST 5] Verify navbar reflects detected Table 03")
    nav_resp = session.get(f"{BASE_URL}/menu")
    assert "Table 03" in nav_resp.text, "Navbar did not update to Table 03"
    print("  --> PASS: Seated station badge displays 'Table 03' across pages.")

    # 6. Add Items to Tray while Seated at Table 03
    print("\n[TEST 6] Add items to tray and verify order association with Table 03")
    cart_items = [
        {"item_id": "c1", "quantity": 1, "name": "Estate Espresso", "price": 160, "selected_options": []},
        {"item_id": "c2", "quantity": 1, "name": "Velvet Flat White", "price": 220, "selected_options": []}
    ]
    sync_resp = session.post(f"{BASE_URL}/api/cart/sync", json={"items": cart_items})
    assert sync_resp.status_code == 200
    assert len(sync_resp.json().get("items", [])) == 2

    # 7. Complete Checkout and Confirm Order is Assigned to Table 03
    order_resp = session.post(f"{BASE_URL}/api/orders", json={
        "items": cart_items,
        "payment_method": "Counter",
        "customer_name": "QR Table Tester"
    })
    assert order_resp.status_code == 200, f"Order creation failed: {order_resp.text}"
    created_order = order_resp.json().get("order", {})
    assert created_order.get("table_id") in ("03", "T03"), f"Expected table_id 03, got {created_order.get('table_id')}"
    print(f"  --> PASS: Order #{created_order.get('id')} correctly created and bound to Table 03.")

    # 8. Table Transition: Change Table to Table 05 (/table/05)
    print("\n[TEST 8] Scan Table 05 QR code to update table destination")
    # Put an item in tray first
    session.post(f"{BASE_URL}/api/cart/sync", json={"items": [cart_items[0]]})
    
    t5_resp = session.get(f"{BASE_URL}/table/05")
    assert t5_resp.status_code == 200
    assert "Table 05" in t5_resp.text
    assert "Main Timber Hall" in t5_resp.text
    assert "Table destination updated" in t5_resp.text or "Table 05" in t5_resp.text
    
    # Check that tray is preserved
    cart_check = session.get(f"{BASE_URL}/api/cart")
    assert len(cart_check.json().get("items", [])) == 1, "Tray lost during table transition"
    
    # Check checkout page receives updated Table 05
    co_resp = session.get(f"{BASE_URL}/checkout")
    assert "Table 05" in co_resp.text or 'value="05" selected' in co_resp.text
    print("  --> PASS: Transition to Table 05 successful. Existing tray preserved intact.")

    # 9. Invalid Table ID Handling (/table/999)
    print("\n[TEST 9] Verify invalid table ID (/table/999)")
    inv_resp = session.get(f"{BASE_URL}/table/999")
    assert inv_resp.status_code == 404, f"Expected 404, got {inv_resp.status_code}"
    assert "Table Not Found" in inv_resp.text, "'Table Not Found' text missing"
    assert "Return to Menu" in inv_resp.text, "Return to Menu link missing"
    print("  --> PASS: Invalid table safely handled with clean SmartCafe 404 template.")

    # 10. Reservation Discrepancy Note Integration
    print("\n[TEST 10] Reservation Integration: Scanned Table differs from Reserved Room")
    user_email = "solarium_patron@smartcafe.internal"
    session.post(f"{BASE_URL}/api/auth/login", json={"email": user_email, "name": "Solarium Patron"})
    # Create reservation in Courtyard Solarium
    res_create = session.post(f"{BASE_URL}/api/reservations", json={
        "name": "Solarium Patron",
        "email": user_email,
        "phone": "+91 99999 88888",
        "date": "2026-10-15",
        "time": "10:30",
        "guests": 2,
        "special_request": "Courtyard Solarium"
    })
    assert res_create.status_code == 200

    # User arrives and scans Table 05 (Main Timber Hall)
    t5_res_resp = session.get(f"{BASE_URL}/table/05")
    assert t5_res_resp.status_code == 200
    assert "Note: Your booked reservation is for Courtyard Solarium" in t5_res_resp.text
    print("  --> PASS: Reservation room discrepancy detected and communicated politely.")

    print("\n" + "=" * 65)
    print("ALL TABLE QR & RESERVATION INTEGRATION TESTS PASSED!")
    print("=" * 65)

if __name__ == "__main__":
    run_table_qr_tests()
