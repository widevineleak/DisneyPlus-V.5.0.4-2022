from hashlib import md5
import xml.etree.ElementTree as ElementTREE

from vinetrimmer.objects import Track, Tracks, VideoTrack


def parse(url: str, source: str, session):
    tracks = Tracks()

    req = session.get(url=url)
    if not req.status_code == 200:
        raise ValueError("Unable to download ISM Manifest content")

    response = req.text

    root = ElementTREE.fromstring(response)
    pssh_element = root.find(".//ProtectionHeader")
    if pssh_element is not None:
        pssh_base64 = pssh_element.text.strip()

    all_stream_index = root.findall(".//StreamIndex")
    for adaptation_set in all_stream_index:
        content_type = adaptation_set.get("Type")
        if not content_type == "video":
            continue

        elements = adaptation_set.findall("QualityLevel")
        for element in elements:
            codec_private_data = element.get("CodecPrivateData")
            codec = element.get("FourCC")
            bitrate = element.get("Bitrate")
            width = element.get("MaxWidth")
            height = element.get("MaxHeight")

            tracks.add(
                VideoTrack(
                    id_=md5(
                        str(codec_private_data + bitrate + codec).encode()
                    ).hexdigest(),
                    source=source,
                    url=url,
                    # metadata
                    codec=codec,
                    bitrate=bitrate,
                    width=width,
                    height=height,
                    fps=None,
                    hdr10=False,
                    hlg=False,
                    dv=False,
                    # switches/options
                    descriptor=Track.Descriptor.ISM,
                    # decryption
                    needs_repack=True,
                    encrypted=True,
                    pssh=pssh_base64,
                    # extra
                    extra=(url,),
                )
            )

    return tracks
