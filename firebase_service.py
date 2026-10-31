import os
import re
import json
import logging
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config

logger = logging.getLogger(__name__)

# Attempt to initialize Firebase Admin SDK (optional live cloud connection)
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

        try:
            list(firestore_client.collection("_health").limit(1).stream())
            is_firebase_live = True
            logger.info("[Firestore] Successfully connected to live Cloud Firestore database for project: %s", Config.FIREBASE_PROJECT_ID)
        except Exception as conn_err:
            is_firebase_live = False
            logger.warning("[Firestore] Using resilient local store. Error: %s", conn_err)
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


def normalize_mobile(mobile_str: str) -> str:
    """
    Normalizes Indian mobile numbers:
    - Strips spaces, dashes, dots, parentheses, and leading '+91', '91', or '0'
    - Validates that the remaining string is exactly 10 digits starting with 6, 7, 8, or 9
    """
    if not mobile_str:
        return ""
    cleaned = re.sub(r'[\s\-\(\)\.]', '', str(mobile_str).strip())
    if cleaned.startswith('+91'):
        cleaned = cleaned[3:]
    elif cleaned.startswith('91') and len(cleaned) == 12:
        cleaned = cleaned[2:]
    elif cleaned.startswith('0') and len(cleaned) == 11:
        cleaned = cleaned[1:]
    
    if re.match(r'^[6-9]\d{9}$', cleaned):
        return cleaned
    return ""


# Default Seed Data for Aroma Cafe
DEFAULT_SEED_DATA = {
    "settings": {
        "cafe_name": "Aroma Cafe",
        "tagline": "Boutique Artisanal Sanctuary & Kitchen",
        "location": "12th Main, Indiranagar, Bengaluru",
        "opening_hours": "07:30 AM – 11:00 PM Daily",
        "gst_rate": 5.0,
        "sound_enabled": True,
        "currency_symbol": "₹",
        "contact_phone": "+91 82008 78170"
    },
    "menu_categories": [
        {"id": "all", "name": "All Offerings", "order": 0},
        {"id": "coffee", "name": "Coffee & Espresso", "order": 1},
        {"id": "manual_brew", "name": "Manual Brews", "order": 2},
        {"id": "tea", "name": "Tea & Botanicals", "order": 3},
        {"id": "bakery", "name": "Bakery & Small Plates", "order": 4},
        {"id": "mains", "name": "Artisanal Mains", "order": 5}
    ],
    "menu_items": [
        {
            "id": "c1",
            "slug": "estate-espresso",
            "name": "Estate Espresso",
            "tagline": "Double extraction / Chikmagalur Reserve",
            "category": "coffee",
            "price": 160,
            "description": "A vibrant double pull highlighting notes of dark cacao, candied orange peel, and raw panela sugar. Extracted on custom Synesso MVP.",
            "image": "https://images.unsplash.com/photo-1510591509098-f4fdc6d0ff04?auto=format&fit=crop&w=1000&q=80",
            "is_vegetarian": True,
            "is_vegan": True,
            "is_featured": True,
            "available": True,
            "options": [{"name": "Extraction", "choices": [{"label": "Standard Double", "price": 0}, {"label": "Ristretto", "price": 0}]}]
        },
        {
            "id": "c2",
            "slug": "velvet-flat-white",
            "name": "Velvet Flat White",
            "tagline": "Micro-textured steam / Honey roast",
            "category": "coffee",
            "price": 220,
            "description": "Silky micro-foam delicately folded into a concentrated double shot of medium-roast Arabica blend.",
            "image": "https://images.unsplash.com/photo-1577968897966-3d4325b36b61?auto=format&fit=crop&w=1000&q=80",
            "is_vegetarian": True,
            "is_vegan": False,
            "is_featured": True,
            "available": True,
            "options": [{"name": "Milk Choice", "choices": [{"label": "Whole Milk (Standard)", "price": 0}, {"label": "Oat Milk", "price": 40}, {"label": "Almond Milk", "price": 40}]}]
        },
        {
            "id": "c3",
            "slug": "kyoto-cold-brew",
            "name": "18-Hour Kyoto Cold Brew",
            "tagline": "Slow drip / Ethiopian Yirgacheffe",
            "category": "coffee",
            "price": 240,
            "description": "Slow cold-water dripped over 18 hours drop-by-drop through an architectural Kyoto glass tower.",
            "image": "https://images.unsplash.com/photo-1517701604599-bb29b565090c?auto=format&fit=crop&w=1000&q=80",
            "is_vegetarian": True,
            "is_vegan": True,
            "is_featured": True,
            "available": True,
            "options": []
        },
        {
            "id": "c4",
            "slug": "single-origin-pourover",
            "name": "V60 Single-Origin Pourover",
            "tagline": "Manual filter / Shevaroys Honey Process",
            "category": "manual_brew",
            "price": 260,
            "description": "Delicate notes of stone fruit, white tea, and lemon blossom filtered through Japanese Hario paper cone.",
            "image": "https://images.unsplash.com/photo-1495474472287-4d71bcdd2085?auto=format&fit=crop&w=1000&q=80",
            "is_vegetarian": True,
            "is_vegan": True,
            "is_featured": True,
            "available": True,
            "options": []
        },
        {
            "id": "c5",
            "slug": "aeropress-immersion",
            "name": "AeroPress Clean Immersion",
            "tagline": "Inverted immersion / Coorg Washed",
            "category": "manual_brew",
            "price": 230,
            "description": "Full-immersion extraction producing high body, sweetness, and ultra-low acidity.",
            "image": "https://images.unsplash.com/photo-1514432324607-a09d9b4aefdd?auto=format&fit=crop&w=1000&q=80",
            "is_vegetarian": True,
            "is_vegan": True,
            "is_featured": False,
            "available": True,
            "options": []
        },
        {
            "id": "t1",
            "slug": "silver-needle-white-tea",
            "name": "Silver Needle Spring White Tea",
            "tagline": "First Flush / Darjeeling Single Estate",
            "category": "tea",
            "price": 210,
            "description": "Plucked early morning before dawn. Unoxidized buds offering silky notes of melon, melon blossom, and clean pine.",
            "image": "https://images.unsplash.com/photo-1576092768241-dec231879fc3?auto=format&fit=crop&w=1000&q=80",
            "is_vegetarian": True,
            "is_vegan": True,
            "is_featured": True,
            "available": True,
            "options": []
        },
        {
            "id": "t2",
            "slug": "ceremonial-matcha-latte",
            "name": "Uji Ceremonial Matcha Latte",
            "tagline": "Stone Ground / Kyoto Harvest",
            "category": "tea",
            "price": 280,
            "description": "First-harvest ceremonial matcha whisked by hand with bamboo chasen and folded into steamed oat milk.",
            "image": "https://images.unsplash.com/photo-1536256263959-770b48d82b0a?auto=format&fit=crop&w=1000&q=80",
            "is_vegetarian": True,
            "is_vegan": True,
            "is_featured": True,
            "available": True,
            "options": []
        },
        {
            "id": "b1",
            "slug": "truffle-scramble-croissant",
            "name": "Black Truffle Croissant",
            "tagline": "Cultured butter / French pasture eggs",
            "category": "bakery",
            "price": 360,
            "description": "Twice-baked butter croissant folded with soft creamy pasture-raised eggs, shaved black summer truffle, and Parmigiano.",
            "image": "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?auto=format&fit=crop&w=1000&q=80",
            "is_vegetarian": True,
            "is_vegan": False,
            "is_featured": True,
            "available": True,
            "options": []
        },
        {
            "id": "b2",
            "slug": "cardamom-pistachio-bun",
            "name": "Swedish Cardamom Knot",
            "tagline": "Laminated sourdough / Freshly ground cardamom",
            "category": "bakery",
            "price": 190,
            "description": "Laminated brioche dough knotted with browned butter, raw Demerara sugar, and crushed Kerala green cardamom.",
            "image": "https://images.unsplash.com/photo-1509440159596-0249088772ff?auto=format&fit=crop&w=1000&q=80",
            "is_vegetarian": True,
            "is_vegan": False,
            "is_featured": True,
            "available": True,
            "options": []
        },
        {
            "id": "b3",
            "slug": "sourdough-tartine-avocado",
            "name": "Avocado & Labneh Tartine",
            "tagline": "Wild sourdough / Za'atar emulsion",
            "category": "bakery",
            "price": 320,
            "description": "Thick toasted country sourdough rubbed with garlic, layered with strained citrus labneh, Hass avocado, and toasted pistachios.",
            "image": "https://images.unsplash.com/photo-1525351484163-7529414344d8?auto=format&fit=crop&w=1000&q=80",
            "is_vegetarian": True,
            "is_vegan": False,
            "is_featured": False,
            "available": True,
            "options": []
        },
        {
            "id": "m1",
            "slug": "wild-mushroom-polenta-bowl",
            "name": "Braised Forest Mushroom Bowl",
            "tagline": "Creamy polenta / Porcini thyme jus",
            "category": "mains",
            "price": 420,
            "description": "Pan-seared king oyster and cremini mushrooms over slow-cooked mascarpone polenta, crispy sage, and shaved Pecorino Romano.",
            "image": "https://images.unsplash.com/photo-1546069901-ba9599a7e63c?auto=format&fit=crop&w=1000&q=80",
            "is_vegetarian": True,
            "is_vegan": False,
            "is_featured": True,
            "available": True,
            "options": []
        },
        {
            "id": "m2",
            "slug": "artisan-burrata-panzanella",
            "name": "Bengaluru Artisanal Burrata",
            "tagline": "Heirloom tomatoes / Sourdough crisp",
            "category": "mains",
            "price": 460,
            "description": "Locally cultured buffalo milk burrata, charred estate peaches, basil pesto, cold-pressed olive oil, and balsamic caviar.",
            "image": "https://images.unsplash.com/photo-1592417817098-8f3d6eb22509?auto=format&fit=crop&w=1000&q=80",
            "is_vegetarian": True,
            "is_vegan": False,
            "is_featured": True,
            "available": True,
            "options": []
        }
    ],
    "tables": [
        {"id": "T1", "number": "01", "capacity": 2, "section": "Window Solarium", "status": "free", "active_order_id": None},
        {"id": "T2", "number": "02", "capacity": 2, "section": "Window Solarium", "status": "occupied", "active_order_id": "ORD-101"},
        {"id": "T3", "number": "03", "capacity": 4, "section": "Espresso Bar", "status": "occupied", "active_order_id": "ORD-102"},
        {"id": "T4", "number": "04", "capacity": 4, "section": "Courtyard Garden", "status": "free", "active_order_id": None},
        {"id": "T5", "number": "05", "capacity": 6, "section": "Courtyard Garden", "status": "reserved", "active_order_id": None},
        {"id": "T6", "number": "06", "capacity": 2, "section": "Library Mezzanine", "status": "needs_cleaning", "active_order_id": None},
        {"id": "T7", "number": "07", "capacity": 4, "section": "Library Mezzanine", "status": "free", "active_order_id": None},
        {"id": "T8", "number": "08", "capacity": 8, "section": "Private Tasting Room", "status": "occupied", "active_order_id": "ORD-103"},
        {"id": "Takeaway", "number": "Takeaway", "capacity": 0, "section": "Express Counter", "status": "free", "active_order_id": None}
    ],
    "users": [
        {
            "id": "staff-admin",
            "username": "admin",
            "name": "Head of Operations",
            "mobile": "9999900001",
            "password_hash": generate_password_hash("admin@123"),
            "role": "admin",
            "created_at": "2024-01-15T09:00:00"
        },
        {
            "id": "staff-mgr",
            "username": "manager",
            "name": "Floor Manager",
            "mobile": "9999900002",
            "password_hash": generate_password_hash("manager@123"),
            "role": "manager",
            "created_at": "2024-02-01T10:30:00"
        },
        {
            "id": "staff-barista",
            "username": "barista",
            "name": "Lead Barista",
            "mobile": "9999900003",
            "password_hash": generate_password_hash("staff@123"),
            "role": "staff",
            "created_at": "2024-03-10T11:00:00"
        },
        {
            "id": "cust-smit",
            "name": "Smit Patel",
            "mobile": "8200878170",
            "password_hash": generate_password_hash("password123"),
            "role": "customer",
            "created_at": "2024-06-12T14:20:00",
            "orders_count": 5,
            "total_spend": 2840,
            "last_visit": "2024-10-31T18:45:00"
        },
        {
            "id": "cust-priya",
            "name": "Priya Sen",
            "mobile": "9876543210",
            "password_hash": generate_password_hash("password123"),
            "role": "customer",
            "created_at": "2024-07-20T16:15:00",
            "orders_count": 3,
            "total_spend": 1420,
            "last_visit": "2024-10-30T15:20:00"
        },
        {
            "id": "cust-karan",
            "name": "Karan Singhal",
            "mobile": "9845012345",
            "password_hash": generate_password_hash("password123"),
            "role": "customer",
            "created_at": "2024-08-05T12:00:00",
            "orders_count": 2,
            "total_spend": 880,
            "last_visit": "2024-10-28T11:10:00"
        },
        {
            "id": "cust-ananya",
            "name": "Ananya Rao",
            "mobile": "9916098765",
            "password_hash": generate_password_hash("password123"),
            "role": "customer",
            "created_at": "2024-09-14T19:30:00",
            "orders_count": 4,
            "total_spend": 2150,
            "last_visit": "2024-10-29T20:15:00"
        }
    ],
    "orders": [
        {
            "id": "ORD-101",
            "table_number": "02",
            "table_section": "Window Solarium",
            "customer_name": "Smit Patel",
            "customer_mobile": "8200878170",
            "status": "PREPARING",
            "items": [
                {"name": "Estate Espresso", "quantity": 1, "unit_price": 160, "item_total": 160},
                {"name": "Swedish Cardamom Knot", "quantity": 2, "unit_price": 190, "item_total": 380}
            ],
            "subtotal": 540,
            "tax": 27,
            "discount": 0,
            "total": 567,
            "payment_status": "PAID",
            "payment_method": "UPI",
            "notes": "Serve espresso extra hot",
            "created_at": "2024-10-31T20:42:00",
            "timeline": [
                {"status": "PENDING", "time": "2024-10-31T20:42:00", "actor": "Customer"},
                {"status": "PREPARING", "time": "2024-10-31T20:45:00", "actor": "Barista"}
            ]
        },
        {
            "id": "ORD-102",
            "table_number": "03",
            "table_section": "Espresso Bar",
            "customer_name": "Priya Sen",
            "customer_mobile": "9876543210",
            "status": "PENDING",
            "items": [
                {"name": "Velvet Flat White", "quantity": 2, "unit_price": 220, "item_total": 440},
                {"name": "Black Truffle Croissant", "quantity": 1, "unit_price": 360, "item_total": 360}
            ],
            "subtotal": 800,
            "tax": 40,
            "discount": 0,
            "total": 840,
            "payment_status": "PENDING",
            "payment_method": "Counter Pay",
            "notes": "Oat milk for flat whites please",
            "created_at": "2024-10-31T20:48:00",
            "timeline": [
                {"status": "PENDING", "time": "2024-10-31T20:48:00", "actor": "Customer"}
            ]
        },
        {
            "id": "ORD-103",
            "table_number": "08",
            "table_section": "Private Tasting Room",
            "customer_name": "Ananya Rao",
            "customer_mobile": "9916098765",
            "status": "READY",
            "items": [
                {"name": "Braised Forest Mushroom Bowl", "quantity": 2, "unit_price": 420, "item_total": 840},
                {"name": "18-Hour Kyoto Cold Brew", "quantity": 2, "unit_price": 240, "item_total": 480}
            ],
            "subtotal": 1320,
            "tax": 66,
            "discount": 0,
            "total": 1386,
            "payment_status": "PAID",
            "payment_method": "Card",
            "notes": "Ready on pass for Table 08",
            "created_at": "2024-10-31T20:25:00",
            "timeline": [
                {"status": "PENDING", "time": "2024-10-31T20:25:00", "actor": "Customer"},
                {"status": "PREPARING", "time": "2024-10-31T20:28:00", "actor": "Kitchen"},
                {"status": "READY", "time": "2024-10-31T20:46:00", "actor": "Pass"}
            ]
        },
        {
            "id": "ORD-100",
            "table_number": "01",
            "table_section": "Window Solarium",
            "customer_name": "Karan Singhal",
            "customer_mobile": "9845012345",
            "status": "COMPLETED",
            "items": [
                {"name": "V60 Single-Origin Pourover", "quantity": 1, "unit_price": 260, "item_total": 260},
                {"name": "Swedish Cardamom Knot", "quantity": 1, "unit_price": 190, "item_total": 190}
            ],
            "subtotal": 450,
            "tax": 22.5,
            "discount": 0,
            "total": 472.5,
            "payment_status": "PAID",
            "payment_method": "UPI",
            "notes": "",
            "created_at": "2024-10-31T19:15:00",
            "timeline": [
                {"status": "PENDING", "time": "2024-10-31T19:15:00", "actor": "Customer"},
                {"status": "PREPARING", "time": "2024-10-31T19:18:00", "actor": "Barista"},
                {"status": "READY", "time": "2024-10-31T19:30:00", "actor": "Pass"},
                {"status": "COMPLETED", "time": "2024-10-31T20:10:00", "actor": "Staff"}
            ]
        }
    ],
    "reservations": [
        {
            "id": "RES-201",
            "name": "Dr. Sameer Joshi",
            "mobile": "9820011223",
            "party_size": 4,
            "date": "2024-10-31",
            "time": "21:00",
            "zone": "Courtyard Garden",
            "table_number": "05",
            "status": "CONFIRMED",
            "special_notes": "Anniversary celebration, quieter table requested.",
            "created_at": "2024-10-31T14:00:00"
        },
        {
            "id": "RES-202",
            "name": "Meera Nambiar",
            "mobile": "9845099887",
            "party_size": 2,
            "date": "2024-10-31",
            "time": "21:30",
            "zone": "Window Solarium",
            "table_number": "01",
            "status": "CONFIRMED",
            "special_notes": "High stool or window seat preferred.",
            "created_at": "2024-10-31T16:30:00"
        },
        {
            "id": "RES-200",
            "name": "Vikram Seth",
            "mobile": "9880012345",
            "party_size": 3,
            "date": "2024-10-31",
            "time": "19:00",
            "zone": "Espresso Bar",
            "table_number": "03",
            "status": "SEATED",
            "special_notes": "Tasting flight consultation.",
            "created_at": "2024-10-31T12:00:00"
        }
    ],
    "offers": [
        {"code": "AROMA10", "discount_percent": 10, "description": "10% privilege on boutique brews", "active": True},
        {"code": "WELCOME50", "discount_amount": 50, "description": "₹50 welcome on first artisanal order", "active": True}
    ],
    "reviews": []
}


class FirestoreManager:
    """
    Central database manager supporting local JSON persistence and Firestore SDK.
    """
    def __init__(self, local_file=None):
        if local_file is None:
            local_file = os.path.join(os.path.dirname(__file__), "local_firestore.json")
        self.local_file = local_file
        self._load_local_data()

    def _load_local_data(self):
        if os.path.exists(self.local_file):
            try:
                with open(self.local_file, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
                    self._run_migrations()
                    return
            except Exception as e:
                logger.error(f"Error loading local store {self.local_file}: {e}")
        self._data = json.loads(json.dumps(DEFAULT_SEED_DATA))
        self._save_local_data()

    def _save_local_data(self):
        try:
            with open(self.local_file, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving local data: {e}")

    def _run_migrations(self):
        """
        Auto-migration on startup:
        - Ensure password hashing for all users
        - Strip email fields from customer records and ensure 10-digit mobile exists
        - Ensure default staff accounts (admin, manager, barista)
        - Ensure settings key exists
        """
        changed = False
        if "settings" not in self._data:
            self._data["settings"] = DEFAULT_SEED_DATA["settings"]
            changed = True
        
        # Ensure users array
        if "users" not in self._data:
            self._data["users"] = DEFAULT_SEED_DATA["users"]
            changed = True

        # Check staff accounts
        usernames = {u.get("username") for u in self._data.get("users", []) if u.get("username")}
        for default_staff in DEFAULT_SEED_DATA["users"]:
            if default_staff.get("username") and default_staff["username"] not in usernames:
                self._data["users"].append(default_staff)
                changed = True

        # Normalize mobile & passwords for existing users
        for user in self._data.get("users", []):
            if "email" in user:
                del user["email"]
                changed = True
            raw_pwd = user.get("password")
            if raw_pwd and not user.get("password_hash"):
                user["password_hash"] = generate_password_hash(raw_pwd)
                del user["password"]
                changed = True
            if user.get("mobile"):
                norm = normalize_mobile(user["mobile"])
                if norm and norm != user["mobile"]:
                    user["mobile"] = norm
                    changed = True

        # Normalize orders: customer_mobile instead of customer_email
        for order in self._data.get("orders", []):
            if "customer_email" in order:
                del order["customer_email"]
                changed = True

        if changed:
            self._save_local_data()

    # ── SETTINGS ─────────────────────────────────────────────────────────────
    def get_settings(self):
        return self._data.get("settings", DEFAULT_SEED_DATA["settings"])

    def update_settings(self, new_settings: dict):
        current = self.get_settings()
        current.update(new_settings)
        self._data["settings"] = current
        self._save_local_data()
        return current

    # ── MENU ─────────────────────────────────────────────────────────────────
    def get_categories(self):
        return self._data.get("menu_categories", DEFAULT_SEED_DATA["menu_categories"])

    def get_menu_items(self, category=None, search=None, only_available=True):
        items = self._data.get("menu_items", [])
        if only_available:
            items = [i for i in items if i.get("available", True)]
        if category and category != "all":
            items = [i for i in items if i.get("category") == category]
        if search:
            q = search.lower().strip()
            items = [i for i in items if q in i.get("name", "").lower() or q in i.get("description", "").lower() or q in i.get("tagline", "").lower()]
        return items

    def get_menu_item_by_id(self, item_id):
        for item in self._data.get("menu_items", []):
            if item.get("id") == item_id or item.get("slug") == item_id:
                return item
        return None

    def save_menu_item(self, item_dict):
        items = self._data.get("menu_items", [])
        idx = next((i for i, x in enumerate(items) if x.get("id") == item_dict.get("id")), -1)
        if idx >= 0:
            items[idx].update(item_dict)
        else:
            items.append(item_dict)
        self._data["menu_items"] = items
        self._save_local_data()
        return item_dict

    def toggle_menu_item_86(self, item_id, available=None):
        item = self.get_menu_item_by_id(item_id)
        if not item:
            return None
        if available is None:
            item["available"] = not item.get("available", True)
        else:
            item["available"] = bool(available)
        self._save_local_data()
        return item

    def bulk_toggle_menu(self, available: bool):
        for item in self._data.get("menu_items", []):
            item["available"] = available
        self._save_local_data()
        return len(self._data.get("menu_items", []))

    def delete_menu_item(self, item_id):
        items = self._data.get("menu_items", [])
        initial_len = len(items)
        items = [i for i in items if i.get("id") != item_id]
        if len(items) != initial_len:
            self._data["menu_items"] = items
            self._save_local_data()
            return True
        return False

    # ── TABLES ───────────────────────────────────────────────────────────────
    def get_tables(self):
        return self._data.get("tables", DEFAULT_SEED_DATA["tables"])

    def get_table_by_number(self, table_number):
        for t in self.get_tables():
            if str(t.get("number")).lower() == str(table_number).lower() or str(t.get("id")).lower() == str(table_number).lower():
                return t
        return None

    def update_table_status(self, table_number, status, active_order_id=None):
        for t in self._data.get("tables", []):
            if str(t.get("number")).lower() == str(table_number).lower() or str(t.get("id")).lower() == str(table_number).lower():
                t["status"] = status
                if active_order_id is not None:
                    t["active_order_id"] = active_order_id
                elif status == "free":
                    t["active_order_id"] = None
                self._save_local_data()
                return t
        return None

    # ── ORDERS ───────────────────────────────────────────────────────────────
    def get_orders(self):
        orders = self._data.get("orders", [])
        # Return sorted by created_at desc
        return sorted(orders, key=lambda o: o.get("created_at", ""), reverse=True)

    def get_order_by_id(self, order_id):
        for o in self._data.get("orders", []):
            if o.get("id") == order_id or str(o.get("order_id")) == str(order_id):
                return o
        return None

    def create_order(self, order_dict):
        if "id" not in order_dict:
            order_dict["id"] = f"ORD-{len(self._data.get('orders', [])) + 101}"
        if "created_at" not in order_dict:
            order_dict["created_at"] = datetime.now().isoformat()
        if "timeline" not in order_dict:
            order_dict["timeline"] = [
                {"status": order_dict.get("status", "PENDING"), "time": order_dict["created_at"], "actor": "Customer"}
            ]
        self._data.setdefault("orders", []).append(order_dict)

        # Update table status
        tbl = order_dict.get("table_number")
        if tbl and str(tbl).lower() != "takeaway":
            self.update_table_status(tbl, "occupied", active_order_id=order_dict["id"])

        # Update customer spend
        cust_mobile = order_dict.get("customer_mobile")
        if cust_mobile:
            user = self.get_user_by_mobile(cust_mobile)
            if user:
                user["orders_count"] = user.get("orders_count", 0) + 1
                user["total_spend"] = user.get("total_spend", 0) + float(order_dict.get("total", 0))
                user["last_visit"] = order_dict["created_at"]

        self._save_local_data()
        return order_dict

    def update_order_status(self, order_id, status, notes=None, actor="Staff"):
        for o in self._data.get("orders", []):
            if o.get("id") == order_id:
                o["status"] = status
                now_str = datetime.now().isoformat()
                timeline = o.setdefault("timeline", [])
                timeline.append({"status": status, "time": now_str, "actor": actor, "notes": notes or ""})
                
                # Table status sync on complete/cancel
                if status in ("COMPLETED", "CANCELLED"):
                    tbl = o.get("table_number")
                    if tbl and str(tbl).lower() != "takeaway":
                        self.update_table_status(tbl, "free", active_order_id=None)
                self._save_local_data()
                return o
        return None

    # ── RESERVATIONS ─────────────────────────────────────────────────────────
    def get_reservations(self):
        return sorted(self._data.get("reservations", []), key=lambda r: (r.get("date", ""), r.get("time", "")), reverse=True)

    def get_reservation_by_id(self, res_id):
        for r in self._data.get("reservations", []):
            if r.get("id") == res_id:
                return r
        return None

    def create_reservation(self, res_dict):
        if "id" not in res_dict:
            res_dict["id"] = f"RES-{len(self._data.get('reservations', [])) + 201}"
        if "created_at" not in res_dict:
            res_dict["created_at"] = datetime.now().isoformat()
        if "status" not in res_dict:
            res_dict["status"] = "CONFIRMED"
        self._data.setdefault("reservations", []).append(res_dict)
        self._save_local_data()
        return res_dict

    def update_reservation_status(self, res_id, status):
        for r in self._data.get("reservations", []):
            if r.get("id") == res_id:
                r["status"] = status
                self._save_local_data()
                return r
        return None

    # ── USERS & AUTH ─────────────────────────────────────────────────────────
    def get_users(self):
        return self._data.get("users", [])

    def get_user_by_mobile(self, mobile):
        norm = normalize_mobile(mobile)
        if not norm:
            return None
        for u in self._data.get("users", []):
            if u.get("mobile") == norm:
                return u
        return None

    def get_user_by_username(self, username):
        u_clean = str(username).strip().lower()
        for u in self._data.get("users", []):
            if u.get("username", "").strip().lower() == u_clean:
                return u
        return None

    def create_customer(self, name: str, mobile: str, password: str):
        norm = normalize_mobile(mobile)
        if not norm:
            raise ValueError("Invalid Indian mobile number. Must be 10 digits starting with 6-9.")
        if len(name.strip()) < 2:
            raise ValueError("Full Name must be at least 2 characters.")
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters.")

        if self.get_user_by_mobile(norm):
            raise ValueError("An account with this mobile number already exists. Please sign in.")

        user = {
            "id": f"cust-{datetime.now().strftime('%y%m%d%H%M%S')}",
            "name": name.strip(),
            "mobile": norm,
            "password_hash": generate_password_hash(password),
            "role": "customer",
            "created_at": datetime.now().isoformat(),
            "orders_count": 0,
            "total_spend": 0,
            "last_visit": datetime.now().isoformat()
        }
        self._data.setdefault("users", []).append(user)
        self._save_local_data()
        return user

    def verify_customer(self, mobile: str, password: str):
        norm = normalize_mobile(mobile)
        if not norm:
            return None
        user = self.get_user_by_mobile(norm)
        if not user:
            return None
        if check_password_hash(user.get("password_hash", ""), password):
            return user
        return None

    def verify_staff(self, identifier: str, password: str):
        """
        Verify staff login by username or mobile.
        """
        clean_id = str(identifier).strip().lower()
        user = None
        for u in self._data.get("users", []):
            if u.get("role") in ("admin", "manager", "staff"):
                if u.get("username", "").lower() == clean_id or u.get("mobile") == clean_id:
                    user = u
                    break
        if not user:
            return None
        if check_password_hash(user.get("password_hash", ""), password):
            return user
        return None

    def reset_customer_password(self, mobile: str, new_password: str):
        norm = normalize_mobile(mobile)
        user = self.get_user_by_mobile(norm)
        if not user:
            raise ValueError("No account found with this mobile number.")
        if len(new_password) < 8:
            raise ValueError("New password must be at least 8 characters.")
        user["password_hash"] = generate_password_hash(new_password)
        self._save_local_data()
        return user

    def add_staff_account(self, username, name, mobile, password, role="staff"):
        clean_u = str(username).strip().lower()
        if self.get_user_by_username(clean_u):
            raise ValueError("Username already exists.")
        norm = normalize_mobile(mobile) if mobile else f"99999{len(self.get_users()):05d}"
        user = {
            "id": f"staff-{datetime.now().strftime('%y%m%d%H%M%S')}",
            "username": clean_u,
            "name": name.strip(),
            "mobile": norm,
            "password_hash": generate_password_hash(password),
            "role": role if role in ("admin", "manager", "staff") else "staff",
            "created_at": datetime.now().isoformat()
        }
        self._data.setdefault("users", []).append(user)
        self._save_local_data()
        return user

    def delete_staff_account(self, staff_id):
        users = self._data.get("users", [])
        # Prevent deleting the master admin
        for u in users:
            if u.get("id") == staff_id or u.get("username") == staff_id:
                if u.get("username") == "admin":
                    raise ValueError("Cannot delete master admin account.")
        new_users = [u for u in users if u.get("id") != staff_id and u.get("username") != staff_id]
        if len(new_users) != len(users):
            self._data["users"] = new_users
            self._save_local_data()
            return True
        return False

    def get_customers_aggregated(self):
        """
        Returns all customer profiles enriched with dynamic order stats.
        """
        customers = [u for u in self._data.get("users", []) if u.get("role") == "customer"]
        orders = self.get_orders()
        for c in customers:
            c_mobile = c.get("mobile")
            c_orders = [o for o in orders if o.get("customer_mobile") == c_mobile and o.get("status") != "CANCELLED"]
            c["order_count"] = len(c_orders)
            c["total_spend"] = sum(float(o.get("total", 0)) for o in c_orders)
            if c_orders:
                c["last_visit"] = c_orders[0].get("created_at")
            elif "last_visit" not in c:
                c["last_visit"] = c.get("created_at")
        return customers

    # ── OFFERS & REVIEWS ──────────────────────────────────────────────────────
    def get_offers(self):
        return self._data.get("offers", DEFAULT_SEED_DATA["offers"])

    def get_offer_by_code(self, code):
        for o in self.get_offers():
            if o.get("code", "").upper() == str(code).upper() and o.get("active", True):
                return o
        return None

    def get_reviews(self):
        return self._data.get("reviews", [])

    def add_review(self, review_dict):
        review_dict["id"] = f"REV-{len(self._data.get('reviews', [])) + 1}"
        review_dict["created_at"] = datetime.now().isoformat()
        self._data.setdefault("reviews", []).append(review_dict)
        self._save_local_data()
        return review_dict


# Global Singleton Database Manager
db_manager = FirestoreManager()
