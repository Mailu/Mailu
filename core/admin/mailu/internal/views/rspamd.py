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
    selectors = []
    if domain := models.Domain.query.get(domain_name):
        if key := domain.dkim_key:
            selectors.append(
                {
                    'domain'  : domain.name,
                    'key'     : key.decode('utf8'),
                    'selector': flask.current_app.config.get('DKIM_SELECTOR', 'dkim'),
                }
            )
    return flask.jsonify({'data': {'selectors': selectors}})

@internal.route("/rspamd/local_domains", methods=['GET'])
def rspamd_local_domains():
    return '\n'.join(domain[0] for domain in models.Domain.query.with_entities(models.Domain.name).all() + models.Alternative.query.with_entities(models.Alternative.name).all())
