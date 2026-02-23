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

// Global variable to store current user
let currentUser = null;

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

  // =========================
  // FETCH CURRENT USER
  // =========================
  (async () => {
    try {
      const res = await fetch("/api/current-user/", { credentials: "include" });
      currentUser = await res.json();
      console.log("Current user:", currentUser); // Check in console
    } catch (err) {
      console.error("Failed to fetch current user:", err);
    }
  })();

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
          credentials: "include",
          body: JSON.stringify({ email, password }),
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Login failed");

        localStorage.setItem("user_type", data.user_type);
        localStorage.setItem("user_id", data.user_id);
        localStorage.setItem("first_name", data.first_name);
        localStorage.setItem("last_name", data.last_name);
        localStorage.setItem("email", data.email);

        // Verify session by fetching current user
        const currentUserRes = await fetch("/api/current-user/", { credentials: "include" });
        const currentUser = await currentUserRes.json();
        
        if (currentUserRes.ok) {
          console.log("✅ Session confirmed:", currentUser);
        } else {
          console.warn("⚠️ Session not confirmed:", currentUser);
        }

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

  document.getElementById("availability-form")
    .addEventListener("submit", async function (e) {

      e.preventDefault();

      const data = {
        doctor_id: currentUser.doctor_id, // pass the doctor ID
        date: document.getElementById("availability-date").value,
        start_time: document.getElementById("start-time").value,
        end_time: document.getElementById("end-time").value,
        reason: document.querySelector("select").value,
      };

      const response = await fetch("/api/doctor/blocked-slots/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken"),
        },
        credentials: "include",
        body: JSON.stringify(data),
      });

      const result = await response.json();

      if (response.ok) {
        alert("Availability saved ✅");
      } else {
        alert(result.error || "Something went wrong ❌");
      }
    });

  /* =========================
   PATIENT PREFERENCES FORM
  ========================= */
  const patientForm = document.getElementById("patient-preferences-form");
  if (patientForm) {
    patientForm.addEventListener("submit", async (e) => {
      e.preventDefault();

      const csrftoken = getCookie("csrftoken");

      const preferredSpecialtyEl = patientForm.querySelector('select[name="preferred_specialty"]');
      const preferredGenderEl = patientForm.querySelector('select[name="preferred_gender"]');
      const preferredTimeEl = patientForm.querySelector('input[name="preferred_time_range"]:checked');
      const requestDateEl = patientForm.querySelector('input[name="request_date"]');

      const data = {
        preferred_specialty: preferredSpecialtyEl ? preferredSpecialtyEl.value : "",
        preferred_gender: preferredGenderEl && preferredGenderEl.value ? preferredGenderEl.value : "any",
        preferred_time_range: preferredTimeEl ? preferredTimeEl.value : "",
        request_date: requestDateEl ? requestDateEl.value : null
      };

      console.log('patient prefs data', data);

      // Basic validation: only specialty is mandatory
      if (!data.preferred_specialty) {
        Swal.fire({icon:'warning', title:'Missing field', text:'Please select a specialty'});
        return;
      }

      try {
        const response = await fetch("/api/patient/preferences/", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrftoken
          },
          credentials: "include",
          body: JSON.stringify(data)
        });

        const result = await response.json();

        if (response.ok) {
          Swal.fire({icon:'success', title:'Saved', text:'Preferences saved successfully!'});
          patientForm.reset();
          // Reset Alpine.js selected class for radio buttons
          const radios = patientForm.querySelectorAll('input[name="preferred_time_range"]');
          radios.forEach(r => r.checked = false);
          if (Alpine) Alpine.store("selected", ""); // optional if using Alpine store
        } else {
          Swal.fire({icon:'error', title:'Error', text: result.error || 'Something went wrong'});
        }
      } catch (err) {
        console.error(err);
        Swal.fire({icon:'error', title:'Failure', text:'Failed to save preferences'});
      }
    });
  }


  // =========================
  // LOAD DOCTOR'S BLOCKED SLOTS
  // =========================
  const loadBlockedSlots = async () => {
    try {
      const res = await fetch("/api/doctor/blocked-slots/list/", { credentials: "include" });
      const slots = await res.json();

      const tbody = document.getElementById("blocked-slots-table");
      if (!tbody) return; // Table not on this page

      tbody.innerHTML = ""; // Clear existing rows

      if (!res.ok) {
        tbody.innerHTML = `<tr><td colspan="4" class="px-5 py-4 text-center text-gray-500">Error loading slots</td></tr>`;
        return;
      }

      if (slots.length === 0) {
        tbody.innerHTML = `<tr><td colspan="4" class="px-5 py-4 text-center text-gray-500">No blocked slots</td></tr>`;
        return;
      }

      slots.forEach(slot => {
        const row = document.createElement("tr");
        row.innerHTML = `
          <td class="px-5 py-4 sm:px-6">
            <p class="text-gray-800 text-theme-sm dark:text-white/90">${slot.date}</p>
          </td>
          <td class="px-5 py-4 sm:px-6">
            <p class="text-gray-500 text-theme-sm dark:text-gray-400">${slot.start_time}</p>
          </td>
          <td class="px-5 py-4 sm:px-6">
            <p class="text-gray-500 text-theme-sm dark:text-gray-400">${slot.end_time}</p>
          </td>
          <td class="px-5 py-4 sm:px-6">
            <span class="rounded-full bg-warning-50 px-2 py-0.5 text-theme-xs font-medium text-warning-700 dark:bg-warning-500/15 dark:text-warning-400">
              ${slot.reason}
            </span>
          </td>
        `;
        tbody.appendChild(row);
      });
    } catch (err) {
      console.error("Failed to load blocked slots:", err);
    }
  };

  // Load slots when page loads
  loadBlockedSlots();

  /* =========================
     FILL USER INFO
  ========================= */
  const userIdInput = document.querySelector('input[name="user_id"]');
  const userTypeInput = document.querySelector('input[name="user_type"]');
  const fnameInput = document.querySelector('input[name="first_name"]');
  const lnameInput = document.querySelector('input[name="last_name"]');
  const emailInput = document.querySelector('input[name="email"]');

  if (userIdInput) userIdInput.value = localStorage.getItem("user_id") || "";
  if (userTypeInput) userTypeInput.value = localStorage.getItem("user_type") || "";
  if (fnameInput) fnameInput.value = localStorage.getItem("first_name") || "";
  if (lnameInput) lnameInput.value = localStorage.getItem("last_name") || "";
  if (emailInput) emailInput.value = localStorage.getItem("email") || "";

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

// CSRF helper
function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== "") {
    const cookies = document.cookie.split(";");
    for (let cookie of cookies) {
      cookie = cookie.trim();
      if (cookie.startsWith(name + "=")) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}
