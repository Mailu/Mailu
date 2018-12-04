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
    localpart, domain_name = models.Email.resolve_domain(alias)
    if localpart is None:
        return flask.jsonify(domain_name)
    destination = models.Email.resolve_destination(localpart, domain_name)
    return flask.jsonify(",".join(destination)) if destination else flask.abort(404)


@internal.route("/postfix/transport/<email>")
def postfix_transport(email):
    if email == '*':
        return flask.abort(404)
    localpart, domain_name = models.Email.resolve_domain(email)
    relay = models.Relay.query.get(domain_name) or flask.abort(404)
    return flask.jsonify("smtp:[{}]".format(relay.smtp))


@internal.route("/postfix/sender/login/<sender>")
def postfix_sender_login(sender):
    localpart, domain_name = models.Email.resolve_domain(sender)
    if localpart is None:
        return flask.abort(404)
    destination = models.Email.resolve_destination(localpart, domain_name, True)
    return flask.jsonify(",".join(destination)) if destination else flask.abort(404)


@internal.route("/postfix/sender/access/<sender>")
def postfix_sender_access(sender):
    """ Simply reject any sender that pretends to be from a local domain
    """
    localpart, domain_name = models.Email.resolve_domain(sender)
    return flask.jsonify("REJECT") if models.Domain.query.get(domain_name) else flask.abort(404)
