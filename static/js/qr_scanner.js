/**
 * SmartCafe Camera QR Scanner
 * Clean, minimal camera scanner to scan physical table QR codes.
 * Uses html5-qrcode. No QR images are displayed on the website.
 */

let html5QrScannerInstance = null;
let isScannerActive = false;
let isProcessingScan = false;

// Extract table ID from scanned content
function extractTableId(text) {
  if (!text || typeof text !== "string") return null;
  const cleaned = text.trim();

  // Match URL containing /table/<id> (e.g. https://domain.com/table/03 or /table/03)
  const urlMatch = cleaned.match(/\/table\/([a-zA-Z0-9_-]+)/i);
  if (urlMatch && urlMatch[1]) {
    return urlMatch[1];
  }

  // Match table prefix (e.g. "table-03", "table:03", "table 03")
  const prefixMatch = cleaned.match(/^table[-:\s]+([a-zA-Z0-9]+)$/i);
  if (prefixMatch && prefixMatch[1]) {
    return prefixMatch[1];
  }

  // Match standalone 2-digit numbers "01" through "08"
  if (/^0[1-8]$/.test(cleaned)) {
    return cleaned;
  }
  if (/^[1-8]$/.test(cleaned)) {
    return cleaned.padStart(2, "0");
  }

  // Match "takeaway"
  if (cleaned.toLowerCase() === "takeaway") {
    return "Takeaway";
  }

  return null;
}

// Open Table Scanner Modal
function openTableScanner() {
  const modal = document.getElementById("cameraScannerModal");
  if (!modal) {
    // If not on a page with modal, navigate to /scan-table
    window.location.href = "/scan-table";
    return;
  }

  // Close any open table status modal or nav drawers
  closeTableStatusModal();
  if (typeof toggleMobileNav === "function") toggleMobileNav(false);
  if (typeof toggleCartDrawer === "function") toggleCartDrawer(false);

  modal.classList.remove("hidden");
  document.body.style.overflow = "hidden";

  // Reset UI elements
  resetScannerUI();

  // Start Camera
  startCameraScanner("scannerVideoViewport");
}

// Close Table Scanner Modal
function closeTableScanner() {
  const modal = document.getElementById("cameraScannerModal");
  if (modal) {
    modal.classList.add("hidden");
  }
  document.body.style.overflow = "";

  stopCameraScanner();
}

// Reset UI state
function resetScannerUI() {
  isProcessingScan = false;
  const statusEl = document.getElementById("scannerStatusMessage");
  const errorBox = document.getElementById("scannerErrorNotice");
  const successBox = document.getElementById("scannerSuccessCard");
  const viewfinder = document.getElementById("scannerViewfinder");

  if (statusEl) {
    statusEl.textContent = "Point your camera at the QR code on your SmartCafe table.";
    statusEl.className = "scanner-status-text";
  }
  if (errorBox) errorBox.classList.add("hidden");
  if (successBox) successBox.classList.add("hidden");
  if (viewfinder) viewfinder.classList.remove("hidden");
}

// Start Camera using Html5Qrcode
async function startCameraScanner(viewportId) {
  const container = document.getElementById(viewportId);
  const errorBox = document.getElementById("scannerErrorNotice");
  const errorText = document.getElementById("scannerErrorText");
  const retryBtn = document.getElementById("scannerRetryBtn");

  if (!container) return;

  // Check secure context (HTTPS or localhost)
  const isSecure = window.isSecureContext || window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1";
  if (!isSecure) {
    showScannerError("Camera access requires a secure connection (HTTPS or localhost).", false);
    return;
  }

  // Check camera support
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    showScannerError("We couldn't access your camera on this browser. Please verify camera permissions.", true);
    return;
  }

  if (typeof Html5Qrcode === "undefined") {
    showScannerError("Scanner initializing. Please try again.", true);
    return;
  }

  // Stop any existing instance
  await stopCameraScanner();

  try {
    html5QrScannerInstance = new Html5Qrcode(viewportId);
    isScannerActive = true;

    // Responsive square scan frame: min(72vw, 280px)
    const qrBoxSize = Math.max(180, Math.min(280, Math.floor(window.innerWidth * 0.72)));

    const config = {
      fps: 15,
      qrbox: { width: qrBoxSize, height: qrBoxSize },
      aspectRatio: 1.0,
      videoConstraints: {
        facingMode: { ideal: "environment" }
      },
      experimentalFeatures: {
        useBarCodeDetectorIfSupported: true
      }
    };

    await html5QrScannerInstance.start(
      { facingMode: "environment" },
      config,
      onQrCodeDetected,
      (errorMessage) => {
        // Continuous decoding frame failures are expected when no QR in frame - ignore
      }
    );

    // Ensure playsinline, webkit-playsinline, and muted on created video element for iOS Safari / Android Chrome
    const vid = container.querySelector("video");
    if (vid) {
      vid.setAttribute("playsinline", "true");
      vid.setAttribute("webkit-playsinline", "true");
      vid.muted = true;
      vid.style.width = "100%";
      vid.style.height = "100%";
      vid.style.objectFit = "cover";
    }

    // Camera started successfully
    if (errorBox) errorBox.classList.add("hidden");
  } catch (err) {
    console.warn("Camera start result:", err);
    isScannerActive = false;

    const errStr = (err && (err.name || err.message || "")).toString().toLowerCase();

    if (errStr.includes("notallowed") || errStr.includes("permission") || errStr.includes("denied")) {
      showScannerError("Camera access is blocked. Allow camera access in your browser settings and try again.", true);
    } else if (errStr.includes("notfound") || errStr.includes("device") || errStr.includes("notreadable") || errStr.includes("trackstart")) {
      showScannerError("We couldn't access your camera. Make sure another app isn't using it.", true);
    } else {
      showScannerError("We couldn't access your camera. Please check permissions and try again.", true);
    }
  }
}

// Stop Camera
async function stopCameraScanner() {
  if (html5QrScannerInstance && isScannerActive) {
    try {
      await html5QrScannerInstance.stop();
      html5QrScannerInstance.clear();
    } catch (e) {
      // Ignore stop errors
    }
    isScannerActive = false;
  }
}

// Show error inside scanner modal
function showScannerError(message, showRetry) {
  const errorBox = document.getElementById("scannerErrorNotice");
  const errorText = document.getElementById("scannerErrorText");
  const retryBtn = document.getElementById("scannerRetryBtn");
  const viewfinder = document.getElementById("scannerViewfinder");

  if (errorBox && errorText) {
    errorText.textContent = message;
    errorBox.classList.remove("hidden");
  }
  if (retryBtn) {
    retryBtn.style.display = showRetry ? "inline-flex" : "none";
  }
  if (viewfinder) {
    viewfinder.classList.add("hidden");
  }
}

// Handler when QR code is detected in camera stream
async function onQrCodeDetected(decodedText, decodedResult) {
  if (isProcessingScan) return;

  const tableId = extractTableId(decodedText);

  if (!tableId) {
    // Non-SmartCafe QR detected
    const statusEl = document.getElementById("scannerStatusMessage");
    if (statusEl) {
      statusEl.textContent = "This QR code isn't a SmartCafe table QR.";
      statusEl.className = "scanner-status-text warning";
      setTimeout(() => {
        if (!isProcessingScan && statusEl) {
          statusEl.textContent = "Point your camera at the QR code on your SmartCafe table.";
          statusEl.className = "scanner-status-text";
        }
      }, 3000);
    }
    return;
  }

  isProcessingScan = true;

  // Stop camera to freeze frame & release hardware
  await stopCameraScanner();

  const statusEl = document.getElementById("scannerStatusMessage");
  if (statusEl) {
    statusEl.textContent = "Validating Table...";
    statusEl.className = "scanner-status-text";
  }

  // Validate Table against server
  try {
    const res = await fetch(`/api/table/validate/${encodeURIComponent(tableId)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" }
    });

    const data = await res.json();

    if (data.success) {
      const tableNumber = data.table_number || data.table_id;
      handleSuccessfulScan(tableNumber, data.name || `Table ${tableNumber}`);
    } else {
      showScannerError(data.error || "Table not found.", true);
      isProcessingScan = false;
    }
  } catch (err) {
    showScannerError("Table not found. Please try again.", true);
    isProcessingScan = false;
  }
}

// Handle successful validation
function handleSuccessfulScan(tableNumber, tableName) {
  // Update state without touching cart/orders/reservations
  if (typeof setGlobalTable === "function") {
    setGlobalTable(tableNumber);
  } else {
    try {
      localStorage.setItem("smartcafe_table", tableNumber);
    } catch (e) {}
    updateTableBadges(tableNumber);
  }

  // Show small premium confirmation
  const viewfinder = document.getElementById("scannerViewfinder");
  const successBox = document.getElementById("scannerSuccessCard");
  const successNum = document.getElementById("scannerSuccessNumber");
  const statusEl = document.getElementById("scannerStatusMessage");

  if (viewfinder) viewfinder.classList.add("hidden");
  if (statusEl) statusEl.textContent = `Table ${tableNumber} detected.`;
  if (successBox) {
    if (successNum) successNum.textContent = `TABLE ${tableNumber}`;
    successBox.classList.remove("hidden");
  }

  // Seamlessly redirect to /menu
  setTimeout(() => {
    window.location.href = "/menu";
  }, 1200);
}

// Synchronize all table badges across the page
function updateTableBadges(tableNum) {
  const formatted = tableNum ? `● TABLE ${tableNum}` : "● TABLE —";
  const badges = document.querySelectorAll("#activeTableBadge, .live-table-label");
  badges.forEach(b => {
    b.textContent = formatted;
  });

  const statusDisplay = document.getElementById("tableStatusModalCurrent");
  if (statusDisplay) {
    statusDisplay.textContent = tableNum ? `TABLE ${tableNum}` : "No Table Active";
  }
}

// Table Status Popover / Modal
function openTableStatusModal() {
  const modal = document.getElementById("tableStatusModal");
  if (!modal) return;

  // Sync active table text
  fetch("/api/table/active")
    .then(r => r.json())
    .then(data => {
      const current = data.table_number || localStorage.getItem("smartcafe_table") || "";
      const display = document.getElementById("tableStatusModalCurrent");
      const changeBtn = document.getElementById("tableStatusChangeBtn");
      if (display) {
        display.textContent = current ? `TABLE ${current}` : "No Table Active";
      }
      if (changeBtn) {
        changeBtn.style.display = current ? "inline-flex" : "none";
      }
    })
    .catch(() => {});

  modal.classList.remove("hidden");
}

function closeTableStatusModal() {
  const modal = document.getElementById("tableStatusModal");
  if (modal) modal.classList.add("hidden");
}

function triggerScanFromTableStatus() {
  closeTableStatusModal();
  openTableScanner();
}

// Global initialization
document.addEventListener("DOMContentLoaded", () => {
  // Sync table status on page load from server session
  fetch("/api/table/active")
    .then(r => r.json())
    .then(data => {
      if (data.success && data.active && data.table_number) {
        updateTableBadges(data.table_number);
        try {
          localStorage.setItem("smartcafe_table", data.table_number);
        } catch (e) {}
      } else {
        const stored = localStorage.getItem("smartcafe_table");
        if (stored) {
          updateTableBadges(stored);
        } else {
          updateTableBadges(null);
        }
      }
    })
    .catch(() => {
      const stored = localStorage.getItem("smartcafe_table");
      updateTableBadges(stored || null);
    });

  // Attach navbar table badge click to Table Status Modal
  const tableBadgeLink = document.getElementById("navTableBadgeLink");
  if (tableBadgeLink) {
    tableBadgeLink.addEventListener("click", (e) => {
      e.preventDefault();
      openTableStatusModal();
    });
  }

  // Attach mobile scan button
  const mobileScanBtn = document.getElementById("mobileScanTableBtn");
  if (mobileScanBtn) {
    mobileScanBtn.addEventListener("click", (e) => {
      e.preventDefault();
      openTableScanner();
    });
  }
});
