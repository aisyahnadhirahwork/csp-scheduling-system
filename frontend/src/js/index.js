import "jsvectormap/dist/jsvectormap.min.css";
import "flatpickr/dist/flatpickr.min.css";
import "dropzone/dist/dropzone.css";
import "../css/style.css";

import Alpine from "alpinejs";
import persist from "@alpinejs/persist";
import flatpickr from "flatpickr";
import Dropzone from "dropzone";

import chart01 from "./components/charts/chart-01";
import chart02 from "./components/charts/chart-02";
import chart03 from "./components/charts/chart-03";
import map01 from "./components/map-01";
import "./components/calendar-init.js";
import "./components/image-resize";

Alpine.plugin(persist);
window.Alpine = Alpine;
Alpine.start();

/* =========================
   AUTH + PAGE BOOTSTRAP
========================= */
document.addEventListener("DOMContentLoaded", () => {
  const page = window.location.pathname.split("/").pop();
  const userType = localStorage.getItem("user_type");

  /* ---- Redirect rules ---- */
  if ((page === "" || page === "index.html") && !userType) {
    window.location.href = "/signin.html";
    return;
  }

  if (page === "signin.html" && userType) {
    window.location.href = "/index.html";
    return;
  }

  /* =========================
     SIGN IN PAGE LOGIC ONLY
  ========================= */
  if (page === "signin.html") {
    const form = document.getElementById("signinForm");
    const loginBtn = document.getElementById("loginBtn");
    const spinner = document.getElementById("spinner");
    const errorMsg = document.getElementById("error-msg");

    if (!form || !loginBtn) return;

    form.addEventListener("submit", (e) => e.preventDefault());

    loginBtn.addEventListener("click", async () => {
      const email = document.getElementById("email")?.value;
      const password = document.getElementById("password")?.value;

      errorMsg.textContent = "";
      spinner.style.display = "block";

      try {
        const response = await fetch("http://localhost:8000/api/login/", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password }),
        });

        const data = await response.json();

        if (!response.ok) {
          throw new Error(data.error || "Login failed");
        }

        localStorage.setItem("user_type", data.user_type);
        window.location.href = "/index.html";
      } catch (err) {
        errorMsg.textContent = err.message;
      } finally {
        spinner.style.display = "none";
      }
    });

    return; // 🚨 stop here, don’t init dashboard stuff
  }

// ===== SIGN OUT (works with dynamic header) =====
document.addEventListener("click", (e) => {
  const btn = e.target.closest("#signOutBtn");
  if (!btn) return;

  localStorage.removeItem("user_type");
  window.location.href = "/signin.html";
});


  /* =========================
     DASHBOARD INIT ONLY
  ========================= */
  chart01();
  chart02();
  chart03();
  map01();

  flatpickr(".datepicker", {
    mode: "range",
    static: true,
    monthSelectorType: "static",
    dateFormat: "M j",
    defaultDate: [
      new Date().setDate(new Date().getDate() - 6),
      new Date(),
    ],
    prevArrow:
      '<svg class="stroke-current" width="24" height="24" viewBox="0 0 24 24"><path d="M15.25 6L9 12.25L15.25 18.5"/></svg>',
    nextArrow:
      '<svg class="stroke-current" width="24" height="24" viewBox="0 0 24 24"><path d="M8.75 19L15 12.75L8.75 6.5"/></svg>',
  });

  const dropzoneArea = document.querySelectorAll("#demo-upload");
  if (dropzoneArea.length) {
    new Dropzone("#demo-upload", { url: "/file/post" });
  }

  const year = document.getElementById("year");
  if (year) year.textContent = new Date().getFullYear();
});
