import base64
import itertools
import json
import os
import re
import requests
from enum import Enum
from urllib.parse import unquote
from click import Context
import click
import m3u8
from datetime import datetime
from vinetrimmer.objects import AudioTrack, TextTrack, Title, Tracks, VideoTrack, MenuTrack
from vinetrimmer.services.BaseService import BaseService
from vinetrimmer.vendor.pymp4.parser import Box
import plistlib

class iTunes(BaseService):
    """
    Service code for Apple's VOD streaming service (https://tv.apple.com).

    \b
    Authorization: Cookies
    Security: UHD@L1 FHD@L1 HD@L1 SD@L3
    """

    ALIASES = ["iT", "itunes"]
    TITLE_RE = r"^(?:https?://tv\.apple\.com(?:/[a-z]{2})?/(?:movie|show|episode)/[a-z0-9-]+/)?(?P<id>umc\.cmc\.[a-z0-9]+)"

    VIDEO_CODEC_MAP = {
        "H264": ["avc"],
        "H265": ["hvc", "hev", "dvh"]
    }
    AUDIO_CODEC_MAP = {
        "AAC": ["HE", "stereo"],
        "AC3": ["ac3"],
        "EC3": ["ec3", "atmos"]
    }

    @staticmethod
    @click.command(name="iTunes", short_help="https://itunes.apple.com")
    @click.argument("title", type=str, required=False)
    @click.option("-m", "--movie", is_flag=True, default=False, help="Title is a Movie.")
    @click.option("-ca", "--checkall", is_flag=True, default=False, help="Check all storefront manifests for additional audios and subs.")
    @click.option("-sf", "--storefront", type=int, default="143480", help="Define storefront int if needed.")
    @click.pass_context
    def cli(ctx, **kwargs):
        return iTunes(ctx, **kwargs)

    def __init__(self, ctx, title: str, movie, checkall, storefront: bool):
        super().__init__(ctx)
        self.parse_title(ctx, title)

        self.vcodec = ctx.parent.params["vcodec"]
        self.acodec = ctx.parent.params["acodec"]

        self.profile = ctx.obj.profile

        self.extra_server_parameters = None
        self.rental_id = None
        self.rentals_supported = False
        self.movie = movie
        self.checkall = checkall
        self.storefront = storefront

        self.configure()

    def get_titles(self):
        titles = []

        contentId = re.findall('(umc.[a-z0-9]*.[a-z0-9]*)', self.title)[0]
        self.params = {
            'utsk': '6e3013c6d6fae3c2::::::9318c17fb39d6b9c',
            'caller': 'web',
            'sf': self.storefront,
            'v': '46',
            'pfm': 'appletv',
            'mfr': 'Apple',
            'locale': 'en-US',
            'l': 'en',
            'ctx_brand': 'tvs.sbd.9001',
            'count': '100',
            'skip': '0',
        }

        if self.movie:
            res = self.session.get(
                url=f'https://tv.apple.com/api/uts/v2/view/product/{contentId}',
                params=self.params
            )
            information = res.json()['data']['content']
            titles.append(Title(
                id_=self.title,
                type_=Title.Types.MOVIE,
                name=information['title'],
                #year=datetime.fromtimestamp(information['releaseDate'] / 1000).strftime('%Y'),
                # TODO: Find a way to get year
                original_lang="en",  # TODO: Don't assume
                source=self.ALIASES[0],
                service_data=information
            ))
        else:
            res = self.session.get(
                url=f'https://tv.apple.com/api/uts/v2/view/show/{contentId}/episodes',
                params=self.params
            )
            episodes = res.json()["data"]["episodes"]
            for episode in episodes:
                titles.append(Title(
                    id_=self.title,
                    type_=Title.Types.TV,
                    name=episode["showTitle"],
                    season=episode["seasonNumber"],
                    episode=episode["episodeNumber"],
                    episode_name=episode.get("title"),
                    original_lang="en",  # TODO: Don't assume
                    source=self.ALIASES[0],
                    service_data=episode
                ))
        return titles

    def get_tracks(self, title: Title) -> Tracks:
        res = self.session.get(
            url=f'https://tv.apple.com/api/uts/v2/view/product/{title.service_data["id"]}/personalized',
            params={
                'utscf': 'OjAAAAAAAAA~',
                'utsk': '6e3013c6d6fae3c2::::::235656c069bb0efb',
                'caller': 'web',
                'sf': self.storefront,
                'v': '46',
                'pfm': 'web',
                'locale': 'en-US'
            }
        ).json()
        stream_data = res
        master_hls_url = stream_data['data']['content']['playables'][0]['itunesMediaApiData']['offers'][0][
            'hlsUrl'].replace("SD", "UHD").replace("HD", "UHD").replace("UUHD", "UHD")
        r = self.session.get(master_hls_url)
        if not r.ok:
            self.log.exit(f" - HTTP Error {r.status_code}: {r.reason}")
            raise

        master_hls_manifest = r.text
        master_playlist = m3u8.loads(master_hls_manifest, master_hls_url)
        if 'chapter' in master_hls_manifest:
            chapterLink = master_hls_manifest.rsplit('chapters.plist"', 1)[0].rsplit(',URI="', 1)[1] + 'chapters.plist'
            title.service_data['chapters'] = plistlib.loads(self.session.get(chapterLink).content)['chapters'][
                'chapter-list']
        try:
            self.rental_id = \
            stream_data['data']['content']['playables'][0]['itunesMediaApiData']['personalizedOffers'][0]['rentalId']
        except (IndexError, KeyError):
            self.rental_id = None

        tracks = Tracks.from_m3u8(
            master_playlist,
            #lang=title.original_lang,
            source=self.ALIASES[0]
        )
        
        # Function for grabbing additional audios from other storefronts
        if self.checkall:
            self.log.info(f"Checking extra storefronts")
            storefronts = ["143563","143564","143538","143540","143505","143524","143460","143445","143568","143559","143490","143541","143565","143446","143555","143542","143556","143525","143503","143543","143560","143526","143455","143544","143483","143465","143501","143495","143527","143494","143557","143489","143458","143545","143508","143509","143516","143506","143518","143447","143442","143443","143573","143448","143546","143504","143553","143510","143463","143482","143558","143467","143476","143449","143491","143450","143511","143462","143528","143517","143529","143466","143493","143519","143497","143522","143520","143451","143515","143530","143531","143473","143488","143532","143521","143533","143468","143523","143547","143484","143452","143461","143512","143534","143561","143457","143562","143477","143485","143513","143507","143474","143478","143453","143498","143487","143469","143479","143535","143500","143464","143496","143499","143472","143454","143486","143548","143549","143550","143554","143456","143459","143470","143572","143475","143539","143551","143536","143480","143552","143537","143444","143492","143481","143514","143441","143566","143502","143471","143571"]
            for extrastorefront in storefronts:
                self.log.info(f"Checking storefront: {extrastorefront}")
                try:
                    res = self.session.get(
                        url=f'https://tv.apple.com/api/uts/v2/view/product/{title.service_data["id"]}/personalized',
                        params={
                            'utscf': 'OjAAAAAAAAA~',
                            'utsk': '6e3013c6d6fae3c2::::::235656c069bb0efb',
                            'caller': 'web',
                            'sf': extrastorefront,
                            'v': '46',
                            'pfm': 'web',
                            'locale': 'pt-BR'
                        }
                    ).json()
                    
                    stream_data = res
                    master_hls_url = stream_data['data']['content']['playables'][0]['itunesMediaApiData']['offers'][0][
                        'hlsUrl'].replace("SD", "UHD").replace("HD", "UHD").replace("UUHD", "UHD")
                    r = self.session.get(master_hls_url)
                    if not r.ok:
                        continue

                    master_hls_manifest = r.text
                    master_playlist = m3u8.loads(master_hls_manifest, master_hls_url)
                    if 'chapter' in master_hls_manifest:
                        chapterLink = master_hls_manifest.rsplit('chapters.plist"', 1)[0].rsplit(',URI="', 1)[1] + 'chapters.plist'
                        title.service_data['chapters'] = plistlib.loads(self.session.get(chapterLink).content)['chapters'][
                            'chapter-list']
                    try:
                        self.rental_id = \
                        stream_data['data']['content']['playables'][0]['itunesMediaApiData']['personalizedOffers'][0]['rentalId']
                    except (IndexError, KeyError):
                        self.rental_id = None

                    extratracks = Tracks.from_m3u8(
                        master_playlist,
                        #lang=title.original_lang,
                        source=self.ALIASES[0]
                    )
                    for extratrack in extratracks:
                        if isinstance(extratrack, AudioTrack) or isinstance(extratrack, TextTrack):
                            tracks.add(extratrack)
                except: continue
        for track in tracks:
            if isinstance(track, AudioTrack):
                listel = track.extra.uri.split("/")
                for i in listel:
                    if 'gr' in i:
                        list2 = i.split("_")
                        for j in list2:
                            if 'gr' in j:
                                if "." in j:
                                    b1 = (j.split(".")[0][2:])
                                    bitrate = int(re.findall("\d+", b1)[0])
                                    # print(bitrate)
                                else:
                                    b1 = (j[2:])
                                    bitrate = int(re.findall("\d+", b1)[0])
                                    # print(bitrate)
                if bitrate:
                    track.bitrate = bitrate * 1000  # e.g. 128->128,000, 2448->448,000
                else:
                    # continue
                    raise ValueError(f"Unable to get a bitrate value for Track {track.id}")
                track.codec = track.codec.replace("_ak", "").replace("_ap3", "").replace("_vod", "")
                track.encrypted = True
            if isinstance(track, VideoTrack):
                track.encrypted = True
            if isinstance(track, TextTrack):
                track.codec = "vtt"

        tracks.videos = [
            x for x in tracks.videos
            if x.codec[:3] in self.VIDEO_CODEC_MAP[self.vcodec]
        ]

        if self.acodec:
            tracks.audios = [
                x for x in tracks.audios
                if x.codec.split("-")[0] in self.AUDIO_CODEC_MAP[self.acodec]
            ]

        sdh_tracks = [x.language for x in tracks.subtitles if x.sdh]
        tracks.subtitles = [x for x in tracks.subtitles if x.language not in sdh_tracks or x.sdh]

        return Tracks([
            # multiple CDNs, only want one
            x for x in tracks if "ak-amt" in x.url or x.url == ""
        ])

    def get_chapters(self, title):
        try:
            chapterData = title.service_data["chapters"]
            chapters: list[MenuTrack] = []
            for chapter in chapterData:
                chapters.append(MenuTrack(
                    number=len(chapters) + 1,
                    title=f"Chapter {len(chapters) + 1}",
                    timecode=datetime.utcfromtimestamp(float(chapter['start'])).strftime("%H:%M:%S.%f")[:-3]
                ))
            return chapters
        except KeyError:
            return []

    def certificate(self, **_):
        return None  # will use common privacy cert

    def license(self, challenge, track, **_):
        data = {
            "streaming-request": {
                "version": 1,
                "streaming-keys": [
                    {
                        "id": 1,
                        "uri": f"data:text/plain;charset=UTF-16;base64,{track.pssh}",
                        "challenge": base64.b64encode(challenge.encode('utf-8')).decode('utf-8'),
                        "key-system": "com.microsoft.playready",
                        "lease-action": "start",
                    }
                ]
            }
        }

        if self.rental_id:
            data["streaming-request"]["streaming-keys"][0]["rental-id"] = self.rental_id

        res = self.session.post(
            url=self.config["endpoints"]["license"],
            json=data
        ).json()
        status = res["streaming-response"]["streaming-keys"][0]["status"]
        if status != ResponseCode.OK.value:
            self.log.debug(res)
            try:
                desc = ResponseCode(status).name
            except ValueError:
                desc = "UNKNOWN"
            raise self.log.exit(f" - License request failed. Error: {status} ({desc})")
        return res["streaming-response"]["streaming-keys"][0]["license"]

    # Service specific functions

    def configure(self):
        #if not re.match(r"https?://(?:geo\.)?itunes\.apple\.com/", self.title):
         #   raise ValueError("Url must be an iTunes URL...")

        environment = self.get_environment_config()
        if not environment:
            raise self.log.exit("Failed to get iTunes' WEB TV App Environment Configuration...")
        try:
            self.session.headers.update({
                "User-Agent": self.config["user_agent"],
                "Authorization": f"Bearer {environment['MEDIA_API']['token']}",
                "media-user-token": self.session.cookies.get_dict()["media-user-token"],
                "x-apple-music-user-token": self.session.cookies.get_dict()["media-user-token"]
            })
        except KeyError:
            raise self.log.exit(" - No media-user-token cookie found, cannot log in.")




    def get_environment_config(self):
        """Loads environment config data from WEB App's <meta> tag."""
        res = self.session.get("https://tv.apple.com").text
        env = re.search(r'web-tv-app/config/environment"[\s\S]*?content="([^"]+)', res)
        if not env:
            return None
        return json.loads(unquote(env[1]))


class ResponseCode(Enum):
    OK = 0
    INVALID_PSSH = -1001
    NOT_OWNED = -1002  # Title not owned in the requested quality
    INSUFFICIENT_SECURITY = -1021  # L1 required or the key used is revoked
