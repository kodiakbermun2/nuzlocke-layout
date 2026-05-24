-- mGBA live memory bridge for PokemonOverlay.
--
-- Goals:
-- - Write live party state to tracker/memory_state.json every ~100ms.
-- - Keep writes atomic and resilient.
-- - Report diagnostics in console.

local BRIDGE_PATH = "C:/Users/kodia/nuzlocke/PokemonOverlay/tracker/memory_state.json"
local TEMP_PATH = BRIDGE_PATH .. ".tmp"
local WRITE_INTERVAL_SECONDS = 0.25
local ENABLE_PC_SCAN = false

-- FireRed / Radical Red (FireRed-based) party memory layout.
-- Addresses are in EWRAM in the running ROM process space.
local ADDRESS_MAP = {
  party_count = 0x02024029,
  party_start = 0x02024284,
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
  min_score = 12,
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
  print("[mgba_bridge] " .. tostring(msg))
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

local last_pc_scan_clock = -999.0
local cached_pc_base = nil

local function find_pc_base(now)
  if cached_pc_base ~= nil then
    return cached_pc_base
  end

  if (now - last_pc_scan_clock) < PC_MAP.rescan_seconds then
    return nil
  end

  last_pc_scan_clock = now
  local best_base = nil
  local best_score = -1

  local window = PC_MAP.record_size * PC_MAP.box_slots

  local function scan_range(start_addr, end_addr)
    for base = start_addr, (end_addr - window), 16 do
      local score, sampled = score_pc_base(base)
      if sampled > 0 and score > best_score then
        best_score = score
        best_base = base
      end
    end
  end

  scan_range(PC_MAP.preferred_start, PC_MAP.preferred_end)
  if best_score < PC_MAP.min_score then
    scan_range(PC_MAP.search_start, PC_MAP.search_end)
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
    log(string.format("pc base selected: 0x%08X score=%d", best_base, best_score))
  else
    cached_pc_base = nil
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
  -- Prefer direct overwrite on Windows to avoid delete/rename races that can
  -- make readers observe transient missing-file states.
  local direct, derr = io.open(path, "wb")
  if direct then
    local okw, ew = direct:write(payload)
    direct:close()
    if okw then
      return true, nil
    end
    return false, "direct_write_failed: " .. tostring(ew)
  end

  local f, err = io.open(temp_path, "wb")
  if not f then
    return false, "open_failed: " .. tostring(err or derr)
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

local function build_payload(party, pc, detail, game_mode, pc_detail)
  return string.format(
    '{"timestamp_ms":%d,"party":%s,"pc":%s,"dead":[],"meta":{"provider":"mgba_live","game_mode":"%s","detail":"%s","pc_detail":"%s","pc_scope":"current_box","pc_box_known":false}}',
    now_ms(),
    encode_party_json(party),
    encode_pc_json(pc),
    json_escape(game_mode or "unknown"),
    json_escape(detail or "ok"),
    json_escape(pc_detail or "")
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
  local payload = build_payload(party, pc, detail, game_mode, pc_detail)
  local ok_write, err = atomic_write(BRIDGE_PATH, TEMP_PATH, payload)
  if ok_write then
    write_counter = write_counter + 1
    if (write_counter % 20) == 0 then
      log(string.format("write ok #%d %s", write_counter, tostring(detail)))
    end
  else
    log("write failure: " .. tostring(err))
  end
end

local function try_register_frame_callback()
  local function on_frame()
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
log(string.format("party_count=0x%08X party_start=0x%08X", ADDRESS_MAP.party_count, ADDRESS_MAP.party_start))

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
