from mailu import models
from mailu.internal import internal

import flask
import idna

def vault_error(*messages, status=404):
    return flask.make_response(flask.jsonify({'errors':messages}), status)

# rspamd key format:
# {"selectors":[{"pubkey":"...","domain":"...","valid_start":TS,"valid_end":TS,"key":"...","selector":"...","bits":...,"alg":"..."}]}

# hashicorp vault answer format:
# {"request_id":"...","lease_id":"","renewable":false,"lease_duration":2764800,"data":{...see above...},"wrap_info":null,"warnings":null,"auth":null}

@internal.route("/rspamd/vault/v1/dkim/<domain_name>", methods=['GET'])
def rspamd_dkim_key(domain_name):
    selectors = []
    domain = models.db.session.get(models.Domain, domain_name)
    alternative = models.db.session.get(models.Alternative, domain_name)
    signing_domains = [item for item in (domain, alternative.domain if alternative else None) if item]
    seen = set()
    for signing_domain in signing_domains:
        for key in signing_domain.dkim_keys:
            if key.active and key.selector not in seen:
                seen.add(key.selector)
                selectors.append({
                    'domain': idna.encode(domain_name.lower()).decode('ascii'),
                    'key': key.private_key.decode('utf8'),
                    'selector': key.selector,
                    'alg': key.algorithm,
                })
    return flask.jsonify({'data': {'selectors': selectors}})

@internal.route("/rspamd/local_domains", methods=['GET'])
def rspamd_local_domains():
    return '\n'.join(domain[0] for domain in models.Domain.query.with_entities(models.Domain.name).all() + models.Alternative.query.with_entities(models.Alternative.name).all())
