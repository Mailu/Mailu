from mailu import models
from mailu.internal import internal

import flask

db = models.db


def vault_error(*messages, status=404):
    return flask.make_response(flask.jsonify({'errors':messages}), status)

# rspamd key format:
# {"selectors":[{"pubkey":"...","domain":"...","valid_start":TS,"valid_end":TS,"key":"...","selector":"...","bits":...,"alg":"..."}]}

# hashicorp vault answer format:
# {"request_id":"...","lease_id":"","renewable":false,"lease_duration":2764800,"data":{...see above...},"wrap_info":null,"warnings":null,"auth":null}


@internal.route("/rspamd/vault/v1/dkim/<domain_name>", methods=['GET'])
def rspamd_dkim_key(domain_name):
    selectors = []
    if domain := db.session.get(models.Domain, domain_name):
        if key := domain.dkim_key:
            selectors.append(
                {
                    'domain': domain.name,
                    'key': key.decode('utf8'),
                    'selector': flask.current_app.config.get('DKIM_SELECTOR', 'dkim'),
                }
            )
    return flask.jsonify({'data': {'selectors': selectors}})


@internal.route("/rspamd/local_domains", methods=['GET'])
def rspamd_local_domains():
    domains = db.session.execute(db.select(models.Domain).with_only_columns(models.Domain.name)).all()
    alternatives = db.session.execute(db.select(models.Alternative).with_only_columns(models.Alternative.name)).all()

    return '\n'.join(domain[0] for domain in domains + alternatives)
