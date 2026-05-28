const fs = require("fs");
const path = require("path");

function readText(filePath) {
  return fs.readFileSync(filePath, "utf8");
}

function parseRewardsFromPy(pyText) {
  const out = [];
  const re = /TrainerReward\("([^"]+)",\s*"([^"]+)",\s*(\d+),\s*"([^"]+)"(?:,\s*([^\)]+))?\)/g;
  for (const m of pyText.matchAll(re)) {
    const raw = String(m[5] || "").trim();
    let explicitFlagId = null;
    if (raw) {
      const parsed = Number(raw);
      if (Number.isFinite(parsed)) {
        explicitFlagId = parsed;
      } else if (/^0x[0-9a-f]+$/i.test(raw)) {
        explicitFlagId = parseInt(raw, 16);
      }
    }

    out.push({
      reward_id: m[1],
      reward_name: m[2],
      points: Number(m[3]),
      flag_key: m[4],
      explicit_flag_id: explicitFlagId,
    });
  }
  return out;
}

function chooseTrainerDbId(row) {
  const rawTrainerDbId = row ? row.trainer_db_id : null;
  if (rawTrainerDbId !== null && rawTrainerDbId !== undefined && String(rawTrainerDbId).trim() !== "") {
    const parsed = Number(rawTrainerDbId);
    if (Number.isFinite(parsed) && parsed > 0) {
      return parsed;
    }
  }

  if (Array.isArray(row.matched_trainers) && row.matched_trainers.length > 1) {
    const ids = [];
    for (const match of row.matched_trainers) {
      const id = Number(match && match.trainer_id);
      if (Number.isFinite(id) && id > 0 && !ids.includes(id)) {
        ids.push(id);
      }
    }
    if (ids.length > 1) {
      return ids;
    }
  }

  if (Array.isArray(row.matched_trainers) && row.matched_trainers.length === 1) {
    const id = Number(row.matched_trainers[0].trainer_id);
    if (Number.isFinite(id) && id > 0) {
      return id;
    }
  }
  return null;
}

function main() {
  const trackerDir = __dirname;
  const rewardsPath = path.join(trackerDir, "trainer_rewards.py");
  const mappingPath = path.join(trackerDir, "trainer_points_team_mapping.json");
  const outPath = path.join(trackerDir, "trainer_reward_flag_ids.json");

  const trainerFlagBase = Number(process.env.POKEMON_OVERLAY_TRAINER_FLAG_BASE || 0x500);

  const manualMultiFlagOverrides = {
    rival_route_22: [329, 330, 331].map((id) => trainerFlagBase + id),
    FLAG_DEFEATED_RIVAL_ROUTE_22: [329, 330, 331].map((id) => trainerFlagBase + id),
    rival_rematch_route_22: [435, 436, 437].map((id) => trainerFlagBase + id),
    FLAG_DEFEATED_RIVAL_REMATCH_ROUTE_22: [435, 436, 437].map((id) => trainerFlagBase + id),
  };

  const rewards = parseRewardsFromPy(readText(rewardsPath));
  const mapping = JSON.parse(readText(mappingPath));
  const rows = Array.isArray(mapping.rows) ? mapping.rows : [];
  const rowByRewardId = new Map(rows.map((r) => [String(r.reward_id || ""), r]));

  const overrides = {};
  const notes = [];

  for (const reward of rewards) {
    const manualRewardIds = manualMultiFlagOverrides[reward.reward_id];
    const manualFlagIds = manualMultiFlagOverrides[reward.flag_key];
    if (Array.isArray(manualRewardIds) && manualRewardIds.length > 0) {
      overrides[reward.reward_id] = manualRewardIds;
      overrides[reward.flag_key] = Array.isArray(manualFlagIds) && manualFlagIds.length > 0 ? manualFlagIds : manualRewardIds;
      notes.push({
        reward_id: reward.reward_id,
        source: "manual_multi_flag_override",
        trainer_flag_base: trainerFlagBase,
        flag_ids: overrides[reward.reward_id],
      });
      continue;
    }

    // Keep explicit reward table flag IDs as-is.
    if (reward.explicit_flag_id !== null) {
      overrides[reward.reward_id] = reward.explicit_flag_id;
      overrides[reward.flag_key] = reward.explicit_flag_id;
      notes.push({
        reward_id: reward.reward_id,
        source: "explicit_reward_flag_id",
        flag_id: reward.explicit_flag_id,
      });
      continue;
    }

    const mapped = rowByRewardId.get(reward.reward_id);
    if (!mapped || !mapped.matched) {
      notes.push({
        reward_id: reward.reward_id,
        source: "missing_mapping",
        flag_id: null,
      });
      continue;
    }

    const trainerDbId = chooseTrainerDbId(mapped);
    if (Array.isArray(trainerDbId) && trainerDbId.length > 0) {
      const derivedMany = trainerDbId
        .map((id) => trainerFlagBase + Number(id))
        .filter((id, index, arr) => Number.isFinite(id) && id >= 0 && arr.indexOf(id) === index);

      if (!derivedMany.length) {
        notes.push({
          reward_id: reward.reward_id,
          source: "invalid_multi_trainer_mapping",
          flag_id: null,
        });
        continue;
      }

      overrides[reward.reward_id] = derivedMany;
      overrides[reward.flag_key] = derivedMany;
      notes.push({
        reward_id: reward.reward_id,
        source: "derived_from_multi_trainer_db_ids",
        trainer_db_ids: trainerDbId,
        trainer_flag_base: trainerFlagBase,
        flag_ids: derivedMany,
      });
      continue;
    }

    if (!Number.isFinite(trainerDbId)) {
      notes.push({
        reward_id: reward.reward_id,
        source: "ambiguous_trainer_mapping",
        flag_id: null,
      });
      continue;
    }

    // FireRed/CFRU trainer defeat flags are typically FLAG_TRAINER_START + trainerId.
    const derivedFlagId = trainerFlagBase + trainerDbId;
    overrides[reward.reward_id] = derivedFlagId;
    overrides[reward.flag_key] = derivedFlagId;
    notes.push({
      reward_id: reward.reward_id,
      source: "derived_from_trainer_db_id",
      trainer_db_id: trainerDbId,
      trainer_flag_base: trainerFlagBase,
      flag_id: derivedFlagId,
    });
  }

  const wrapper = {
    generated_at: new Date().toISOString(),
    trainer_flag_base: trainerFlagBase,
    override_count: Object.keys(overrides).length,
    unresolved_reward_count: notes.filter((n) => n.flag_id === null).length,
    notes,
    overrides,
  };

  fs.writeFileSync(outPath, JSON.stringify(wrapper, null, 2) + "\n", "utf8");
  console.log(
    JSON.stringify({
      out_path: outPath,
      override_count: wrapper.override_count,
      unresolved_reward_count: wrapper.unresolved_reward_count,
      trainer_flag_base: trainerFlagBase,
    })
  );
}

if (require.main === module) {
  main();
}
