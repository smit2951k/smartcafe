/**
 * SmartCafe — Global Vanilla JavaScript
 * Zero external libraries: Toast, Mobile Nav, Sticky Nav Scroll, IntersectionObserver
 */

document.addEventListener("DOMContentLoaded", () => {
  initScrollNavbar();
  initIntersectionReveals();
  initTableBadgeSync();
});

// Toast Notifications (Inline SVG)
function showToast(title, message, isError = false) {
  const toast = document.getElementById("globalToast");
  const titleEl = document.getElementById("toastTitle");
  const msgEl = document.getElementById("toastMessage");
  const iconWrap = document.getElementById("toastIconWrap");

  if (!toast || !titleEl || !msgEl) return;

  titleEl.textContent = title;
  msgEl.textContent = message;

  if (iconWrap) {
    if (isError) {
      iconWrap.innerHTML = `
        <svg viewBox="0 0 24 24" fill="none" stroke="#DC2626" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width: 20px; height: 20px;">
          <circle cx="12" cy="12" r="10"></circle>
          <line x1="12" y1="8" x2="12" y2="12"></line>
          <line x1="12" y1="16" x2="12.01" y2="16"></line>
        </svg>
      `;
    } else {
      iconWrap.innerHTML = `
        <svg viewBox="0 0 24 24" fill="none" stroke="#B27340" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width: 20px; height: 20px;">
          <polyline points="20 6 9 17 4 12"></polyline>
        </svg>
      `;
    }
  }

  toast.classList.add("is-active");

  if (window.toastTimeout) clearTimeout(window.toastTimeout);
  window.toastTimeout = setTimeout(() => {
    toast.classList.remove("is-active");
  }, 3800);
}

// Fullscreen Mobile Nav Toggle
function toggleMobileNav(forceOpen) {
  const overlay = document.getElementById("mobileNavMenu");
  if (!overlay) return;

  const isOpen = overlay.classList.contains("is-active");
  const willOpen = forceOpen !== undefined ? Boolean(forceOpen) : !isOpen;

  if (willOpen) {
    overlay.classList.add("is-active");
    document.body.style.overflow = "hidden";
  } else {
    overlay.classList.remove("is-active");
    document.body.style.overflow = "";
  }
}

// Global keydown listener for accessibility (Escape closes modals/dropdowns/mobile nav)
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    toggleMobileNav(false);
    if (typeof toggleProfileDropdown === "function") {
      toggleProfileDropdown(false);
    }
    if (typeof toggleCartDrawer === "function") {
      toggleCartDrawer(false);
    }
  }
});

// Close mobile navigation on desktop viewport resize
window.addEventListener("resize", () => {
  if (window.innerWidth >= 900) {
    toggleMobileNav(false);
  }
});

// Navbar Scroll Listener
function initScrollNavbar() {
  const nav = document.getElementById("mainNavbar");
  if (!nav) return;

  const isHome = window.location.pathname === "/" || nav.classList.contains("nav-transparent");
  if (!isHome) {
    nav.classList.add("nav-solid");
    return;
  }

  const handleScroll = () => {
    if (window.scrollY > 30) {
      nav.classList.add("is-scrolled");
    } else {
      nav.classList.remove("is-scrolled");
    }
  };

  window.addEventListener("scroll", handleScroll, { passive: true });
  handleScroll();
}

// Intersection Observer for Smooth Reveal Animations
function initIntersectionReveals() {
  if (!("IntersectionObserver" in window)) {
    document.querySelectorAll(".reveal").forEach(el => el.classList.add("is-visible"));
    return;
  }

  const observer = new IntersectionObserver((entries, obs) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add("is-visible");
        obs.unobserve(entry.target);
      }
    });
  }, {
    threshold: 0.12,
    rootMargin: "0px 0px -40px 0px"
  });

  document.querySelectorAll(".reveal").forEach(el => observer.observe(el));
}

// Table badge sync
function initTableBadgeSync() {
  const activeTable = localStorage.getItem("smartcafe_table") || "";
  const badge = document.getElementById("activeTableBadge");
  if (badge && !badge.textContent.includes("●")) {
    badge.textContent = activeTable === "Takeaway" ? "● TAKEAWAY" : (activeTable ? `● TABLE ${activeTable}` : "● TABLE —");
  }
}

