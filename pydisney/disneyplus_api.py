import uuid, requests, json


class DSNP(object):

	def __init__(self, DsnyID, Token, Type, Season=False, ishdr=False, isuhd=False, ishevc=False):

		self.uhd = isuhd
		self.hdr = ishdr
		self.hevc = ishevc

		self.isAmovie = True
		self.DsnyID = DsnyID
		self.contentTransactionId = uuid.uuid4()
		self.Token = Token

		if Type == 'show':
			self.isAmovie = False
			self.Season = Season

		self.api = {
			'DmcSeriesBundle': 'https://disney.content.edge.bamgrid.com/svc/content/DmcSeriesBundle/version/5.1/region/US/audience/false/maturity/1850/language/en/encodedSeriesId/{video_id}',

			'DmcEpisodes': 'https://disney.content.edge.bamgrid.com/svc/content/DmcEpisodes/version/5.1/region/US/audience/false/maturity/1850/language/en/seasonId/{season_id}/pageSize/30/page/1',

   			'DmcVideo': 'https://disney.content.edge.bamgrid.com/svc/content/DmcVideoBundle/version/5.1/region/US/audience/false/maturity/1850/language/en/encodedFamilyId/{family_id}',

			'LicenseServer': 'https://edge.bamgrid.com/widevine/v1/obtain-license',
			'manifest': 'https://us.edge.bamgrid.com/media/{mediaid}/scenarios/{scenarios}'
		}
		self.scenarios = {
			"default": "restricted-drm-ctr-sw",
			"default_hevc": "handset-drm-ctr-h265",
			"SD": "handset-drm-ctr",
			"HD": "tv-drm-ctr",
			"atmos": "tv-drm-ctr-h265-hdr10-atmos",
			"uhd_sdr": "tv-drm-ctr-h265-atmos",
			"uhd_hdr": "tv-drm-ctr-h265-hdr10-atmos",
			"uhd_dv": "tv-drm-ctr-h265-dovi-atmos",
		}

	def load_info_m3u8(self, mediaId, mediaFormat, quality, isAtmos=False):

		headers = {
			"accept": "application/vnd.media-service+json; version=2",
			"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/76.0.3809.132 Safari/537.36",
			"Sec-Fetch-Mode": "cors",
			"x-bamsdk-platform": "windows",
			"x-bamsdk-version": '3.10',
			"Origin": 'https://www.disneyplus.com',
			"authorization": self.Token
		}
		if isAtmos:
			atmosurl = self.api['manifest'].format(mediaid=mediaId, scenarios=self.scenarios['uhd_hdr'])
			resp = requests.get(atmosurl, headers=headers)

			if resp.status_code != 200:
				print('M3U8 - Error:' + str(resp.text))
				return False

			data = json.loads(resp.text)
			atmos_url = data['stream']['complete']

		if mediaFormat == 'SD':
			url = self.api['manifest'].format(mediaid=mediaId, scenarios=self.scenarios['SD'])

		else:
			if self.uhd:
				url = self.api['manifest'].format(mediaid=mediaId, scenarios=self.scenarios['uhd_sdr'])
			elif self.hdr:
				url = self.api['manifest'].format(mediaid=mediaId, scenarios=self.scenarios['uhd_hdr'])

			elif self.hevc:
				url = self.api['manifest'].format(mediaid=mediaId, scenarios=self.scenarios['uhd_sdr'])

			elif int(quality) == 720:
				url = self.api['manifest'].format(mediaid=mediaId, scenarios=self.scenarios['default'])

			elif int(quality) < 720:
				url = self.api['manifest'].format(mediaid=mediaId, scenarios=self.scenarios['SD'])

			elif int(quality) == 720 and self.hevc:
				url = self.api['manifest'].format(mediaid=mediaId, scenarios=self.scenarios['default_hevc'])

			else:
				url = self.api['manifest'].format(mediaid=mediaId, scenarios=self.scenarios['HD'])

		resp = requests.get(url=url, headers=headers)

		if resp.status_code != 200:
			print('M3U8 - Error:' + str(resp.text))
			return False

		data = json.loads(resp.text)
		m3u8_url = data['stream']['complete']

		if isAtmos:
			return m3u8_url, atmos_url

		return m3u8_url, None

	def load_playlist(self):

		headers = {
			"accept": "application/json",
			"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.82 Safari/537.36",
			"Sec-Fetch-Mode": "cors",
			"x-bamsdk-platform": "windows",
			"x-bamsdk-version": '3.10',
			"authorization": f'Bearer {self.Token}'
		}


		if self.isAmovie:
			url = self.api['DmcVideo'].format(family_id=self.DsnyID)
		else:
			url = self.api['DmcSeriesBundle'].format(video_id=self.DsnyID)


		resp = requests.get(url=url, headers=headers)

		if resp.status_code != 200:
			print('DATA - Error:' + str(resp.text))
			return False

		data = resp.json()

		if self.isAmovie:
			data_info = data['data']['DmcVideoBundle']['video']
			title = data_info['text']['title']['full']['program']['default']['content']
			description = data_info['text']['description']['medium']['program']['default']['content']
			js_data = {
				'Title': title,
				'Year': data_info['releases'][0]['releaseYear'],
				'Description': description,
				'mediaFormat': data_info['mediaMetadata']['format'],
				'id': {
					'contentId': data_info['contentId'],
					'mediaId': data_info['mediaMetadata']['mediaId']
					}
			}
			return js_data
		else:
			EpisodeList = []
			data_info = data['data']['DmcSeriesBundle']

			SeasonTitle = data_info['series']['text']['title']['full']['series']['default']['content']
			for season in data_info['seasons']['seasons']:
				if int(season['seasonSequenceNumber']) == int(self.Season):
					SeascontentId = season['seasonId']

			headers = {
			  "accept": "application/json",
			  "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/76.0.3809.132 Safari/537.36",
			  "Sec-Fetch-Mode": "cors",
			  "x-bamsdk-platform": "windows",
			  "x-bamsdk-version": '3.10',
			  "authorization": f'Bearer {self.Token}'
			}

			url = self.api['DmcEpisodes'].format(season_id=SeascontentId)

			resp = requests.get(url=url, headers=headers)

			if resp.status_code != 200:
				print('DATA - Error:' + str(resp.text))
				return False

			JS = resp.json()

			JS = JS['data']['DmcEpisodes']['videos']

			for eps in JS:
				EpisodesDict = {'contentId': eps['contentId'],
								'mediaId': eps['mediaMetadata']['mediaId'],
								'seasonNumber': eps['seasonSequenceNumber'],
								'episodeNumber': eps['episodeSequenceNumber'],
								'Title': SeasonTitle,
								'mediaFormat': eps['mediaMetadata']['format']}

				EpisodeList.append(EpisodesDict)

			return EpisodeList

		return
