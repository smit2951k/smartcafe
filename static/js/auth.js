// SmartCafe Authentication — Server-Side Firebase Auth Integration
// ================================================================
// LOGIN and ORDERING are completely separate flows.
// Authentication NEVER creates orders, submits checkout, or triggers payments.
// All Firebase Auth REST API calls are made server-side (via Flask endpoints).
// The Firebase Web API key is NEVER exposed to the browser.

// ─── Safe redirect URL validator ────────────────────────────────────────────
function getSafeRedirectUrl(targetUrl) {
  if (!targetUrl || typeof targetUrl !== "string") return "/";
  const trimmed = targetUrl.trim();
  if (!trimmed.startsWith("/") || trimmed.startsWith("//") || trimmed.startsWith("/\\")) return "/";
  if (trimmed.split("?")[0].includes(":")) return "/";
  return trimmed;
}

// ─── Update navbar: Profile icon vs Sign In link ────────────────────────────
function updateAuthUI(customer) {
  const profileWrap = document.getElementById("navProfileWrap");
  const signInLink = document.getElementById("navSignInLink");
  const dropdownName = document.getElementById("dropdownUserName");
  const dropdownEmail = document.getElementById("dropdownUserEmail");

  if (customer && customer.email) {
    if (profileWrap) profileWrap.classList.remove("hidden");
    if (signInLink) signInLink.classList.add("hidden");
    if (dropdownName) dropdownName.textContent = customer.name || "Patron Member";
    if (dropdownEmail) dropdownEmail.textContent = customer.email;
  } else {
    if (profileWrap) {
      profileWrap.classList.add("hidden");
      toggleProfileDropdown(false);
    }
    if (signInLink) signInLink.classList.remove("hidden");
  }
}

// ─── Toggle profile dropdown ─────────────────────────────────────────────────
function toggleProfileDropdown(forceState) {
  const menu = document.getElementById("navProfileDropdown");
  const btn = document.getElementById("navProfileBtn");
  if (!menu) return;

  const isOpen = menu.classList.contains("is-open");
  const shouldOpen = forceState !== undefined ? Boolean(forceState) : !isOpen;

  if (shouldOpen) {
    menu.classList.add("is-open");
    if (btn) btn.setAttribute("aria-expanded", "true");
  } else {
    menu.classList.remove("is-open");
    if (btn) btn.setAttribute("aria-expanded", "false");
  }
}

// Close profile dropdown when clicking outside
document.addEventListener("click", (e) => {
  const wrap = document.getElementById("navProfileWrap");
  if (wrap && !wrap.contains(e.target)) {
    toggleProfileDropdown(false);
  }
});

// ─── Sign In — calls server-side Flask endpoint ──────────────────────────────
async function loginCustomer(email, password) {
  const cleanEmail = email.trim().toLowerCase();

  if (!cleanEmail || !cleanEmail.includes("@")) {
    return { success: false, error: "Please enter a valid email address." };
  }
  if (!password) {
    return { success: false, error: "Please enter your password." };
  }

  try {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: cleanEmail, password })
    });

    const data = await res.json();

    if (data.success && data.customer) {
      sessionStorage.setItem("smartcafe_current_customer", JSON.stringify(data.customer));
      if (typeof window.syncCartWithServer === "function") {
        await window.syncCartWithServer();
      }
      updateAuthUI(data.customer);
      return { success: true, customer: data.customer };
    }

    return { success: false, error: data.error || "Sign in failed. Please try again." };
  } catch (err) {
    console.error("Login network error:", err);
    return { success: false, error: "Unable to connect. Please check your connection and try again." };
  }
}

// ─── Register — calls server-side Flask endpoint ──────────────────────────────
async function registerCustomer(name, email, password, phone) {
  const cleanEmail = email.trim().toLowerCase();

  if (!cleanEmail || !cleanEmail.includes("@")) {
    return { success: false, error: "Please enter a valid email address." };
  }
  if (!password || password.length < 6) {
    return { success: false, error: "Password must be at least 6 characters long." };
  }

  try {
    const res = await fetch("/api/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: name || "",
        email: cleanEmail,
        password,
        phone: phone || ""
      })
    });

    const data = await res.json();

    if (data.success && data.customer) {
      sessionStorage.setItem("smartcafe_current_customer", JSON.stringify(data.customer));
      if (typeof window.syncCartWithServer === "function") {
        await window.syncCartWithServer();
      }
      updateAuthUI(data.customer);
      return { success: true, customer: data.customer };
    }

    return { success: false, error: data.error || "Account creation failed. Please try again." };
  } catch (err) {
    console.error("Register network error:", err);
    return { success: false, error: "Unable to connect. Please check your connection and try again." };
  }
}

// ─── Sign Out ────────────────────────────────────────────────────────────────
async function logoutCustomer() {
  try {
    await fetch("/api/auth/logout", { method: "POST" });
  } catch {}

  sessionStorage.removeItem("smartcafe_current_customer");
  updateAuthUI(null);
  window.location.href = "/";
}

// ─── Expose globally ─────────────────────────────────────────────────────────
window.loginCustomer = loginCustomer;
window.registerCustomer = registerCustomer;
window.logoutCustomer = logoutCustomer;
window.updateAuthUI = updateAuthUI;
window.toggleProfileDropdown = toggleProfileDropdown;
window.getSafeRedirectUrl = getSafeRedirectUrl;

// ─── On page load: restore UI from session storage ───────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  try {
    const raw = sessionStorage.getItem("smartcafe_current_customer");
    if (raw) {
      const user = JSON.parse(raw);
      if (user && user.email) updateAuthUI(user);
    }
  } catch {}
});