const state = {
  data: null,
  depthIndex: 0,
};

const depthButtons = Array.from(document.querySelectorAll("[data-depth]"));
const teamField = document.getElementById("team-field");
const coachOverlay = document.getElementById("coach-overlay");
const boardToolbar = document.getElementById("board-toolbar");
const playerModal = document.getElementById("player-modal");
const modalContent = document.getElementById("modal-content");
const modalTemplate = document.getElementById("player-modal-template");
const coachModalTemplate = document.getElementById("coach-modal-template");
const PORTRAIT_LAYOUTS = {
  offense: {
    "WR-X": { x: 8, y: 63 },
    "WR-SL": { x: 20, y: 77 },
    LT: { x: 18, y: 69 },
    LG: { x: 34, y: 69 },
    C: { x: 50, y: 69 },
    RG: { x: 66, y: 69 },
    RT: { x: 82, y: 69 },
    TE: { x: 80, y: 79 },
    QB: { x: 50, y: 83 },
    RB: { x: 62, y: 90 },
    "WR-Z": { x: 92, y: 63 },
  },
  defense: {
    FS: { x: 35, y: 23 },
    SS: { x: 65, y: 23 },
    WLB: { x: 40, y: 35 },
    MLB: { x: 60, y: 35 },
    NB: { x: 22, y: 43 },
    LDE: { x: 18, y: 47 },
    NT: { x: 40, y: 47 },
    DT: { x: 60, y: 47 },
    RDE: { x: 82, y: 47 },
    LCB: { x: 8, y: 39 },
    RCB: { x: 92, y: 39 },
  },
};
let lastPortraitMobile = false;

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

function isPortraitMobile() {
  return window.matchMedia("(max-width: 700px) and (orientation: portrait)").matches;
}

function activeLayout(side) {
  if (!state.data) return {};
  if (isPortraitMobile()) {
    return PORTRAIT_LAYOUTS[side];
  }
  return state.data.depthChart.layouts[side];
}

function formatRating(value) {
  if (value === null || value === undefined || value === "") return "--";
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric.toFixed(1) : "--";
}

function buildPlayerButton(player, position, coordinates, side) {
  const button = document.createElement("button");
  button.className = `field-player field-player--${side}`;
  button.style.left = `${coordinates.x}%`;
  button.style.top = `${coordinates.y}%`;
  button.innerHTML = `
    <div class="field-player__top">
      <span class="field-player__pos">${position}</span>
      <span class="field-player__rating">${formatRating(player.rating)}</span>
    </div>
    <h3 class="field-player__name">${player.name}</h3>
    <p class="field-player__meta">${player.class || player.eligibility || ""}</p>
  `;
  button.addEventListener("click", () => openPlayerModal(player));
  return button;
}

function renderRows(rows, layout, side) {
  rows.forEach((row) => {
    const playerId = row.playerIds[state.depthIndex];
    const player = state.data.players[playerId];
    if (!player) return;
    teamField.appendChild(
      buildPlayerButton(player, row.position, positionPoint(layout, row.position), side)
    );
  });
}

function buildToolbarPanel(label, value, detail) {
  return `
    <article class="board-panel">
      <span class="board-panel__label">${label}</span>
      <strong class="board-panel__value">${value}</strong>
      <span class="board-panel__detail">${detail}</span>
    </article>
  `;
}

function renderBoardToolbar() {
  if (!state.data || !boardToolbar) return;
  const offense = state.data.depthChart.styleSummary.offense;
  const defense = state.data.depthChart.styleSummary.defense;
  const depthLabel = ["Starters", "Second String", "Third String"][state.depthIndex];

  boardToolbar.innerHTML = [
    buildToolbarPanel("Team", state.data.team.name, "College football"),
    buildToolbarPanel(
      "Offense",
      offense.formation.label,
      `${offense.formation.percent}% • Run ${offense.runPass.run}% / Pass ${offense.runPass.pass}%`
    ),
    buildToolbarPanel(
      "Defense",
      defense.formation.label,
      `${defense.formation.percent}% • Run ${defense.runPass.run}% / Pass ${defense.runPass.pass}%`
    ),
    buildToolbarPanel("Depth", depthLabel, "Current lineup")
  ].join("");
}

function bindExpandableBio(fragment, fullBio, previewBio) {
  const bioElement = fragment.querySelector(".modal-card__bio");
  const toggle = fragment.querySelector(".bio-toggle");
  if (!bioElement || !toggle) return;

  const fallback = "Official bio not available from the current source set.";
  const fullText = (fullBio || "").trim() || fallback;
  const previewText =
    (previewBio || "").trim() ||
    (fullText.length > 420 ? `${fullText.slice(0, 420).trimEnd()}...` : fullText);
  const canExpand = previewText !== fullText;
  let expanded = !canExpand;

  const render = () => {
    bioElement.textContent = expanded ? fullText : previewText;
    toggle.hidden = !canExpand;
    if (canExpand) {
      toggle.textContent = expanded ? "Show less" : "Show full bio";
    }
  };

  toggle.addEventListener("click", () => {
    expanded = !expanded;
    render();
  });

  render();
}

function renderMetricCards(fragment, player) {
  const statGrid = fragment.querySelector(".stat-grid");
  statGrid.innerHTML = "";
  const cards = player.metricCards || [];
  if (!cards.length) {
    const chip = document.createElement("div");
    chip.className = "stat-chip";
    chip.innerHTML = `
      <span class="stat-chip__label">Overall Grade Profile</span>
      <strong class="stat-chip__value">Unavailable</strong>
      <span class="stat-chip__detail">No matching overall-grade source row for this player.</span>
    `;
    statGrid.appendChild(chip);
    return;
  }
  cards.forEach((stat) => {
    const chip = document.createElement("div");
    chip.className = "stat-chip";
    chip.innerHTML = `
      <span class="stat-chip__label">${stat.label}</span>
      <strong class="stat-chip__value">${stat.value}</strong>
      <span class="stat-chip__detail">${stat.detail || ""}</span>
    `;
    statGrid.appendChild(chip);
  });
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
  bindExpandableBio(fragment, player.bio, player.bioShort);
  const ratingLabel =
    player.ratingSource?.type === "csv"
      ? "Overall Grade"
      : player.ratingSource?.type === "missing"
        ? "No Overall Grade"
        : "Overall Grade";
  fragment.querySelector(".rating-pill span").textContent = ratingLabel;
  fragment.querySelector(".rating-pill strong").textContent = formatRating(player.rating);

  const badgeRow = fragment.querySelector(".badge-row");
  player.badges.forEach((badge) => {
    const pill = document.createElement("span");
    pill.className = "badge";
    pill.textContent = badge;
    badgeRow.appendChild(pill);
  });

  renderMetricCards(fragment, player);

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

function openCoachModal(coach) {
  const fragment = coachModalTemplate.content.cloneNode(true);
  fragment.querySelector(".modal-card__headshot").src =
    coach.headshot || state.data.team.logo;
  fragment.querySelector(".modal-card__headshot").alt = `${coach.name} headshot`;
  fragment.querySelector(".modal-card__depth").textContent = coach.role;
  fragment.querySelector(".modal-card__name").textContent = coach.name;
  fragment.querySelector(".modal-card__meta").textContent = "Texas A&M Football Staff";
  bindExpandableBio(fragment, coach.bio, coach.bioShort || coach.bio);

  const tendencyList = fragment.querySelector(".tendency-list");
  coach.tendencies.forEach((item) => {
    const pill = document.createElement("span");
    pill.className = "badge badge--soft";
    pill.textContent = item;
    tendencyList.appendChild(pill);
  });

  const linkRow = fragment.querySelector(".link-row");
  coach.tendencySources.forEach((source) => {
    const anchor = document.createElement("a");
    anchor.href = source.url;
    anchor.target = "_blank";
    anchor.rel = "noreferrer";
    anchor.className = "badge";
    anchor.textContent = source.label;
    linkRow.appendChild(anchor);
  });

  modalContent.innerHTML = "";
  modalContent.appendChild(fragment);
  playerModal.showModal();
}

function renderFields() {
  if (!state.data) return;
  teamField.innerHTML = "";
  renderRows(state.data.depthChart.defense, activeLayout("defense"), "defense");
  renderRows(state.data.depthChart.offense, activeLayout("offense"), "offense");
  renderBoardToolbar();
}

function handleViewportChange() {
  const portraitMobile = isPortraitMobile();
  if (portraitMobile === lastPortraitMobile) return;
  lastPortraitMobile = portraitMobile;
  renderFields();
}

function renderCoaches() {
  const coaches = Object.values(state.data.coaches);
  coachOverlay.innerHTML = "";
  coaches.forEach((coach) => {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "coach-card";
    card.innerHTML = `
      <div class="coach-card__header">
        <img class="coach-card__headshot" src="${coach.headshot || state.data.team.logo}" alt="${coach.name}" />
        <div>
          <h3 class="coach-card__name">${coach.name}</h3>
          <p class="coach-card__role">${coach.role}</p>
        </div>
      </div>
      <p class="coach-card__bio">${coach.tendencies[0] || ""}</p>
    `;
    card.addEventListener("click", () => openCoachModal(coach));
    coachOverlay.appendChild(card);
  });
}

async function init() {
  const response = await fetch("data/aggies.json", { cache: "no-store" });
  state.data = await response.json();

  document.title = "Texas A&M Depth Chart";
  setText("hero-title", "Texas A&M Depth Chart");
  document.getElementById("hero-logo").src = state.data.team.logo;
  document.getElementById("hero-logo").alt = `${state.data.team.shortName} logo`;
  lastPortraitMobile = isPortraitMobile();
  window.addEventListener("resize", handleViewportChange);

  renderFields();
  renderCoaches();
}

init().catch((error) => {
  console.error(error);
  setText("hero-title", "Unable to load depth chart data");
});
