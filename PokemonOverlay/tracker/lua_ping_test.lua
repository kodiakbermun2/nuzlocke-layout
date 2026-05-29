local MARKER_PATH = "C:/Users/kodia/nuzlocke/PokemonOverlay/tracker/lua_ping_marker.txt"

local function append_line(line)
  local f = io.open(MARKER_PATH, "a")
  if f then
    f:write(tostring(line) .. "\n")
    f:close()
  end
end

local function log(msg)
  local line = "[lua_ping_test] " .. tostring(msg)
  print(line)
  append_line(line)
end

local function stamp(tag)
  local now = os.time and os.time() or 0
  log(tag .. " t=" .. tostring(now))
end

stamp("script loaded")

local tick = 0
local function on_frame()
  tick = tick + 1
  if (tick % 120) == 0 then
    stamp("frame tick=" .. tostring(tick))
  end
end

if event and type(event.onframeend) == "function" then
  event.onframeend(on_frame)
  stamp("registered via event.onframeend")
elseif event and type(event.onframestart) == "function" then
  event.onframestart(on_frame)
  stamp("registered via event.onframestart")
elseif callbacks and type(callbacks.add) == "function" then
  local ok = pcall(callbacks.add, callbacks, "frame", on_frame)
  if not ok then
    pcall(callbacks.add, "frame", on_frame)
  end
  stamp("registered via callbacks.add")
else
  stamp("no frame callback API found")
end
