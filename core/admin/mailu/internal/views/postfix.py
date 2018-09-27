from mailu import db, models
from mailu.internal import internal

import flask


@internal.route("/postfix/domain/<domain_name>")
def postfix_mailbox_domain(domain_name):
    domain = models.Domain.query.get(domain_name) or flask.abort(404)
    return flask.jsonify(domain.name)


@internal.route("/postfix/mailbox/<email>")
def postfix_mailbox_map(email):
    user = models.User.query.get(email) or flask.abort(404)
    return flask.jsonify(user.email)


@internal.route("/postfix/alias/<alias>")
def postfix_alias_map(alias):
    localpart, domain = alias.split('@', 1) if '@' in alias else (None, alias)
    alternative = models.Alternative.query.get(domain)
    if alternative:
        domain = alternative.domain_name
    email = '{}@{}'.format(localpart, domain)
    if localpart is None:
        return flask.jsonify(domain)
    else:
        alias_obj = models.Alias.resolve(localpart, domain)
        if alias_obj:
            return flask.jsonify(",".join(alias_obj.destination))
        user_obj = models.User.query.get(email)
        if user_obj:
            return flask.jsonify(user_obj.destination)
        return flask.abort(404)


@internal.route("/postfix/transport/<email>")
def postfix_transport(email):
    localpart, domain = email.split('@', 1) if '@' in email else (None, email)
    relay = models.Relay.query.get(domain) or flask.abort(404)
    return flask.jsonify("smtp:[{}]".format(relay.smtp))
