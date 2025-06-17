import json
import re
from urllib.parse import urljoin
from datetime import datetime, timedelta
from pathlib import Path

import click
import m3u8
import requests
import base64

from vinetrimmer.objects import Title, Tracks
from vinetrimmer.objects.tracks import AudioTrack, MenuTrack, TextTrack, VideoTrack
from vinetrimmer.services.BaseService import BaseService
from requests.adapters import HTTPAdapter, Retry
from vinetrimmer.config import config

class ParamountPlus(BaseService):
    """
    Service code for Paramount's Paramount+ streaming service (https://paramountplus.com).

    \b
    Authorization: Credentials
    Security: UHD@L3, doesn't care about releases.
    """

    ALIASES = ["PMTP", "paramountplus", "paramount+"]
    TITLE_RE = [
        r"^https?://(?:www\.)?paramountplus\.com/(?P<type>movies)/[a-z0-9_-]+/(?P<id>\w+)",
        r"^https?://(?:www\.)?paramountplus\.com/(?P<type>shows)/(?P<id>[a-zA-Z0-9_-]+)(/)?",
        r"^https?://(?:www\.)?paramountplus\.com(?:/[a-z]{2})?/(?P<type>movies)/[a-z0-9_-]+/(?P<id>\w+)",
        r"^https?://(?:www\.)?paramountplus\.com(?:/[a-z]{2})?/(?P<type>shows)/(?P<id>[a-zA-Z0-9_-]+)(/)?",
        r"^(?P<id>\d+)$",
    ]
    VIDEO_CODEC_MAP = {"H264": ["avc", "avc1"], "H265": ["hvc", "dvh", "hvc1", "hev1", "dvh1", "dvhe"]}
    AUDIO_CODEC_MAP = {"AAC": "mp4a", "AC3": "ac-3", "EC3": "ec-3"}

    @staticmethod
    @click.command(name="ParamountPlus", short_help="https://paramountplus.com")
    @click.argument("title", type=str, required=False)
    @click.option("-m", "--movie", is_flag=True, default=False, help="Title is a Movie.")
    @click.option(
        "-c", "--clips", is_flag=True, default=False, help="Download clips instead of episodes (for TV shows)"
    )
    @click.pass_context
    def cli(ctx: click.Context, **kwargs):
        return ParamountPlus(ctx, **kwargs)

    def __init__(self, ctx: click.Context, title: str, movie: bool, clips: bool):
        super().__init__(ctx)
        m = self.parse_title(ctx, title)
        self.movie = movie or m.get("type") == "movies"
        self.clips = clips

        self.vcodec = ctx.parent.params["vcodec"]
        self.acodec = ctx.parent.params["acodec"]
        self.range = ctx.parent.params["range_"]
        self.wanted = ctx.parent.params["wanted"]
        self.shorts = False
        
        self.cdm = ctx.obj.cdm
        self.profile = ctx.obj.profile

        ctx.parent.params["acodec"] = "EC3"

        if self.range != "SDR":
            # vcodec must be H265 for High Dynamic Range
            self.vcodec = "H265"

        self.configure()

    def get_titles(self):
        if self.movie:
            res = self.session.get(
                url=self.config[self.region]["movie"].format(title_id=self.title),
                params={
                    "includeTrailerInfo": "true",
                    "includeContentInfo": "true",
                    "locale": "en-us",
                    "at": self.config[self.region]["at_token"],
                },
            ).json()
            if not res["success"]:
                if res["message"] == "No movie found for contentId.":
                    raise self.log.exit(" - Unable to find movie. For TV shows, use the numeric ID.")
                else:
                    raise self.log.exit(f" - Failed to get title information: {res['message']}")

            title = res["movie"]["movieContent"]

            return Title(
                id_=title["contentId"],
                type_=Title.Types.MOVIE,
                name=title["title"],
                year=title["_airDateISO"][:4],  # todo: find a way to get year, this api doesnt return it
                original_lang="en",  # TODO: Don't assume
                source=self.ALIASES[0],
                service_data=title,
            )
        else:
            res = self.session.get(
                url=self.config[self.region]["shows"].format(title=self.title)
            ).json()
            links = next((x.get("links") for x in res["showMenu"] if x.get("device_app_id") == "all_platforms"), None)
            config = next((x.get("videoConfigUniqueName") for x in links if x.get("title").strip() == "Episodes"), None)
            show = next((x for x in res["show"]["results"] if x.get("type") == "show"), None)
            seasons = [x["seasonNum"] for x in res["available_video_seasons"]["itemList"] if x.get("seasonNum")]
            showId = show.get("show_id")

            show_data = self.session.get(
                url=self.config[self.region]["section"].format(showId=showId, config=config),
                params={"platformType": "apps", "rows": "1", "begin": "0"},
            ).json()

            section = next(
                (x["sectionId"] for x in show_data["videoSectionMetadata"] if x["title"] == "Full Episodes"), None
            )

            episodes = []
            for season in seasons:
                res = self.session.get(
                    url=self.config[self.region]["seasons"].format(section=section),
                    params={"begin": "0", "rows": "999", "params": f"seasonNum={season}", "seasonNum": season},
                ).json()
                episodes.extend(res["sectionItems"].get("itemList"))

            titles = []
            for episode in episodes:
                titles.append(
                    Title(
                        id_=episode.get("contentId") or episode.get("content_id"),
                        type_=Title.Types.TV,
                        name=episode.get("seriesTitle") or episode.get("series_title"),
                        season=episode.get("seasonNum") or episode.get("season_number") or 0,
                        episode=episode["episodeNum"] if episode["fullEpisode"] else episode["positionNum"],
                        episode_name=episode["label"],
                        original_lang="en",  # TODO: Don't assume
                        source=self.ALIASES[0],
                        service_data=episode,
                    )
                )

            return titles

    def get_tracks(self, title: Title):
        assets = (
            ["DASH_CENC_HDR10"],
            [
                "HLS_AES",
                "DASH_LIVE",
                "DASH_CENC_HDR10",
                "DASH_TA",
                "DASH_CENC",
                "DASH_CENC_PRECON",
                "DASH_CENC_PS4",
            ],
        )
        for asset in assets:
            r = requests.Request(
                "GET",
                url=self.config["LINK_PLATFORM_URL"].format(video_id=title.id),
                params={
                    "format": "redirect",
                    "formats": "MPEG-DASH",
                    "assetTypes": "|".join(asset),
                    "manifest": "M3U",
                    "Tracking": "true",
                    "mbr": "true",
                },
            )
            req = self.session.send(self.session.prepare_request(r), allow_redirects=False)
            if req.ok:
                break
        else:
            raise ValueError(f"Manifest Error: {req.text}")

        mpd_url = req.headers.get('location')

        try:
            tracks: Tracks = Tracks.from_mpd(
                url=mpd_url.replace("cenc_precon_dash", "cenc_dash"),
                source=self.ALIASES[0],
                session=self.session,
            )
        except:
            tracks: Tracks = Tracks.from_mpd(
                url=mpd_url,
                source=self.ALIASES[0],
                session=self.session,
            )
        tracks.subtitles.clear()

        req = self.session.get(
            url=self.config["LINK_PLATFORM_URL"].format(video_id=title.id),
            params={
                "format": "redirect",
                "formats": "M3U",
                "assetTypes": "|".join(["HLS_FPS_PRECON"]),
                "manifest": "M3U",
                "Tracking": "true",
                "mbr": "true",
            },
        )
        hls_url = req.url

        tracks_m3u8 = Tracks.from_m3u8(
            m3u8.load(hls_url),
            source=self.ALIASES[0],
        )
        tracks.subtitles = tracks_m3u8.subtitles

        for track in tracks:
            # track.id = track.id
            if isinstance(track, VideoTrack):
                track.hdr10 = (
                    track.codec[:4] in ("hvc1", "hev1") and track.extra[0].attrib.get("codecs")[5] == "2"
                ) or (track.codec[:4] in ("hvc1", "hev1") and "HDR10plus" in track.url)

                track.dv = track.codec[:4] in ("dvh1", "dvhe")

            if isinstance(track, VideoTrack) or isinstance(track, AudioTrack):
                if self.shorts:
                    track.encrypted = False

            if isinstance(track, TextTrack):
                track.codec = "vtt"
                #if track.language.language == "en":
                #    track.sdh = True  # TODO: don't assume SDH

        if self.vcodec:
             tracks.videos = [x for x in tracks.videos if (x.codec or "")[:4] in self.VIDEO_CODEC_MAP[self.vcodec]]

        if self.acodec:
            tracks.audios = [x for x in tracks.audios if (x.codec or "")[:4] == self.AUDIO_CODEC_MAP[self.acodec]]
            
        for track in tracks.audios:
            role = track.extra[1].find("Role")
            if role is not None and role.get("value") == "description":
                track.descriptive = True

        return tracks

    def get_chapters(self, title: Title):
        chapters = []
        events = title.service_data.get("playbackEvents")
        events = {k: v for k, v in events.items() if v is not None}
        events = dict(sorted(events.items(), key=lambda item: item[1]))
        if not events:
            return chapters

        chapters_titles = {
            "endCreditChapterTimeMs": "Credits",
            "previewStartTimeMs": "Preview Start",
            "previewEndTimeMs": "Preview End",
            "openCreditEndTimeMs": "openCreditEnd",
            "openCreditStartTime": "openCreditStart",
        }

        for name, time_ in events.items():
            if isinstance(time_, (int, float)):
                chapters.append(
                    MenuTrack(
                        number=len(chapters) + 1,
                        title=chapters_titles.get(name),
                        timecode=MenuTrack.format_duration(time_ / 1000),
                    )
                )

        # chapters = sorted(chapters, key=self.converter_timecode)

        return chapters

    def certificate(self, **_):
        return None  # will use common privacy cert

    def license(self, challenge, title, **_):
        contentId = title.service_data.get("contentId") or title.service_data.get("content_id")
        if not contentId:
            raise ValueError("Error")

        r = self.session.post(
            url=self.config["license"],
            params={
                "CrmId": "cbsi",
                "AccountId": "cbsi",
                "SubContentType": "Default",
                "ContentId": title.service_data.get("contentId") or title.service_data.get("content_id"),
            },
            headers={"Authorization": f"Bearer {self.get_barrear(content_id=contentId)}"},
            data=challenge,  # expects bytes
        )

        if r.headers["Content-Type"].startswith("application/json"):
            res = r.json()
            raise ValueError(res["message"])

        return base64.b64encode(r.content).decode()

    def configure(self):
        self.region = self.session.get("https://ipinfo.io/json").json()["country"]
        if self.region != "US":
            if self.region != "FR":
                self.region = "INTL"

            #self.device_cache_path = Path(self.get_cache("device_tokens_{profile}.json".format(
            #profile=self.profile,
            #)))

            #if self.device_cache_path.exists():
                #with open(self.device_cache_path, encoding="utf-8") as fd:
                    #date = jsonpickle.decode(fd.read())  
                #if "expiry" in date and datetime.fromisoformat(date["expiry"]) > datetime.now():
                    #self.log.warning(" + Using cached device tokens")
                    #cache = date
                #else:
                    #self.log.warning(" + Refreshing cookies")
                    #self.device_cache_path.unlink()
                    #if not self.credentials:
                        #raise self.log.exit(" - No credentials provided, unable to log in.")
                    #self.session.headers.update({"user-agent": self.config["Android"]["UserAgent"]})
                    #self.session.params.update({"at": self.config[self.region]["at_token"]})
                    #username = self.credentials.username
                    #password = self.credentials.password
                    #expiry = (datetime.now() + timedelta(minutes=3)).isoformat()
                    #cookie = self.login(username=username, password=password)
                    #cache = {"cookie": cookie, "expiry": expiry}
                    #self.device_cache_path.parent.mkdir(exist_ok=True, parents=True)
                    #with open(self.device_cache_path, "w", encoding="utf-8") as fd:
                        #fd.write(jsonpickle.encode(cache))
            #else:
            if not self.credentials:
                raise self.log.exit(" - No credentials provided, unable to log in.")
            self.log.warning(" + Logging in")
            self.session.headers.update({"user-agent": self.config["Android"]["UserAgent"]})
            self.session.params.update({"at": self.config[self.region]["at_token"]})
            username = self.credentials.username
            password = self.credentials.password
            #expiry = (datetime.now() + timedelta(minutes=3)).isoformat()
            cookie = self.login(username=username, password=password)
                #cache = {"cookie": cookie, "expiry": expiry}
                #self.device_cache_path.parent.mkdir(exist_ok=True, parents=True)
                #with open(self.device_cache_path, "w", encoding="utf-8") as fd:
                    #fd.write(jsonpickle.encode(cache))
            #cookie = cache["cookie"]
            self.session.headers.update({"cookie": cookie})
        else:
            self.session.headers.update(
                {
                    "Origin": "https://www.paramountplus.com",
                }
            )
            self.session.params.update({"at": self.config[self.region]["at_token"]})

        #if not self.is_logged_in():
            #raise ValueError("InvalidCookies")

        #if not self.is_subscribed():
            #raise ValueError("NotEntitled")

    # Service specific functions

    def get_prop(self, prop):
        res = self.session.get("https://www.paramountplus.com")
        prop_re = prop.replace(".", r"\.")
        search = re.search(rf"{prop_re} ?= ?[\"']?([^\"';]+)", res.text)
        if not search:
            raise ValueError("InvalidCookies")

        return search.group(1)

    def is_logged_in(self):
        return self.get_prop("CBS.UserAuthStatus") == "true"

    def is_subscribed(self):
        return self.get_prop("CBS.Registry.user.sub_status") == "SUBSCRIBER"
    
    def login(self, username, password):
        login_params = {
            "j_username": username,
            "j_password": password
        }

        response = self.session.post(url=self.config[self.region]["login"], params=login_params)

        status_response = self.session.get(url=self.config[self.region]["status"]).json()
        self.log.debug(status_response)
        if status_response["success"] == False:
            raise ValueError("InvalidCredentials")
        #if not status_response["userStatus"]["description"] == "SUBSCRIBER":
            #raise ValueError("NotEntitled")
        
        cookies = ";".join([f"{key}={value}" for key, value in response.cookies.get_dict().items()])

        return cookies
    
    def get_barrear(self, content_id):
        #license_data = self.session.get(url="https://www.intl.paramountplus.com/apps-api/v3.0/androidphone/irdeto-control/session-token.json?contentId=%s&locale=en-us&at=ABATOpD5wXyjhjIMO0BaNh/gW0iCu0ISRy2U7/tyGiKZTQTlYDFL1NPD58CcuJLOQYY=" % (content_id)).json()
        try:  
            res = self.session.get(url=self.config[self.region]["barrearUrl"], params={"contentId": content_id})
            res.raise_for_status()
        except requests.HTTPError as e:
            if e.response.status_code == 401:
                self.log.warning("Received a 401 error, deleting cached cookies")
                self.device_cache_path.unlink()
                self.session.headers.clear()
                self.session.params = {}
                self.configure()
                self.retrying = True
        
        res = res.json()

        if not res["success"]:
            raise self.log.exit("Unable to get license token: %s" % (res["errors"]))

        #license_url = license_data["url"]
        ls_session = res["ls_session"]

        return ls_session

    def parse_movie_year(self, url):
        html_raw = self.session.get(url)

        if html_raw.status_code != 200:
            return None

        self.year = int(
            re.findall('"movie__air-year">[0-9]+<', html_raw.text)[0].replace('"movie__air-year">', "").replace("<", "")
        )

    def parse_show_id(self, url):
        html_raw = self.session.get(url)

        if html_raw.status_code != 200:
            self.log.exit("Could not parse Show Id.")

        show = json.loads('{"' + re.search('CBS.Registry.Show = {"(.*)"}', html_raw.text).group(1) + '"}')

        return str(show["id"])

    def get_session(self):
        session = requests.Session()
        session.mount("https://", HTTPAdapter(
            max_retries=Retry(
                total=5,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
            )
        ))
        session.headers.update(config.headers)
        session.cookies.update(self.cookies or {})
        return session