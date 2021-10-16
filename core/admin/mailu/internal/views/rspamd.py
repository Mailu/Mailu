from mailu import models
from mailu.internal import internal

import flask

def vault_error(*messages, status=404):
    return flask.make_response(flask.jsonify({'errors':messages}), status)

# rspamd key format:
# {"selectors":[{"pubkey":"...","domain":"...","valid_start":TS,"valid_end":TS,"key":"...","selector":"...","bits":...,"alg":"..."}]}

# hashicorp vault answer format:
# {"request_id":"...","lease_id":"","renewable":false,"lease_duration":2764800,"data":{...see above...},"wrap_info":null,"warnings":null,"auth":null}

@internal.route("/rspamd/vault/v1/dkim/<domain_name>", methods=['GET'])
def rspamd_dkim_key(domain_name):
    domain = models.Domain.query.get(domain_name) or flask.abort(vault_error('unknown domain'))
    key = domain.dkim_key or flask.abort(vault_error('no dkim key', status=400))
    return flask.jsonify({
        'data': {
            'selectors': [
                {
                    'domain'  : domain.name,
                    'key'     : key.decode('utf8'),
                    'selector': flask.current_app.config.get('DKIM_SELECTOR', 'dkim'),
                }
            ]
        }
    })

