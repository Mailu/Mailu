json = require('json')

function script_init()
    return 0
end

function script_deinit()
end

local http_client = dovecot.http.client {
    timeout = 2000;
    max_attempts = 3;
}

function urlEncode(str)
    return str:gsub("[^%w_.-~]", function(c)
        return string.format("%%%02X", string.byte(c))
    end)
end

function setRequestHeadersFromDovecotRequest(auth_request, req)
    auth_request:add_header('Auth-Port', req.local_port)
    local user = urlEncode(req.user)
    auth_request:add_header('Auth-User', user)
    if req.password ~= nil
    then
        local password = urlEncode(req.password)
        auth_request:add_header('Auth-Pass', password)
    end
    if req.service ~= nil
    then
        auth_request:add_header('Auth-Protocol', req.service)
    end

    if req.remote_ip ~= nil
    then
        local client_ip = urlEncode(req.remote_ip)
        auth_request:add_header('Client-Ip', client_ip)
    end
    if req.remote_port ~= nil
    then
        auth_request:add_header('Client-Port', req.remote_port)
    end

    if req.secured ~= nil
    then
        auth_request:add_header('Auth-SSL', req.secured)
    end
    if req.mechanism ~= nil
    then
        auth_request:add_header('Auth-Method', req.mechanism)
    end
end

function formatJsonToKeyValueString(json_str)
    local data = json.decode(json_str)
    local result = {}

    for key, value in pairs(data) do
        local formatted_value
        if value == nil then
            formatted_value = ""
        else
            formatted_value = tostring(value)
        end
        table.insert(result, key .. "=" .. formatted_value)
    end

    return table.concat(result, " ")
end

function auth_passdb_lookup(req)
    local auth_request = http_client:request {
        url = "http://{{ ADMIN_ADDRESS }}:8080/internal/dovecot/passdb/" .. urlEncode(req.user);
    }
    setRequestHeadersFromDovecotRequest(auth_request, req)
    local auth_response = auth_request:submit()
    local resp_status = auth_response:status()

    if resp_status == 200
    then
        return dovecot.auth.PASSDB_RESULT_OK, formatJsonToKeyValueString(auth_response:payload())
    else
        return dovecot.auth.PASSDB_RESULT_USER_UNKNOWN, ""
    end
end

function auth_userdb_lookup(req)
    local auth_request = http_client:request {
        url = "http://{{ ADMIN_ADDRESS }}:8080/internal/dovecot/userdb/" .. urlEncode(req.user);
    }
    setRequestHeadersFromDovecotRequest(auth_request, req)
    local auth_response = auth_request:submit()
    local resp_status = auth_response:status()

    if resp_status == 200
    then
        local json_body = auth_response:payload()
        local result_str = formatJsonToKeyValueString(json_body)

        return dovecot.auth.USERDB_RESULT_OK, result_str
    else
        return dovecot.auth.USERDB_RESULT_USER_UNKNOWN, ""
    end
end

function auth_userdb_iterate()
    local auth_request = http_client:request {
        url = "http://{{ ADMIN_ADDRESS }}:8080/internal/dovecot/userdb/";
    }
    local auth_response = auth_request:submit()

    return json.decode(auth_response:payload())
end
