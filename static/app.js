const tabs = document.querySelectorAll("[data-tab]");
const panels = document.querySelectorAll(".panel");
const adminModal = document.getElementById("adminModal");
const adminOpen = document.getElementById("adminOpen");
const adminClose = document.getElementById("adminClose");
const adminBackdrop = document.getElementById("adminBackdrop");
const unlockAdmin = document.getElementById("unlockAdmin");
const adminCode = document.getElementById("adminCode");
const lockAdmin = document.getElementById("lockAdmin");

function switchTab(name) {
  tabs.forEach((button) => button.classList.toggle("is-active", button.dataset.tab === name));
  panels.forEach((panel) => panel.classList.toggle("is-active", panel.id === name));
}

tabs.forEach((button) => {
  button.addEventListener("click", () => switchTab(button.dataset.tab));
});

function openAdmin() {
  adminModal?.classList.add("is-open");
  adminModal?.setAttribute("aria-hidden", "false");
}

function closeAdmin() {
  adminModal?.classList.remove("is-open");
  adminModal?.setAttribute("aria-hidden", "true");
}

adminOpen?.addEventListener("click", openAdmin);
adminClose?.addEventListener("click", closeAdmin);
adminBackdrop?.addEventListener("click", closeAdmin);

unlockAdmin?.addEventListener("click", async () => {
  const code = adminCode?.value?.trim() || "";
  if (!code) return;

  const response = await fetch("/api/admin/unlock", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code }),
  });

  if (response.ok) {
    window.location.reload();
    return;
  }

  adminCode.value = "";
  adminCode.placeholder = "Wrong code";
});

lockAdmin?.addEventListener("click", async () => {
  await fetch("/api/admin/lock", { method: "POST" });
  window.location.reload();
});

window.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeAdmin();
});

