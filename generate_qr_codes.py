import os
import qrcode
from config import Config

def generate_table_qr_codes():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    qr_dir = os.path.join(base_dir, "qrcode")
    os.makedirs(qr_dir, exist_ok=True)

    base_url = getattr(Config, "BASE_URL", "http://127.0.0.1:5000").rstrip("/")

    tables = [
        {"num": "01", "name": "Table 01", "file": "table-01.png"},
        {"num": "02", "name": "Table 02", "file": "table-02.png"},
        {"num": "03", "name": "Table 03", "file": "table-03.png"},
        {"num": "04", "name": "Table 04", "file": "table-04.png"},
        {"num": "05", "name": "Table 05", "file": "table-05.png"},
        {"num": "06", "name": "Table 06", "file": "table-06.png"},
        {"num": "07", "name": "Table 07", "file": "table-07.png"},
        {"num": "08", "name": "Table 08", "file": "table-08.png"},
        {"num": "takeaway", "name": "Takeaway Counter", "file": "table-takeaway.png"}
    ]

    print(f"Generating scannable QR codes in: {qr_dir}")
    print(f"Using Base URL: {base_url}")

    for t in tables:
        target_url = f"{base_url}/table/{t['num']}"
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4
        )
        qr.add_data(target_url)
        qr.make(fit=True)

        # Crisp, dark espresso on clean white background for maximum scannability
        img = qr.make_image(fill_color="#171716", back_color="#FFFFFF")
        dest_path = os.path.join(qr_dir, t["file"])
        img.save(dest_path)
        print(f"  [+] {t['name']} -> {t['file']} (URL: {target_url})")

    print("\nAll Table QR codes generated successfully!")

if __name__ == "__main__":
    generate_table_qr_codes()
