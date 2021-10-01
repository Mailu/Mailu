from mailu import models, utils
from mailu.internal import internal
from flask import current_app as app

import flask
import idna
import re
import srslib

@internal.route("/postfix/dane/<domain_name>")
def postfix_dane_map(domain_name):
    return flask.jsonify('dane-only') if utils.has_dane_record(domain_name) else flask.abort(404)

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
    _, domain_name = models.Email.resolve_domain(email)
    relay = models.Relay.query.get(domain_name) or flask.abort(404)
    target = relay.smtp.lower()
    port = None
    use_lmtp = False
    use_mx = False
    # strip prefixes mx: and lmtp:
    if target.startswith('mx:'):
        target = target[3:]
        use_mx = True
    elif target.startswith('lmtp:'):
        target = target[5:]
        use_lmtp = True
    # split host:port or [host]:port
    if target.startswith('['):
        if use_mx or ']' not in target:
            # invalid target (mx: and [] or missing ])
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
    # default for empty host part is mx:domain
    if not host:
        if not use_lmtp:
            host = relay.name.lower()
            use_mx = True
        else:
            # lmtp: needs a host part
            flask.abort(400)
    # detect ipv6 address or encode host
    if ':' in host:
        host = f'ipv6:{host}'
    else:
        try:
            host = idna.encode(host).decode('ascii')
        except idna.IDNAError:
            # invalid host (fqdn not encodable)
            flask.abort(400)
    # validate port
    if port is not None:
        try:
            port = int(port, 10)
        except ValueError:
            # invalid port (should be numeric)
            flask.abort(400)
    # create transport
    transport = 'lmtp' if use_lmtp else 'smtp'
    # use [] when not using MX lookups or host is an ipv6 address
    if host.startswith('ipv6:') or (not use_lmtp and not use_mx):
        host = f'[{host}]'
    # create port suffix
    port = '' if port is None else f':{port}'
    return flask.jsonify(f'{transport}:{host}{port}')


@internal.route("/postfix/recipient/map/<path:recipient>")
def postfix_recipient_map(recipient):
    """ Rewrite the envelope recipient if it is a valid SRS address.

    This is meant for bounces to go back to the original sender.
    """
    srs = srslib.SRS(flask.current_app.srs_key)
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
    srs = srslib.SRS(flask.current_app.srs_key)
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
    wildcard_senders = [s for s in flask.current_app.config.get('WILDCARD_SENDERS', '').lower().replace(' ', '').split(',') if s]
    localpart, domain_name = models.Email.resolve_domain(sender)
    if localpart is None:
        return flask.jsonify(",".join(wildcard_senders)) if wildcard_senders else flask.abort(404)
    destination = models.Email.resolve_destination(localpart, domain_name, True)
    destination = [*destination, *wildcard_senders] if destination else [*wildcard_senders]
    return flask.jsonify(",".join(destination)) if destination else flask.abort(404)

@internal.route("/postfix/sender/rate/<path:sender>")
def postfix_sender_rate(sender):
    """ Rate limit outbound emails per sender login
    """
    user = models.User.get(sender) or flask.abort(404)
    return flask.abort(404) if user.sender_limiter.hit() else flask.jsonify("450 4.2.1 You are sending too many emails too fast.")

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
