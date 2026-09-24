function script_init()
  return 0
end

function script_deinit()
end

local http_client = dovecot.http.client {
    request_timeout = "2s";
    request_max_attempts = 3;
}

-- on the other end we use urllib.parse.unquote()
function urlEncode(str)
    return str:gsub("[^%w_.-~]", function(c)
        return string.format("%%%02X", string.byte(c))
    end)
end

function addHeader(auth_request, name, value)
  auth_request:add_header(name, value or "")
end

function auth_passdb_lookup(req)
  local auth_request = http_client:request {
    url = "http://{{ ADMIN_ADDRESS }}:8080/internal/auth/email";
  }
  addHeader(auth_request, 'Auth-Port', req.local_port)
  local user = urlEncode(req.user)
  auth_request:add_header('Auth-User', user)
  addHeader(auth_request, 'Auth-Pass', req.password and urlEncode(req.password))
  -- Every header is sent even when its field is unset: the endpoint indexes
  -- rather than gets them, so a missing one answers 400. An auth-master PASS
  -- lookup (the lmtp proxy) has none of these fields.
  addHeader(auth_request, 'Auth-Protocol', req.protocol)
  addHeader(auth_request, 'Client-Ip', req.remote_ip and urlEncode(req.remote_ip))
  addHeader(auth_request, 'Client-Port', req.remote_port)
  addHeader(auth_request, 'Auth-SSL', req.secured)
  addHeader(auth_request, 'Auth-Method', req.mechanism)
  local auth_response = auth_request:submit()
  local resp_status = auth_response:status()

  if resp_status == 200
  then
    if auth_response:header('Auth-Status') == 'OK'
    then
      local server = auth_response:header('Auth-Server')
      local port = auth_response:header('Auth-Port')
      local reply = {
        proxy = "y",
        host = server,
        port = port,
        nopassword = "Y",
        proxy_noauth = "Y",
      }
      if req.protocol == "imap" then
        reply.proxy_mech = "PLAIN"
      end
      return dovecot.auth.PASSDB_RESULT_OK, reply
    else
      return dovecot.auth.PASSDB_RESULT_PASSWORD_MISMATCH, ""
    end
  else
    return dovecot.auth.PASSDB_RESULT_INTERNAL_FAILURE, ""
  end
end
