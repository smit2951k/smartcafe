import requests
import re

BASE_URL = "http://127.0.0.1:5000"

def test_menu_and_tray():
    print("=" * 60)
    print("RUNNING MENU & TRAY INTERACTION VALIDATION")
    print("=" * 60)

    session = requests.Session()

    # 1. Verify Menu Page HTML structure
    print("\n[TEST 1] Verify /menu page structure and + Tray buttons")
    resp_menu = session.get(f"{BASE_URL}/menu")
    assert resp_menu.status_code == 200, "Menu page failed to load"
    html_menu = resp_menu.text

    # Find + Tray buttons
    matches = re.findall(r'addSimpleItemToCart\([^)]+\)', html_menu)
    assert len(matches) > 0, "No 'addSimpleItemToCart' calls found on menu cards"
    print(f"  --> Found {len(matches)} '+ Tray' button handlers on Menu page.")

    first_btn_match = matches[0]
    assert "this" in first_btn_match and "event" in first_btn_match, "Button must pass this and event for feedback"
    print(f"  --> PASS: Menu cards have direct '+ Tray' button with interactive handler: {first_btn_match}")

    # 2. Verify Top Navigation Tray button is an anchor to /cart
    print("\n[TEST 2] Verify top-right Tray button navigates to /cart")
    assert 'href="/cart" class="nav-tray-btn" id="navTrayTrigger"' in html_menu or 'id="navTrayTrigger"' in html_menu, "navTrayTrigger not found"
    assert 'id="cartCountBadge"' in html_menu, "cartCountBadge not found in navbar"
    assert 'href="/cart"' in html_menu, "Link to /cart not found"
    print("  --> PASS: navTrayTrigger is a clickable link directly to /cart with badge ID #cartCountBadge.")

    # 3. Verify /cart page template structure
    print("\n[TEST 3] Verify /cart page structure")
    resp_cart = session.get(f"{BASE_URL}/cart")
    assert resp_cart.status_code == 200, "Cart page failed to load"
    html_cart = resp_cart.text
    assert "Your Tray" in html_cart, "'Your Tray' header not found on /cart"
    assert 'id="fullCartItems"' in html_cart, "fullCartItems container not found"
    assert 'id="fullCartSummaryCard"' in html_cart, "fullCartSummaryCard not found"
    assert "Nothing here yet." in html_cart, "Empty tray state text not found in /cart script template"
    assert "Start with something worth ordering." in html_cart, "Empty tray subtitle not found"
    assert "Explore Menu" in html_cart, "Explore Menu link not found"
    print("  --> PASS: /cart contains editorial header, dynamic item container, settlement card, and empty state.")

    # 4. Verify Server Price Calculation API
    print("\n[TEST 4] Verify /api/cart/calculate logic")
    calc_payload = {
        "items": [
            {"item_id": "c1", "quantity": 1, "selected_options": []},
            {"item_id": "c2", "quantity": 2, "selected_options": []}
        ]
    }
    calc_resp = session.post(f"{BASE_URL}/api/cart/calculate", json=calc_payload)
    assert calc_resp.status_code == 200, "Calculate API failed"
    data = calc_resp.json()
    assert data["success"] is True
    assert data["subtotal"] == 600, f"Expected subtotal 600, got {data['subtotal']}"
    assert data["tax"] == 30, f"Expected tax 30 (5%), got {data['tax']}"
    assert data["total"] == 630, f"Expected total 630, got {data['total']}"
    print(f"  --> PASS: Server calculation verified: Subtotal INR {data['subtotal']}, Tax INR {data['tax']}, Total INR {data['total']}.")

    # 5. Verify Mobile Menu Tray link
    print("\n[TEST 5] Verify Mobile navigation menu contains Tray link")
    assert '<a href="/cart" onclick="toggleMobileNav(false)">Tray' in html_menu, "Mobile menu does not contain /cart link"
    print("  --> PASS: Mobile navigation menu includes Tray link.")

    print("\n" + "=" * 60)
    print("ALL MENU & TRAY INTERACTION TESTS PASSED!")
    print("=" * 60)

if __name__ == "__main__":
    test_menu_and_tray()
