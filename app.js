const state = {
  data: null,
  depthIndex: 0,
};

const depthButtons = Array.from(document.querySelectorAll("[data-depth]"));
const offenseField = document.getElementById("offense-field");
const defenseField = document.getElementById("defense-field");
const coachGrid = document.getElementById("coach-grid");
const sourceList = document.getElementById("source-list");
const playerModal = document.getElementById("player-modal");
const modalContent = document.getElementById("modal-content");
const modalTemplate = document.getElementById("player-modal-template");

depthButtons.forEach((button) => {
  button.addEventListener("click", () => {
    state.depthIndex = Number(button.dataset.depth || "0");
    depthButtons.forEach((item) => item.classList.toggle("is-active", item === button));
    renderFields();
  });
});

document.getElementById("modal-close").addEventListener("click", () => playerModal.close());
playerModal.addEventListener("click", (event) => {
  if (event.target === playerModal) {
    playerModal.close();
  }
});

function setText(id, value) {
  const element = document.getElementById(id);
  if (element) element.textContent = value || "-";
}

function positionPoint(layout, position) {
  return layout[position] || { x: 50, y: 50 };
}

function buildPlayerButton(player, position, coordinates) {
  const button = document.createElement("button");
  button.className = "field-player";
  button.style.left = `${coordinates.x}%`;
  button.style.top = `${coordinates.y}%`;
  button.innerHTML = `
    <span class="field-player__pos">${position}</span>
    <h3 class="field-player__name">${player.name}</h3>
    <p class="field-player__meta">${player.class || player.eligibility || ""}</p>
    <span class="field-player__rating">${player.rating}</span>
  `;
  button.addEventListener("click", () => openPlayerModal(player));
  return button;
}

function buildField(fieldElement, rows, layout) {
  fieldElement.innerHTML = "";
  const marker = document.createElement("div");
  marker.className = "field-marker";
  fieldElement.appendChild(marker);

  rows.forEach((row) => {
    const playerId = row.playerIds[state.depthIndex];
    const player = state.data.players[playerId];
    if (!player) return;
    fieldElement.appendChild(
      buildPlayerButton(player, row.position, positionPoint(layout, row.position))
    );
  });
}

function summarizeStats(player) {
  const groups = player.stats?.statGroups || {};
  const order = ["passing", "rushing", "receiving", "defensive"];
  const group = order.find((name) => groups[name]) || Object.keys(groups)[0];
  if (!group) return [];
  return Object.values(groups[group].stats)
    .filter((stat) => stat.displayValue && stat.displayValue !== "0")
    .slice(0, 6);
}

function openPlayerModal(player) {
  const fragment = modalTemplate.content.cloneNode(true);
  fragment.querySelector(".modal-card__headshot").src =
    player.headshot || state.data.team.logo;
  fragment.querySelector(".modal-card__headshot").alt = `${player.name} headshot`;
  fragment.querySelector(".modal-card__depth").textContent = `${player.depthLabel} • ${player.position}`;
  fragment.querySelector(".modal-card__name").textContent = player.name;
  fragment.querySelector(".modal-card__meta").textContent = [
    player.class || player.eligibility,
    player.height,
    player.weight,
    player.hometown,
  ]
    .filter(Boolean)
    .join(" • ");
  fragment.querySelector(".modal-card__bio").textContent =
    player.bio || "Official bio not available from the current source set.";
  fragment.querySelector(".rating-pill strong").textContent = player.rating;

  const badgeRow = fragment.querySelector(".badge-row");
  player.badges.forEach((badge) => {
    const pill = document.createElement("span");
    pill.className = "badge";
    pill.textContent = badge;
    badgeRow.appendChild(pill);
  });

  const statGrid = fragment.querySelector(".stat-grid");
  summarizeStats(player).forEach((stat) => {
    const chip = document.createElement("div");
    chip.className = "stat-chip";
    chip.innerHTML = `
      <span class="stat-chip__label">${stat.abbreviation}</span>
      <strong class="stat-chip__value">${stat.displayValue}</strong>
    `;
    statGrid.appendChild(chip);
  });

  const linkRow = fragment.querySelector(".link-row");
  const links = [
    player.highlight,
    ...(player.sourceLinks || []),
  ].filter(Boolean);

  links.forEach((link) => {
    const anchor = document.createElement("a");
    anchor.href = link.url;
    anchor.target = "_blank";
    anchor.rel = "noreferrer";
    anchor.className = "badge";
    anchor.textContent = link.label;
    linkRow.appendChild(anchor);
  });

  modalContent.innerHTML = "";
  modalContent.appendChild(fragment);
  playerModal.showModal();
}

function renderFields() {
  if (!state.data) return;
  buildField(offenseField, state.data.depthChart.offense, state.data.depthChart.layouts.offense);
  buildField(defenseField, state.data.depthChart.defense, state.data.depthChart.layouts.defense);
}

function renderCoaches() {
  const coaches = Object.values(state.data.coaches);
  coachGrid.innerHTML = "";
  coaches.forEach((coach) => {
    const card = document.createElement("article");
    card.className = "coach-card";
    card.innerHTML = `
      <div class="coach-card__header">
        <img class="coach-card__headshot" src="${coach.headshot || state.data.team.logo}" alt="${coach.name}" />
        <div>
          <h3 class="coach-card__name">${coach.name}</h3>
          <p class="coach-card__role">${coach.role}</p>
        </div>
      </div>
      <p class="coach-card__bio">${coach.bio || ""}</p>
      <ul>${coach.tendencies.map((item) => `<li>${item}</li>`).join("")}</ul>
      <p>${coach.tendencySources
        .map((source) => `<a href="${source.url}" target="_blank" rel="noreferrer">${source.label}</a>`)
        .join(" · ")}</p>
    `;
    coachGrid.appendChild(card);
  });
}

function renderSources() {
  sourceList.innerHTML = "";
  state.data.sources.forEach((source) => {
    const item = document.createElement("li");
    item.innerHTML = `<a href="${source.url}" target="_blank" rel="noreferrer">${source.label}</a>`;
    sourceList.appendChild(item);
  });
}

async function init() {
  const response = await fetch("data/aggies.json", { cache: "no-store" });
  state.data = await response.json();

  document.title = `${state.data.team.shortName} Football Depth Chart`;
  setText("hero-title", `${state.data.team.shortName} depth chart in formation view`);
  setText(
    "hero-copy",
    "Switch between starters, second string, and third string while keeping each lineup mapped onto the field."
  );
  setText("offense-scheme", state.data.depthChart.offenseScheme);
  setText("defense-scheme", state.data.depthChart.defenseScheme);
  setText(
    "depth-updated",
    state.data.depthChart.updatedAt || `Generated ${new Date(state.data.generatedAt).toLocaleString()}`
  );
  setText("stats-season", state.data.latestStatSeason);
  setText("season-note", state.data.seasonContext.note);

  renderFields();
  renderCoaches();
  renderSources();
}

init().catch((error) => {
  console.error(error);
  setText("hero-title", "Unable to load depth chart data");
  setText("hero-copy", "The generated JSON payload is missing or invalid.");
});
