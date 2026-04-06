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
// create the matches store immediately so templates can read it even if
// someone accidentally registers their init handler too late
if (!Alpine.store || !Alpine.store('matches')) {
  Alpine.store('matches', []);
}
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
    window.location.href = "/auth.html";
    return;
  }

  if (page === "auth.html" && userType) {
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
  // auth.html handles its own login via inline script
  if (page === "auth.html") {
    return;
  }

  /* =========================
     SIGN OUT
  ========================= */
  document.addEventListener("click", (e) => {
    const btn = e.target.closest("#signOutBtn");
    if (!btn) return;

    localStorage.clear();
    window.location.href = "/auth.html";
  });

  const availForm = document.getElementById("availability-form");
  if (availForm) {
    availForm.addEventListener("submit", async function (e) {

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
        let msg = "Blocked slot saved successfully!";
        if (result.cancelled_appointments > 0) {
          msg += `\n\n⚠️ ${result.cancelled_appointments} clashing appointment(s) were automatically cancelled.`;
        }
        Swal.fire({ icon: 'success', title: 'Saved', text: msg });
      } else {
        Swal.fire({ icon: 'error', title: 'Error', text: result.error || 'Something went wrong' });
      }
    });
  }

  /* =========================
   PATIENT PREFERENCES FORM
  ========================= */
  // Alpine store for match results will be initialized when Alpine starts
  document.addEventListener('alpine:init', () => {
    Alpine.store('matches', []);
  });

  const patientForm = document.getElementById("patient-preferences-form");
  if (patientForm) {
    patientForm.addEventListener("submit", async (e) => {
      e.preventDefault();

      const csrftoken = getCookie("csrftoken");

      const preferredSpecialtyEl = patientForm.querySelector('select[name="preferred_specialty"]');
      const preferredGenderEl = patientForm.querySelector('select[name="preferred_gender"]');
      const preferredTimeEl = patientForm.querySelector('input[name="preferred_time_range"]:checked');
      const requestDateEl = patientForm.querySelector('input[name="request_date"]');
      const sessionLengthEl = patientForm.querySelector('input[name="session_length"]:checked');

      const data = {
        preferred_specialty: preferredSpecialtyEl ? preferredSpecialtyEl.value : "",
        preferred_gender: preferredGenderEl && preferredGenderEl.value ? preferredGenderEl.value : "any",
        preferred_time_range: preferredTimeEl ? preferredTimeEl.value : "",
        request_date: requestDateEl ? requestDateEl.value : null,
        session_length: sessionLengthEl ? parseInt(sessionLengthEl.value, 10) : 60
      };

      console.log('patient prefs data', data);

      // Basic validation: specialty and date are required for meaningful results
      if (!data.preferred_specialty) {
        Swal.fire({icon:'warning', title:'Missing field', text:'Please select a specialty'});
        return;
      }
      if (!data.request_date) {
        Swal.fire({icon:'warning', title:'Missing date', text:'Please choose a preferred date'});
        return;
      }

      try {
        // show loading popup while solver runs on server
      let loadingSwal = Swal.fire({
        title: 'Finding matches...',
        allowOutsideClick: false,
        didOpen: () => Swal.showLoading()
      });

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
        console.log('preferences API result:', result);
        if (result.matches) {
          result.matches.forEach(d => console.log('avail slots', d.doctor_id, d.available_slots));
        }
        Swal.close();

        if (response.ok) {
          Swal.fire({icon:'success', title:'Saved', text:'Preferences saved successfully!'});
          // update match store if present
          if (Alpine) {
            let arr = [];
            Alpine.store('latestPreference', data);
            Alpine.store('preferenceId', result.preference_id || null);
            if (!Alpine.store || !Alpine.store('matches')) {
                Alpine.store('matches', []);
              }

              if (!Alpine.store || !Alpine.store('latestPreference')) {
                Alpine.store('latestPreference', null);
              }
            if (Array.isArray(result.matches)) {
              // filter out null/undefined entries just in case
              arr = result.matches.filter(d => d != null);
            } else {
              console.warn('expected array of matches but got', result.matches);
            }
            console.log('updating Alpine store matches to', arr);
            Alpine.store('matches', arr);
          }
          document.querySelector("#matching-results")?.scrollIntoView({
            behavior: "smooth"
          });
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
        Swal.close();
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
        tbody.innerHTML = `<div class="flex flex-col items-center justify-center py-10 text-center"><p class="text-sm font-medium text-error-600 dark:text-error-400">Error loading slots</p></div>`;
        return;
      }

      if (slots.length === 0) {
        tbody.innerHTML = `<div class="flex flex-col items-center justify-center py-12 text-center"><div class="flex h-12 w-12 items-center justify-center rounded-2xl bg-gray-100 text-gray-400 dark:bg-gray-800 dark:text-gray-500"><svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M10 5V10L13.3333 11.6667" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><path d="M17.5 10C17.5 14.1421 14.1421 17.5 10 17.5C5.85786 17.5 2.5 14.1421 2.5 10C2.5 5.85786 5.85786 2.5 10 2.5C14.1421 2.5 17.5 5.85786 17.5 10Z" stroke="currentColor" stroke-width="1.5"/></svg></div><p class="mt-3 text-sm font-medium text-gray-600 dark:text-gray-300">No blocked slots yet</p><p class="mt-1 text-xs text-gray-400 dark:text-gray-500">Blocked times you create will appear here.</p></div>`;
        return;
      }

      const formatSlotDate = (value) => {
        if (!value) return "-";
        const date = new Date(`${value}T00:00:00`);
        if (Number.isNaN(date.getTime())) return value;
        return date.toLocaleDateString([], {
          weekday: "short",
          day: "numeric",
          month: "short",
          year: "numeric",
        });
      };

      const formatSlotTime = (value) => {
        if (!value) return "-";
        const [hours, minutes] = value.split(":");
        if (hours === undefined || minutes === undefined) return value;
        const date = new Date();
        date.setHours(Number(hours), Number(minutes), 0, 0);
        if (Number.isNaN(date.getTime())) return value;
        return date.toLocaleTimeString([], {
          hour: "numeric",
          minute: "2-digit",
          hour12: true,
        });
      };

      const formatReasonLabel = (value) => {
        if (!value) return "Unavailable";
        return value
          .replace(/_/g, " ")
          .replace(/\b\w/g, (char) => char.toUpperCase());
      };

      slots.forEach(slot => {
        const row = document.createElement("div");
        const formattedDate = formatSlotDate(slot.date);
        const formattedStartTime = formatSlotTime(slot.start_time);
        const formattedEndTime = formatSlotTime(slot.end_time);
        const formattedReason = formatReasonLabel(slot.reason);

        row.className = "group relative grid grid-cols-[1.2fr_0.8fr_0.8fr_1fr] items-center gap-3 rounded-xl border border-gray-200/70 bg-white px-4 py-3 transition-all hover:border-error-200 hover:shadow-md hover:shadow-error-500/5 dark:border-gray-800/50 dark:bg-white/[0.02] dark:hover:border-error-500/30";
        row.innerHTML = `
          <div class="absolute inset-y-2 left-0 w-[3px] rounded-full bg-gradient-to-b from-error-400 to-error-300 opacity-0 transition-opacity group-hover:opacity-100 dark:from-error-500 dark:to-error-400"></div>
          <div>
            <p class="text-sm font-semibold text-gray-800 dark:text-white/90">${formattedDate}</p>
          </div>
          <div class="flex items-center gap-1.5">
            <span class="inline-block h-1.5 w-1.5 rounded-full bg-success-400"></span>
            <span class="text-sm font-medium tabular-nums text-gray-700 dark:text-gray-300">${formattedStartTime}</span>
          </div>
          <div class="flex items-center gap-1.5">
            <span class="inline-block h-1.5 w-1.5 rounded-full bg-error-400"></span>
            <span class="text-sm font-medium tabular-nums text-gray-700 dark:text-gray-300">${formattedEndTime}</span>
          </div>
          <div>
            <span class="inline-flex items-center rounded-full border border-error-200/60 bg-error-50/80 px-2.5 py-0.5 text-[11px] font-medium text-error-600 dark:border-error-500/20 dark:bg-error-500/10 dark:text-error-400">
              ${formattedReason}
            </span>
          </div>
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
