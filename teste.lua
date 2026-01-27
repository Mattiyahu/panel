--[[
    AUTO GET KEY - Script para autoexec do Delta
    Coloque este arquivo em: /sdcard/Delta/autoexec/
    
    O que faz:
    1. Monitora e tenta capturar o link/ticket da key
    2. Salva em /sdcard/delta_key.txt
    3. Copia para o clipboard
    
    O script Python pode então ler o arquivo e fazer o bypass automaticamente
]]

-- Configurações
local OUTPUT_FILE = "/sdcard/delta_key.txt"
local CHECK_INTERVAL = 1 -- segundos

-- Função para salvar em arquivo
local function saveToFile(content)
    local success, err = pcall(function()
        writefile(OUTPUT_FILE, content)
    end)
    if success then
        print("[AutoKey] Salvo em: " .. OUTPUT_FILE)
    end
end

-- Função para copiar para clipboard
local function copyToClipboard(content)
    local success, err = pcall(function()
        setclipboard(content)
    end)
    if success then
        print("[AutoKey] Copiado para clipboard!")
    end
end

-- Função para enviar para webhook (opcional)
local function sendToWebhook(content)
    local webhookUrl = "" -- Coloque sua URL de webhook aqui se quiser
    if webhookUrl ~= "" then
        pcall(function()
            local http = game:GetService("HttpService")
            http:PostAsync(webhookUrl, http:JSONEncode({content = content}))
        end)
    end
end

-- Método 1: Tentar pegar via getgenv() ou variáveis globais
local function tryGetFromGlobals()
    local possibleVars = {
        "KeyLink", "keylink", "key_link",
        "GetKeyLink", "getKeyLink",
        "DeltaKey", "deltaKey", "delta_key",
        "AuthLink", "authLink", "auth_link",
        "PlatoLink", "platoLink",
        "Ticket", "ticket",
        "KeyURL", "keyUrl", "key_url"
    }
    
    for _, varName in ipairs(possibleVars) do
        local success, value = pcall(function()
            return getgenv()[varName]
        end)
        if success and value and type(value) == "string" and value:find("platorelay") then
            return value
        end
        
        -- Tenta também em _G
        success, value = pcall(function()
            return _G[varName]
        end)
        if success and value and type(value) == "string" and value:find("platorelay") then
            return value
        end
    end
    
    return nil
end

-- Método 2: Hookar funções HTTP para interceptar requisições
local function hookHttpRequests()
    local oldRequest = nil
    local oldHttpGet = nil
    
    -- Hook request/http_request
    pcall(function()
        if request then
            oldRequest = request
            getgenv().request = function(options)
                if options and options.Url and options.Url:find("platorelay") then
                    print("[AutoKey] URL interceptada: " .. options.Url)
                    saveToFile(options.Url)
                    copyToClipboard(options.Url)
                end
                return oldRequest(options)
            end
        end
    end)
    
    -- Hook syn.request se disponível
    pcall(function()
        if syn and syn.request then
            local oldSynRequest = syn.request
            syn.request = function(options)
                if options and options.Url and options.Url:find("platorelay") then
                    print("[AutoKey] URL interceptada (syn): " .. options.Url)
                    saveToFile(options.Url)
                    copyToClipboard(options.Url)
                end
                return oldSynRequest(options)
            end
        end
    end)
    
    -- Hook game:HttpGet
    pcall(function()
        local mt = getrawmetatable(game)
        local oldNamecall = mt.__namecall
        setreadonly(mt, false)
        mt.__namecall = newcclosure(function(self, ...)
            local method = getnamecallmethod()
            local args = {...}
            
            if method == "HttpGet" or method == "HttpGetAsync" then
                local url = args[1]
                if url and type(url) == "string" and url:find("platorelay") then
                    print("[AutoKey] HttpGet interceptado: " .. url)
                    saveToFile(url)
                    copyToClipboard(url)
                end
            end
            
            return oldNamecall(self, ...)
        end)
        setreadonly(mt, true)
    end)
end

-- Método 3: Monitorar clipboard periodicamente
local function monitorClipboard()
    spawn(function()
        local lastClip = ""
        while true do
            pcall(function()
                local clip = getclipboard()
                if clip and clip ~= lastClip then
                    lastClip = clip
                    if clip:find("platorelay") or clip:find("platoboost") then
                        print("[AutoKey] Link encontrado no clipboard!")
                        saveToFile(clip)
                    end
                end
            end)
            wait(CHECK_INTERVAL)
        end
    end)
end

-- Método 4: Procurar em todas as variáveis do ambiente
local function scanEnvironment()
    spawn(function()
        while true do
            -- Escaneia getgenv()
            pcall(function()
                for key, value in pairs(getgenv()) do
                    if type(value) == "string" and value:find("platorelay") then
                        print("[AutoKey] Encontrado em getgenv()." .. tostring(key))
                        saveToFile(value)
                        copyToClipboard(value)
                        return
                    end
                end
            end)
            
            -- Escaneia _G
            pcall(function()
                for key, value in pairs(_G) do
                    if type(value) == "string" and value:find("platorelay") then
                        print("[AutoKey] Encontrado em _G." .. tostring(key))
                        saveToFile(value)
                        copyToClipboard(value)
                        return
                    end
                end
            end)
            
            wait(CHECK_INTERVAL)
        end
    end)
end

-- Método 5: Interceptar setclipboard
local function hookSetClipboard()
    pcall(function()
        if setclipboard then
            local oldSetClipboard = setclipboard
            getgenv().setclipboard = function(content)
                if content and type(content) == "string" then
                    if content:find("platorelay") or content:find("platoboost") then
                        print("[AutoKey] setclipboard interceptado!")
                        saveToFile(content)
                    end
                end
                return oldSetClipboard(content)
            end
        end
    end)
end

-- Método 6: Tentar acessar diretamente a função de key do Delta
local function tryDeltaInternal()
    pcall(function()
        -- Tenta acessar funções internas do Delta
        if Delta and Delta.GetKey then
            local key = Delta.GetKey()
            if key then
                print("[AutoKey] Key do Delta: " .. key)
                saveToFile(key)
                copyToClipboard(key)
            end
        end
        
        if getgenv().Delta then
            for k, v in pairs(getgenv().Delta) do
                print("[AutoKey] Delta." .. tostring(k) .. " = " .. tostring(v))
            end
        end
    end)
end

-- INICIALIZAÇÃO
print("========================================")
print("   AUTO GET KEY - Iniciado!")
print("   Monitorando link da key...")
print("========================================")

-- Executa todos os métodos
hookHttpRequests()
hookSetClipboard()
monitorClipboard()
scanEnvironment()
tryDeltaInternal()

-- Verifica imediatamente se já existe algo
local found = tryGetFromGlobals()
if found then
    print("[AutoKey] Link encontrado imediatamente!")
    saveToFile(found)
    copyToClipboard(found)
end

print("[AutoKey] Hooks instalados. Aguardando link...")
