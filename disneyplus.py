import subprocess, ffmpy, pycountry, unidecode, shutil, re, requests, json, os, argparse, time, sys, base64, configparser, glob, pycaption, m3u8
from collections import OrderedDict
from natsort import natsorted
from titlecase import titlecase
from pydisney.disneyplus_api import DSNP
from pydisney.disneyplus_parser import Parser
from pydisney.m3u8_formater import M3U8
from pydisney.disneyplus_login import LOGIN
from pydisney.disneyplus_muxer import Muxer
import pydisney.namehelper as namer 
from pywidevine.decrypt.wvdecrypt import WvDecrypt

parser = argparse.ArgumentParser(description='>>> DISNEY+ <<<')
parser.add_argument("--url", dest="disneyurl", help="If set, The DSNP viewable URL.")
parser.add_argument('-q', action="store", dest='customquality', help="For configure quality of video.", default=0)
parser.add_argument("--atmos", dest="atmos", help="If set, return atmos audio manifest", action="store_true")
parser.add_argument("--only-2ch-audio", dest="only_2ch_audio", help="If set, to force get only eac3 2.0 Ch audios.", action="store_true")
parser.add_argument("--hevc", dest="hevc", help="If set, return hevc video manifest", action="store_true")
parser.add_argument("--hdr", dest="hdr", help="If set, return uhd_hdr video manifest", action="store_true")
parser.add_argument("--uhd", dest="uhd", help="If set, return uhd video manifest", action="store_true")
parser.add_argument('--default-audio-mux', action='store', dest='default_audio_mux', help='set default audio language mux, default value is eng.', default=0)
parser.add_argument('--default-sub-mux', action='store', dest='default_sub_mux', help='set default sub language mux, default value is eng.', default=0)
parser.add_argument("--all-season", dest="all_season", help="If set, season pack download.", action="store_true")
parser.add_argument("-e", "--episode", dest="episode", help="If set, it will start downloading the season from that episode.")
parser.add_argument("-s", dest="season", help="If set, it will start downloading the from that season.")
parser.add_argument("-o", "--output", dest="outputfolder", help="If set, it will download all assets to directory provided.")
parser.add_argument("--alang", "--audio-language", dest="audiolang", nargs="*", help="If set, download only selected audio languages", default=[])
parser.add_argument("--slang", "--subtitle-language", dest="sublang", nargs="*", help="If set, download only selected subtitle languages", default=[])
parser.add_argument("--flang", "--forced-language", dest="forcedlang", nargs="*", help="If set, download only selected forced subtitle languages", default=[])
parser.add_argument("--license", dest="license", help="If set, print keys and exit.", action="store_true")
parser.add_argument("--nv", "--no-video", dest="novideo", help="If set, don't download video", action="store_true")
parser.add_argument("--na", "--no-audio", dest="noaudio", help="If set, don't download audio", action="store_true")
parser.add_argument("--ns", "--no-subs", dest="nosubs", help="If set, don't download subs", action="store_true")
parser.add_argument("--keep", dest="keep", help="If set, well keep all files after mux, by default all erased.", action="store_true")
parser.add_argument("--group", "--gr", dest="group", help="Tag.", action="store")
parser.add_argument("--txtkeys", dest="txtkeys", help="If set, read keys from txt.", action="store_true")
args = parser.parse_args()

Config = configparser.ConfigParser(interpolation=None)

currentFile = 'Disney+'
realPath = os.path.realpath(currentFile)
dirPath = os.path.dirname(realPath)
dirName = os.path.basename(dirPath)
mp4decryptexe = dirPath + "/bin/mp4decrypt.exe"
mkvmergeexe = dirPath + "/bin/mkvmerge.exe"
aria2cexe = dirPath + "/bin/aria2c.exe"
ffmpegpath =  dirPath + '/bin/ffmpeg.exe'
SubtitleEditexe = dirPath + '/bin/SE363/SubtitleEdit.exe'
mp4dumptexe = dirPath + '/bin/mp4dump.exe'
KEYS_Folder = dirPath + '/KEYS'
KEYS_Text = dirPath + '/KEYS/KEYS.txt'
token_file = dirPath + "/token.ini"
DsnpCFG = dirPath + "/dsnp.cfg"

proxy_user = {
	'proxy': '---',
	'email': '---',
	'passwd': '---'
}

proxies = {
	"http": "http://{email}:{passwd}@{proxy}".format(
		email=proxy_user['email'],
		passwd=proxy_user['passwd'],
		proxy=proxy_user['proxy']
	),
	"https": "http://{email}:{passwd}@{proxy}".format(
		email=proxy_user['email'],
		passwd=proxy_user['passwd'],
		proxy=proxy_user['proxy']
	)
}

if os.path.exists(DsnpCFG):
	Config.read(DsnpCFG)
	DSNP_EMAIL = Config.get("config", "email")
	DSNP_PASS = Config.get("config", "pass")
else:
	print("\ndsnp.cfg File is missing.")
	sys.exit()

global account_info
account_info = {
	'email': DSNP_EMAIL,
	'pass': DSNP_PASS
}

def load(m3u8):
	is2ch=False	
	m3u8_main = m3u8[0].replace('/mickey/', '/')
	atmos_m3u8 = m3u8[1]
	load_manifest = Parser(m3u8_main, atmos_m3u8, is2ch=is2ch)
	videoList, AudioList, subtitleList, forcedlist, AudioExtension = load_manifest.Parser()

	return videoList, AudioList, subtitleList, forcedlist, AudioExtension

def get_pssh(url):
	widevine_pssh = None
	m3u8_obj = m3u8.load(url)

	for key in m3u8_obj.keys:
		if key is not None and key.keyformat == "urn:uuid:edef8ba9-79d6-4ace-a3c8-27dcd51d21ed":
			widevine_pssh = key.uri

	if widevine_pssh is not None:
		widevine_pssh = widevine_pssh.partition('base64,')[2]

		return widevine_pssh

	return False

def find_str(s, char):
	index = 0
	if char in s:
		c = char[0]
		for ch in s:
			if ch == c:
				if s[index:index + len(char)] == char:
					pass
				return index
			index += 1

	return -1

def getKeyId(mp4_file):
	KID_dict = {}
	KID_list = []
	data = subprocess.check_output([mp4dumptexe, '--format', 'json', '--verbosity', '1', mp4_file])
	mp4dump = json.loads(data)
	for atom in mp4dump:
		if atom['name'] == 'moov':
			for children in atom['children']:
				if children['name'] == 'trak':
					for trak in children['children']:
						if trak['name'] == 'mdia':
							for mdia in trak['children']:
								if mdia['name'] == 'minf':
									for minf in mdia['children']:
										if minf['name'] == 'stbl':
											for stbl in minf['children']:
												if stbl['name'] == 'stsd':
													for stsd in stbl['children']:
														if stsd['name'] == 'encv':
															for encv in stsd['children']:
																if encv['name'] == 'sinf':
																	for sinf in encv['children']:
																		if sinf['name'] == 'schi':
																			for schi in sinf['children']:
																				default_KID = schi['default_KID'].replace(' ', '').replace('[', '').replace(']', '').lower()
																				KID_upper = default_KID.upper()
																				KID_upper = KID_upper[0:8] + '-' + KID_upper[8:12] + '-' + KID_upper[12:16] + '-' + KID_upper[16:20] + '-' + KID_upper[20:32]
																				KID_dict = {'name':schi['name'], 
																				 'default_KID':default_KID, 
																				 'KID_alt':KID_upper}
																				KID_list.append(KID_dict)

	if KID_list:
		KID = KID_list[-1]['default_KID']
		KID_alt = KID_list[-1]['KID_alt']
	else:
		KID = 'nothing'
		KID_alt = 'nothing'
	print(KID)
	return (KID)

def generate_token():
	print('\nGenerate token...')
	LOG = LOGIN(email=account_info['email'], password=account_info['pass'], proxies={})
	TOKEN, EXPIRE = LOG.GetAuthToken()
	print("Done!")

	return TOKEN, EXPIRE

def save_token(token, expire_in):
	print('\nSaving token...')
	current_time = int(time.time())
	expire_date = current_time + expire_in

	token_dump = {'token': token, 'expire_date': str(expire_date)}

	if os.path.exists(token_file):
		os.remove(token_file)

	with open(token_file, 'w') as tok:
		tok.write(json.dumps(token_dump))

	print("Done!")

	return 

def load_token_file():
	print('\nLoading token...')
	if not os.path.exists(token_file):
		print(f'Error!: token file not found.')
		return False
	else:
		current_time = int(time.time())

		with open(token_file, 'r') as tok:
			token = json.loads(tok.read())

		token_time = int(token['expire_date'])
		token_less_10min = token_time - 600

		#~ check if token expired.
		if current_time > token_time:
			print('Error: token is expired.')
			return False
		#~ check if token will be expired within 10 minutes.
		elif current_time > token_less_10min:
			print('Warning: token will be expired within 10 min.')
			return False
		else:
			try:
				print('Done: expire in: ' + str(int((int(token['expire_date']) - int(time.time())) / 60)) + ' min')
			except Exception:
				pass
			Token = token['token']

	return Token

def do_decrypt(pssh):
	wvdecrypt = WvDecrypt(pssh)
	challenge = wvdecrypt.get_challenge()
	resp = requests.post(
		url='https://global.edge.bamgrid.com/widevine/v1/obtain-license',
		headers={
			'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3865.75 Safari/537.36',
			'Authorization': f'Bearer {AuthorizationToken}'
		},
		data=challenge
	)
	license_b64 = base64.b64encode(resp.content)
	wvdecrypt.update_license(license_b64)
	keys = wvdecrypt.start_process()

	return keys

def ReplaceDontLikeWord(X):
	try:    
		X = X.replace(" : ", " - ").replace(": ", " - ").replace(":", " - ").replace("&", "and").replace("+", "").replace(";", "").replace("ÃƒÂ³", "o").\
			replace("[", "").replace("'", "").replace("]", "").replace("/", "").replace("//", "").\
			replace("’", "'").replace("*", "x").replace("<", "").replace(">", "").replace("|", "").\
			replace("~", "").replace("#", "").replace("%", "").replace("{", "").replace("}", "").replace(",","").\
			replace("?","").encode('latin-1').decode('latin-1')
	except Exception:
		X = X.decode('utf-8').replace(" : ", " - ").replace(": ", " - ").replace(":", " - ").replace("&", "and").replace("+", "").replace(";", "").\
			replace("ÃƒÂ³", "o").replace("[", "").replace("'", "").replace("]", "").replace("/", "").\
			replace("//", "").replace("’", "'").replace("*", "x").replace("<", "").replace(">", "").replace(",","").\
			replace("|", "").replace("~", "").replace("#", "").replace("%", "").replace("{", "").replace("}", "").\
			replace("?","").encode('latin-1').decode('latin-1')
	
	return titlecase(X)

def FixShowName(name):
	x = name
	try:
		try:
			x = ReplaceDontLikeWord(unidecode.unidecode(name))
		except Exception:
			x = ReplaceDontLikeWord(name)
	except Exception:
		pass

	return x

def FixSeq(seq):
	if int(len(str(seq))) == 1:
		return f'0{str(seq)}'

	return str(seq)

def StripInputInt(inputint):
	x = inputint
	if int(x[0]) == 0:
		stripped_x = x[1:]
	else:
		stripped_x = x
	return str(stripped_x)

def do_clean(CurrentName):
	try:    
		os.system('if exist "' + CurrentName + '*.mp4" (del /q /f "' + CurrentName + '*.mp4")')
		os.system('if exist "' + CurrentName + '*.h265" (del /q /f "' + CurrentName + '*.h265")')
		os.system('if exist "' + CurrentName + '*.h264" (del /q /f "' + CurrentName + '*.h264")')
		os.system('if exist "' + CurrentName + '*.eac3" (del /q /f "' + CurrentName + '*.eac3")')
		os.system('if exist "' + CurrentName + '*.m4a" (del /q /f "' + CurrentName + '*.m4a")')
		os.system('if exist "' + CurrentName + '*.ac3" (del /q /f "' + CurrentName + '*.ac3")')
		os.system('if exist "' + CurrentName + '*.srt" (del /q /f "' + CurrentName + '*.srt")')
		os.system('if exist "' + CurrentName + '*.vtt" (del /q /f "' + CurrentName + '*.vtt")')
		os.system('if exist "' + CurrentName + '*.txt" (del /q /f "' + CurrentName + '*.txt")')
		os.system('if exist "' + CurrentName + '*.aac" (del /q /f "' + CurrentName + '*.aac")')
		os.system('if exist "' + CurrentName + '*.m3u8" (del /q /f "' + CurrentName + '*.m3u8")')
	except Exception:
		pass

	return 

def PRINT(videoList, AudioList, subtitleList):
	try:
		print('\nVIDEO')
		for i in videoList:
			print('VIDEO' + ' - Bitrate: ' + i['bitrate'] + 'kbps | Codec: ' + i['codec'] + ' | Resolution: ' + i['resolution'])
		print('\nAUDIO')
		for i in AudioList:
			print('AUDIO' + ' - Bitrate: ' + i['bitrate'] + 'kbps | Codec: ' + i['codec'] + ' | Channels: ' + i['channels'] + ' | Language: ' + i['language'])
		print('\nSUBS')
		for s in subtitleList:
			code = s['code']
			lang = s['language']
			print(f'SUBS - Language: {lang} | ISO 639-2: {code}')
	except Exception:
		pass

	return

def demux(inputName, outputName, inpType):

	if ishevc or ishdr or isuhd and inpType == 'video':
		os.rename(inputName, outputName)
		return

	ff = ffmpy.FFmpeg(
		executable=ffmpegpath,
		inputs={inputName: None},
		outputs={outputName: '-c copy'},
		global_options="-y -hide_banner -loglevel warning"
		)

	ff.run()
	time.sleep (50.0/1000.0)
	
	return True

def build_commandline_list(KEYS):
	keycommand = []
	keycommand.append('--key')
	keycommand.append(KEYS)

	return keycommand

def decryptmedia(KEYS, inputName, outputName):
	cmd_dec = [mp4decryptexe.replace('\\', '/')]
	cmd_keys = build_commandline_list(KEYS)
	cmd = cmd_dec + cmd_keys
	cmd.append(inputName)
	cmd.append(outputName)

	wvdecrypt_process = subprocess.Popen(cmd)
	stdoutdata, stderrdata = wvdecrypt_process.communicate()
	wvdecrypt_process.wait()

	return True

def vtt2srt(vtt, srt):
	with open(vtt, "r", encoding="utf8") as f: subs = f.read()
	text = pycaption.SRTWriter().write(pycaption.WebVTTReader().read(subs))
	with open(srt, "w", encoding="utf8") as f: f.write(text)

	return 

def updt(total, progress, textname):
	barLength, status = 20, ""
	progress = float(progress) / float(total)
	if progress >= 1.:
		progress, status = 1, "\r\n"
	block = int(round(barLength * progress))
	text = "\rMerging: {} [{}] {:.0f}% {}".format(
		textname, "#" * block + "-" * (barLength - block), round(progress * 100, 0),
		status)
	sys.stdout.write(text)
	sys.stdout.flush()

def downloadsubs(url, output):
	print("Downloading %s" % output)
	baseurl = url.rsplit('/', 1)[0] + '/'
	manifest = requests.get(url).text
	segments = re.findall('^(?!#).*',manifest,re.MULTILINE)
	segments = list(dict.fromkeys(segments))
	segments = [baseurl+x for x in segments]
	if 'MAIN' in manifest:
		segments = [x for x in segments if 'MAIN' in x]
	
	temp_vtt = output.replace('.srt', '.vtt')

	open_vtt = open(temp_vtt , "wb")
	for url in segments:
		response = requests.get(url)
		open_vtt.write(response.content)
	open_vtt.close()

	if 'sdh' in temp_vtt:
		vtt2srt(temp_vtt, output)
		if os.path.isfile(temp_vtt) and os.path.isfile(output):
			os.remove(temp_vtt)
	else:
		vtt2srt(temp_vtt, temp_vtt)

	return

def download(url, output):

	txturls = output + '_links_.txt'
	baseurl = url.rsplit('/', 1)[0] + '/'
	manifest = requests.get(url).text
	dict_m3u8 = M3U8(manifest)
	media_segment = dict_m3u8.media_segment
	segments = []
	frags_path = []

	if 'MAIN' in manifest:
		for seg in media_segment:
			if seg.get('EXT-X-MAP') is not None and 'MAIN' in seg.get('EXT-X-MAP').get('URI'):
				segments.append(baseurl+seg.get('EXT-X-MAP').get('URI'))
				segments.append(baseurl+seg.get('URI'))
			if seg.get('EXT-X-MAP') is None and 'MAIN' in seg.get('URI'):
				segments.append(baseurl+seg.get('URI'))
	else:
		for seg in media_segment:
			if seg.get('EXT-X-MAP') is not None:
				segments.append(baseurl+seg.get('EXT-X-MAP').get('URI'))
				segments.append(baseurl+seg.get('URI'))
			if seg.get('EXT-X-MAP') is None:
				segments.append(baseurl+seg.get('URI'))

	if segments == []:
		print('no segments found!!!!')
		return

	segments = list(dict.fromkeys(segments))
	txt = open(txturls,"w+")
	for i, s in enumerate(segments):
		name = "0" + str(i) + '.mp4'
		frags_path.append(name)
		txt.write(s + f"\n out={name}\n")
	txt.close()

	aria2c_command = [
				aria2cexe,
				f'--input-file={txturls}',
				'-x16',
				'-j16',
				'-s16',
				'--summary-interval=0',
				'--retry-wait=3',
				'--max-tries=10',
				'--enable-color=false',
				'--download-result=hide',
				'--console-log-level=error'
	]

	subprocess.run(aria2c_command)
	print('Done!\n')

	runs = int(len(frags_path))
	openfile = open(output ,"wb")
	for run_num, fragment in enumerate(frags_path):
		if os.path.isfile(fragment):
			shutil.copyfileobj(open(fragment,"rb"),openfile)
		os.remove(fragment)
		updt(runs, run_num + 1, output)
	openfile.close()
	#os.remove(txturls)
	print('Done!')

	return

def subtitleformatter(name):
	subs = glob.glob(name + "*.vtt")
	if subs != []:
		subprocess.call([SubtitleEditexe, "/convert", name + '*.vtt', "srt", "/removetextforhi", "/fixcommonerrors", "/overwrite"])

	for s in subs:
		if os.path.isfile(s):
			os.remove(s)

	return 

def main(episodename, seasonfolder, m3u8Url, SHOW=True):

	print("\nParsing M3U8...")
	videoList, AudioList, subtitleList, forcedlist, AudioExtension = load(m3u8Url)
	print("Done!")

	print(f"\n{episodename}")
	PRINT(videoList, AudioList, subtitleList+forcedlist)

	if not args.license:
		if args.customquality:
			height = args.customquality
			quality_available = [int(x['height']) for x in videoList]
			quality_available = list(OrderedDict.fromkeys(quality_available))
			if not int(height) in quality_available:
				print(f'This quality is not available, the available ones are: ' + ', '.join(str(x) for x in quality_available) + '.')
				height = input('Enter a correct quality (without p): ').strip()

			videoList = [x for x in videoList if int(x['height']) == int(height)]
			videoList = videoList[-1]
		else:
			videoList = videoList[-1]
	else:
		videoList = videoList[-1]

	# --
	keys_requested = False
	pssh = get_pssh(videoList['url'])

	if args.license:
		print ("\nGetting KEYS...")
		KEYS = []
		try:
			KEYS = do_decrypt(pssh)
		except Exception as e:
			print(str(e))
			pass
		if KEYS == []:
			print("Error!")
		else:
			keys_requested = True
			print("Done!")
		print('\n'.join(KEYS))
	
		return True

	# --

	CurrentHeigh = str(videoList["height"])

	if args.hevc:
		inputVideo = episodename + " [" + CurrentHeigh + "p] [HEVC].mp4"
		inputVideo_decrypted = episodename + ' [' + CurrentHeigh + 'p] [HEVC]_dec.mp4'
		inputVideo_demuxed = episodename + ' [' + CurrentHeigh + 'p] [HEVC].h265'
		MKVOUT1 = episodename + '.mkv' 
		MKVOUT2 = str(seasonfolder) + '\\' + episodename + '.mkv'
	elif args.hdr:
		inputVideo = episodename + " [" + CurrentHeigh + "p] [HDR].mp4"
		inputVideo_decrypted = episodename + ' [' + CurrentHeigh + 'p] [HDR]_dec.mp4'
		inputVideo_demuxed = episodename + ' [' + CurrentHeigh + 'p] [HDR].h265'
		MKVOUT1 = episodename + '.mkv' 
		MKVOUT2 = str(seasonfolder) + '\\' + episodename + '.mkv'                 
	else:
		inputVideo = episodename + " [" + CurrentHeigh + "p].mp4"
		inputVideo_decrypted = episodename + ' [' + CurrentHeigh + 'p]_dec.mp4'
		inputVideo_demuxed = episodename + ' [' + CurrentHeigh + 'p].h264'
		MKVOUT1 = episodename + '.mkv' 
		MKVOUT2 = str(seasonfolder) + '\\' + episodename + '.mkv'        

	if not args.noaudio or not args.novideo:

		KEYS = []
		if args.txtkeys:
			print()
			print('Getting KEYS from txt...')
			with open(KEYS_Text, 'r') as (keys_file):
				for line in keys_file.readlines():
					line = line.split('\n')[0]
					if ':' in line:
						KEYS.append(line)
		
		if KEYS == []:
			print()
			print("Getting KEYS from license server...")
			try:
				KEYS = do_decrypt(pssh=pssh)
				SAVELIST = ['\n'] + [episodename] + ['\n'] + KEYS + ['\n']
				with open(KEYS_Text, "a", encoding="utf8") as file:
					for KEY in SAVELIST:
						file.write(KEY)                
			except Exception as e:
				print(str(e))
				pass

		if KEYS == []:
			print("Error!")
		else:
			keys_requested = True
			print("Done!")

	if os.path.isfile(MKVOUT1) or os.path.isfile(MKVOUT2):
		print("\nFile '" + str(MKVOUT1) + "' already exists.")
		return

	# DOWNLOAD VIDEO

	if not args.novideo:
		if not os.path.isfile(inputVideo) and not os.path.isfile(inputVideo_decrypted) and not os.path.isfile(inputVideo_demuxed):
			print ("\nDownloading video...")
			download(url=videoList['url'], output=inputVideo)
		else:
			print("\n" + inputVideo + "\ndownloaded previously.")

	# DOWNLOAD AUDIO

	if not args.noaudio:
		print ("\nDownloading audio...")
		if args.audiolang:
			for aud in AudioList:
				if aud['code'] in args.audiolang:
					AudioEnc = episodename + ' ' + aud['code'] + '.mp4'
					AudioDem = episodename + ' ' + aud['code'] + AudioExtension

					print ("\n" + str(aud['language']) + ' - audio')

					if not os.path.isfile(AudioDem):
						if not os.path.isfile(AudioEnc):
							download(url=aud['url'], output=AudioEnc)
					else:
						print(AudioEnc + "\ndownloaded previously.")
		else:
			for aud in AudioList:
				AudioEnc = episodename + ' ' + aud['code'] + '.mp4'
				AudioDem = episodename + ' ' + aud['code'] + AudioExtension

				print ("\n" + str(aud['language']) + ' - audio')

				if not os.path.isfile(AudioDem):
					if not os.path.isfile(AudioEnc):
						download(url=aud['url'], output=AudioEnc)
				else:
					print(AudioEnc + "\ndownloaded previously.")

	if keys_requested:

		# DECRYPT VIDEO

		if os.path.isfile(inputVideo) and not os.path.isfile(inputVideo_decrypted) and not os.path.isfile(inputVideo_demuxed):
			kid = getKeyId(inputVideo)
			for key in KEYS:
				if kid == key.split(':')[0]:
					KEYS=key
			if KEYS == '':
				print('please put vaild keys in txt.')
				sys.exit(0)
			print("\nDecrypt video...")
			decryptmedia(KEYS, inputVideo, inputVideo_decrypted)
			print("Done!")

		# DEMUX VIDEO

		if os.path.isfile(inputVideo_decrypted) and not os.path.isfile(inputVideo_demuxed):
			print("\nRemuxing video...")
			demux(inputVideo_decrypted, inputVideo_demuxed, 'video')
			print("Done!")

	for aud in AudioList:
		AudioEnc = episodename + ' ' + aud['code'] + '.mp4'
		AudioDem = episodename + ' ' + aud['code'] + AudioExtension
		langAud = aud['language']

		if os.path.isfile(AudioEnc) and not os.path.isfile(AudioDem):
			print(f"\nDemuxing audio ({langAud})...")
			demux(AudioEnc, AudioDem, 'audio')
			print("Done!")

	if not args.nosubs:
		print ("\nDownloading subtitles...")
		if args.sublang:
			for sub in subtitleList:
				if sub['code'] in args.sublang:
					subname = episodename + ' ' + sub['code'] + '.srt'
					if not os.path.isfile(subname):
						downloadsubs(sub['url'], subname)
					else:
						print(str(sub['language']) + " - has already been successfully downloaded previously.")
		else:
			for sub in subtitleList:
				subname = episodename + ' ' + sub['code'] + '.srt'
				if not os.path.isfile(subname):
					downloadsubs(sub['url'], subname)
				else:
					print(str(sub['language']) + " - has already been successfully downloaded previously.")

		if args.forcedlang:
			for sub in forcedlist:
				if sub['code'] in args.forcedlang:
					subname = episodename + ' ' + 'forced-' + sub['code'] + '.srt'
					if not os.path.isfile(subname):
						downloadsubs(sub['url'], subname)
					else:
						print(str(sub['language']) + " - has already been successfully downloaded previously.")
		else:
			for sub in forcedlist:
				subname = episodename + ' ' + 'forced-' + sub['code'] + '.srt'
				if not os.path.isfile(subname):
					downloadsubs(sub['url'], subname)
				else:
					print(str(sub['language']) + " - has already been successfully downloaded previously.")

	# MUX

	subtitleformatter(episodename)

	AudioExist = False
	isAudios = glob.glob(episodename + "*" + AudioExtension)
	if isAudios != []: AudioExist = True
 
	muxer_defaults = {'audio':None, 'sub':None}
	if args.default_audio_mux: muxer_defaults.update({'audio': str(args.default_audio_mux)})
	else: muxer_defaults.update({'audio': 'eng'})
	if args.default_sub_mux: muxer_defaults.update({'sub': str(args.default_sub_mux)})
	else: muxer_defaults.update({'sub': 'eng'})

	if not args.novideo and not args.noaudio:
		if os.path.isfile(inputVideo_demuxed) and AudioExist:
			print ("\nMuxing...")
			if SHOW == False:
				MKV_Muxer=Muxer(
					CurrentName=episodename,
					SeasonFolder=None,
					CurrentHeigh=CurrentHeigh,
					Type="movie",
					defaults=muxer_defaults,
					mkvmergeexe=mkvmergeexe)
				MKV_Muxer.DPMuxer()
			else:
				if not os.path.exists(seasonfolder): os.makedirs(seasonfolder)
				MKV_Muxer=Muxer(
					CurrentName=episodename,
					SeasonFolder=seasonfolder,
					CurrentHeigh=CurrentHeigh,
					Type="show",
					defaults=muxer_defaults,
					mkvmergeexe=mkvmergeexe)
				MKV_Muxer.DPMuxer()

	if 'movies' in dsnpurl and not args.novideo:
		namer.rename(
			file=MKVOUT1,
			source='DSNP',
			group=args.group
		)  
	if not 'movies' in dsnpurl and not args.novideo:   
		namer.rename(
			file=MKVOUT2,
			source='DSNP',
			group=args.group
		)

	if not args.keep:
		do_clean(episodename)

	print('Done!')

if __name__ == '__main__':
	
	print('\nDisney Plus DRM Downloader v.5.0')
	global AuthorizationToken
	global dsnpurl
	global isuhd
	global ishevc
	global ishdr

	load_token_ini = load_token_file()

	if load_token_ini:
		AuthorizationToken = load_token_ini
	else:
		TOKEN, EXPIRE = generate_token()
		save_token(TOKEN, EXPIRE)
		AuthorizationToken = TOKEN

	if args.outputfolder:
		downloadpath = str(args.outputfolder)
	else:
		downloadpath = 'Downloads'

	if not os.path.exists(KEYS_Folder): 
		os.makedirs(KEYS_Folder)

	if not os.path.exists(downloadpath):
		os.makedirs(downloadpath)
	os.chdir(downloadpath)

	if not args.disneyurl:
		dsnpurl = input("DisneyPlus URL: ")
	else:
		dsnpurl = str(args.disneyurl)

	dsnpid = dsnpurl.rsplit('/', 1)[1]

	ishevc=False    
	ishdr=False
	isuhd=False
	isAtmos=False

	if args.hevc: ishevc=True
	if args.hdr: ishdr=True
	if args.uhd: isuhd=True
	if args.atmos: isAtmos=True

	if 'movies' in dsnpurl:
		print('\nGetting DRM movie metadata & m3u8...')
		dsnp = DSNP(dsnpid, AuthorizationToken, 'movie', ishdr=ishdr, isuhd=isuhd, ishevc=ishevc)
		movie = dsnp.load_playlist()
		url = dsnp.load_info_m3u8(movie['id']['mediaId'], movie['mediaFormat'], args.customquality, isAtmos=isAtmos)
		print('Done!')
		name = FixShowName(movie['Title']) + ' ' + str(movie['Year'])
		main(episodename=name, seasonfolder=None, m3u8Url=url, SHOW=False)
	
	else:
		if 'series' in dsnpurl:
			if args.season:
				season_number = StripInputInt(str(args.season))
			else:
				season_number = StripInputInt(str(input("ENTER Season Number: ")))
			if args.episode:
				episode_number = StripInputInt(str(args.episode))
			else:
				episode_number = StripInputInt(str(input("ENTER Episode Number: ")))

			print('\nGetting season metadata')
			dsnp = DSNP(DsnyID=dsnpid, Token=AuthorizationToken, Type='show', Season=season_number, ishdr=ishdr, isuhd=isuhd, ishevc=ishevc)
			episodes = dsnp.load_playlist()
			print('Done!')

			start_episode = int(episode_number) - 1
			if args.all_season:
				del episodes[0:start_episode]
				for ep in episodes:
					sizonumbr = FixSeq(ep['seasonNumber'])
					epsnumbr = FixSeq(ep['episodeNumber'])
					showname = FixShowName(ep['Title'])
					name = f"{showname} S{sizonumbr}E{epsnumbr}"
					folder = f"{showname} S{sizonumbr}"
					dsnp_m3u8 = DSNP(DsnyID=False, Token=AuthorizationToken, Type='show', Season=True, ishdr=ishdr, isuhd=isuhd, ishevc=ishevc)
					url = dsnp_m3u8.load_info_m3u8(ep['mediaId'], ep['mediaFormat'], args.customquality, isAtmos=isAtmos)
					main(episodename=name, seasonfolder=folder, m3u8Url=url, SHOW=True)
			else:
				episodes = episodes[start_episode]
				sizonumbr = FixSeq(episodes['seasonNumber'])
				epsnumbr = FixSeq(episodes['episodeNumber'])
				showname = FixShowName(episodes['Title'])
				name = f"{showname} S{sizonumbr}E{epsnumbr}"
				folder = f"{showname} S{sizonumbr}"
				dsnp_m3u8 = DSNP(DsnyID=False, Token=AuthorizationToken, Type='show', Season=True, ishdr=ishdr,  isuhd=isuhd, ishevc=ishevc)
				url = dsnp_m3u8.load_info_m3u8(episodes['mediaId'], episodes['mediaFormat'], args.customquality, isAtmos=isAtmos)
				main(episodename=name, seasonfolder=folder, m3u8Url=url, SHOW=True)
		else:
			print("looks like you entered wrong disney url movie/show type.")
			print("url must contain: (disneyplus.com)")
			sys.exit()

