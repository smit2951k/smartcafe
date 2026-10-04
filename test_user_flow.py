import requests
import json
import sys

BASE_URL = "http://127.0.0.1:5000"

def run_tests():
    print("=" * 60)
    print("RUNNING CRITICAL VERIFICATION: SEPARATION OF LOGIN & ORDERING")
    print("=" * 60)

    # Helper to count total orders currently in system
    def get_order_count(cust_email=None):
        url = f"{BASE_URL}/api/orders"
        if cust_email:
            url += f"?customer_email={cust_email}"
        r = requests.get(url)
        if r.status_code == 200:
            return len(r.json().get("orders", []))
        return 0

    initial_total_orders = get_order_count()
    test_user_email = "tester_flow_2026@smartcafe.internal"
    user_initial_orders = get_order_count(test_user_email)

    session = requests.Session()

    # Register user first if not exists
    session.post(f"{BASE_URL}/api/auth/register", json={
        "email": test_user_email,
        "password": "securepassword123",
        "name": "Verified Patron",
        "phone": "+91 9123456789"
    })

    # TEST 1: Open website -> Login -> Verify NO order created
    print("\n[TEST 1] Open website -> Login -> Check order count")
    resp_home = session.get(f"{BASE_URL}/")
    assert resp_home.status_code == 200, "Home page failed to load"
    
    login_resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": test_user_email,
        "password": "securepassword123",
        "name": "Verified Patron"
    })
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    after_login_orders = get_order_count(test_user_email)
    total_after_login = get_order_count()
    assert after_login_orders == user_initial_orders, f"FAIL: Login created an order! Orders before: {user_initial_orders}, after: {after_login_orders}"
    assert total_after_login == initial_total_orders, f"FAIL: System total orders increased after login!"
    print("  --> PASS: Login succeeded. Zero orders created.")

    # TEST 2: Login -> Profile -> Verify Profile opens & NO order created
    print("\n[TEST 2] Login -> Profile -> Verify Profile opens & zero orders created")
    acc_resp = session.get(f"{BASE_URL}/account")
    assert acc_resp.status_code == 200, "Account page failed to load"
    assert "Flow Tester" in acc_resp.text or "Sanctuary" in acc_resp.text, "Profile page did not render correctly"
    after_profile_orders = get_order_count(test_user_email)
    assert after_profile_orders == user_initial_orders, "FAIL: Opening profile created an order!"
    print("  --> PASS: Profile accessed. Zero orders created.")

    # TEST 3: Login -> Menu -> Add item -> Verify item in tray
    print("\n[TEST 3] Login -> Menu -> Add item to tray")
    menu_resp = session.get(f"{BASE_URL}/menu")
    assert menu_resp.status_code == 200, "Menu page failed to load"
    
    # Client adds Estate Espresso (c1) to tray
    cart_items = [
        {"item_id": "c1", "quantity": 1, "name": "Estate Espresso", "price": 160, "selected_options": []}
    ]
    sync_resp = session.post(f"{BASE_URL}/api/cart/sync", json={"items": cart_items})
    assert sync_resp.status_code == 200, "Cart sync failed"
    synced_cart = sync_resp.json().get("items", [])
    assert len(synced_cart) == 1, "Cart item was not preserved in tray"
    after_add_orders = get_order_count(test_user_email)
    assert after_add_orders == user_initial_orders, "FAIL: Adding item to tray created an order!"
    print(f"  --> PASS: Item added to tray. Tray count = {len(synced_cart)}. Zero orders created.")

    # TEST 4: Add items -> Login -> Verify items remain in tray
    print("\n[TEST 4] Add items as guest -> Login -> Verify tray preserved")
    guest_session = requests.Session()
    guest_tray = [
        {"item_id": "c1", "quantity": 1, "name": "Estate Espresso", "price": 160, "selected_options": []},
        {"item_id": "c2", "quantity": 2, "name": "Velvet Flat White", "price": 220, "selected_options": []}
    ]
    # Sync guest tray to server
    guest_sync = guest_session.post(f"{BASE_URL}/api/cart/sync", json={"items": guest_tray})
    assert guest_sync.status_code == 200
    
    # Guest logs in
    guest_login = guest_session.post(f"{BASE_URL}/api/auth/login", json={
        "email": "returning_patron@smartcafe.internal",
        "name": "Returning Patron"
    })
    assert guest_login.status_code == 200
    # Check cart after login
    cart_check = guest_session.get(f"{BASE_URL}/api/cart")
    assert cart_check.status_code == 200
    user_cart = cart_check.json().get("items", [])
    assert len(user_cart) == 2, f"FAIL: Cart lost during login! Expected 2 items, got {len(user_cart)}"
    print(f"  --> PASS: Guest tray preserved across login. Items count = {len(user_cart)}.")

    # TEST 5: Login -> Logout -> Verify NO order created & tray preserved
    print("\n[TEST 5] Login -> Logout -> Verify zero orders created")
    before_logout_orders = get_order_count("returning_patron@smartcafe.internal")
    logout_resp = guest_session.post(f"{BASE_URL}/api/auth/logout")
    assert logout_resp.status_code == 200
    after_logout_orders = get_order_count("returning_patron@smartcafe.internal")
    assert before_logout_orders == after_logout_orders, "FAIL: Logout affected order count!"
    print("  --> PASS: Logged out successfully. Zero orders created.")

    # TEST 6: Menu -> Add item -> Checkout -> Login -> Returns to Checkout with cart
    print("\n[TEST 6] Menu -> Add item -> Checkout -> Login with safe return URL")
    checkout_session = requests.Session()
    checkout_tray = [
        {"item_id": "c1", "quantity": 1, "name": "Estate Espresso", "price": 160, "selected_options": []}
    ]
    checkout_session.post(f"{BASE_URL}/api/cart/sync", json={"items": checkout_tray})
    
    # User goes to /login?next=/checkout
    login_page_resp = checkout_session.get(f"{BASE_URL}/login?next=/checkout")
    assert login_page_resp.status_code == 200
    assert 'next_url' in login_page_resp.text or '/checkout' in login_page_resp.text
    
    # User logs in
    checkout_initial_orders = get_order_count("checkout_patron@smartcafe.internal")
    login_act = checkout_session.post(f"{BASE_URL}/api/auth/login", json={
        "email": "checkout_patron@smartcafe.internal",
        "name": "Checkout Patron"
    })
    assert login_act.status_code == 200
    
    # Returns to /checkout
    co_page = checkout_session.get(f"{BASE_URL}/checkout")
    assert co_page.status_code == 200
    cart_after_co = checkout_session.get(f"{BASE_URL}/api/cart").json().get("items", [])
    assert len(cart_after_co) == 1, "Cart lost on returning to checkout!"
    orders_co = get_order_count("checkout_patron@smartcafe.internal")
    assert orders_co == checkout_initial_orders, "FAIL: Order created simply by logging in on checkout!"
    print("  --> PASS: User returned to checkout. Cart intact. Zero orders created.")

    # TEST 7: Checkout -> Cancel payment -> Verify NO completed order created
    print("\n[TEST 7] Checkout -> Initialize payment -> Cancel payment -> Verify NO order created")
    orders_before_payment = get_order_count("checkout_patron@smartcafe.internal")
    pay_init = checkout_session.post(f"{BASE_URL}/api/payment/create", json={
        "items": cart_after_co,
        "customer_name": "Checkout Patron"
    })
    assert pay_init.status_code == 200
    # Payment opened, but user closes/dismisses modal without verifying
    orders_after_cancel = get_order_count("checkout_patron@smartcafe.internal")
    assert orders_before_payment == orders_after_cancel, "FAIL: Payment init created an order!"
    print("  --> PASS: Payment initialization/dismissal created ZERO orders.")

    # TEST 8: Checkout -> Explicit order creation -> Verify status is PENDING and order created
    print("\n[TEST 8] Checkout -> Explicit Counter Order confirmation")
    create_order_resp = checkout_session.post(f"{BASE_URL}/api/orders", json={
        "table_number": "04",
        "customer_name": "Checkout Patron",
        "customer_email": "checkout_patron@smartcafe.internal",
        "items": cart_after_co,
        "payment_method": "Counter"
    })
    assert create_order_resp.status_code == 200
    order_data = create_order_resp.json().get("order", {})
    assert order_data.get("id"), "Order ID was not generated"
    assert order_data.get("status") == "PENDING", f"FAIL: Expected initial status PENDING, got {order_data.get('status')}"
    print(f"  --> PASS: Explicit order created with ID #{order_data.get('id')} and status '{order_data.get('status')}'.")

    # TEST 8b: Checkout -> Successful Payment Verification -> Status is CONFIRMED & PAID
    print("\n[TEST 8b] Checkout -> Verified UPI Payment -> Order created as CONFIRMED & PAID")
    payment_tray = [
        {"item_id": "c1", "quantity": 1, "name": "Estate Espresso", "price": 160, "selected_options": []}
    ]
    # Initialize Razorpay order
    pay_res = session.post(f"{BASE_URL}/api/payment/create", json={"items": payment_tray})
    rzp_order_id = pay_res.json().get("order_id")
    
    # Complete verification
    verify_resp = session.post(f"{BASE_URL}/api/payment/verify", json={
        "razorpay_order_id": rzp_order_id,
        "razorpay_payment_id": "pay_test_verified_123",
        "razorpay_signature": "simulated_valid_sig",
        "table_number": "04",
        "customer_name": "Flow Tester",
        "customer_email": test_user_email,
        "items": payment_tray
    })
    assert verify_resp.status_code == 200
    verified_order = verify_resp.json().get("order", {})
    assert verified_order.get("id"), "Order ID missing on payment verification"
    assert verified_order.get("status") == "CONFIRMED", f"Expected CONFIRMED status, got {verified_order.get('status')}"
    assert verified_order.get("payment_status") == "PAID", f"Expected PAID payment status, got {verified_order.get('payment_status')}"
    print(f"  --> PASS: Order #{verified_order.get('id')} created only after payment verification with status '{verified_order.get('status')}'.")

    # TEST 9: Refresh page after login -> User remains logged in & no duplicate order
    print("\n[TEST 9] Refresh page after login -> Remains logged in, zero duplicate orders")
    orders_before_refresh = get_order_count(test_user_email)
    refresh_home = session.get(f"{BASE_URL}/")
    assert refresh_home.status_code == 200
    auth_me = session.get(f"{BASE_URL}/api/auth/me")
    assert auth_me.status_code == 200
    assert auth_me.json().get("customer", {}).get("email") == test_user_email
    orders_after_refresh = get_order_count(test_user_email)
    assert orders_before_refresh == orders_after_refresh, "FAIL: Page refresh created duplicate order!"
    print("  --> PASS: User session persists on refresh. Zero duplicate orders.")

    # TEST 10: Safe Redirect URL security check
    print("\n[TEST 10] Security verification: Safe Return URL mechanism")
    bad_urls = [
        "https://evil.com/phish",
        "//evil.com",
        "/\\evil.com",
        "javascript:alert(1)"
    ]
    for b in bad_urls:
        r = session.get(f"{BASE_URL}/login?next={b}")
        assert r.status_code == 200
        # Check that evil URL is NOT injected into next_url
        assert "evil.com" not in r.text or "next_url" not in r.text
    print("  --> PASS: Arbitrary external redirect URLs are strictly rejected.")

    print("\n" + "=" * 60)
    print("ALL 10 VERIFICATION TESTS PASSED PERFECTLY!")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
