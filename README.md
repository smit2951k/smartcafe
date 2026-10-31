# Aroma Cafe (Bengaluru) — Full Stack Operations & Patron Platform

A boutique artisanal hospitality and smart table ordering platform built with a Python Flask backend, semantic HTML5, modern vanilla CSS, and JavaScript.

---

## 🛠 Quickstart & Run Steps

### 1. Set Up Python Environment
```bash
# Navigate to the project root
cd "smart cafe"

# Create a virtual environment
python -m venv venv

# Activate virtual environment
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# macOS / Linux:
source venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r smartcafe/requirements.txt
```

### 3. Seed Database with Rich Demo Data
Populates 12 artisanal menu items, 9 dining tables, active orders across all statuses, today's reservations, staff operator accounts, and customer profiles.
```bash
python smartcafe/seed_data.py
```

### 4. Run the Development Server
```bash
cd smartcafe
python app.py
```
Open **[http://localhost:5000](http://localhost:5000)** in your browser.

---

## 🔑 Access Credentials

### Staff Operations Terminal (`/admin`)
- **Admin**: Username `admin` | Password `admin@123` (Full system access)
- **Manager**: Username `manager` | Password `manager@123` (Floor & menu operations)
- **Barista**: Username `barista` | Password `staff@123` (Kitchen & pass queue)

### Patron Accounts (`/login`)
- **Smit Patel**: Mobile `8200878170` | Password `password123`
- **Priya Sen**: Mobile `9876543210` | Password `password123`
- **Karan Singhal**: Mobile `9845012345` | Password `password123`
- **Ananya Rao**: Mobile `9916098765` | Password `password123`

---

## 📋 What Changed

### 1. Admin Redesign (`/admin`)
- **Unified Navigation**: Replaced duplicate top navigation links and tab rows with a single, responsive left sidebar (collapsible into a slide drawer on mobile) covering **Overview**, **Orders**, **Reservations**, **Tables**, **Menu**, **Customers**, and **Settings**.
- **Slim Top Bar**: Integrated page title, global search bar (`/` shortcut), working live clock (updates every second), customer site shortcut, and compact grouped status cluster (pulsing green live feed indicator, Web Audio chime toggle, manual sync).
- **Operations Overview**:
  - 7 KPI cards: Today's Revenue, Orders Today, Avg Ticket (shows `—` when no orders), Kitchen Active, Ready on Pass, Tables Occupied (`x/total`), Reservations Today, with vs-yesterday deltas.
  - Native HTML5 Canvas 7-Day Revenue Velocity Chart (zero heavy external charting dependencies).
  - Active Floor Queue mini-board and Boutique Bestsellers volume ranking.
- **Orders Kanban Board**:
  - 4 Kanban columns: **Pending** → **Preparing** → **Ready on Pass** → **Completed** (+ Cancelled filter).
  - Cards show Order ID, Table #, Customer name & mobile, items summary, total (`₹`), one-tap status action buttons, and elapsed timer badges (green <10 min, amber >10 min, blinking red >20 min).
  - Toggle between Kanban Board and Dense Table view.
  - Real empty states with icon and message for every column/filter.
  - 5-second live polling loop with Web Audio dual-tone synthesizer chime (`AudioContext`), toast notification, and card pulse highlight.
  - **Order Detail Drawer**: itemization, customer notes, status timeline, 80mm thermal kitchen ticket printing (`window.print()`), and cancel order modal with reason.
- **Floor Tables**: Visual floor plan grid with color-coded nodes (free, occupied, reserved, needs cleaning), active ticket viewer, status toggling, and table QR code PNG download.
- **Menu & 86 Controls**: Card grid with instant 86 availability toggle switches, bulk toggle ("Mark All Available" & "86 All Offerings"), add/edit modals, and category filtering.
- **Patron Directory**: Table listing Name, Mobile (no email), total order count, lifetime spend (`₹`), and last visit, with customer order history drawer.
- **Sanctuary Settings**: Opening hours, GST % (5%), staff operator management (list, add, delete with roles `admin`, `manager`, `staff`).

### 2. Customer Auth Overhaul (Mobile + Password Only)
- **Create Account**: Exclusively requires Full Name (min 2 chars), Mobile Number (10 Indian digits starting 6–9), Password (min 8 chars), and Confirm Password. Removed email completely from registration, sign-in, and database models.
- **Sign In**: Mobile Number + Password only.
- **Security**: Passwords hashed with `werkzeug.security` (`generate_password_hash` / `check_password_hash`), rate-limiting lockout after 5 consecutive failed attempts (HTTP 429), and secure session cookies (`HttpOnly`, `SameSite=Lax`).
- **Forgot Password**: 6-digit stub OTP flow over mobile with a clearly designated SMS provider placeholder comment in `smartcafe/app.py`.
- **Public Admin Link Removal**: Removed public "Staff Operations Terminal" link from customer navigation, footer, and login forms. Access to `/admin` is strictly secured by `@require_staff` server-side role enforcement.

### 3. Rebranding & Demo Polish
- Rebranded all instances of "SmartCafe" to **Aroma Cafe**.
- Replaced hardcoded demo string (`"TABLE 03 DETECTED"`) with real dynamic scanned table number (`"TABLE ${tableNum} DETECTED"`).
- Verified test suite (`smartcafe/test_aroma_flows.py`) passing 100%.
