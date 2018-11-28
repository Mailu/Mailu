from mailu import app
from mailu.models import User
import ldap
import logging

logger = logging.getLogger('ldap_auth')

def init_ldap_connection():
    return ldap.initialize(app.config.get('LDAP_SERVER_URI'))

ldap_server = init_ldap_connection()
ldap_bind_user = app.config.get('LDAP_BIND_DN')
ldap_bind_password = app.config.get('LDAP_BIND_PASSWORD')

ldap_server.bind_s(ldap_bind_user,ldap_bind_password)

ldap_base = app.config.get('LDAP_BASE')
ldap_mail_attribute = app.config.get('LDAP_MAIL_ATTRIBUTE')
ldap_search_filter = app.config.get('LDAP_SEARCH_FILTER')

def get_user_by_mail(mail_address):
    mail_filter = '({}={})'.format(ldap_mail_attribute,mail_address)
    search_query = "(&{}{})".format(ldap_search_filter,mail_filter)
    search_result = ldap_server.search_s(ldap_base,ldap.SCOPE_SUBTREE,search_query)

    # Search-result must not contain multiple results, otherwise mail-address is not unique
    if len(search_result) > 1:
        logger.error('Found {} results while searching for user with mail-address {}. A mail-address must be unique! This login-try will be ignored and canceled.'.format(len(search_result),mail_address))
        return None
    
    if len(search_result) == 1:
        search_result_tuple = search_result[0]
        return map_ldap_user_to_model_user(search_result_tuple[0])
    else:
        return None

def map_ldap_user_to_model_user(ldap_user_dn):
    if not ldap_user_dn:
        return None

    def check_password_by_ldap(password):
        ldap_server = init_ldap_connection()
        try:
            ldap_server.bind_s(ldap_user_dn,password)
        except ldap.INVALID_CREDENTIALS:
            return False

        return True

    temp_user = User()
    temp_user.enable_imap = True
    temp_user.enable_pop = True
    temp_user.enabled = True
    temp_user.check_password = check_password_by_ldap
    temp_user.tokens = []
    return temp_user
