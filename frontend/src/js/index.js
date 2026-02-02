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

document.addEventListener("DOMContentLoaded", () => {
  /* =========================
     PAGE & AUTH LOGIC
  ========================= */
  const page = window.location.pathname.split("/").pop();
  const userType = localStorage.getItem("user_type");

  if ((page === "" || page === "index.html") && !userType) {
    window.location.href = "/signin.html";
    return;
  }

  if (page === "signin.html" && userType) {
    window.location.href = "/index.html";
    return;
  }

  /* =========================
     DATE LIMIT (TODAY → FUTURE)
  ========================= */
  const dateInput = document.getElementById("availability-date");
  if (dateInput) {
    const today = new Date().toISOString().split("T")[0];
    dateInput.min = today;
  }

  /* =========================
     TIME LIMIT (09:00 → 17:00)
  ========================= */
  const startTime = document.getElementById("start-time");
  const endTime = document.getElementById("end-time");

  if (startTime && endTime) {
    const MIN = "09:00";
    const MAX = "17:00";

    const clamp = (input) => {
      if (!input.value) return;
      if (input.value < MIN) input.value = MIN;
      if (input.value > MAX) input.value = MAX;
    };

    startTime.addEventListener("input", () => {
      clamp(startTime);
      if (endTime.value && endTime.value < startTime.value) {
        endTime.value = startTime.value;
      }
    });

    endTime.addEventListener("input", () => {
      clamp(endTime);
      if (endTime.value < startTime.value) {
        endTime.value = startTime.value;
      }
    });
  }

  /* =========================
     SIGNIN PAGE LOGIC
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

      spinner.style.display = "block";
      errorMsg.textContent = "";

      try {
        const res = await fetch("/api/login/", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password }),
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Login failed");

        localStorage.setItem("user_type", data.user_type);
        localStorage.setItem("username", data.username);
        localStorage.setItem("first_name", data.first_name);
        localStorage.setItem("email", data.email);

        window.location.href = "/index.html";
      } catch (err) {
        errorMsg.textContent = err.message;
      } finally {
        spinner.style.display = "none";
      }
    });

    return;
  }

  /* =========================
     SIGN OUT
  ========================= */
  document.addEventListener("click", (e) => {
    const btn = e.target.closest("#signOutBtn");
    if (!btn) return;

    localStorage.clear();
    window.location.href = "/signin.html";
  });

  /* =========================
     FILL USER INFO
  ========================= */
  const usernameInput = document.querySelector('input[name="username"]');
  const userTypeInput = document.querySelector('input[name="user_type"]');
  const fnameInput = document.querySelector('input[name="first_name"]');

  if (usernameInput) usernameInput.value = localStorage.getItem("username") || "";
  if (userTypeInput) userTypeInput.value = localStorage.getItem("user_type") || "";
  if (fnameInput) fnameInput.value = localStorage.getItem("first_name") || "";

  /* =========================
     DASHBOARD INIT
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
