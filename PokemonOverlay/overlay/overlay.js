const STATE_URL = "../tracker/state.json";
const CONFIG_URL = "../config.json";

const DEFAULT_CONFIG = {
  pollMs: 1000,
  theme: "default",
  spriteStyle: "auto",
  overlayScale: 1,
  pcBoxes: [1],
  memorialBoxes: [25],
  spriteOverrides: {},
  websocket: {
    enabled: true,
    host: "127.0.0.1",
    port: 8765,
    reconnectMs: 1000,
  },
};

const FETCH_TIMEOUT_MS = 1400;
const DISCONNECTED_AFTER_MS = 8000;
const DEBUG = true;

const partyGrid = document.getElementById("partyGrid");
const pcGrid = document.getElementById("pcGrid");
const deadGrid = document.getElementById("deadGrid");
const overlayRoot = document.getElementById("overlayRoot");
const statusLine = document.getElementById("statusLine");
const statusStrip = document.getElementById("statusStrip");
const cardTemplate = document.getElementById("pokemonCardTemplate");
const pointsBadgeButton = document.getElementById("pointsBadgeButton");
const pointsBadgeValue = document.getElementById("pointsBadgeValue");
const LAYOUT_EDIT_QUERY_PARAM = "layoutEdit";
const LAYOUT_PRESET_STORAGE_KEY = "nuzlockeOverlay.layoutVars.v2";
const LAYOUT_EDIT_BASE_VARS = [
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
  "--pc-zone-left",
  "--pc-zone-top",
  "--pc-zone-width",
  "--pc-zone-height",
  "--pc-grid-gap",
  "--pc-row-overlap-y",
  "--memorial-zone-left",
  "--memorial-zone-top",
  "--memorial-zone-width",
  "--memorial-zone-height",
  "--memorial-columns",
  "--memorial-grid-gap",
  "--memorial-row-overlap-y",
  "--memorial-row1-y-offset",
  "--memorial-row2-y-offset",
  "--memorial-points-barrier-width",
  "--memorial-overlap-x",
  "--memorial-sprite-size",
  "--memorial-sprite-scale",
  "--points-badge-left",
  "--points-badge-bottom",
  "--points-badge-width",
  "--points-badge-height",
  "--points-count-single-x",
  "--points-count-single-y",
  "--points-count-double-x",
  "--points-count-double-y",
];

const FALLBACK_SPRITE_DATA_URI =
  "data:image/svg+xml;utf8," +
  encodeURIComponent(
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'><rect width='64' height='64' rx='8' fill='#0f1320'/><circle cx='32' cy='32' r='23' fill='#f44336'/><path d='M9 32h46' stroke='#111' stroke-width='6'/><circle cx='32' cy='32' r='11' fill='#f5f5f5' stroke='#111' stroke-width='4'/><circle cx='32' cy='32' r='4' fill='#111'/></svg>"
  );

let config = { ...DEFAULT_CONFIG };
let timerId = null;
let previousStateDigest = "";
let previousMonSignatures = new Map();
let lastSuccessAt = 0;
let ws = null;
let wsReconnectAttempts = 0;
let wsReconnectTimer = null;
let pollInFlight = false;
let wsFallbackPollingActive = false;
let pointsShopUi = null;
let pointsCommandSeq = 0;
const overlayClientId = (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function")
  ? crypto.randomUUID()
  : `overlay_${Date.now()}_${Math.random().toString(16).slice(2)}`;
const pendingPointsCommands = new Map();
const pcBoxCache = new Map();
let lastTrainerProfileKey = "";
const partyHpCacheByKey = new Map();

const spriteResolutionCache = new Map();
const spriteLoadPromiseCache = new Map();

const FORM_ALIAS_MAP = {
  AEGISLASH_BLADE: ["AEGISLASH_1"],
  AEGISLASH_SHIELD: ["AEGISLASH"],
  ARCEUS_FIRE: ["ARCEUS_12"],
  BASCULEGION_F: ["BASCULEGION_FEMALE"],
  FLABB: ["FLABEBE"],
};

// Fallbacks for form/species IDs that may not carry reliable gender metadata
// in live snapshots. Config overrides can still replace these when provided.
const SPECIES_ID_SPRITE_HINTS = {
  645: "frillish_female",
  646: "jellicent_female",
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

function getLayoutEditVarNames() {
  const vars = [...LAYOUT_EDIT_BASE_VARS];
  for (let slot = 1; slot <= 6; slot += 1) {
    vars.push(`--party-slot${slot}-sprite-x`);
    vars.push(`--party-slot${slot}-sprite-y`);
    vars.push(`--party-slot${slot}-sprite-scale`);
  }
  return vars;
}

function getLayoutVarsSnapshot() {
  const style = getComputedStyle(document.documentElement);
  const out = {};
  for (const varName of getLayoutEditVarNames()) {
    out[varName] = style.getPropertyValue(varName).trim();
  }
  return out;
}

function applyLayoutVarsToRoot(layoutVars) {
  if (!layoutVars || typeof layoutVars !== "object") {
    return false;
  }
  const rootStyle = document.documentElement.style;
  for (const [varName, varValue] of Object.entries(layoutVars)) {
    if (!String(varName).startsWith("--")) {
      continue;
    }
    rootStyle.setProperty(varName, String(varValue));
  }
  return true;
}

function loadSavedLayoutVarsFromLocalStorage() {
  try {
    const raw = localStorage.getItem(LAYOUT_PRESET_STORAGE_KEY);
    if (!raw) {
      return null;
    }
    const saved = JSON.parse(raw);
    return saved && typeof saved === "object" ? saved : null;
  } catch (_error) {
    return null;
  }
}

function persistLayoutVarsToLocalStorage(layoutVars) {
  try {
    localStorage.setItem(LAYOUT_PRESET_STORAGE_KEY, JSON.stringify(layoutVars));
    return true;
  } catch (_error) {
    return false;
  }
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

function sortPartyBySlot(party) {
  return [...party].sort((a, b) => {
    const aSlot = Number.isFinite(a.slot) ? a.slot : Number.MAX_SAFE_INTEGER;
    const bSlot = Number.isFinite(b.slot) ? b.slot : Number.MAX_SAFE_INTEGER;
    if (aSlot !== bSlot) {
      return aSlot - bSlot;
    }
    return String(a.nickname || "").localeCompare(String(b.nickname || ""));
  });
}

function hydratePartyHpFromCache(party) {
  for (const mon of party) {
    const key = String(mon.key || "");
    if (!key) {
      continue;
    }
    const hasHp = Number.isFinite(mon.currentHp) && Number.isFinite(mon.maxHp) && mon.maxHp > 0;
    if (hasHp) {
      partyHpCacheByKey.set(key, { currentHp: mon.currentHp, maxHp: mon.maxHp });
      continue;
    }
    const cached = partyHpCacheByKey.get(key);
    if (cached) {
      mon.currentHp = cached.currentHp;
      mon.maxHp = cached.maxHp;
    }
  }
}

function normalizeState(data) {
  const party = sortPartyBySlot(
    sanitizeArray(data.party).map((p, i) => normalizePokemon(p, "party", i))
  );
  hydratePartyHpFromCache(party);
  const incomingPc = sanitizeArray(data.pc).map((p, i) => normalizePokemon(p, "pc", i));
  const sharedCachedPc = sanitizeArray(data.pc_cached).map((p, i) => normalizePokemon(p, "pc", i));
  let pc = incomingPc;
  let dead = sanitizeArray(data.dead).map((p, i) => normalizePokemon(p, "dead", i));
  let usedPcFallback = false;

  const pcBoxSet = new Set(config.pcBoxes || []);

  // Prefer tracker-shared cache so all browser clients (OBS + VS) render the
  // same box composition. Keep per-browser cache as fallback for older tracker
  // payloads that don't include pc_cached yet.
  let sourcePc = [];
  if (sharedCachedPc.length > 0) {
    sourcePc = sharedCachedPc;
  } else {
    const seenIncomingBoxes = new Set(
      incomingPc
        .map((mon) => mon.box)
        .filter((box) => Number.isFinite(box) && box > 0)
    );

    for (const box of seenIncomingBoxes) {
      for (const key of [...pcBoxCache.keys()]) {
        if (key.startsWith(`${box}:`)) {
          pcBoxCache.delete(key);
        }
      }
    }

    for (const mon of incomingPc) {
      if (!Number.isFinite(mon.box) || mon.box <= 0 || !Number.isFinite(mon.boxSlot) || mon.boxSlot <= 0) {
        continue;
      }
      pcBoxCache.set(`${mon.box}:${mon.boxSlot}`, { ...mon, section: "pc" });
    }

    sourcePc = [...pcBoxCache.values()].sort((a, b) => {
      if ((a.box || 0) !== (b.box || 0)) {
        return (a.box || 0) - (b.box || 0);
      }
      return (a.boxSlot || 0) - (b.boxSlot || 0);
    });
  }

  if (sourcePc.length > 0) {
    if (pcBoxSet.size > 0) {
      const configuredPc = sourcePc
        .filter((mon) => mon.box != null && pcBoxSet.has(mon.box))
        .map((mon) => ({ ...mon, key: `pc-${mon.box}-${mon.boxSlot}` }));

      if (configuredPc.length > 0) {
        pc = configuredPc;
      } else if (incomingPc.length > 0) {
        // Keep PC visible if the configured box has not been observed yet.
        // This prevents an empty PC panel after startup/restart.
        usedPcFallback = true;
        pc = incomingPc.map((mon, idx) => ({
          ...mon,
          key: `pc-fallback-${mon.box || 0}-${mon.boxSlot || idx + 1}`,
        }));
      } else {
        pc = [];
      }
    } else {
      pc = sourcePc.map((mon) => ({ ...mon, key: `pc-${mon.box}-${mon.boxSlot}` }));
    }

  }

  if (!usedPcFallback && pcBoxSet.size > 0) {
    const filteredPc = pc.filter((mon) => mon.box != null && pcBoxSet.has(mon.box));
    pc = filteredPc;
  }

  return { party, pc, dead };
}

function trainerProfileKeyFromRaw(data) {
  const meta = data && typeof data === "object" && data.meta && typeof data.meta === "object"
    ? data.meta
    : {};
  const explicit = String(meta.trainer_profile_key || "").trim();
  if (explicit) {
    return explicit;
  }
  const publicId = Number(meta.trainer_public_id);
  const secretId = Number(meta.trainer_secret_id);
  if (Number.isFinite(publicId) && Number.isFinite(secretId)) {
    return `${Math.max(0, Math.trunc(publicId))}-${Math.max(0, Math.trunc(secretId))}`;
  }
  const trainerId = String(meta.trainer_id || "").trim();
  return trainerId;
}

function purchaseLockedInBattleFromRaw(data) {
  const meta = data && typeof data === "object" && data.meta && typeof data.meta === "object"
    ? data.meta
    : {};

  const booleanKeys = [
    "in_battle",
    "is_in_battle",
    "battle_active",
    "battle_locked",
    "is_battle",
  ];
  for (const key of booleanKeys) {
    const value = meta[key];
    if (typeof value === "boolean") {
      return value;
    }
    if (typeof value === "number") {
      return value !== 0;
    }
    if (typeof value === "string") {
      const normalized = value.trim().toLowerCase();
      if (["1", "true", "yes", "on"].includes(normalized)) {
        return true;
      }
      if (["0", "false", "no", "off"].includes(normalized)) {
        return false;
      }
    }
  }

  const textKeys = ["game_state", "state", "mode", "scene"];
  for (const key of textKeys) {
    const value = String(meta[key] || "").trim().toLowerCase();
    if (value.includes("battle")) {
      return true;
    }
  }

  return false;
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

function applyPointsState(pointsState) {
  if (!pointsState || typeof pointsState !== "object") {
    return;
  }

  logDebug("points_update_incoming", {
    points: Number(pointsState.current_points || 0),
    inventory_count: Array.isArray(pointsState.inventory) ? pointsState.inventory.length : 0,
    transaction_count: Array.isArray(pointsState.transactions) ? pointsState.transactions.length : 0,
  });

  if (pointsBadgeValue) {
    pointsBadgeValue.textContent = String(pointsState.current_points || 0);
  }

  if (pointsShopUi) {
    pointsShopUi.setState(pointsState);
  }
}

async function sendPointsCommand(command, payload) {
  if (!ws || ws.readyState !== WebSocket.OPEN) {
    return {
      ok: false,
      message: "Live tracker connection is required for points actions.",
    };
  }

  pointsCommandSeq += 1;
  const requestId = `points_${Date.now()}_${pointsCommandSeq}`;
  const message = {
    type: "points_shop_command",
    request_id: requestId,
    command,
    payload,
  };

  const waiter = new Promise((resolve) => {
    pendingPointsCommands.set(requestId, {
      resolve,
      timeoutId: setTimeout(() => {
        pendingPointsCommands.delete(requestId);
        resolve({ ok: false, message: "Points command timed out." });
      }, 4500),
    });
  });

  try {
    ws.send(JSON.stringify(message));
  } catch (_error) {
    const pending = pendingPointsCommands.get(requestId);
    if (pending) {
      clearTimeout(pending.timeoutId);
      pendingPointsCommands.delete(requestId);
      pending.resolve({ ok: false, message: "Failed to send points command." });
    }
  }

  return waiter;
}

async function sendPointsUiCommand(command, payload) {
  const uiPayload = payload && typeof payload === "object" ? payload : {};
  return sendPointsCommand(command, {
    source_client_id: overlayClientId,
    timestamp: Date.now(),
    ...uiPayload,
  });
}

function applyOverlayUiState(overlayUi, source) {
  if (!pointsShopUi || !overlayUi || typeof overlayUi !== "object") {
    return;
  }
  pointsShopUi.applyOverlayUiState(overlayUi, source);
}

function initPointsShopUi() {
  if (!overlayRoot || !pointsBadgeButton || !pointsBadgeValue || typeof window.PointsShopUI !== "function") {
    return;
  }

  if (pointsShopUi) {
    return;
  }

  pointsShopUi = new window.PointsShopUI({
    root: overlayRoot,
    badgeButton: pointsBadgeButton,
    badgeValue: pointsBadgeValue,
    onCommand: sendPointsCommand,
    onUiCommand: sendPointsUiCommand,
    log: (event, fields) => logDebug(event, fields),
  });
}

function statusMode(text, mode) {
  statusLine.textContent = text;
  statusStrip.dataset.mode = mode;
}

function statusClassFromCode(statusCode) {
  const code = String(statusCode || "").toUpperCase();
  if (!code) {
    return "";
  }

  if (code === "PAR" || code === "PLZ") {
    return "par";
  }
  if (code === "SLP") {
    return "slp";
  }
  if (code === "PSN") {
    return "psn";
  }
  if (code === "TOX") {
    return "tox";
  }
  if (code === "FRZ") {
    return "frz";
  }
  if (code === "BRN") {
    return "brn";
  }
  if (code === "FNT") {
    return "fnt";
  }
  return "other";
}

function isFaintedPartyMon(mon) {
  if (!Number.isFinite(mon.currentHp)) {
    return false;
  }

  if (Number.isFinite(mon.maxHp) && mon.maxHp <= 0) {
    return false;
  }

  return mon.currentHp <= 0;
}

function toSpriteNameBase(text) {
  return String(text || "")
    .trim()
    .replace(/\s+/g, "_")
    .replace(/-/g, "_")
    .replace(/[^a-zA-Z0-9_]/g, "");
}

function getSpriteHint(mon) {
  const configHint = config.spriteOverrides[String(mon.speciesId)] || config.spriteOverrides[mon.species];
  if (configHint) {
    return configHint;
  }

  const idHint = SPECIES_ID_SPRITE_HINTS[Number(mon.speciesId)];
  if (idHint) {
    return idHint;
  }

  return null;
}

function spriteNameCandidates(mon) {
  const out = [];
  const pushUnique = (value) => {
    if (!value || out.includes(value)) {
      return;
    }
    out.push(value);
  };

  let nameBase = toSpriteNameBase(mon.species);
  if (nameBase.toUpperCase() === "FLABB" || nameBase.toUpperCase().startsWith("FLABB_")) {
    nameBase = nameBase.replace(/^FLABB/i, "FLABEBE");
  }
  const isPlaceholderName = /^species_[0-9]+$/i.test(nameBase);
  const gender = String(mon.gender || "").toLowerCase();
  const hint = getSpriteHint(mon);

  const pushFemaleVariants = (token) => {
    if (gender !== "female") {
      return;
    }

    const base = toSpriteNameBase(token);
    if (!base) {
      return;
    }

    const upper = base.toUpperCase();
    const lower = base.toLowerCase();
    const compactUpper = upper.replace(/_/g, "");
    const compactLower = lower.replace(/_/g, "");

    // Prefer explicit female forms first so shared species names do not
    // resolve to the default male/base sprite when a female sprite exists.
    pushUnique(`${upper}_female`);
    pushUnique(`${lower}_female`);
    pushUnique(`${upper}_F`);
    pushUnique(`${lower}_f`);
    pushUnique(`${compactUpper}_female`);
    pushUnique(`${compactLower}_female`);
    pushUnique(`${compactUpper}_F`);
    pushUnique(`${compactLower}_f`);
  };

  const pushAliasVariants = (token) => {
    const key = String(token || "").toUpperCase();
    const aliases = FORM_ALIAS_MAP[key] || [];
    for (const alias of aliases) {
      pushFemaleVariants(alias);
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

  // Placeholder names like species_832 come from memory bridge snapshots.
  // Keep lookup short to avoid a flood of failed sprite URL probes.
  if (isPlaceholderName) {
    if (hint) {
      pushFemaleVariants(hint);
      pushUnique(hint);
      pushUnique(String(hint).toUpperCase());
    }

    pushUnique(String(mon.speciesId));
    pushUnique(String(mon.speciesId).padStart(3, "0"));

    return out;
  }

  // Explicit overrides should win over generic species names.
  if (hint) {
    pushFemaleVariants(hint);
    pushUnique(hint);
    pushUnique(hint.toUpperCase());
    pushUnique(hint.replace(/_/g, ""));
    pushUnique(hint.replace(/_/g, "").toUpperCase());
    pushAliasVariants(hint);
  }

  pushFemaleVariants(nameBase);
  pushUnique(nameBase);
  pushUnique(nameBase.toUpperCase());
  pushUnique(nameBase.replace(/_/g, ""));
  pushUnique(nameBase.replace(/_/g, "").toUpperCase());
  pushAliasVariants(nameBase);

  // Support prior numeric naming conventions where available.
  if (!isPlaceholderName) {
    pushUnique(String(mon.speciesId));
    pushUnique(String(mon.speciesId).padStart(3, "0"));
  }

  return out;
}

function buildSpriteCandidates(mon, roots, tails) {
  const candidates = [];
  const names = spriteNameCandidates(mon);
  for (const root of roots) {
    for (const name of names) {
      candidates.push(`${root}/${name}.png`);
    }
  }
  return [...candidates, ...tails];
}

function resolvePartyCandidates(mon) {
  const roots = [mon.shiny ? "../../Front shiny" : "../../Front", "sprites/normal"];
  if (mon.shiny) {
    roots.push("sprites/shiny");
  }
  return buildSpriteCandidates(mon, roots, ["../../Front/000.png", "sprites/normal/missingno.png", FALLBACK_SPRITE_DATA_URI]);
}

function resolvePcCandidates(mon) {
  const roots = [mon.shiny ? "../../Icons shiny" : "../../Icons", mon.shiny ? "sprites/icons/shiny" : "sprites/icons"];
  return buildSpriteCandidates(mon, roots, ["sprites/icons/missingno.png", FALLBACK_SPRITE_DATA_URI]);
}

function resolveMemorialCandidates(mon) {
  const roots = [];
  if (mon.shiny) {
    roots.push("../../Front shiny");
    roots.push("sprites/shiny");
  }
  roots.push("../../Front");
  roots.push("sprites/normal");
  return buildSpriteCandidates(mon, roots, ["../../Front/000.png", "sprites/normal/missingno.png", FALLBACK_SPRITE_DATA_URI]);
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

async function resolveSpriteSource(mon, candidates, resolverTag) {
  const cacheKey = [
    resolverTag,
    mon.section,
    mon.shiny,
    mon.species,
    mon.speciesId,
    mon.gender,
    getSpriteHint(mon) || "",
    config.spriteStyle,
  ].join("|");
  const cached = spriteResolutionCache.get(cacheKey);
  if (cached) {
    return cached;
  }

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

async function resolvePartySprite(mon) {
  return resolveSpriteSource(mon, resolvePartyCandidates(mon), "party");
}

async function resolvePcIconSprite(mon) {
  return resolveSpriteSource(mon, resolvePcCandidates(mon), "pc");
}

async function resolveMemorialSprite(mon) {
  const source = await resolveSpriteSource(mon, resolveMemorialCandidates(mon), "memorial");
  logDebug("memorial sprite resolved", { species: mon.species, src: source });
  return source;
}

function updateCardVisual(node, mon) {
  node.classList.toggle("shiny", mon.shiny);
  node.classList.toggle("sprite-right", mon.section === "party" && mon.slot % 2 === 0);
  if (mon.section === "party") {
    const normalizedSlot = Math.max(1, Math.min(6, Math.trunc(Number(mon.slot) || 1)));
    node.style.setProperty("--slot-sprite-x", `var(--party-slot${normalizedSlot}-sprite-x)`);
    node.style.setProperty("--slot-sprite-y", `var(--party-slot${normalizedSlot}-sprite-y)`);
    node.style.setProperty("--slot-sprite-scale", `var(--party-slot${normalizedSlot}-sprite-scale)`);
  } else {
    node.style.removeProperty("--slot-sprite-x");
    node.style.removeProperty("--slot-sprite-y");
    node.style.removeProperty("--slot-sprite-scale");
  }

  const levelText = mon.level == null ? "Lv ?" : `Lv ${mon.level}`;
  const heldText = mon.heldItem ? ` | Held: ${mon.heldItem}` : "";
  node.title = `${mon.nickname} (#${mon.speciesId}) ${levelText}${heldText}`;

  if (mon.section !== "party") {
    return;
  }

  const fainted = isFaintedPartyMon(mon);
  node.classList.toggle("fainted", fainted);

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
    const statusCode = mon.status ? String(mon.status).toUpperCase() : "";
    const statusClass = statusClassFromCode(statusCode);
    statusEl.className = "party-status";
    if (statusClass) {
      statusEl.classList.add(`status-${statusClass}`);
    }
    statusEl.textContent = statusCode;
    statusEl.hidden = !statusCode;
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
  const resolvedSrc = mon.section === "party"
    ? await resolvePartySprite(mon)
    : mon.section === "pc"
      ? await resolvePcIconSprite(mon)
      : await resolveMemorialSprite(mon);
  if (node.dataset.signature !== monSignature(mon)) {
    // Card changed while async sprite lookup was running.
    return;
  }
  if (sprite.src !== resolvedSrc) {
    sprite.src = resolvedSrc;
  }

  // Icon sheets in this setup are typically 2:1 (two 64x64 frames in one PNG).
  // Apply two-frame mode after the DOM image has fully loaded to avoid race conditions
  // that can briefly render both frames squeezed together.
  const applyTwoFrameMode = () => {
    const isIconSection = mon.section === "pc";
    const w = Number(sprite.naturalWidth || 0);
    const h = Number(sprite.naturalHeight || 0);
    const ratio = h > 0 ? w / h : 0;
    const isTwoFrameSheet = isIconSection && ratio >= 1.95 && ratio <= 2.05;
    if (isTwoFrameSheet) {
      sprite.dataset.twoFrame = "true";
      frame?.classList.add("two-frame");
    } else {
      delete sprite.dataset.twoFrame;
      frame?.classList.remove("two-frame");
    }
  };

  if (sprite.complete && sprite.naturalWidth > 0) {
    applyTwoFrameMode();
  } else {
    sprite.addEventListener("load", applyTwoFrameMode, { once: true });
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
  if (mon.section === "dead") {
    logDebug("memorial node created", { key: mon.key, species: mon.species, nickname: mon.nickname });
  }
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

function parseCssNumericValue(raw, fallback = 0) {
  const value = Number(String(raw || "").replace(/[^0-9.-]/g, ""));
  return Number.isFinite(value) ? value : fallback;
}

function applyMemorialTokenLayout() {
  if (!deadGrid) {
    return;
  }

  const tokens = Array.from(deadGrid.querySelectorAll(".pokemon-token[data-key]"));
  if (!tokens.length) {
    return;
  }

  const rootComputed = getComputedStyle(document.documentElement);
  const configuredColumns = parseCssNumericValue(rootComputed.getPropertyValue("--memorial-columns"), 10);
  const columns = Math.max(1, Math.round(configuredColumns));

  tokens.forEach((token, index) => {
    const columnIndex = index % columns;
    const rowIndex = Math.floor(index / columns);

    token.style.setProperty(
      "--memorial-runtime-margin-left",
      columnIndex === 0 ? "0px" : "calc(var(--memorial-overlap-x) * -1)"
    );

    if (rowIndex <= 0) {
      token.style.setProperty("--memorial-runtime-translate-y", "var(--memorial-row1-y-offset)");
    } else {
      token.style.setProperty("--memorial-runtime-translate-y", "var(--memorial-row2-y-offset)");
    }
  });
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
  logDebug("memorial render count", { count: state.dead.length });

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

  applyMemorialTokenLayout();

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
  if (!wsFallbackPollingActive && config.websocket?.enabled) {
    return;
  }
  if (timerId) {
    clearTimeout(timerId);
  }
  timerId = setTimeout(runPollingUpdate, config.pollMs);
}

function clearReconnectTimer() {
  if (wsReconnectTimer) {
    clearTimeout(wsReconnectTimer);
    wsReconnectTimer = null;
  }
}

function applyIncomingRawState(raw, source) {
  if (pointsShopUi && typeof pointsShopUi.setPurchaseLockDuringBattle === "function") {
    pointsShopUi.setPurchaseLockDuringBattle(purchaseLockedInBattleFromRaw(raw));
  }

  applyPointsState(raw?.points_shop);
  applyOverlayUiState(raw?.overlay_ui, source);

  const incomingProfileKey = trainerProfileKeyFromRaw(raw || {});
  if (incomingProfileKey && lastTrainerProfileKey && incomingProfileKey !== lastTrainerProfileKey) {
    pcBoxCache.clear();
    partyHpCacheByKey.clear();
  }
  if (incomingProfileKey) {
    lastTrainerProfileKey = incomingProfileKey;
  }

  const state = normalizeState(raw);
  const digest = stateDigest(state);

  if (!previousStateDigest) {
    statusMode("Connected. Loading save data...", "loading");
  }

  if (digest !== previousStateDigest) {
    previousStateDigest = digest;
    render(state);
    preloadSprites(state);
    statusMode(`Updated via ${source} at ${new Date().toLocaleTimeString()}`, "ok");
  } else if (state.party.length === 0 && state.pc.length === 0 && state.dead.length === 0) {
    statusMode("Connected. Waiting for save data...", "waiting");
  } else {
    statusMode("Connected. Waiting for next save update...", "ok");
  }

  lastSuccessAt = Date.now();
}

async function runPollingUpdate() {
  if (pollInFlight) {
    scheduleNextPoll();
    return;
  }

  pollInFlight = true;
  try {
    const raw = await fetchState();
    applyIncomingRawState(raw, "JSON");
  } catch (error) {
    const now = Date.now();
    if (lastSuccessAt === 0 || now - lastSuccessAt > DISCONNECTED_AFTER_MS) {
      statusMode("Save disconnected. Waiting for tracker...", "disconnected");
    } else {
      statusMode("Transient read error. Retrying...", "warning");
    }
    console.error("[overlay] Polling update error", error);
  } finally {
    pollInFlight = false;
    scheduleNextPoll();
  }
}

function closeSocket() {
  if (!ws) {
    return;
  }
  try {
    ws.onopen = null;
    ws.onmessage = null;
    ws.onerror = null;
    ws.onclose = null;
    ws.close();
  } catch (_error) {
    // Best effort close only.
  }
  ws = null;
}

function scheduleReconnect() {
  clearReconnectTimer();
  wsReconnectAttempts += 1;
  const baseDelay = Math.max(250, Number(config.websocket?.reconnectMs || 1000));
  const delay = Math.min(10000, Math.round(baseDelay * Math.pow(1.65, Math.min(wsReconnectAttempts, 6))));
  statusMode(`Live feed disconnected. Reconnecting in ${delay}ms...`, "disconnected");
  wsFallbackPollingActive = true;
  scheduleNextPoll();

  wsReconnectTimer = setTimeout(() => {
    connectWebSocket();
  }, delay);
}

function connectWebSocket() {
  closeSocket();

  const host = config.websocket?.host || "127.0.0.1";
  const port = Number(config.websocket?.port || 8765);
  const url = `ws://${host}:${port}`;

  statusMode("Connecting to live tracker feed...", "loading");
  try {
    ws = new WebSocket(url);
  } catch (error) {
    console.error("[overlay] WebSocket constructor failed", error);
    scheduleReconnect();
    return;
  }

  ws.onopen = () => {
    wsReconnectAttempts = 0;
    clearReconnectTimer();
    wsFallbackPollingActive = false;
    if (timerId) {
      clearTimeout(timerId);
      timerId = null;
    }
    statusMode("Connected to live tracker feed.", "ok");
    logDebug("WebSocket connected", { url });
    sendPointsCommand("get_state", {}).catch((_error) => {
      // Best effort refresh; websocket state_update still drives the overlay.
    });
  };

  ws.onmessage = (event) => {
    let payload = null;
    try {
      payload = JSON.parse(event.data);
    } catch (error) {
      console.error("[overlay] Invalid websocket payload", error);
      return;
    }

    if (!payload || typeof payload !== "object") {
      return;
    }

    if (payload.type === "points_shop_response") {
      logDebug("points_ws_response", {
        request_id: String(payload.request_id || ""),
        command: String(payload.command || ""),
        ok: Boolean(payload.ok),
      });
      const requestId = String(payload.request_id || "");
      const pending = pendingPointsCommands.get(requestId);
      if (pending) {
        clearTimeout(pending.timeoutId);
        pendingPointsCommands.delete(requestId);
        pending.resolve(payload);
      }
      if (payload.state) {
        applyPointsState(payload.state);
      }
      if (payload.overlay_ui) {
        applyOverlayUiState(payload.overlay_ui, "points_shop_response");
      }
      return;
    }

    if (payload.type === "points_shop_update") {
      logDebug("points_ws_update", {
        points: Number((payload.state || {}).current_points || 0),
      });
      applyPointsState(payload.state);
      if (payload.overlay_ui) {
        applyOverlayUiState(payload.overlay_ui, "points_shop_update");
      }
      return;
    }

    if (payload.type === "overlay_ui_update") {
      applyOverlayUiState(payload.overlay_ui, "overlay_ui_update");
      return;
    }

    if (payload.type === "state_update" && payload.state) {
      applyIncomingRawState(payload.state, "WebSocket");
      return;
    }

    if (payload.type === "tracker_status") {
      const status = String(payload.status || "").toLowerCase();
      const message = String(payload.message || "Tracker status update");
      const lowerMessage = message.toLowerCase();
      if (
        lowerMessage.includes("pc/memorial sync waiting for valid save updates") ||
        lowerMessage.includes("save reconcile unavailable")
      ) {
        return;
      }
      if (status === "ok") {
        statusMode(message, "ok");
      } else if (status === "warning") {
        statusMode(message, "warning");
      } else if (status === "error") {
        statusMode(message, "disconnected");
      }
      return;
    }

    if (payload.type === "heartbeat") {
      lastSuccessAt = Date.now();
    }
  };

  ws.onerror = (error) => {
    console.error("[overlay] WebSocket error", error);
  };

  ws.onclose = () => {
    ws = null;
    scheduleReconnect();
  };
}

function startDataPipeline() {
  if (config.websocket?.enabled) {
    wsFallbackPollingActive = true;
    scheduleNextPoll();
    connectWebSocket();
    return;
  }

  wsFallbackPollingActive = true;
  statusMode("WebSocket disabled. Using JSON polling fallback...", "waiting");
  runPollingUpdate();
}

window.addEventListener("beforeunload", () => {
  clearReconnectTimer();
  if (timerId) {
    clearTimeout(timerId);
  }

  for (const pending of pendingPointsCommands.values()) {
    clearTimeout(pending.timeoutId);
    pending.resolve({ ok: false, message: "Overlay shutting down." });
  }
  pendingPointsCommands.clear();

  closeSocket();
});

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
      flex-wrap: wrap;
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
    <h3>PC Layout Edit</h3>
    <div class="layout-edit-row"><label>PC Left %</label><input data-var="--pc-zone-left" data-unit="%" type="number" step="0.1"></div>
    <div class="layout-edit-row"><label>PC Top %</label><input data-var="--pc-zone-top" data-unit="%" type="number" step="0.1"></div>
    <div class="layout-edit-row"><label>PC Width %</label><input data-var="--pc-zone-width" data-unit="%" type="number" step="0.1"></div>
    <div class="layout-edit-row"><label>PC Height %</label><input data-var="--pc-zone-height" data-unit="%" type="number" step="0.1"></div>
    <div class="layout-edit-row"><label>PC Grid Gap px</label><input data-var="--pc-grid-gap" data-unit="px" type="number" step="0.5"></div>
    <div class="layout-edit-row"><label>PC Row Overlap px</label><input data-var="--pc-row-overlap-y" data-unit="px" type="number" step="1" min="0" max="40"></div>
    <h3>Memorial Layout Edit</h3>
    <div class="layout-edit-row"><label>Memorial Left %</label><input data-var="--memorial-zone-left" data-unit="%" type="number" step="0.1"></div>
    <div class="layout-edit-row"><label>Memorial Top %</label><input data-var="--memorial-zone-top" data-unit="%" type="number" step="0.1"></div>
    <div class="layout-edit-row"><label>Memorial Width %</label><input data-var="--memorial-zone-width" data-unit="%" type="number" step="0.1"></div>
    <div class="layout-edit-row"><label>Memorial Height %</label><input data-var="--memorial-zone-height" data-unit="%" type="number" step="0.1"></div>
    <div class="layout-edit-row"><label>Memorial Columns</label><input data-var="--memorial-columns" data-unit="" type="number" step="1" min="1" max="30"></div>
    <div class="layout-edit-row"><label>Memorial Gap px</label><input data-var="--memorial-grid-gap" data-unit="px" type="number" step="0.5"></div>
    <div class="layout-edit-row"><label>Memorial Row Overlap px</label><input data-var="--memorial-row-overlap-y" data-unit="px" type="number" step="1" min="0" max="60"></div>
    <div class="layout-edit-row"><label>Memorial Row 1 Y px</label><input data-var="--memorial-row1-y-offset" data-unit="px" type="number" step="1" min="-80" max="80"></div>
    <div class="layout-edit-row"><label>Memorial Row 2 Y px</label><input data-var="--memorial-row2-y-offset" data-unit="px" type="number" step="1" min="-80" max="80"></div>
    <div class="layout-edit-row"><label>Points Barrier Width px</label><input data-var="--memorial-points-barrier-width" data-unit="px" type="number" step="1" min="0" max="240"></div>
    <div class="layout-edit-row"><label>Memorial Overlap px</label><input data-var="--memorial-overlap-x" data-unit="px" type="number" step="1" min="0" max="80"></div>
    <div class="layout-edit-row"><label>Memorial Sprite px</label><input data-var="--memorial-sprite-size" data-unit="px" type="number" step="1"></div>
    <div class="layout-edit-row"><label>Memorial Scale</label><input data-var="--memorial-sprite-scale" data-unit="" type="number" step="0.01"></div>
    <h3>Points Badge Edit</h3>
    <div class="layout-edit-row"><label>Badge Left %</label><input data-var="--points-badge-left" data-unit="%" type="number" step="0.1"></div>
    <div class="layout-edit-row"><label>Badge Bottom %</label><input data-var="--points-badge-bottom" data-unit="%" type="number" step="0.1"></div>
    <div class="layout-edit-row"><label>Badge Width px</label><input data-var="--points-badge-width" data-unit="px" type="number" step="1"></div>
    <div class="layout-edit-row"><label>Badge Height px</label><input data-var="--points-badge-height" data-unit="px" type="number" step="1"></div>
    <div class="layout-edit-row"><label>Points Single X px</label><input data-var="--points-count-single-x" data-unit="px" type="number" step="1" min="-80" max="80"></div>
    <div class="layout-edit-row"><label>Points Single Y px</label><input data-var="--points-count-single-y" data-unit="px" type="number" step="1" min="-80" max="80"></div>
    <div class="layout-edit-row"><label>Points Double X px</label><input data-var="--points-count-double-x" data-unit="px" type="number" step="1" min="-80" max="80"></div>
    <div class="layout-edit-row"><label>Points Double Y px</label><input data-var="--points-count-double-y" data-unit="px" type="number" step="1" min="-80" max="80"></div>
    <div class="layout-edit-row"><label>Points Preview Value</label><input id="pointsPreviewValue" type="text" placeholder="5 or 55"></div>
    <div class="layout-edit-actions">
      <button data-action="preview-points">Apply Points Preview</button>
      <button data-action="clear-preview-points">Clear Points Preview</button>
    </div>
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
      <button data-action="save">Save Local</button>
      <button data-action="load">Load Local</button>
      <button data-action="clear">Clear</button>
      <button data-action="hide">Hide Panel</button>
    </div>
    <pre class="layout-edit-output" id="layoutEditOutput"></pre>
  `;
  document.body.appendChild(panel);

  const showButton = document.createElement("button");
  showButton.type = "button";
  showButton.textContent = "Show Layout Panel";
  showButton.style.position = "fixed";
  showButton.style.left = "12px";
  showButton.style.top = "12px";
  showButton.style.zIndex = "10001";
  showButton.style.background = "#12394a";
  showButton.style.border = "1px solid #2f6f86";
  showButton.style.color = "#dff3fb";
  showButton.style.borderRadius = "6px";
  showButton.style.padding = "6px 9px";
  showButton.style.cursor = "pointer";
  showButton.style.fontSize = "12px";
  showButton.hidden = true;
  document.body.appendChild(showButton);

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
    scheduleLayoutAutosave();
  }

  let autosaveTimerId = null;

  function scheduleLayoutAutosave() {
    if (autosaveTimerId) {
      clearTimeout(autosaveTimerId);
    }
    autosaveTimerId = setTimeout(() => {
      autosaveTimerId = null;
      persistLayoutVarsToLocalStorage(getLayoutVarsSnapshot());
    }, 140);
  }

  function flushLayoutAutosave() {
    if (autosaveTimerId) {
      clearTimeout(autosaveTimerId);
      autosaveTimerId = null;
    }
    persistLayoutVarsToLocalStorage(getLayoutVarsSnapshot());
  }

  function updateOutput() {
    const vars = getLayoutEditVarNames();
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

  function getLayoutVarsObject() {
    return getLayoutVarsSnapshot();
  }

  function syncInputsFromCssVars() {
    panel.querySelectorAll("input[data-var]").forEach((input) => {
      const varName = input.dataset.var;
      input.value = String(getVarNumber(varName));
    });
    syncSlotInputs();
  }

  function applySavedLayoutVars(savedVars) {
    const ok = applyLayoutVarsToRoot(savedVars);
    if (!ok) {
      return false;
    }
    syncInputsFromCssVars();
    updateOutput();
    return true;
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
    scheduleLayoutAutosave();
  }

  slotSelect?.addEventListener("change", syncSlotInputs);
  slotSpriteX?.addEventListener("input", applySlotInputs);
  slotSpriteY?.addEventListener("input", applySlotInputs);
  slotSpriteScale?.addEventListener("input", applySlotInputs);

  const copyButton = panel.querySelector('button[data-action="copy"]');
  const saveButton = panel.querySelector('button[data-action="save"]');
  const loadButton = panel.querySelector('button[data-action="load"]');
  const clearButton = panel.querySelector('button[data-action="clear"]');
  const hideButton = panel.querySelector('button[data-action="hide"]');
  const pointsPreviewInput = panel.querySelector("#pointsPreviewValue");
  const previewPointsButton = panel.querySelector('button[data-action="preview-points"]');
  const clearPreviewPointsButton = panel.querySelector('button[data-action="clear-preview-points"]');

  previewPointsButton?.addEventListener("click", () => {
    if (!pointsShopUi) {
      return;
    }
    const value = String(pointsPreviewInput?.value || "").trim();
    pointsShopUi.setPreviewPoints(value || null);
  });

  clearPreviewPointsButton?.addEventListener("click", () => {
    if (!pointsShopUi) {
      return;
    }
    if (pointsPreviewInput) {
      pointsPreviewInput.value = "";
    }
    pointsShopUi.setPreviewPoints(null);
  });

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

  saveButton?.addEventListener("click", () => {
    const saved = persistLayoutVarsToLocalStorage(getLayoutVarsObject());
    if (saved) {
      saveButton.textContent = "Saved";
      setTimeout(() => {
        saveButton.textContent = "Save";
      }, 900);
    } else {
      saveButton.textContent = "Save failed";
      setTimeout(() => {
        saveButton.textContent = "Save";
      }, 1200);
    }
  });

  loadButton?.addEventListener("click", () => {
    const savedVars = loadSavedLayoutVarsFromLocalStorage();
    if (!savedVars) {
      loadButton.textContent = "No save";
      setTimeout(() => {
        loadButton.textContent = "Load";
      }, 900);
      return;
    }

    const ok = applySavedLayoutVars(savedVars);
    loadButton.textContent = ok ? "Loaded" : "Load failed";
    setTimeout(() => {
      loadButton.textContent = "Load";
    }, 900);
  });

  clearButton?.addEventListener("click", () => {
    try {
      localStorage.removeItem(LAYOUT_PRESET_STORAGE_KEY);
      clearButton.textContent = "Cleared";
      setTimeout(() => {
        clearButton.textContent = "Clear";
      }, 900);
    } catch (_error) {
      clearButton.textContent = "Clear failed";
      setTimeout(() => {
        clearButton.textContent = "Clear";
      }, 1200);
    }
  });

  function setPanelHidden(hidden) {
    panel.hidden = hidden;
    showButton.hidden = !hidden;
  }

  // Keep edit-mode controls available but start hidden to avoid obscuring overlay.
  setPanelHidden(true);

  hideButton?.addEventListener("click", () => {
    setPanelHidden(true);
  });
  showButton.addEventListener("click", () => {
    setPanelHidden(false);
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
    const rootRect = overlayRoot?.getBoundingClientRect();
    if (!rootRect || rootRect.width <= 0 || rootRect.height <= 0) {
      return;
    }

    if (dragState) {
      const dx = ev.clientX - dragState.startX;
      const dy = ev.clientY - dragState.startY;
      const leftPct = ((dragState.leftPx + dx - rootRect.left) / rootRect.width) * 100;
      const topPct = ((dragState.topPx + dy - rootRect.top) / rootRect.height) * 100;
      rootStyle.setProperty("--party-zone-left", `${leftPct.toFixed(2)}%`);
      rootStyle.setProperty("--party-zone-top", `${topPct.toFixed(2)}%`);
      const leftInput = panel.querySelector('input[data-var="--party-zone-left"]');
      const topInput = panel.querySelector('input[data-var="--party-zone-top"]');
      if (leftInput) leftInput.value = leftPct.toFixed(2);
      if (topInput) topInput.value = topPct.toFixed(2);
      updateOutput();
      scheduleLayoutAutosave();
    }

    if (resizeState) {
      const dx = ev.clientX - resizeState.startX;
      const dy = ev.clientY - resizeState.startY;
      const widthPct = (Math.max(220, resizeState.widthPx + dx) / rootRect.width) * 100;
      const heightPct = (Math.max(220, resizeState.heightPx + dy) / rootRect.height) * 100;
      rootStyle.setProperty("--party-zone-width", `calc(${widthPct.toFixed(2)}% - 13px)`);
      rootStyle.setProperty("--party-zone-height", `calc(${heightPct.toFixed(2)}% - 13px)`);
      const widthInput = panel.querySelector('input[data-var="--party-zone-width"]');
      const heightInput = panel.querySelector('input[data-var="--party-zone-height"]');
      if (widthInput) widthInput.value = widthPct.toFixed(2);
      if (heightInput) heightInput.value = heightPct.toFixed(2);
      updateOutput();
      scheduleLayoutAutosave();
    }
  }

  function endPointer() {
    if (dragState || resizeState) {
      flushLayoutAutosave();
    }
    dragState = null;
    resizeState = null;
  }

  dragHandle.addEventListener("pointerdown", beginDrag);
  resizeHandle.addEventListener("pointerdown", beginResize);
  window.addEventListener("pointermove", onPointerMove);
  window.addEventListener("pointerup", endPointer);

  syncSlotInputs();
  const initialLocalVars = loadSavedLayoutVarsFromLocalStorage();
  if (initialLocalVars) {
    applySavedLayoutVars(initialLocalVars);
  }
  syncInputsFromCssVars();
  updateOutput();
}

async function applyTemplateAspect() {
  const templateVar = getComputedStyle(document.documentElement).getPropertyValue("--template-image").trim();
  const urlMatch = templateVar.match(/^url\((['"]?)(.*)\1\)$/i);
  if (!urlMatch) {
    return;
  }

  const rawUrl = urlMatch[2];
  if (!rawUrl) {
    return;
  }

  try {
    const resolvedUrl = new URL(rawUrl, window.location.href).href;
    await new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => {
        if (img.naturalWidth > 0 && img.naturalHeight > 0) {
          const aspect = img.naturalWidth / img.naturalHeight;
          document.documentElement.style.setProperty("--template-aspect", String(aspect));
        }
        resolve();
      };
      img.onerror = () => reject(new Error("Template image load failed"));
      img.src = resolvedUrl;
    });
  } catch (error) {
    logDebug("Template aspect detection failed; using default aspect", error);
  }
}

function applyTemplateFit() {
  if (!overlayRoot) {
    return;
  }

  const aspectRaw = Number(getComputedStyle(document.documentElement).getPropertyValue("--template-aspect").trim());
  const aspect = Number.isFinite(aspectRaw) && aspectRaw > 0 ? aspectRaw : 16 / 9;
  const viewportWidth = window.innerWidth;
  const viewportHeight = window.innerHeight;

  let fitWidth = viewportWidth;
  let fitHeight = fitWidth / aspect;
  if (fitHeight > viewportHeight) {
    fitHeight = viewportHeight;
    fitWidth = fitHeight * aspect;
  }

  overlayRoot.style.width = `${fitWidth}px`;
  overlayRoot.style.height = `${fitHeight}px`;
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
    const websocket = typeof overlay.websocket === "object" && overlay.websocket ? overlay.websocket : {};

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
      websocket: {
        enabled: Boolean(websocket.enabled ?? DEFAULT_CONFIG.websocket.enabled),
        host: String(websocket.host || DEFAULT_CONFIG.websocket.host),
        port: Number(websocket.port || DEFAULT_CONFIG.websocket.port),
        reconnectMs: Math.max(
          250,
          Number(websocket.reconnect_interval_ms || DEFAULT_CONFIG.websocket.reconnectMs)
        ),
      },
    };

    const layoutVars =
      typeof overlay.layout_vars === "object" && overlay.layout_vars
        ? overlay.layout_vars
        : null;
    applyLayoutVarsToRoot(layoutVars);

    document.documentElement.style.setProperty("--overlay-scale", String(config.overlayScale));
    document.documentElement.setAttribute("data-theme", config.theme);
    logDebug("Overlay config loaded", config);
  } catch (_error) {
    logDebug("Overlay config not loaded, using defaults");
  }
}

(async function bootstrap() {
  statusMode("Loading overlay...", "loading");
  await loadConfig();
  applyLayoutVarsToRoot(loadSavedLayoutVarsFromLocalStorage());
  await applyTemplateAspect();
  applyTemplateFit();
  initPointsShopUi();
  initLayoutEditMode();
  startDataPipeline();
})();

window.addEventListener("resize", applyTemplateFit);
