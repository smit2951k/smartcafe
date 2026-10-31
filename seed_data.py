"""
Seed Script for Aroma Cafe
Populates local database with:
- 12 artisanal menu items across 5 categories
- 9 restaurant tables with floor sections
- Sample active orders across PENDING, PREPARING, READY, COMPLETED
- Real reservations
- Staff operator accounts (admin, manager, barista)
- Customer profiles with 10-digit Indian mobile numbers
"""
import os
import json
import logging
from werkzeug.security import generate_password_hash
from firebase_service import DEFAULT_SEED_DATA, FirestoreManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)

def run_seed():
    db_path = os.path.join(os.path.dirname(__file__), "local_firestore.json")
    logger.info("Seeding Aroma Cafe database at: %s", db_path)

    # Deep copy seed data
    data = json.loads(json.dumps(DEFAULT_SEED_DATA))

    # Ensure all passwords in user seed are hashed
    for user in data["users"]:
        raw_pwd = "admin@123" if user.get("role") == "admin" else ("manager@123" if user.get("role") == "manager" else ("staff@123" if user.get("role") == "staff" else "password123"))
        user["password_hash"] = generate_password_hash(raw_pwd)

    with open(db_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    logger.info("Successfully seeded database!")
    logger.info("Seeded %d menu items", len(data["menu_items"]))
    logger.info("Seeded %d tables", len(data["tables"]))
    logger.info("Seeded %d orders", len(data["orders"]))
    logger.info("Seeded %d reservations", len(data["reservations"]))
    logger.info("Seeded %d users (3 staff, 4 customers)", len(data["users"]))

if __name__ == "__main__":
    run_seed()

