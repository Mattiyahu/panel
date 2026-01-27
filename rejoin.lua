#!/usr/bin/env lua
--[[
    REJOIN TOOL v2.0.1
    Auto-rejoin Roblox ke Private Server
    For Termux/Android (Cloud Phone)
    
    Features:
    - Auto-detect packages
    - Private server URL
    - Cookie management
    - Discord webhook alerts
    - Script injection (autoexecute)
]]

-- ============================================
-- CONFIGURATION
-- ============================================
local VERSION = "2.1.0"
local CONFIG_FILE = "/sdcard/download/rejoin_config.json"
local COOKIES_FILE = "/sdcard/download/rejoin_cookies.txt"
local SCRIPTS_DIR = "/sdcard/download/rejoin_scripts/"
local BANNER_COLOR = "\27[32m"  -- Green
local RESET = "\27[0m"
local CYAN = "\27[36m"
local YELLOW = "\27[33m"
local RED = "\27[31m"
local WHITE = "\27[37m"
local MAGENTA = "\27[35m"

-- ============================================
-- UTILITY FUNCTIONS
-- ============================================
local function clear_screen()
    os.execute("clear")
end

local function sleep(seconds)
    os.execute("sleep " .. seconds)
end

local function execute_command(cmd)
    local handle = io.popen(cmd)
    local result = handle:read("*a")
    handle:close()
    return result
end

local function file_exists(path)
    local file = io.open(path, "r")
    if file then
        file:close()
        return true
    end
    return false
end

local function read_file(path)
    local file = io.open(path, "r")
    if not file then return nil end
    local content = file:read("*a")
    file:close()
    return content
end

local function write_file(path, content)
    local file = io.open(path, "w")
    if not file then return false end
    file:write(content)
    file:close()
    return true
end

local function append_file(path, content)
    local file = io.open(path, "a")
    if not file then return false end
    file:write(content)
    file:close()
    return true
end

local function mkdir(path)
    os.execute("mkdir -p " .. path)
end

local function escape_json_string(s)
    return s:gsub('\\', '\\\\'):gsub('"', '\\"'):gsub('\n', '\\n')
end

-- JSON encode with nested tables support
local function json_encode(tbl, indent)
    indent = indent or 0
    local spaces = string.rep("  ", indent)
    local result = "{\n"
    local first = true
    
    for k, v in pairs(tbl) do
        if not first then result = result .. ",\n" end
        first = false
        
        if type(v) == "table" then
            if #v > 0 or next(v) == nil then
                -- Array
                result = result .. spaces .. '  "' .. k .. '": ['
                for i, item in ipairs(v) do
                    if i > 1 then result = result .. ", " end
                    if type(item) == "string" then
                        result = result .. '"' .. escape_json_string(item) .. '"'
                    else
                        result = result .. tostring(item)
                    end
                end
                result = result .. ']'
            else
                -- Object
                result = result .. spaces .. '  "' .. k .. '": ' .. json_encode(v, indent + 1)
            end
        elseif type(v) == "number" then
            result = result .. spaces .. '  "' .. k .. '": ' .. v
        elseif type(v) == "boolean" then
            result = result .. spaces .. '  "' .. k .. '": ' .. tostring(v)
        else
            result = result .. spaces .. '  "' .. k .. '": "' .. escape_json_string(tostring(v)) .. '"'
        end
    end
    result = result .. "\n" .. spaces .. "}"
    return result
end

local function json_decode(str)
    local result = {
        packages = {},
        scripts = {},
        private_server_url = "",
        discord_webhook = "",
        mask_username = false,
        inject_scripts = false,
        delay_between_launch = 8,
        delay_before_rejoin = 60
    }
    
    -- Parse packages array
    local packages_match = str:match('"packages"%s*:%s*%[(.-)%]')
    if packages_match then
        for pkg in packages_match:gmatch('"([^"]+)"') do
            table.insert(result.packages, pkg)
        end
    end
    
    -- Parse scripts array
    local scripts_match = str:match('"scripts"%s*:%s*%[(.-)%]')
    if scripts_match then
        for script in scripts_match:gmatch('"([^"]+)"') do
            table.insert(result.scripts, script)
        end
    end
    
    -- Parse strings
    result.private_server_url = str:match('"private_server_url"%s*:%s*"([^"]*)"') or ""
    result.discord_webhook = str:match('"discord_webhook"%s*:%s*"([^"]*)"') or ""
    
    -- Parse booleans
    result.mask_username = str:match('"mask_username"%s*:%s*true') ~= nil
    result.inject_scripts = str:match('"inject_scripts"%s*:%s*true') ~= nil
    
    -- Parse numbers
    result.delay_between_launch = tonumber(str:match('"delay_between_launch"%s*:%s*(%d+)')) or 8
    result.delay_before_rejoin = tonumber(str:match('"delay_before_rejoin"%s*:%s*(%d+)')) or 60
    
    return result
end

-- ============================================
-- UI FUNCTIONS
-- ============================================
local function print_banner()
    clear_screen()
    print(BANNER_COLOR .. [[
╔═══════════════════════════════════════════╗
║         REJOIN TOOL - Main Menu           ║
║         Version: ]] .. VERSION .. [[ (2025-12-23)         ║
╚═══════════════════════════════════════════╝]] .. RESET)
    print()
end

local function print_colored(color, text)
    print(color .. text .. RESET)
end

local function prompt(message)
    io.write(CYAN .. message .. RESET)
    io.flush()
    return io.read()
end

local function prompt_yn(message, default)
    local def_str = default and "[Y/n]" or "[y/N]"
    io.write(CYAN .. message .. " " .. def_str .. ": " .. RESET)
    io.flush()
    local answer = io.read():lower()
    if answer == "" then return default end
    return answer == "y" or answer == "yes"
end

-- ============================================
-- DISCORD WEBHOOK
-- ============================================
local function send_discord_webhook(webhook_url, title, message, color)
    if not webhook_url or webhook_url == "" then return end
    
    color = color or 16711680  -- Red default
    local payload = string.format(
        '{"embeds":[{"title":"%s","description":"%s","color":%d,"timestamp":"%s"}]}',
        escape_json_string(title),
        escape_json_string(message),
        color,
        os.date("!%Y-%m-%dT%H:%M:%SZ")
    )
    
    local cmd = string.format(
        'curl -s -X POST -H "Content-Type: application/json" -d \'%s\' "%s" 2>/dev/null',
        payload,
        webhook_url
    )
    os.execute(cmd)
end

-- ============================================
-- PACKAGE DETECTION
-- ============================================
local function auto_detect_packages()
    print_colored(YELLOW, "[i] Auto-detecting packages...")
    
    local cmd = "pm list packages 2>/dev/null | grep -i roblox | sed 's/package://g'"
    local result = execute_command(cmd)
    
    local packages = {}
    for line in result:gmatch("[^\r\n]+") do
        local pkg = line:match("^%s*(.-)%s*$")
        if pkg and #pkg > 0 then
            table.insert(packages, pkg)
        end
    end
    
    return packages
end

local function display_packages(packages)
    if #packages == 0 then
        print_colored(RED, "[!] No Roblox packages found!")
        return nil
    end
    
    print_colored(CYAN, "[?] Discovered packages:")
    for i, pkg in ipairs(packages) do
        print("    " .. i .. ") " .. pkg)
    end
    print()
    print("- Press " .. CYAN .. "<Enter>" .. RESET .. " or '" .. CYAN .. "all" .. RESET .. "' to select ALL packages (Default)")
    print("- Type '" .. YELLOW .. "none" .. RESET .. "' to skip, or enter indices (e.g. '1,3')")
    
    local choice = prompt("[?] Select: ")
    
    if choice == "" or choice:lower() == "all" then
        print_colored(YELLOW, "[+] Selected ALL packages.")
        return packages
    elseif choice:lower() == "none" then
        return {}
    else
        local selected = {}
        for idx in choice:gmatch("(%d+)") do
            local i = tonumber(idx)
            if i and packages[i] then
                table.insert(selected, packages[i])
            end
        end
        return selected
    end
end

-- ============================================
-- URL PARSING
-- ============================================
local function parse_private_server_url(url)
    local place_id = url:match("games/(%d+)") or url:match("placeId=(%d+)") or url:match("share%?code=") and url:match("(%d+)")
    local link_code = url:match("privateServerLinkCode=([%w_-]+)") or 
                      url:match("linkCode=([%w_-]+)") or
                      url:match("code=([%w_-]+)")
    
    return place_id, link_code
end

-- ============================================
-- COOKIE MANAGEMENT
-- ============================================
local function load_cookies()
    if not file_exists(COOKIES_FILE) then return {} end
    local content = read_file(COOKIES_FILE)
    if not content then return {} end
    
    local cookies = {}
    for line in content:gmatch("[^\r\n]+") do
        local cookie = line:match("^%s*(.-)%s*$")
        if cookie and #cookie > 0 and not cookie:match("^#") then
            table.insert(cookies, cookie)
        end
    end
    return cookies
end

local function save_cookies(cookies)
    local content = "# Roblox Cookies - One per line\n# Format: _|WARNING:-DO-NOT-SHARE-THIS...\n\n"
    for _, cookie in ipairs(cookies) do
        content = content .. cookie .. "\n"
    end
    return write_file(COOKIES_FILE, content)
end

local function add_cookie()
    print_banner()
    print_colored(CYAN, "=== Add Cookie ===\n")
    print("Paste your .ROBLOSECURITY cookie below.")
    print("It should start with: _|WARNING:-DO-NOT-SHARE-THIS...")
    print()
    
    local cookie = prompt("[?] Cookie: ")
    if cookie == "" then
        print_colored(RED, "[!] No cookie entered.")
        prompt("\nPress Enter to continue...")
        return
    end
    
    local cookies = load_cookies()
    table.insert(cookies, cookie)
    
    if save_cookies(cookies) then
        print_colored(YELLOW, "[+] Cookie added! Total: " .. #cookies)
    else
        print_colored(RED, "[!] Failed to save cookie!")
    end
    
    prompt("\nPress Enter to continue...")
end

local function list_cookies()
    print_banner()
    print_colored(CYAN, "=== Cookie List ===\n")
    
    local cookies = load_cookies()
    if #cookies == 0 then
        print_colored(YELLOW, "[i] No cookies saved.")
    else
        for i, cookie in ipairs(cookies) do
            local masked = cookie:sub(1, 30) .. "..." .. cookie:sub(-10)
            print("  " .. i .. ") " .. masked)
        end
        print()
        print_colored(WHITE, "Total: " .. #cookies .. " cookie(s)")
    end
    
    prompt("\nPress Enter to continue...")
end

local function remove_cookie()
    print_banner()
    print_colored(CYAN, "=== Remove Cookie ===\n")
    
    local cookies = load_cookies()
    if #cookies == 0 then
        print_colored(YELLOW, "[i] No cookies to remove.")
        prompt("\nPress Enter to continue...")
        return
    end
    
    for i, cookie in ipairs(cookies) do
        local masked = cookie:sub(1, 30) .. "..."
        print("  " .. i .. ") " .. masked)
    end
    print()
    
    local idx = tonumber(prompt("[?] Enter cookie number to remove: "))
    if idx and cookies[idx] then
        table.remove(cookies, idx)
        save_cookies(cookies)
        print_colored(YELLOW, "[+] Cookie removed!")
    else
        print_colored(RED, "[!] Invalid selection.")
    end
    
    prompt("\nPress Enter to continue...")
end

local function cookie_management()
    while true do
        print_banner()
        print_colored(CYAN, "=== Cookie Management ===\n")
        print("  " .. YELLOW .. "1)" .. RESET .. " Add Cookie")
        print("  " .. YELLOW .. "2)" .. RESET .. " List Cookies")
        print("  " .. YELLOW .. "3)" .. RESET .. " Remove Cookie")
        print("  " .. RED .. "4)" .. RESET .. " Back to Main Menu")
        print()
        
        local choice = prompt("[?] Choice: ")
        
        if choice == "1" then
            add_cookie()
        elseif choice == "2" then
            list_cookies()
        elseif choice == "3" then
            remove_cookie()
        elseif choice == "4" then
            break
        end
    end
end

-- ============================================
-- SCRIPT MANAGEMENT
-- ============================================
local function deploy_script_to_autoexec(package_name, script_content, script_name)
    -- Path to autoexecute folder for each Roblox package
    local autoexec_path = string.format("/data/data/%s/files/autoexecute/", package_name)
    local script_path = autoexec_path .. script_name
    
    -- Create directory and write script using root
    local cmd = string.format(
        'su -c "mkdir -p %s && echo \'%s\' > %s && chmod 644 %s"',
        autoexec_path,
        script_content:gsub("'", "'\"'\"'"),
        script_path,
        script_path
    )
    
    os.execute(cmd)
    return true
end

local function add_script(config)
    print_banner()
    print_colored(CYAN, "=== Add Script ===\n")
    
    local script_num = #config.scripts + 1
    local confirm = prompt_yn("[?] Add Script #" .. script_num .. "?", true)
    
    if not confirm then return config end
    
    print()
    print("[i] Paste your script below. Type 'END' on a new line to save.")
    print()
    
    local lines = {}
    while true do
        local line = io.read()
        if line == "END" then break end
        table.insert(lines, line)
    end
    
    local script_content = table.concat(lines, "\n")
    
    if #script_content == 0 then
        print_colored(RED, "[!] No script content entered.")
        prompt("\nPress Enter to continue...")
        return config
    end
    
    -- Save script to file
    mkdir(SCRIPTS_DIR)
    local script_file = SCRIPTS_DIR .. "script_" .. script_num .. ".lua"
    write_file(script_file, script_content)
    
    table.insert(config.scripts, script_file)
    
    print_colored(YELLOW, "[+] Deploying script_" .. script_num .. ".lua...")
    
    -- Deploy to all packages if inject_scripts is enabled
    if config.inject_scripts and #config.packages > 0 then
        for _, pkg in ipairs(config.packages) do
            deploy_script_to_autoexec(pkg, script_content, "script_" .. script_num .. ".lua")
        end
        print_colored(YELLOW, "[+] Finished deploying script_" .. script_num .. ".lua")
    end
    
    print_colored(YELLOW, "[+] Configuration saved.")
    
    -- Ask for another script
    print()
    local add_more = prompt_yn("[?] Add Script #" .. (script_num + 1) .. "?", false)
    if add_more then
        return add_script(config)
    end
    
    prompt("\nPress Enter to return to menu...")
    return config
end

-- ============================================
-- APP LAUNCH
-- ============================================
local function launch_app(package_name, place_id, link_code)
    local deep_link = string.format(
        "roblox://placeId=%s\\&linkCode=%s",
        place_id or "",
        link_code or ""
    )
    
    -- Use VIEW intent to let Android find the correct activity automatically
    -- This works better for cloned apps where activity names vary
    local cmd = string.format(
        'su -c "am start -a android.intent.action.VIEW -d \\"%s\\" -p %s --windowingMode 5"',
        deep_link,
        package_name
    )
    
    print_colored(YELLOW, "[>] Launching: " .. package_name)
    os.execute(cmd)
end

local function force_stop_app(package_name)
    local cmd = string.format('su -c "am force-stop %s"', package_name)
    os.execute(cmd)
end

local function is_app_running(package_name)
    local cmd = string.format('su -c "pidof %s"', package_name)
    local result = execute_command(cmd)
    return result and #result:match("^%s*(.-)%s*$") > 0
end

-- ============================================
-- CONFIGURATION MANAGEMENT
-- ============================================
local function load_config()
    if not file_exists(CONFIG_FILE) then return nil end
    local content = read_file(CONFIG_FILE)
    if not content then return nil end
    return json_decode(content)
end

local function save_config(config)
    local content = json_encode(config)
    return write_file(CONFIG_FILE, content)
end

local function reset_config()
    os.remove(CONFIG_FILE)
    print_colored(YELLOW, "[i] Config reset successfully!")
end

-- ============================================
-- SETUP WIZARD
-- ============================================
local function setup_configuration()
    print_banner()
    print_colored(CYAN, "=== Setup Configuration ===\n")
    
    local existing = load_config()
    if existing then
        print_colored(YELLOW, "[i] Reset detected. Removing old config...")
        reset_config()
    end
    
    local config = {
        packages = {},
        scripts = {},
        private_server_url = "",
        discord_webhook = "",
        mask_username = false,
        inject_scripts = false,
        delay_between_launch = 8,
        delay_before_rejoin = 60
    }
    
    -- Step 1: Package Selection
    print_colored(CYAN, "[1] Select package selection mode:")
    print("    1) Auto-detect (Recommended)")
    print("    2) Use package pattern (e.g., 'com.roblox.*')")
    print("    3) Enter manual package names")
    print()
    
    local mode = prompt("[?] Choice [1]: ")
    if mode == "" then mode = "1" end
    
    if mode == "1" then
        local detected = auto_detect_packages()
        config.packages = display_packages(detected) or {}
    elseif mode == "2" then
        print_colored(CYAN, "\n[?] Enter package pattern (e.g., com.roblox):")
        local pattern = prompt("Pattern: ")
        local cmd = "pm list packages 2>/dev/null | grep -i '" .. pattern .. "' | sed 's/package://g'"
        local result = execute_command(cmd)
        local packages = {}
        for line in result:gmatch("[^\r\n]+") do
            table.insert(packages, line:match("^%s*(.-)%s*$"))
        end
        config.packages = display_packages(packages) or {}
    else
        print_colored(CYAN, "\n[?] Enter package names (comma separated):")
        local input = prompt("Packages: ")
        for pkg in input:gmatch("[^,]+") do
            table.insert(config.packages, pkg:match("^%s*(.-)%s*$"))
        end
    end
    
    if #config.packages == 0 then
        print_colored(RED, "[!] No packages selected. Aborting setup.")
        prompt("\nPress Enter to continue...")
        return nil
    end
    
    print_colored(YELLOW, "[+] Selected " .. #config.packages .. " package(s)")
    
    -- Step 2: Same URL for all?
    print()
    config.use_same_url = prompt_yn("[?] Use same Private Server URL for all packages?", true)
    
    -- Step 3: Private Server URL
    print()
    print_colored(CYAN, "[?] Global Private Server URL (or Game URL):")
    print("    Example: https://www.roblox.com/share?code=63ee81e4d5...")
    config.private_server_url = prompt("[?] URL: ")
    
    local place_id, link_code = parse_private_server_url(config.private_server_url)
    if place_id then
        print_colored(YELLOW, "[i] Detected PlaceId: " .. place_id)
    end
    if link_code then
        print_colored(YELLOW, "[i] Detected LinkCode: " .. link_code:sub(1, 16) .. "...")
    end
    
    -- Step 4: Mask username
    print()
    config.mask_username = prompt_yn("[?] Mask username in status (e.g. naxxie)?", true)
    
    -- Step 5: Discord Webhook
    print()
    print_colored(CYAN, "[?] Discord Webhook URL (for critical alerts) [Enter to skip]:")
    config.discord_webhook = prompt("[?] Webhook: ")
    
    -- Step 6: Script Injection
    print()
    config.inject_scripts = prompt_yn("[?] Inject scripts to 'autoexecute' folder?", true)
    
    if config.inject_scripts then
        print_colored(WHITE, "[i] You can add multiple scripts.")
        config = add_script(config)
    end
    
    -- Save config
    if save_config(config) then
        print_colored(YELLOW, "\n[+] Configuration saved.")
    else
        print_colored(RED, "[!] Failed to save configuration!")
    end
    
    prompt("\nPress Enter to return to menu...")
    return config
end

-- ============================================
-- RUN SCRIPT (MAIN LOOP)
-- ============================================
local function run_script()
    print_banner()
    
    local config = load_config()
    if not config or #config.packages == 0 then
        print_colored(RED, "[!] No configuration found. Please run Setup first.")
        prompt("\nPress Enter to continue...")
        return
    end
    
    local place_id, link_code = parse_private_server_url(config.private_server_url)
    if not place_id then
        print_colored(RED, "[!] Invalid Private Server URL in config.")
        prompt("\nPress Enter to continue...")
        return
    end
    
    print_colored(CYAN, "=== Run Script ===\n")
    print_colored(WHITE, "Packages: " .. #config.packages)
    print_colored(WHITE, "PlaceId: " .. place_id)
    if link_code then
        print_colored(WHITE, "LinkCode: " .. link_code:sub(1, 8) .. "...")
    end
    print_colored(WHITE, "Scripts: " .. #config.scripts)
    print()
    
    -- Deploy scripts if enabled
    if config.inject_scripts and #config.scripts > 0 then
        print_colored(YELLOW, "[i] Deploying scripts to autoexecute folders...")
        for _, script_file in ipairs(config.scripts) do
            local content = read_file(script_file)
            if content then
                local script_name = script_file:match("([^/]+)$")
                for _, pkg in ipairs(config.packages) do
                    deploy_script_to_autoexec(pkg, content, script_name)
                end
                print_colored(YELLOW, "    [+] Deployed: " .. script_name)
            end
        end
    end
    
    -- Initial launch
    print()
    print_colored(YELLOW, "[i] Launching all apps...")
    for i, pkg in ipairs(config.packages) do
        launch_app(pkg, place_id, link_code)
        if i < #config.packages then
            print_colored(WHITE, "    Waiting " .. config.delay_between_launch .. "s...")
            sleep(config.delay_between_launch)
        end
    end
    
    print()
    print_colored(YELLOW, "[i] All apps launched! Starting monitoring loop...")
    print_colored(WHITE, "    Press Ctrl+C to stop")
    print()
    
    -- Send webhook notification
    if config.discord_webhook and config.discord_webhook ~= "" then
        send_discord_webhook(
            config.discord_webhook,
            "🚀 Rejoin Tool Started",
            "Monitoring " .. #config.packages .. " package(s)",
            65280  -- Green
        )
    end
    
    -- Monitoring loop with simple display
    local cycle = 0
    while true do
        cycle = cycle + 1
        sleep(config.delay_before_rejoin)
        
        -- Clear and redraw
        clear_screen()
        
        -- Banner
        print(CYAN .. "REJOIN TOOL v" .. VERSION .. RESET)
        print(CYAN .. "========================" .. RESET)
        print()
        print(WHITE .. "Cycle: " .. YELLOW .. "#" .. cycle .. RESET)
        print()
        
        -- Package status
        local any_crashed = false
        for i, pkg in ipairs(config.packages) do
            local display_name = pkg
            if config.mask_username then
                display_name = pkg:gsub("client", "cli***")
            end
            
            local is_running = is_app_running(pkg)
            local status_text, status_color
            
            if is_running then
                status_text = "Running"
                status_color = YELLOW
            else
                status_text = "Rejoining..."
                status_color = RED
                any_crashed = true
                
                if config.discord_webhook and config.discord_webhook ~= "" then
                    send_discord_webhook(
                        config.discord_webhook,
                        "App Crashed",
                        display_name .. " stopped. Rejoining...",
                        16711680
                    )
                end
                
                launch_app(pkg, place_id, link_code)
            end
            
            print(WHITE .. i .. ") " .. display_name)
            print("   " .. status_color .. status_text .. RESET)
        end
        
        print()
        print(WHITE .. "Stop: pkill -f rejoin" .. RESET)
        
        if any_crashed then
            sleep(2)
        end
    end
end

-- ============================================
-- MAIN MENU
-- ============================================
local function main_menu()
    while true do
        print_banner()
        print_colored(CYAN, "What would you like to do?\n")
        print("  " .. YELLOW .. "1)" .. RESET .. " Setup Configuration (First Run)")
        print("  " .. YELLOW .. "2)" .. RESET .. " Run Script (Launch apps + optimizations)")
        print("  " .. YELLOW .. "3)" .. RESET .. " Cookie Management")
        print("  " .. RED .. "4)" .. RESET .. " Exit")
        print()
        
        local choice = prompt("[?] Enter your choice [1-4]: ")
        
        if choice == "1" then
            setup_configuration()
        elseif choice == "2" then
            run_script()
        elseif choice == "3" then
            cookie_management()
        elseif choice == "4" then
            print_colored(YELLOW, "\n[i] Goodbye!")
            break
        else
            print_colored(RED, "[!] Invalid choice. Please try again.")
            sleep(1)
        end
    end
end

-- ============================================
-- ENTRY POINT
-- ============================================
if arg and arg[1] == "--reset" then
    reset_config()
    os.exit(0)
end

main_menu()
