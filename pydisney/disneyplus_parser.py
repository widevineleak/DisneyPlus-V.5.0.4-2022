import os, clipboard, uuid, requests, re, sys, pycountry
from pydisney.m3u8_formater import M3U8

languageCodes = {
	"zh-Hans": "zhoS",
	"zh-Hant": "zhoT",
	"pt-BR": "brPor",
	"es-ES": "euSpa",
	"en-GB": "enGB",
	"en-PH": "enPH",
	"nl-BE": "nlBE",
	"fil": "enPH",
	"yue": "zhoS",
	'fr-CA':'caFra'
}

class Parser(object):
	def __init__(self, m3u8, atmos_m3u8, is2ch=False):
		self.m3u8 = m3u8
		self.base = self.m3u8.rsplit('/', 1)[0] + '/'

		if atmos_m3u8 is not None:	
			self.isAtmos = True	
			self.atmos_m3u8 = atmos_m3u8
			self.atmos_base = self.atmos_m3u8.rsplit('/', 1)[0] + '/'
		else:
			self.isAtmos=False
		
		self.is2ch = is2ch

	def countrycode(self, code):
		if code == 'cmn-Hans':
			return 'Mandarin Chinese (Simplified)', 'zh-Hans'
		elif code == 'cmn-Hant':
			return 'Mandarin Chinese (Traditional)', 'zh-Hant'
		elif code == 'es-419':
			return 'Spanish', 'spa'
		elif code == 'es-ES':
			return 'European Spanish', 'euSpa'
		elif code == 'pt-BR':
			return 'Brazilian Portuguese', 'brPor'
		elif code == 'pt-PT':
			return 'Portuguese', 'por'
		elif code == 'fr-CA':
			return 'French Canadian', 'caFra'
		elif code == 'fr-FR':
			return 'French', 'fra'

		lang_code = code[:code.index('-')] if '-' in code else code
		lang = pycountry.languages.get(alpha_2=lang_code)
		if lang is None:
			lang = pycountry.languages.get(alpha_3=lang_code)

		try:
			languagecode = languageCodes[code]
		except KeyError:
			languagecode = lang.alpha_3

		return lang.name, languagecode

	def getCodec(self, codecs):
		if ishevc or ishdr or ishdrdv:
			search = 'hvc'
		else:
			search = 'avc'
		l = []
		for c in codecs.split(','):
			if search in c:
				l.append(c)

		return l[-1]

	def Parser(self):
		AudioCodecs = None
		AudioExtension = None
		AudioList = []
		subtitleList = []
		forcedlist = []
		videoList = []
		added = set()

		manifest_req = requests.get(self.m3u8)
		video_manifest = M3U8(manifest_req.text)

		if self.isAtmos:
			atmos_req = requests.get(self.atmos_m3u8)
			try:
				audio_manifest = M3U8(atmos_req.text)
				audio_base = self.atmos_base
				audio_text = atmos_req.text
			except ValueError:
				audio_manifest = video_manifest
				audio_base = self.base
				audio_text = manifest_req.text
		else:
			audio_manifest = video_manifest
			audio_base = self.base
			audio_text = manifest_req.text
				
		if self.isAtmos:
			if 'atmos' in str(audio_text):
				AudioCodecs = 'atmos'
				AudioExtension = '.eac3'
			else:
				print('this item has no atmos.')
				print('trying ac3 6ch...')
				if 'eac-3' in str(audio_text):
					AudioCodecs = 'eac-3'
					AudioExtension = '.eac3'
				else:
					print('this item has no ac3 6ch, trying aac 2ch')
					if 'aac-128k' in str(audio_text):
						AudioCodecs = 'aac-128k'
						AudioExtension = '.aac'                    
					else:
						sys.exit(1)
		
		else:
			if self.is2ch:
				if 'aac-128k' in str(audio_text):
					AudioCodecs = 'aac-128k'
					AudioExtension = '.aac'
				else:
					print('this item has no aac 2ch')
					sys.exit(1)
			else:
				if 'eac-3' in str(audio_text):
					AudioCodecs = 'eac-3'
					AudioExtension = '.eac3'
				else:
					print('this item has no ac3 6ch, trying aac 2ch')
					if 'aac-128k' in str(audio_text):
						AudioCodecs = 'aac-128k'
						AudioExtension = '.aac'
					else:
						print('this item has no aac 2ch')
						sys.exit(1)

		if AudioCodecs is None or AudioExtension is None:
			print('error while search for audio codec in m3u8 streams.')
			sys.exit(1)

		video_streams = [x for x in video_manifest.master_playlist if x['TAG'] == 'EXT-X-STREAM-INF']
		audio_streams = [x for x in audio_manifest.master_playlist if x['TAG'] == 'EXT-X-MEDIA']
		subs_streams = [x for x in video_manifest.master_playlist if x['TAG'] == 'EXT-X-MEDIA']

		for video in video_streams:
			if not video["URI"] in added:
				bitrate = 'None'
				if re.search('([0-9]*)k_', video["URI"]):
					bitrate = str(re.search('([0-9]*)k_', video["URI"])[1])
				else:
					if re.search('([0-9]*)_complete', video["URI"]):
						bitrate = str(re.search('([0-9]*)_complete', video["URI"])[1])

				videoList.append(
							{
								'resolution': video["RESOLUTION"],
								'codec': str(video["CODECS"]),
								'bandwidth': str(video["BANDWIDTH"]),
								'bitrate': bitrate,
								'height': video["RESOLUTION"].rsplit('x', 1)[1],
								'url': self.base+video["URI"]
							}
						)
				added.add(video["URI"])

		for m in audio_streams:
			if m['TYPE'] == 'AUDIO' and m['GROUP-ID'] == AudioCodecs and m.get('CHARACTERISTICS') is None:
				bitrate = 'None'
				if re.search('([0-9]*)k_', m["URI"]):
					bitrate = str(re.search('([0-9]*)k_', m["URI"])[1])
				else:
					if re.search('([0-9]*)_complete', m["URI"]):
						bitrate = str(re.search('([0-9]*)_complete', m["URI"])[1])

				bitrate = '768' if str(m['CHANNELS']) == '16/JOC' and int(bitrate) > 768 else bitrate
				language, code = self.countrycode(m['LANGUAGE'])
				
				Profile = m['GROUP-ID']
				Profile = "aac" if "aac" in m['GROUP-ID'].lower() else Profile
				Profile = "eac-3" if "eac-3" in m['GROUP-ID'].lower() else Profile
				Profile = "atmos" if "joc" in m['GROUP-ID'].lower() else Profile

				AudioList.append(
						{
							'language': str(language),
							'code': str(code),
							'bitrate': bitrate,
							'codec': Profile,
							'channels': str(m['CHANNELS'].replace('"', "").replace("/JOC", "")),
							'url': audio_base+m['URI']
						}
					)

		for m in subs_streams:                    
			if m['TYPE'] == 'SUBTITLES' and m['FORCED'] == 'NO':
				language, code = self.countrycode(m['LANGUAGE'])
				subtitleList.append(
						{
							'language': str(language),
							'code': str(code),
							'url': self.base+m['URI']
						}
					)

			if m['TYPE'] == 'SUBTITLES' and m['FORCED'] == 'NO' and m['LANGUAGE'] == 'en':
				language, code = self.countrycode(m['LANGUAGE'])
				subtitleList.append(
						{
							'language': str(language),
							'code': 'sdh-' + str(code),
							'url': self.base+m['URI']
						}
					)

			if m['TYPE'] == 'SUBTITLES' and m['FORCED'] == 'YES':
				language, code = self.countrycode(m['LANGUAGE'])
				forcedlist.append(
						{
							'language': str(language),
							'code': str(code),
							'url': self.base+m['URI']
						}
					)

		videoList = sorted(videoList, key=lambda k: int(k['bandwidth']))
		print(videoList)

		return videoList, AudioList, subtitleList, forcedlist, AudioExtension
			