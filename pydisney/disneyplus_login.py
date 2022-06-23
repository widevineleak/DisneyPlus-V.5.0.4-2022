import re
import requests, json

class LOGIN(object):
    def __init__(self, email, password, proxies=False):
        self.email = email
        self.password = password
        self.web_page = 'https://www.disneyplus.com/login'
        self.devices_url = "https://global.edge.bamgrid.com/devices"
        self.login_url = 'https://global.edge.bamgrid.com/idp/login'
        self.token_url = "https://global.edge.bamgrid.com/token"
        self.grant_url = 'https://global.edge.bamgrid.com/accounts/grant'
        self.SESSION = requests.Session()
        if proxies:
            self.SESSION.proxies.update(proxies)

    def clientapikey(self):
        r = self.SESSION.get(self.web_page)
        match = re.search("window.server_path = ({.*});", r.text)
        janson = json.loads(match.group(1))
        clientapikey = janson["sdk"]["clientApiKey"]

        return clientapikey

    def assertion(self, client_apikey):

        postdata = {
            "applicationRuntime": "firefox",
            "attributes": {},
            "deviceFamily": "browser",
            "deviceProfile": "macosx"
        }

        header = {"authorization": "Bearer {}".format(client_apikey), "Origin": "https://www.disneyplus.com"}
        res = self.SESSION.post(url=self.devices_url, headers=header, json=postdata)

        assertion = res.json()["assertion"]
        
        return assertion

    def access_token(self, client_apikey, assertion_):

        header = {"authorization": "Bearer {}".format(client_apikey), "Origin": "https://www.disneyplus.com"}

        postdata = {
            "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
            "latitude": "0",
            "longitude": "0",
            "platform": "browser",
            "subject_token": assertion_,
            "subject_token_type": "urn:bamtech:params:oauth:token-type:device"
        }

        res = self.SESSION.post(url=self.token_url, headers=header, data=postdata)

        if res.status_code == 200:
            access_token = res.json()["access_token"]
            return access_token

        if 'unreliable-location' in str(res.text):
            print('Make sure you use NL proxy/vpn, or your proxy/vpn is blacklisted.')
            exit()
        else:
            try:
                print('Error: ' + str(res.json()["errors"]['error_description']))
                exit()
            except Exception:
                print('Error: ' + str(res.text))
                exit()

        return None

    def login(self, access_token):
        headers = {
            'accept': 'application/json; charset=utf-8',
            'authorization': "Bearer {}".format(access_token),
            'content-type': 'application/json; charset=UTF-8',
            'Origin': 'https://www.disneyplus.com',
            'Referer': 'https://www.disneyplus.com/login/password',
            'Sec-Fetch-Mode': 'cors',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/76.0.3809.132 Safari/537.36',
            'x-bamsdk-platform': 'windows',
            'x-bamsdk-version': '3.10',
        }

        data = {'email': self.email, 'password': self.password}
        res = self.SESSION.post(url=self.login_url, data=json.dumps(data), headers=headers)
        if res.status_code == 200:
            id_token = res.json()["id_token"]
            return id_token

        try:
            print('Error: ' + str(res.json()["errors"]))
            exit()
        except Exception:
            print('Error: ' + str(res.text))
            exit()

        return None

    def grant(self, id_token, access_token):

        headers = {
            'accept': 'application/json; charset=utf-8',
            'authorization': "Bearer {}".format(access_token),
            'content-type': 'application/json; charset=UTF-8',
            'Origin': 'https://www.disneyplus.com',
            'Referer': 'https://www.disneyplus.com/login/password',
            'Sec-Fetch-Mode': 'cors',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/76.0.3809.132 Safari/537.36',
            'x-bamsdk-platform': 'windows',
            'x-bamsdk-version': '3.10',
        }

        data = {'id_token': id_token}

        res = self.SESSION.post(url=self.grant_url, data=json.dumps(data), headers=headers)
        assertion = res.json()["assertion"]

        return assertion


    def FinalToken(self, subject_token, client_apikey):

        header = {"authorization": "Bearer {}".format(client_apikey), "Origin": "https://www.disneyplus.com"}

        postdata = {
            "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
            "latitude": "0",
            "longitude": "0",
            "platform": "browser",
            "subject_token": subject_token,
            "subject_token_type": "urn:bamtech:params:oauth:token-type:account"
        }

        res = self.SESSION.post(url=self.token_url, headers=header, data=postdata)

        if res.status_code == 200:
            access_token = res.json()["access_token"]
            expires_in = res.json()["expires_in"]
            return access_token, expires_in

        try:
            print('Error: ' + str(res.json()["errors"]))
            exit()
        except Exception:
            print('Error: ' + str(res.text))
            exit()

        return None, None

    def GetAuthToken(self):

        clientapikey_ = self.clientapikey()
        assertion_ = self.assertion(clientapikey_)
        access_token_ = self.access_token(clientapikey_, assertion_)
        id_token_ = self.login(access_token_)
        user_assertion = self.grant(id_token_, access_token_)
        TOKEN, EXPIRE = self.FinalToken(user_assertion, clientapikey_)

        return TOKEN, EXPIRE

