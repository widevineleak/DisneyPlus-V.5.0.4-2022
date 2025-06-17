from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import time
import requests,json
import os
from datetime import datetime


import click
from click import Context

from vinetrimmer.objects import MenuTrack, Title, Tracks
from vinetrimmer.services.BaseService import BaseService


class Skyshowtime(BaseService):
    """
    Service code for NBC's Skyshowtime streaming service (https://skyshowtime.com).
    Edited L4M

    \b
    Authorization: Cookies
    Security: UHD@-- FHD@L3, doesn't care about releases.
    """

    ALIASES = ["SKST", "Skyshowtime"]
    #GEOFENCE = ["es"]

    VIDEO_RANGE_MAP = {
        "DV": "DOLBY_VISION"
    }

    AUDIO_CODEC_MAP = {
        "AAC": "mp4a",
        "AC3": "ac-3",
        "EC3": "ec-3"
    }
    
    @staticmethod
    @click.command(name="Skyshowtime", short_help="https://skyshowtime.com")
    @click.argument("title", type=str)
    @click.option("-m", "--movie", is_flag=True, default=False, help="Title is a Movie.")
    @click.pass_context
    def cli(ctx, **kwargs):
        return Skyshowtime(ctx, **kwargs)

    def __init__(self, ctx, title: str, movie: bool):
        self.title = title
        self.movie = movie
        super().__init__(ctx)

        self.profile = ctx.obj.profile

        self.range = ctx.parent.params["range_"]
        self.vcodec = ctx.parent.params["vcodec"]
        self.acodec = ctx.parent.params["acodec"]

        if (ctx.parent.params.get("quality") or 0) > 1080 and self.vcodec != "H265":
            self.log.info(" + Switched video codec to H265 to be able to get 2160p video track")
            self.vcodec = "H265"

        if self.range in ("HDR10", "DV") and self.vcodec != "H265":
            self.log.info(f" + Switched video codec to H265 to be able to get {self.range} dynamic range")
            self.vcodec = "H265"


        self.service_config = None
        self.hmac_key: bytes
        self.tokens: dict
        self.license_api = None
        self.license_bt = None

        self.configure()

    def get_titles(self):
        # Title is a slug, example: `/tv/the-office/4902514835143843112`.
        res = self.session.get(
            url=self.config["endpoints"]["node"],
            params={
                "slug": self.title,#'provider_series_id/'+self.title.split('/')[3],
                "represent": "(items(items))",
                # "represent": "(items(items),recs[take=8],collections(items(items[take=8])),trailers)"
            },
            headers={
                "Accept": "*",
                "Referer": f"https://www.skyshowtime.com/watch/asset{self.title}",
                "x-skyott-Activeterritory": self.session.cookies.get("activeTerritory"),
                "x-skyott-device": self.config["client"]["device"],
                "x-skyott-language": self.config["client"]["language"],
                "x-skyott-platform": self.config["client"]["platform"],
                "x-skyott-proposition": self.config["client"]["proposition"],
                "x-skyott-provider": self.config["client"]["provider"],
                "x-skyott-territory": self.session.cookies.get("activeTerritory")
            }
        )
        if not res.ok:
            self.log.exit(f" - HTTP Error {res.status_code}: {res.reason}")
            raise
        data = res.json()

        titles = []
        if "relationships" in data:
            for season in data["relationships"]["items"]["data"]:
                for episode in season["relationships"]["items"]["data"]:
                    titles.append(episode)
        else:
            return [Title(
                id_=self.title,
                type_=Title.Types.MOVIE,
                name=data["attributes"]["title"],
                year=data["attributes"].get("year"),
                original_lang="en",  # TODO: Don't assume
                source=self.ALIASES[0],
                service_data=data
            )]
        return [Title(
            id_=self.title,
            type_=Title.Types.TV,
            name=data["attributes"]["title"],
            year=x["attributes"].get("year"),
            season=x["attributes"].get("seasonNumber"),
            episode=x["attributes"].get("episodeNumber"),
            episode_name=x["attributes"].get("title"),
            original_lang="en",  # TODO: Don't assume
            source=self.ALIASES[0],
            service_data=x
        ) for x in titles]

    def get_tracks(self, title: Title) -> Tracks:
        supported_colour_spaces=["SDR"]

        if self.range == "HDR10":
            self.log.info("Switched dynamic range to  HDR10")
            supported_colour_spaces=["HDR10"]
        if self.range == "DV":
            self.log.info("Switched dynamic range to  DV")
            supported_colour_spaces=["DolbyVision"]
        content_id = title.service_data["attributes"]["formats"]["HD"]["contentId"]
        variant_id = title.service_data["attributes"]["providerVariantId"]

        sky_headers = {
            # order of these matter!
            "x-skyott-Activeterritory": self.session.cookies.get("activeTerritory"),
            "x-skyott-agent": ".".join([
                self.config["client"]["proposition"].lower(),
                self.config["client"]["device"].lower(),
                self.config["client"]["platform"].lower()
            ]),
            # "x-skyott-coppa": "false",
            "x-skyott-device": self.config["client"]["device"],
            "x-skyott-language": self.config["client"]["language"],
            "x-skyott-platform": self.config["client"]["platform"],
            "x-skyott-proposition": self.config["client"]["proposition"],
            "x-skyott-provider": self.config["client"]["provider"],
            "x-skyott-territory": self.session.cookies.get("activeTerritory"),
            "x-skyott-usertoken": self.tokens["userToken"]
        }

        body = json.dumps({
        "contentId": content_id,
        "providerVariantId": variant_id,
        "device": {
            "capabilities": [
            {
                "transport": "DASH",
                "protection": "NONE",
                "vcodec": "H265",
                "acodec": "AAC",
                "container": "ISOBMFF"
            },
            {
                "transport": "DASH",
                "protection": "PLAYREADY",
                "vcodec": "H265",
                "acodec": "AAC",
                "container": "ISOBMFF"
            },
            {
                "transport": "DASH",
                "protection": "NONE",
                "vcodec": "H264",
                "acodec": "AAC",
                "container": "ISOBMFF"
            },
            {
                "transport": "DASH",
                "protection": "PLAYREADY",
                "vcodec": "H264",
                "acodec": "AAC",
                "container": "ISOBMFF"
            },
            
            ],
            "maxVideoFormat": "UHD" if self.vcodec == "H265" else "HD",
            "supportedColourSpaces": supported_colour_spaces,
            "hdcpEnabled": "true",
        },
        "client": {
            "thirdParties": [
            "COMSCORE",
            "CONVIVA",
            "FREEWHEEL"
            ]
        },
        "personaParentalControlRating": 9
        }, separators=(",", ":"))
        manifest = self.session.post(
            url=self.config["endpoints"]["vod"],
            data=body,
            headers=dict(**sky_headers, **{
                "accept": "application/vnd.playvod.v1+json",
                "content-type": "application/vnd.playvod.v1+json",
                "x-sky-signature": self.create_signature_header(
                    method="POST",
                    path="/video/playouts/vod",
                    sky_headers=sky_headers,
                    body=body,
                    timestamp=int(time.time())
                ),
            })
        ).json()

        if "errorCode" in manifest:
            self.log.exit(f" - An error occurred: {manifest['description']} [{manifest['errorCode']}]")
            raise

        self.license_api = manifest["protection"]["licenceAcquisitionUrl"]
        self.license_bt = manifest["protection"]["licenceToken"]

        tracks = Tracks.from_mpd(
            url=manifest["asset"]["endpoints"][0]["url"]+'&audio=all&subtitle=all',
            session=self.session,
            #lang=title.original_lang,
            source=self.ALIASES[0]
        )
        
        if supported_colour_spaces == ["HDR10"]:
            for track in tracks.videos:
                track.hdr10 = True if supported_colour_spaces == ["HDR10"] else False
        if supported_colour_spaces == ["DolbyVision"]:
            for track in tracks.videos:
                track.dolbyvison = True if supported_colour_spaces == ["DV"] else False

        for track in tracks:
            track.needs_proxy = True

        if self.acodec:
            tracks.audios = [
                x for x in tracks.audios
                if x.codec and x.codec[:4] == self.AUDIO_CODEC_MAP[self.acodec]
            ]

        return tracks

    def get_chapters(self, title: Title) -> list[MenuTrack]:
        return []

    def certificate(self, challenge, **_):
        return self.license(challenge)

    def license(self, challenge: bytes, **_) -> bytes:
        assert self.license_api is not None
        res = self.session.post(
            url=self.license_api,
            headers={
                "Accept": "*",
                "X-Sky-Signature": self.create_signature_header(
                    method="POST",
                    path="/" + self.license_api.split("://", 1)[1].split("/", 1)[1],
                    sky_headers={},
                    body="",
                    timestamp=int(time.time())
                )
            },
            data=challenge  # expects bytes
        ).content
        
        return base64.b64encode(res).decode()

    # Service specific functions
    def configure(self) -> None:
        self.session.headers.update({"Origin": "https://www.skyshowtime.com"})
        self.log.info("Getting Skyshowtime Client configuration")
        if self.config["client"]["platform"] != "PC":
            self.service_config = self.session.get(
                url=self.config["endpoints"]["config"].format(
                    territory=self.session.cookies.get("activeTerritory"),
                    provider=self.config["client"]["provider"],
                    proposition=self.config["client"]["proposition"],
                    platform=self.config["client"]["platform"],
                    version=self.config["client"]["version"]
                )
            ).json()
        self.hmac_key = bytes(self.config["security"]["signature_hmac_key_v4"], "utf-8")
        self.log.info("Getting Authorization Tokens")
        self.tokens = self.get_tokens()
        self.log.info("Verifying Authorization Tokens")
        #if not self.verify_tokens():
        #    self.log.info(" - Failed! Cookies might be outdated.")
        #     raise

    @staticmethod
    def calculate_sky_header_md5(headers: dict) -> str:
        if len(headers.items()) > 0:
            headers_str = "\n".join(list(map(lambda x: f"{x[0].lower()}: {x[1]}", headers.items()))) + "\n"
        else:
            headers_str = "{}"
        return str(hashlib.md5(headers_str.encode()).hexdigest())

    @staticmethod
    def calculate_body_md5(body: str) -> str:
        return str(hashlib.md5(body.encode()).hexdigest())

    def calculate_signature(self, msg: str) -> str:
        digest = hmac.new(self.hmac_key, bytes(msg, "utf-8"), hashlib.sha1).digest()
        return str(base64.b64encode(digest), "utf-8")

    def create_signature_header(self, method: str, path: str, sky_headers: dict, body: str, timestamp: int) -> str:
        data = "\n".join([
            method.upper(),
            path,
            "",  # important!
            self.config["client"]["client_sdk"],
            "1.0",
            self.calculate_sky_header_md5(sky_headers),
            str(timestamp),
            self.calculate_body_md5(body)
        ]) + "\n"

        signature_hmac = self.calculate_signature(data)

        return self.config["security"]["signature_format"].format(
            client=self.config["client"]["client_sdk"],
            signature=signature_hmac,
            timestamp=timestamp
        )

    def get_tokens(self):
        # Try to get cached tokens
        tokens_cache_path = self.get_cache("tokens_{profile}_{id}.json".format(
            profile=self.profile,
            id=self.config["client"]["id"]
        ))
        if os.path.isfile(tokens_cache_path):
            with open(tokens_cache_path, encoding="utf-8") as fd:
                tokens = json.load(fd)
            tokens_expiration = tokens.get("tokenExpiryTime", None)
            if tokens_expiration and datetime.strptime(tokens_expiration, "%Y-%m-%dT%H:%M:%S.%fZ") > datetime.now():
                return tokens

        # Get all SkyOTT headers
        sky_headers = {
            # order of these matter!
            "x-skyott-Activeterritory": self.session.cookies.get("activeTerritory"),
            "x-skyott-device": self.config["client"]["device"],
            "x-skyott-language": self.config["client"]["language"],
            "x-skyott-platform": self.config["client"]["platform"],
            "x-skyott-proposition": self.config["client"]["proposition"],
            "x-skyott-provider": self.config["client"]["provider"],
            "x-skyott-territory": self.session.cookies.get("activeTerritory")
        }

        # Craft the body data that will be sent to the tokens endpoint, being minified and order matters!
        body = json.dumps({
            "auth": {
                "authScheme": self.config["client"]["auth_scheme"],
                "authIssuer": self.config["client"]["auth_issuer"],
                "provider": self.config["client"]["provider"],
                "providerTerritory": self.session.cookies.get("activeTerritory"),
                "proposition": self.config["client"]["proposition"],
            },
            "device": {
                "type": self.config["client"]["device"],
                "platform": self.config["client"]["platform"],
                "id": self.config["client"]["id"],
                "drmDeviceId": self.config["client"]["drm_device_id"]
            }
        }, separators=(",", ":"))

        # Get the tokens
        tokens = self.session.post(
            url=self.config["endpoints"]["tokens"],
            headers=dict(**sky_headers, **{
                "Accept": "application/vnd.tokens.v1+json",
                "Content-Type": "application/vnd.tokens.v1+json",
                "X-Sky-Signature": self.create_signature_header(
                    method="POST",
                    path="/auth/tokens",
                    sky_headers=sky_headers,
                    body=body,
                    timestamp=int(time.time())
                )
            }),
            data=body
        ).json()

        os.makedirs(os.path.dirname(tokens_cache_path), exist_ok=True)
        with open(tokens_cache_path, "w", encoding="utf-8") as fd:
            json.dump(tokens, fd)

        return tokens

    def verify_tokens(self) -> bool:
        """Verify the tokens by calling the /auth/users/me endpoint and seeing if it works"""
        sky_headers = {
            # order of these matter!
            "x-skyott-Activeterritory": self.session.cookies.get("activeTerritory"),
            "x-skyott-device": self.config["client"]["device"],
            "x-skyott-platform": self.config["client"]["platform"],
            "x-skyott-proposition": self.config["client"]["proposition"],
            "x-skyott-provider": self.config["client"]["provider"],
            "x-skyott-territory": self.session.cookies.get("activeTerritory"),
            "x-skyott-usertoken": self.tokens["userToken"]
        }
        me = self.session.get(
            url=self.config["endpoints"]["me"],
            headers=dict(**sky_headers, **{
                "accept": "application/vnd.userinfo.v2+json",
                "content-type": "application/vnd.userinfo.v2+json",
                "x-sky-signature": self.create_signature_header(
                    method="GET",
                    path="/auth/users/me",
                    sky_headers=sky_headers,
                    body="",
                    timestamp=int(time.time())
                )
            })
        )

        return me.status_code == 200
