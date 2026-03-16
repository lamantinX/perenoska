const state = {
  token: localStorage.getItem("perenositsa.token") || "",
  user: null,
  products: [],
  selectedProducts: new Set(),
  preview: null,
  jobs: [],
  targetCategories: [],
  catalogMessage: "Товары еще не загружены.",
  expandedProductId: null,
  productDetailsCache: {},
  modalProductId: null,
  modalImageIndex: 0,
  previewCardProductId: null,
  previewCardImageIndex: 0,
  productOverrides: {},
  previewLoading: false,
  previewProgressValue: 0,
  previewProgressText: "",
  previewProgressTimer: null,
};

const elements = {
  sessionStatus: document.getElementById("sessionStatus"),
  workspace: document.getElementById("workspace"),
  logoutButton: document.getElementById("logoutButton"),
  toast: document.getElementById("toast"),
  registerForm: document.getElementById("registerForm"),
  loginForm: document.getElementById("loginForm"),
  wbConnectionForm: document.getElementById("wbConnectionForm"),
  ozonConnectionForm: document.getElementById("ozonConnectionForm"),
  wbConnectionBadge: document.getElementById("wbConnectionBadge"),
  ozonConnectionBadge: document.getElementById("ozonConnectionBadge"),
  wbMasked: document.getElementById("wbMasked"),
  ozonMasked: document.getElementById("ozonMasked"),
  refreshConnectionsButton: document.getElementById("refreshConnectionsButton"),
  sourceMarketplace: document.getElementById("sourceMarketplace"),
  targetMarketplace: document.getElementById("targetMarketplace"),
  targetCategorySelect: document.getElementById("targetCategorySelect"),
  loadProductsButton: document.getElementById("loadProductsButton"),
  loadCategoriesButton: document.getElementById("loadCategoriesButton"),
  previewButton: document.getElementById("previewButton"),
  launchButton: document.getElementById("launchButton"),
  previewProgressPanel: document.getElementById("previewProgressPanel"),
  previewProgressFill: document.getElementById("previewProgressFill"),
  previewProgressText: document.getElementById("previewProgressText"),
  previewProgressValue: document.getElementById("previewProgressValue"),
  refreshJobsButton: document.getElementById("refreshJobsButton"),
  productGrid: document.getElementById("productGrid"),
  previewList: document.getElementById("previewList"),
  jobsList: document.getElementById("jobsList"),
  catalogSummary: document.getElementById("catalogSummary"),
  productModal: document.getElementById("productModal"),
  modalBackdrop: document.getElementById("modalBackdrop"),
  closeModalButton: document.getElementById("closeModalButton"),
  modalTitle: document.getElementById("modalTitle"),
  modalContent: document.getElementById("modalContent"),
  previewCardModal: document.getElementById("previewCardModal"),
  previewCardBackdrop: document.getElementById("previewCardBackdrop"),
  closePreviewCardButton: document.getElementById("closePreviewCardButton"),
  previewCardTitle: document.getElementById("previewCardTitle"),
  previewCardContent: document.getElementById("previewCardContent"),
  imageModal: document.getElementById("imageModal"),
  imageModalBackdrop: document.getElementById("imageModalBackdrop"),
  closeImageModalButton: document.getElementById("closeImageModalButton"),
  zoomedImage: document.getElementById("zoomedImage"),
};

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (!headers.has("Content-Type") && options.body) {
    headers.set("Content-Type", "application/json");
  }
  if (state.token) {
    headers.set("Authorization", `Bearer ${state.token}`);
  }

  const response = await fetch(path, { ...options, headers });
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : await response.text();

  if (!response.ok) {
    const detail = typeof payload === "string" ? payload : payload.detail || JSON.stringify(payload);
    throw new Error(detail);
  }
  return payload;
}

function showToast(message, isError = false) {
  elements.toast.textContent = message;
  elements.toast.classList.remove("hidden");
  elements.toast.style.background = isError ? "rgba(119, 32, 18, 0.94)" : "rgba(25, 24, 22, 0.92)";
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => elements.toast.classList.add("hidden"), 3200);
}

function setAuth(authResponse) {
  state.token = authResponse.access_token;
  state.user = authResponse.user;
  localStorage.setItem("perenositsa.token", state.token);
  renderSession();
}

function clearAuth() {
  state.token = "";
  state.user = null;
  state.products = [];
  state.selectedProducts = new Set();
  state.preview = null;
  state.jobs = [];
  state.productOverrides = {};
  localStorage.removeItem("perenositsa.token");
  renderSession();
  renderProducts();
  renderPreview();
  renderJobs();
}

function productOverride(productId, field) {
  return state.productOverrides[productId]?.[field] || "";
}

function renderPreviewProgress() {
  if (!state.previewLoading) {
    elements.previewProgressPanel.classList.add("hidden");
    return;
  }
  elements.previewProgressPanel.classList.remove("hidden");
  elements.previewProgressFill.style.width = `${state.previewProgressValue}%`;
  elements.previewProgressText.textContent = state.previewProgressText || "Подготавливаю preview...";
  elements.previewProgressValue.textContent = `${Math.round(state.previewProgressValue)}%`;
}

function startPreviewProgress() {
  window.clearInterval(state.previewProgressTimer);
  state.previewLoading = true;
  state.previewProgressValue = 8;
  state.previewProgressText = "Собираю данные товара и категории...";
  renderPreviewProgress();
  state.previewProgressTimer = window.setInterval(() => {
    if (state.previewProgressValue < 34) {
      state.previewProgressValue += 6;
      state.previewProgressText = "Проверяю карточки и атрибуты...";
    } else if (state.previewProgressValue < 68) {
      state.previewProgressValue += 4;
      state.previewProgressText = "Строю payload для переноса...";
    } else if (state.previewProgressValue < 86) {
      state.previewProgressValue += 2;
      state.previewProgressText = "Формирую итоговый preview...";
    }
    renderPreviewProgress();
  }, 220);
}

function finishPreviewProgress() {
  window.clearInterval(state.previewProgressTimer);
  state.previewProgressValue = 100;
  state.previewProgressText = "Preview готов.";
  renderPreviewProgress();
  window.setTimeout(() => {
    state.previewLoading = false;
    renderPreviewProgress();
  }, 450);
}

function renderSession() {
  if (state.user) {
    elements.sessionStatus.textContent = `Авторизован: ${state.user.email}`;
    elements.workspace.classList.remove("hidden");
    elements.logoutButton.classList.remove("hidden");
  } else {
    elements.sessionStatus.textContent = "Не авторизован";
    elements.workspace.classList.add("hidden");
    elements.logoutButton.classList.add("hidden");
  }
}

function connectionBadge(connection) {
  if (!connection || !connection.is_configured) {
    return { text: "Не подключен", className: "badge badge-neutral" };
  }
  return { text: "Подключен", className: "badge badge-success" };
}

function renderConnections(connections) {
  const wb = connections.find((item) => item.marketplace === "wb");
  const ozon = connections.find((item) => item.marketplace === "ozon");
  const wbBadge = connectionBadge(wb);
  const ozonBadge = connectionBadge(ozon);

  elements.wbConnectionBadge.textContent = wbBadge.text;
  elements.wbConnectionBadge.className = wbBadge.className;
  elements.ozonConnectionBadge.textContent = ozonBadge.text;
  elements.ozonConnectionBadge.className = ozonBadge.className;
  elements.wbMasked.textContent = "";
  elements.ozonMasked.textContent = "";
}

function renderProducts() {
  if (!state.products.length) {
    elements.productGrid.innerHTML = `<div class="empty-state">${escapeHtml(state.catalogMessage)}</div>`;
    elements.catalogSummary.textContent = state.catalogMessage;
    return;
  }

  elements.catalogSummary.textContent = `Загружено ${state.products.length}. Выбрано ${state.selectedProducts.size}.`;
  elements.productGrid.innerHTML = state.products
    .map((product) => {
      const selected = state.selectedProducts.has(product.id);
      const expanded = state.expandedProductId === product.id;
      const image = product.images?.[0]
        ? `<img class="product-image" src="${product.images[0]}" alt="${escapeHtml(product.title)}" />`
        : '<div class="product-image"></div>';
      return `
        <article class="product-card ${selected ? "selected" : ""} ${expanded ? "expanded" : ""}" data-card-id="${product.id}">
          ${image}
          <label class="product-check">
            <input type="checkbox" ${selected ? "checked" : ""} data-product-id="${product.id}" />
            <span>Выбрать для переноса</span>
          </label>
          <div class="product-actions">
            <button class="ghost-button" type="button" data-toggle-details="${product.id}">
              ${expanded ? "Скрыть детали" : "Показать детали"}
            </button>
            ${expanded ? `<button class="secondary-button" type="button" data-open-modal="${product.id}">Полная карточка</button>` : ""}
          </div>
          <div class="product-title">${escapeHtml(product.title)}</div>
          <div class="meta-grid">
            <div class="meta">ID: ${escapeHtml(product.id)}</div>
            <div class="meta">Артикул: ${escapeHtml(product.offer_id || "—")}</div>
            <div class="meta">Категория: ${escapeHtml(product.category_name || "—")}</div>
            <div class="meta">Цена: ${escapeHtml(productOverride(product.id, "price") || product.price || "—")}</div>
          </div>
          ${
            expanded
              ? `<label class="inline-field">
                  <span>Цена для переноса</span>
                  <input
                    type="text"
                    inputmode="decimal"
                    placeholder="${product.price ? "Цена из WB" : "Введите цену вручную"}"
                    value="${escapeHtml(productOverride(product.id, "price"))}"
                    data-price-override="${product.id}"
                  />
                </label>`
              : ""
          }
        </article>
      `;
    })
    .join("");

  elements.productGrid.querySelectorAll("[data-card-id]").forEach((card) => {
    card.addEventListener("click", (event) => {
      if (event.target.closest("button, input, label")) {
        return;
      }
      const productId = card.dataset.cardId;
      state.expandedProductId = state.expandedProductId === productId ? null : productId;
      renderProducts();
    });
  });

  elements.productGrid.querySelectorAll('input[type="checkbox"]').forEach((checkbox) => {
    checkbox.addEventListener("change", () => {
      const productId = checkbox.dataset.productId;
      if (checkbox.checked) {
        state.selectedProducts.add(productId);
      } else {
        state.selectedProducts.delete(productId);
      }
      renderProducts();
    });
  });

  elements.productGrid.querySelectorAll("[data-toggle-details]").forEach((button) => {
    button.addEventListener("click", () => {
      const productId = button.dataset.toggleDetails;
      state.expandedProductId = state.expandedProductId === productId ? null : productId;
      renderProducts();
    });
  });

  elements.productGrid.querySelectorAll("[data-open-modal]").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        await openProductModal(button.dataset.openModal);
      } catch (error) {
        showToast(error.message, true);
      }
    });
  });

  elements.productGrid.querySelectorAll("[data-price-override]").forEach((input) => {
    input.addEventListener("input", () => {
      const productId = input.dataset.priceOverride;
      const value = input.value.trim();
      state.productOverrides[productId] = { ...(state.productOverrides[productId] || {}) };
      if (value) {
        state.productOverrides[productId].price = value;
      } else {
        delete state.productOverrides[productId].price;
        if (!Object.keys(state.productOverrides[productId]).length) {
          delete state.productOverrides[productId];
        }
      }
    });
  });
}

function renderPreview() {
  if (!state.preview?.items?.length) {
    elements.previewList.innerHTML =
      '<div class="empty-state">Сделайте preview, чтобы увидеть итоговые payload и обязательные поля.</div>';
    return;
  }

  elements.previewList.innerHTML = state.preview.items
    .map((item) => {
      const missing = item.missing_required_attributes || [];
      const missingCritical = item.missing_critical_fields || [];
      const warnings = item.warnings || [];
      const tags = [
        ...missing.map((value) => `<span class="tag danger">${escapeHtml(value)}</span>`),
        ...missingCritical.map((value) => `<span class="tag danger">critical: ${escapeHtml(value)}</span>`),
        ...warnings.map((value) => `<span class="tag warning">${escapeHtml(value)}</span>`),
      ].join("");

      return `
        <article class="preview-card">
          <div class="meta-line">
            <div>
              <div class="preview-title">${escapeHtml(item.title)}</div>
              <div class="meta">Источник: ${escapeHtml(String(item.source_category_id || "—"))}</div>
              <div class="meta">Цель: ${escapeHtml(item.target_category_name || "Не выбрана")}</div>
            </div>
            <div class="inline-actions">
              <span class="badge ${missing.length || missingCritical.length ? "badge-danger" : "badge-success"}">
                ${missing.length || missingCritical.length ? "Нужна корректировка" : "Готов к импорту"}
              </span>
              <button class="ghost-button" type="button" data-open-preview-card="${item.product_id}">Показать карточку</button>
            </div>
          </div>
          ${tags ? `<div class="tag-list">${tags}</div>` : ""}
          <pre>${escapeHtml(JSON.stringify(item.payload, null, 2))}</pre>
        </article>
      `;
    })
    .join("");

  elements.previewList.querySelectorAll("[data-open-preview-card]").forEach((button) => {
    button.addEventListener("click", () => openPreviewCardModal(button.dataset.openPreviewCard));
  });
}

function previewItemByProductId(productId) {
  return state.preview?.items?.find((item) => item.product_id === productId) || null;
}

function payloadFieldValue(payload, label) {
  const attributes = payload.attributes || [];
  const attribute = attributes.find((item) => String(item.name || "").toLowerCase() === label.toLowerCase());
  return attribute ? (attribute.value || []).join(", ") : "";
}

function previewMainFields(item) {
  const payload = item.payload || {};
  if (state.preview?.target_marketplace === "ozon") {
    return [
      ["Название", payload.name || item.title || "—"],
      ["Артикул", payload.offer_id || "—"],
      ["Категория", item.target_category_name || "—"],
      ["Цена", payload.price || "—"],
      ["Остаток", payload.stock ?? "—"],
      ["Бренд", payloadFieldValue(payload, "Бренд") || "—"],
      ["Штрихкод", payload.barcode || "—"],
      ["Габариты", `${payload.width || "—"} × ${payload.height || "—"} × ${payload.depth || "—"} мм`],
      ["Вес", payload.weight ? `${payload.weight} г` : "—"],
    ];
  }
  const variant = (payload.variants || [])[0] || {};
  const size = (variant.sizes || [])[0] || {};
  return [
    ["Название", variant.title || item.title || "—"],
    ["Артикул", variant.vendorCode || "—"],
    ["Категория", item.target_category_name || "—"],
    ["Цена", size.price || "—"],
    ["Бренд", variant.brand || "—"],
    ["SKU", (size.skus || []).join(", ") || "—"],
  ];
}

function renderPreviewCardModal(item) {
  const payload = item.payload || {};
  const images = payload.images || [];
  const selectedImage = images[state.previewCardImageIndex] || images[0] || "";
  const mainFields = previewMainFields(item);
  const attributes = payload.attributes || [];
  const missing = [...(item.missing_required_attributes || []), ...(item.missing_critical_fields || []).map((value) => `critical: ${value}`)];
  const mappedEntries = Object.entries(item.mapped_attributes || {}).map(([key, values]) => [
    key,
    Array.isArray(values) ? values.map((value) => value.value || value).join(", ") : String(values),
  ]);
  const chips = [
    payload.offer_id || ((payload.variants || [])[0] || {}).vendorCode || "",
    item.target_category_name || "",
    payload.price ? `${payload.price} ₽` : "",
  ].filter(Boolean);

  elements.previewCardTitle.textContent = state.preview?.target_marketplace === "ozon" ? "Карточка Ozon после переноса" : "Карточка WB после переноса";
  elements.previewCardContent.innerHTML = `
    <div class="preview-card-layout">
      <section class="preview-showcase">
        <div class="preview-showcase-card">
          <div class="preview-image-frame">
            ${
              selectedImage
                ? `<img class="preview-hero-image" src="${selectedImage}" alt="${escapeHtml(item.title)}" data-zoom-image="${escapeHtml(selectedImage)}" />`
                : '<div class="empty-state">Изображения не подтянулись в payload.</div>'
            }
            ${
              images.length
                ? `<div class="thumbnail-row">
                    ${images
                      .map(
                        (image, index) => `
                          <button class="thumbnail-button ${index === state.previewCardImageIndex ? "active" : ""}" type="button" data-preview-image="${index}">
                            <img class="thumbnail-image" src="${image}" alt="Фото ${index + 1}" />
                          </button>
                        `,
                      )
                      .join("")}
                  </div>`
                : ""
            }
          </div>
        </div>
        <div class="preview-showcase-card">
          <div class="preview-chip-row">
            ${chips.map((chip) => `<span class="preview-chip">${escapeHtml(chip)}</span>`).join("")}
          </div>
          <h3 class="preview-title">${escapeHtml(payload.name || ((payload.variants || [])[0] || {}).title || item.title)}</h3>
          <div class="preview-price">${escapeHtml(payload.price ? `${payload.price} ₽` : "Цена не определена")}</div>
          <div class="preview-description">${escapeHtml(payload.description || ((payload.variants || [])[0] || {}).description || "Описание не заполнено.")}</div>
        </div>
      </section>

      <div class="preview-columns">
        <section class="detail-card">
          <h3 class="preview-section-title">Какие поля подтянулись</h3>
          ${renderDetailList(mainFields)}
        </section>
        <section class="detail-card">
          <h3 class="preview-section-title">Проблемные поля</h3>
          ${
            missing.length
              ? `<div class="tag-list">${missing.map((value) => `<span class="tag danger">${escapeHtml(value)}</span>`).join("")}</div>`
              : '<div class="empty-state">Все обязательные поля для этого preview заполнены.</div>'
          }
        </section>
      </div>

      <div class="preview-columns">
        <section class="detail-card">
          <h3 class="preview-section-title">Подтянутые атрибуты</h3>
          ${
            mappedEntries.length
              ? `<div class="preview-attribute-list">
                  ${mappedEntries
                    .map(
                      ([label, value]) => `
                        <div class="preview-attribute-item">
                          <div class="meta">${escapeHtml(label)}</div>
                          <div class="detail-value">${escapeHtml(value || "—")}</div>
                        </div>
                      `,
                    )
                    .join("")}
                </div>`
              : '<div class="empty-state">Атрибуты в preview не были сматчены автоматически.</div>'
          }
        </section>
        <section class="detail-card">
          <h3 class="preview-section-title">Payload для переноса</h3>
          <pre class="json-block">${escapeHtml(JSON.stringify(payload, null, 2))}</pre>
        </section>
      </div>
    </div>
  `;

  elements.previewCardContent.querySelectorAll("[data-preview-image]").forEach((button) => {
    button.addEventListener("click", () => {
      state.previewCardImageIndex = Number(button.dataset.previewImage);
      renderPreviewCardModal(item);
    });
  });

  elements.previewCardContent.querySelectorAll("[data-zoom-image]").forEach((node) => {
    node.addEventListener("click", () => openImageModal(node.dataset.zoomImage));
  });
}

function openPreviewCardModal(productId) {
  const item = previewItemByProductId(productId);
  if (!item) {
    showToast("Preview для выбранного товара не найден.", true);
    return;
  }
  state.previewCardProductId = productId;
  state.previewCardImageIndex = 0;
  elements.previewCardModal.classList.remove("hidden");
  renderPreviewCardModal(item);
}

function closePreviewCardModal() {
  elements.previewCardModal.classList.add("hidden");
}

function statusBadge(status) {
  const value = String(status || "").toLowerCase();
  if (value === "completed") return "badge badge-success";
  if (value === "failed") return "badge badge-danger";
  if (["processing", "submitted", "pending"].includes(value)) return "badge badge-warning";
  return "badge badge-neutral";
}

function renderJobs() {
  if (!state.jobs.length) {
    elements.jobsList.innerHTML = '<div class="empty-state">Задач пока нет.</div>';
    return;
  }

  elements.jobsList.innerHTML = state.jobs
    .map(
      (job) => `
        <article class="job-card">
          <div class="job-meta">
            <div>
              <div class="job-title">Задача #${job.id}</div>
              <div class="meta">${escapeHtml(job.source_marketplace)} → ${escapeHtml(job.target_marketplace)}</div>
              <div class="meta">Создана: ${escapeHtml(job.created_at)}</div>
            </div>
            <div class="inline-actions">
              <span class="${statusBadge(job.status)}">${escapeHtml(job.status)}</span>
              <button class="ghost-button" type="button" data-sync-job="${job.id}">Синхронизировать</button>
            </div>
          </div>
          <pre>${escapeHtml(JSON.stringify(job.result || {}, null, 2))}</pre>
        </article>
      `,
    )
    .join("");

  elements.jobsList.querySelectorAll("[data-sync-job]").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        await syncJob(button.dataset.syncJob);
      } catch (error) {
        showToast(error.message, true);
      }
    });
  });
}

function renderCategories() {
  const options = ['<option value="">Автовыбор</option>']
    .concat(
      state.targetCategories.map(
        (category) => `<option value="${category.id}">${escapeHtml(category.name)} · ${category.id}</option>`,
      ),
    )
    .join("");
  elements.targetCategorySelect.innerHTML = options;
}

function selectedProductIds() {
  return Array.from(state.selectedProducts);
}

function currentTransferPayload() {
  const targetCategoryId = elements.targetCategorySelect.value ? Number(elements.targetCategorySelect.value) : null;
  return {
    source_marketplace: elements.sourceMarketplace.value,
    target_marketplace: elements.targetMarketplace.value,
    product_ids: selectedProductIds(),
    target_category_id: targetCategoryId,
    product_overrides: state.productOverrides,
  };
}

async function loadProfile() {
  if (!state.token) {
    renderSession();
    return;
  }
  try {
    state.user = await api("/api/v1/auth/me");
    renderSession();
    await Promise.all([refreshConnections(), refreshJobs()]);
  } catch {
    clearAuth();
  }
}

async function refreshConnections() {
  const connections = await api("/api/v1/connections");
  renderConnections(connections);
}

async function refreshJobs() {
  state.jobs = await api("/api/v1/transfers");
  renderJobs();
}

async function loadProducts() {
  const marketplace = elements.sourceMarketplace.value;
  state.catalogMessage = "Загружаю товары из выбранного источника...";
  renderProducts();
  state.products = await api(`/api/v1/catalog/products?marketplace=${marketplace}`);
  state.selectedProducts = new Set();
  state.preview = null;
  state.expandedProductId = null;
  state.productDetailsCache = {};
  state.productOverrides = {};
  state.catalogMessage = state.products.length
    ? `Найдено товаров: ${state.products.length}.`
    : "API вернул 0 товаров. Проверьте, что в кабинете есть карточки и у токена есть нужные права.";
  renderProducts();
  renderPreview();
}

async function loadProductDetails(productId) {
  if (state.productDetailsCache[productId]) {
    return state.productDetailsCache[productId];
  }
  const marketplace = elements.sourceMarketplace.value;
  const details = await api(`/api/v1/catalog/products/${encodeURIComponent(productId)}?marketplace=${marketplace}`);
  state.productDetailsCache[productId] = details;
  return details;
}

function renderDetailList(entries) {
  if (!entries.length) {
    return '<div class="empty-state">Нет данных.</div>';
  }
  return `
    <div class="detail-list">
      ${entries
        .map(
          ([label, value]) => `
            <div class="detail-item">
              <div class="meta">${escapeHtml(label)}</div>
              <div class="detail-value">${escapeHtml(value)}</div>
            </div>
          `,
        )
        .join("")}
    </div>
  `;
}

function detailValueOrFallback(details, field, fallback) {
  const value = details[field];
  if (value !== null && value !== undefined && value !== "") {
    return String(value);
  }
  return fallback;
}

function renderToggleSection(title, body, open = false) {
  return `
    <details class="detail-card detail-toggle" ${open ? "open" : ""}>
      <summary>${escapeHtml(title)}</summary>
      <div class="detail-toggle-body">${body}</div>
    </details>
  `;
}

async function openProductModal(productId) {
  state.modalProductId = productId;
  state.modalImageIndex = 0;
  elements.modalTitle.textContent = "Загрузка карточки...";
  elements.modalContent.innerHTML = '<div class="empty-state">Загружаю полную карточку товара...</div>';
  elements.productModal.classList.remove("hidden");
  const details = await loadProductDetails(productId);
  renderProductModal(details);
}

function renderProductModal(details) {
  elements.modalTitle.textContent = details.title || `Товар ${details.id || ""}`;
  const sourceMarketplace = elements.sourceMarketplace.value;
  const priceFallback =
    sourceMarketplace === "wb"
      ? "Не найдено ни в seller API, ни в public WB detail"
      : "Не найдено в ответе API";
  const brandFallback =
    sourceMarketplace === "wb"
      ? "Не указан в карточке WB"
      : "Не найдено в ответе API";

  const mainEntries = [
    ["ID", details.id || "—"],
    ["Артикул", detailValueOrFallback(details, "offer_id", "Не найден в ответе API")],
    ["Категория", details.category_name || details.category_id || "—"],
    ["Цена", detailValueOrFallback(details, "price", priceFallback)],
    ["Бренд", detailValueOrFallback(details, "brand", brandFallback)],
    ["Поставщик", detailValueOrFallback(details, "supplier", "Не найден в ответе API")],
    ["ID поставщика", detailValueOrFallback(details, "supplier_id", "Не найден в ответе API")],
    ["Штрихкоды", details.barcode_list?.length ? details.barcode_list.join(", ") : "Не найдено в ответе API"],
    ["Количество фото", String((details.images || []).length)],
    ["Остаток", details.stock ?? "Не найдено в ответе API"],
  ];

  const attributeEntries = Object.entries(details.attributes || {}).map(([key, value]) => [
    key,
    Array.isArray(value) ? value.join(", ") : JSON.stringify(value),
  ]);

  const sizeEntries = (details.sizes || []).map((item, index) => [
    `Размер ${index + 1}`,
    JSON.stringify(item),
  ]);

  const dimensionEntries = Object.entries(details.dimensions || {}).map(([key, value]) => [key, String(value)]);
  const sellerEntries = Object.entries(details.seller_info || {}).map(([key, value]) => [key, String(value)]);
  const groupedSections = (details.grouped_attributes || [])
    .map((group) =>
      renderToggleSection(
        group.group_name || "Группа характеристик",
        renderDetailList(
          (group.options || []).map((option) => [option.name || "Поле", option.value || option.variable_values?.join(", ") || "—"]),
        ),
        false,
      ),
    )
    .join("");

  const images = details.images || [];
  const selectedImage = images[state.modalImageIndex] || images[0] || "";
  const galleryBlock = images.length
    ? `
      <section class="detail-card gallery-card">
        <div class="panel-head">
          <div>
            <p class="panel-kicker">Галерея</p>
            <h3>Изображения товара</h3>
          </div>
          <button class="ghost-button" type="button" data-zoom-image="${escapeHtml(selectedImage)}">Увеличить</button>
        </div>
        <img class="modal-hero-image" src="${selectedImage}" alt="${escapeHtml(details.title || "Товар")}" data-zoom-image="${escapeHtml(selectedImage)}" />
        <div class="thumbnail-row">
          ${images
            .map(
              (image, index) => `
                <button class="thumbnail-button ${index === state.modalImageIndex ? "active" : ""}" type="button" data-select-image="${index}">
                  <img class="thumbnail-image" src="${image}" alt="Фото ${index + 1}" />
                </button>
              `,
            )
            .join("")}
        </div>
      </section>
    `
    : '<div class="empty-state">Изображения в ответе API не найдены.</div>';

  const descriptionBlock = details.description
    ? `<div class="detail-value">${escapeHtml(details.description)}</div>`
    : '<div class="empty-state">Описание в ответе API не найдено.</div>';

  elements.modalContent.innerHTML = `
    ${galleryBlock}
    <div class="detail-grid">
      <section class="detail-card">
        <h3>Важные поля для переноса</h3>
        ${renderDetailList(mainEntries)}
      </section>
      ${renderToggleSection("Информация о продавце", renderDetailList(sellerEntries), false)}
      ${renderToggleSection("Все атрибуты", renderDetailList(attributeEntries), false)}
      ${renderToggleSection("Описание", descriptionBlock, false)}
      ${renderToggleSection("Размеры и SKU", renderDetailList(sizeEntries), false)}
      ${renderToggleSection("Габариты", renderDetailList(dimensionEntries), false)}
    </div>
    ${groupedSections}
    ${renderToggleSection(
      "Сырой JSON карточки",
      `<pre class="json-block">${escapeHtml(JSON.stringify(details.raw_sources || details, null, 2))}</pre>`,
      false,
    )}
  `;

  elements.modalContent.querySelectorAll("[data-select-image]").forEach((button) => {
    button.addEventListener("click", () => {
      state.modalImageIndex = Number(button.dataset.selectImage);
      renderProductModal(details);
    });
  });

  elements.modalContent.querySelectorAll("[data-zoom-image]").forEach((node) => {
    node.addEventListener("click", () => openImageModal(node.dataset.zoomImage));
  });
}

function closeProductModal() {
  elements.productModal.classList.add("hidden");
}

function openImageModal(imageUrl) {
  elements.zoomedImage.src = imageUrl;
  elements.imageModal.classList.remove("hidden");
}

function closeImageModal() {
  elements.imageModal.classList.add("hidden");
  elements.zoomedImage.src = "";
}

async function loadTargetCategories() {
  const marketplace = elements.targetMarketplace.value;
  state.targetCategories = await api(`/api/v1/catalog/categories?marketplace=${marketplace}`);
  renderCategories();
}

async function makePreview() {
  const payload = currentTransferPayload();
  if (!payload.product_ids.length) {
    throw new Error("Выберите хотя бы один товар.");
  }
  startPreviewProgress();
  try {
    state.preview = await api("/api/v1/transfers/preview", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    renderPreview();
    showToast(state.preview.ready_to_import ? "Preview готов." : "Preview показал, что есть незаполненные поля.");
  } finally {
    finishPreviewProgress();
  }
}

async function launchTransfer() {
  const payload = currentTransferPayload();
  if (!payload.product_ids.length) {
    throw new Error("Выберите хотя бы один товар.");
  }
  const job = await api("/api/v1/transfers", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  showToast(`Задача #${job.id} создана.`);
  await refreshJobs();
}

async function syncJob(jobId) {
  await api(`/api/v1/transfers/${jobId}/sync`, { method: "POST" });
  await refreshJobs();
  showToast(`Задача #${jobId} обновлена.`);
}

function syncMarketplaceSelectors(changed = "source") {
  if (elements.sourceMarketplace.value !== elements.targetMarketplace.value) return;
  if (changed === "source") {
    elements.targetMarketplace.value = elements.sourceMarketplace.value === "wb" ? "ozon" : "wb";
  } else {
    elements.sourceMarketplace.value = elements.targetMarketplace.value === "wb" ? "ozon" : "wb";
  }
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

elements.registerForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formElement = elements.registerForm;
  const form = new FormData(formElement);
  try {
    const authResponse = await api("/api/v1/auth/register", {
      method: "POST",
      body: JSON.stringify(Object.fromEntries(form.entries())),
    });
    setAuth(authResponse);
    await Promise.all([refreshConnections(), refreshJobs()]);
    showToast("Аккаунт создан.");
  } catch (error) {
    showToast(error.message, true);
  }
});

elements.loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formElement = event.currentTarget;
  const form = new FormData(formElement);
  try {
    const authResponse = await api("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify(Object.fromEntries(form.entries())),
    });
    setAuth(authResponse);
    await Promise.all([refreshConnections(), refreshJobs()]);
    showToast("Вход выполнен.");
  } catch (error) {
    showToast(error.message, true);
  }
});

elements.wbConnectionForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formElement = elements.wbConnectionForm;
  const form = new FormData(formElement);
  try {
    await api("/api/v1/connections/wb", {
      method: "PUT",
      body: JSON.stringify({ marketplace: "wb", token: form.get("token") }),
    });
    await refreshConnections();
    formElement?.reset?.();
    showToast("WB подключение сохранено.");
  } catch (error) {
    showToast(error.message, true);
  }
});

elements.ozonConnectionForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formElement = elements.ozonConnectionForm;
  const form = new FormData(formElement);
  try {
    await api("/api/v1/connections/ozon", {
      method: "PUT",
      body: JSON.stringify({
        marketplace: "ozon",
        client_id: form.get("client_id"),
        api_key: form.get("api_key"),
      }),
    });
    await refreshConnections();
    formElement?.reset?.();
    showToast("Ozon подключение сохранено.");
  } catch (error) {
    showToast(error.message, true);
  }
});

elements.refreshConnectionsButton.addEventListener("click", async () => {
  try {
    await refreshConnections();
    showToast("Подключения обновлены.");
  } catch (error) {
    showToast(error.message, true);
  }
});

elements.refreshJobsButton.addEventListener("click", async () => {
  try {
    await refreshJobs();
    showToast("Список задач обновлен.");
  } catch (error) {
    showToast(error.message, true);
  }
});

elements.loadProductsButton.addEventListener("click", async () => {
  try {
    syncMarketplaceSelectors("source");
    await loadProducts();
    showToast(
      state.products.length
        ? `Каталог загружен: ${state.products.length} товар(ов).`
        : "Товары не найдены. Нужна проверка прав токена или структуры ответа API.",
      state.products.length === 0,
    );
  } catch (error) {
    showToast(error.message, true);
  }
});

elements.loadCategoriesButton.addEventListener("click", async () => {
  try {
    syncMarketplaceSelectors("target");
    await loadTargetCategories();
    showToast("Категории загружены.");
  } catch (error) {
    showToast(error.message, true);
  }
});

elements.previewButton.addEventListener("click", async () => {
  try {
    syncMarketplaceSelectors("target");
    await makePreview();
  } catch (error) {
    showToast(error.message, true);
  }
});

elements.launchButton.addEventListener("click", async () => {
  try {
    syncMarketplaceSelectors("target");
    await launchTransfer();
  } catch (error) {
    showToast(error.message, true);
  }
});

elements.sourceMarketplace.addEventListener("change", () => syncMarketplaceSelectors("source"));
elements.targetMarketplace.addEventListener("change", () => syncMarketplaceSelectors("target"));
elements.logoutButton.addEventListener("click", () => {
  clearAuth();
  showToast("Сессия завершена.");
});
elements.closeModalButton.addEventListener("click", closeProductModal);
elements.modalBackdrop.addEventListener("click", closeProductModal);
elements.closePreviewCardButton.addEventListener("click", closePreviewCardModal);
elements.previewCardBackdrop.addEventListener("click", closePreviewCardModal);
elements.closeImageModalButton.addEventListener("click", closeImageModal);
elements.imageModalBackdrop.addEventListener("click", closeImageModal);

renderSession();
renderProducts();
renderPreview();
renderJobs();
renderCategories();
renderPreviewProgress();
loadProfile();
