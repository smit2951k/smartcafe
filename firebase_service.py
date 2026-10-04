import os
import json
import logging
from datetime import datetime
from config import Config

logger = logging.getLogger(__name__)

# Attempt to initialize Firebase Admin SDK
firebase_app = None
firestore_client = None
firebase_auth = None
firebase_bucket = None
is_firebase_live = False

try:
    import firebase_admin
    from firebase_admin import credentials, firestore, auth, storage

    if os.path.exists(Config.FIREBASE_CREDENTIALS_PATH):
        cred = credentials.Certificate(Config.FIREBASE_CREDENTIALS_PATH)
        firebase_app = firebase_admin.initialize_app(cred, {
            'storageBucket': Config.FIREBASE_STORAGE_BUCKET
        })
        firestore_client = firestore.client()
        firebase_auth = auth
        try:
            firebase_bucket = storage.bucket()
        except Exception:
            firebase_bucket = None

        # Verify whether Cloud Firestore API is enabled on the project
        try:
            list(firestore_client.collection("_health").limit(1).stream())
            is_firebase_live = True
            logger.info("[Firestore] Successfully connected to live Cloud Firestore database for project: %s", Config.FIREBASE_PROJECT_ID)
        except Exception as conn_err:
            is_firebase_live = False
            logger.warning(
                "[Firestore Status] Firebase Admin credentials are valid for project '%s', but the Cloud Firestore database is not yet created/enabled in Google Cloud / Firebase Console. "
                "Error: %s. "
                "To enable Cloud Firestore, visit: https://console.firebase.google.com/project/%s/firestore and click 'Create database'.",
                Config.FIREBASE_PROJECT_ID, conn_err, Config.FIREBASE_PROJECT_ID
            )
    elif Config.FIREBASE_CLIENT_EMAIL and Config.FIREBASE_PRIVATE_KEY:
        cred = credentials.Certificate({
            "type": "service_account",
            "project_id": Config.FIREBASE_PROJECT_ID,
            "private_key": Config.FIREBASE_PRIVATE_KEY,
            "client_email": Config.FIREBASE_CLIENT_EMAIL,
            "token_uri": "https://oauth2.googleapis.com/token",
        })
        firebase_app = firebase_admin.initialize_app(cred, {
            'storageBucket': Config.FIREBASE_STORAGE_BUCKET
        })
        firestore_client = firestore.client()
        firebase_auth = auth
        is_firebase_live = True
        logger.info("Connected to Firebase Admin SDK via environment credentials.")
    else:
        logger.warning("No Firebase Admin credentials found. Initializing resilient local Firestore store.")
except Exception as e:
    logger.warning(f"Firebase Admin initialization deferred: {e}. Using resilient local Firestore layer.")

# Default seed data matching SmartCafe exact menu & tables
SEED_DATA = {
    "menu_categories": [
        {"id": "all", "name": "All Offerings", "order": 0},
        {"id": "coffee", "name": "Coffee & Espresso", "order": 1},
        {"id": "breakfast", "name": "Morning Plates", "order": 2},
        {"id": "brunch", "name": "Brunch & Tartines", "order": 3},
        {"id": "mains", "name": "Bowls & Mains", "order": 4},
        {"id": "desserts", "name": "Pastry & Sweets", "order": 5},
        {"id": "drinks", "name": "Botanicals & Tea", "order": 6},
    ],
    "menu_items": [
        {
            "id": "c1",
            "slug": "single-origin-espresso",
            "name": "Estate Espresso",
            "tagline": "Double extraction / Chikmagalur Reserve",
            "category": "coffee",
            "price": 160,
            "description": "A vibrant double pull highlighting notes of dark cacao, candied orange peel, and raw panela sugar. Extracted on custom Synesso MVP.",
            "image": "https://images.unsplash.com/photo-1510591509098-f4fdc6d0ff04?auto=format&fit=crop&w=1000&q=80",
            "is_vegetarian": True,
            "is_vegan": True,
            "is_gluten_free": True,
            "is_featured": True,
            "available": True,
            "ingredients": ["100% Arabica washed beans", "Filtered mineral water (90 ppm)"],
            "notes": "Brew temperature: 93.5°C | Extraction: 27 seconds",
            "options": [
                {"name": "Profile", "choices": [{"label": "Standard Double", "price": 0}, {"label": "Ristretto (Dense & syrupy)", "price": 0}, {"label": "Lungo (Bright & lengthened)", "price": 0}]}
            ]
        },
        {
            "id": "c2",
            "slug": "velvet-flat-white",
            "name": "Velvet Flat White",
            "tagline": "Micro-textured steam / Honey roast",
            "category": "coffee",
            "price": 220,
            "description": "Silky micro-foam delicately folded into a concentrated double shot of our medium-roast blend. Balanced, sweet, and comforting.",
            "image": "https://images.unsplash.com/photo-1577968897966-3d4325b36b61?auto=format&fit=crop&w=1000&q=80",
            "is_vegetarian": True,
            "is_vegan": False,
            "is_gluten_free": True,
            "is_featured": True,
            "available": True,
            "ingredients": ["Arabica espresso blend", "Whole milk or choice of oat/almond"],
            "notes": "Served at silky 60°C drinking temperature.",
            "options": [
                {"name": "Milk Choice", "choices": [{"label": "Whole Milk (Standard)", "price": 0}, {"label": "Minor Figures Oat Milk", "price": 40}, {"label": "House Almond Milk", "price": 40}]}
            ]
        },
        {
            "id": "c3",
            "slug": "cold-brew-amber",
            "name": "18-Hour Kyoto Cold Brew",
            "tagline": "Slow drip / Ethiopian Yirgacheffe",
            "category": "coffee",
            "price": 240,
            "description": "Slow cold-water dripped over 18 hours drop-by-drop through an architectural Kyoto glass tower. Delicate floral jasmine aromatics and bergamot clarity.",
            "image": "https://images.unsplash.com/photo-1517701604599-bb29b565090c?auto=format&fit=crop&w=1000&q=80",
            "is_vegetarian": True,
            "is_vegan": True,
            "is_gluten_free": True,
            "is_featured": True,
            "available": True,
            "ingredients": ["Ethiopian Yirgacheffe G1 beans", "Chilled alkaline water"],
            "notes": "Served over crystal clear hand-cut ice diamond.",
            "options": []
        },
        {
            "id": "b1",
            "slug": "truffle-scramble-croissant",
            "name": "Black Truffle Croissant",
            "tagline": "Cultured butter / French pasture eggs",
            "category": "breakfast",
            "price": 360,
            "description": "Twice-baked butter croissant folded with soft creamy pasture-raised eggs, shaved black summer truffle, Parmigiano Reggiano, and micro chives.",
            "image": "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?auto=format&fit=crop&w=1000&q=80",
            "is_vegetarian": True,
            "is_vegan": False,
            "is_gluten_free": False,
            "is_featured": True,
            "available": True,
            "ingredients": ["French cultured butter croissant", "Organic free-range eggs", "Black winter truffle paste", "24-month Parmigiano"],
            "notes": "Baked in small batches every morning at 6:30 AM.",
            "options": []
        },
        {
            "id": "b2",
            "slug": "sourdough-avocado-tartine",
            "name": "Wild Sourdough Avocado Tartine",
            "tagline": "48h Ferment / Hass Avocado / Dukkah",
            "category": "brunch",
            "price": 340,
            "description": "Thick toasted naturally leavened country sourdough topped with crushed Hass avocado, pickled shallots, Persian feta, toasted Egyptian dukkah, and cold-pressed olive oil.",
            "image": "https://images.unsplash.com/photo-1525351484163-7529414344d8?auto=format&fit=crop&w=1000&q=80",
            "is_vegetarian": True,
            "is_vegan": False,
            "is_gluten_free": False,
            "is_featured": True,
            "available": True,
            "ingredients": ["Stone-ground country loaf", "Hass avocado", "Persian feta", "House toasted dukkah", "Cold pressed EVOO"],
            "notes": "Vegan preparation available without feta upon request.",
            "options": []
        },
        {
            "id": "b3",
            "slug": "vanilla-bean-ricotta-hotcake",
            "name": "Whipped Ricotta Hotcake",
            "tagline": "Cast iron baked / Seasonal berries / Salted maple",
            "category": "breakfast",
            "price": 380,
            "description": "Single-skillet soufflé hotcake loaded with fresh whipped buffalo ricotta, caramelized figs, roasted macadamia crumble, and dark Quebec maple syrup.",
            "image": "https://images.unsplash.com/photo-1567620905732-2d1ec7ab7445?auto=format&fit=crop&w=1000&q=80",
            "is_vegetarian": True,
            "is_vegan": False,
            "is_gluten_free": False,
            "is_featured": False,
            "available": True,
            "ingredients": ["House made ricotta", "Tahitian vanilla bean", "Macadamia nut crumble", "Pure grade-A maple"],
            "notes": "Please allow 15 minutes as every hotcake is baked fresh to order.",
            "options": []
        },
        {
            "id": "m1",
            "slug": "miso-glazed-salmon-bowl",
            "name": "Miso Cured Salmon Bowl",
            "tagline": "Forbidden black rice / Edamame / Ponzu",
            "category": "mains",
            "price": 490,
            "description": "Gently torched sashimi-grade salmon steeped in sweet white miso glaze, served over warm heirloom black rice, shaved cucumber ribbons, avocado, and toasted sesame ponzu.",
            "image": "https://images.unsplash.com/photo-1546069901-ba9599a7e63c?auto=format&fit=crop&w=1000&q=80",
            "is_vegetarian": False,
            "is_vegan": False,
            "is_gluten_free": True,
            "is_featured": True,
            "available": True,
            "ingredients": ["Norwegian salmon", "Shiro miso", "Heirloom black rice", "Edamame", "Japanese ponzu"],
            "notes": "Gluten-free tamari glaze used.",
            "options": []
        },
        {
            "id": "m2",
            "slug": "wild-mushroom-burrata-tagliatelle",
            "name": "Forest Mushroom & Handcrafted Burrata",
            "tagline": "Hand-rolled pasta / Brown butter sage",
            "category": "mains",
            "price": 460,
            "description": "Morel, chanterelle, and king oyster mushrooms sauteed in hazelnut brown butter and sage, layered around silk handmade ribbons of egg tagliatelle and a whole torn pugliese burrata.",
            "image": "https://images.unsplash.com/photo-1555949258-eb67b1ef0ceb?auto=format&fit=crop&w=1000&q=80",
            "is_vegetarian": True,
            "is_vegan": False,
            "is_gluten_free": False,
            "is_featured": False,
            "available": True,
            "ingredients": ["Wild morels & king oysters", "Handcrafted tagliatelle", "Pugliese burrata (125g)", "Cultured butter", "Crisp sage"],
            "notes": "Pasta rolled fresh twice daily.",
            "options": []
        },
        {
            "id": "d1",
            "slug": "valrhona-dark-chocolate-fondant",
            "name": "70% Valrhona Dark Fondant",
            "tagline": "Warm molten core / Smoked sea salt gelato",
            "category": "desserts",
            "price": 320,
            "description": "Baked to order single-estate chocolate cake with an oozing liquid ganache interior, accompanied by house-spun Madagascar vanilla gelato with a dusting of smoked Maldon salt.",
            "image": "https://images.unsplash.com/photo-1606313564200-e75d5e30476c?auto=format&fit=crop&w=1000&q=80",
            "is_vegetarian": True,
            "is_vegan": False,
            "is_gluten_free": False,
            "is_featured": True,
            "available": True,
            "ingredients": ["Valrhona Guanaja 70%", "Madagascar Bourbon vanilla", "Maldon sea salt flake"],
            "notes": "12 minute baking time. Best enjoyed immediately at table.",
            "options": []
        },
        {
            "id": "d2",
            "slug": "pistachio-cardamom-choux",
            "name": "Bronte Pistachio Paris-Brest",
            "tagline": "Craquelin choux / Sicilian pistachio praline",
            "category": "desserts",
            "price": 290,
            "description": "Crisp golden choux ring crowned with butter craquelin, piped full of dense roasted Bronte pistachio mousseline and a molten salted pistachio praline heart.",
            "image": "https://images.unsplash.com/photo-1509440159596-0249088772ff?auto=format&fit=crop&w=1000&q=80",
            "is_vegetarian": True,
            "is_vegan": False,
            "is_gluten_free": False,
            "is_featured": False,
            "available": True,
            "ingredients": ["Sicilian Bronte pistachio paste", "Choux pastry", "Pure butter craquelin", "Cardamom infusion"],
            "notes": "Contains tree nuts (pistachio).",
            "options": []
        },
        {
            "id": "t1",
            "slug": "sparkling-yuzu-matcha",
            "name": "Sparkling Yuzu Ceremonial Matcha",
            "tagline": "Uji First Flush / Kochi Yuzu / Tonic",
            "category": "drinks",
            "price": 260,
            "description": "Stone-ground ceremonial Uji matcha whisked tableside and poured over chilled Japanese Kochi yuzu extract, subtle botanical tonic, and shaved ice.",
            "image": "https://images.unsplash.com/photo-1536256263959-770b48d82b0a?auto=format&fit=crop&w=1000&q=80",
            "is_vegetarian": True,
            "is_vegan": True,
            "is_gluten_free": True,
            "is_featured": True,
            "available": True,
            "ingredients": ["Ceremonial Uji matcha (Kyoto)", "Kochi yuzu reduction", "Fever-Tree tonic", "Shaved mineral ice"],
            "notes": "Whisked with bamboo chasen before service.",
            "options": []
        },
        {
            "id": "t2",
            "slug": "smoked-rosemary-cascara-tea",
            "name": "Smoked Rosemary Cascara Spritz",
            "tagline": "Coffee cherry tea / Charred rosemary / Botanicals",
            "category": "drinks",
            "price": 210,
            "description": "Brewed from sundried coffee cherry skins (cascara), lightly carbonated with notes of hibiscus, dried tamarind, and cold-smoked rosemary oil.",
            "image": "https://images.unsplash.com/photo-1556679343-c7306c1976bc?auto=format&fit=crop&w=1000&q=80",
            "is_vegetarian": True,
            "is_vegan": True,
            "is_gluten_free": True,
            "is_featured": False,
            "available": True,
            "ingredients": ["Estate cascara", "House soda", "Charred rosemary oil", "Dehydrated blood orange"],
            "notes": "Low caffeine botanical elixir.",
            "options": []
        }
    ],
    "tables": [
        {"id": "T01", "number": "01", "name": "Table 01", "capacity": 2, "section": "Courtyard Solarium", "status": "AVAILABLE", "qr_path": "/qrcode/table-01.png"},
        {"id": "T02", "number": "02", "name": "Table 02", "capacity": 2, "section": "Courtyard Solarium", "status": "AVAILABLE", "qr_path": "/qrcode/table-02.png"},
        {"id": "T03", "number": "03", "name": "Table 03", "capacity": 4, "section": "Architectural Library", "status": "AVAILABLE", "qr_path": "/qrcode/table-03.png"},
        {"id": "T04", "number": "04", "name": "Table 04", "capacity": 4, "section": "Architectural Library", "status": "OCCUPIED", "qr_path": "/qrcode/table-04.png"},
        {"id": "T05", "number": "05", "name": "Table 05", "capacity": 6, "section": "Main Timber Hall", "status": "AVAILABLE", "qr_path": "/qrcode/table-05.png"},
        {"id": "T06", "number": "06", "name": "Table 06", "capacity": 2, "section": "Barista Counter", "status": "AVAILABLE", "qr_path": "/qrcode/table-06.png"},
        {"id": "T07", "number": "07", "name": "Table 07", "capacity": 4, "section": "Garden Terrace", "status": "AVAILABLE", "qr_path": "/qrcode/table-07.png"},
        {"id": "T08", "number": "08", "name": "Table 08", "capacity": 4, "section": "Mezzanine Lounge", "status": "AVAILABLE", "qr_path": "/qrcode/table-08.png"},
        {"id": "T99", "number": "Takeaway", "name": "Takeaway Counter", "capacity": 100, "section": "Espresso Bar Pickup", "status": "AVAILABLE", "qr_path": "/qrcode/table-takeaway.png"}
    ],
    "orders": [],
    "reservations": [],
    "offers": [
        {"code": "WELCOME10", "discount_percent": 10, "description": "10% off on your first table ritual", "active": True},
        {"code": "SOLARIUM", "discount_amount": 50, "description": "Flat ₹50 off on breakfast plates above ₹400", "active": True}
    ],
    "reviews": [
        {"id": "r1", "name": "Priya Sen", "rating": 5, "comment": "The Black Truffle Croissant and Kyoto Cold Brew are unmatched in Bengaluru.", "date": "Yesterday"},
        {"id": "r2", "name": "Karan Singhal", "rating": 5, "comment": "Pure quiet luxury. Seamless table ordering and impeccable coffee extraction.", "date": "3 days ago"}
    ],
    "users": [
        {
            "id": "admin",
            "name": "Staff Operations",
            "email": "admin@smartcafe.in",
            "phone": "+91 80 4123 8890",
            "role": "admin",
            "member_since": "January 2024",
            "loyalty_points": 0
        }
    ],
    "loyalty_accounts": [],
    "favorites": []
}

class FirestoreManager:
    """Manages collections across Firebase Firestore or local persistent fallback."""

    def __init__(self):
        self.local_file = "local_firestore.json"
        self._data = {}
        self._load_local_data()

    def _load_local_data(self):
        if os.path.exists(self.local_file):
            try:
                with open(self.local_file, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except Exception:
                self._data = json.loads(json.dumps(SEED_DATA))
                self._save_local_data()
        else:
            self._data = json.loads(json.dumps(SEED_DATA))
            self._save_local_data()

    def _save_local_data(self):
        try:
            with open(self.local_file, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
        except Exception as e:
            logger.error(f"Error persisting local firestore: {e}")

    # COLLECTION: menu_items
    def get_menu_items(self, category=None, search=None, only_available=True):
        if is_firebase_live:
            try:
                col = firestore_client.collection("menu_items")
                query = col
                if only_available:
                    query = query.where("available", "==", True)
                if category and category != "all":
                    query = query.where("category", "==", category)
                docs = query.stream()
                items = [d.to_dict() for d in docs]
                if items:
                    if search:
                        q = search.lower()
                        items = [i for i in items if q in i.get("name", "").lower() or q in i.get("description", "").lower()]
                    return items
            except Exception as e:
                logger.error(f"Firestore get_menu_items error: {e}")

        # Local fallback
        items = list(self._data.get("menu_items", []))
        if only_available:
            items = [i for i in items if i.get("available", True)]
        if category and category != "all":
            items = [i for i in items if i.get("category") == category]
        if search:
            q = search.lower()
            items = [i for i in items if q in i.get("name", "").lower() or q in i.get("description", "").lower() or any(q in ing.lower() for ing in i.get("ingredients", []))]
        return items

    def get_menu_item_by_id(self, item_id):
        if is_firebase_live:
            try:
                doc = firestore_client.collection("menu_items").document(item_id).get()
                if doc.exists:
                    return doc.to_dict()
            except Exception as e:
                logger.error(f"Firestore get_menu_item_by_id error: {e}")

        for i in self._data.get("menu_items", []):
            if i.get("id") == item_id or i.get("slug") == item_id:
                return i
        return None

    def save_menu_item(self, item_data):
        item_id = item_data.get("id") or f"m-{int(datetime.now().timestamp())}"
        item_data["id"] = item_id
        if is_firebase_live:
            try:
                firestore_client.collection("menu_items").document(item_id).set(item_data, merge=True)
            except Exception as e:
                logger.error(f"Firestore save_menu_item error: {e}")

        existing = [i for i in self._data.get("menu_items", []) if i.get("id") == item_id]
        if existing:
            self._data["menu_items"] = [item_data if i.get("id") == item_id else i for i in self._data.get("menu_items", [])]
        else:
            self._data.setdefault("menu_items", []).append(item_data)
        self._save_local_data()
        return item_data

    def delete_menu_item(self, item_id):
        if is_firebase_live:
            try:
                firestore_client.collection("menu_items").document(item_id).delete()
            except Exception as e:
                logger.error(f"Firestore delete_menu_item error: {e}")

        self._data["menu_items"] = [i for i in self._data.get("menu_items", []) if i.get("id") != item_id]
        self._save_local_data()
        return True

    # COLLECTION: menu_categories
    def get_categories(self):
        if is_firebase_live:
            try:
                docs = firestore_client.collection("menu_categories").order_by("order").stream()
                cats = [d.to_dict() for d in docs]
                if cats:
                    return cats
            except Exception:
                pass
        return self._data.get("menu_categories", [])

    # COLLECTION: tables
    def get_tables(self):
        if is_firebase_live:
            try:
                docs = firestore_client.collection("tables").stream()
                tables = [d.to_dict() for d in docs]
                if tables:
                    return tables
            except Exception:
                pass
        return self._data.get("tables", [])

    def get_table_by_number(self, table_number):
        if not table_number:
            return None
        raw = str(table_number).strip().lower()
        cleaned = raw.replace("table", "").replace("-", "").strip()
        for t in self.get_tables():
            t_num = str(t.get("number")).strip().lower()
            if t_num == raw or t_num == cleaned:
                return t
            if t_num.isdigit() and cleaned.isdigit() and int(t_num) == int(cleaned):
                return t
            if str(t.get("id")).lower() == raw or str(t.get("id")).lower() == f"t{cleaned}":
                return t
        return None

    # COLLECTION: orders
    def create_order(self, order_dict):
        order_id = order_dict.get("id") or f"SC-{int(datetime.now().timestamp() * 1000) % 10000:04d}"
        order_dict["id"] = order_id
        order_dict["created_at"] = order_dict.get("created_at") or datetime.now().isoformat()

        if is_firebase_live:
            try:
                firestore_client.collection("orders").document(order_id).set(order_dict)
                logger.info("[Firestore] Order document successfully created: orders/%s", order_id)
            except Exception as e:
                logger.error("[Firestore] create_order write failed for %s: %s", order_id, e)

        self._data.setdefault("orders", []).insert(0, order_dict)
        self._save_local_data()
        return order_dict

    def get_orders(self, customer_email=None):
        if is_firebase_live:
            try:
                query = firestore_client.collection("orders")
                if customer_email:
                    query = query.where("customer_email", "==", customer_email.lower())
                docs = query.order_by("created_at", direction=firestore.Query.DESCENDING).stream()
                orders = [d.to_dict() for d in docs]
                if orders:
                    return orders
            except Exception as e:
                logger.error(f"Firestore get_orders error: {e}")

        orders = self._data.get("orders", [])
        if customer_email:
            orders = [o for o in orders if o.get("customer_email", "").lower() == customer_email.lower()]
        return orders

    def get_order_by_id(self, order_id):
        if is_firebase_live:
            try:
                doc = firestore_client.collection("orders").document(order_id).get()
                if doc.exists:
                    return doc.to_dict()
            except Exception as e:
                logger.error(f"Firestore get_order_by_id error: {e}")

        for o in self._data.get("orders", []):
            if o.get("id") == order_id:
                return o
        return None

    def update_order_status(self, order_id, status, payment_status=None):
        if is_firebase_live:
            try:
                updates = {"status": status}
                if payment_status:
                    updates["payment_status"] = payment_status
                firestore_client.collection("orders").document(order_id).update(updates)
            except Exception as e:
                logger.error(f"Firestore update_order_status error: {e}")

        for o in self._data.get("orders", []):
            if o.get("id") == order_id:
                o["status"] = status
                if payment_status:
                    o["payment_status"] = payment_status
                self._save_local_data()
                return o
        return None

    # COLLECTION: reservations
    def create_reservation(self, res_data):
        res_id = res_data.get("id") or f"RES-{int(datetime.now().timestamp() * 1000) % 10000:04d}"
        res_data["id"] = res_id
        res_data["created_at"] = res_data.get("created_at") or datetime.now().isoformat()
        res_data["status"] = res_data.get("status") or "CONFIRMED"

        if is_firebase_live:
            try:
                firestore_client.collection("reservations").document(res_id).set(res_data)
                logger.info("[Firestore] Reservation document successfully created: reservations/%s", res_id)
            except Exception as e:
                logger.error("[Firestore] create_reservation write failed for %s: %s", res_id, e)

        self._data.setdefault("reservations", []).insert(0, res_data)
        self._save_local_data()
        return res_data

    def get_reservations(self, customer_email=None):
        if is_firebase_live:
            try:
                query = firestore_client.collection("reservations")
                if customer_email:
                    query = query.where("email", "==", customer_email.lower())
                docs = query.order_by("created_at", direction=firestore.Query.DESCENDING).stream()
                res = [d.to_dict() for d in docs]
                if res:
                    return res
            except Exception as e:
                logger.error(f"Firestore get_reservations error: {e}")

        res = self._data.get("reservations", [])
        if customer_email:
            res = [r for r in res if r.get("email", "").lower() == customer_email.lower()]
        return res

    # COLLECTION: offers
    def get_offers(self):
        return [o for o in self._data.get("offers", []) if o.get("active", True)]

    def get_offer_by_code(self, code):
        for o in self.get_offers():
            if o.get("code", "").upper() == code.upper():
                return o
        return None

    # COLLECTION: reviews
    def get_reviews(self):
        return self._data.get("reviews", [])

    def add_review(self, review_data):
        review_data["id"] = f"r-{int(datetime.now().timestamp())}"
        self._data.setdefault("reviews", []).insert(0, review_data)
        self._save_local_data()
        return review_data

    # COLLECTION: users
    def get_user_by_email(self, email):
        clean = email.strip().lower()
        if is_firebase_live:
            try:
                docs = firestore_client.collection("users").where("email", "==", clean).limit(1).stream()
                for d in docs:
                    return d.to_dict()
            except Exception as e:
                logger.error(f"[Firestore] get_user_by_email error: {e}")

        for u in self._data.get("users", []):
            if u.get("email", "").lower() == clean:
                return u
        return None

    def get_users(self):
        if is_firebase_live:
            try:
                docs = firestore_client.collection("users").stream()
                user_list = [d.to_dict() for d in docs]
                if user_list:
                    return user_list
            except Exception as e:
                logger.error(f"[Firestore] get_users error: {e}")
        return self._data.get("users", [])

    def create_or_update_user(self, user_dict):
        clean = user_dict.get("email", "").strip().lower()
        user_dict["email"] = clean
        uid = user_dict.get("firebase_uid") or user_dict.get("id") or clean

        if is_firebase_live:
            try:
                doc_ref = firestore_client.collection("users").document(uid)
                doc_ref.set(user_dict, merge=True)
                logger.info("[Firestore] User document created/merged: %s", uid)
            except Exception as e:
                logger.error(f"[Firestore] create_or_update_user error: {e}")

        existing = [u for u in self._data.get("users", []) if u.get("email", "").lower() == clean]
        if existing:
            self._data["users"] = [user_dict if u.get("email", "").lower() == clean else u for u in self._data.get("users", [])]
        else:
            self._data.setdefault("users", []).append(user_dict)
        self._save_local_data()
        return user_dict

    def update_table_status(self, table_number, status):
        clean_num = str(table_number).strip().lower()
        if is_firebase_live:
            try:
                tables_ref = firestore_client.collection("tables")
                docs = tables_ref.where("number", "==", str(table_number)).stream()
                for d in docs:
                    d.reference.update({"status": status})
            except Exception as e:
                logger.error(f"[Firestore] update_table_status error: {e}")

        for t in self._data.get("tables", []):
            if str(t.get("number")).strip().lower() == clean_num:
                t["status"] = status
                self._save_local_data()
                return t
        return None

    def update_reservation_status(self, res_id, status):
        if is_firebase_live:
            try:
                firestore_client.collection("reservations").document(res_id).update({"status": status})
            except Exception as e:
                logger.error(f"[Firestore] update_reservation_status error: {e}")

        for r in self._data.get("reservations", []):
            if r.get("id") == res_id:
                r["status"] = status
                self._save_local_data()
                return r
        return None



# Global Firestore Manager instance
db_manager = FirestoreManager()
