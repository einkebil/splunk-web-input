"""
This class wraps various web-clients so that different ones can be used.
"""
import urllib2
import httplib2
from httplib2 import socks
import socket
import mechanize

class WebClientException(Exception):
    def __init__(self, message=None, cause=None):
        if message is not None and cause is not None:
            super(WebClientException, self).__init__(message + u', caused by ' + repr(cause))
        self.cause = cause

class FormAuthenticationNotSupported(WebClientException):
    pass

class FormAuthenticationFailed(WebClientException):
    pass

class RequestTimeout(WebClientException):
    pass

class ConnectionFailure(WebClientException):
    pass

class LoginFormNotFound(FormAuthenticationFailed):
    pass

DEFAULT_USER_AGENT = 'Splunk Website Input (+https://splunkbase.splunk.com/app/1818/)'

class WebClient(object):
    """
    This is the base-class.
    """

    def __init__(self, timeout=30, user_agent=DEFAULT_USER_AGENT, logger=None):

        # These are for storing the options for performing the request
        self.timeout = timeout
        self.user_agent = user_agent
        self.headers = {}
        self.username = None
        self.password = None

        self.logger = logger

        # The proxy server information
        self.proxy_type = None
        self.proxy_server = None
        self.proxy_port = None
        self.proxy_user = None
        self.proxy_pass = None

        # The following will be populated by the request
        self.response_code = None
        self.content = None

    def add_header(self, header_name, header_value):
        self.headers[header_name] = header_value

    def setProxy(self, proxy_type, proxy_server, proxy_port, proxy_user, proxy_pass):
        self.proxy_type = proxy_type
        self.proxy_server = proxy_server
        self.proxy_port = proxy_port
        self.proxy_user = proxy_user
        self.proxy_pass = proxy_pass

    def setCredentials(self, username, password):
        self.username = username
        self.password = password

    def doFormLogin(self, login_url, username_field=None, password_field=None):
        raise FormAuthenticationNotSupported()

    # The following need to be implemented by the inheriting classes
    def get_url(self, url, operation='GET'):
        pass

    def get_response_headers(self):
        pass

class Http2LibClient(WebClient):
    """
    A web-client based on http2lib.
    """

    def __init__(self, timeout=30, user_agent=DEFAULT_USER_AGENT, logger=None):
        super(Http2LibClient, self).__init__(timeout, user_agent, logger)

        # This is a reference to the HTTP client
        self.http = None
        self.response = None

    def resolve_proxy_type(self, proxy_type):

        # Make sure the proxy string is not none
        if proxy_type is None:
            return None

        # Prepare the string so that the proxy type can be matched more reliably
        t = proxy_type.strip().lower()

        if t == "socks4":
            return socks.PROXY_TYPE_SOCKS4
        elif t == "socks5":
            return socks.PROXY_TYPE_SOCKS5
        elif t == "http":
            return socks.PROXY_TYPE_HTTP
        elif t == "":
            return None
        else:
            if self.logger is not None:
                self.logger.warn("Proxy type is not recognized: %s", proxy_type)
            return None

    def get_http_client(self):

        if self.http is not None:
            return self.http

        else:
            # Determine which type of proxy is to be used (if any)
            resolved_proxy_type = self.resolve_proxy_type(self.proxy_type)
                
            # Setup the proxy info if so configured
            if resolved_proxy_type is not None and self.proxy_server is not None and len(self.proxy_server.strip()) > 0:
                proxy_info = httplib2.ProxyInfo(resolved_proxy_type, self.proxy_server, self.proxy_port, proxy_user=self.proxy_user, proxy_pass=self.proxy_password)

                if self.logger is not None:
                    self.logger.debug('Using a proxy server, type=%s, proxy_server="%s"', resolved_proxy_type, self.proxy_server)
            else:
                # No proxy is being used
                proxy_info = None

                if self.logger is not None:
                    self.logger.debug("Not using a proxy server")

            # Make the HTTP object
            self.http = httplib2.Http(proxy_info=proxy_info, timeout=self.timeout, disable_ssl_certificate_validation=True)

            # Setup the credentials if necessary
            if self.username is not None or self.password is not None:
                username, password = self.username, self.password

                if self.username is None:
                    username = ""

                if self.password is None:
                    password = ""

                self.http.add_credentials(username, password)

            return self.http

    def get_url(self, url, operation='GET'):

        http = self.get_http_client()

        # Setup the headers as necessary
        if self.user_agent is not None:
            if self.logger is not None:
                self.logger.debug("Setting user-agent=%s", self.user_agent)

            self.headers['User-Agent'] = self.user_agent

        try:
            self.response, self.content = http.request(url, 'GET', headers=self.headers)
        except socket.timeout:
            raise RequestTimeout()

        except socket.error as e:
            if e.errno in [60, 61]:
                raise RequestTimeout()
            raise ConnectionFailure()

        self.response_code = self.response.status

        return self.content

    def get_response_headers(self):
        return self.response

class MechanizeClient(WebClient):
    """
    A web-client based on the mechanize browser. This client supports things such as form
    submission and authentication.
    """

    def __init__(self, timeout=30, user_agent=DEFAULT_USER_AGENT, logger=None):
        super(MechanizeClient, self).__init__(timeout, user_agent, logger)

        # This is a reference to the HTTP client
        self.http = None
        self.response = None
        self.response_headers = None

        self.browser = None
        self.is_logged_in = False

    @classmethod
    def get_browser(cls, proxy_type=None, proxy_server=None, proxy_port=None, proxy_user=None, proxy_pass=None):
        browser = mechanize.Browser()

        # Ignore robots.txt
        browser.set_handle_robots(False)

        # Ignore meta-refresh handlers
        browser.set_handle_refresh(False)

        # Setup the proxy
        if proxy_server is not None:
            proxy_str = ""

            # Add the user info
            if proxy_user is not None and proxy_pass is not None:
                proxy_str += proxy_user + ":" + proxy_pass + "@"

            # Add the proxy server
            proxy_str += proxy_server

            # Add the proxy server
            if proxy_port is not None:
                proxy_str += ":" + str(proxy_port)

            browser.set_proxies({"http": proxy_str, "https": proxy_str}) # e.g. joe:password@myproxy.example.com:3128

        return browser

    def get_url(self, url, operation='GET'):

        # Get the browser
        if self.browser is None:
            self.browser = self.get_browser(self.proxy_type, self.proxy_server, self.proxy_port, self.proxy_user, self.proxy_pass)

        # Setup the credentials if necessary
        if self.username is not None or self.password is not None and not self.is_logged_in:
            username, password = self.username, self.password

            if username is None:
                username = ""

            if password is None:
                password = ""

            self.browser.add_password(url, self.username, self.password)

        # Set the user-agent
        if self.logger is not None:
            self.logger.debug("Setting user-agent=%s", self.user_agent)

        self.browser.addheaders = [('User-agent', self.user_agent)]

        try:
            self.response = self.browser.open(url, timeout=self.timeout)
            content = self.response.read()
            """
        except mechanize.HTTPError as e:
            raise ConnectionFailure(e)
            """
        except urllib2.URLError as e:
            # Make sure the exception is a timeout
            if e.reason is not None and str(e.reason) == "timed out":
                raise RequestTimeout()
            else:
                raise ConnectionFailure(e)

        # Get the response code
        self.response_code = self.response.code

        # Get the headers
        self.response_headers = {}
        res_info = self.response.info()

        for k in res_info.keys():
            self.response_headers[k] = res_info[k]

        return content

    def get_response_headers(self):
        return self.response_headers

    @classmethod
    def detectFormFields(cls, login_url, proxy_type=None, proxy_server=None, proxy_port=None, proxy_user=None, proxy_pass=None):

        browser = cls.get_browser(proxy_type, proxy_server, proxy_port, proxy_user, proxy_pass)
        browser.open(login_url)

        # Check each form
        for form in browser.forms():
            password_control = None
            user_control = None

            # Try to find the controls
            for control in form.controls:
                # See if this is the password field
                if control.name == "password" and control.type in ["password", "text"]:
                    password_control = control

                # See if this is the username field
                if control.name in ['username', 'uname', 'login', 'email', 'email_address'] and control.type in ["password", "text"]:
                    user_control = control

            if password_control is not None and user_control is not None:
                return form, user_control.name, password_control.name

        return None, None, None

    def doFormLogin(self, login_url, username_field=None, password_field=None):

        self.browser = self.get_browser(self.proxy_type, self.proxy_server, self.proxy_port, self.proxy_user, self.proxy_pass)
        self.browser.open(login_url)

        # Detect the login form and fields if necessary
        if username_field is None or password_field is None:
            _, username_field_name, password_field_name = self.detectFormFields(login_url, self.proxy_type, self.proxy_server, self.proxy_port, self.proxy_user, self.proxy_pass)

            if username_field is None:
                username_field = username_field_name

            if password_field is None:
                password_field = password_field_name

        # Stop if some fields are missing
        if username_field is None:
            raise FormAuthenticationFailed("Username field is missing")

        if password_field is None:
            raise FormAuthenticationFailed("Password field is missing")

        # Find the form with the username and password fields
        login_form = None

        for form in self.browser.forms():
            try:
                form.find_control(username_field)
                form.find_control(password_field)

                login_form = form

                break
            except mechanize._form_controls.ControlNotFoundError:
                # This form didn't have the field, it doesn't appear to be the correct one
                pass

        # Stop if we couldn't find the form
        if login_form is None:
            raise LoginFormNotFound("Login form was not found")

        # Set the form
        self.browser.form = login_form
        self.browser.form[username_field] = self.username
        self.browser.form[password_field] = self.password

        # Authenticate
        res = self.browser.submit()
        content = res.read()

        self.is_logged_in = True

class DefaultWebClient(MechanizeClient):
    """
    This class represents the default web-client that is recommended.
    """
    pass
