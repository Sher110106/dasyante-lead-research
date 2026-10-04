const state = { data: null, selectedId: null, filter: "all" };

const signalLabels = {
  customer_facing_agent: "Customer-facing agent",
  persistent_memory: "Persistent memory",
  reliability: "Reliability / evaluation",
  relevant_hiring: "Relevant hiring",
  multi_model_or_framework: "Multi-model or framework",
  recommendations_or_actions: "Recommendations or actions",
  enterprise_or_regulated: "Enterprise or regulated",
  recent_launch_or_scale: "Recent launch or scale",
};

const $ = (selector) => document.querySelector(selector);

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#039;", '"': "&quot;",
  }[character]));
}

async function request(path, options = {}) {
  const response = await fetch(path, { headers: { "Content-Type": "application/json" }, ...options });
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || "Request failed");
  return body;
}

function setMessage(id, message, type = "") {
  const element = $(`#${id}`);
  element.textContent = message;
  element.className = `inline-message ${type}`;
}

function statusLabel(candidate) {
  if (candidate.reviewed) return '<span class="state-label reviewed">reviewed</span>';
  if (candidate.qualified) return '<span class="state-label qualified">qualified</span>';
  return '<span class="state-label">watching</span>';
}

function scoreClass(score) {
  return score >= 65 ? "high" : score > 0 ? "" : "low";
}

function filteredCandidates() {
  const candidates = state.data?.candidates || [];
  if (state.filter === "qualified") return candidates.filter((candidate) => candidate.qualified);
  if (state.filter === "reviewed") return candidates.filter((candidate) => candidate.reviewed);
  return candidates;
}

function renderStats() {
  const stats = state.data?.stats || {};
  $("#stat-companies").textContent = stats.companies || 0;
  $("#stat-qualified").textContent = stats.qualified || 0;
  $("#stat-review").textContent = Math.max(0, (stats.qualified || 0) - (stats.reviewed || 0));
  $("#stat-average").innerHTML = `${stats.avg_score || 0}<span>/100</span>`;
}

function renderQueue() {
  const list = $("#candidate-list");
  const candidates = filteredCandidates();
  if (!candidates.length) {
    list.innerHTML = '<div class="empty-list"><strong>No companies in this view.</strong>Run a research pass or change the filter.</div>';
    return;
  }
  list.innerHTML = candidates.map((candidate, index) => `
    <button class="candidate-row ${candidate.id === state.selectedId ? "selected" : ""}" data-candidate="${escapeHtml(candidate.id)}">
      <span class="company-index">${String(index + 1).padStart(2, "0")}</span>
      <span><p class="company-name">${escapeHtml(candidate.name)}</p><p class="company-domain">${escapeHtml(candidate.domain)}</p></span>
      <span class="row-meta"><span class="score ${scoreClass(candidate.score)}">${candidate.score}/100</span>${statusLabel(candidate)}</span>
    </button>`).join("");
  list.querySelectorAll("[data-candidate]").forEach((row) => row.addEventListener("click", () => selectCandidate(row.dataset.candidate)));
}

function renderCompanyProfile(candidate) {
  const profile = candidate.company_profile;
  if (!profile) {
    const message = state.data?.providers?.apollo_configured
      ? "Not fetched yet. New research runs request an Apollo profile first."
      : "Apollo is not configured. Public-web research still works.";
    return `<div class="detail-section"><div class="section-title"><h3>Apollo company profile</h3><span>not fetched</span></div><p class="profile-note">${message}</p></div>`;
  }
  const data = profile.data || {};
  const technologies = data.technologies || [];
  const labels = { success: "profile ready", not_found: "no match", error: "unavailable" };
  const rows = [
    ["Industry", data.industry],
    ["Employees", data.employee_count],
    ["Location", data.location],
    ["Total funding", data.total_funding],
    ["Latest round", [data.latest_funding_stage, data.latest_funding_date].filter(Boolean).join(" · ")],
    ["Technologies", technologies.slice(0, 8).join(", ") + (technologies.length > 8 ? ` (+${technologies.length - 8} more)` : "")],
  ];
  const retrieved = new Date(profile.fetched_at);
  const timestamp = profile.fetched_at && !Number.isNaN(retrieved.getTime()) ? retrieved.toLocaleString() : "not retrieved";
  const warning = profile.status === "error"
    ? `<p class="profile-warning" role="status">${escapeHtml(profile.error || "Apollo is unavailable.")}${profile.data ? " Showing the previous profile." : " Public-web research continued."}</p>`
    : profile.status === "not_found" ? '<p class="profile-note">Apollo returned no company match. This is not a failed qualification.</p>' : "";
  const details = profile.data ? `<dl class="company-profile-grid">${rows.map(([label, value]) => `<div><dt>${label}</dt><dd>${escapeHtml(value === null || value === undefined || value === "" ? "Not available" : value)}</dd></div>`).join("")}</dl>` : "";
  const allTechnologies = technologies.length > 8 ? `<details class="profile-technologies"><summary>Show all ${technologies.length} technologies</summary><p>${escapeHtml(technologies.join(", "))}</p></details>` : "";
  return `<div class="detail-section"><div class="section-title"><h3>Apollo company profile</h3><span>${escapeHtml(labels[profile.status] || "unknown")}</span></div>${warning}${details}${allTechnologies}<p class="profile-note">Retrieved: ${escapeHtml(timestamp)}. Profiles are cached for 7 days. Company context does not add fit-score points.</p></div>`;
}

function renderDetails() {
  const panel = $("#detail-panel");
  const candidate = (state.data?.candidates || []).find((item) => item.id === state.selectedId);
  if (!candidate) {
    panel.innerHTML = '<div class="empty-detail"><div class="empty-orbit">+</div><p class="eyebrow">Select a company</p><h2>Evidence before outreach.</h2><p>Choose a row to inspect the signals, source quotes, and contact gate.</p></div>';
    return;
  }
  const evidence = candidate.evidence || [];
  const signals = Object.entries(signalLabels).map(([key, label]) => {
    const items = evidence.filter((item) => item.signal === key);
    const item = items[0];
    return `<div class="signal-row"><span class="signal-dot ${item?.status === "yes" ? "yes" : ""}"></span><span class="signal-name">${label}</span><span class="signal-score">${item?.status === "yes" ? "confirmed" : "unknown"}</span>${item ? `<span class="evidence-quote">“${escapeHtml(item.quote)}” <a href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">source ↗</a></span>` : ""}</div>`;
  }).join("");
  const contacts = (candidate.contacts || []).map((contact) => {
    const rawStatus = String(contact.email_status || "unknown").toLowerCase();
    const statusClass = rawStatus === "valid" ? "valid" : rawStatus === "invalid" ? "invalid" : "unknown";
    const statusLabel = rawStatus === "valid" ? "verified" : rawStatus === "invalid" ? "invalid" : rawStatus;
    return `<div class="contact-row"><div><div class="contact-name">${escapeHtml(contact.first_name)} ${escapeHtml(contact.last_name)}</div><div class="contact-title">${escapeHtml(contact.title || "Role not supplied")}</div></div><div class="contact-email"><div>${escapeHtml(contact.email || "Email pending")}</div><span class="contact-status ${statusClass}">${escapeHtml(statusLabel)}</span></div></div>`;
  }).join("");
  const reviewAction = candidate.qualified && !candidate.reviewed ? '<button class="button button-primary" id="review-candidate">Approve for contacts <span>→</span></button>' : "";
  const contactAction = candidate.reviewed ? '<button class="button button-secondary" id="import-contacts">Import contacts</button>' : "";
  panel.innerHTML = `<div class="detail-content">
    <div class="detail-head"><div><p class="eyebrow">Candidate detail</p><h2>${escapeHtml(candidate.name)}</h2><div class="detail-domain"><a href="${escapeHtml(candidate.website)}" target="_blank" rel="noreferrer">${escapeHtml(candidate.domain)} ↗</a></div></div><div class="score-stamp"><strong>${candidate.score}</strong><span>of 100</span></div></div>
    <div class="detail-actions">${reviewAction}${contactAction}${candidate.reviewed ? '<span class="state-label reviewed">review gate passed</span>' : candidate.qualified ? '<span class="state-label qualified">review needed</span>' : '<span class="state-label">not qualified</span>'}</div>
    ${renderCompanyProfile(candidate)}
    <div class="detail-section"><div class="section-title"><h3>Signal ledger</h3><span>${evidence.length} source${evidence.length === 1 ? "" : "s"}</span></div>${signals}</div>
    <div class="detail-section"><div class="section-title"><h3>Decision makers</h3><span>${(candidate.contacts || []).length} imported</span></div>${contacts || '<p class="contact-email">No contacts yet. Approve the company, then import your Apollo CSV.</p>'}</div>
  </div>`;
  $("#review-candidate")?.addEventListener("click", () => reviewCandidate(candidate.id));
  $("#import-contacts")?.addEventListener("click", () => openModal("contacts-modal"));
}

function render() {
  renderStats();
  renderQueue();
  renderDetails();
}

async function refresh(preferredId = state.selectedId) {
  try {
    state.data = await request("/api/dashboard");
    const candidates = state.data.candidates || [];
    state.selectedId = candidates.some((candidate) => candidate.id === preferredId) ? preferredId : candidates[0]?.id || null;
    render();
  } catch (error) {
    $("#candidate-list").innerHTML = `<div class="error-copy">Unable to load the workspace.<br />${escapeHtml(error.message)}</div>`;
  }
}

function selectCandidate(id) {
  state.selectedId = id;
  renderQueue();
  renderDetails();
}

async function reviewCandidate(id) {
  const button = $("#review-candidate");
  if (button) button.disabled = true;
  try {
    await request(`/api/candidates/${encodeURIComponent(id)}/review`, { method: "POST", body: "{}" });
    await refresh(id);
  } catch (error) {
    alert(error.message);
    if (button) button.disabled = false;
  }
}

function openModal(id) {
  const modal = $(`#${id}`);
  modal.hidden = false;
  modal.querySelector("textarea")?.focus();
}

function closeModal(id) {
  $(`#${id}`).hidden = true;
}

function parseCsv(text) {
  const rows = [];
  let row = [];
  let cell = "";
  let quoted = false;
  for (let index = 0; index < text.length; index += 1) {
    const character = text[index];
    if (character === '"') {
      if (quoted && text[index + 1] === '"') {
        cell += '"';
        index += 1;
      } else {
        quoted = !quoted;
      }
    } else if (character === "," && !quoted) {
      row.push(cell);
      cell = "";
    } else if ((character === "\n" || character === "\r") && !quoted) {
      if (character === "\r" && text[index + 1] === "\n") index += 1;
      row.push(cell);
      if (row.some((value) => value.trim())) rows.push(row);
      row = [];
      cell = "";
    } else {
      cell += character;
    }
  }
  if (quoted) throw new Error("CSV has an unterminated quoted field");
  if (cell || row.length) {
    row.push(cell);
    if (row.some((value) => value.trim())) rows.push(row);
  }
  if (rows.length < 2) throw new Error("CSV needs a header and at least one company row");
  const headers = rows.shift().map((value) => value.trim().toLowerCase().replace(/\s+/g, "_"));
  if (headers.some((header) => !header)) throw new Error("CSV headers cannot be empty");
  const companyHeader = headers.includes("company_name") ? "company_name" : headers.includes("name") ? "name" : "";
  if (!companyHeader || !headers.includes("website")) throw new Error("CSV must include company_name and website columns");
  const records = rows.map((values, rowIndex) => {
    const record = Object.fromEntries(headers.map((header, index) => [header, (values[index] || "").trim()]));
    if (!record[companyHeader] || !record.website) throw new Error(`CSV row ${rowIndex + 2} needs a company name and website`);
    return { company_name: record[companyHeader], website: record.website, linkedin_url: record.linkedin_url || "" };
  });
  return records;
}

function csvField(value) {
  return `"${String(value ?? "").replace(/"/g, '""')}"`;
}

async function runResearch() {
  const button = $("#run-research");
  button.disabled = true;
  let companies;
  try {
    companies = parseCsv($("#research-csv").value);
  } catch (error) {
    setMessage("research-message", error.message, "error");
    button.disabled = false;
    return;
  }
  const skipApollo = $("#skip-apollo").checked;
  const refreshApollo = $("#refresh-apollo").checked;
  const outcomes = [];
  const warnings = [];
  setMessage("research-message", `Preparing ${companies.length} company run${companies.length === 1 ? "" : "s"}...`);
  try {
    for (const [index, company] of companies.entries()) {
      setMessage("research-message", `Researching ${index + 1} of ${companies.length}: ${company.company_name}...`);
      const csv = ["company_name,website,linkedin_url", [company.company_name, company.website, company.linkedin_url].map(csvField).join(",")].join("\n");
      try {
        const result = await request("/api/research", { method: "POST", body: JSON.stringify({ csv, skip_apollo: skipApollo, refresh_apollo: refreshApollo }) });
        warnings.push(...(result.warnings || []));
        outcomes.push(`${company.company_name}: complete`);
      } catch (error) {
        outcomes.push(`${company.company_name}: failed (${error.message})`);
      }
    }
    const failures = outcomes.filter((outcome) => outcome.includes(": failed"));
    const succeeded = outcomes.length - failures.length;
    if (!succeeded) throw new Error(outcomes.join(" · "));
    const message = `${succeeded}/${companies.length} company run${companies.length === 1 ? "" : "s"} complete${warnings.length ? ` · ${warnings.length} Apollo warning(s)` : ""}${failures.length ? ` · ${failures.length} failed` : ""}`;
    setMessage("research-message", `${message}\n${outcomes.join("\n")}`, failures.length || warnings.length ? "warning" : "success");
    await refresh();
    if (!failures.length && !warnings.length) setTimeout(() => closeModal("research-modal"), 700);
  } catch (error) {
    setMessage("research-message", error.message, "error");
  } finally {
    button.disabled = false;
  }
}

async function runContactImport() {
  if (!state.selectedId) return;
  const button = $("#run-import");
  button.disabled = true;
  setMessage("contacts-message", "Importing reviewed contacts...");
  try {
    const result = await request(`/api/candidates/${encodeURIComponent(state.selectedId)}/contacts`, { method: "POST", body: JSON.stringify({ csv: $("#contacts-csv").value }) });
    setMessage("contacts-message", `Imported ${result.imported} contact${result.imported === 1 ? "" : "s"}.`, "success");
    await refresh(state.selectedId);
    setTimeout(() => closeModal("contacts-modal"), 700);
  } catch (error) {
    setMessage("contacts-message", error.message, "error");
  } finally {
    button.disabled = false;
  }
}

$("#open-research").addEventListener("click", () => openModal("research-modal"));
$("#run-research").addEventListener("click", runResearch);
$("#run-import").addEventListener("click", runContactImport);
$("#skip-apollo").addEventListener("change", () => {
  if ($("#skip-apollo").checked) $("#refresh-apollo").checked = false;
});
$("#refresh-apollo").addEventListener("change", () => {
  if ($("#refresh-apollo").checked) $("#skip-apollo").checked = false;
});
document.querySelectorAll("[data-close]").forEach((button) => button.addEventListener("click", () => closeModal(button.dataset.close)));
document.querySelectorAll(".filter").forEach((button) => button.addEventListener("click", () => {
  document.querySelectorAll(".filter").forEach((item) => item.classList.remove("active"));
  button.classList.add("active");
  state.filter = button.dataset.filter;
  renderQueue();
}));
document.querySelectorAll(".nav-item").forEach((button) => button.addEventListener("click", () => {
  document.querySelectorAll(".nav-item").forEach((item) => item.classList.remove("active"));
  button.classList.add("active");
  if (button.dataset.view === "contacts") state.filter = "reviewed";
  if (button.dataset.view === "research") state.filter = "all";
  if (button.dataset.view === "evidence") state.filter = "qualified";
  document.querySelectorAll(".filter").forEach((item) => item.classList.toggle("active", item.dataset.filter === state.filter));
  renderQueue();
}));

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") document.querySelectorAll(".modal-backdrop:not([hidden])").forEach((modal) => { modal.hidden = true; });
});

refresh();
