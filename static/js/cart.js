// SmartCafe Cart State & Server Price Calculation
let cart = [];
let activeTable = localStorage.getItem("smartcafe_table") || "";

function loadCartFromStorage() {
  try {
    const raw = localStorage.getItem("smartcafe_cart");
    cart = raw ? JSON.parse(raw) : [];
  } catch (e) {
    cart = [];
  }
  updateCartUI();
}

function saveCartToStorage() {
  try {
    localStorage.setItem("smartcafe_cart", JSON.stringify(cart));
  } catch (e) {}
  updateCartUI();
  window.dispatchEvent(new Event("cartUpdated"));
}

function toggleCartDrawer(open) {
  const drawer = document.getElementById("cartDrawer");
  const backdrop = document.getElementById("cartBackdrop");
  if (!drawer || !backdrop) return;

  const isClosed = drawer.classList.contains("translate-x-full");
  const shouldOpen = open !== undefined ? Boolean(open) : isClosed;

  if (shouldOpen) {
    drawer.classList.remove("translate-x-full");
    backdrop.classList.remove("hidden");
    renderCartDrawer();
  } else {
    drawer.classList.add("translate-x-full");
    backdrop.classList.add("hidden");
  }
}

function setGlobalTable(tableNumber) {
  if (!tableNumber) return;
  activeTable = String(tableNumber);
  try {
    localStorage.setItem("smartcafe_table", activeTable);
  } catch (e) {}

  // Sync navbar table badge
  const navBadge = document.getElementById("activeTableBadge");
  if (navBadge) {
    navBadge.textContent = activeTable === "Takeaway" ? "● TAKEAWAY" : (activeTable ? `● TABLE ${activeTable}` : "● TABLE —");
  }

  // Sync drawer table display
  const drawerDisplay = document.getElementById("drawerTableDisplay");
  if (drawerDisplay) {
    drawerDisplay.textContent = activeTable === "Takeaway" ? "Takeaway Counter" : (activeTable ? `Table ${activeTable}` : "Scan QR to Assign");
  }

  // Sync checkout table select & label
  const checkoutSelect = document.getElementById("checkoutTableSelect");
  if (checkoutSelect) checkoutSelect.value = activeTable;

  const checkoutDisplay = document.getElementById("checkoutTableDisplay");
  if (checkoutDisplay) {
    checkoutDisplay.textContent = activeTable === "Takeaway" ? "Takeaway Counter" : `Table ${activeTable}`;
  }

  // Sync menu page assigned table title
  const tableTitle = document.getElementById("assignedTableTitle");
  if (tableTitle) {
    tableTitle.textContent = activeTable === "Takeaway" ? "Takeaway Counter" : `Table ${activeTable}`;
  }

  // Sync floating tray table label
  const trayTableLabel = document.getElementById("floatingTrayTableLabel");
  if (trayTableLabel) {
    trayTableLabel.textContent = activeTable === "Takeaway" ? "Takeaway Order" : `Ordering for Table ${activeTable}`;
  }

  const tableBadge = document.getElementById("assignedTableBadge");
  if (tableBadge) {
    tableBadge.textContent = activeTable === "Takeaway" ? "Takeaway Counter" : `Table ${activeTable}`;
  }

  window.dispatchEvent(new CustomEvent("tableChanged", { detail: { table: activeTable } }));
}

function getGlobalTable() {
  return activeTable || localStorage.getItem("smartcafe_table") || "Takeaway";
}

function addToCart(item, quantity = 1, options = [], openDrawer = false) {
  const optKey = options.map(o => o.option_name || o.optionName || o.name || "").sort().join("|");
  const cartItemId = `${item.id}-${optKey || "std"}`;

  const existing = cart.find(ci => ci.cart_id === cartItemId);
  if (existing) {
    existing.quantity += quantity;
  } else {
    const extraPrice = options.reduce((sum, o) => sum + (parseFloat(o.price) || 0), 0);
    cart.push({
      cart_id: cartItemId,
      id: item.id,
      item_id: item.id,
      slug: item.slug || item.id,
      name: item.name,
      price: parseFloat(item.price),
      image: item.image,
      category: item.category,
      quantity: quantity,
      selected_options: options,
      extra_price: extraPrice
    });
  }

  saveCartToStorage();
  if (openDrawer) {
    toggleCartDrawer(true);
  }
}

function updateCartQuantity(cartItemId, delta) {
  const item = cart.find(ci => ci.cart_id === cartItemId || (!ci.cart_id && (ci.id === cartItemId || ci.item_id === cartItemId)));
  if (!item) return;

  item.quantity += delta;
  if (item.quantity <= 0) {
    cart = cart.filter(ci => ci !== item);
  }
  saveCartToStorage();
  renderCartDrawer();
}

function removeCartItem(cartItemId) {
  cart = cart.filter(ci => (ci.cart_id ? ci.cart_id !== cartItemId : (ci.id !== cartItemId && ci.item_id !== cartItemId)));
  saveCartToStorage();
  renderCartDrawer();
}

function clearCart() {
  cart = [];
  saveCartToStorage();
  renderCartDrawer();
}

function clearLocalCart() {
  cart = [];
  try {
    localStorage.removeItem("smartcafe_cart");
  } catch (e) {}
  updateCartUI();
  window.dispatchEvent(new Event("cartUpdated"));
}

function getLocalCart() {
  try {
    const raw = localStorage.getItem("smartcafe_cart");
    return raw ? JSON.parse(raw) : [];
  } catch (e) {
    return [];
  }
}

function addSimpleItemToCart(id, name, price, image, category, btnElement, event) {
  if (event) {
    if (typeof event.preventDefault === "function") event.preventDefault();
    if (typeof event.stopPropagation === "function") event.stopPropagation();
  }

  // Prevent accidental rapid duplicate clicks while preserving intentional multiple adds
  if (btnElement && btnElement.dataset.adding === "true") {
    addToCart({ id, name, price, image, category }, 1, [], false);
    return;
  }

  if (btnElement) {
    btnElement.dataset.adding = "true";
  }

  addToCart({ id, name, price, image, category }, 1, [], false);

  if (btnElement) {
    const originalHtml = btnElement.innerHTML;
    btnElement.innerHTML = `<span>Added ✓</span>`;
    btnElement.style.transition = "all 0.2s ease";
    btnElement.style.backgroundColor = "var(--color-accent-bronze)";
    btnElement.style.borderColor = "var(--color-accent-bronze)";
    btnElement.style.color = "var(--color-white)";

    setTimeout(() => {
      btnElement.innerHTML = originalHtml;
      btnElement.style.backgroundColor = "";
      btnElement.style.borderColor = "";
      btnElement.style.color = "";
      delete btnElement.dataset.adding;
    }, 850);
  }
}

function addItemToCart(itemObj) {
  const quantity = itemObj.quantity || 1;
  const options = itemObj.options || itemObj.selected_options || [];
  addToCart(itemObj, quantity, options, false);
}

function updateCartItemQuantity(idOrCartId, delta) {
  const item = cart.find(ci => ci.cart_id === idOrCartId || ci.item_id === idOrCartId || ci.id === idOrCartId);
  if (item) {
    updateCartQuantity(item.cart_id, delta);
  }
}

// Calculate server-side total through Flask API
async function fetchServerTotals() {
  try {
    const res = await fetch("/api/cart/calculate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ items: cart })
    });
    const data = await res.json();
    if (data.success) {
      return data;
    }
  } catch (err) {
    console.warn("Server total fallback:", err);
  }

  // Client estimation fallback
  const subtotal = cart.reduce((sum, ci) => sum + ((ci.price + (ci.extra_price || 0)) * ci.quantity), 0);
  const tax = Math.round(subtotal * 0.05);
  return { subtotal, tax, discount: 0, total: subtotal + tax };
}

async function renderCartDrawer() {
  const container = document.getElementById("drawerItemsList");
  const subtotalEl = document.getElementById("drawerSubtotal");
  const taxEl = document.getElementById("drawerTax");
  const totalEl = document.getElementById("drawerTotal");
  const badgeEl = document.getElementById("drawerItemCountBadge");
  const checkoutBtn = document.getElementById("drawerCheckoutBtn");

  if (!container) return;

  const totalCount = cart.reduce((sum, ci) => sum + ci.quantity, 0);
  if (badgeEl) badgeEl.textContent = `${totalCount} ${totalCount === 1 ? 'item' : 'items'}`;

  if (cart.length === 0) {
    container.innerHTML = `
      <div class="h-64 flex flex-col items-center justify-center text-center space-y-3 text-muted-gray">
        <div class="w-12 h-12 rounded-full bg-warm-sand/30 flex items-center justify-center text-charcoal">
          <i data-lucide="shopping-bag" class="w-6 h-6 stroke-[1.5]"></i>
        </div>
        <p class="font-serif text-lg text-charcoal">Your tray is empty</p>
        <p class="text-xs font-sans max-w-xs">Explore our estate coffees and seasonal kitchen offerings to begin your table service.</p>
        <a href="/menu" onclick="toggleCartDrawer(false)" class="mt-2 px-4 py-2 bg-deep-forest text-warm-ivory text-xs uppercase tracking-wider rounded-lg font-sans font-medium cursor-pointer">Explore Menu</a>
      </div>
    `;
    if (subtotalEl) subtotalEl.textContent = "₹0";
    if (taxEl) taxEl.textContent = "₹0";
    if (totalEl) totalEl.textContent = "₹0";
    if (checkoutBtn) checkoutBtn.classList.add("opacity-50", "pointer-events-none");
    if (window.lucide) window.lucide.createIcons();
    return;
  }

  if (checkoutBtn) checkoutBtn.classList.remove("opacity-50", "pointer-events-none");

  // Render items
  container.innerHTML = cart.map(item => `
    <div class="flex gap-3 py-3 border-b border-warm-sand/30 last:border-b-0">
      <img src="${item.image}" alt="${item.name}" class="w-16 h-16 object-cover rounded-lg bg-warm-sand/30 shrink-0" />
      <div class="flex-1 min-w-0">
        <div class="flex justify-between items-start">
          <h4 class="font-serif text-sm text-charcoal font-medium truncate">${item.name}</h4>
          <span class="font-serif text-sm text-charcoal font-semibold ml-2">₹${(item.price + (item.extra_price || 0)) * item.quantity}</span>
        </div>
        ${item.selected_options && item.selected_options.length > 0 ? `
          <p class="text-[10px] text-muted-gray truncate mt-0.5">${item.selected_options.map(o => o.option_name || o.optionName || o.name).join(", ")}</p>
        ` : ''}
        <div class="flex items-center justify-between mt-2">
          <div class="flex items-center border border-warm-sand/80 rounded bg-white">
            <button type="button" onclick="updateCartQuantity('${item.cart_id}', -1)" class="w-6 h-6 flex items-center justify-center text-charcoal hover:bg-warm-sand/20 font-bold cursor-pointer">-</button>
            <span class="w-6 text-center text-xs font-sans font-medium">${item.quantity}</span>
            <button type="button" onclick="updateCartQuantity('${item.cart_id}', 1)" class="w-6 h-6 flex items-center justify-center text-charcoal hover:bg-warm-sand/20 font-bold cursor-pointer">+</button>
          </div>
          <button type="button" onclick="removeCartItem('${item.cart_id}')" class="text-[11px] text-red-700 hover:underline cursor-pointer">Remove</button>
        </div>
      </div>
    </div>
  `).join("");

  if (window.lucide) window.lucide.createIcons();

  // Get server-verified totals
  const totals = await fetchServerTotals();
  if (subtotalEl) subtotalEl.textContent = `₹${totals.subtotal}`;
  if (taxEl) taxEl.textContent = `₹${totals.tax}`;
  if (totalEl) totalEl.textContent = `₹${totals.total}`;
}

function updateCartUI() {
  const totalCount = cart.reduce((sum, ci) => sum + ci.quantity, 0);

  // Update navbar tray badge
  const trayBadge = document.getElementById("cartCountBadge");
  if (trayBadge) {
    trayBadge.textContent = totalCount;
  }

  const mobileMenuBadge = document.getElementById("mobileMenuTrayBadge");
  if (mobileMenuBadge) {
    mobileMenuBadge.textContent = totalCount;
  }

  const globalCount = document.getElementById("globalCartCount");
  if (globalCount) {
    if (totalCount > 0) {
      globalCount.textContent = totalCount;
      globalCount.classList.remove("hidden");
    } else {
      globalCount.classList.add("hidden");
    }
  }

  // Update floating dock if exists on page
  const floatingDock = document.getElementById("floatingTrayDock");
  const dockCount = document.getElementById("dockItemCount");
  const dockTotal = document.getElementById("dockTotalAmount");
  if (floatingDock && dockCount && dockTotal) {
    if (totalCount > 0) {
      floatingDock.classList.remove("hidden");
      dockCount.textContent = totalCount;
      const approxTotal = cart.reduce((sum, ci) => sum + ((ci.price + (ci.extra_price || 0)) * ci.quantity), 0);
      dockTotal.textContent = `₹${Math.round(approxTotal * 1.05)}`;
    } else {
      floatingDock.classList.add("hidden");
    }
  }
}

function proceedToCheckout() {
  if (cart.length === 0) {
    if (typeof showToast === "function") {
      showToast("Tray Empty", "Please select items before proceeding to checkout.", true);
    }
    return;
  }
  const table = getGlobalTable();
  window.location.href = `/checkout?table=${encodeURIComponent(table)}`;
}

async function syncCartWithServer() {
  try {
    const localItems = getLocalCart();
    const res = await fetch("/api/cart/sync", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ items: localItems })
    });
    const data = await res.json();
    if (data.success && Array.isArray(data.items)) {
      cart = data.items;
      saveCartToStorage();
    }
  } catch (err) {
    console.warn("Cart sync warning:", err);
  }
}

// Make functions explicitly globally accessible on window
window.toggleCartDrawer = toggleCartDrawer;
window.setGlobalTable = setGlobalTable;
window.getGlobalTable = getGlobalTable;
window.addToCart = addToCart;
window.addSimpleItemToCart = addSimpleItemToCart;
window.addItemToCart = addItemToCart;
window.updateCartQuantity = updateCartQuantity;
window.updateCartItemQuantity = updateCartItemQuantity;
window.removeCartItem = removeCartItem;
window.clearCart = clearCart;
window.clearLocalCart = clearLocalCart;
window.getLocalCart = getLocalCart;
window.proceedToCheckout = proceedToCheckout;
window.renderCartDrawer = renderCartDrawer;
window.syncCartWithServer = syncCartWithServer;

// Keyboard shortcuts: ESC to close cart drawer & modals
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    toggleCartDrawer(false);
    const tableModal = document.getElementById("tableModal");
    if (tableModal) tableModal.classList.add("hidden");
  }
});

document.addEventListener("DOMContentLoaded", () => {
  loadCartFromStorage();
  const drawerDisplay = document.getElementById("drawerTableDisplay");
  if (drawerDisplay && activeTable) {
    drawerDisplay.textContent = activeTable === "Takeaway" ? "Takeaway Counter" : `Table ${activeTable}`;
  }
  const navBadge = document.getElementById("activeTableBadge");
  if (navBadge) {
    const current = navBadge.textContent.trim();
    if (!current || current === "Table 04" || current === "● TABLE 04" || !current.includes("●")) {
      navBadge.textContent = activeTable === "Takeaway" ? "● TAKEAWAY" : (activeTable ? `● TABLE ${activeTable}` : "● TABLE —");
    }
  }
});
