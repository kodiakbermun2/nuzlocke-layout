-- mGBA live memory bridge for PokemonOverlay.
--
-- Goals:
-- - Write live party state to tracker/memory_state.json every ~100ms.
-- - Keep writes atomic and resilient.
-- - Report diagnostics in console.

local BRIDGE_PATH = "C:/Users/kodia/nuzlocke/PokemonOverlay/tracker/memory_state.json"
local TEMP_PATH = BRIDGE_PATH .. ".tmp"
local BRIDGE_LOG_PATH = "C:/Users/kodia/nuzlocke/PokemonOverlay/tracker/mgba_bridge_runtime.log"
local WRITE_INTERVAL_SECONDS = 0.25
local ENABLE_PC_SCAN = false
local AUTO_MANAGE_TRACKER = false
local TRACKER_PYTHON_PATH = "C:/Users/kodia/nuzlocke/.venv/Scripts/python.exe"
local TRACKER_MAIN_PATH = "C:/Users/kodia/nuzlocke/PokemonOverlay/tracker/main.py"
local TRACKER_CONFIG_PATH = "C:/Users/kodia/nuzlocke/PokemonOverlay/config.json"
local TRACKER_START_DEBUG = true

-- FireRed / Radical Red (FireRed-based) party memory layout.
-- Addresses are in EWRAM in the running ROM process space.
local ADDRESS_MAP = {
  party_count = 0x02024029,
  party_start = 0x02024284,
  saveblock1_ptr_addr = 0x03005008,
  saveblock2_ptr_addr = 0x0300500C,
  saveblock1_party_offset = 0x0038,
  saveblock1_flags_offset = 0x0EE0,
  saveblock1_flags_bytes = 0x120,
  saveblock2_trainer_name_offset = 0x0000,
  saveblock2_trainer_name_len = 8,
  saveblock2_trainer_id_offset = 0x000A,
  party_slot_size = 100,
  box_size = 80,
  status_offset = 0x50,
  level_offset = 0x54,
  current_hp_offset = 0x56,
  max_hp_offset = 0x58,
}

local PC_MAP = {
  record_size = 80,
  box_slots = 30,
  preferred_start = 0x02029000,
  preferred_end = 0x0202C000,
  search_start = 0x02024000,
  search_end = 0x02034000,
  rescan_seconds = 10.0,
  failed_rescan_seconds = 45.0,
  preferred_stride = 32,
  full_stride = 64,
  min_score = 12,
}

-- FireRed-family battle type flags (best-known live RAM location).
-- Non-zero means the game is currently in battle context.
local BATTLE_MAP = {
  battle_type_flags_addr = 0x02022B4C,
  battle_type_flags_mask = 0x003FFFFF,
}

local SUBSTRUCT_ORDERS = {
  {0,1,2,3},{0,1,3,2},{0,2,1,3},{0,3,1,2},{0,2,3,1},{0,3,2,1},
  {1,0,2,3},{1,0,3,2},{2,0,1,3},{3,0,1,2},{2,0,3,1},{3,0,2,1},
  {1,2,0,3},{1,3,0,2},{2,1,0,3},{3,1,0,2},{2,3,0,1},{3,2,0,1},
  {1,2,3,0},{1,3,2,0},{2,1,3,0},{3,1,2,0},{2,3,1,0},{3,2,1,0},
}

local ITEM_MAP = {
  [0] = nil,
  [79] = "oran_berry",
  [80] = "sitrus_berry",
}

local GEN3_CHAR_MAP = {
  [0x00] = " ", [0xAB] = "!", [0xAC] = "?", [0xAE] = ".", [0xB4] = "'", [0xB7] = "-", [0xB8] = ",",
}

for i = 0, 25 do
  GEN3_CHAR_MAP[0xBB + i] = string.char(string.byte("A") + i)
  GEN3_CHAR_MAP[0xD5 + i] = string.char(string.byte("a") + i)
end
for i = 0, 9 do
  GEN3_CHAR_MAP[0xA1 + i] = tostring(i)
end

local function log(msg)
  local line = "[mgba_bridge] " .. tostring(msg)
  print(line)
  local f = io.open(BRIDGE_LOG_PATH, "a")
  if f then
    f:write(line .. "\n")
    f:close()
  end
end

local BRIDGE_INSTANCE_KEY = "__POKEMON_OVERLAY_BRIDGE_INSTANCE_ID"
local BRIDGE_INSTANCE_ID = tostring(os.time()) .. "_" .. tostring(math.random(100000, 999999))
local previous_instance = _G[BRIDGE_INSTANCE_KEY]
_G[BRIDGE_INSTANCE_KEY] = BRIDGE_INSTANCE_ID

local function bridge_instance_is_active()
  return tostring(_G[BRIDGE_INSTANCE_KEY] or "") == BRIDGE_INSTANCE_ID
end

local function maybe_restart_tracker()
  if not AUTO_MANAGE_TRACKER then
    return
  end

  if not (os and type(os.execute) == "function") then
    log("auto tracker management skipped: os.execute unavailable")
    return
  end

  local arg_list_ps = string.format(
    "@('%s','--config','%s'%s)",
    TRACKER_MAIN_PATH,
    TRACKER_CONFIG_PATH,
    TRACKER_START_DEBUG and ",'--debug'" or ""
  )

  local ps = "$targets = Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and ($_.CommandLine -match 'PokemonOverlay/tracker/main.py' -or $_.CommandLine -match '_emit_bridge_updates.py') }; if($targets){ $targets | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue } }; Start-Process -FilePath '"
    .. TRACKER_PYTHON_PATH
    .. "' -ArgumentList "
    .. arg_list_ps
    .. " -WindowStyle Minimized"

  local command_ps = "powershell -NoProfile -ExecutionPolicy Bypass -Command \""
    .. ps
    .. "\""

  local ok_ps, _, exit_ps = os.execute(command_ps)
  if ok_ps then
    log("tracker restart command issued (powershell)")
    return
  end

  -- Fallback for environments where PowerShell invocation is restricted.
  local debug_arg = TRACKER_START_DEBUG and " --debug" or ""
  local kill_cmd = "wmic process where \"name='python.exe' and (CommandLine like '%PokemonOverlay/tracker/main.py%' or CommandLine like '%_emit_bridge_updates.py%')\" call terminate >NUL 2>NUL"
  local start_cmd = "start \"\" /MIN \"" .. TRACKER_PYTHON_PATH .. "\" \"" .. TRACKER_MAIN_PATH .. "\" --config \"" .. TRACKER_CONFIG_PATH .. "\"" .. debug_arg
  local command_cmd = "cmd /c \"" .. kill_cmd .. " & " .. start_cmd .. "\""

  local ok_cmd, _, exit_cmd = os.execute(command_cmd)
  if ok_cmd then
    log("tracker restart command issued (cmd fallback)")
  else
    log("tracker restart command failed (powershell=" .. tostring(exit_ps) .. ", cmd=" .. tostring(exit_cmd) .. ")")
  end
end

local has_bitops = (_G.bit32 ~= nil) or (_G.bit ~= nil)
if not has_bitops and _VERSION ~= "Lua 5.3" and _VERSION ~= "Lua 5.4" then
  error("No bit operations available in this Lua runtime")
end

local function band(a, b)
  if bit32 then return bit32.band(a, b) end
  if bit then return bit.band(a, b) end
  return a & b
end

local function bxor(a, b)
  if bit32 then return bit32.bxor(a, b) end
  if bit then return bit.bxor(a, b) end
  return a ~ b
end

local function rshift(a, n)
  if bit32 then return bit32.rshift(a, n) end
  if bit then return bit.rshift(a, n) end
  return a >> n
end

local function now_ms()
  return math.floor(os.clock() * 1000)
end

local function read_u8_raw(addr)
  if emu and emu.read8 then
    return emu:read8(addr)
  end
  if emu and emu.readU8 then
    return emu:readU8(addr)
  end
  if memory and memory.read8 then
    return memory.read8(addr)
  end
  if memory and memory.readbyte then
    return memory.readbyte(addr)
  end
  if memory and memory.read_u8 then
    return memory.read_u8(addr)
  end
  error("No supported memory read API found")
end

local function read_u8(addr)
  local ok, value = pcall(read_u8_raw, addr)
  if not ok then
    return nil, value
  end
  if type(value) ~= "number" then
    return nil, "non-numeric u8 read"
  end
  return band(value, 0xFF), nil
end

local function read_u16(addr)
  local b0, e0 = read_u8(addr)
  if not b0 then return nil, e0 end
  local b1, e1 = read_u8(addr + 1)
  if not b1 then return nil, e1 end
  return b0 + b1 * 256, nil
end

local function read_u32(addr)
  local b0, e0 = read_u8(addr)
  if not b0 then return nil, e0 end
  local b1, e1 = read_u8(addr + 1)
  if not b1 then return nil, e1 end
  local b2, e2 = read_u8(addr + 2)
  if not b2 then return nil, e2 end
  local b3, e3 = read_u8(addr + 3)
  if not b3 then return nil, e3 end
  return b0 + b1 * 256 + b2 * 65536 + b3 * 16777216, nil
end

local function read_bytes(addr, count)
  local out = {}
  for i = 0, count - 1 do
    local v, err = read_u8(addr + i)
    if not v then
      return nil, err
    end
    out[#out + 1] = v
  end
  return out, nil
end

local function u16_from(tbl, idx)
  local lo = tbl[idx + 1] or 0
  local hi = tbl[idx + 2] or 0
  return lo + hi * 256
end

local function u32_from(tbl, idx)
  local b0 = tbl[idx + 1] or 0
  local b1 = tbl[idx + 2] or 0
  local b2 = tbl[idx + 3] or 0
  local b3 = tbl[idx + 4] or 0
  return b0 + b1 * 256 + b2 * 65536 + b3 * 16777216
end

local function decode_gen3_string(raw)
  local chars = {}
  for i = 1, #raw do
    local b = raw[i]
    if b == 0xFF then
      break
    end
    chars[#chars + 1] = GEN3_CHAR_MAP[b] or ""
  end
  local out = table.concat(chars)
  if out == "" then
    return "missingno"
  end
  return out
end

local function is_blank_name(name)
  if not name then
    return true
  end
  local compact = string.gsub(name, "%s+", "")
  if compact == "" then
    return true
  end
  if not string.find(compact, "[A-Za-z0-9]") then
    return true
  end
  return false
end

local function decode_status(status_word, hp)
  if hp ~= nil and hp <= 0 then
    return "FNT"
  end
  if band(status_word, 0x7) ~= 0 then return "SLP" end
  if band(status_word, 0x80) ~= 0 then return "TOX" end
  if band(status_word, 0x10) ~= 0 then return "BRN" end
  if band(status_word, 0x20) ~= 0 then return "FRZ" end
  if band(status_word, 0x40) ~= 0 then return "PAR" end
  if band(status_word, 0x8) ~= 0 then return "PSN" end
  return nil
end

local function is_shiny(personality, ot_id)
  local tid = band(ot_id, 0xFFFF)
  local sid = band(rshift(ot_id, 16), 0xFFFF)
  local pid_low = band(personality, 0xFFFF)
  local pid_high = band(rshift(personality, 16), 0xFFFF)
  return band(bxor(bxor(tid, sid), bxor(pid_low, pid_high)), 0xFFFF) < 8
end

local function decrypt_substructs(encrypted48, personality, ot_id)
  if #encrypted48 ~= 48 then
    return nil
  end

  local key = bxor(personality, ot_id)
  local decrypted = {}
  for i = 0, 44, 4 do
    local chunk = u32_from(encrypted48, i)
    local dec = bxor(chunk, key)
    decrypted[#decrypted + 1] = band(dec, 0xFF)
    decrypted[#decrypted + 1] = band(rshift(dec, 8), 0xFF)
    decrypted[#decrypted + 1] = band(rshift(dec, 16), 0xFF)
    decrypted[#decrypted + 1] = band(rshift(dec, 24), 0xFF)
  end

  local order = SUBSTRUCT_ORDERS[(personality % 24) + 1]
  local canonical = { {}, {}, {}, {} }
  for encrypted_block_index = 0, 3 do
    local block_type = order[encrypted_block_index + 1]
    local block_start = encrypted_block_index * 12
    for j = 0, 11 do
      canonical[block_type + 1][j + 1] = decrypted[block_start + j + 1]
    end
  end

  local out = {}
  for block_type = 1, 4 do
    for j = 1, 12 do
      out[#out + 1] = canonical[block_type][j] or 0
    end
  end
  return out
end

local function checksum_decrypted48(decrypted)
  local checksum = 0
  for i = 0, 46, 2 do
    checksum = band(checksum + u16_from(decrypted, i), 0xFFFF)
  end
  return checksum
end

local function decode_growth(core80)
  local personality = u32_from(core80, 0)
  local ot_id = u32_from(core80, 4)
  local checksum_stored = u16_from(core80, 28)

  local species_plain = u16_from(core80, 32)
  local held_plain = u16_from(core80, 34)

  if checksum_stored == 0 and species_plain > 0 and species_plain <= 3000 then
    return species_plain, held_plain, "radical_red_plain"
  end

  local encrypted = {}
  for i = 32, 79 do
    encrypted[#encrypted + 1] = core80[i + 1]
  end
  local decrypted = decrypt_substructs(encrypted, personality, ot_id)
  if not decrypted then
    return nil, nil, "decrypt_failed"
  end

  local calc = checksum_decrypted48(decrypted)
  if calc ~= checksum_stored then
    if species_plain > 0 and species_plain <= 3000 then
      return species_plain, held_plain, "radical_red_plain_fallback"
    end
    return nil, nil, "checksum_mismatch"
  end

  return u16_from(decrypted, 0), u16_from(decrypted, 2), "vanilla_encrypted"
end

local function species_name(species_id)
  return "species_" .. tostring(species_id or 0)
end

local function held_item_name(item_id)
  if not item_id or item_id == 0 then
    return nil
  end
  return ITEM_MAP[item_id] or ("item_" .. tostring(item_id))
end

local function detect_game_mode(party)
  local title_bytes, _ = read_bytes(0x080000A0, 12)
  if title_bytes then
    local chars = {}
    for i = 1, #title_bytes do
      local b = title_bytes[i]
      if b >= 32 and b <= 126 then
        chars[#chars + 1] = string.char(b)
      end
    end
    local title = string.upper(table.concat(chars))
    if string.find(title, "RADICAL", 1, true) then
      return "radical_red"
    end
  end

  for _, mon in ipairs(party or {}) do
    if (mon.species_id or 0) > 411 then
      return "radical_red"
    end
  end
  return "vanilla_firered"
end

local TRAINER_DEFEAT_FLAGS = {
  { key = "FLAG_DEFEATED_BROCK", id = 0x4B0 },
  { key = "FLAG_DEFEATED_MISTY", id = 0x4B1 },
  { key = "FLAG_DEFEATED_LT_SURGE", id = 0x4B2 },
  { key = "FLAG_DEFEATED_ERIKA", id = 0x4B3 },
  { key = "FLAG_DEFEATED_KOGA", id = 0x4B4 },
  { key = "FLAG_DEFEATED_SABRINA", id = 0x4B5 },
  { key = "FLAG_DEFEATED_BLAINE", id = 0x4B6 },
  { key = "FLAG_DEFEATED_GIOVANNI", id = 0x4B7 },
  { key = "FLAG_DEFEATED_LORELEI", id = 0x4B8 },
  { key = "FLAG_DEFEATED_BRUNO", id = 0x4B9 },
  { key = "FLAG_DEFEATED_AGATHA", id = 0x4BA },
  { key = "FLAG_DEFEATED_LANCE", id = 0x4BB },
  { key = "FLAG_DEFEATED_CHAMP", id = 0x4BC },
}

local function candidate_saveblock1_bases()
  local out = {}

  local function push(base)
    if type(base) ~= "number" then
      return
    end
    if base < 0x02000000 or base > 0x0207FFFF then
      return
    end
    for i = 1, #out do
      if out[i] == base then
        return
      end
    end
    out[#out + 1] = base
  end

  -- FireRed-family RAM pointers (commonly used in decomp/CFRU builds).
  local ptr_addrs = {
    ADDRESS_MAP.saveblock1_ptr_addr,
    ADDRESS_MAP.saveblock2_ptr_addr,
    0x03005010,
  }
  for i = 1, #ptr_addrs do
    local ptr, _ = read_u32(ptr_addrs[i])
    if ptr then
      push(ptr)
    end
  end

  -- Legacy fixed-base approximation (kept as fallback).
  push(ADDRESS_MAP.party_start - ADDRESS_MAP.saveblock1_party_offset)

  return out
end

local function validate_saveblock1_base(base)
  if type(base) ~= "number" then
    return false
  end

  local party_count, party_count_err = read_u8(ADDRESS_MAP.party_count)
  if not party_count then
    return false
  end
  if party_count < 0 or party_count > 6 then
    return false
  end

  local flags_raw, flags_err = read_bytes(base + ADDRESS_MAP.saveblock1_flags_offset, ADDRESS_MAP.saveblock1_flags_bytes)
  if not flags_raw then
    return false
  end

  if party_count > 0 then
    local live_personality, live_err = read_u32(ADDRESS_MAP.party_start)
    local save_party_personality, save_err = read_u32(base + ADDRESS_MAP.saveblock1_party_offset)
    if live_personality and save_party_personality and live_personality ~= 0 and save_party_personality ~= 0 then
      if live_personality ~= save_party_personality then
        return false
      end
    elseif live_err and save_err then
      return false
    end
  end

  return true
end

local function resolve_saveblock1_base()
  local candidates = candidate_saveblock1_bases()
  for i = 1, #candidates do
    local base = candidates[i]
    if validate_saveblock1_base(base) then
      return base, nil
    end
  end

  -- If no candidate validates, still return the first candidate as best effort.
  if #candidates > 0 then
    return candidates[1], "saveblock1_unvalidated"
  end

  return nil, "saveblock1_unresolved"
end

local function candidate_saveblock2_bases()
  local out = {}

  local function push(base)
    if type(base) ~= "number" then
      return
    end
    if base < 0x02000000 or base > 0x0207FFFF then
      return
    end
    for i = 1, #out do
      if out[i] == base then
        return
      end
    end
    out[#out + 1] = base
  end

  local ptr, _ = read_u32(ADDRESS_MAP.saveblock2_ptr_addr)
  if ptr then
    push(ptr)
  end

  local saveblock1_base, _ = resolve_saveblock1_base()
  if saveblock1_base then
    push(saveblock1_base)
  end

  return out
end

local function validate_saveblock2_base(base)
  if type(base) ~= "number" then
    return false
  end

  local trainer_id_full, _ = read_u32(base + ADDRESS_MAP.saveblock2_trainer_id_offset)
  if not trainer_id_full or trainer_id_full == 0 then
    return false
  end

  local name_raw, _ = read_bytes(base + ADDRESS_MAP.saveblock2_trainer_name_offset, ADDRESS_MAP.saveblock2_trainer_name_len)
  if not name_raw then
    return false
  end

  local trainer_name = decode_gen3_string(name_raw)
  if is_blank_name(trainer_name) then
    return false
  end

  return true
end

local function resolve_saveblock2_base()
  local candidates = candidate_saveblock2_bases()
  for i = 1, #candidates do
    local base = candidates[i]
    if validate_saveblock2_base(base) then
      return base, nil
    end
  end

  if #candidates > 0 then
    return candidates[1], "saveblock2_unvalidated"
  end

  return nil, "saveblock2_unresolved"
end

local function read_trainer_defeat_flags()
  local saveblock1_base, base_err = resolve_saveblock1_base()
  if not saveblock1_base then
    return {}, {}, {}, tostring(base_err or "saveblock1_missing")
  end
  local flags_addr = saveblock1_base + ADDRESS_MAP.saveblock1_flags_offset
  local flags_raw, err = read_bytes(flags_addr, ADDRESS_MAP.saveblock1_flags_bytes)
  if not flags_raw then
    return {}, {}, {}, "flags_read_failed: " .. tostring(err)
  end

  local out_flags = {}
  local out_keys = {}
  for i = 1, #TRAINER_DEFEAT_FLAGS do
    local def = TRAINER_DEFEAT_FLAGS[i]
    local bit = tonumber(def.id or -1)
    local byte_index = math.floor(bit / 8)
    local mask = 2 ^ (bit % 8)
    local byte_value = flags_raw[byte_index + 1] or 0
    local defeated = band(byte_value, mask) ~= 0
    out_flags[def.key] = defeated
    if defeated then
      out_keys[#out_keys + 1] = def.key
    end
  end

  if base_err then
    return out_flags, out_keys, flags_raw, tostring(base_err)
  end

  return out_flags, out_keys, flags_raw, nil
end

local function read_trainer_profile_meta()
  local saveblock2_base, base_err = resolve_saveblock2_base()
  if not saveblock2_base then
    return {}, tostring(base_err or "saveblock2_missing")
  end
  local trainer_id_full, id_err = read_u32(saveblock2_base + ADDRESS_MAP.saveblock2_trainer_id_offset)
  if not trainer_id_full then
    return {}, "trainer_id_read_failed: " .. tostring(id_err)
  end

  local name_raw, name_err = read_bytes(
    saveblock2_base + ADDRESS_MAP.saveblock2_trainer_name_offset,
    ADDRESS_MAP.saveblock2_trainer_name_len
  )
  if not name_raw then
    return {
      trainer_id = trainer_id_full,
      trainer_public_id = band(trainer_id_full, 0xFFFF),
      trainer_secret_id = band(rshift(trainer_id_full, 16), 0xFFFF),
      trainer_name = "",
      trainer_profile_key = string.format(
        "%05d-%05d",
        band(trainer_id_full, 0xFFFF),
        band(rshift(trainer_id_full, 16), 0xFFFF)
      ),
    }, "trainer_name_read_failed: " .. tostring(name_err)
  end

  local trainer_name = decode_gen3_string(name_raw)
  local public_id = band(trainer_id_full, 0xFFFF)
  local secret_id = band(rshift(trainer_id_full, 16), 0xFFFF)

  return {
    trainer_id = trainer_id_full,
    trainer_public_id = public_id,
    trainer_secret_id = secret_id,
    trainer_name = trainer_name,
    trainer_profile_key = string.format("%05d-%05d", public_id, secret_id),
  }, base_err
end

local function read_in_battle_flag()
  local raw, err = read_u32(BATTLE_MAP.battle_type_flags_addr)
  if not raw then
    return false, "battle_flag_read_failed: " .. tostring(err)
  end

  local masked = band(raw, BATTLE_MAP.battle_type_flags_mask)
  return masked ~= 0, nil
end

local function decode_party_slot(slot_addr, slot_index)
  local core80, err = read_bytes(slot_addr, ADDRESS_MAP.box_size)
  if not core80 then
    return nil, "core_read_failed: " .. tostring(err)
  end

  local personality = u32_from(core80, 0)
  local ot_id = u32_from(core80, 4)
  if personality == 0 and ot_id == 0 then
    return nil, "empty"
  end

  local species_id, held_item_id, growth_mode = decode_growth(core80)
  if not species_id or species_id <= 0 or species_id > 3000 then
    return nil, "species_invalid"
  end

  local nick_raw = {}
  for i = 8, 17 do
    nick_raw[#nick_raw + 1] = core80[i + 1]
  end
  local nickname = decode_gen3_string(nick_raw)

  local level, e_level = read_u8(slot_addr + ADDRESS_MAP.level_offset)
  if not level then
    return nil, "level_read_failed: " .. tostring(e_level)
  end
  local status_word, e_status = read_u32(slot_addr + ADDRESS_MAP.status_offset)
  if not status_word then
    return nil, "status_read_failed: " .. tostring(e_status)
  end
  local current_hp, e_hp = read_u16(slot_addr + ADDRESS_MAP.current_hp_offset)
  if not current_hp then
    return nil, "hp_read_failed: " .. tostring(e_hp)
  end
  local max_hp, e_mhp = read_u16(slot_addr + ADDRESS_MAP.max_hp_offset)
  if not max_hp then
    return nil, "maxhp_read_failed: " .. tostring(e_mhp)
  end

  local mon = {
    species = species_name(species_id),
    species_id = species_id,
    nickname = nickname,
    level = level,
    gender = "unknown",
    shiny = is_shiny(personality, ot_id),
    held_item = held_item_name(held_item_id),
    slot = slot_index,
    current_hp = current_hp,
    max_hp = max_hp,
    status = decode_status(status_word, current_hp),
    types = {},
    _growth_mode = growth_mode,
  }

  return mon, nil
end

local function read_party_from_memory()
  local count, err = read_u8(ADDRESS_MAP.party_count)
  if not count then
    return {}, "party_count_read_failed: " .. tostring(err)
  end
  if count < 0 then count = 0 end
  if count > 6 then count = 6 end

  local party = {}
  local failures = 0
  for i = 0, count - 1 do
    local slot_addr = ADDRESS_MAP.party_start + i * ADDRESS_MAP.party_slot_size
    local ok, mon_or_nil, reason = pcall(decode_party_slot, slot_addr, i + 1)
    if ok and mon_or_nil then
      mon_or_nil._growth_mode = nil
      party[#party + 1] = mon_or_nil
    else
      failures = failures + 1
      if ok and reason and reason ~= "empty" then
        log(string.format("slot %d decode warning: %s", i + 1, tostring(reason)))
      elseif not ok then
        log(string.format("slot %d decode error: %s", i + 1, tostring(mon_or_nil)))
      end
    end
  end

  local detail = string.format("party_count=%d parsed=%d failures=%d", count, #party, failures)
  return party, detail
end

local function decode_pc_record_at(addr, slot, box)
  local rec, err = read_bytes(addr, PC_MAP.record_size)
  if not rec then
    return nil, err
  end

  local personality = u32_from(rec, 0)
  local ot_id = u32_from(rec, 4)
  if personality == 0 and ot_id == 0 then
    return nil, "empty"
  end

  local species_id, held_item_id, growth_mode = decode_growth(rec)
  if not species_id or species_id <= 0 or species_id > 3000 then
    return nil, "species_invalid"
  end

  local nick_raw = {}
  for i = 8, 17 do
    nick_raw[#nick_raw + 1] = rec[i + 1]
  end
  local nickname = decode_gen3_string(nick_raw)
  if nickname == "missingno" or is_blank_name(nickname) then
    return nil, "missingno"
  end

  if growth_mode ~= "vanilla_encrypted" and growth_mode ~= "radical_red_plain" then
    return nil, "growth_invalid"
  end

  if held_item_id == 65535 then
    return nil, "item_invalid"
  end

  return {
    species = species_name(species_id),
    species_id = species_id,
    nickname = nickname,
    level = nil,
    gender = "unknown",
    shiny = is_shiny(personality, ot_id),
    held_item = held_item_name(held_item_id),
    slot = slot,
    box = box,
    box_slot = slot,
    types = {},
  }, nil
end

local function score_pc_base(base)
  local score = 0
  local sampled = 0
  local sample_slots = {1, 2, 3, 4, 5, 6, 10, 15, 20, 25, 30}
  for i = 1, #sample_slots do
    local slot = sample_slots[i]
    local off = base + ((slot - 1) * PC_MAP.record_size)
    local mon = decode_pc_record_at(off, slot, 1)
    sampled = sampled + 1
    if mon and mon.nickname and mon.nickname ~= "missingno" then
      score = score + 1
      if mon.species_id and mon.species_id > 0 and mon.species_id <= 3000 then
        score = score + 1
      end
    end
  end
  return score, sampled
end

local next_pc_scan_clock = -999.0
local cached_pc_base = nil

local function find_pc_base(now)
  if cached_pc_base ~= nil then
    return cached_pc_base
  end

  if now < next_pc_scan_clock then
    return nil
  end

  local best_base = nil
  local best_score = -1

  local window = PC_MAP.record_size * PC_MAP.box_slots

  local function scan_range(start_addr, end_addr, stride)
    for base = start_addr, (end_addr - window), stride do
      local score, sampled = score_pc_base(base)
      if sampled > 0 and score > best_score then
        best_score = score
        best_base = base
      end
    end
  end

  scan_range(PC_MAP.preferred_start, PC_MAP.preferred_end, PC_MAP.preferred_stride)
  if best_score < PC_MAP.min_score then
    scan_range(PC_MAP.search_start, PC_MAP.search_end, PC_MAP.full_stride)
  end

  if best_base ~= nil then
    local refine_start = math.max(PC_MAP.search_start, best_base - 16)
    local refine_end = math.min(PC_MAP.search_end - window, best_base + 16)
    for base = refine_start, refine_end, 2 do
      local score, sampled = score_pc_base(base)
      if sampled > 0 and score > best_score then
        best_score = score
        best_base = base
      end
    end
  end

  if best_base ~= nil and best_score >= PC_MAP.min_score then
    cached_pc_base = best_base
    next_pc_scan_clock = now + PC_MAP.rescan_seconds
    log(string.format("pc base selected: 0x%08X score=%d", best_base, best_score))
  else
    cached_pc_base = nil
    next_pc_scan_clock = now + PC_MAP.failed_rescan_seconds
    log("pc base scan inconclusive; deferring next scan")
  end

  return cached_pc_base
end

local function read_current_box_pc(now)
  local base = find_pc_base(now)
  if not base then
    return {}, "pc_base_not_found"
  end

  local out = {}
  local failures = 0
  local box = 1
  for slot = 1, PC_MAP.box_slots do
    local off = base + ((slot - 1) * PC_MAP.record_size)
    local mon, reason = decode_pc_record_at(off, slot, box)
    if mon then
      out[#out + 1] = mon
    elseif reason and reason ~= "empty" and reason ~= "missingno" then
      failures = failures + 1
    end
  end

  if #out == 0 then
    cached_pc_base = nil
    return {}, "pc_base_invalid"
  end

  local detail = string.format("pc_base=0x%08X parsed=%d failures=%d", base, #out, failures)
  return out, detail
end

local function json_escape(s)
  if s == nil then
    return ""
  end
  s = tostring(s)
  s = s:gsub('\\', '\\\\')
  s = s:gsub('"', '\\"')
  s = s:gsub('\n', '\\n')
  s = s:gsub('\r', '\\r')
  s = s:gsub('\t', '\\t')
  return s
end

local function encode_types_json(types)
  local rows = {}
  for i = 1, #(types or {}) do
    rows[#rows + 1] = '"' .. json_escape(types[i]) .. '"'
  end
  return "[" .. table.concat(rows, ",") .. "]"
end

local function encode_string_array_json(values)
  local rows = {}
  for i = 1, #(values or {}) do
    rows[#rows + 1] = '"' .. json_escape(values[i]) .. '"'
  end
  return "[" .. table.concat(rows, ",") .. "]"
end

local function encode_u8_array_json(values)
  local rows = {}
  for i = 1, #(values or {}) do
    rows[#rows + 1] = tostring(tonumber(values[i] or 0))
  end
  return "[" .. table.concat(rows, ",") .. "]"
end

local function encode_trainer_flags_json(flags)
  local rows = {}
  for i = 1, #TRAINER_DEFEAT_FLAGS do
    local key = TRAINER_DEFEAT_FLAGS[i].key
    rows[#rows + 1] = string.format('"%s":%s', json_escape(key), flags[key] and "true" or "false")
  end
  return "{" .. table.concat(rows, ",") .. "}"
end

local function encode_trainer_profile_fields(meta)
  if type(meta) ~= "table" then
    return ""
  end
  local trainer_id = tonumber(meta.trainer_id)
  local public_id = tonumber(meta.trainer_public_id)
  local secret_id = tonumber(meta.trainer_secret_id)
  local trainer_name = tostring(meta.trainer_name or "")
  local trainer_profile_key = tostring(meta.trainer_profile_key or "")
  if not trainer_id or not public_id or not secret_id then
    return ""
  end
  return string.format(
    ',"trainer_id":%d,"trainer_public_id":%d,"trainer_secret_id":%d,"trainer_name":"%s","trainer_profile_key":"%s"',
    trainer_id,
    public_id,
    secret_id,
    json_escape(trainer_name),
    json_escape(trainer_profile_key)
  )
end

local function encode_party_json(party)
  local rows = {}
  for i, mon in ipairs(party) do
    rows[#rows + 1] = string.format(
      '{"species":"%s","species_id":%d,"nickname":"%s","level":%d,"gender":"%s","shiny":%s,"held_item":%s,"slot":%d,"current_hp":%d,"max_hp":%d,"status":%s,"types":%s}',
      json_escape(mon.species or "missingno"),
      tonumber(mon.species_id or 0),
      json_escape(mon.nickname or "Unknown"),
      tonumber(mon.level or 0),
      json_escape(mon.gender or "unknown"),
      mon.shiny and "true" or "false",
      mon.held_item and ('"' .. json_escape(mon.held_item) .. '"') or "null",
      tonumber(mon.slot or i),
      tonumber(mon.current_hp or 0),
      tonumber(mon.max_hp or 0),
      mon.status and ('"' .. json_escape(mon.status) .. '"') or "null",
      encode_types_json(mon.types)
    )
  end
  return "[" .. table.concat(rows, ",") .. "]"
end

local function encode_pc_json(pc)
  local rows = {}
  for i, mon in ipairs(pc) do
    rows[#rows + 1] = string.format(
      '{"species":"%s","species_id":%d,"nickname":"%s","level":null,"gender":"%s","shiny":%s,"held_item":%s,"slot":%d,"box":%d,"box_slot":%d,"types":%s}',
      json_escape(mon.species or "missingno"),
      tonumber(mon.species_id or 0),
      json_escape(mon.nickname or "Unknown"),
      json_escape(mon.gender or "unknown"),
      mon.shiny and "true" or "false",
      mon.held_item and ('"' .. json_escape(mon.held_item) .. '"') or "null",
      tonumber(mon.slot or i),
      tonumber(mon.box or 1),
      tonumber(mon.box_slot or i),
      encode_types_json(mon.types)
    )
  end
  return "[" .. table.concat(rows, ",") .. "]"
end

local function atomic_write(path, temp_path, payload)
  local f, err = io.open(temp_path, "wb")
  if not f then
    return false, "open_failed: " .. tostring(err)
  end
  local okw, ew = f:write(payload)
  if not okw then
    f:close()
    return false, "temp_write_failed: " .. tostring(ew)
  end
  f:close()

  os.remove(path)
  local okr, er = os.rename(temp_path, path)
  if not okr then
    os.remove(temp_path)
    return false, "rename_failed: " .. tostring(er)
  end
  return true, nil
end

local function build_payload(
  party,
  pc,
  detail,
  game_mode,
  pc_detail,
  in_battle,
  trainer_flags,
  trainer_flag_keys,
  trainer_flag_bytes,
  trainer_profile_meta
)
  return string.format(
    '{"timestamp_ms":%d,"party":%s,"pc":%s,"dead":[],"meta":{"provider":"mgba_live","game_mode":"%s","detail":"%s","pc_detail":"%s","in_battle":%s,"pc_scope":"current_box","pc_box_known":false,"trainer_defeat_flags":%s,"trainer_defeat_flag_keys":%s,"trainer_defeat_flags_bytes":%s%s}}',
    now_ms(),
    encode_party_json(party),
    encode_pc_json(pc),
    json_escape(game_mode or "unknown"),
    json_escape(detail or "ok"),
    json_escape(pc_detail or ""),
    in_battle and "true" or "false",
    encode_trainer_flags_json(trainer_flags or {}),
    encode_string_array_json(trainer_flag_keys or {}),
    encode_u8_array_json(trainer_flag_bytes or {}),
    encode_trainer_profile_fields(trainer_profile_meta or {})
  )
end

local function try_call(target, name)
  if not target then
    return false
  end

  local fn = target[name]
  if type(fn) ~= "function" then
    return false
  end

  -- Try method-style first (fn(self, ...)), then plain function-style.
  local ok_method = pcall(fn, target)
  if ok_method then
    return true
  end

  local ok_fn = pcall(fn)
  if ok_fn then
    return true
  end

  return false
end

local warned_no_frame_api = false
local last_write_clock = 0.0
local write_counter = 0

local function frame_advance()
  local names = {
    "frameAdvance",
    "frameadvance",
    "yield",
  }

  for i = 1, #names do
    local name = names[i]
    if try_call(emu, name) then
      return true
    end
  end

  -- Some builds expose globals rather than emu methods.
  for i = 1, #names do
    local name = names[i]
    local global_fn = _G[name]
    if type(global_fn) == "function" then
      local ok = pcall(global_fn)
      if ok then
        return true
      end
    end
  end

  -- Last resort: do not spin forever without yielding a frame.
  if not warned_no_frame_api then
    warned_no_frame_api = true
    log("error: no recognized frame advance API; stopping bridge to avoid emulator freeze")
  end
  return false
end

local function bridge_write_tick(now)
  if not bridge_instance_is_active() then
    return
  end
  if (now - last_write_clock) < WRITE_INTERVAL_SECONDS then
    return
  end
  last_write_clock = now

  local ok_read, party, detail = pcall(read_party_from_memory)
  if not ok_read then
    log("memory read failure: " .. tostring(party))
    party = {}
    detail = "read_exception"
  end

  local game_mode = detect_game_mode(party)
  local pc = {}
  local pc_detail = "pc_scan_disabled"
  if ENABLE_PC_SCAN then
    pc, pc_detail = read_current_box_pc(now)
  end
  local trainer_flags, trainer_flag_keys, trainer_flag_bytes, trainer_flag_err = read_trainer_defeat_flags()
  if trainer_flag_err then
    detail = tostring(detail) .. " | " .. tostring(trainer_flag_err)
  end
  local trainer_profile_meta, trainer_profile_err = read_trainer_profile_meta()
  if trainer_profile_err then
    detail = tostring(detail) .. " | " .. tostring(trainer_profile_err)
  end
  local in_battle, in_battle_err = read_in_battle_flag()
  if in_battle_err then
    detail = tostring(detail) .. " | " .. tostring(in_battle_err)
  end
  local payload = build_payload(
    party,
    pc,
    detail,
    game_mode,
    pc_detail,
    in_battle,
    trainer_flags,
    trainer_flag_keys,
    trainer_flag_bytes,
    trainer_profile_meta
  )
  local ok_write, err = atomic_write(BRIDGE_PATH, TEMP_PATH, payload)
  if ok_write then
    write_counter = write_counter + 1
    if (write_counter % 20) == 0 then
      local profile_key = ""
      if type(trainer_profile_meta) == "table" then
        profile_key = tostring(trainer_profile_meta.trainer_profile_key or "")
      end
      log(string.format("write ok #%d %s trainer_profile_key=%s", write_counter, tostring(detail), profile_key))
    end
  else
    log("write failure: " .. tostring(err))
  end
end

local function try_register_frame_callback()
  local function on_frame()
    if not bridge_instance_is_active() then
      return
    end
    bridge_write_tick(os.clock())
  end

  local attempts = {
    function()
      if callbacks and type(callbacks.add) == "function" then
        local ok = pcall(callbacks.add, callbacks, "frame", on_frame)
        if ok then return true end
        ok = pcall(callbacks.add, "frame", on_frame)
        if ok then return true end
      end
      return false
    end,
    function()
      if callbacks and type(callbacks.register) == "function" then
        local ok = pcall(callbacks.register, callbacks, "frame", on_frame)
        if ok then return true end
        ok = pcall(callbacks.register, "frame", on_frame)
        if ok then return true end
      end
      return false
    end,
    function()
      if event and type(event.onframeend) == "function" then
        local ok = pcall(event.onframeend, on_frame)
        if ok then return true end
      end
      return false
    end,
    function()
      if event and type(event.onframestart) == "function" then
        local ok = pcall(event.onframestart, on_frame)
        if ok then return true end
      end
      return false
    end,
  }

  for i = 1, #attempts do
    local ok = false
    local call_ok, result = pcall(attempts[i])
    if call_ok and result then
      ok = true
    end
    if ok then
      return true
    end
  end

  return false
end

log("bridge started")
if previous_instance and tostring(previous_instance) ~= "" then
  log("superseding previous bridge instance " .. tostring(previous_instance))
end
log(string.format("party_count=0x%08X party_start=0x%08X", ADDRESS_MAP.party_count, ADDRESS_MAP.party_start))
maybe_restart_tracker()

local tight_loop_count = 0
local last_loop_clock = os.clock()

local function loop_guard_check()
  local now = os.clock()
  local delta = now - last_loop_clock
  last_loop_clock = now

  -- If frame advance fails to yield, this loop can spin and freeze mGBA.
  if delta < 0.0005 then
    tight_loop_count = tight_loop_count + 1
  else
    tight_loop_count = 0
  end

  if tight_loop_count > 200 then
    log("error: bridge loop detected non-yielding frame API; stopping to prevent freeze")
    return false
  end
  return true
end

while true do
  if not bridge_instance_is_active() then
    log("bridge instance superseded; stopping old script")
    break
  end

  -- Prefer callback-driven ticking when available to avoid tight manual loops.
  if try_register_frame_callback() then
    log("registered frame callback mode")
    return
  end

  local now = os.clock()
  bridge_write_tick(now)

  local advanced = frame_advance()
  if not advanced then
    break
  end

  if not loop_guard_check() then
    break
  end
end
