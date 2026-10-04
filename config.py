import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "smartcafe_secret_key_2026_super_secure")
    DEBUG = os.getenv("FLASK_DEBUG", "True").lower() in ("true", "1", "t")

    # Firebase Admin SDK configuration
    FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "smart-cafe-6514f")
    FIREBASE_PRIVATE_KEY = os.getenv("FIREBASE_PRIVATE_KEY", "").replace("\\n", "\n")
    FIREBASE_CLIENT_EMAIL = os.getenv("FIREBASE_CLIENT_EMAIL", "")
    FIREBASE_CREDENTIALS_PATH = os.getenv("FIREBASE_CREDENTIALS_PATH", "smart-cafe-6514f-firebase-adminsdk-fbsvc-b95660154d.json")
    FIREBASE_STORAGE_BUCKET = os.getenv("FIREBASE_STORAGE_BUCKET", "smart-cafe-6514f.firebasestorage.app")
    FIREBASE_WEB_API_KEY = os.getenv("FIREBASE_WEB_API_KEY", "")

    # Razorpay Configuration
    RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "rzp_test_smartcafe2026")
    RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "rzp_secret_smartcafe2026")

    # Tax configuration (GST 5%)
    TAX_RATE = 0.05

    # Base URL for dynamic QR codes and redirects
    BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:5000")
