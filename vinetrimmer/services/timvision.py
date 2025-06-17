import base64

import click
import platform
import requests
from pathlib import Path
import jsonpickle
import subprocess
import urllib.parse
import json
import os

from vinetrimmer.objects import Title, Tracks
from vinetrimmer.services.BaseService import BaseService
from vinetrimmer.utils.regex import find
from vinetrimmer.utils.xml import load_xml




class TimVision(BaseService):
    """
    Service code for TimVision (https://www.timvision.it).

    \b
    Authorization: Cookies
    Security: UHD@SL3000 FHD@SL2000/L1 HD@L3(ChromeCDM) SD@L3

    \b
    Notes:
        - If the connection just hangs/times out, your IP may be blocked.
        - UHD requires a whitelisted device.
    """

    ALIASES = ["TMVS", "TimVision", "Timvision", "timvision"]
    DRM_TYPE_MAP = {
        "DRM_MKPC_WIDEVINE_DASH": 0,
        "DRM_WIDEVINE": 1,
        "DRM_MKPC_PLAYREADY_DASH": 2,
    }

    TITLE_RE = r"^(?P<url>https?://(?:www\.)?timvision.it/(?P<type>cinema|serie|kids)/[a-zA-Z0-9-]+/h/(?P<id>[0-9]+_[0-9]+))"

    @staticmethod
    @click.command(
        name="TimVision",
        short_help="https://www.timvision.it/",
    )
    @click.argument("title", type=str, required=False)
    @click.pass_context
    def cli(ctx, **kwargs):
        return TimVision(ctx, **kwargs)

    def __init__(self, ctx, title):
        super().__init__(ctx)

        m = self.parse_title(ctx, title)

        self.title = m.get("id")
        self.type = m.get("type")
        self.url = m.get("url")

        self.vcodec = ctx.parent.params["vcodec"]
        self.audio_only = ctx.parent.params["audio_only"]
        self.subtitles_only = ctx.parent.params["subs_only"]
        self.chapters_only = ctx.parent.params["chapters_only"]
        self.profile = ctx.obj.profile
        self.playready = True
        self.retrying = False

        self.configure()

    def get_titles(self):
        title = []

        res = self.session.get(
            url=self.url,
            headers=self.headers,
        ).text

        token_hash = self.session.cookies.get("tokenCMS")

        if self.type in ("serie", "kids"):
            res = self.session.get(
                url=self.config["endpoints"]["titles"].format(
                    id=self.title, token=token_hash
                ),
                params={
                    "detailType": "detailShow",
                    "objectType": "brand",
                    "dsp": "detailPage",
                    "featureToggles": "detailV5",
                },
                headers=self.headers,
            ).json()
            self.log.debug(res)
            title_str = res.get('currentPage', {}).get('displayName', '')
            
            tracks_headers = {
                'origin': 'https://www.timvision.it',
                'referer': 'https://www.timvision.it/',
                'tokenpass': f'{self.logintoken}',
                'xx-profile-id': '0',
            }

            response = self.session.get(
                url=self.config["endpoints"]["episodes"].format(
                    id=self.title, token=token_hash
                ),
            params = {
                    'trkContentId': f'{self.title}',
                    'featureToggles': 'tvodFunnelV5',
                },
                headers=tracks_headers,
            )
            data_episode = json.loads(response.text)
            episodes = data_episode.get("episodes", {}).get("contents", [])
            if len(episodes) == 50:
                episodes += data_episode.get("episodes", {}).get("contents", [])
            season_urls = []
            for x in season_urls:
                data = self.session.get(
                    url=x,
                    headers=tracks_headers,
                ).json()
                episodes += data.get("episodes", {}).get("contents", [])
                if len(data.get("episodes", {}).get("contents", [])) == 50:
                    episodes += data_episode.get("episodes", {}).get("contents", [])

            for episode in episodes:
                title.append(
                    Title(
                        id_=episode.get("contentID"),
                        type_=Title.Types.TV,
                        name=title_str,
                        episode_name=episode.get("editorialTitle")
                        or episode.get("title"),
                        season=episode["seasonNumber"],
                        episode=episode["episodeNumber"],
                        original_lang="en",  # TODO: Get original language
                        source=self.ALIASES[0]
                    )
                )

            self.log.debug(res)
        elif self.type == "cinema":
            info_headers = {
                    'origin': 'https://www.timvision.it',
                    'referer': 'https://www.timvision.it/',
            }

            res = self.session.get(
                url=self.config["endpoints"]["titles"].format(
                    id=self.title, token=token_hash
                ),
                params={
                    'objectType': 'brand',
                    'dsp': 'detailPage',
                    'trkContentId': f'{self.title}',
                },
                headers=info_headers,
            ).json()
            self.log.debug(res)
            if year := res.get('meta', {}).get('title', ''):
                year = year[-4:]

            title = Title(
                id_=res.get('tracking', {}).get('dataLayer', {}).get('content_id', ''),
                type_=Title.Types.MOVIE,
                name=res.get('currentPage', {}).get('displayName', ''),
                year=year,
                original_lang="en",  # TODO: Get original language
                source=self.ALIASES[0],
                service_data=res,
            )

        return title

    def get_tracks(self, title):

        self.log.debug(title.service_data)

        try:
            res = self.session.get(
                url=self.config["endpoints"]["playset"].format(id=title.id),
                headers=self.headers,
            ).json()
        except requests.HTTPError as e:
            res = e.response.json()

            if "403" in res["code"] and not self.retrying:
                self.log.warning("Received a 403 error, deleting cached tokens")
                self.device_cache_path.unlink()
                self.configure()
                self.retrying = True
                return self.get_tracks(title)

            raise self.log.exit(f"{res['message']} [{res['code']}]") from res

        self.log.debug(res)

        if self.playready:
            desired_drm_type_map = [x for x in self.DRM_TYPE_MAP if "PLAYREADY" in x]
        else:
            desired_drm_type_map = [x for x in self.DRM_TYPE_MAP if "WIDEVINE" in x]

        streams = sorted(
            (x for x in res["available"] if x["drmType"] in desired_drm_type_map),
            key=lambda x: self.DRM_TYPE_MAP[x["drmType"]],
        )
        quality = "HD"

        streams_ = [x for x in streams if x["quality"] == quality]
        if not streams_:
            streams_ = streams

        data = self.session.put(
            url=self.config["endpoints"]["view"],
            params={"include": "medias"},
            json=streams_[0],
            headers=self.headers,
        ).json()

        self.log.debug(data)

        for media in data.get("medias", []):
            title.service_data = {
                "license_media": media.get("@licence"),
                "drmId": media.get("drmId"),
            }
            for file_data in media.get("files", []):
                if file_data.get("mimeType") == "application/dash+xml":
                    dash_mpd = file_data.get('distribURL', '')
                    self.log.info(f"DASH: {dash_mpd}")
                    tracks = Tracks.from_mpd(
                        url=file_data.get("distribURL"),
                        session=self.session,
                        source=self.ALIASES[0]
                    )

        for x in tracks:
            for num, y in enumerate(reversed(x.url)):
                if num > 8:
                    break
                if requests.head(y).status_code == 200:
                    break
                else:
                    x.url.remove(y)

        return tracks

    def certificate(self, *_, **__):
        return None #Cdm.common_privacy_cert
    
    def license(self, challenge, title, *_, **__):
        if self.playready:
            challenge = challenge[challenge.find("<soap:Envelope") :]
        try:
            res = self.session.post(
                url=self.config["endpoints"]["license"].format(
                    media=title.service_data["license_media"]
                ),
                data=challenge if self.playready else base64.b64encode(challenge),
                params={"drmConfig": "mkpl::true", "drmId": title.service_data["drmId"]},
                headers={
                    "Content-Type": "text/plain",
                    **self.headers,
                },
            ).text
        except requests.HTTPError as e:
            res = e.response.json()
            self.log.debug(res)
            raise self.log.exit(f"{res['message']} [{res['code']}]") from res

        self.log.debug(res)

        if self.playready:
            res = (
                '<?xml version="1.0" encoding="utf-8"?>'
                + res[res.find("<soap:Envelope") : res.rfind("</soap:Envelope>") + 16]
            )
            base64_lic = base64.b64encode(res.encode()).decode()

            return base64_lic

        res = load_xml(res)
        return res.findtext(".//license")

    # Service-specific functions

    def configure(self):
        self.log.info(" + Logging in")
        self.headers = {
            "origin": "https://www.timvision.it",
            "referer": "https://www.timvision.it/",
        }

        self.device_cache_path = Path(self.get_cache("device_tokens_{profile}.json".format(
            profile=self.profile,
        )))

        self.pass_id = self.session.cookies.get("p_pass_token")
        self.session_id = self.session.cookies.get("sessionId")
        self.device_id = self.session.cookies.get("deviceId")

        if self.device_cache_path.exists():
            self.log.info(" + Using cached device tokens")
            with open(self.device_cache_path, encoding="utf-8") as fd:
                cache = jsonpickle.decode(fd.read())
        else:
            res = self.session.get(url=self.config["endpoints"]["prod"]).json()
            data = res.get("pass", [])
            url = data.get("url")
            portailId = data.get("portailId")
            system = platform.system()
            if system == "Windows":
                passId_encoded = urllib.parse.quote(self.pass_id, safe='') 
                current_dir = os.getcwd()
                curl_path = os.path.join(current_dir, 'binaries', 'curl.exe')
                login = [
                    curl_path, url,
                    "-H", "accept: */*",
                    "-H", "accept-language: it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7,es;q=0.6,pt;q=0.5,ru;q=0.4",
                    "-H", "content-type: application/x-www-form-urlencoded",
                    "-H", "origin: https://www.timvision.it",
                    "-H", "priority: u=1, i",
                    "-H", "referer: https://www.timvision.it/",
                    "-H", 'sec-ch-ua: "Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
                    "-H", "sec-ch-ua-mobile: ?0",
                    "-H", 'sec-ch-ua-platform: "Windows"',
                    "-H", "sec-fetch-dest: empty",
                    "-H", "sec-fetch-mode: cors",
                    "-H", "sec-fetch-site: cross-site",
                    "-H", "user-agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
                    "--data-raw", f"portailId={portailId}&media=web&vect=INTERNET&passIdType=pass&noCache=false&passId={passId_encoded}"
                ]
                try:
                    result = subprocess.run(login, capture_output=True, text=True, check=True)
                    login_info = result.stdout
                    login_json = json.loads(login_info)
                    self.log.debug(login_json)
                except subprocess.CalledProcessError as e:
                    self.log.info("Logging error: ", e)
            elif system == "Darwin":
                passId_encoded = urllib.parse.quote(self.pass_id, safe='') 
                current_dir = os.getcwd()
                curl_path = os.path.join(current_dir, 'binaries', 'curl')
                login = [
                    curl_path, url,
                    "-H", "Accept: */*",
                    "-H", "Accept-Language: it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
                    "-H", "Connection: keep-alive",
                    "-H", "Content-Type: application/x-www-form-urlencoded",
                    "-H", "Origin: https://www.timvision.it",
                    "-H", "Referer: https://www.timvision.it/",
                    "-H", "Sec-Fetch-Dest: empty",
                    "-H", "Sec-Fetch-Mode: cors",
                    "-H", "Sec-Fetch-Site: cross-site",
                    "-H", "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
                    "-H", "sec-ch-ua: \"Chromium\";v=\"128\", \"Not;A=Brand\";v=\"24\", \"Google Chrome\";v=\"128\"",
                    "-H", "sec-ch-ua-mobile: ?0",
                    "-H", "sec-ch-ua-platform: \"macOS\"",
                    "--data-raw", f"portailId={portailId}&media=web&vect=INTERNET&noCache=false&analytics=true&trackingPub=true&anonymousTracking=true&passId={passId_encoded}&passIdType=pass"
                ]
                try:
                    result = subprocess.run(login, capture_output=True, text=True, check=True)
                    login_info = result.stdout
                    login_json = json.loads(login_info)
                    self.log.debug(login_json)
                except subprocess.CalledProcessError as e:
                    self.log.info("Logging error: ", e)
            
            cache = login_json.get("response", {})
            self.device_cache_path.parent.mkdir(exist_ok=True, parents=True)
            with open(self.device_cache_path, "w", encoding="utf-8") as fd:
                fd.write(jsonpickle.encode(cache))
        self.logintoken = cache.get("passToken", '')
        self.headers = {
            "Authorization": f'PASS Token=\"{cache["passToken"]}\"',
            "Xx-Device": f"pc {self.session_id}",
            "XX-DISTMODES": "catchup,live,svod,tvod,posttvod",
            "xx-domain": "tiita",
            "Xx-Operator": "pc",    
            "Xx-Oz": "tiita",
            "Xx-Profile-Id": "0",
            "Xx-Request-Id": f"{self.device_id}",
            "Xx-Service": "mycanal",
            "XX-API-VERSION": "3.0",
            "XX-SPYRO-VERSION": "3.0",
            "origin": "https://www.timvision.it",
            "referer": "https://www.timvision.it/",
        }