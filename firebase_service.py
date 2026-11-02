import os
import re
import json
import logging
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config

logger = logging.getLogger(__name__)

# Helper: check production environment
def is_production() -> bool:
    return bool(os.environ.get("VERCEL") or os.environ.get("PRODUCTION") or os.getenv("FLASK_ENV") == "production")


def serialize_firestore_data(data):
    """Recursively serializes Firestore timestamps and objects into JSON-compatible values."""
    if isinstance(data, dict):
        return {k: serialize_firestore_data(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [serialize_firestore_data(x) for x in data]
    elif hasattr(data, "isoformat"):
        return data.isoformat()
    return data

try:
    from google.cloud.firestore_v1.base_query import FieldFilter
except Exception:
    FieldFilter = None

def _where(col_ref, field_name: str, op: str, value):
    """Executes Firestore where clause using modern FieldFilter if available."""
    if FieldFilter is not None:
        return col_ref.where(filter=FieldFilter(field_name, op, value))
    return col_ref.where(field_name, op, value).isoformat()
    return data


try:
    from google.cloud.firestore_v1.base_query import FieldFilter
except Exception:
    FieldFilter = None


def _where(col_ref, field_name: str, op: str, value):
    """Executes Firestore where clause using modern FieldFilter if available."""
    if FieldFilter is not None:
        return col_ref.where(filter=FieldFilter(field_name, op, value))
    return col_ref.where(field_name, op, value)


# Attempt to initialize Firebase Admin SDK (optional live cloud connection)
firebase_app = None
firestore_client = None
firebase_auth = None
firebase_bucket = None
is_firebase_live = False

try:
    import firebase_admin
    from firebase_admin import credentials, firestore, auth, storage

    if not firebase_admin._apps:
        if Config.FIREBASE_CLIENT_EMAIL and Config.FIREBASE_PRIVATE_KEY:
            pk = Config.FIREBASE_PRIVATE_KEY.strip().strip('"').strip("'").replace("\\n", "\n")
            cred = credentials.Certificate({
                "type": "service_account",
                "project_id": Config.FIREBASE_PROJECT_ID,
                "private_key": pk,
                "client_email": Config.FIREBASE_CLIENT_EMAIL,
                "token_uri": "https://oauth2.googleapis.com/token",
            })
            firebase_app = firebase_admin.initialize_app(cred, {
                'storageBucket': Config.FIREBASE_STORAGE_BUCKET
            })
            firestore_client = firestore.client()
            firebase_auth = auth
            try:
                firebase_bucket = storage.bucket()
            except Exception:
                firebase_bucket = None
            is_firebase_live = True
            logger.info("[Firestore] Successfully connected to live Cloud Firestore database via environment credentials: %s", Config.FIREBASE_PROJECT_ID)
        elif os.path.exists(Config.FIREBASE_CREDENTIALS_PATH):
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
            is_firebase_live = True
            logger.info("[Firestore] Successfully connected to live Cloud Firestore database via credentials file: %s", Config.FIREBASE_PROJECT_ID)
        else:
            logger.warning("No Firebase Admin credentials found. Local store will be used in development.")
    else:
        firebase_app = firebase_admin.get_app()
        firestore_client = firestore.client()
        firebase_auth = auth
        is_firebase_live = True
        logger.info("[Firestore] Re-used existing Firebase app instance.")
except Exception as e:
    logger.warning(f"Firebase Admin initialization deferred: {e}. Local fallback will be used if non-production.")


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


def _ensure_firestore_seeded(db):
    """
    Safely seeds initial collection documents into Cloud Firestore
    ONLY if the target collection is completely empty.
    DO NOT delete, overwrite, migrate, or reseed existing production data.
    """
    try:
        # 1. Settings
        settings_ref = db.collection("settings").document("general")
        if not settings_ref.get().exists:
            settings_ref.set(DEFAULT_SEED_DATA["settings"])
            logger.info("[Firestore] Initialized settings/general document.")

        # 2. Menu categories
        cat_docs = list(db.collection("menu_categories").limit(1).stream())
        if not cat_docs:
            batch = db.batch()
            for cat in DEFAULT_SEED_DATA["menu_categories"]:
                batch.set(db.collection("menu_categories").document(cat["id"]), cat)
            batch.commit()
            logger.info("[Firestore] Initialized menu_categories collection.")

        # 3. Menu items
        item_docs = list(db.collection("menu_items").limit(1).stream())
        if not item_docs:
            batch = db.batch()
            for item in DEFAULT_SEED_DATA["menu_items"]:
                batch.set(db.collection("menu_items").document(item["id"]), item)
            batch.commit()
            logger.info("[Firestore] Initialized menu_items collection.")

        # 4. Tables
        table_docs = list(db.collection("tables").limit(1).stream())
        if not table_docs:
            batch = db.batch()
            for tbl in DEFAULT_SEED_DATA["tables"]:
                batch.set(db.collection("tables").document(str(tbl["number"])), tbl)
            batch.commit()
            logger.info("[Firestore] Initialized tables collection.")

        # 5. Default Staff & Seed Users
        user_docs = list(db.collection("users").limit(1).stream())
        if not user_docs:
            batch = db.batch()
            for u in DEFAULT_SEED_DATA["users"]:
                u_copy = dict(u)
                if "password" in u_copy and not u_copy.get("password_hash"):
                    u_copy["password_hash"] = generate_password_hash(u_copy.pop("password"))
                batch.set(db.collection("users").document(u_copy["id"]), u_copy)
            batch.commit()
            logger.info("[Firestore] Initialized initial users collection with staff accounts.")

        # 6. Offers
        offer_docs = list(db.collection("offers").limit(1).stream())
        if not offer_docs:
            batch = db.batch()
            for o in DEFAULT_SEED_DATA["offers"]:
                doc_id = o.get("id") or o.get("code")
                batch.set(db.collection("offers").document(doc_id), o)
            batch.commit()
            logger.info("[Firestore] Initialized offers collection.")

    except Exception as e:
        logger.error("[Firestore] Seed initialization check warning: %s", e)


class FirestoreManager:
    """
    Central database manager supporting live Cloud Firestore and local JSON development fallback.
    """
    def __init__(self, local_file=None):
        if local_file is None:
            local_file = os.path.join(os.path.dirname(__file__), "local_firestore.json")
        self.local_file = local_file
        self.db = firestore_client
        self.is_live = is_firebase_live

        if self.is_live and self.db:
            _ensure_firestore_seeded(self.db)
            self._data = {}
        else:
            if is_production():
                logger.error("[CRITICAL] Cloud Firestore client is NOT initialized in production!")
            self._load_local_data()

    def _load_local_data(self):
        if is_production():
            self._data = json.loads(json.dumps(DEFAULT_SEED_DATA))
            return
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
        if is_production():
            logger.error("[CRITICAL] Attempted local filesystem write in production environment! Write aborted.")
            raise RuntimeError("Local JSON persistence is disabled in production. Cloud Firestore is required.")
        try:
            with open(self.local_file, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving local data: {e}")

    def _run_migrations(self):
        changed = False
        if "settings" not in self._data:
            self._data["settings"] = DEFAULT_SEED_DATA["settings"]
            changed = True
        
        if "users" not in self._data:
            self._data["users"] = DEFAULT_SEED_DATA["users"]
            changed = True

        usernames = {u.get("username") for u in self._data.get("users", []) if u.get("username")}
        for default_staff in DEFAULT_SEED_DATA["users"]:
            if default_staff.get("username") and default_staff["username"] not in usernames:
                self._data["users"].append(default_staff)
                changed = True

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

        for order in self._data.get("orders", []):
            if "customer_email" in order:
                del order["customer_email"]
                changed = True

        if changed:
            self._save_local_data()

    # ── SETTINGS ─────────────────────────────────────────────────────────────
    def get_settings(self):
        if self.is_live and self.db:
            try:
                doc = self.db.collection("settings").document("general").get()
                if doc.exists:
                    return serialize_firestore_data(doc.to_dict())
                self.db.collection("settings").document("general").set(DEFAULT_SEED_DATA["settings"])
                return DEFAULT_SEED_DATA["settings"]
            except Exception as e:
                logger.error("[Firestore] get_settings error: %s", e)
                if is_production():
                    raise
        return self._data.get("settings", DEFAULT_SEED_DATA["settings"])

    def update_settings(self, new_settings: dict):
        if self.is_live and self.db:
            try:
                current = self.get_settings()
                current.update(new_settings)
                self.db.collection("settings").document("general").set(current, merge=True)
                return serialize_firestore_data(current)
            except Exception as e:
                logger.error("[Firestore] update_settings error: %s", e)
                if is_production():
                    raise
        current = self.get_settings()
        current.update(new_settings)
        self._data["settings"] = current
        self._save_local_data()
        return current

    # ── MENU ─────────────────────────────────────────────────────────────────
    def get_categories(self):
        if self.is_live and self.db:
            try:
                docs = self.db.collection("menu_categories").stream()
                cats = [serialize_firestore_data(d.to_dict()) for d in docs]
                if cats:
                    return sorted(cats, key=lambda c: c.get("order", 0))
                for c in DEFAULT_SEED_DATA["menu_categories"]:
                    self.db.collection("menu_categories").document(c["id"]).set(c)
                return DEFAULT_SEED_DATA["menu_categories"]
            except Exception as e:
                logger.error("[Firestore] get_categories error: %s", e)
                if is_production():
                    raise
        return self._data.get("menu_categories", DEFAULT_SEED_DATA["menu_categories"])

    def get_menu_items(self, category=None, search=None, only_available=True):
        if self.is_live and self.db:
            try:
                docs = self.db.collection("menu_items").stream()
                items = [serialize_firestore_data(d.to_dict()) for d in docs]
                if not items:
                    for itm in DEFAULT_SEED_DATA["menu_items"]:
                        self.db.collection("menu_items").document(itm["id"]).set(itm)
                    items = [dict(i) for i in DEFAULT_SEED_DATA["menu_items"]]
                if only_available:
                    items = [i for i in items if i.get("available", True)]
                if category and category != "all":
                    items = [i for i in items if i.get("category") == category]
                if search:
                    q = search.lower().strip()
                    items = [i for i in items if q in i.get("name", "").lower() or q in i.get("description", "").lower() or q in i.get("tagline", "").lower()]
                return items
            except Exception as e:
                logger.error("[Firestore] get_menu_items error: %s", e)
                if is_production():
                    raise
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
        if self.is_live and self.db:
            try:
                doc = self.db.collection("menu_items").document(str(item_id)).get()
                if doc.exists:
                    return serialize_firestore_data(doc.to_dict())
                q = list(_where(self.db.collection("menu_items"), "slug", "==", str(item_id)).limit(1).stream())
                if q:
                    return serialize_firestore_data(q[0].to_dict())
                return None
            except Exception as e:
                logger.error("[Firestore] get_menu_item_by_id error: %s", e)
                if is_production():
                    raise
        for item in self._data.get("menu_items", []):
            if item.get("id") == item_id or item.get("slug") == item_id:
                return item
        return None

    def save_menu_item(self, item_dict):
        if self.is_live and self.db:
            try:
                self.db.collection("menu_items").document(str(item_dict["id"])).set(item_dict, merge=True)
                return item_dict
            except Exception as e:
                logger.error("[Firestore] save_menu_item error: %s", e)
                if is_production():
                    raise
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
        if self.is_live and self.db:
            try:
                item = self.get_menu_item_by_id(item_id)
                if not item:
                    return None
                new_avail = not item.get("available", True) if available is None else bool(available)
                self.db.collection("menu_items").document(str(item["id"])).update({"available": new_avail})
                item["available"] = new_avail
                return item
            except Exception as e:
                logger.error("[Firestore] toggle_menu_item_86 error: %s", e)
                if is_production():
                    raise
        item = self.get_menu_item_by_id(item_id)
        if not item:
            return None
        item["available"] = not item.get("available", True) if available is None else bool(available)
        self._save_local_data()
        return item

    def bulk_toggle_menu(self, available: bool):
        if self.is_live and self.db:
            try:
                docs = list(self.db.collection("menu_items").stream())
                batch = self.db.batch()
                for d in docs:
                    batch.update(d.reference, {"available": available})
                batch.commit()
                return len(docs)
            except Exception as e:
                logger.error("[Firestore] bulk_toggle_menu error: %s", e)
                if is_production():
                    raise
        for item in self._data.get("menu_items", []):
            item["available"] = available
        self._save_local_data()
        return len(self._data.get("menu_items", []))

    def delete_menu_item(self, item_id):
        if self.is_live and self.db:
            try:
                self.db.collection("menu_items").document(str(item_id)).delete()
                return True
            except Exception as e:
                logger.error("[Firestore] delete_menu_item error: %s", e)
                if is_production():
                    raise
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
        if self.is_live and self.db:
            try:
                docs = self.db.collection("tables").stream()
                tbls = [serialize_firestore_data(d.to_dict()) for d in docs]
                if tbls:
                    return sorted(tbls, key=lambda t: str(t.get("number", "")))
                for t in DEFAULT_SEED_DATA["tables"]:
                    self.db.collection("tables").document(str(t["number"])).set(t)
                return DEFAULT_SEED_DATA["tables"]
            except Exception as e:
                logger.error("[Firestore] get_tables error: %s", e)
                if is_production():
                    raise
        return self._data.get("tables", DEFAULT_SEED_DATA["tables"])

    def get_table_by_number(self, table_number):
        tbl_str = str(table_number).strip().lower()
        tbl_digits = tbl_str.lstrip("t").lstrip("0")
        for t in self.get_tables():
            t_num = str(t.get("number", "")).strip().lower()
            t_id = str(t.get("id", "")).strip().lower()
            if t_num == tbl_str or t_id == tbl_str:
                return t
            if tbl_digits and (t_num.lstrip("t").lstrip("0") == tbl_digits or t_id.lstrip("t").lstrip("0") == tbl_digits):
                return t
        return None

    def update_table_status(self, table_number, status, active_order_id=None):
        if self.is_live and self.db:
            try:
                tbl = self.get_table_by_number(table_number)
                if not tbl:
                    return None
                doc_id = str(tbl.get("number") or tbl.get("id"))
                update_data = {"status": status}
                if active_order_id is not None:
                    update_data["active_order_id"] = active_order_id
                elif status == "free":
                    update_data["active_order_id"] = None
                self.db.collection("tables").document(doc_id).set(update_data, merge=True)
                tbl.update(update_data)
                return serialize_firestore_data(tbl)
            except Exception as e:
                logger.error("[Firestore] update_table_status error: %s", e)
                if is_production():
                    raise
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
        if self.is_live and self.db:
            try:
                docs = self.db.collection("orders").stream()
                orders = []
                for d in docs:
                    data = d.to_dict()
                    if "id" not in data:
                        data["id"] = d.id
                    orders.append(serialize_firestore_data(data))
                return sorted(orders, key=lambda o: str(o.get("created_at", "")), reverse=True)
            except Exception as e:
                logger.error("[Firestore] get_orders error: %s", e)
                if is_production():
                    raise
        orders = self._data.get("orders", [])
        return sorted(orders, key=lambda o: o.get("created_at", ""), reverse=True)

    def get_order_by_id(self, order_id):
        if self.is_live and self.db:
            try:
                doc = self.db.collection("orders").document(str(order_id)).get()
                if doc.exists:
                    data = doc.to_dict()
                    if "id" not in data:
                        data["id"] = doc.id
                    return serialize_firestore_data(data)
                q = list(_where(self.db.collection("orders"), "id", "==", str(order_id)).limit(1).stream())
                if q:
                    data = q[0].to_dict()
                    if "id" not in data:
                        data["id"] = q[0].id
                    return serialize_firestore_data(data)
                return None
            except Exception as e:
                logger.error("[Firestore] get_order_by_id error: %s", e)
                if is_production():
                    raise
        for o in self._data.get("orders", []):
            if o.get("id") == order_id or str(o.get("order_id")) == str(order_id):
                return o
        return None

    def create_order(self, order_dict):
        import time
        if "id" not in order_dict:
            order_dict["id"] = f"ORD-{int(time.time())}"
        if "created_at" not in order_dict:
            order_dict["created_at"] = datetime.now().isoformat()
        if "timeline" not in order_dict:
            order_dict["timeline"] = [
                {"status": order_dict.get("status", "PENDING"), "time": order_dict["created_at"], "actor": "Customer"}
            ]

        if self.is_live and self.db:
            try:
                self.db.collection("orders").document(str(order_dict["id"])).set(order_dict)

                tbl = order_dict.get("table_number")
                if tbl and str(tbl).lower() != "takeaway":
                    self.update_table_status(tbl, "occupied", active_order_id=order_dict["id"])

                cust_mobile = order_dict.get("customer_mobile")
                if cust_mobile:
                    user = self.get_user_by_mobile(cust_mobile)
                    if user:
                        new_count = user.get("orders_count", 0) + 1
                        new_spend = user.get("total_spend", 0) + float(order_dict.get("total", 0))
                        self.db.collection("users").document(user["id"]).update({
                            "orders_count": new_count,
                            "total_spend": new_spend,
                            "last_visit": order_dict["created_at"]
                        })
                return order_dict
            except Exception as e:
                logger.error("[Firestore] create_order error: %s", e)
                if is_production():
                    raise

        self._data.setdefault("orders", []).append(order_dict)
        tbl = order_dict.get("table_number")
        if tbl and str(tbl).lower() != "takeaway":
            self.update_table_status(tbl, "occupied", active_order_id=order_dict["id"])
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
        if self.is_live and self.db:
            try:
                doc_ref = self.db.collection("orders").document(str(order_id))
                doc = doc_ref.get()
                if not doc.exists:
                    q = list(_where(self.db.collection("orders"), "id", "==", str(order_id)).limit(1).stream())
                    if not q:
                        return None
                    doc_ref = q[0].reference
                    o = q[0].to_dict()
                else:
                    o = doc.to_dict()

                o["status"] = status
                now_str = datetime.now().isoformat()
                timeline = o.setdefault("timeline", [])
                timeline.append({"status": status, "time": now_str, "actor": actor, "notes": notes or ""})
                doc_ref.update({"status": status, "timeline": timeline})

                if status in ("COMPLETED", "CANCELLED"):
                    tbl = o.get("table_number")
                    if tbl and str(tbl).lower() != "takeaway":
                        self.update_table_status(tbl, "free", active_order_id=None)
                return serialize_firestore_data(o)
            except Exception as e:
                logger.error("[Firestore] update_order_status error: %s", e)
                if is_production():
                    raise

        for o in self._data.get("orders", []):
            if o.get("id") == order_id:
                o["status"] = status
                now_str = datetime.now().isoformat()
                timeline = o.setdefault("timeline", [])
                timeline.append({"status": status, "time": now_str, "actor": actor, "notes": notes or ""})
                if status in ("COMPLETED", "CANCELLED"):
                    tbl = o.get("table_number")
                    if tbl and str(tbl).lower() != "takeaway":
                        self.update_table_status(tbl, "free", active_order_id=None)
                self._save_local_data()
                return o
        return None

    # ── RESERVATIONS ─────────────────────────────────────────────────────────
    def get_reservations(self):
        if self.is_live and self.db:
            try:
                docs = self.db.collection("reservations").stream()
                res = [serialize_firestore_data(d.to_dict()) for d in docs]
                return sorted(res, key=lambda r: (str(r.get("date", "")), str(r.get("time", ""))), reverse=True)
            except Exception as e:
                logger.error("[Firestore] get_reservations error: %s", e)
                if is_production():
                    raise
        return sorted(self._data.get("reservations", []), key=lambda r: (r.get("date", ""), r.get("time", "")), reverse=True)

    def get_reservation_by_id(self, res_id):
        if self.is_live and self.db:
            try:
                doc = self.db.collection("reservations").document(str(res_id)).get()
                return serialize_firestore_data(doc.to_dict()) if doc.exists else None
            except Exception as e:
                logger.error("[Firestore] get_reservation_by_id error: %s", e)
                if is_production():
                    raise
        for r in self._data.get("reservations", []):
            if r.get("id") == res_id:
                return r
        return None

    def create_reservation(self, res_dict):
        import time
        if "id" not in res_dict:
            res_dict["id"] = f"RES-{int(time.time())}"
        if "created_at" not in res_dict:
            res_dict["created_at"] = datetime.now().isoformat()
        if "status" not in res_dict:
            res_dict["status"] = "CONFIRMED"

        if self.is_live and self.db:
            try:
                self.db.collection("reservations").document(str(res_dict["id"])).set(res_dict)
                return res_dict
            except Exception as e:
                logger.error("[Firestore] create_reservation error: %s", e)
                if is_production():
                    raise

        self._data.setdefault("reservations", []).append(res_dict)
        self._save_local_data()
        return res_dict

    def update_reservation_status(self, res_id, status):
        if self.is_live and self.db:
            try:
                doc_ref = self.db.collection("reservations").document(str(res_id))
                doc_ref.update({"status": status})
                doc = doc_ref.get()
                return serialize_firestore_data(doc.to_dict()) if doc.exists else None
            except Exception as e:
                logger.error("[Firestore] update_reservation_status error: %s", e)
                if is_production():
                    raise
        for r in self._data.get("reservations", []):
            if r.get("id") == res_id:
                r["status"] = status
                self._save_local_data()
                return r
        return None

    # ── USERS & AUTH ─────────────────────────────────────────────────────────
    def get_users(self):
        if self.is_live and self.db:
            try:
                docs = self.db.collection("users").stream()
                return [serialize_firestore_data(d.to_dict()) for d in docs]
            except Exception as e:
                logger.error("[Firestore] get_users error: %s", e)
                if is_production():
                    raise
        return self._data.get("users", [])

    def get_user_by_mobile(self, mobile):
        norm = normalize_mobile(mobile)
        if not norm:
            return None
        if self.is_live and self.db:
            try:
                q = list(_where(self.db.collection("users"), "mobile", "==", norm).limit(1).stream())
                return serialize_firestore_data(q[0].to_dict()) if q else None
            except Exception as e:
                logger.error("[Firestore] get_user_by_mobile error: %s", e)
                if is_production():
                    raise
        for u in self._data.get("users", []):
            if u.get("mobile") == norm:
                return u
        return None

    def get_user_by_username(self, username):
        clean_u = str(username).strip().lower()
        if not clean_u:
            return None
        if self.is_live and self.db:
            try:
                q = list(_where(self.db.collection("users"), "username", "==", clean_u).limit(1).stream())
                return serialize_firestore_data(q[0].to_dict()) if q else None
            except Exception as e:
                logger.error("[Firestore] get_user_by_username error: %s", e)
                if is_production():
                    raise
        for u in self._data.get("users", []):
            if u.get("username", "").strip().lower() == clean_u:
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

        if self.is_live and self.db:
            try:
                self.db.collection("users").document(user["id"]).set(user)
                return user
            except Exception as e:
                logger.error("[Firestore] create_customer error: %s", e)
                if is_production():
                    raise

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
        clean_id = str(identifier).strip().lower()
        user = None
        if self.is_live and self.db:
            try:
                q_user = list(_where(self.db.collection("users"), "username", "==", clean_id).limit(1).stream())
                if q_user:
                    cand = q_user[0].to_dict()
                    if cand.get("role") in ("admin", "manager", "staff"):
                        user = cand
                if not user:
                    q_mob = list(_where(self.db.collection("users"), "mobile", "==", clean_id).limit(1).stream())
                    if q_mob:
                        cand = q_mob[0].to_dict()
                        if cand.get("role") in ("admin", "manager", "staff"):
                            user = cand
            except Exception as e:
                logger.error("[Firestore] verify_staff error: %s", e)
                if is_production():
                    raise
        else:
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

        new_hash = generate_password_hash(new_password)
        user["password_hash"] = new_hash

        if self.is_live and self.db:
            try:
                self.db.collection("users").document(user["id"]).update({"password_hash": new_hash})
                return user
            except Exception as e:
                logger.error("[Firestore] reset_customer_password error: %s", e)
                if is_production():
                    raise

        self._save_local_data()
        return user

    def add_staff_account(self, username, name, mobile, password, role="staff"):
        clean_u = str(username).strip().lower()
        if self.get_user_by_username(clean_u):
            raise ValueError("Username already exists.")
        import time
        norm = normalize_mobile(mobile) if mobile else f"99999{int(time.time())%100000:05d}"
        user = {
            "id": f"staff-{datetime.now().strftime('%y%m%d%H%M%S')}",
            "username": clean_u,
            "name": name.strip(),
            "mobile": norm,
            "password_hash": generate_password_hash(password),
            "role": role if role in ("admin", "manager", "staff") else "staff",
            "created_at": datetime.now().isoformat()
        }
        if self.is_live and self.db:
            try:
                self.db.collection("users").document(user["id"]).set(user)
                return user
            except Exception as e:
                logger.error("[Firestore] add_staff_account error: %s", e)
                if is_production():
                    raise
        self._data.setdefault("users", []).append(user)
        self._save_local_data()
        return user

    def delete_staff_account(self, staff_id):
        if staff_id == "admin":
            raise ValueError("Cannot delete master admin account.")
        if self.is_live and self.db:
            try:
                doc = self.db.collection("users").document(staff_id).get()
                if doc.exists and doc.to_dict().get("username") == "admin":
                    raise ValueError("Cannot delete master admin account.")
                self.db.collection("users").document(staff_id).delete()
                return True
            except Exception as e:
                logger.error("[Firestore] delete_staff_account error: %s", e)
                if is_production():
                    raise
        users = self._data.get("users", [])
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
        if self.is_live and self.db:
            try:
                q = _where(self.db.collection("users"), "role", "==", "customer").stream()
                customers = [serialize_firestore_data(d.to_dict()) for d in q]
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
            except Exception as e:
                logger.error("[Firestore] get_customers_aggregated error: %s", e)
                if is_production():
                    raise
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
        if self.is_live and self.db:
            try:
                docs = self.db.collection("offers").stream()
                offers = [serialize_firestore_data(d.to_dict()) for d in docs]
                if offers:
                    return offers
                for o in DEFAULT_SEED_DATA["offers"]:
                    doc_id = o.get("id") or o.get("code")
                    self.db.collection("offers").document(doc_id).set(o)
                return DEFAULT_SEED_DATA["offers"]
            except Exception as e:
                logger.error("[Firestore] get_offers error: %s", e)
                if is_production():
                    raise
        return self._data.get("offers", DEFAULT_SEED_DATA["offers"])

    def get_offer_by_code(self, code):
        for o in self.get_offers():
            if o.get("code", "").upper() == str(code).upper() and o.get("active", True):
                return o
        return None

    def get_reviews(self):
        if self.is_live and self.db:
            try:
                docs = self.db.collection("reviews").stream()
                return [serialize_firestore_data(d.to_dict()) for d in docs]
            except Exception as e:
                logger.error("[Firestore] get_reviews error: %s", e)
                if is_production():
                    raise
        return self._data.get("reviews", [])

    def add_review(self, review_dict):
        import time
        if "id" not in review_dict:
            review_dict["id"] = f"REV-{int(time.time())}"
        if "created_at" not in review_dict:
            review_dict["created_at"] = datetime.now().isoformat()
        if self.is_live and self.db:
            try:
                self.db.collection("reviews").document(review_dict["id"]).set(review_dict)
                return review_dict
            except Exception as e:
                logger.error("[Firestore] add_review error: %s", e)
                if is_production():
                    raise
        self._data.setdefault("reviews", []).append(review_dict)
        self._save_local_data()
        return review_dict


# Global Singleton Database Manager
db_manager = FirestoreManager()
