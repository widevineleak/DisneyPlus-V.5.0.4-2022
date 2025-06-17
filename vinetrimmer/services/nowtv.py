import base64
import json
import hashlib
import hmac
import time
import sys

import click
from bs4 import BeautifulSoup
from langcodes import Language

from vinetrimmer.objects import Title, Tracks
from vinetrimmer.services.BaseService import BaseService
from vinetrimmer.utils.regex import find

#from selenium import webdriver
#from selenium.webdriver.chrome.service import Service
#from selenium.webdriver.common.by import By
#from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
#from selenium.webdriver.support.ui import WebDriverWait
from langcodes import Language


class NowTV(BaseService):
    """
    Service code for Nowtv italia (https://www.nowtv.it/).

    \b
    Authorization: Cookies
    Security: UHD@-- FHD@SL2000

    Requires an IT IP
    """

    ALIASES = ["NOW"]

    @staticmethod
    @click.command(name="NowTV", short_help="https://nowtv.it")
    @click.argument("title", type=str)
    @click.option("-m", "--movie", is_flag=True, default=False, help="Title is a movie.")
    @click.pass_context
    def cli(ctx, **kwargs):
        return NowTV(ctx, **kwargs)

    def __init__(self, ctx, title, movie):
        self.title = title
        self.movie = movie
        super().__init__(ctx)

        self.license_api = None
        self.skyCEsidismesso01 = None
        self.persona_id = None
        self.userToken = None

        self.configure()

    def configure(self):
        self.skyCEsidismesso01 = self.session.cookies.get('skyCEsidismesso01')
        self.persona_id = self.persona()
        self.userToken = self.get_user_token()

    def get_titles(self):
        headers = {
            "origin": "https://www.nowtv.it",
            "referer": "https://www.nowtv.it/",
            "X-Skyott-Device": "COMPUTER",
            "X-Skyott-Language": "it",
            "X-Skyott-Platform": "PC",
            "X-Skyott-Proposition": "NOWTV",
            "X-Skyott-Provider": "NOWTV",
            "X-Skyott-Territory": "IT"
        }
        if self.movie:
            res = self.session.get(
                url=self.config['endpoints']['movie_info'].format(title_id=self.title),
                headers=headers
            ).json()
            movie = res['data']['showpage']['hero']
            return Title(
                id_=self.title,
                type_=Title.Types.MOVIE,
                name=movie['title'],
                year=movie['year'],
                original_lang="ita",  # TODO: Don't assume
                source=self.ALIASES[0],
                service_data=movie
            )
        else:
            res = self.session.get(
                url=self.config['endpoints']['series_info'].format(title_id=self.title),
                headers=headers
            ).json()
            episodes = []
            for season in res['data']['showpage']['hero']['seasons']:
                episodes = episodes + season['episodes']
            return [Title(
                id_=self.title,
                type_=Title.Types.TV,
                name=e['titleMedium'],
                season=e['seasonNumber'],
                episode=e['episodeNumber'],
                episode_name=e['title'],
                original_lang="ita",  # TODO: Don't assume
                source=self.ALIASES[0],
                service_data=e
            ) for e in episodes]

    def get_tracks(self, title):
        now_id = None
        if "HD" in title.service_data['formats']:
            now_id = title.service_data['formats']["HD"]['contentId']
        else:
            now_id = title.service_data['formats']["SD"]['contentId']

        '''service = Service(executable_path=r'./chromedriver')
        options = webdriver.ChromeOptions()
        options.add_argument('--headless=new')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--no-sandbox')
        options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
        options.add_experimental_option('excludeSwitches', ['disable-component-update'])
        driver = webdriver.Chrome(service=service, options=options)
        driver.get("https://www.nowtv.it/404")
        for cookie in self.cookies:
            cookie_dict = {'domain': cookie.domain, 'name': cookie.name, 'value': cookie.value, 'secure': cookie.secure}
            if cookie.expires:
                cookie_dict['expiry'] = cookie.expires
            if cookie.path_specified:
                cookie_dict['path'] = cookie.path
            driver.add_cookie(cookie_dict)
        driver.get("https://www.nowtv.it/watch/playback/vod/"+contentId)

        res = None
        tries = 0

        def process_browser_log_entry(entry):
                response = json.loads(entry['message'])['message']
                return response

        while res == None and tries < 10:
            time.sleep(10)
            tries += 1
            browser_log = driver.get_log('performance') 
            events = [process_browser_log_entry(entry) for entry in browser_log]
            events = [event for event in events if 'Network.response' in event['method']]
            
            for e in events:
                if 'params' in e and 'response' in e['params']:
                    if '/video/playouts/vod' in e['params']['response']['url'] and e['params']['type'] != 'Preflight':
                        res = driver.execute_cdp_cmd('Network.getResponseBody', {'requestId': e["params"]["requestId"]})

        driver.close()'''

        '''if not res:
            self.log.exit(f" - Selenium couldn't find /video/playouts/vod request")
            raise

        manifest = json.loads(res['body'])

        if "errorCode" in manifest:
            self.log.exit(f" - An error occurred: {manifest['description']} [{manifest['errorCode']}]")
            raise

        self.license_api = manifest["protection"]["licenceAcquisitionUrl"]
        #self.license_bt = manifest["protection"]["licenceToken"]'''

        headers = {
            'accept': 'application/vnd.playvod.v1+json',
            'content-type': 'application/vnd.playvod.v1+json',
            'x-skyott-device': 'TV',
            'x-skyott-platform': 'ANDROIDTV',
            'x-skyott-proposition': 'NOWTV',
            'x-skyott-provider': 'NOWTV',
            'x-skyott-territory': 'IT',
            'x-skyott-usertoken': self.userToken,
        }

        vod_url = 'https://p.sky.com/video/playouts/vod'

        post_data = {
		  "device": {
			"capabilities": [
					#H265 EAC3
					{
					  "transport": "DASH",
					  "protection": "PLAYREADY",
					  "vcodec": "H265",
					  "acodec": "EAC3",
					  "container": "TS"
					},
					{
					  "transport": "DASH",
					  "protection": "PLAYREADY",
					  "vcodec": "H265",
					  "acodec": "EAC3",
					  "container": "ISOBMFF"
					},
					{
					  "container": "MP4",
					  "vcodec": "H265",
					  "acodec": "EAC3",
					  "protection": "PLAYREADY",
					  "transport": "DASH"
					},

					#H264 EAC3
					{
					  "transport": "DASH",
					  "protection": "PLAYREADY",
					  "vcodec": "H264",
					  "acodec": "EAC3",
					  "container": "TS"
					},
					{
					  "transport": "DASH",
					  "protection": "PLAYREADY",
					  "vcodec": "H264",
					  "acodec": "EAC3",
					  "container": "ISOBMFF"
					},
					{
					  "container": "MP4",
					  "vcodec": "H264",
					  "acodec": "EAC3",
					  "protection": "PLAYREADY",
					  "transport": "DASH"
					},

					#H265 AAC
					{
					  "transport": "DASH",
					  "protection": "PLAYREADY",
					  "vcodec": "H265",
					  "acodec": "AAC",
					  "container": "TS"
					},
					{
					  "transport": "DASH",
					  "protection": "PLAYREADY",
					  "vcodec": "H265",
					  "acodec": "AAC",
					  "container": "ISOBMFF"
					},
					{
					  "container": "MP4",
					  "vcodec": "H265",
					  "acodec": "AAC",
					  "protection": "PLAYREADY",
					  "transport": "DASH"
					},

					#H264 AAC
					{
					  "transport": "DASH",
					  "protection": "PLAYREADY",
					  "vcodec": "H264",
					  "acodec": "AAC",
					  "container": "TS"
					},
					{
					  "transport": "DASH",
					  "protection": "PLAYREADY",
					  "vcodec": "H264",
					  "acodec": "AAC",
					  "container": "ISOBMFF"
					},
					{
					  "container": "MP4",
					  "vcodec": "H264",
					  "acodec": "AAC",
					  "protection": "PLAYREADY",
					  "transport": "DASH"
					},
				],
			"model": "Nvidia Shield Android TV",
			"maxVideoFormat": 'UHD',
			"hdcpEnabled": 'false',
			"supportedColourSpaces": [
			  "DV",
			  "HDR10",
			  "SDR"
			]
		  },
		  "client": {
			"thirdParties": [
			  "CONVIVA",
			  "FREEWHEEL"
			]
		  },
		  "parentalControlPin": "null"
		}
        
        #now_id = now_id.replace('_HD', '')
        
        if len(now_id) < 21:
            post_data['device']['maxVideoFormat'] = 'HD'
            post_data['contentId'] = now_id
        else:
            post_data['providerVariantId'] = now_id
            
        if 'TF' in now_id:
            post_data['providerVariantId'] = now_id
            
        post_data = json.dumps(post_data)

        headers['x-sky-signature'] = self.calculate_signature('POST', '/video/playouts/vod', headers, post_data)

        manifest = json.loads(self.session.post(vod_url, headers=headers, data=post_data).content)

        self.license_api = manifest['protection']['licenceAcquisitionUrl']

        print(f"lic: {self.license_api}")

        dash = manifest["asset"]["endpoints"][0]["url"]

        self.log.info(f'DASH: {dash}')

        tracks = Tracks.from_mpd(
            url=manifest["asset"]["endpoints"][0]["url"],
            session=self.session,
            #lang=title.original_lang,
            source=self.ALIASES[0]
        )
        for track in tracks:
            if track.language.to_alpha3() == 'ori':
                track.is_original_lang = True
                track.language = Language.get('eng') # Don't assume
                for t in tracks:
                    if t.__class__.__name__ == track.__class__.__name__ and t.language.to_alpha3() == 'ita':
                        t.is_original_lang = False

            track.needs_proxy = True

        return tracks

    def get_chapters(self, title):
        return []

    def certificate(self, challenge, **_):
        return None

    def license(self, challenge, **_):
        # TODO
        # returns b'{"errorCode":"OVP_00118","description":"OTT proposition mismatch"}'
        # Maybe needs UK proxy
        #path = "/" + self.license_api.split("://", 1)[1].split("/", 1)[1]

        res = self.session.post(
            url=self.license_api,
            #headers={
                #"Accept": "*/*",
                #'Content-Type':'application/octet-stream',
                #"X-Sky-Signature": self.calculate_signature('POST', path, {}, "")
            #},
            data=challenge.encode('utf-8'),  # expects bytes
        ).content
        
        return base64.b64encode(res).decode()
   
    def persona(self):
        persona_url = 'https://persona-store.sky.com/persona-store/personas'

        headers = {
            'accept': 'application/vnd.persona.v1+json',
            'x-skyid-token': self.skyCEsidismesso01,
            'x-skyott-device': 'TV',
            'x-skyott-platform': 'ANDROIDTV',
            'x-skyott-proposition': 'NOWTV',
            'x-skyott-provider': 'NOWTV',
            'x-skyott-territory': 'IT',
            'x-skyott-tokentype': 'SSO',
        }

        try:
            response = json.loads(self.session.get(persona_url, headers=headers).content)
            return response['personas'][0]['personaId']
        except:
            self.log.exit(f" - Unable to get persona, try updating cookies")
            raise

    def get_user_token(self):
        token_url = 'https://auth.client.ott.sky.com/auth/tokens'

        headers = {
            'Accept': 'application/vnd.tokens.v1+json',
            'Content-Type': 'application/vnd.tokens.v1+json',
            'X-SkyOTT-Device': 'TV',
            'X-SkyOTT-Platform': 'ANDROIDTV',
            'X-SkyOTT-Proposition': 'NOWTV',
            'X-SkyOTT-Provider': 'NOWTV',
            'X-SkyOTT-Territory': 'IT',
        }

        post_data = {
            "auth": {
                "authScheme": "MESSO",
                "authToken": self.skyCEsidismesso01,
                "authIssuer": "NOWTV",
                "personaId": self.persona_id,
                "provider": "NOWTV",
                "providerTerritory": 'IT',
                "proposition": "NOWTV"
            },
            "device": {
                "type": 'TV',
                "platform": 'ANDROIDTV',
                "id": 'Z-sKxKApCe7c3dBMGAYtKU8NmWKDcWrCKobKpnVTLqc', #Not so irrelavant anymore
                "drmDeviceId": 'UNKNOWN'
            }
        }

        post_data = json.dumps(post_data)

        headers['Content-MD5'] = hashlib.md5(post_data.encode('utf-8')).hexdigest()

        token_request = json.loads(self.session.post(token_url, headers=headers, data=post_data).content)

        if token_request['userToken'] == None:
            self.log.exit(f" - Unable to get userToken")
            raise

        return token_request['userToken']
            
    def calculate_signature(self, method, path, headers, payload, timestamp=None):
        app_id = 'IE-NOWTV-ANDROID-v1'
        signature_key = bytearray('5f8RLBppaqKGO8bwKwNifjZ6bM8zXCVwkAK7hkhq3PS4pf', 'utf-8')
        sig_version = '1.0'

        if not timestamp:
            timestamp = int(time.time())

        #print('path: {}'.format(path))

        text_headers = ''
        for key in sorted(headers.keys()):
            if key.lower().startswith('x-skyott'):
                text_headers += key + ': ' + headers[key] + '\n'
        #print(text_headers)
        headers_md5 = hashlib.md5(text_headers.encode()).hexdigest()
        #print(headers_md5)

        if sys.version_info[0] > 2 and isinstance(payload, str):
            payload = payload.encode('utf-8')
            payload_md5 = hashlib.md5(payload).hexdigest()

        to_hash = ('{method}\n{path}\n{response_code}\n{app_id}\n{version}\n{headers_md5}\n'
                '{timestamp}\n{payload_md5}\n').format(method=method, path=path,
                    response_code='', app_id=app_id, version=sig_version,
                    headers_md5=headers_md5, timestamp=timestamp, payload_md5=payload_md5)
        #print(to_hash)

        hashed = hmac.new(signature_key, to_hash.encode('utf8'), hashlib.sha1).digest()
        signature = base64.b64encode(hashed).decode('utf8')
        return 'SkyOTT client="{}",signature="{}",timestamp="{}",version="{}"'.format(app_id, signature, timestamp, sig_version)