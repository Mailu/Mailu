"""OIDC Client"""

from time import time
from typing import Optional
import flask

# [OIDC] Import the OIDC related modules
from oic.oic import Client
from oic.exception import PyoidcError
from oic.extension.client import Client as ExtensionClient
from oic.utils.authn.client import CLIENT_AUTHN_METHOD
from oic.utils.settings import OicClientSettings
from oic import rndstr
from oic.exception import MessageException, NotForMe
from oic.oauth2.message import (
    ROPCAccessTokenRequest,
    AccessTokenResponse,
    ErrorResponse,
)
from oic.oic.message import (
    AuthorizationResponse,
    RegistrationResponse,
    EndSessionRequest,
    BackChannelLogoutRequest,
    OpenIDSchema,
    UserInfoErrorResponse,
)
from oic.oauth2.grant import Token

# [OIDC] Client class
class OicClient:
    """OpenID Connect Client"""

    ready: bool = False
    app: Optional[flask.Flask] = None
    client: Optional[Client] = None
    extension_client: Optional[ExtensionClient] = None
    registration_response: Optional[RegistrationResponse] = None
    enable_change_password_redirect: bool = True
    change_password_url: Optional[str] = None
    redirect_url: Optional[str] = None

    def receive_provider_info(self):
        self.app.logger.info("[OIDC] Getting provider config..")
        try:
            self.client.provider_config(self.app.config["OIDC_PROVIDER_INFO_URL"])
            self.extension_client.provider_config(self.app.config["OIDC_PROVIDER_INFO_URL"])

            self.change_password_url = self.app.config["OIDC_CHANGE_PASSWORD_REDIRECT_URL"] or (
            self.client.issuer + "/.well-known/change-password"
            )
            self.redirect_url = self.app.config["OIDC_REDIRECT_URL"] or (
                "https://" + self.app.config["HOSTNAME"]
            )

            client_reg = RegistrationResponse(
                client_id=self.app.config["OIDC_CLIENT_ID"],
                client_secret=self.app.config["OIDC_CLIENT_SECRET"],
                redirect_uris=[f"{self.redirect_url}/sso/login"],
            )
            self.client.store_registration_info(client_reg)
            self.extension_client.store_registration_info(client_reg)

            self.ready = True
        except Exception as e:
            self.app.logger.warning(f"[OIDC] Error getting provider config: {e}")
            self.app.logger.warning("[OIDC] Retrying with the next request..")
        return self.ready

    def init_app(self, app: flask.Flask):
        """Initialize OIDC client"""

        self.app = app

        settings = OicClientSettings(verify_ssl=app.config["OIDC_VERIFY_SSL"])

        self.enable_change_password_redirect = (
            app.config["OIDC_CHANGE_PASSWORD_REDIRECT_ENABLED"] or False
        )

        self.client = Client(client_authn_method=CLIENT_AUTHN_METHOD, settings=settings)
        self.extension_client = ExtensionClient(
            client_authn_method=CLIENT_AUTHN_METHOD, settings=settings
        )

    def get_redirect_url(self) -> Optional[str]:
        """Get the redirect URL"""
        if not self.is_enabled():
            return None
        
        if not self.ready and self.receive_provider_info() == False:
            return None

        flask.session["state"] = rndstr()
        flask.session["nonce"] = rndstr()

        args = {
            "client_id": self.client.client_id,
            "response_type": ["code"],
            "scope": ["openid", "email"],
            "nonce": flask.session["nonce"],
            "redirect_uri": self.redirect_url + "/sso/login",
            "state": flask.session["state"],
        }

        auth_req = self.client.construct_AuthorizationRequest(request_args=args)
        login_url = auth_req.request(self.client.authorization_endpoint)
        return login_url

    def _get_authorization_code(self, query: str) -> Optional[AuthorizationResponse]:
        """
        Get the authorization response and check if it is valid

        :param query: The query string
        :return: The authorization code if valid, None otherwise
        """

        auth_response = self.client.parse_response(
            AuthorizationResponse, info=query, sformat="urlencoded"
        )

        if not isinstance(auth_response, AuthorizationResponse):
            self.app.logger.debug(f"[OIDC] Error response in authorization: {auth_response}")
            raise PyoidcError("Error response in authorization")

        if "state" not in flask.session:
            self.app.logger.warning("[OIDC] No state in session")
            raise PyoidcError("No state in session")

        if flask.session["state"] != auth_response["state"]:
            self.app.logger.warning(
                f"[OIDC] State mismatch: expected {flask.session['state']}, got {auth_response['state']}"
            )
            raise PyoidcError("State mismatch")

        return auth_response["code"]

    def _get_id_and_access_tokens(self, auth_response_code: str):
        """
        Get the id and access tokens

        :param auth_response_code: The authorization response code
        :return: The token response if valid, None otherwise
        """

        token_response = self.client.do_access_token_request(
            state=flask.session["state"],
            request_args={"code": auth_response_code},
            authn_method="client_secret_basic",
        )

        if not isinstance(token_response, AccessTokenResponse):
            self.app.logger.warning(
                f"[OIDC] No access token or invalid response: {token_response}"
            )
            raise PyoidcError("No access token or invalid response")

        if "id_token" not in token_response:
            self.app.logger.warning("[OIDC] No id token in response")
            raise PyoidcError("No id token in response")

        if token_response["id_token"]["nonce"] != flask.session["nonce"]:
            self.app.logger.warning("[OIDC] Nonce mismatch")
            raise PyoidcError("Nonce mismatch")

        if "access_token" not in token_response:
            self.app.logger.warning("[OIDC] No access token or invalid response")
            raise PyoidcError("No access token or invalid response")

        return token_response

    def exchange_code(
        self, query: str
    ) -> tuple[str, str, str, AccessTokenResponse] | tuple[None, None, None, None]:
        """Exchange the code for the token"""

        if not self.ready and self.receive_provider_info() == False:
            return None, None, None, None

        auth_response_code = self._get_authorization_code(query)
        if not auth_response_code:
            raise PyoidcError("Error response in authorization")

        token_response = self._get_id_and_access_tokens(auth_response_code)
        if not token_response:
            raise PyoidcError("Error response in token")

        user_info_response = self.get_user_info(token_response)
        if not isinstance(user_info_response, OpenIDSchema):
            self.app.logger.debug("[OIDC] Error response in user info")
            raise PyoidcError("Error response in user info")

        return (
            user_info_response["email"],
            user_info_response["sub"],
            token_response["id_token"],
            token_response,
        )

    def get_user_info(
        self, token: AccessTokenResponse
    ) -> OpenIDSchema | UserInfoErrorResponse | ErrorResponse:
        """Get user info from the token"""
        return self.client.do_user_info_request(token=token["access_token"])

    def check_validity(
        self, token: AccessTokenResponse
    ) -> Optional[AccessTokenResponse]:
        """Check if the token is still valid"""

        # Assume the token is valid if it has an expiration time and it has not expired
        if "exp" in token["id_token"] and token["id_token"]["exp"] > time():
            return token
        return self.refresh_token(token)

    def refresh_token(
        self, token: AccessTokenResponse
    ) -> Optional[AccessTokenResponse]:
        """Refresh the token"""
        try:
            args = {"refresh_token": token["refresh_token"]}
            response = self.client.do_access_token_refresh(
                request_args=args, token=Token(token)
            )
            if isinstance(response, AccessTokenResponse):
                return response

        except Exception as e:
            flask.current_app.logger.error(f"Error refreshing token: {e}")
        return None

    def backchannel_logout(self, body):
        """
        Backchannel logout. See https://openid.net/specs/openid-connect-backchannel-1_0.html
        """

        # TODO: Finish backchannel logout implementation
        req = BackChannelLogoutRequest().from_dict(body)

        kwargs = {
            "aud": self.client.client_id,
            "iss": self.client.issuer,
            "keyjar": self.client.keyjar,
        }

        try:
            req.verify(**kwargs)
        except (MessageException, ValueError, NotForMe) as err:
            self.app.logger.error(err)
            return None

        sub = req["logout_token"]["sub"]

        if sub is not None and sub != "":
            return sub

        return True

    def is_enabled(self):
        """Check if OIDC is enabled"""

        if self.app is not None and self.app.config["OIDC_ENABLED"]:
            return True
        return False

    def change_password(self) -> Optional[str]:
        """Get the URL for changing password if the redirect is enabled"""

        if self.enable_change_password_redirect:
            return self.change_password_url
        return None
