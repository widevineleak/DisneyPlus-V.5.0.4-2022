import logging, os, re, subprocess, sys
from pymediainfo import MediaInfo

__LOGGER__ = logging.getLogger(__name__)

def rename(file, source, group):

	base_name = file
	name = os.path.splitext(os.path.basename(file))[0]
	directory_name = os.path.dirname(file)
	media_info = MediaInfo.parse(file)
	
	for track in media_info.tracks:        
		if track.track_type == 'Video':            
			if int(track.width) == 1280 or int(track.height) == 720: resolution = '720p'
			elif int(track.width) == 1920 or int(track.height) == 1080: resolution = '1080p'
			else: 
				if int(track.height) > 600: 
					resolution = '{}p'.format(track.height)
				else:
					resolution = None 

			if track.format == "AVC": 
				if track.encoding_settings: codec = "x264"
				else:codec = "H.264"
			elif track.format == "HEVC":
				if track.encoding_settings: codec = "x265"
				else:codec = "H.265"
			if 'Main 10@L5' in track.format_profile:
				hdr = True  
			else:
				hdr = None                                         
		
		
		try:
			track = [track for track in media_info.tracks if track.track_type == "Audio"][0]
		except IndexError:
			track = track
		if track.track_type == 'Audio':

			if track.format == "E-AC-3":
				audioCodec = "DDP"
			elif track.format == "AC-3":
				audioCodec = "DD"
			elif track.format == "AAC":
				audioCodec = "AAC"
			elif track.format == "DTS":
				audioCodec = "DTS"
			elif "DTS" in track.format:
				audioCodec = "DTS"
			else:
				print("No Audio Root Found: {}".format(track.format))
				audioCodec = None                
			
			if track.channel_s == 6:
				if "Atmos" in track.commercial_name: 
					channels = '5.1.Atmos'
				else:
					channels = "5.1"
			elif track.channel_s == 2: channels = "2.0"		
			elif track.channel_s == 1: channels = "1.0"
			else:
				print("No Audio Channel Found: {}".format(track.channel_s))
				channels = None                
	
	name = name.replace(" ", ".").replace("'", "").replace(',', '')
	if hdr is not None:
		name = '{}.{}.{}.WEB-DL.HDR.{}{}.{}-{}'.format(
			name, resolution, source, audioCodec, channels, codec, group).replace('.-.', '.')
	else:
		if resolution is None:
			name = '{}.{}.WEB-DL.{}{}.{}-{}'.format(
			name, source, audioCodec, channels, codec, group).replace('.-.', '.')  
		else:
			name = '{}.{}.{}.WEB-DL.{}{}.{}-{}'.format(
			name, resolution, source, audioCodec, channels, codec, group).replace('.-.', '.')             
	name = re.sub(r'(\.\.)', '.', name)
	filename = '{}.mkv'.format(os.path.join(directory_name, name))
	if os.path.exists(filename): os.remove(filename)
	os.rename(base_name, filename)