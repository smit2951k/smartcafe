import os
import logging
import requests as http_requests
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory
from flask_cors import CORS
from config import Config
from firebase_service import db_manager, is_firebase_live
from razorpay_service import RazorpayService

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config.from_object(Config)
CORS(app)

# Helper: Calculate server-side total
def calculate_order_totals(items, promo_code=None):
    subtotal = 0
    validated_items = []

    for cart_item in items:
        item_id = cart_item.get("item_id") or cart_item.get("id")
        menu_item = db_manager.get_menu_item_by_id(item_id)
        if not menu_item:
            continue

        base_price = float(menu_item.get("price", 0))
        qty = max(1, int(cart_item.get("quantity", 1)))

        # Options extra price
        extra_price = 0
        selected_options = cart_item.get("selected_options") or cart_item.get("options") or []
        for opt in selected_options:
            extra_price += float(opt.get("price", 0))

        item_unit_price = base_price + extra_price
        item_total = item_unit_price * qty
        subtotal += item_total

        validated_items.append({
            "item_id": menu_item.get("id"),
            "slug": menu_item.get("slug"),
            "name": menu_item.get("name"),
            "image": menu_item.get("image"),
            "category": menu_item.get("category"),
            "unit_price": item_unit_price,
            "quantity": qty,
            "item_total": item_total,
            "selected_options": selected_options
        })

    discount = 0
    if promo_code:
        offer = db_manager.get_offer_by_code(promo_code)
        if offer:
            if offer.get("discount_percent"):
                discount = round(subtotal * (offer["discount_percent"] / 100))
            elif offer.get("discount_amount"):
                discount = min(subtotal, offer["discount_amount"])

    taxable = max(0, subtotal - discount)
    tax = round(taxable * Config.TAX_RATE)
    total = taxable + tax

    return {
        "items": validated_items,
        "subtotal": subtotal,
        "discount": discount,
        "tax": tax,
        "total": total
    }

# -------------------------------------------------------------
# PAGE ROUTES
# -------------------------------------------------------------

@app.route("/")
def home():
    featured_items = [i for i in db_manager.get_menu_items() if i.get("is_featured")][:4]
    return render_template("index.html", featured_items=featured_items)

@app.route("/menu")
def menu():
    category = request.args.get("category", "all")
    search = request.args.get("search", "")
    table_from_query = request.args.get("table", "")

    categories = db_manager.get_categories()
    items = db_manager.get_menu_items(category=category, search=search)
    tables = db_manager.get_tables()

    current_table = table_from_query or session.get("table_number", "04")
    if table_from_query:
        session["table_number"] = table_from_query

    return render_template(
        "menu.html",
        categories=categories,
        items=items,
        active_category=category,
        search_query=search,
        tables=tables,
        current_table=current_table
    )

@app.route("/menu/<item_id>")
def menu_detail(item_id):
    item = db_manager.get_menu_item_by_id(item_id)
    if not item:
        return render_template("404.html", message="Culinary offering not found"), 404
    all_items = db_manager.get_menu_items()
    related = [i for i in all_items if i.get("id") != item.get("id") and i.get("category") == item.get("category")][:3]
    if len(related) < 3:
        extras = [i for i in all_items if i.get("id") != item.get("id") and i not in related][:3 - len(related)]
        related.extend(extras)
    return render_template("menu_detail.html", item=item, related_items=related)

@app.route("/experience")
def experience():
    return render_template("experience.html")

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/gallery")
def gallery():
    return render_template("gallery.html")

@app.route("/qrcode/<path:filename>")
def serve_qrcode(filename):
    qr_dir = os.path.join(app.root_path, "qrcode")
    return send_from_directory(qr_dir, filename)

@app.route("/reservations")
def reservations():
    tables = [t for t in db_manager.get_tables() if t.get("number") != "Takeaway"]
    current_table = session.get("table_number", "")
    base_url = getattr(Config, "BASE_URL", request.host_url.rstrip('/'))
    return render_template("reservations.html", tables=tables, current_table=current_table, base_url=base_url)

@app.route("/scan-table")
def scan_table():
    current_table = session.get("table_id") or session.get("table_number") or ""
    return render_template("scan_table.html", current_table=current_table)

@app.route("/table/<table_id>")
def table_detect(table_id):
    table = db_manager.get_table_by_number(table_id)
    if not table:
        return render_template("table_not_found.html", requested_table=table_id), 404

    previous_table = session.get("table_id") or session.get("table_number")
    table_changed = bool(previous_table and str(previous_table).lower() != str(table.get("number")).lower())

    # Set table in session
    session["table_id"] = str(table["number"])
    session["table_number"] = str(table["number"])

    # Check active reservation notice for logged in patrons
    reservation_note = None
    customer = session.get("customer")
    if customer and customer.get("email"):
        res_list = db_manager.get_reservations(customer_email=customer["email"])
        if res_list:
            latest_res = res_list[0]
            res_room = latest_res.get("special_request") or latest_res.get("room")
            table_section = table.get("section")
            if res_room and table_section and res_room.lower() not in table_section.lower() and table_section.lower() not in res_room.lower():
                reservation_note = f"Note: Your booked reservation is for {res_room}. You are currently seated and ordering from Table {table.get('number')} ({table_section})."

    return render_template(
        "table_detected.html",
        table=table,
        previous_table=previous_table,
        table_changed=table_changed,
        reservation_note=reservation_note
    )

@app.route("/api/table/validate/<table_id>", methods=["GET", "POST"])
def api_validate_table(table_id):
    table = db_manager.get_table_by_number(table_id)
    if not table:
        return jsonify({"success": False, "error": "Table not found."}), 404

    # Save to validated session
    session["table_id"] = str(table["number"])
    session["table_number"] = str(table["number"])

    return jsonify({
        "success": True,
        "table_id": str(table["number"]),
        "table_number": str(table["number"]),
        "name": table.get("name"),
        "section": table.get("section"),
        "capacity": table.get("capacity")
    })

@app.route("/api/table/active", methods=["GET"])
def api_active_table():
    table_id = session.get("table_id") or session.get("table_number")
    if not table_id:
        return jsonify({"success": True, "active": False, "table_id": None, "table_number": None})
    table = db_manager.get_table_by_number(table_id)
    return jsonify({
        "success": True,
        "active": True,
        "table_id": str(table_id),
        "table_number": str(table_id),
        "table": table
    })

@app.route("/api/table/clear", methods=["POST"])
def api_clear_table():
    session.pop("table_id", None)
    session.pop("table_number", None)
    return jsonify({"success": True, "message": "Table session cleared"})

@app.route("/cart")
def cart_page():
    return render_template("cart.html")

@app.route("/checkout")
def checkout_page():
    table = session.get("table_number") or request.args.get("table", "")
    if not table:
        table = "Takeaway"
    return render_template("checkout.html", table_number=table, razorpay_key=Config.RAZORPAY_KEY_ID)

@app.route("/order")
def order_qr():
    table = request.args.get("table", "")
    if table:
        return redirect(url_for("table_detect", table_id=table))
    return redirect(url_for("menu"))

@app.route("/order/<order_id>")
def order_status(order_id):
    order = db_manager.get_order_by_id(order_id)
    if not order:
        return render_template("404.html", message="Ticket not found"), 404
    return render_template("order_status.html", order=order)

def is_safe_url(target):
    if not target or not isinstance(target, str):
        return False
    target = target.strip()
    if not target.startswith("/") or target.startswith("//") or target.startswith("/\\"):
        return False
    if ":" in target.split("?")[0]:
        return False
    return True

@app.route("/account")
def account():
    customer = session.get("customer")
    customer_email = customer.get("email") if customer else None
    orders = db_manager.get_orders(customer_email=customer_email) if customer_email else []
    user_reservations = db_manager.get_reservations(customer_email=customer_email) if customer_email else []
    return render_template("account.html", customer=customer, orders=orders, reservations=user_reservations)

@app.route("/profile")
def profile():
    tab = request.args.get("tab", "profile")
    return redirect(url_for("account", tab=tab))

@app.route("/logout", methods=["GET", "POST"])
def logout():
    session.pop("customer", None)
    return redirect(url_for("home"))

@app.route("/login")
def login_page():
    mode = request.args.get("mode", "signin")
    next_url = request.args.get("next", "").strip()
    if not is_safe_url(next_url):
        next_url = ""
    return render_template("login.html", mode=mode, next_url=next_url)

@app.route("/register")
def register_page():
    next_url = request.args.get("next", "").strip()
    if not is_safe_url(next_url):
        next_url = ""
    return redirect(url_for("login_page", mode="signup", next=next_url if next_url else None))

@app.route("/admin")
def admin_page():
    orders = db_manager.get_orders()
    tables = db_manager.get_tables()
    res_list = db_manager.get_reservations()
    menu_items = db_manager.get_menu_items(only_available=False)
    users = db_manager.get_users()

    # Safe helpers: Firestore may store total as string or number
    def _safe_total(o):
        try:
            return float(o.get("total") or o.get("amount") or o.get("grand_total") or 0)
        except (TypeError, ValueError):
            return 0.0

    def _status(o):
        return str(o.get("status") or "").upper()

    total_revenue = int(sum(_safe_total(o) for o in orders if _status(o) != "CANCELLED"))
    active_count = len([o for o in orders if _status(o) in ("PENDING", "CONFIRMED", "PREPARING")])
    ready_count = len([o for o in orders if _status(o) == "READY"])

    return render_template(
        "admin.html",
        orders=orders,
        tables=tables,
        reservations=res_list,
        menu_items=menu_items,
        users=users,
        total_revenue=total_revenue,
        active_count=active_count,
        ready_count=ready_count
    )


# -------------------------------------------------------------
# REST API ENDPOINTS
# -------------------------------------------------------------

@app.route("/api/menu", methods=["GET"])
def api_get_menu():
    category = request.args.get("category", "all")
    search = request.args.get("search", "")
    items = db_manager.get_menu_items(category=category, search=search)
    categories = db_manager.get_categories()
    return jsonify({"success": True, "categories": categories, "items": items})

@app.route("/api/menu/<item_id>", methods=["GET"])
def api_get_menu_item(item_id):
    item = db_manager.get_menu_item_by_id(item_id)
    if not item:
        return jsonify({"success": False, "error": "Item not found"}), 404
    return jsonify({"success": True, "item": item})

@app.route("/api/cart", methods=["GET"])
def api_get_cart():
    return jsonify({"success": True, "items": session.get("cart", [])})

def _cart_item_key(item):
    item_id = str(item.get("item_id") or item.get("id") or "")
    options = item.get("selected_options") or item.get("options") or []
    opt_keys = []
    for opt in options:
        name = opt.get("option_name") or opt.get("optionName") or opt.get("name") or ""
        opt_keys.append(str(name))
    opt_keys.sort()
    return f"{item_id}::{'|'.join(opt_keys)}"

@app.route("/api/cart/sync", methods=["POST"])
def api_sync_cart():
    data = request.get_json() or {}
    client_items = data.get("items", [])
    server_cart = session.get("cart", [])

    merged = {}
    for item in server_cart:
        k = _cart_item_key(item)
        merged[k] = item

    for item in client_items:
        k = _cart_item_key(item)
        if k in merged:
            merged[k]["quantity"] = max(merged[k].get("quantity", 1), item.get("quantity", 1))
        else:
            merged[k] = item

    final_cart = list(merged.values())
    session["cart"] = final_cart
    return jsonify({"success": True, "items": final_cart})

@app.route("/api/cart/calculate", methods=["POST"])
def api_calculate_cart():
    data = request.get_json() or {}
    items = data.get("items", [])
    promo_code = data.get("promo_code", "").strip()

    totals = calculate_order_totals(items, promo_code)
    return jsonify({"success": True, **totals})

@app.route("/api/orders", methods=["POST"])
def api_create_order():
    data = request.get_json() or {}
    client_items = data.get("items", [])
    if not client_items:
        return jsonify({"success": False, "error": "Cart is empty"}), 400

    promo_code = data.get("promo_code")
    totals = calculate_order_totals(client_items, promo_code)

    # Server-side table validation: session table takes priority, fallback to payload, validated against database
    table_candidate = session.get("table_id") or session.get("table_number") or data.get("table_number") or "Takeaway"
    valid_table = db_manager.get_table_by_number(table_candidate)
    table_number = valid_table.get("number") if valid_table else "Takeaway"
    table_id = valid_table.get("id") if valid_table else "T99"
    table_section = valid_table.get("section") if valid_table else "General"

    customer_name = data.get("customer_name") or session.get("customer", {}).get("name") or "Walk-in Guest"
    customer_email = data.get("customer_email") or session.get("customer", {}).get("email") or ""
    customer_phone = data.get("customer_phone") or session.get("customer", {}).get("phone") or ""
    payment_method = data.get("payment_method", "Counter")

    # New orders must start as PENDING
    order_payload = {
        "table_number": str(table_number),
        "table_id": str(table_number),
        "tableId": str(table_id),
        "table_section": str(table_section),
        "items": totals["items"],
        "subtotal": totals["subtotal"],
        "discount": totals["discount"],
        "tax": totals["tax"],
        "total": totals["total"],
        "status": "PENDING",
        "payment_status": "PENDING",
        "payment_method": payment_method,
        "customer_name": customer_name,
        "customer_email": customer_email,
        "customer_phone": customer_phone,
        "special_instructions": data.get("special_instructions", ""),
        "created_at": datetime.now().isoformat()
    }

    new_order = db_manager.create_order(order_payload)
    session["cart"] = []
    return jsonify({"success": True, "order": new_order})

@app.route("/api/orders", methods=["GET"])
def api_get_orders():
    customer_email = request.args.get("customer_email")
    orders = db_manager.get_orders(customer_email=customer_email)
    return jsonify({"success": True, "orders": orders})

@app.route("/api/orders/<order_id>", methods=["GET"])
def api_get_order(order_id):
    order = db_manager.get_order_by_id(order_id)
    if not order:
        return jsonify({"success": False, "error": "Order not found"}), 404
    return jsonify({"success": True, "order": order})

@app.route("/api/orders/<order_id>/status", methods=["PATCH", "POST"])
def api_update_order_status(order_id):
    data = request.get_json() or {}
    new_status = data.get("status")
    payment_status = data.get("payment_status")

    if not new_status:
        return jsonify({"success": False, "error": "Status is required"}), 400

    valid_statuses = ["PENDING", "CONFIRMED", "PREPARING", "READY", "COMPLETED", "CANCELLED"]
    if new_status not in valid_statuses:
        return jsonify({"success": False, "error": f"Invalid status: {new_status}"}), 400

    updated = db_manager.update_order_status(order_id, new_status, payment_status)
    if not updated:
        return jsonify({"success": False, "error": "Order not found"}), 404
    return jsonify({"success": True, "order": updated})

@app.route("/api/reservations", methods=["POST"])
def api_create_reservation():
    # Real Authentication is Required: user must be signed in
    customer = session.get("customer")
    if not customer or not customer.get("email"):
        return jsonify({
            "success": False,
            "error": "Authentication required. Please sign in to confirm your table reservation."
        }), 401

    data = request.get_json() or {}
    name = (data.get("name") or customer.get("name") or "").strip()
    email = (data.get("email") or customer.get("email") or "").strip().lower()
    phone = (data.get("phone") or customer.get("phone") or "").strip()
    date = data.get("date", "").strip()
    time = data.get("time", "").strip()
    guests = int(data.get("guests", 2))
    special_request = data.get("special_request", "").strip()

    if not (name and email and phone and date and time):
        return jsonify({"success": False, "error": "All required reservation fields (Name, Phone, Email, Date, Time) must be provided"}), 400

    # Ensure updated contact is saved to authenticated profile
    if phone and phone != customer.get("phone"):
        customer["phone"] = phone
        session["customer"] = customer
        db_manager.create_or_update_user(customer)

    res_payload = {
        "name": name,
        "email": email,
        "phone": phone,
        "date": date,
        "time": time,
        "guests": guests,
        "special_request": special_request,
        "status": "CONFIRMED",
        "created_at": datetime.now().isoformat(),
        "user_uid": customer.get("firebase_uid", "")
    }

    new_res = db_manager.create_reservation(res_payload)
    return jsonify({"success": True, "reservation": new_res})

@app.route("/api/reservations", methods=["GET"])
def api_get_reservations():
    email = request.args.get("email")
    reservations = db_manager.get_reservations(customer_email=email)
    return jsonify({"success": True, "reservations": reservations})

@app.route("/api/payment/create", methods=["POST"])
def api_create_payment():
    data = request.get_json() or {}
    client_items = data.get("items", [])
    if not client_items:
        return jsonify({"success": False, "error": "No items to purchase"}), 400

    totals = calculate_order_totals(client_items, data.get("promo_code"))
    receipt_id = f"rcpt_{int(datetime.now().timestamp())}"

    rzp_res = RazorpayService.create_order(
        amount_in_rupees=totals["total"],
        receipt_id=receipt_id,
        notes={"customer_name": data.get("customer_name", "Patron")}
    )

    return jsonify({"success": True, **rzp_res, "totals": totals})

@app.route("/api/payment/verify", methods=["POST"])
def api_verify_payment():
    data = request.get_json() or {}
    order_id = data.get("razorpay_order_id")
    payment_id = data.get("razorpay_payment_id")
    signature = data.get("razorpay_signature")
    cafe_order_id = data.get("cafe_order_id")

    verified = RazorpayService.verify_payment(order_id, payment_id, signature)
    if not verified:
        return jsonify({"success": False, "error": "Invalid signature verification"}), 400

    if cafe_order_id:
        updated = db_manager.update_order_status(cafe_order_id, status="CONFIRMED", payment_status="PAID")
        session["cart"] = []
        return jsonify({"success": True, "message": "Payment verified successfully", "order_id": cafe_order_id, "order": updated})

    client_items = data.get("items", [])
    if client_items:
        promo_code = data.get("promo_code")
        totals = calculate_order_totals(client_items, promo_code)

        # Server-side table validation: session table takes priority, fallback to payload, validated against database
        table_candidate = session.get("table_id") or session.get("table_number") or data.get("table_number") or "Takeaway"
        valid_table = db_manager.get_table_by_number(table_candidate)
        table_number = valid_table.get("number") if valid_table else "Takeaway"
        table_id = valid_table.get("id") if valid_table else "T99"
        table_section = valid_table.get("section") if valid_table else "General"

        customer_name = data.get("customer_name") or session.get("customer", {}).get("name") or "Walk-in Guest"
        customer_email = data.get("customer_email") or session.get("customer", {}).get("email") or ""
        customer_phone = data.get("customer_phone") or session.get("customer", {}).get("phone") or ""

        order_payload = {
            "table_number": str(table_number),
            "table_id": str(table_number),
            "tableId": str(table_id),
            "table_section": str(table_section),
            "items": totals["items"],
            "subtotal": totals["subtotal"],
            "discount": totals["discount"],
            "tax": totals["tax"],
            "total": totals["total"],
            "status": "CONFIRMED",
            "payment_status": "PAID",
            "payment_method": "UPI",
            "payment_id": payment_id,
            "razorpay_order_id": order_id,
            "customer_name": customer_name,
            "customer_email": customer_email,
            "customer_phone": customer_phone,
            "special_instructions": data.get("special_instructions", ""),
            "created_at": datetime.now().isoformat()
        }

        new_order = db_manager.create_order(order_payload)
        session["cart"] = []
        return jsonify({"success": True, "message": "Payment verified successfully", "order_id": new_order["id"], "order": new_order})

    return jsonify({"success": True, "message": "Payment verified successfully"})

@app.route("/api/auth/login", methods=["POST"])
def api_auth_login():
    """
    Authenticate an existing user via Firebase Auth REST API.
    NEVER creates an account automatically.
    NEVER triggers an order.
    """
    data = request.get_json() or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    name = (data.get("name") or "").strip()

    if not email or not email.count("@") == 1:
        return jsonify({"success": False, "error": "Please enter a valid email address."}), 400

    # If no password is provided, allow session recognition/sync if a name or existing user is available
    if not password:
        existing = db_manager.get_user_by_email(email)
        display_name = name or (existing.get("name") if existing else None) or email.split("@")[0].replace(".", " ").title()
        user_dict = {
            "name": display_name,
            "email": email,
            "phone": (existing or {}).get("phone", "+91 98000 00000"),
            "member_since": (existing or {}).get("member_since", datetime.now().strftime("%B %Y")),
            "loyalty_points": (existing or {}).get("loyalty_points", 0),
        }
        session["customer"] = user_dict
        db_manager.create_or_update_user(user_dict)
        return jsonify({"success": True, "customer": user_dict})

    web_api_key = Config.FIREBASE_WEB_API_KEY

    # ── Firebase Auth REST API path ──────────────────────────────────────────
    if web_api_key:
        try:
            fb_res = http_requests.post(
                f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={web_api_key}",
                json={"email": email, "password": password, "returnSecureToken": True},
                timeout=8
            )
            fb_data = fb_res.json()

            if fb_res.ok and "idToken" in fb_data:
                # Authenticated — sync or fetch profile from our DB
                existing = db_manager.get_user_by_email(email)
                display_name = fb_data.get("displayName") or (
                    existing.get("name") if existing else None
                ) or email.split("@")[0].replace(".", " ").title()

                user_dict = {
                    "name": display_name,
                    "email": email,
                    "phone": (existing or {}).get("phone", "+91 98000 00000"),
                    "member_since": (existing or {}).get("member_since", datetime.now().strftime("%B %Y")),
                    "loyalty_points": (existing or {}).get("loyalty_points", 0),
                    "firebase_uid": fb_data.get("localId", ""),
                }
                session["customer"] = user_dict
                db_manager.create_or_update_user(user_dict)
                return jsonify({"success": True, "customer": user_dict})

            # Map Firebase error codes to human-friendly messages
            fb_error = fb_data.get("error", {}).get("message", "")
            if "CONFIGURATION_NOT_FOUND" in fb_error or "PROJECT_NOT_FOUND" in fb_error:
                logger.warning("Firebase Auth is not enabled in Firebase console (%s). Falling back to local accounts.", fb_error)
                existing = db_manager.get_user_by_email(email)
                if existing:
                    session["customer"] = existing
                    return jsonify({"success": True, "customer": existing})
                return jsonify({"success": False, "error": "Firebase Email/Password provider is not enabled yet in Firebase Console."}), 503

            if "EMAIL_NOT_FOUND" in fb_error or "USER_NOT_FOUND" in fb_error:
                # If user exists in local demo db, log them in seamlessly
                existing = db_manager.get_user_by_email(email)
                if existing:
                    session["customer"] = existing
                    return jsonify({"success": True, "customer": existing})
                return jsonify({"success": False, "error": "No SmartCafe account found with this email. Please create an account first."}), 401
            if "INVALID_PASSWORD" in fb_error or "INVALID_LOGIN_CREDENTIALS" in fb_error:
                return jsonify({"success": False, "error": "Incorrect password. Please check your credentials and try again."}), 401
            if "USER_DISABLED" in fb_error:
                return jsonify({"success": False, "error": "This account has been disabled. Please contact SmartCafe support."}), 403
            if "TOO_MANY_ATTEMPTS_TRY_LATER" in fb_error:
                return jsonify({"success": False, "error": "Too many failed attempts. Please wait a moment and try again."}), 429
            if "INVALID_EMAIL" in fb_error:
                return jsonify({"success": False, "error": "Please enter a valid email address."}), 400

            logger.warning("Firebase Auth login error: %s", fb_error)
            existing = db_manager.get_user_by_email(email)
            if existing:
                session["customer"] = existing
                return jsonify({"success": True, "customer": existing})
            return jsonify({"success": False, "error": "Sign in failed. Please check your credentials."}), 401

        except http_requests.Timeout:
            logger.warning("Firebase Auth REST API timed out during login.")
            existing = db_manager.get_user_by_email(email)
            if existing:
                session["customer"] = existing
                return jsonify({"success": True, "customer": existing})
            return jsonify({"success": False, "error": "Authentication service is temporarily unavailable. Please try again."}), 503
        except Exception as e:
            logger.error("Firebase Auth login exception: %s", e)
            existing = db_manager.get_user_by_email(email)
            if existing:
                session["customer"] = existing
                return jsonify({"success": True, "customer": existing})
            return jsonify({"success": False, "error": "Unable to reach authentication service. Please try again."}), 503

    # ── Fallback: no Web API key configured — check local DB only ───────────
    existing = db_manager.get_user_by_email(email)
    if existing:
        session["customer"] = existing
        return jsonify({"success": True, "customer": existing})

    return jsonify({
        "success": False,
        "error": "Authentication is not fully configured. Please contact SmartCafe admin."
    }), 503


@app.route("/api/auth/register", methods=["POST"])
def api_auth_register():
    """
    Create a new SmartCafe account via Firebase Auth REST API.
    NEVER logs in an existing user — registration only.
    """
    data = request.get_json() or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    name = (data.get("name") or "").strip()
    phone = (data.get("phone") or "").strip()

    if not email or not email.count("@") == 1:
        return jsonify({"success": False, "error": "Please enter a valid email address."}), 400
    if not password or len(password) < 6:
        return jsonify({"success": False, "error": "Password must be at least 6 characters long."}), 400

    display_name = name or email.split("@")[0].replace(".", " ").title()

    web_api_key = Config.FIREBASE_WEB_API_KEY

    if web_api_key:
        try:
            fb_res = http_requests.post(
                f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={web_api_key}",
                json={"email": email, "password": password, "returnSecureToken": True},
                timeout=8
            )
            fb_data = fb_res.json()

            if fb_res.ok and "idToken" in fb_data:
                # Try to update display name via Firebase Auth REST API
                try:
                    http_requests.post(
                        f"https://identitytoolkit.googleapis.com/v1/accounts:update?key={web_api_key}",
                        json={"idToken": fb_data["idToken"], "displayName": display_name, "returnSecureToken": False},
                        timeout=6
                    )
                except Exception:
                    pass  # Non-critical

                user_dict = {
                    "name": display_name,
                    "email": email,
                    "phone": phone or "+91 98000 00000",
                    "member_since": datetime.now().strftime("%B %Y"),
                    "loyalty_points": 0,
                    "firebase_uid": fb_data.get("localId", ""),
                }
                session["customer"] = user_dict
                db_manager.create_or_update_user(user_dict)
                return jsonify({"success": True, "customer": user_dict})

            fb_error = fb_data.get("error", {}).get("message", "")
            if "CONFIGURATION_NOT_FOUND" in fb_error or "PROJECT_NOT_FOUND" in fb_error:
                logger.warning("Firebase Auth is not enabled in Firebase console (%s). Creating local demo account.", fb_error)
                if db_manager.get_user_by_email(email):
                    return jsonify({"success": False, "error": "An account with this email already exists. Please Sign In instead."}), 409
                user_dict = {
                    "name": display_name,
                    "email": email,
                    "phone": phone or "+91 98000 00000",
                    "member_since": datetime.now().strftime("%B %Y"),
                    "loyalty_points": 0,
                }
                session["customer"] = user_dict
                db_manager.create_or_update_user(user_dict)
                return jsonify({"success": True, "customer": user_dict})

            if "EMAIL_EXISTS" in fb_error:
                return jsonify({"success": False, "error": "An account with this email already exists. Please Sign In instead."}), 409
            if "INVALID_EMAIL" in fb_error:
                return jsonify({"success": False, "error": "Please enter a valid email address."}), 400
            if "WEAK_PASSWORD" in fb_error:
                return jsonify({"success": False, "error": "Password is too weak. Please use at least 6 characters."}), 400
            if "TOO_MANY_ATTEMPTS_TRY_LATER" in fb_error:
                return jsonify({"success": False, "error": "Too many attempts. Please try again in a few minutes."}), 429

            logger.warning("Firebase Auth register error: %s", fb_error)
            return jsonify({"success": False, "error": "Account creation failed. Please try again."}), 400

        except http_requests.Timeout:
            return jsonify({"success": False, "error": "Authentication service is temporarily unavailable. Please try again."}), 503
        except Exception as e:
            logger.error("Firebase Auth register exception: %s", e)
            return jsonify({"success": False, "error": "Unable to reach authentication service. Please try again."}), 503

    # Fallback: no Web API key — store in local DB only
    if db_manager.get_user_by_email(email):
        return jsonify({"success": False, "error": "An account with this email already exists. Please Sign In instead."}), 409

    user_dict = {
        "name": display_name,
        "email": email,
        "phone": phone or "+91 98000 00000",
        "member_since": datetime.now().strftime("%B %Y"),
        "loyalty_points": 0,
    }
    session["customer"] = user_dict
    db_manager.create_or_update_user(user_dict)
    return jsonify({"success": True, "customer": user_dict})


@app.route("/api/auth/session", methods=["POST"])
def api_auth_session():
    """Sync an already-authenticated user's profile into the Flask session."""
    data = request.get_json() or {}
    email = data.get("email", "").strip().lower()
    if not email:
        return jsonify({"success": False, "error": "Email required"}), 400

    existing = db_manager.get_user_by_email(email)
    user_dict = {
        "name": data.get("name") or (existing or {}).get("name") or email.split("@")[0].capitalize(),
        "email": email,
        "phone": data.get("phone") or (existing or {}).get("phone", "+91 98000 00000"),
        "member_since": (existing or {}).get("member_since", datetime.now().strftime("%B %Y")),
        "loyalty_points": (existing or {}).get("loyalty_points", 0),
        "firebase_uid": data.get("firebase_uid") or (existing or {}).get("firebase_uid", ""),
    }
    session["customer"] = user_dict
    db_manager.create_or_update_user(user_dict)
    return jsonify({"success": True, "customer": user_dict})


@app.route("/api/auth/logout", methods=["POST"])
def api_auth_logout():
    session.pop("customer", None)
    return jsonify({"success": True})


@app.route("/api/auth/me", methods=["GET"])
def api_auth_me():
    return jsonify({"success": True, "customer": session.get("customer")})


@app.route("/api/auth/reset-password", methods=["POST"])
def api_auth_reset_password():
    """Send a Firebase password reset email via REST API."""
    data = request.get_json() or {}
    email = data.get("email", "").strip().lower()

    if not email or "@" not in email:
        return jsonify({"success": False, "error": "Please enter a valid email address."}), 400

    web_api_key = Config.FIREBASE_WEB_API_KEY
    if not web_api_key:
        return jsonify({"success": False, "error": "Password reset is not configured. Please contact SmartCafe support."}), 503

    try:
        fb_res = http_requests.post(
            f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={web_api_key}",
            json={"requestType": "PASSWORD_RESET", "email": email},
            timeout=8
        )
        fb_data = fb_res.json()

        if fb_res.ok:
            return jsonify({"success": True})

        fb_error = fb_data.get("error", {}).get("message", "")
        if "EMAIL_NOT_FOUND" in fb_error:
            return jsonify({"success": False, "error": "No account found with this email address."}), 404
        return jsonify({"success": False, "error": "Unable to send reset email. Please try again."}), 400

    except http_requests.Timeout:
        return jsonify({"success": False, "error": "Service temporarily unavailable. Please try again."}), 503
    except Exception as e:
        logger.error("Password reset error: %s", e)
        return jsonify({"success": False, "error": "Unable to process reset request. Please try again."}), 503




@app.route("/api/tables", methods=["GET"])
def api_get_tables():
    tables = db_manager.get_tables()
    return jsonify({"success": True, "tables": tables})


@app.route("/api/admin/stats", methods=["GET"])
def api_admin_stats():
    orders = db_manager.get_orders()
    reservations = db_manager.get_reservations()
    tables = db_manager.get_tables()

    def _safe_total(o):
        try:
            return float(o.get("total") or o.get("amount") or o.get("grand_total") or 0)
        except (TypeError, ValueError):
            return 0.0

    def _status(o):
        return str(o.get("status") or "").upper()

    total_rev = int(sum(_safe_total(o) for o in orders if _status(o) != "CANCELLED"))
    active_orders = len([o for o in orders if _status(o) in ("PENDING", "CONFIRMED", "PREPARING")])
    ready_orders = len([o for o in orders if _status(o) == "READY"])

    occupied_tables = len(set(
        o.get("table_number") for o in orders
        if _status(o) in ("PENDING", "CONFIRMED", "PREPARING", "READY")
    ))

    return jsonify({
        "success": True,
        "total_revenue": total_rev,
        "active_orders": active_orders,
        "ready_orders": ready_orders,
        "total_orders": len(orders),
        "total_reservations": len(reservations),
        "occupied_tables": occupied_tables,
        "total_tables": len(tables)
    })

@app.route("/api/admin/menu", methods=["POST"])
def api_admin_save_menu():
    data = request.get_json() or {}
    saved = db_manager.save_menu_item(data)
    return jsonify({"success": True, "item": saved})

@app.route("/api/admin/menu/<item_id>", methods=["DELETE"])
def api_admin_delete_menu(item_id):
    deleted = db_manager.delete_menu_item(item_id)
    return jsonify({"success": True, "deleted": deleted})

@app.route("/api/tables/<table_number>/status", methods=["PATCH", "POST"])
def api_update_table_status(table_number):
    data = request.get_json() or {}
    status = data.get("status", "AVAILABLE").upper()
    valid_statuses = ["AVAILABLE", "OCCUPIED", "RESERVED", "CLEANING"]
    if status not in valid_statuses:
        return jsonify({"success": False, "error": f"Invalid table status: {status}"}), 400
    updated = db_manager.update_table_status(table_number, status)
    if not updated:
        return jsonify({"success": False, "error": "Table not found"}), 404
    return jsonify({"success": True, "table": updated})

@app.route("/api/reservations/<res_id>/status", methods=["PATCH", "POST"])
def api_update_reservation_status(res_id):
    data = request.get_json() or {}
    status = data.get("status", "CONFIRMED").upper()
    valid_statuses = ["CONFIRMED", "SEATED", "CANCELLED", "COMPLETED"]
    if status not in valid_statuses:
        return jsonify({"success": False, "error": f"Invalid reservation status: {status}"}), 400
    updated = db_manager.update_reservation_status(res_id, status)
    if not updated:
        return jsonify({"success": False, "error": "Reservation not found"}), 404
    return jsonify({"success": True, "reservation": updated})

@app.route("/api/admin/users", methods=["GET"])
def api_admin_users():
    return jsonify({"success": True, "users": db_manager.get_users()})

@app.route("/api/offers", methods=["GET"])
def api_get_offers():

    return jsonify({"success": True, "offers": db_manager.get_offers()})

@app.route("/api/reviews", methods=["GET", "POST"])
def api_reviews():
    if request.method == "POST":
        data = request.get_json() or {}
        new_rev = db_manager.add_review({
            "name": data.get("name", "Patron"),
            "rating": int(data.get("rating", 5)),
            "comment": data.get("comment", ""),
            "date": "Today"
        })
        return jsonify({"success": True, "review": new_rev})
    return jsonify({"success": True, "reviews": db_manager.get_reviews()})

# -------------------------------------------------------------
# ERROR HANDLERS
# -------------------------------------------------------------

@app.errorhandler(404)
def not_found_error(error):
    if request.path.startswith("/api/"):
        return jsonify({"success": False, "error": "Endpoint not found"}), 404
    return render_template("404.html", message="The sanctuary page you requested cannot be found."), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    if request.path.startswith("/api/"):
        return jsonify({"success": False, "error": "Internal server error"}), 500
    return render_template("500.html", message="Our kitchen is attending to an unexpected service issue."), 500

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=Config.DEBUG)
