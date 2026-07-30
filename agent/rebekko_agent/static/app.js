const messages = document.querySelector("#messages");
const composer = document.querySelector("#composer");
const input = document.querySelector("#message");
const send = document.querySelector("#send");
const stopButton = document.querySelector("#stop");
const workStatus = document.querySelector("#work-status");
const statusTitle = document.querySelector("#status-title");
const elapsed = document.querySelector("#elapsed");
const updated = document.querySelector("#updated");
const technicalOutput = document.querySelector("#technical-output");
const connection = document.querySelector("#connection");

let activeJob = null;
let pollTimer = null;
let clockTimer = null;
let lastUpdate = null;

function duration(from, to = new Date()) {
  if (!from) return "00:00";
  const seconds = Math.max(0, Math.floor((to - new Date(from)) / 1000));
  const minutes = Math.floor(seconds / 60);
  return `${String(minutes).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}

function render(jobs) {
  messages.replaceChildren();
  for (const job of jobs) {
    const user = document.createElement("article");
    user.className = "message user";
    user.innerHTML = `<div class="bubble"></div><div class="meta"></div>`;
    user.querySelector(".bubble").textContent = job.request;
    user.querySelector(".meta").textContent = new Date(job.created_at).toLocaleString();
    messages.append(user);

    if (["completed", "failed", "cancelled"].includes(job.status)) {
      const reply = document.createElement("article");
      reply.className = `message assistant ${job.status}`;
      const text = job.response || job.error || "Job interrotto.";
      reply.innerHTML = `<div class="bubble"></div><div class="meta"></div>`;
      reply.querySelector(".bubble").textContent = text;
      const label = job.status === "completed" ? "Completato" :
        job.status === "failed" ? "Fallito" : "Interrotto";
      reply.querySelector(".meta").textContent =
        `${label} in ${duration(job.started_at || job.created_at, new Date(job.finished_at))}`;
      messages.append(reply);
    }
  }
  const active = jobs.find((job) => ["queued", "running"].includes(job.status));
  setActive(active || null);
  window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" });
}

function setActive(job) {
  activeJob = job;
  workStatus.classList.toggle("hidden", !job);
  send.disabled = Boolean(job);
  if (!job) {
    clearTimeout(pollTimer);
    clearInterval(clockTimer);
    pollTimer = null;
    clockTimer = null;
    return;
  }
  statusTitle.textContent = job.status === "queued" ? "In attesa…" : "Codex sta lavorando…";
  technicalOutput.textContent = job.output || "";
  lastUpdate = new Date();
  updateClock();
  if (!clockTimer) clockTimer = setInterval(updateClock, 1000);
  schedulePoll();
}

function updateClock() {
  if (!activeJob) return;
  elapsed.textContent = `Tempo trascorso: ${duration(activeJob.started_at || activeJob.created_at)}`;
  const age = Math.floor((new Date() - lastUpdate) / 1000);
  updated.textContent = `Ultimo aggiornamento: ${age} secondi fa`;
}

function schedulePoll() {
  clearTimeout(pollTimer);
  if (!activeJob || document.hidden) return;
  pollTimer = setTimeout(poll, 2500);
}

async function poll() {
  if (!activeJob || document.hidden) return;
  try {
    const response = await fetch(`/api/jobs/${activeJob.id}`, { cache: "no-store" });
    if (!response.ok) throw new Error("Stato non disponibile");
    const job = await response.json();
    connection.textContent = "Online";
    connection.classList.remove("offline");
    lastUpdate = new Date();
    if (["queued", "running"].includes(job.status)) {
      activeJob = job;
      technicalOutput.textContent = job.output || "";
      schedulePoll();
    } else {
      await loadHistory();
    }
  } catch {
    connection.textContent = "Offline";
    connection.classList.add("offline");
    schedulePoll();
  }
}

async function loadHistory() {
  const response = await fetch("/api/jobs", { cache: "no-store" });
  if (!response.ok) throw new Error("Impossibile caricare lo storico");
  render(await response.json());
}

composer.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = input.value.trim();
  if (!message || activeJob) return;
  send.disabled = true;
  try {
    const response = await fetch("/api/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });
    const body = await response.json();
    if (!response.ok) {
      const detail = body.detail?.message || body.detail || "Richiesta non riuscita";
      throw new Error(detail);
    }
    input.value = "";
    await loadHistory();
  } catch (error) {
    alert(error.message);
    send.disabled = false;
  }
});

stopButton.addEventListener("click", async () => {
  if (!activeJob || !confirm("Interrompere il job corrente?")) return;
  stopButton.disabled = true;
  try {
    await fetch(`/api/jobs/${activeJob.id}/cancel`, { method: "POST" });
    await loadHistory();
  } finally {
    stopButton.disabled = false;
  }
});

document.addEventListener("visibilitychange", () => {
  if (!document.hidden && activeJob) poll();
  if (document.hidden) clearTimeout(pollTimer);
});

loadHistory().catch((error) => {
  connection.textContent = "Offline";
  connection.classList.add("offline");
  alert(error.message);
});

