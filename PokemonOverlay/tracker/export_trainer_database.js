const fs = require("fs");
const path = require("path");

function loadData(dataPath) {
  const raw = fs.readFileSync(dataPath, "utf8");
  return Function("return " + raw)();
}

function toName(value) {
  if (value === null || value === undefined) return "";
  return String(value);
}

function csvEscape(value) {
  const text = String(value ?? "");
  if (text.includes(",") || text.includes("\n") || text.includes("\"")) {
    return '"' + text.replace(/"/g, '""') + '"';
  }
  return text;
}

function getSpeciesName(data, speciesId) {
  const entry = data.species && data.species[speciesId];
  if (!entry) return `species_${speciesId}`;
  return toName(entry.name || entry.key || `species_${speciesId}`);
}

function getMoveName(data, moveId) {
  const entry = data.moves && data.moves[moveId];
  if (!entry) return `move_${moveId}`;
  return toName(entry.name || `move_${moveId}`);
}

function getItemName(data, itemId) {
  const entry = data.items && data.items[itemId];
  if (!entry) return itemId ? `item_${itemId}` : "";
  return toName(entry.name || `item_${itemId}`);
}

function buildAreaTrainerRefs(data) {
  const byTrainerId = new Map();
  const areas = Array.isArray(data.areas) ? data.areas : [];

  for (let areaIndex = 0; areaIndex < areas.length; areaIndex += 1) {
    const area = areas[areaIndex] || {};
    const areaName = toName(area.name || `area_${areaIndex}`);
    const trainerBuckets = area.trainers;
    if (!trainerBuckets || typeof trainerBuckets !== "object") continue;

    for (const [stageKey, trainerList] of Object.entries(trainerBuckets)) {
      if (!Array.isArray(trainerList)) continue;
      for (const rawTrainerId of trainerList) {
        const trainerId = Number(rawTrainerId);
        if (!Number.isFinite(trainerId)) continue;

        const ref = {
          area_index: areaIndex,
          area_name: areaName,
          stage: stageKey,
        };

        if (!byTrainerId.has(trainerId)) {
          byTrainerId.set(trainerId, []);
        }
        byTrainerId.get(trainerId).push(ref);
      }
    }
  }

  return byTrainerId;
}

function findTeamVariants(trainerEntry) {
  const variants = [];
  for (const [key, value] of Object.entries(trainerEntry || {})) {
    if (!Array.isArray(value) || value.length === 0) continue;
    const first = value[0];
    if (first && typeof first === "object" && Number.isFinite(Number(first.species))) {
      variants.push(key);
    }
  }
  return variants.sort();
}

function enrichMon(data, mon) {
  const moves = Array.isArray(mon.moves) ? mon.moves : [];
  return {
    species_id: Number(mon.species),
    species_name: getSpeciesName(data, Number(mon.species)),
    level: Number(mon.level),
    ability_index: Number(mon.ability ?? 0),
    nature_id: Number(mon.nature ?? 0),
    item_id: Number(mon.item ?? 0),
    item_name: getItemName(data, Number(mon.item ?? 0)),
    moves: moves.map((id) => ({
      move_id: Number(id),
      move_name: getMoveName(data, Number(id)),
    })),
    ivs: Array.isArray(mon.IVs) ? mon.IVs.map((v) => Number(v)) : [],
    evs: Array.isArray(mon.EVs) ? mon.EVs.map((v) => Number(v)) : [],
  };
}

function summarizeTeam(team) {
  return team
    .map((mon) => `${mon.species_name} Lv${mon.level}`)
    .join(" | ");
}

function exportTrainerDatabase(projectRoot) {
  const dataPath = path.join(projectRoot, "_rr_data_tmp.js");
  const outJsonPath = path.join(projectRoot, "tracker", "trainer_database_full.json");
  const outCsvPath = path.join(projectRoot, "tracker", "trainer_database_index.csv");

  if (!fs.existsSync(dataPath)) {
    throw new Error(`Data file not found: ${dataPath}`);
  }

  const data = loadData(dataPath);
  const trainers = data.trainers || {};
  const areaRefs = buildAreaTrainerRefs(data);

  const trainerIds = Object.keys(trainers)
    .map((id) => Number(id))
    .filter((id) => Number.isFinite(id))
    .sort((a, b) => a - b);

  const rows = [];
  for (const trainerId of trainerIds) {
    const entry = trainers[trainerId] || {};
    const variants = findTeamVariants(entry);

    const teams = {};
    for (const variant of variants) {
      const rawTeam = Array.isArray(entry[variant]) ? entry[variant] : [];
      teams[variant] = rawTeam.map((mon) => enrichMon(data, mon));
    }

    rows.push({
      trainer_id: trainerId,
      trainer_name: toName(entry.name || `trainer_${trainerId}`),
      variants,
      teams,
      locations: areaRefs.get(trainerId) || [],
    });
  }

  const full = {
    source_file: "_rr_data_tmp.js",
    total_trainers: rows.length,
    exported_at: new Date().toISOString(),
    trainers: rows,
  };

  fs.writeFileSync(outJsonPath, JSON.stringify(full, null, 2) + "\n", "utf8");

  const csvHeader = [
    "trainer_id",
    "trainer_name",
    "variants",
    "location_count",
    "locations",
    "normal_team_preview",
    "hardcore_team_preview",
  ];
  const csvLines = [csvHeader.join(",")];

  for (const row of rows) {
    const locations = row.locations
      .map((loc) => `${loc.area_name} [stage=${loc.stage}]`)
      .join("; ");
    const normalPreview = Array.isArray(row.teams.normal) ? summarizeTeam(row.teams.normal) : "";
    const hardcorePreview = Array.isArray(row.teams.hardcore) ? summarizeTeam(row.teams.hardcore) : "";

    const fields = [
      row.trainer_id,
      row.trainer_name,
      row.variants.join("|"),
      row.locations.length,
      locations,
      normalPreview,
      hardcorePreview,
    ];
    csvLines.push(fields.map(csvEscape).join(","));
  }

  fs.writeFileSync(outCsvPath, csvLines.join("\n") + "\n", "utf8");

  return {
    data_path: dataPath,
    out_json: outJsonPath,
    out_csv: outCsvPath,
    trainer_count: rows.length,
  };
}

function main() {
  const projectRoot = path.resolve(__dirname, "..");
  const result = exportTrainerDatabase(projectRoot);
  console.log(JSON.stringify(result));
}

if (require.main === module) {
  main();
}
