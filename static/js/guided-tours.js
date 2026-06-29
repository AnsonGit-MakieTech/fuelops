(function () {
  "use strict";

  const tours = {
    dashboard: [
      {
        target: "dashboard-actions",
        title: "Start the daily workflow",
        description: "Create today's sale record here, or open reports when you need a financial review.",
      },
      {
        target: "dashboard-metrics",
        title: "Read today's position",
        description: "Track expected sales, liters sold, cash variance, and month-to-date net profit.",
      },
      {
        target: "dashboard-alerts",
        title: "Resolve operational alerts",
        description: "Low stock, cash shortages, and missing daily operations appear here for action.",
      },
      {
        target: "dashboard-inventory",
        title: "Monitor fuel inventory",
        description: "Review tank balances and use Refill before a product reaches its low-stock level.",
      },
      {
        target: "dashboard-recent-sales",
        title: "Open recent operations",
        description: "Review current totals and status, then open a daily sale to continue encoding or approval.",
      },
    ],
    "daily-sales-list": [
      {
        target: "daily-sales-create",
        title: "Create a daily sale",
        description: "Start one operation record for the station and business date before encoding readings.",
      },
      {
        target: "daily-sales-history",
        title: "Review operation history",
        description: "Compare liters, expected sales, collections, variance, and status. Open a row to continue work.",
      },
    ],
    "daily-sale-create": [
      {
        target: "daily-sale-fields",
        title: "Choose the station and date",
        description: "Confirm the correct station and business date. Duplicate operations for the same date are blocked.",
      },
      {
        target: "daily-sale-submit",
        title: "Create the operation",
        description: "Create opens the encoding workspace. A confirmation appears before the record is saved.",
      },
    ],
    "daily-operation": [
      {
        target: "operation-summary",
        title: "Watch calculated totals",
        description: "Liters, expected sales, collections, and cash variance update from the records below.",
      },
      {
        target: "operation-reading-form",
        title: "Add pump readings",
        description: "Select a pump and enter opening and closing meters. Fuel volume and expected sales calculate automatically.",
      },
      {
        target: "operation-readings",
        title: "Verify encoded readings",
        description: "Check every pump's meter values, liters, price, and expected sales before submission.",
      },
      {
        target: "operation-collection",
        title: "Record collections",
        description: "Enter cash and non-cash payments. FuelOps compares the collection with expected sales to show variance.",
      },
      {
        target: "operation-review-actions",
        title: "Complete the review flow",
        description: "Submit sends the operation for review. Authorized users can approve and deduct inventory, or reject it for correction.",
      },
    ],
    "fuel-refills-list": [
      {
        target: "fuel-refill-create",
        title: "Record a fuel refill",
        description: "Add each supplier delivery when it is received so the selected tank balance stays accurate.",
      },
      {
        target: "fuel-refill-history",
        title: "Audit delivery history",
        description: "Use supplier, invoice, volume, and cost details to verify inventory purchases.",
      },
    ],
    "fuel-refill-create": [
      {
        target: "fuel-refill-fields",
        title: "Enter delivery details",
        description: "Match the station, product, and tank, then record supplier, delivered liters, unit cost, and invoice.",
      },
      {
        target: "fuel-refill-submit",
        title: "Update inventory",
        description: "Saving creates the delivery and increases tank stock. Confirm the quantity before continuing.",
      },
    ],
    "expenses-list": [
      {
        target: "expense-create",
        title: "Record an operating expense",
        description: "Add costs promptly so profitability reports reflect the station's actual spending.",
      },
      {
        target: "expense-history",
        title: "Review expense history",
        description: "Use category, vendor, reference, and payer details to audit recorded costs.",
      },
    ],
    "expense-create": [
      {
        target: "expense-fields",
        title: "Enter the expense",
        description: "Choose the station and category, then record date, amount, vendor, reference, payer, and notes.",
      },
      {
        target: "expense-submit",
        title: "Apply the cost to reports",
        description: "Saving includes this expense in the selected station's monthly profitability calculation.",
      },
    ],
    "station-setup": [
      {
        target: "station-setup-fields",
        title: "Configure the first fuel line",
        description: "Enter one product, its prices, tank capacity and stock, pump meter, and supplier. More equipment can be added later.",
      },
      {
        target: "station-setup-submit",
        title: "Activate daily operations",
        description: "Complete setup to make pump readings, refills, expenses, and reports available for this station.",
      },
    ],
    "station-settings": [
      {
        target: "settings-products",
        title: "Manage fuel products",
        description: "Add every fuel grade sold by the station and maintain its current selling price and cost basis.",
      },
      {
        target: "settings-tanks",
        title: "Configure storage tanks",
        description: "Connect each tank to a product and maintain capacity, current stock, and reorder level.",
      },
      {
        target: "settings-pumps",
        title: "Connect pumps and meters",
        description: "Assign each pump to the matching product and tank before recording daily readings.",
      },
    ],
    inventory: [
      {
        target: "inventory-tanks",
        title: "Monitor tank balances",
        description: "Review current volume, capacity, reorder level, and low-stock status for every fuel product.",
      },
      {
        target: "inventory-adjustments",
        title: "Control stock corrections",
        description: "Adjustment requests remain pending until an owner or manager approves the inventory change.",
      },
      {
        target: "inventory-deliveries",
        title: "Review incoming fuel",
        description: "Recent supplier deliveries show the product, tank, delivered liters, and acquisition cost.",
      },
    ],
    "inventory-adjustment": [
      {
        target: "adjustment-fields",
        title: "Describe the stock change",
        description: "Choose a tank, adjustment type, liters, and a specific operational reason for the request.",
      },
      {
        target: "adjustment-submit",
        title: "Submit for approval",
        description: "Submitting records the request without changing inventory until an authorized reviewer approves it.",
      },
    ],
    reports: [
      {
        target: "reports-filters",
        title: "Choose the reporting period",
        description: "Select a station, a daily date, and a monthly period, then apply the filters.",
      },
      {
        target: "reports-summary",
        title: "Read monthly performance",
        description: "Compare volume, gross sales, gross profit, and net profit for the selected month.",
      },
      {
        target: "reports-daily",
        title: "Inspect daily results",
        description: "Review sales, collection variance, and workflow status for the selected business date.",
      },
      {
        target: "reports-variance",
        title: "Monitor cash variance",
        description: "Monthly shortage and overage totals highlight collection controls that need attention.",
      },
      {
        target: "reports-expenses",
        title: "Analyze expense categories",
        description: "See which operating cost categories are reducing net profit in the selected month.",
      },
    ],
  };

  const body = document.body;
  const guideKey = body.dataset.guideKey;
  const layer = document.querySelector("[data-guide-layer]");
  const dialog = document.querySelector("[data-guide-dialog]");
  const spotlight = document.querySelector("[data-guide-spotlight]");
  const title = document.querySelector("[data-guide-title]");
  const description = document.querySelector("[data-guide-description]");
  const counter = document.querySelector("[data-guide-counter]");
  const previous = document.querySelector("[data-guide-previous]");
  const next = document.querySelector("[data-guide-next]");
  const dismiss = document.querySelector("[data-guide-dismiss]");

  if (!guideKey || !layer || !dialog || !spotlight || !tours[guideKey]) return;

  let availableSteps = [];
  let currentIndex = 0;
  let activeTarget = null;
  let previouslyFocused = null;

  function isVisible(element) {
    if (!element) return false;
    const style = window.getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
  }

  function findTarget(targetName) {
    const matches = document.querySelectorAll(`[data-guide-target="${targetName}"]`);
    return Array.from(matches).find(isVisible) || null;
  }

  function resolveSteps() {
    return tours[guideKey]
      .map((step) => ({ ...step, element: findTarget(step.target) }))
      .filter((step) => step.element);
  }

  function csrfToken() {
    const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    if (input) return input.value;

    const cookie = document.cookie
      .split(";")
      .map((item) => item.trim())
      .find((item) => item.startsWith("csrftoken="));
    return cookie ? decodeURIComponent(cookie.split("=").slice(1).join("=")) : "";
  }

  function saveProgress(status) {
    const progressUrl = body.dataset.guideProgressUrl;
    if (!progressUrl) return;

    window.fetch(progressUrl, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken(),
      },
      body: JSON.stringify({
        guide_key: guideKey,
        version: Number(body.dataset.guideVersion),
        status,
      }),
    }).catch(() => {});
  }

  function placeGuide() {
    if (!activeTarget || layer.hidden) return;

    const padding = 6;
    const margin = 12;
    const gap = 16;
    const targetRect = activeTarget.getBoundingClientRect();

    spotlight.style.top = `${Math.max(4, targetRect.top - padding)}px`;
    spotlight.style.left = `${Math.max(4, targetRect.left - padding)}px`;
    spotlight.style.width = `${Math.min(window.innerWidth - 8, targetRect.width + padding * 2)}px`;
    spotlight.style.height = `${Math.min(window.innerHeight - 8, targetRect.height + padding * 2)}px`;

    if (window.innerWidth <= 820) {
      dialog.style.removeProperty("top");
      dialog.style.removeProperty("left");
      return;
    }

    const dialogRect = dialog.getBoundingClientRect();
    let left;
    let top;

    if (targetRect.right + gap + dialogRect.width <= window.innerWidth - margin) {
      left = targetRect.right + gap;
      top = targetRect.top;
    } else if (targetRect.left - gap - dialogRect.width >= margin) {
      left = targetRect.left - gap - dialogRect.width;
      top = targetRect.top;
    } else if (targetRect.bottom + gap + dialogRect.height <= window.innerHeight - margin) {
      left = targetRect.left;
      top = targetRect.bottom + gap;
    } else {
      left = targetRect.left;
      top = targetRect.top - gap - dialogRect.height;
    }

    dialog.style.left = `${Math.min(Math.max(margin, left), window.innerWidth - dialogRect.width - margin)}px`;
    dialog.style.top = `${Math.min(Math.max(margin, top), window.innerHeight - dialogRect.height - margin)}px`;
  }

  function renderStep() {
    const step = availableSteps[currentIndex];
    if (!step) return;

    activeTarget = step.element;
    title.textContent = step.title;
    description.textContent = step.description;
    counter.textContent = `Step ${currentIndex + 1} of ${availableSteps.length}`;
    previous.hidden = currentIndex === 0;
    next.innerHTML = currentIndex === availableSteps.length - 1
      ? 'Finish <i data-lucide="check"></i>'
      : 'Next <i data-lucide="arrow-right"></i>';

    const rect = activeTarget.getBoundingClientRect();
    const isOutsideViewport = rect.top < 76 || rect.bottom > window.innerHeight - 100;
    if (isOutsideViewport) {
      activeTarget.scrollIntoView({
        behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
        block: "center",
      });
    }

    if (window.lucide) {
      window.lucide.createIcons({ attrs: { width: 18, height: 18, strokeWidth: 2 } });
    }

    window.setTimeout(placeGuide, isOutsideViewport ? 260 : 0);
    dialog.focus({ preventScroll: true });
  }

  function startGuide() {
    availableSteps = resolveSteps();
    if (!availableSteps.length) return;

    currentIndex = 0;
    previouslyFocused = document.activeElement;
    layer.hidden = false;
    body.classList.add("is-guided-tour-open");
    renderStep();
  }

  function closeGuide(status) {
    layer.hidden = true;
    body.classList.remove("is-guided-tour-open");
    activeTarget = null;
    saveProgress(status);
    if (previouslyFocused && typeof previouslyFocused.focus === "function") {
      previouslyFocused.focus();
    }
  }

  previous.addEventListener("click", () => {
    if (currentIndex > 0) {
      currentIndex -= 1;
      renderStep();
    }
  });

  next.addEventListener("click", () => {
    if (currentIndex < availableSteps.length - 1) {
      currentIndex += 1;
      renderStep();
    } else {
      closeGuide("completed");
    }
  });

  dismiss.addEventListener("click", () => closeGuide("dismissed"));

  document.querySelectorAll("[data-guide-replay]").forEach((button) => {
    button.addEventListener("click", startGuide);
  });

  document.addEventListener("keydown", (event) => {
    if (layer.hidden) return;

    if (event.key === "Escape") {
      event.preventDefault();
      closeGuide("dismissed");
      return;
    }

    if (event.key === "Tab") {
      const focusable = Array.from(dialog.querySelectorAll("button:not([hidden])"));
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
  });

  window.addEventListener("resize", placeGuide);
  window.addEventListener("scroll", placeGuide, true);

  if (body.dataset.guideHasSeen !== "true") {
    window.setTimeout(startGuide, 450);
  }
})();
