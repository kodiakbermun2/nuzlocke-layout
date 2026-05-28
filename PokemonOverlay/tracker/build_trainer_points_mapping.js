const fs = require("fs");
const path = require("path");

const STOPWORDS = new Set([
  "PKMN",
  "POKEMON",
  "TRAINER",
  "LEADER",
  "ADMIN",
  "BUG",
  "CATCHER",
  "LASS",
  "YOUNGSTER",
  "CAMPER",
  "ROCKET",
  "GRUNT",
  "ROCKER",
  "FISHERMAN",
  "BIRD",
  "KEEPER",
  "PICKNICKER",
  "BIKER",
  "CUE",
  "BALL",
  "BLACK",
  "BELT",
  "SUPER",
  "NERD",
  "BEAUTY",
  "TAMER",
  "ACE",
  "DUMBASS",
  "DUMASS",
  "CAPTAIN",
  "ELITE",
  "FOUR",
  "CHAMPION",
]);

const NAME_ALIASES = [
  [/\bPICKNICKER\b/g, "PICNICKER"],
  [/\bGIOVANNIA\b/g, "GIOVANNI"],
  [/\bLT\b/g, "LIEUTENANT"],
];

const MANUAL_REWARD_ID_TO_DB_IDS = {
  rocket_grunt_nugget_bridge: [356],
  rocket_grunt_dig_house: [355],
  rocket_guard_game_corner: [357],
  left_guard_rocket_hideout: [366],
  right_guard_rocket_hideout: [367],
  rival_elite_four_champion: [438, 439, 440],
};

function readText(filePath) {
  return fs.readFileSync(filePath, "utf8");
}

function normalizeText(value) {
  if (!value) return "";
  let out = String(value)
    .toUpperCase()
    .replace(/VIRID\./g, "VIRIDIAN")
    .replace(/VERMILLION/g, "VERMILION")
    .replace(/FUSHSIA/g, "FUCHSIA")
    .replace(/S\.S\./g, "SS")
    .replace(/[^A-Z0-9]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();

  for (const [re, replacement] of NAME_ALIASES) {
    out = out.replace(re, replacement);
  }
  return out;
}

function tokenize(value) {
  const norm = normalizeText(value);
  if (!norm) return [];
  return norm.split(" ").filter(Boolean);
}

function personKey(value) {
  const tokens = tokenize(value).filter((t) => !STOPWORDS.has(t));
  return tokens.join(" ").trim();
}

function parseRewardsFromPy(pyText) {
  const out = [];
  const re = /TrainerReward\("([^"]+)",\s*"([^"]+)",\s*(\d+),\s*"([^"]+)"(?:,\s*([^\)]+))?\)/g;
  for (const m of pyText.matchAll(re)) {
    out.push({
      reward_id: m[1],
      reward_name: m[2],
      points: Number(m[3]),
      flag_key: m[4],
      flag_id_raw: (m[5] || "").trim(),
    });
  }
  return out;
}

function parseCsvLine(line) {
  const out = [];
  let cur = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i += 1) {
    const ch = line[i];
    const next = i + 1 < line.length ? line[i + 1] : "";
    if (ch === '"') {
      if (inQuotes && next === '"') {
        cur += '"';
        i += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }
    if (ch === "," && !inQuotes) {
      out.push(cur);
      cur = "";
      continue;
    }
    cur += ch;
  }
  out.push(cur);
  return out;
}

function parseTrainerOrderSheet(csvText) {
  const lines = csvText.split(/\r?\n/);
  const entries = [];
  let pendingName = null;
  let pendingCap = null;

  for (const line of lines) {
    const cols = parseCsvLine(line).map((c) => c.trim());
    const nonEmpty = cols.filter(Boolean);
    if (nonEmpty.length === 0) {
      continue;
    }

    if (nonEmpty.length === 2 && /^\d+$/.test(nonEmpty[1])) {
      const candidate = nonEmpty[0];
      const candidateNorm = normalizeText(candidate);
      if (
        candidateNorm &&
        !candidateNorm.includes("CLICK") &&
        !candidateNorm.includes("OPTIONAL") &&
        !candidateNorm.includes("LEVEL CAPS")
      ) {
        pendingName = candidate;
        pendingCap = Number(nonEmpty[1]);
      }
      continue;
    }

    if (pendingName && nonEmpty.length === 1) {
      const location = nonEmpty[0];
      const locNorm = normalizeText(location);
      if (
        locNorm &&
        !locNorm.includes("OPTIONAL") &&
        !locNorm.includes("CLICK") &&
        !locNorm.includes("TRAINER") &&
        !locNorm.includes("PAGE")
      ) {
        entries.push({
          sheet_name: pendingName,
          sheet_location: location,
          level_cap: pendingCap,
          sheet_name_norm: normalizeText(pendingName),
          sheet_location_norm: locNorm,
        });
        pendingName = null;
        pendingCap = null;
      }
    }
  }

  return entries;
}

function parseRewardName(raw) {
  const out = {
    raw,
    base_name: raw,
    location_hint: "",
  };

  const locMatch = /\(([^\)]*)\)\s*$/.exec(raw);
  if (locMatch) {
    out.location_hint = locMatch[1].trim();
  }

  out.base_name = raw
    .replace(/\(Rematch\)/gi, "")
    .replace(/\(Elite Four Champion\)/gi, "Champion")
    .replace(/\([^\)]*\)/g, "")
    .replace(/\s+/g, " ")
    .trim();

  out.base_name_norm = normalizeText(out.base_name);
  out.base_person = personKey(out.base_name);
  out.location_norm = normalizeText(out.location_hint);

  return out;
}

function containsAny(haystack, needle) {
  if (!needle) return false;
  if (!haystack) return false;
  return haystack.includes(needle) || needle.includes(haystack);
}

function jaccard(tokensA, tokensB) {
  if (!tokensA.length || !tokensB.length) return 0;
  const a = new Set(tokensA);
  const b = new Set(tokensB);
  let intersection = 0;
  for (const t of a) {
    if (b.has(t)) intersection += 1;
  }
  const union = a.size + b.size - intersection;
  return union > 0 ? intersection / union : 0;
}

function matchRewardToDb(reward, dbRows, sheetEntries) {
  const parsed = parseRewardName(reward.reward_name);
  const rewardNameTokens = tokenize(parsed.base_name_norm);
  const rewardPersonTokens = tokenize(parsed.base_person);
  const rewardLoc = parsed.location_norm;

  const relevantSheet = sheetEntries.filter((entry) => {
    const nameOverlap =
      containsAny(entry.sheet_name_norm, parsed.base_name_norm) ||
      containsAny(parsed.base_name_norm, entry.sheet_name_norm) ||
      (parsed.base_person && containsAny(personKey(entry.sheet_name), parsed.base_person));
    const locOverlap = !rewardLoc || containsAny(entry.sheet_location_norm, rewardLoc) || containsAny(rewardLoc, entry.sheet_location_norm);
    return nameOverlap && locOverlap;
  });

  const pairNames = parsed.base_name.includes("&")
    ? parsed.base_name
        .split("&")
        .map((x) => personKey(x.trim()))
        .filter(Boolean)
    : [];

  const scored = dbRows.map((row) => {
    const rowNameNorm = normalizeText(row.trainer_name);
    const rowPerson = personKey(row.trainer_name);
    const rowNameTokens = tokenize(rowNameNorm);
    const rowPersonTokens = tokenize(rowPerson);
    const areaNames = (row.locations || []).map((loc) => normalizeText(loc.area_name || ""));
    const areaBlob = areaNames.join(" | ");

    let score = 0;

    if (parsed.base_person && rowPerson && parsed.base_person === rowPerson) {
      score += 70;
    }

    if (pairNames.length > 0) {
      if (pairNames.some((name) => name && containsAny(rowPerson, name))) {
        score += 60;
      }
    }

    if (containsAny(rowNameNorm, parsed.base_name_norm) || containsAny(parsed.base_name_norm, rowNameNorm)) {
      score += 30;
    }

    if (rewardLoc) {
      const locMatch = areaNames.some((area) => containsAny(area, rewardLoc) || containsAny(rewardLoc, area));
      if (locMatch) score += 25;

      // "Elite Four" and "Champion" are held at Pokemon League in DB area names.
      if (!locMatch && (rewardLoc.includes("ELITE FOUR") || rewardLoc.includes("CHAMP"))) {
        if (areaNames.some((area) => area.includes("POKEMON LEAGUE"))) {
          score += 20;
        }
      }
    }

    const nameJac = jaccard(rewardNameTokens, rowNameTokens);
    const personJac = jaccard(rewardPersonTokens, rowPersonTokens);
    score += Math.round(nameJac * 20);
    score += Math.round(personJac * 20);

    const sheetConfirm = relevantSheet.some((entry) => {
      const nameOverlap = containsAny(entry.sheet_name_norm, rowNameNorm) || containsAny(personKey(entry.sheet_name), rowPerson);
      const locOverlap = entry.sheet_location_norm ? containsAny(areaBlob, entry.sheet_location_norm) : false;
      return nameOverlap && locOverlap;
    });
    if (sheetConfirm) score += 10;

    return {
      row,
      score,
      rowNameNorm,
      rowPerson,
      areaBlob,
    };
  });

  scored.sort((a, b) => b.score - a.score);
  const best = scored[0];
  const second = scored[1];
  const ambiguous = Boolean(second && best && best.score - second.score <= 7);
  const confidence = best
    ? best.score >= 95
      ? "high"
      : best.score >= 70
        ? "medium"
        : "low"
    : "none";

  return {
    parsed,
    relevant_sheet: relevantSheet,
    best,
    second,
    ambiguous,
    confidence,
  };
}

function findPairMatches(parsed, dbRows) {
  if (!parsed.base_name.includes("&")) {
    return [];
  }

  const names = parsed.base_name
    .split("&")
    .map((x) => personKey(x.trim()))
    .filter(Boolean);
  if (names.length < 2) return [];

  const out = [];
  const locHint = parsed.location_norm;
  for (const name of names) {
    const candidates = dbRows
      .map((row) => {
        const rowPerson = personKey(row.trainer_name);
        const areaNames = (row.locations || []).map((x) => normalizeText(x.area_name || ""));
        let score = 0;
        if (containsAny(rowPerson, name) || containsAny(name, rowPerson)) score += 70;
        if (locHint && areaNames.some((a) => containsAny(a, locHint) || containsAny(locHint, a))) score += 20;
        return { row, score };
      })
      .sort((a, b) => b.score - a.score);

    if (candidates[0] && candidates[0].score >= 70) {
      out.push(candidates[0].row);
    }
  }

  return out;
}

function main() {
  const root = path.resolve(__dirname, "..");
  const rewardsPath = path.join(root, "tracker", "trainer_rewards.py");
  const dbPath = path.join(root, "tracker", "trainer_database_full.json");
  const sheetPath = path.join(root, "tracker", "sheet_trainer_order.csv");

  const rewardsText = readText(rewardsPath);
  const db = JSON.parse(readText(dbPath));
  const sheetCsv = readText(sheetPath);

  const rewards = parseRewardsFromPy(rewardsText);
  const sheetEntries = parseTrainerOrderSheet(sheetCsv);
  const dbRows = Array.isArray(db.trainers) ? db.trainers : [];

  const mapped = [];
  let matched = 0;

  for (const reward of rewards) {
    const manualIds = MANUAL_REWARD_ID_TO_DB_IDS[reward.reward_id] || [];
    const manualRows = manualIds
      .map((id) => dbRows.find((row) => Number(row.trainer_id) === Number(id)))
      .filter(Boolean);

    if (manualRows.length > 0) {
      matched += 1;
      const primary = manualRows[0];
      mapped.push({
        reward_id: reward.reward_id,
        reward_name: reward.reward_name,
        points: reward.points,
        flag_key: reward.flag_key,
        flag_id_raw: reward.flag_id_raw,
        sheet_references: [],
        matched: true,
        confidence: "manual",
        ambiguous: manualRows.length > 1,
        match_score: 999,
        candidate_2_score: manualRows.length > 1 ? 999 : 0,
        trainer_db_id: primary.trainer_id,
        trainer_db_name: primary.trainer_name,
        trainer_db_locations: primary.locations || [],
        teams: primary.teams || {},
        matched_trainers: manualRows.map((r) => ({
          trainer_id: r.trainer_id,
          trainer_name: r.trainer_name,
          locations: r.locations || [],
        })),
      });
      continue;
    }

    const m = matchRewardToDb(reward, dbRows, sheetEntries);
    const pairRows = findPairMatches(m.parsed, dbRows);
    const hasPairMatch = pairRows.length >= 2;
    const hasMatch = hasPairMatch || Boolean(m.best && m.best.score >= 55);
    if (hasMatch) matched += 1;

    const matchedRows = hasPairMatch ? pairRows : hasMatch ? [m.best.row] : [];

    mapped.push({
      reward_id: reward.reward_id,
      reward_name: reward.reward_name,
      points: reward.points,
      flag_key: reward.flag_key,
      flag_id_raw: reward.flag_id_raw,
      sheet_references: m.relevant_sheet,
      matched: hasMatch,
      confidence: m.confidence,
      ambiguous: m.ambiguous,
      match_score: m.best ? m.best.score : 0,
      candidate_2_score: m.second ? m.second.score : 0,
      trainer_db_id: hasPairMatch ? null : hasMatch ? m.best.row.trainer_id : null,
      trainer_db_name: hasPairMatch ? null : hasMatch ? m.best.row.trainer_name : null,
      trainer_db_locations: hasPairMatch ? [] : hasMatch ? m.best.row.locations : [],
      teams: hasPairMatch ? {} : hasMatch ? m.best.row.teams : {},
      matched_trainers: matchedRows.map((r) => ({
        trainer_id: r.trainer_id,
        trainer_name: r.trainer_name,
        locations: r.locations || [],
      })),
    });
  }

  const output = {
    generated_at: new Date().toISOString(),
    source: {
      sheet: "sheet_trainer_order.csv",
      rewards: "trainer_rewards.py",
      trainer_db: "trainer_database_full.json",
    },
    summary: {
      rewards_total: rewards.length,
      matched_count: matched,
      unmatched_count: rewards.length - matched,
      sheet_entries_parsed: sheetEntries.length,
    },
    rows: mapped,
  };

  const outJson = path.join(root, "tracker", "trainer_points_team_mapping.json");
  fs.writeFileSync(outJson, JSON.stringify(output, null, 2) + "\n", "utf8");

  const outCsv = path.join(root, "tracker", "trainer_points_team_mapping.csv");
  const header = [
    "reward_id",
    "reward_name",
    "points",
    "matched",
    "confidence",
    "ambiguous",
    "match_score",
    "trainer_db_id",
    "trainer_db_name",
    "location_preview",
    "normal_team_preview",
    "hardcore_team_preview",
  ];

  const csvLines = [header.join(",")];
  for (const row of mapped) {
    const locPreview = (row.trainer_db_locations || [])
      .map((x) => `${x.area_name} [stage=${x.stage}]`)
      .join("; ");
    const normalPreview = Array.isArray(row.teams?.normal)
      ? row.teams.normal.map((m) => `${m.species_name} Lv${m.level}`).join(" | ")
      : "";
    const hardcorePreview = Array.isArray(row.teams?.hardcore)
      ? row.teams.hardcore.map((m) => `${m.species_name} Lv${m.level}`).join(" | ")
      : "";

    const values = [
      row.reward_id,
      row.reward_name,
      row.points,
      row.matched,
      row.confidence,
      row.ambiguous,
      row.match_score,
      row.trainer_db_id ?? "",
      row.trainer_db_name ?? "",
      locPreview,
      normalPreview,
      hardcorePreview,
    ].map((v) => {
      const t = String(v ?? "");
      if (t.includes(",") || t.includes("\n") || t.includes('"')) {
        return '"' + t.replace(/"/g, '""') + '"';
      }
      return t;
    });

    csvLines.push(values.join(","));
  }

  fs.writeFileSync(outCsv, csvLines.join("\n") + "\n", "utf8");

  console.log(
    JSON.stringify({
      out_json: outJson,
      out_csv: outCsv,
      summary: output.summary,
    })
  );
}

if (require.main === module) {
  main();
}
