from mailu import models
from mailu.internal import internal

import flask
import idna
import re
import srslib


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
    target = relay.smtp.lower()
    port = None
    if use_mx := target.startswith('mx:'):
        target = target[3:]
    if target.startswith('['):
        if use_mx or ']' not in target:
            # invalid target (mx: and [])
            flask.abort(400)
        host, rest = target[1:].split(']', 1)
        if rest.startswith(':'):
            port = rest[1:]
        elif rest:
            # invalid target (rest should be :port)
            flask.abort(400)
    else:
        if ':' in target:
            host, port = target.rsplit(':', 1)
        else:
            host = target
    if not host:
        host = relay.name.lower()
        use_mx = True
    if ':' in host:
        host = f'ipv6:{host}'
    else:
        try:
            host = idna.encode(host).decode('ascii')
        except idna.IDNAError:
            # invalid target (fqdn not encodable)
            flask.abort(400)
    if port is not None:
        try:
            port = int(port, 10)
            if port == 25:
                port = None
        except ValueError:
            # invalid target (port should be numeric)
            flask.abort(400)
    if not use_mx:
        host = f'[{host}]'
    port = '' if port is None else f':{port}'
    return flask.jsonify(f'smtp:{host}{port}')


@internal.route("/postfix/recipient/map/<path:recipient>")
def postfix_recipient_map(recipient):
    """ Rewrite the envelope recipient if it is a valid SRS address.

    This is meant for bounces to go back to the original sender.
    """
    srs = srslib.SRS(flask.current_app.config["SECRET_KEY"])
    if srslib.SRS.is_srs_address(recipient):
        try:
            return flask.jsonify(srs.reverse(recipient))
        except srslib.Error as error:
            return flask.abort(404)
    return flask.abort(404)


@internal.route("/postfix/sender/map/<path:sender>")
def postfix_sender_map(sender):
    """ Rewrite the envelope sender in case the mail was not emitted by us.

    This is for bounces to come back the reverse path properly.
    """
    srs = srslib.SRS(flask.current_app.config["SECRET_KEY"])
    domain = flask.current_app.config["DOMAIN"]
    try:
        localpart, domain_name = models.Email.resolve_domain(sender)
    except Exception as error:
        return flask.abort(404)
    if models.Domain.query.get(domain_name):
        return flask.abort(404)
    return flask.jsonify(srs.forward(sender, domain))


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


def is_void_address(email):
    '''True if the email is void (null) email address.
    '''
    if email.startswith('<') and email.endswith('>'):
        email = email[1:-1]
    # Some MTAs use things like '<MAILER-DAEMON>' instead of '<>'; so let's
    # consider void any such thing.
    return '@' not in email
