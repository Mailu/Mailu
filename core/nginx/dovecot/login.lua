function script_init()
  return 0
end

function script_deinit()
end

local http_client = dovecot.http.client {
    timeout = 2000;
    max_attempts = 3;
}

-- on the other end we use urllib.parse.unquote()
function urlEncode(str)
    return str:gsub("[^%w_.-~]", function(c)
        return string.format("%%%02X", string.byte(c))
    end)
end

function auth_passdb_lookup(req)
  local auth_request = http_client:request {
    url = "http://{{ ADMIN_ADDRESS }}:8080/internal/auth/email";
  }
  auth_request:add_header('Auth-Port', req.local_port)
  local user = urlEncode(req.user)
  auth_request:add_header('Auth-User', user)
  if req.password ~= nil
  then
    local password = urlEncode(req.password)
    auth_request:add_header('Auth-Pass', password)
  end
  auth_request:add_header('Auth-Protocol', req.service)
  local client_ip = urlEncode(req.remote_ip)
  auth_request:add_header('Client-Ip', client_ip)
  auth_request:add_header('Client-Port', req.remote_port)
  auth_request:add_header('Auth-SSL', req.secured)
  auth_request:add_header('Auth-Method', req.mechanism)
  local auth_response = auth_request:submit()
  local resp_status = auth_response:status()

  if resp_status == 200
  then
    if auth_response:header('Auth-Status') == 'OK'
    then
      local server = auth_response:header('Auth-Server')
      local port = auth_response:header('Auth-Port')
      return dovecot.auth.PASSDB_RESULT_OK, "proxy=y host=" .. server .. " port=" .. port .. " nopassword=Y proxy_noauth=Y"
    else
      return dovecot.auth.PASSDB_RESULT_PASSWORD_MISMATCH, ""
    end
  else
    return dovecot.auth.PASSDB_RESULT_INTERNAL_FAILURE, ""
  end
end
