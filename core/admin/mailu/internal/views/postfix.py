from mailu import models, utils
from mailu.internal import internal
from flask import current_app as app

import flask
import re


@internal.route("/postfix/domain/<domain_name>")
def postfix_mailbox_domain(domain_name):
    if re.match("^\[.*\]$", domain_name):
        return flask.abort(404)
    domain = models.Domain.query.get(domain_name) or \
             models.Alternative.query.get(domain_name) or \
             flask.abort(404)
    return flask.jsonify(domain.name)


@internal.route("/postfix/mailbox/<path:email>")
def postfix_mailbox_map(email):
    user = models.User.query.get(email) or flask.abort(404)
    return flask.jsonify(user.email)


@internal.route("/postfix/alias/<path:alias>")
def postfix_alias_map(alias):
    localpart, domain_name = models.Email.resolve_domain(alias)
    if localpart is None:
        return flask.jsonify(domain_name)
    destination = models.Email.resolve_destination(localpart, domain_name)
    return flask.jsonify(",".join(destination)) if destination else flask.abort(404)


@internal.route("/postfix/transport/<path:email>")
def postfix_transport(email):
    if email == '*' or re.match("(^|.*@)\[.*\]$", email):
        return flask.abort(404)
    localpart, domain_name = models.Email.resolve_domain(email)
    relay = models.Relay.query.get(domain_name) or flask.abort(404)
    return flask.jsonify("smtp:[{}]".format(relay.smtp))


@internal.route("/postfix/sender/login/<path:sender>")
def postfix_sender_login(sender):
    localpart, domain_name = models.Email.resolve_domain(sender)
    if localpart is None:
        return flask.abort(404)
    destination = models.Email.resolve_destination(localpart, domain_name, True)
    return flask.jsonify(",".join(destination)) if destination else flask.abort(404)


@internal.route("/postfix/sender/access/<path:sender>")
def postfix_sender_access(sender):
    """ Simply reject any sender that pretends to be from a local domain
    """
    if not is_void_address(sender):
        localpart, domain_name = models.Email.resolve_domain(sender)
        return flask.jsonify("REJECT") if models.Domain.query.get(domain_name) else flask.abort(404)
    else:
        return flask.abort(404)


@internal.route("/postfix/sender/rate/<path:sender>")
def postfix_sender_rate(sender):
    """ Rate limit outbound emails per sender login
    """
    user = models.User.get(sender) or flask.abort(404)
    return flask.abort(404) if user.sender_limiter.hit() else flask.jsonify("REJECT")


def is_void_address(email):
    '''True if the email is void (null) email address.
    '''
    if email.startswith('<') and email.endswith('>'):
        email = email[1:-1]
    # Some MTAs use things like '<MAILER-DAEMON>' instead of '<>'; so let's
    # consider void any such thing.
    return '@' not in email
