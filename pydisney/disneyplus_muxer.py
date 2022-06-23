import os, subprocess, sys, contextlib

class Muxer(object):
	def __init__(self, CurrentName, SeasonFolder, CurrentHeigh, Type, defaults, mkvmergeexe):
		self.CurrentName = CurrentName
		self.SeasonFolder = SeasonFolder
		self.CurrentHeigh = CurrentHeigh
		self.Type = Type
		self.defaults = defaults
		self.mkvmergeexe = mkvmergeexe

	def mux(self, command):
		newlines = ['\n', '\r\n', '\r']
		def unbuffered(proc, stream='stdout'):
			stream = getattr(proc, stream)
			with contextlib.closing(stream):
				while True:
					out = []
					last = stream.read(1)
					# Don't loop forever
					if last == '' and proc.poll() is not None:
						break
					while last not in newlines:
						# Don't loop forever
						if last == '' and proc.poll() is not None:
							break
						out.append(last)
						last = stream.read(1)
					out = ''.join(out)
					yield out

		proc = subprocess.Popen(
			command,
			stdout=subprocess.PIPE,
			stderr=subprocess.STDOUT,
			bufsize=1,
			universal_newlines=True,
		)
		for line in unbuffered(proc):
			if 'Progress:' in line:
				sys.stdout.write("\r%s" % (line.replace('Progress:', 'Progress:')))
				sys.stdout.flush()
		print('')

		return 

	def DPMuxer(self):
		
		VideoInputNoExist = False
		
		if os.path.isfile('.\\'+self.CurrentName + ' [' + self.CurrentHeigh + 'p].h264'):
			VideoInputName = '.\\'+self.CurrentName + ' [' + self.CurrentHeigh + 'p].h264'
			if self.Type == "show":
				VideoOutputName = '.\\'+self.SeasonFolder+'\\'+self.CurrentName + '.mkv'
			else:
				VideoOutputName = '.\\'+self.CurrentName + '.mkv'

		elif os.path.isfile('.\\'+self.CurrentName + ' [' + self.CurrentHeigh + 'p].h265'):
			VideoInputName = '.\\'+self.CurrentName + ' [' + self.CurrentHeigh + 'p].h265'
			if self.Type == "show":
				VideoOutputName = '.\\'+self.SeasonFolder+'\\'+self.CurrentName + '.mkv'
			else:
				VideoOutputName = '.\\'+self.CurrentName + '.mkv'

		elif os.path.isfile('.\\'+self.CurrentName + ' [' + self.CurrentHeigh + 'p] [HEVC].h265'):
			VideoInputName = '.\\'+self.CurrentName + ' [' + self.CurrentHeigh + 'p] [HEVC].h265'
			if self.Type == "show":
				VideoOutputName = '.\\'+self.SeasonFolder+'\\'+self.CurrentName + '.mkv'
			else:
				VideoOutputName = '.\\'+self.CurrentName + '.mkv'
		
		elif os.path.isfile('.\\'+self.CurrentName + ' [' + self.CurrentHeigh + 'p] [HDR].h265'):
			VideoInputName = '.\\'+self.CurrentName + ' [' + self.CurrentHeigh + 'p] [HDR].h265'
			if self.Type == "show":
				VideoOutputName = '.\\'+self.SeasonFolder+'\\'+self.CurrentName + '.mkv'
			else:
				VideoOutputName = '.\\'+self.CurrentName + '.mkv'		
		else:
			VideoInputNoExist = True

		if VideoInputNoExist == False:

			AudioExtensionsList=[
									".ac3",
									".eac3",
									".m4a",
									".dts",
									".mp3",
									".aac",
								]
			
			SubsExtensionsList= [
									".srt",
									".ass",
								]
			

			language_tag = "English"

			if language_tag == "English":
				subs_forced = '[Forced]'
				subs_full = ''
				subs_sdh = '[SDH]'

				LanguageList = [
									["English", "eng", "eng", "English", "yes", "no"],
									["Afrikaans", "af", "afr", "Afrikaans", "no", "no"],
									["Arabic", "ara", "ara", "Arabic", "no", "no"],
									["Arabic (Syria)", "araSy", "ara", "Arabic Syria", "no", "no"],
									["Arabic (Egypt)", "araEG", "ara", "Arabic Egypt", "no", "no"],
									["Arabic (Kuwait)", "araKW", "ara", "Arabic Kuwait", "no", "no"],
									["Arabic (Lebanon)", "araLB", "ara", "Arabic Lebanon", "no", "no"],
									["Arabic (Algeria)", "araDZ", "ara", "Arabic Algeria", "no", "no"],
									["Arabic (Bahrain)", "araBH", "ara", "Arabic Bahrain", "no", "no"],
									["Arabic (Iraq)", "araIQ", "ara", "Arabic Iraq", "no", "no"],
									["Arabic (Jordan)", "araJO", "ara", "Arabic Jordan", "no", "no"],
									["Arabic (Libya)", "araLY", "ara", "Arabic Libya", "no", "no"],
									["Arabic (Morocco)", "araMA", "ara", "Arabic Morocco", "no", "no"],
									["Arabic (Oman)", "araOM", "ara", "Arabic Oman", "no", "no"],
									["Arabic (Saudi Arabia)", "araSA", "ara", "Arabic Saudi Arabia", "no", "no"],
									["Arabic (Tunisia)", "araTN", "ara", "Arabic Tunisia", "no", "no"],
									["Arabic (United Arab Emirates)", "araAE", "ara", "Arabic United Arab Emirates", "no", "no"],
									["Arabic (Yemen)", "araYE", "ara", "Arabic Yemen", "no", "no"],
									["Armenian", "hye", "arm", "Armenian", "no", "no"],
									["Assamese", "asm", "asm", "Assamese", "no", "no"],
									["Bangla", "ben", "ben", "Bengali", "no", "no"],
									["Basque", "eus", "baq", "Basque", "no", "no"],
									["Bulgarian", "bul", "bul", "Bulgarian", "no", "no"],
									["Cantonese", "None", "chi", "Cantonese", "no", "no"],
									["Catalan", "cat", "cat", "Catalan", "no", "no"],
									["Simplified Chinese", "zhoS", "chi", "Chinese Simplified", "no", "no"],
									["Traditional Chinese", "zhoT", "chi", "Chinese Traditional", "no", "no"],
									["Croatian", "hrv", "hrv", "Croatian", "no", "no"],
									["Czech", "ces", "cze", "Czech", "no", "no"],
									["Danish", "dan", "dan", "Danish", "no", "no"],
									["Dutch", "nld", "dut", "Dutch", "no", "no"],
									["Estonian", "est", "est", "Estonian", "no", "no"],
									["Filipino", "fil", "fil", "Filipino", "no", "no"],
									["Finnish", "fin", "fin", "Finnish", "no", "no"],
									["Flemish", "nlBE", "dut", "Flemish", "no", "no"],
									["French", "fra", "fra", "French", "no", "no"],
									["French Canadian", "caFra", "fre", "French Canadian", "no", "no"],
									["German", "deu", "ger", "German", "no", "no"],
									["Greek", "ell", "gre", "Greek", "no", "no"],
									["Gujarati", "guj", "guj", "Gujarati", "no", "no"],
									["Hebrew", "heb", "heb", "Hebrew", "no", "no"],
									["Hindi", "hin", "hin", "Hindi", "no", "no"],
									["Hungarian", "hun", "hun", "Hungarian", "no", "no"],
									["Icelandic", "isl", "ice", "Icelandic", "no", "no"],
									["Indonesian", "ind", "ind", "Indonesian", "no", "no"],
									["Italian", "ita", "ita", "Italian", "no", "no"],
									["Japanese", "jpn", "jpn", "Japanese", "no", "no"],
									["Kannada (India)", "kan", "kan", "Kannada (India)", "no", "no"],
									["Khmer", "khm", "khm", "Khmer", "no", "no"],
									["Klingon", "tlh", "tlh", "Klingon", "no", "no"],
									["Korean", "kor", "kor", "Korean", "no", "no"],
									["Lithuanian", "lit", "lit", "Lithuanian", "no", "no"],
									["Latvian", "lav", "lav", "Latvian", "no", "no"],
									["Malay", "msa", "may", "Malay", "no", "no"],
									["Malayalam", "mal", "mal", "Malayalam", "no", "no"],
									["Mandarin", "None", "chi", "Mandarin", "no", "no"],
									["Mandarin Chinese (Simplified)", "zh-Hans", "chi", "Simplified", "no", "no"],
									["Mandarin Chinese (Traditional)", "zh-Hant", "chi", "Traditional", "no", "no"],
									["Yue Chinese", "yue", "chi", "(Yue Chinese)", "no", "no"],
									["Manipuri", "mni", "mni", "Manipuri", "no", "no"],
									["Marathi", "mar", "mar", "Marathi", "no", "no"],
									["No Dialogue", "zxx", "zxx", "No Dialogue", "no", "no"],
									["Norwegian", "nor", "nor", "Norwegian", "no", "no"],
									["Persian", "fas", "per", "Persian", "no", "no"],
									["Polish", "pol", "pol", "Polish", "no", "no"],
									["Portuguese", "por", "por", "Portuguese", "no", "no"],
									["Brazilian Portuguese", "brPor", "por", "Brazilian Portuguese", "no", "no"],
									["Punjabi", "pan", "pan", "Punjabi", "no", "no"],
									["Romanian", "ron", "rum", "Romanian", "no", "no"],
									["Russian", "rus", "rus", "Russian", "no", "no"],
									["Serbian", "srp", "srp", "Serbian", "no", "no"],
									["Sinhala", "sin", "sin", "Sinhala", "no", "no"],
									["Slovak", "slk", "slo", "Slovak", "no", "no"],
									["Slovenian", "slv", "slv", "Slovenian", "no", "no"],
									["Spanish", "spa", "spa", "Spanish", "no", "no"],
									["European Spanish", "euSpa", "spa", "European Spanish", "no", "no"],
									["Swedish", "swe", "swe", "Swedish", "no", "no"],
									["Tagalog", "tgl", "tgl", "Tagalog", "no", "no"],
									["Tamil", "tam", "tam", "Tamil", "no", "no"],
									["Telugu", "tel", "tel", "Telugu", "no", "no"],
									["Thai", "tha", "tha", "Thai", "no", "no"],
									["Turkish", "tur", "tur", "Turkish", "no", "no"],
									["Ukrainian", "ukr", "ukr", "Ukrainian", "no", "no"],
									["Urdu", "urd", "urd", "Urdu", "no", "no"],
									["Vietnamese", "vie", "vie", "Vietnamese", "no", "no"],								]
			
			ALLAUDIOS = []
			for audio_language, subs_language, language_id, language_name, audio_default, subs_default in LanguageList:
				for AudioExtension in AudioExtensionsList:
					if os.path.isfile('.\\' + self.CurrentName + ' ' + language_id + AudioExtension):
						if language_id == self.defaults['audio']:
							ALLAUDIOS = ALLAUDIOS + ['--language', '0:' + language_id, '--track-name', '0:' + language_name, '--default-track', '0:yes', '(', '.\\' + self.CurrentName + ' ' + language_id + AudioExtension, ')']
						else:
							ALLAUDIOS = ALLAUDIOS + ['--language', '0:' + language_id, '--track-name', '0:' + language_name, '--default-track', '0:no', '(', '.\\' + self.CurrentName + ' ' + language_id + AudioExtension, ')']

			OnlyOneLanguage = False
			if len(ALLAUDIOS) == 9:
				OnlyOneLanguage = True
			
			elif len(ALLAUDIOS) == 18:
				if ALLAUDIOS[1] == ALLAUDIOS[10]:
					if ' - Audio Description' in ALLAUDIOS[7] or ' - Audio Description' in ALLAUDIOS[16]:
						OnlyOneLanguage = True
			else:
				OnlyOneLanguage = False

			ALLSUBS = []
			for audio_language, subs_language, language_id, language_name, audio_default, subs_default in LanguageList:
				if subs_language == self.defaults['sub']:
					subs_default == 'yes'
				for SubsExtension in SubsExtensionsList:
					if os.path.isfile('.\\' + self.CurrentName + ' ' + 'forced-' + subs_language + SubsExtension):
						if subs_language == self.defaults['sub']:
							ALLSUBS = ALLSUBS + ['--language', '0:' + language_id, '--track-name', '0:' + language_name + ' ' + subs_forced, '--forced-track', '0:yes', '--default-track', '0:no', '--compression', '0:none', '(', '.\\' + self.CurrentName + ' ' + 'forced-' + subs_language + SubsExtension, ')']
						else:
							ALLSUBS = ALLSUBS + ['--language', '0:' + language_id, '--track-name', '0:' + language_name + ' ' + subs_forced, '--forced-track', '0:yes', '--default-track', '0:' + subs_default, '--compression', '0:none', '(', '.\\' + self.CurrentName + ' ' + 'forced-' + subs_language + SubsExtension, ')']
					if OnlyOneLanguage == True:
						pass
					if os.path.isfile('.\\' + self.CurrentName + ' ' + subs_language + SubsExtension):
						if subs_language == self.defaults['sub']:
							ALLSUBS = ALLSUBS + ['--language', '0:' + language_id, '--track-name', '0:' + language_name + ' ' + subs_full, '--forced-track', '0:no', '--default-track', '0:yes', '--compression', '0:none', '(', '.\\' + self.CurrentName + ' ' + subs_language + SubsExtension, ')']
						else:
							ALLSUBS = ALLSUBS + ['--language', '0:' + language_id, '--track-name', '0:' + language_name + ' ' + subs_full, '--forced-track', '0:no', '--default-track', '0:' + subs_default, '--compression', '0:none', '(', '.\\' + self.CurrentName + ' ' + subs_language + SubsExtension, ')']
					elif os.path.isfile('.\\' + self.CurrentName + ' ' + subs_language + SubsExtension):
						if subs_language == self.defaults['sub']:
							ALLSUBS = ALLSUBS + ['--language', '0:' + language_id, '--track-name', '0:' + language_name + ' ' + subs_full, '--forced-track', '0:no', '--default-track', '0:yes', '--compression', '0:none', '(', '.\\' + self.CurrentName + ' ' + subs_language + SubsExtension, ')']
						else:
							ALLSUBS = ALLSUBS + ['--language', '0:' + language_id, '--track-name', '0:' + language_name + ' ' + subs_full, '--forced-track', '0:no', '--default-track', '0:no', '--compression', '0:none', '(', '.\\' + self.CurrentName + ' ' + subs_language + SubsExtension, ')']
					if os.path.isfile('.\\' + self.CurrentName + ' ' + 'sdh-' + subs_language + SubsExtension):
						ALLSUBS = ALLSUBS + ['--language', '0:' + language_id, '--track-name', '0:' + language_name + ' ' + subs_sdh, '--forced-track', '0:no', '--default-track', '0:no', '--compression', '0:none', '(', '.\\' + self.CurrentName + ' ' + 'sdh-' + subs_language + SubsExtension, ')']

			#MUX

			mkvmerge_command_video = [self.mkvmergeexe,
										'--output',
										VideoOutputName,
										'--language',
										'0:und',
										'--default-track',
										'0:yes',
										'(',
										VideoInputName,
										')']

			mkvmerge_command = mkvmerge_command_video + ALLAUDIOS + ALLSUBS
			self.mux(mkvmerge_command)