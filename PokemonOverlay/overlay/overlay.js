const STATE_URL = "../tracker/state.json";
const CONFIG_URL = "../config.json";

const DEFAULT_CONFIG = {
  pollMs: 1000,
  theme: "default",
  spriteStyle: "auto",
  overlayScale: 1,
  pcBoxes: [],
  memorialBoxes: [],
  spriteOverrides: {},
};

const FETCH_TIMEOUT_MS = 1400;
const DISCONNECTED_AFTER_MS = 8000;
const DEBUG = true;

const partyGrid = document.getElementById("partyGrid");
const pcGrid = document.getElementById("pcGrid");
const deadGrid = document.getElementById("deadGrid");
const statusLine = document.getElementById("statusLine");
const statusStrip = document.getElementById("statusStrip");
const cardTemplate = document.getElementById("pokemonCardTemplate");
const LAYOUT_EDIT_QUERY_PARAM = "layoutEdit";

const FALLBACK_SPRITE_DATA_URI =
  "data:image/svg+xml;utf8," +
  encodeURIComponent(
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'><rect width='64' height='64' rx='8' fill='#0f1320'/><circle cx='32' cy='32' r='23' fill='#f44336'/><path d='M9 32h46' stroke='#111' stroke-width='6'/><circle cx='32' cy='32' r='11' fill='#f5f5f5' stroke='#111' stroke-width='4'/><circle cx='32' cy='32' r='4' fill='#111'/></svg>"
  );

let config = { ...DEFAULT_CONFIG };
let timerId = null;
let previousStateDigest = "";
let previousMonSignatures = new Map();
let isFirstSuccess = true;
let inFlight = false;
let lastSuccessAt = 0;

const spriteResolutionCache = new Map();
const spriteLoadPromiseCache = new Map();

const FORM_ALIAS_MAP = {
  AEGISLASH_BLADE: ["AEGISLASH_1"],
  AEGISLASH_SHIELD: ["AEGISLASH"],
  ARCEUS_FIRE: ["ARCEUS_12"],
  BASCULEGION_F: ["BASCULEGION_FEMALE"],
  FLABB: ["FLABEBE"],
};

function logDebug(...args) {
  if (!DEBUG) {
    return;
  }
  console.log("[overlay]", ...args);
}

function sanitizeArray(value) {
  return Array.isArray(value) ? value : [];
}

function normalizePokemon(raw, section, index) {
  const speciesId = Number(raw.species_id || 0);
  const species = String(raw.species || "missingno").toLowerCase();
  const nickname = String(raw.nickname || species || "Unknown");
  const level = raw.level == null ? null : Number(raw.level);
  const slot = Number(raw.slot || index + 1);
  const shiny = Boolean(raw.shiny);
  const gender = (raw.gender || "unknown").toLowerCase();
  const heldItem = raw.held_item || null;
  const box = raw.box == null ? null : Number(raw.box);
  const boxSlot = raw.box_slot == null ? null : Number(raw.box_slot);
  const currentHp = raw.current_hp == null ? null : Number(raw.current_hp);
  const maxHp = raw.max_hp == null ? null : Number(raw.max_hp);
  const status = raw.status ? String(raw.status).toUpperCase() : null;
  const types = sanitizeArray(raw.types).map((t) => String(t).toLowerCase());

  return {
    key: `${section}-${slot}`,
    species,
    speciesId,
    nickname,
    level,
    slot,
    shiny,
    gender,
    heldItem,
    box,
    boxSlot,
    currentHp,
    maxHp,
    status,
    types,
    section,
  };
}

function normalizeState(data) {
  const party = sanitizeArray(data.party).map((p, i) => normalizePokemon(p, "party", i));
  let pc = sanitizeArray(data.pc).map((p, i) => normalizePokemon(p, "pc", i));
  let dead = sanitizeArray(data.dead).map((p, i) => normalizePokemon(p, "dead", i));

  const pcBoxSet = new Set(config.pcBoxes || []);
  const memorialBoxSet = new Set(config.memorialBoxes || []);

  if (dead.length === 0 && memorialBoxSet.size > 0) {
    dead = pc
      .filter((mon) => mon.box != null && memorialBoxSet.has(mon.box))
      .map((mon) => ({ ...mon, section: "dead", key: `dead-${mon.box}-${mon.boxSlot}-${mon.slot}` }));
    pc = pc.filter((mon) => !(mon.box != null && memorialBoxSet.has(mon.box)));
  }

  if (pcBoxSet.size > 0) {
    const filteredPc = pc.filter((mon) => mon.box != null && pcBoxSet.has(mon.box));
    // If configured boxes are empty in parsed state, keep all parsed PC mons
    // so the overlay does not look broken while parser offsets are being tuned.
    if (filteredPc.length === 0 && pc.length > 0) {
      logDebug("Configured pc_boxes produced no matches; falling back to all parsed PC mons", {
        configuredBoxes: [...pcBoxSet],
        parsedPcCount: pc.length,
      });
    } else {
      pc = filteredPc;
    }
  }

  return { party, pc, dead };
}

function monSignature(mon) {
  return JSON.stringify([
    mon.species,
    mon.speciesId,
    mon.nickname,
    mon.level,
    mon.shiny,
    mon.heldItem,
    mon.gender,
    mon.currentHp,
    mon.maxHp,
    mon.status,
    (mon.types || []).join(","),
  ]);
}

function stateDigest(state) {
  return JSON.stringify(state);
}

function statusMode(text, mode) {
  statusLine.textContent = text;
  statusStrip.dataset.mode = mode;
}

function toSpriteNameBase(text) {
  return String(text || "")
    .trim()
    .replace(/\s+/g, "_")
    .replace(/-/g, "_")
    .replace(/[^a-zA-Z0-9_]/g, "");
}

function spriteNameCandidates(mon) {
  const out = [];
  const pushUnique = (value) => {
    if (!value || out.includes(value)) {
      return;
    }
    out.push(value);
  };

  const nameBase = toSpriteNameBase(mon.species);
  const isPlaceholderName = /^species_[0-9]+$/i.test(nameBase);

  const pushAliasVariants = (token) => {
    const key = String(token || "").toUpperCase();
    const aliases = FORM_ALIAS_MAP[key] || [];
    for (const alias of aliases) {
      pushUnique(alias);
      pushUnique(alias.toLowerCase());
      pushUnique(alias.replace(/_/g, ""));
      pushUnique(alias.replace(/_/g, "").toLowerCase());
    }
    // RR shorthand FLABB variants should map to existing FLABEBE assets.
    if (key === "FLABB" || key.startsWith("FLABB_")) {
      const flabebe = key.replace(/^FLABB/, "FLABEBE");
      pushUnique(flabebe);
      pushUnique(flabebe.toLowerCase());
      pushUnique(flabebe.replace(/_/g, ""));
      pushUnique(flabebe.replace(/_/g, "").toLowerCase());
    }
  };

  // If parser yields placeholder species names, prioritize numeric IDs first.
  if (isPlaceholderName) {
    pushUnique(String(mon.speciesId));
    pushUnique(String(mon.speciesId).padStart(3, "0"));
  }

  pushUnique(nameBase);
  pushUnique(nameBase.toUpperCase());
  pushUnique(nameBase.replace(/_/g, ""));
  pushUnique(nameBase.replace(/_/g, "").toUpperCase());
  pushAliasVariants(nameBase);

  const hint = config.spriteOverrides[String(mon.speciesId)] || config.spriteOverrides[mon.species];
  if (hint) {
    pushUnique(hint);
    pushUnique(hint.toUpperCase());
    pushUnique(hint.replace(/_/g, ""));
    pushUnique(hint.replace(/_/g, "").toUpperCase());
    pushAliasVariants(hint);
  }

  // Support prior numeric naming conventions where available.
  if (!isPlaceholderName) {
    pushUnique(String(mon.speciesId));
    pushUnique(String(mon.speciesId).padStart(3, "0"));
  }

  return out;
}

function spriteCandidates(mon) {
  const roots = [];

  if (mon.section === "pc") {
    roots.push(mon.shiny ? "../../Icons shiny" : "../../Icons");
    roots.push(mon.shiny ? "sprites/icons/shiny" : "sprites/icons");
  } else {
    // Party and memorial both use front sprites. Memorial visual washout is CSS.
    roots.push(mon.shiny ? "../../Front shiny" : "../../Front");
    if (config.spriteStyle === "icons") {
      roots.push(mon.shiny ? "../../Icons shiny" : "../../Icons");
      roots.push(mon.shiny ? "sprites/icons/shiny" : "sprites/icons");
    } else {
      roots.push(mon.shiny ? "sprites/shiny" : "sprites/normal");
    }
  }

  const candidates = [];
  const names = spriteNameCandidates(mon);
  for (const root of roots) {
    for (const name of names) {
      candidates.push(`${root}/${name}.png`);
    }
  }

  candidates.push("../../Front/000.png");
  candidates.push("sprites/icons/missingno.png");
  candidates.push("sprites/normal/missingno.png");
  candidates.push(FALLBACK_SPRITE_DATA_URI);
  return candidates;
}

function loadImage(url) {
  if (url.startsWith("data:image/")) {
    return Promise.resolve(url);
  }

  if (spriteLoadPromiseCache.has(url)) {
    return spriteLoadPromiseCache.get(url);
  }

  const promise = new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(url);
    img.onerror = () => reject(new Error(`missing sprite: ${url}`));
    img.src = url;
  });

  spriteLoadPromiseCache.set(url, promise);
  return promise;
}

async function resolveSpriteSource(mon) {
  const cacheKey = `${mon.section}|${mon.shiny}|${mon.species}|${mon.speciesId}|${config.spriteStyle}`;
  const cached = spriteResolutionCache.get(cacheKey);
  if (cached) {
    return cached;
  }

  const candidates = spriteCandidates(mon);
  for (const candidate of candidates) {
    try {
      const source = await loadImage(candidate);
      spriteResolutionCache.set(cacheKey, source);
      return source;
    } catch (_error) {
      logDebug("Sprite candidate failed", { species: mon.species, candidate });
    }
  }

  spriteResolutionCache.set(cacheKey, FALLBACK_SPRITE_DATA_URI);
  return FALLBACK_SPRITE_DATA_URI;
}

function updateCardVisual(node, mon) {
  node.classList.toggle("shiny", mon.shiny);
  node.classList.toggle("sprite-right", mon.section === "party" && mon.slot % 2 === 0);

  const levelText = mon.level == null ? "Lv ?" : `Lv ${mon.level}`;
  const heldText = mon.heldItem ? ` | Held: ${mon.heldItem}` : "";
  node.title = `${mon.nickname} (#${mon.speciesId}) ${levelText}${heldText}`;

  if (mon.section !== "party") {
    return;
  }

  const nameEl = node.querySelector(".party-name");
  const levelEl = node.querySelector(".party-level");
  const statusEl = node.querySelector(".party-status");
  const typesEl = node.querySelector(".party-types");
  const hpFill = node.querySelector(".party-hp-fill");
  const hpValue = node.querySelector(".party-hp-value");

  if (nameEl) {
    nameEl.textContent = mon.nickname;
  }
  if (levelEl) {
    levelEl.textContent = levelText;
  }
  if (statusEl) {
    statusEl.textContent = mon.status || "";
    statusEl.hidden = !mon.status;
  }

  if (typesEl) {
    const typeNodes = (mon.types || []).slice(0, 2).map((typeName) => {
      const chip = document.createElement("span");
      chip.className = `party-type type-${typeName.replace(/[^a-z0-9_-]/g, "")}`;
      chip.textContent = typeName.toUpperCase();
      return chip;
    });
    typesEl.replaceChildren(...typeNodes);
  }

  let hpPercent = 0;
  if (Number.isFinite(mon.currentHp) && Number.isFinite(mon.maxHp) && mon.maxHp > 0) {
    hpPercent = Math.max(0, Math.min(100, Math.round((mon.currentHp / mon.maxHp) * 100)));
  }
  if (hpPercent > 0) {
    hpPercent = Math.max(4, hpPercent);
  }
  const hpColor = hpPercent <= 25 ? "#e14e5d" : hpPercent <= 50 ? "#f2be42" : "#44d07a";
  if (hpFill) {
    hpFill.style.width = `${hpPercent}%`;
    hpFill.style.backgroundColor = hpColor;
  }
  if (hpValue) {
    if (Number.isFinite(mon.currentHp) && Number.isFinite(mon.maxHp)) {
      hpValue.textContent = `${mon.currentHp}/${mon.maxHp}`;
    } else {
      hpValue.textContent = "?/?";
    }
  }
}

async function setCardSprite(node, mon) {
  const sprite = node.querySelector(".sprite");
  const frame = node.querySelector(".sprite-frame");
  const resolvedSrc = await resolveSpriteSource(mon);
  if (node.dataset.signature !== monSignature(mon)) {
    // Card changed while async sprite lookup was running.
    return;
  }
  if (sprite.src !== resolvedSrc) {
    sprite.src = resolvedSrc;
  }
  // Icons packs can contain two side-by-side frames for idle animation.
  // Detect widescreen sprite sheets and enable alternating frame animation.
  const isIconSection = mon.section === "pc" || mon.section === "dead";
  if (isIconSection && sprite.naturalWidth > sprite.naturalHeight * 1.65) {
    sprite.dataset.twoFrame = "true";
    frame?.classList.add("two-frame");
  } else {
    delete sprite.dataset.twoFrame;
    frame?.classList.remove("two-frame");
  }
  sprite.alt = `${mon.nickname} sprite`;
}

function createCard(mon) {
  if (mon.section === "party") {
    const node = document.createElement("figure");
    node.className = "pokemon-token party-banner";
    node.innerHTML = `
      <div class="party-banner-inner">
        <span class="sprite-frame">
          <img class="sprite" alt="Pokemon sprite" />
        </span>
        <div class="party-info">
          <div class="party-topline">
            <div class="party-name-level">
              <span class="party-name"></span>
              <span class="party-level"></span>
            </div>
            <div class="party-types"></div>
          </div>
          <div class="party-meta-row">
            <span class="party-status" hidden></span>
          </div>
          <div class="party-hp-row">
            <div class="party-hp-track">
              <div class="party-hp-fill"></div>
            </div>
            <span class="party-hp-value"></span>
          </div>
        </div>
      </div>
    `;
    node.dataset.key = mon.key;
    node.dataset.signature = monSignature(mon);
    updateCardVisual(node, mon);
    setCardSprite(node, mon).catch((err) => {
      console.error("[overlay] Failed to set card sprite", err);
    });
    return node;
  }

  const node = cardTemplate.content.firstElementChild.cloneNode(true);
  node.dataset.key = mon.key;
  node.dataset.signature = monSignature(mon);
  node.classList.toggle("dead", mon.section === "dead");
  updateCardVisual(node, mon);
  setCardSprite(node, mon).catch((err) => {
    console.error("[overlay] Failed to set card sprite", err);
  });
  return node;
}

function updateCard(node, mon) {
  const signature = monSignature(mon);
  if (node.dataset.signature === signature) {
    return;
  }

  node.dataset.signature = signature;
  node.classList.toggle("dead", mon.section === "dead");
  updateCardVisual(node, mon);
  setCardSprite(node, mon).catch((err) => {
    console.error("[overlay] Failed to update card sprite", err);
  });
}

function getCurrentCardRects() {
  const cards = document.querySelectorAll(".pokemon-token[data-key]");
  const rects = new Map();
  cards.forEach((card) => {
    rects.set(card.dataset.key, card.getBoundingClientRect());
  });
  return rects;
}

function applyFlipAnimation(beforeRects, touchedKeys) {
  if (!touchedKeys.size) {
    return;
  }

  const cards = document.querySelectorAll(".pokemon-token[data-key]");
  cards.forEach((card) => {
    const key = card.dataset.key;
    if (!touchedKeys.has(key)) {
      return;
    }

    const oldRect = beforeRects.get(key);
    const newRect = card.getBoundingClientRect();

    if (!oldRect) {
      card.animate(
        [{ opacity: 0, transform: "scale(0.92) translateY(4px)" }, { opacity: 1, transform: "scale(1) translateY(0)" }],
        { duration: 200, easing: "ease-out" }
      );
      return;
    }

    const dx = oldRect.left - newRect.left;
    const dy = oldRect.top - newRect.top;

    if (Math.abs(dx) < 1 && Math.abs(dy) < 1) {
      return;
    }

    card.animate(
      [{ transform: `translate(${dx}px, ${dy}px)` }, { transform: "translate(0px, 0px)" }],
      { duration: 260, easing: "cubic-bezier(0.2, 0.85, 0.2, 1)" }
    );
  });
}

function renderSectionDiff(grid, mons) {
  const touchedKeys = new Set();
  const existing = new Map();
  grid.querySelectorAll(".pokemon-token[data-key]").forEach((node) => {
    existing.set(node.dataset.key, node);
  });

  const orderedNodes = [];
  for (const mon of mons) {
    let node = existing.get(mon.key);
    if (!node) {
      node = createCard(mon);
      touchedKeys.add(mon.key);
    } else {
      existing.delete(mon.key);
      updateCard(node, mon);
      const previousSignature = previousMonSignatures.get(mon.key);
      const currentSignature = monSignature(mon);
      if (previousSignature !== currentSignature) {
        touchedKeys.add(mon.key);
      }
    }
    orderedNodes.push(node);
  }

  for (const [key, staleNode] of existing.entries()) {
    touchedKeys.add(key);
    staleNode.remove();
  }

  orderedNodes.forEach((node, index) => {
    const currentAtIndex = grid.children[index];
    if (currentAtIndex !== node) {
      grid.insertBefore(node, currentAtIndex || null);
      touchedKeys.add(node.dataset.key || "");
    }
  });

  return touchedKeys;
}

function preloadSprites(state) {
  const allMons = [...state.party, ...state.pc, ...state.dead];
  allMons.forEach((mon) => {
    resolveSpriteSource(mon).catch((_error) => {
      // Best effort preload only.
    });
  });
}

function render(state) {
  const beforeRects = getCurrentCardRects();
  const touchedKeys = new Set();

  for (const key of renderSectionDiff(partyGrid, state.party)) {
    touchedKeys.add(key);
  }
  for (const key of renderSectionDiff(pcGrid, state.pc)) {
    touchedKeys.add(key);
  }
  for (const key of renderSectionDiff(deadGrid, state.dead)) {
    touchedKeys.add(key);
  }

  requestAnimationFrame(() => applyFlipAnimation(beforeRects, touchedKeys));

  const nextSignatures = new Map();
  [...state.party, ...state.pc, ...state.dead].forEach((mon) => {
    nextSignatures.set(mon.key, monSignature(mon));
  });
  previousMonSignatures = nextSignatures;
}

async function fetchWithTimeout(url) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
  try {
    const response = await fetch(url, {
      cache: "no-store",
      signal: controller.signal,
    });
    return response;
  } finally {
    clearTimeout(timeoutId);
  }
}

async function fetchState() {
  const bust = `t=${Date.now()}`;
  const response = await fetchWithTimeout(`${STATE_URL}?${bust}`);

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }

  const text = await response.text();
  try {
    return JSON.parse(text);
  } catch (parseError) {
    throw new Error(`Invalid JSON: ${parseError.message}`);
  }
}

function scheduleNextPoll() {
  if (timerId) {
    clearTimeout(timerId);
  }
  timerId = setTimeout(updateLoop, config.pollMs);
}

function initLayoutEditMode() {
  const params = new URLSearchParams(window.location.search);
  if (params.get(LAYOUT_EDIT_QUERY_PARAM) !== "1") {
    return;
  }

  const partyZone = document.querySelector(".party-zone");
  if (!partyZone) {
    return;
  }

  document.body.classList.add("layout-edit-mode");

  const editStyle = document.createElement("style");
  editStyle.textContent = `
    .layout-edit-mode .party-zone {
      pointer-events: auto;
      outline: 2px dashed rgba(0, 217, 255, 0.9);
      outline-offset: 2px;
      z-index: 20;
    }
    .layout-edit-mode .party-zone .edit-drag-handle {
      position: absolute;
      inset: 0;
      cursor: move;
      z-index: 30;
      pointer-events: auto;
      background: rgba(0, 210, 255, 0.08);
      border: 1px dashed rgba(0, 217, 255, 0.65);
    }
    .layout-edit-mode .party-zone .edit-drag-label {
      position: absolute;
      left: 8px;
      top: 8px;
      z-index: 32;
      pointer-events: none;
      background: rgba(9, 28, 37, 0.86);
      border: 1px solid rgba(0, 217, 255, 0.7);
      color: #e5f9ff;
      border-radius: 6px;
      padding: 3px 7px;
      font-size: 11px;
      letter-spacing: 0.03em;
      font-weight: 700;
    }
    .layout-edit-mode .party-zone .edit-resize-handle {
      position: absolute;
      right: -7px;
      bottom: -7px;
      width: 16px;
      height: 16px;
      background: #00d9ff;
      border: 2px solid #07222a;
      border-radius: 4px;
      cursor: nwse-resize;
      z-index: 31;
      pointer-events: auto;
    }
    .layout-edit-panel {
      position: fixed;
      left: 12px;
      top: 12px;
      width: min(380px, 48vw);
      max-height: 82vh;
      overflow: auto;
      padding: 10px;
      border-radius: 10px;
      border: 1px solid #2f5d6d;
      background: rgba(10, 16, 24, 0.93);
      color: #deeff8;
      font-family: "Segoe UI", Tahoma, sans-serif;
      z-index: 10000;
    }
    .layout-edit-panel h3 {
      margin: 0 0 8px;
      font-size: 14px;
      font-weight: 700;
    }
    .layout-edit-row {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 8px;
      align-items: center;
      margin-bottom: 6px;
      font-size: 12px;
    }
    .layout-edit-row input,
    .layout-edit-row select {
      width: 90px;
      background: #0f1a24;
      color: #d7edf7;
      border: 1px solid #305362;
      border-radius: 6px;
      padding: 3px 6px;
    }
    .layout-edit-row input[type="range"] {
      width: 100%;
      padding: 0;
    }
    .layout-edit-actions {
      display: flex;
      gap: 8px;
      margin-top: 8px;
    }
    .layout-edit-actions button {
      background: #12394a;
      border: 1px solid #2f6f86;
      color: #dff3fb;
      border-radius: 6px;
      padding: 5px 8px;
      cursor: pointer;
      font-size: 12px;
    }
    .layout-edit-output {
      margin-top: 8px;
      font-size: 11px;
      white-space: pre;
      padding: 8px;
      border-radius: 8px;
      background: #0a131b;
      border: 1px solid #264854;
      color: #b9d7e6;
    }
  `;
  document.head.appendChild(editStyle);

  const dragHandle = document.createElement("div");
  dragHandle.className = "edit-drag-handle";
  const dragLabel = document.createElement("div");
  dragLabel.className = "edit-drag-label";
  dragLabel.textContent = "Drag party area";
  const resizeHandle = document.createElement("div");
  resizeHandle.className = "edit-resize-handle";
  partyZone.appendChild(dragHandle);
  partyZone.appendChild(dragLabel);
  partyZone.appendChild(resizeHandle);

  const rootStyle = document.documentElement.style;
  const panel = document.createElement("aside");
  panel.className = "layout-edit-panel";
  panel.innerHTML = `
    <h3>Layout Edit Mode</h3>
    <div class="layout-edit-row"><label>Party Left %</label><input data-var="--party-zone-left" data-unit="%" type="number" step="0.1"></div>
    <div class="layout-edit-row"><label>Party Top %</label><input data-var="--party-zone-top" data-unit="%" type="number" step="0.1"></div>
    <div class="layout-edit-row"><label>Party Width %</label><input data-var="--party-zone-width" data-unit="%" data-expr="calc(%v% - 13px)" type="number" step="0.1"></div>
    <div class="layout-edit-row"><label>Party Height %</label><input data-var="--party-zone-height" data-unit="%" data-expr="calc(%v% - 13px)" type="number" step="0.1"></div>
    <div class="layout-edit-row"><label>Grid Gap px</label><input data-var="--party-grid-gap" data-unit="px" type="number" step="0.1"></div>
    <div class="layout-edit-row"><label>Sprite X px</label><input data-var="--party-sprite-x" data-unit="px" type="number" step="1"></div>
    <div class="layout-edit-row"><label>Sprite Y px</label><input data-var="--party-sprite-y" data-unit="px" type="number" step="1"></div>
    <div class="layout-edit-row"><label>Sprite Scale</label><input data-var="--party-sprite-scale" data-unit="" type="number" step="0.01"></div>
    <div class="layout-edit-row"><label>Right Sprite Right px</label><input data-var="--party-right-sprite-right" data-unit="px" type="number" step="1"></div>
    <div class="layout-edit-row"><label>Info Width px</label><input data-var="--party-info-width" data-unit="px" type="number" step="1"></div>
    <div class="layout-edit-row"><label>Sprite Size px</label><input data-var="--party-sprite-size" data-unit="px" type="number" step="1"></div>
    <div class="layout-edit-row"><label>Inner Gap px</label><input data-var="--party-inner-gap" data-unit="px" type="number" step="0.5"></div>
    <div class="layout-edit-row"><label>Info Pad Y px</label><input data-var="--party-info-pad-y" data-unit="px" type="number" step="0.5"></div>
    <div class="layout-edit-row"><label>Info Pad X px</label><input data-var="--party-info-pad-x" data-unit="px" type="number" step="0.5"></div>
    <div class="layout-edit-row"><label>Info Row Gap px</label><input data-var="--party-info-row-gap" data-unit="px" type="number" step="0.25"></div>
    <div class="layout-edit-row"><label>Info Offset X px</label><input data-var="--party-info-offset-x" data-unit="px" type="number" step="1"></div>
    <div class="layout-edit-row"><label>Info Offset Y px</label><input data-var="--party-info-offset-y" data-unit="px" type="number" step="1"></div>
    <div class="layout-edit-row"><label>Name Size px</label><input data-var="--party-name-size" data-unit="px" type="number" step="0.5"></div>
    <div class="layout-edit-row"><label>Level Size px</label><input data-var="--party-level-size" data-unit="px" type="number" step="0.5"></div>
    <div class="layout-edit-row"><label>Type Size px</label><input data-var="--party-type-size" data-unit="px" type="number" step="0.5"></div>
    <div class="layout-edit-row"><label>Status Size px</label><input data-var="--party-status-size" data-unit="px" type="number" step="0.5"></div>
    <div class="layout-edit-row"><label>HP Text Size px</label><input data-var="--party-hp-size" data-unit="px" type="number" step="0.5"></div>
    <div class="layout-edit-row"><label>Topline Gap px</label><input data-var="--party-topline-gap" data-unit="px" type="number" step="0.5"></div>
    <div class="layout-edit-row"><label>Types Gap px</label><input data-var="--party-types-gap" data-unit="px" type="number" step="0.5"></div>
    <div class="layout-edit-row"><label>Overlap Alpha</label><input data-var="--party-info-overlap-alpha" data-unit="" type="number" step="0.01"></div>
    <div class="layout-edit-row"><label>Panel Alpha</label><input data-var="--party-info-solid-alpha" data-unit="" type="number" step="0.01"></div>
    <div class="layout-edit-row"><label>Overlap Width px</label><input data-var="--party-info-overlap-width" data-unit="px" type="number" step="1"></div>
    <h3>Per Slot Sprite</h3>
    <div class="layout-edit-row">
      <label>Edit Slot</label>
      <select id="slotSpriteSelect">
        <option value="1">Slot 1</option>
        <option value="2">Slot 2</option>
        <option value="3">Slot 3</option>
        <option value="4">Slot 4</option>
        <option value="5">Slot 5</option>
        <option value="6">Slot 6</option>
      </select>
    </div>
    <div class="layout-edit-row"><label>Slot Sprite X px</label><input id="slotSpriteX" type="number" step="1"></div>
    <div class="layout-edit-row"><label>Slot Sprite Y px</label><input id="slotSpriteY" type="number" step="1"></div>
    <div class="layout-edit-row"><label>Slot Sprite Scale</label><input id="slotSpriteScale" type="number" step="0.01"></div>
    <div class="layout-edit-actions">
      <button data-action="copy">Copy Vars</button>
    </div>
    <pre class="layout-edit-output" id="layoutEditOutput"></pre>
  `;
  document.body.appendChild(panel);

  function getVarNumber(name) {
    const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    const calcMatch = value.match(/^calc\(([-0-9.]+)%\s*-\s*13px\)$/);
    if (calcMatch) {
      return Number(calcMatch[1]);
    }
    const num = Number(String(value).replace(/[^0-9.-]/g, ""));
    return Number.isFinite(num) ? num : 0;
  }

  function setVarValue(input) {
    const cssVar = input.dataset.var;
    if (!cssVar) {
      return;
    }
    const unit = input.dataset.unit || "";
    const expr = input.dataset.expr || "";
    const value = Number(input.value || 0);
    if (!Number.isFinite(value)) {
      return;
    }
    const formatted = expr ? expr.replace("%v", String(value)) : `${value}${unit}`;
    rootStyle.setProperty(cssVar, formatted);
    updateOutput();
  }

  function updateOutput() {
    const vars = [
      "--party-zone-left",
      "--party-zone-top",
      "--party-zone-width",
      "--party-zone-height",
      "--party-grid-gap",
      "--party-sprite-x",
      "--party-sprite-y",
      "--party-sprite-scale",
      "--party-right-sprite-right",
      "--party-info-width",
      "--party-sprite-size",
      "--party-inner-gap",
      "--party-info-pad-y",
      "--party-info-pad-x",
      "--party-info-row-gap",
      "--party-info-offset-x",
      "--party-info-offset-y",
      "--party-name-size",
      "--party-level-size",
      "--party-type-size",
      "--party-status-size",
      "--party-hp-size",
      "--party-topline-gap",
      "--party-types-gap",
      "--party-info-overlap-alpha",
      "--party-info-solid-alpha",
      "--party-info-overlap-width",
    ];
    for (let slot = 1; slot <= 6; slot += 1) {
      vars.push(`--party-slot${slot}-sprite-x`);
      vars.push(`--party-slot${slot}-sprite-y`);
      vars.push(`--party-slot${slot}-sprite-scale`);
    }
    const lines = [":root {"];
    for (const v of vars) {
      lines.push(`  ${v}: ${getComputedStyle(document.documentElement).getPropertyValue(v).trim()};`);
    }
    lines.push("}");
    const output = panel.querySelector("#layoutEditOutput");
    if (output) {
      output.textContent = lines.join("\n");
    }
  }

  panel.querySelectorAll("input[data-var]").forEach((input) => {
    const varName = input.dataset.var;
    input.value = String(getVarNumber(varName));
    input.addEventListener("input", () => setVarValue(input));
  });

  const slotSelect = panel.querySelector("#slotSpriteSelect");
  const slotSpriteX = panel.querySelector("#slotSpriteX");
  const slotSpriteY = panel.querySelector("#slotSpriteY");
  const slotSpriteScale = panel.querySelector("#slotSpriteScale");

  function slotVar(slot, axis) {
    return `--party-slot${slot}-sprite-${axis}`;
  }

  function getCssVarNumber(name, fallback) {
    const raw = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    if (!raw) {
      return fallback;
    }
    const value = Number(String(raw).replace(/[^0-9.-]/g, ""));
    return Number.isFinite(value) ? value : fallback;
  }

  function syncSlotInputs() {
    const slot = Number(slotSelect?.value || 1);
    if (slotSpriteX) {
      slotSpriteX.value = String(getCssVarNumber(slotVar(slot, "x"), 0));
    }
    if (slotSpriteY) {
      slotSpriteY.value = String(getCssVarNumber(slotVar(slot, "y"), 0));
    }
    if (slotSpriteScale) {
      slotSpriteScale.value = String(getCssVarNumber(slotVar(slot, "scale"), 1));
    }
  }

  function applySlotInputs() {
    const slot = Number(slotSelect?.value || 1);
    const x = Number(slotSpriteX?.value || 0);
    const y = Number(slotSpriteY?.value || 0);
    const scale = Number(slotSpriteScale?.value || 1);
    if (!Number.isFinite(slot) || slot < 1 || slot > 6) {
      return;
    }
    rootStyle.setProperty(slotVar(slot, "x"), `${Number.isFinite(x) ? x : 0}px`);
    rootStyle.setProperty(slotVar(slot, "y"), `${Number.isFinite(y) ? y : 0}px`);
    rootStyle.setProperty(slotVar(slot, "scale"), String(Number.isFinite(scale) ? scale : 1));
    updateOutput();
  }

  slotSelect?.addEventListener("change", syncSlotInputs);
  slotSpriteX?.addEventListener("input", applySlotInputs);
  slotSpriteY?.addEventListener("input", applySlotInputs);
  slotSpriteScale?.addEventListener("input", applySlotInputs);

  const copyButton = panel.querySelector('button[data-action="copy"]');
  copyButton?.addEventListener("click", async () => {
    const output = panel.querySelector("#layoutEditOutput")?.textContent || "";
    try {
      await navigator.clipboard.writeText(output);
      copyButton.textContent = "Copied";
      setTimeout(() => {
        copyButton.textContent = "Copy Vars";
      }, 800);
    } catch (_error) {
      copyButton.textContent = "Copy failed";
      setTimeout(() => {
        copyButton.textContent = "Copy Vars";
      }, 1000);
    }
  });

  let dragState = null;
  let resizeState = null;

  function beginDrag(ev) {
    ev.preventDefault();
    const rect = partyZone.getBoundingClientRect();
    dragState = {
      startX: ev.clientX,
      startY: ev.clientY,
      leftPx: rect.left,
      topPx: rect.top,
    };
    dragHandle.setPointerCapture(ev.pointerId);
  }

  function beginResize(ev) {
    ev.preventDefault();
    ev.stopPropagation();
    const rect = partyZone.getBoundingClientRect();
    resizeState = {
      startX: ev.clientX,
      startY: ev.clientY,
      widthPx: rect.width,
      heightPx: rect.height,
    };
    resizeHandle.setPointerCapture(ev.pointerId);
  }

  function onPointerMove(ev) {
    if (dragState) {
      const dx = ev.clientX - dragState.startX;
      const dy = ev.clientY - dragState.startY;
      const leftPct = ((dragState.leftPx + dx) / window.innerWidth) * 100;
      const topPct = ((dragState.topPx + dy) / window.innerHeight) * 100;
      rootStyle.setProperty("--party-zone-left", `${leftPct.toFixed(2)}%`);
      rootStyle.setProperty("--party-zone-top", `${topPct.toFixed(2)}%`);
      const leftInput = panel.querySelector('input[data-var="--party-zone-left"]');
      const topInput = panel.querySelector('input[data-var="--party-zone-top"]');
      if (leftInput) leftInput.value = leftPct.toFixed(2);
      if (topInput) topInput.value = topPct.toFixed(2);
      updateOutput();
    }

    if (resizeState) {
      const dx = ev.clientX - resizeState.startX;
      const dy = ev.clientY - resizeState.startY;
      const widthPct = ((Math.max(220, resizeState.widthPx + dx) / window.innerWidth) * 100);
      const heightPct = ((Math.max(220, resizeState.heightPx + dy) / window.innerHeight) * 100);
      rootStyle.setProperty("--party-zone-width", `calc(${widthPct.toFixed(2)}% - 13px)`);
      rootStyle.setProperty("--party-zone-height", `calc(${heightPct.toFixed(2)}% - 13px)`);
      const widthInput = panel.querySelector('input[data-var="--party-zone-width"]');
      const heightInput = panel.querySelector('input[data-var="--party-zone-height"]');
      if (widthInput) widthInput.value = widthPct.toFixed(2);
      if (heightInput) heightInput.value = heightPct.toFixed(2);
      updateOutput();
    }
  }

  function endPointer() {
    dragState = null;
    resizeState = null;
  }

  dragHandle.addEventListener("pointerdown", beginDrag);
  resizeHandle.addEventListener("pointerdown", beginResize);
  window.addEventListener("pointermove", onPointerMove);
  window.addEventListener("pointerup", endPointer);

  syncSlotInputs();
  updateOutput();
}

async function loadConfig() {
  try {
    const response = await fetchWithTimeout(`${CONFIG_URL}?t=${Date.now()}`);
    if (!response.ok) {
      return;
    }

    const payload = await response.json();
    const overlay = payload.overlay || {};
    const pollMs = Number(overlay.poll_interval_ms || DEFAULT_CONFIG.pollMs);
    const overlayScale = Number(overlay.overlay_scale || DEFAULT_CONFIG.overlayScale);

    config = {
      pollMs: Number.isFinite(pollMs) ? Math.max(300, pollMs) : DEFAULT_CONFIG.pollMs,
      theme: String(overlay.theme || DEFAULT_CONFIG.theme),
      spriteStyle: String(overlay.sprite_style || DEFAULT_CONFIG.spriteStyle),
      overlayScale: Number.isFinite(overlayScale) ? Math.max(0.5, Math.min(2, overlayScale)) : DEFAULT_CONFIG.overlayScale,
      pcBoxes: sanitizeArray(overlay.pc_boxes).map((n) => Number(n)).filter((n) => Number.isFinite(n) && n > 0),
      memorialBoxes: sanitizeArray(overlay.memorial_boxes).map((n) => Number(n)).filter((n) => Number.isFinite(n) && n > 0),
      spriteOverrides: typeof overlay.sprite_overrides === "object" && overlay.sprite_overrides
        ? overlay.sprite_overrides
        : DEFAULT_CONFIG.spriteOverrides,
    };

    document.documentElement.style.setProperty("--overlay-scale", String(config.overlayScale));
    document.documentElement.setAttribute("data-theme", config.theme);
    logDebug("Overlay config loaded", config);
  } catch (_error) {
    logDebug("Overlay config not loaded, using defaults");
  }
}

async function updateLoop() {
  if (inFlight) {
    scheduleNextPoll();
    return;
  }

  inFlight = true;
  try {
    const raw = await fetchState();
    const state = normalizeState(raw);
    const digest = stateDigest(state);

    if (!previousStateDigest) {
      statusMode("Connected. Loading save data...", "loading");
    }

    if (digest !== previousStateDigest) {
      previousStateDigest = digest;
      render(state);
      preloadSprites(state);
      statusMode(`Updated at ${new Date().toLocaleTimeString()}`, "ok");
      isFirstSuccess = false;
    } else if (state.party.length === 0 && state.pc.length === 0 && state.dead.length === 0) {
      statusMode("Connected. Waiting for save data...", "waiting");
    } else {
      statusMode("Connected. Waiting for next save update...", "ok");
    }

    lastSuccessAt = Date.now();
  } catch (error) {
    const now = Date.now();
    if (lastSuccessAt === 0 || now - lastSuccessAt > DISCONNECTED_AFTER_MS) {
      statusMode("Save disconnected. Waiting for tracker...", "disconnected");
    } else {
      statusMode("Transient read error. Retrying...", "warning");
    }
    console.error("[overlay] Update cycle error", error);
  } finally {
    inFlight = false;
    scheduleNextPoll();
  }
}

(async function bootstrap() {
  statusMode("Loading overlay...", "loading");
  initLayoutEditMode();
  await loadConfig();
  await updateLoop();
})();
