/* Global client-side behaviour: toasts, HTMX error handling, charts. */
(function () {
  "use strict";

  // ---- Toast store (Alpine) -------------------------------------------------
  document.addEventListener("alpine:init", () => {
    Alpine.store("toasts", {
      items: [],
      nextId: 1,
      push({ message, type = "success", timeout = 4000 }) {
        const id = this.nextId++;
        this.items.push({ id, message, type });
        if (timeout) setTimeout(() => this.dismiss(id), timeout);
      },
      dismiss(id) {
        this.items = this.items.filter((t) => t.id !== id);
      },
    });
  });

  const toast = (message, type = "error") =>
    window.dispatchEvent(new CustomEvent("toast", { detail: { message, type } }));

  window.addEventListener("toast", (e) => {
    if (window.Alpine) Alpine.store("toasts").push(e.detail);
  });

  // ---- HTMX error handling --------------------------------------------------
  document.addEventListener("htmx:responseError", (e) => {
    const status = e.detail.xhr.status;
    const msg =
      status === 403 ? "Your session may have expired. Please refresh the page." :
      status === 404 ? "That item no longer exists." :
      status >= 500 ? "Something went wrong on our side. Please try again." :
      `Request failed (${status}).`;
    toast(msg, "error");
  });
  document.addEventListener("htmx:sendError", () => toast("Network error — check your connection.", "error"));
  document.addEventListener("htmx:timeout", () => toast("The request timed out. Please try again.", "error"));

  // Server login redirects during an HTMX request: do a full page navigation instead.
  document.addEventListener("htmx:beforeSwap", (e) => {
    const url = e.detail.xhr.responseURL || "";
    if (url.includes("/accounts/login/")) {
      e.detail.shouldSwap = false;
      window.location.href = url;
    }
  });

  // ---- Charts ---------------------------------------------------------------
  const charts = [];

  function money(value, currency) {
    try {
      return new Intl.NumberFormat(undefined, { style: "currency", currency }).format(value);
    } catch {
      return value.toFixed(2);
    }
  }

  function renderCharts(root) {
    const dataEl = root.querySelector("#chart-data");
    if (!dataEl || typeof Chart === "undefined") return;
    const data = JSON.parse(dataEl.textContent);
    charts.splice(0).forEach((c) => c.destroy());

    Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
    Chart.defaults.color = "#64748b";

    const trendEl = root.querySelector("#trend-chart");
    if (trendEl) {
      charts.push(new Chart(trendEl, {
        type: "bar",
        data: {
          labels: data.trend.labels,
          datasets: [{
            data: data.trend.values,
            backgroundColor: data.trend.values.map((_, i, a) => (i === a.length - 1 ? "#4f46e5" : "#c7d2fe")),
            hoverBackgroundColor: "#4338ca",
            borderRadius: 6,
            maxBarThickness: 36,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                title: (items) => data.trend.full[items[0].dataIndex],
                label: (ctx) => money(ctx.parsed.y, data.currency),
              },
            },
          },
          scales: {
            x: { grid: { display: false }, border: { display: false } },
            y: {
              beginAtZero: true,
              border: { display: false },
              grid: { color: "#f1f5f9" },
              ticks: { maxTicksLimit: 5, callback: (v) => money(v, data.currency).replace(/\.00$/, "") },
            },
          },
        },
      }));
    }

    const catEl = root.querySelector("#category-chart");
    if (catEl && data.categories.values.length) {
      charts.push(new Chart(catEl, {
        type: "doughnut",
        data: {
          labels: data.categories.labels,
          datasets: [{ data: data.categories.values, backgroundColor: data.categories.colors, borderWidth: 2, borderColor: "#fff", hoverOffset: 6 }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          cutout: "68%",
          plugins: {
            legend: { display: false },
            tooltip: { callbacks: { label: (ctx) => ` ${ctx.label}: ${money(ctx.parsed, data.currency)}` } },
          },
        },
      }));
    }
  }

  document.addEventListener("DOMContentLoaded", () => renderCharts(document));
  document.addEventListener("htmx:afterSettle", (e) => {
    const elt = e.detail.elt;
    if (elt.id === "dashboard-content" || elt.querySelector?.("#chart-data")) renderCharts(elt);
  });
})();
