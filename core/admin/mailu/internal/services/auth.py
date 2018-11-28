from mailu import models, app
from mailu.internal.auth_provider import ldap

def authenticate_user(mail_address, password,protocol,ip):
    if ldap_is_configured():
        user = find_user_by_ldap(mail_address)
        if user:
            return __evaluate_user_status(user, password, protocol, ip)
    
    # use sql-auth as fallback
    user = find_user_by_sql(mail_address)
    return __evaluate_user_status(user, password, protocol, ip)

def find_user_by_sql(mail_address):
    return models.User.query.get(mail_address)

def find_user_by_ldap(mail_address):
    return ldap.get_user_by_mail(mail_address)

def ldap_is_configured():
    return bool(app.config.get('LDAP_SERVER_URI'))

def __evaluate_user_status(user, password, protocol, ip):
    status = False
    if user:
        for token in user.tokens:
            if (token.check_password(password) and
                (not token.ip or token.ip == ip)):
                    status = True
        if user.check_password(password):
            status = True
        if status:
            if protocol == "imap" and not user.enable_imap:
                status = False
            elif protocol == "pop3" and not user.enable_pop:
                status = False
        
        if status:
            if not user.enabled:
                status = False
    return status
