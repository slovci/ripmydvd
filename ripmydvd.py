#!/usr/bin/python

import sys
import os
import subprocess
import re
import time

LOG_FILE = "rip.log"
DEBUG = False

##### BEGIN RIPPER CLASS #####

class Ripper:
	def __init__(self, device=None, devType="DVD", preferredLang="en"):
		self.device = self._getDevice(device)
		
		self.devType = devType
		self.preferredLang = preferredLang
		
		self.discInfo = {}
		self.selectedTitles = {}
		
	def _getDevice(self,device=None):	
		if device == None or os.path.exists(device) == False:
			device = "/dev/dvd"
				
		if os.path.exists(device) == False:
			device = "/dev/sr0"
			
		if os.path.exists(device) == False:
			device = None
		
		return device
	
	def getDiscInfo(self):
		if self.devType == "DVD":
			self._getDVDInfo()
		
		return self.discInfo
						
	def _getDVDInfo(self):
		print("Reading Disc...")
		
		discId = ""
		discName = ""
		titles = {}
		
		cmdArgs = ["/usr/bin/mencoder","-msgmodule","-msglevel","all=-1:identify=6","-dvd-device",self.device,"dvd://99","-o","/dev/null"]
		pipe = subprocess.Popen(cmdArgs,stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
		outs,err = pipe.communicate()		
		lines = outs.splitlines()
		for line in lines:
			debug("_getDVDInfo: %s" % (line))
			
			if "IDENTIFY: ID_DVD_DISC_ID" in line:
				discId = re.sub(r'.*=(.*)',r'\1',line)
			
			elif "IDENTIFY: ID_DVD_VOLUME_ID" in line:
				discName = re.sub(r'.*=(.*)',r'\1',line)
			
			elif "IDENTIFY: ID_DVD_TITLE_" in line:
				titleNum = int(re.sub(r'.*IDENTIFY: ID_DVD_TITLE_(.*)_.*',r'\1',line))
				
				title = {}
				if titleNum in titles:
					title = titles[titleNum]
				
				title["number"] = titleNum
					
				if "_ANGLES" in line:
					angles = int(re.sub(r'.*=(.*)',r'\1',line))
					title["angle_count"] = angles
					
				elif "_LENGTH" in line:
					duration = float(re.sub(r'.*=(.*)',r'\1',line))
					title["duration"] = duration
		
				titles[titleNum] = title
		
		for titleNum in range(1,len(titles)+1):
			title = titles[titleNum]
			title = self._getAdditionalTitleInfo(title)
			titles[titleNum] = title
			
		self.discInfo = {
			"disc_id": discId,
			"volume_id": discName,
			"titles": titles
		}
		
	def _getAdditionalTitleInfo(self,title):
		debug("_getAdditionalTitleInfo(): title=%s" % (title))
		
		titleNum = title["number"]
			
		cmdArgs = ["/usr/bin/mencoder","-msgmodule","-msglevel","all=-1:open=6:identify=6","-dvd-device",self.device,"dvd://%s" % (titleNum),"-o","/dev/null"]
		pipe = subprocess.Popen(cmdArgs,stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
		outs,err = pipe.communicate()
		lines = outs.splitlines()
		
		for line in lines:
			debug(line)
		
			if "IDENTIFY: ID_SID_" in line:
				subtitleId = int(re.sub(r'.*ID_SID_(\d+)_.*',r'\1',line))
				subtitleLang = re.sub(r'.*=(.*)',r'\1',line)
				
				subtitle = {"id": subtitleId, "lang": subtitleLang}
				subtitles = [subtitle]
				if "subtitles" in title:
					subtitles = title["subtitles"]
					subtitles.append(subtitle)
				
				title["subtitles"] = subtitles
						
			'''
			if "IDENTIFY: ID_AID_" in line:
				audioId = int(re.sub(r'.*ID_AID_(\d+)_.*',r'\1',line))
				audioLang = re.sub(r'.*=(.*)',r'\1',line)
							
				audioStream = {"id": audioId, "lang": audioLang}
				audioStreams = [audioStream]
				if "audio_streams" in title:
					audioStreams = title["audio_streams"];
					audioStreams.append(audioStream)
				
				title["audio_streams"] = audioStreams
			'''
			
			if "IDENTIFY: CHAPTERS:" in line:
				chapterTimes = re.sub(r'.*IDENTIFY: CHAPTERS: *', "", line)
				chapterTimes = chapterTimes.split(",")
				for chapterTime in chapterTimes:
					if chapterTime == "":
						continue
											
					chapter = {"start_time": chapterTime}
					chapters = [chapter]
					if "chapters" in title:
						chapters = title["chapters"];
						chapters.append(chapter)
					
					title["chapters"] = chapters
				
			if "OPEN: audio stream: " in line:
				#Example: 	OPEN: audio stream: 0 format: ac3 (5.1) language: en aid: 128.
				
				index = int(re.sub(r'.*audio stream: (\d+).*', r'\1', line))
				
				id = int(re.sub(r'.*aid: ([^. ]+).*', r'\1', line))
				lang = re.sub(r'.*language: ([^ ]+).*', r'\1', line)
				format = re.sub(r'.*format: ([^ ]+).*', r'\1', line)
				
				channels = re.sub(r'.*\((.*)\).*', r'\1', line)
				if channels == "mono":
					channels = 1
				elif channels == "stereo":
					channels = 2
					
				channels = float(channels)
				
				audioStream = {"id": id, "lang": lang, "format": format, "channels": channels}
				audioStreams = [audioStream]
				if "audio_streams" in title:
					audioStreams = title["audio_streams"];
					audioStreams.append(audioStream)
				
				title["audio_streams"] = audioStreams
				
			#TODO: maybe get video format
			#DECVIDEO: VIDEO:  MPEG2  720x480  (aspect 3)  29.970 fps  7500.0 kbps (937.5 kbyte/s)
		
		if "chapters" not in title:
			chapter = {"start_time": "00:00:00.000"}
			chapters = [chapter]
			title["chapters"] = chapters
		
		title["settings"] = self._getTitleSettings(title)
		
		debug("_getAdditionalTitleInfo(): returns %s" % (title))
		return title
	
	
		
	def showMainMenu(self):
		if self.device == None:
			print "No Device Found"
			return
			
		self.getDiscInfo()
		
		titleCount = len(self.discInfo["titles"])
		
		selected = {}
		
		while True:
			debug("showMainMenu: self.discInfo=%s" % (self.discInfo))
			debug("showMainMenu: selected=%s" % (selected))
			
			print("Main Menu")
			print("")	
			print("%s (%s)" % (self.discInfo["volume_id"],self.discInfo["disc_id"]))
			print("")	
		
			for t in range(1,titleCount+1):
				selectedText = ""
				if str(t) in selected:
					selectedText = "Selected"
				
				title = self.discInfo["titles"][t]
				seconds = title["duration"]
				chapters = len(title["chapters"])
				angles = title["angle_count"]
				
				audio = ""
				if "audio_streams" in title:
					for audioStream in title["audio_streams"]:
						audId = audioStream["id"]
						audLang = audioStream["lang"]
						audFormat = audioStream["format"]
						audChannels = audioStream["channels"]
						audio += "\n        id=%s, lang=%s, format=%s, channels=%s " % (audId,audLang,audFormat,audChannels)
					
				subtitles = ""
				if "subtitles" in title:
					for subtitle in title["subtitles"]:
						subId = subtitle["id"]
						subLang = subtitle["lang"]
						subtitles += "\n        id=%s, lang=%s" % (subId, subLang)
				
				print("%s) %s" % (t,selectedText))
				print("    Duration: %s seconds" % (seconds))
				print("    Video Angles: %s" % (angles))
				print("    Audio Streams: %s" % (audio))
				print("    Subtitles: %s" % (subtitles))
			
			print("")
			print("1-%s) Select/Unselect a title" % (titleCount))
			print("a) Select all titles")
			print("u) Unselect all titles")
			print("m) Modify title settings")
			print("p) Process selected titles (Currently :%s)" % (sorted(selected.keys())))
			print("q) Quit")
			print("")
			
			userInput = raw_input("Select an option: ")
			
			if re.match(r'^[Qq].*',userInput) != None:
				exit(0)
			
			elif re.match(r'^[Aa].*',userInput) != None:
				selected = {}
				for t in range(1,titleCount+1):
					selected[str(t)] = self.discInfo["titles"][t]
			
			elif re.match(r'^[Uu].*',userInput) != None:
				selected = {}
			
			elif re.match(r'^[1-9][0-9]*',userInput) != None:
				if userInput in selected:
					selected.pop(userInput);
				else:
					selected[userInput] = self.discInfo["titles"][int(userInput)]
				
			elif re.match(r'^[Mm].*',userInput) != None:
				userInput = raw_input("Select an title [1-%s]: " % (titleCount))
				if re.match(r'^[1-9][0-9]*',userInput) != None:
					title = self._showTitleMenu(self.discInfo["titles"][int(userInput)])
					#self.discInfo["titles"][int(userInput)] = title
					
					if userInput in selected:
						#make sure to update the selected titles
						selected[userInput] = self.discInfo["titles"][int(userInput)]
						
			elif re.match(r'^[Pp].*',userInput) != None:
				self._processTitles(selected)
				break
			
	def _showTitleMenu(self, title):
		angles = title["angle_count"]
		
		while True:
			debug("_showTitleMenu: title=%s" % (title))
			settings = title["settings"]
			
			print("Title Menu")
			print("")	
			print("Title %s" % (title["number"]))
					
			print("")
			print("Angles")
			print("    Total: %s" % (title["angle_count"]))
			print("    Current: %s" % (settings["angle"]))
			
			if "audio_streams" in title:
				print("")
				print("Audio Streams")
				for audIdx in range(0,len(title["audio_streams"])):
					aud = title["audio_streams"][audIdx]
					audId = aud["id"]
					audLang = aud["lang"]
					audFormat = aud["format"]
					audChannels = aud["channels"]
					s = "Audio Stream: id=%s, lang=%s, format=%s, channels=%s" %(audId,audLang,audFormat,audChannels)
					
					if audIdx == settings["audio_stream_idx"]:
						s = "%s (selected)" % (s)
						
					print("    %s" % (s))
			
			if "subtitles" in title:	
				print("")
				print("Subtitles")
				for subIdx in range(0,len(title["subtitles"])):
					sub = title["subtitles"][subIdx]
					subId = sub["id"]
					subLang = sub["lang"]
					s = "Subtitle: id=%s, lang=%s" %(subId,subLang)
					
					if subIdx == settings["subtitle_idx"]:
						s = "%s (selected)" % (s)
					print("    %s" % (s))
			
			'''
			print("")
			print("Chapters")
			for chapterIdx in range(0,len(title["chapters"])):
				chapter = title["chapters"][chapterIdx]
				s = "Chapter %s [%s]" % (chapterIdx+1, chapter["start_time"])
				if chapterIdx in settings["selected_chapters"]:
					s = "%s (selected)" % (s)
				print("    %s" % (s))
			'''
			
			print("")
			print("v) Select video angle")
			print("a) Select audio stream")
			print("s) Select subtitle")
			#print("c) Select chapters")
			print("p) Preview title")
			print("b) Back to main menu")
			print("")
			
			done = False
			userInput = raw_input("Select an option: ")
			
			if re.match(r'^[Vv].*',userInput) != None:
				userInput = raw_input("Select an angle [1-%s]: " % (angles))
				if re.match(r'^[1-9][0-9]*',userInput) != None:
					angle = int(userInput)
					if angle > 0 and angle <= angles:
						title["settings"]["angle"] = angle
					
			elif re.match(r'^[Aa].*',userInput) != None:
				audioStreamCount = len(title["audio_streams"])
				userInput = raw_input("Select an audio stream [1-%s, N=None]: " % (audioStreamCount))
				if re.match(r'^[1-9][0-9]*',userInput) != None:
					audioStream = int(userInput)
					if audioStream > 0 and audioStream <= audioStreamCount:
						title["settings"]["audio_stream_idx"] = audioStream-1
				elif re.match(r'^[Nn]*',userInput) != None:
					title["settings"]["audio_stream_idx"] = None
						
			elif re.match(r'^[Ss].*',userInput) != None:
				subtitleCount = len(title["subtitles"])
				userInput = raw_input("Select a subtitle [1-%s, N=None]: " % (subtitleCount))
				if re.match(r'^[1-9][0-9]*',userInput) != None:
					subtitle = int(userInput)
					if subtitle > 0 and subtitle <= subtitleCount:
						title["settings"]["subtitle_idx"] = subtitle-1
				elif re.match(r'^[Nn]*',userInput) != None:
					title["settings"]["subtitle_idx"] = None
			
			'''
			elif re.match(r'^[Cc].*',userInput) != None:
				chapterCount = len(title["chapters"])
				userInput = raw_input("Select a chapter [1-%s, N=None]: " % (chapterCount))
				if re.match(r'^[1-9][0-9]*',userInput) != None:
					chapter = int(userInput)
					if chapter > 0 and chapter <= chapterCount and chapter not in settings["selected_chapters"]:
						title["settings"]["selected_chapters"].append(chapter)
						
				elif re.match(r'^[Nn]*',userInput) != None:
					title["settings"]["selected_chapters"] = []
			'''
			
			if re.match(r'^[Pp].*',userInput) != None:
				self._playTitle(title)
				
			elif re.match(r'^[Bb].*',userInput) != None:
				done = True
		
			if done:
				break
				
		return title
		
	def _getTitleSettings(self,title={}):
		settings = {
			"angle": 1,
			"audio_stream_idx": None,
			"subtitle_idx": None,
			"selected_chapters": []
		}
		
		if "settings" in title:
			settings = title["settings"]
		elif self.preferredLang != None and self.preferredLang != "":
			#audio/subtitle defaults based on preferred lang
						
			if "subtitles" in title:	
				for subIdx in range(0,len(title["subtitles"])):
					sub = title["subtitles"][subIdx]
					subLang = sub["lang"]
					if self.preferredLang == subLang:
						settings["subtitle_idx"] = subIdx
						break
						
			if "audio_streams" in title:
				for audIdx in range(0,len(title["audio_streams"])):
					aud = title["audio_streams"][audIdx]
					audLang = aud["lang"]
					if self.preferredLang == audLang:
						settings["audio_stream_idx"] = audIdx
						
						#We found an audio stream with the preferred language. We don't need subtitle.
						settings["subtitle_idx"] = None
						break
		elif "audio_streams" in title and len(title["audio_streams"]) > 0:
			#audio streams exist, but no preferred lang. just use the first audio stream
			settings["audio_stream_idx"] = None
					
		return settings;

	def _processTitles(self,selectedTitles={}):
		for titleId in selectedTitles:
			title = selectedTitles[titleId]
			self._processTitle(title)
	
	def _processTitle(self,title):
		volumeName = self.discInfo["volume_id"]
		titleNumber = title["number"]
		baseFile = "%s_title_%s" % (volumeName,titleNumber)
		copyFile = "%s.mpeg" % (baseFile)
		outFile  = "%s.mp4" % (baseFile)
		
		ffmpegCmd = ["/usr/bin/ffmpeg","-hide_banner","-y","-loglevel","warning"]
		mplayerCmd = ["/usr/bin/mplayer","-msgmodule","-msglevel","all=2","-dvd-device",self.device,"dvd://%s" % (titleNumber)]
		
		print("\nTitle %s" % (titleNumber))
		
		#Copy source
		copy = True
		if os.path.isfile(copyFile) :
			copy = False
			userInput = raw_input("Overwrite %s (y/[n]): " % (copyFile))
			if re.match(r'^[Yy].*',userInput) != None:
				copy = True	
				
		if copy == True:
			copyCmd = list(mplayerCmd)
			copyCmd.extend(["-dvdangle",str(title["settings"]["angle"]),"-dumpstream","-dumpfile",copyFile])
			
			print("  Copying Audio/Video...")
			debug("copyCmd=%s" % (copyCmd))
			start = time.time()
			pipe = subprocess.Popen(copyCmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
			outs,err = pipe.communicate()
			end = time.time()
			debug("err=%s" %(err))
			print("    Copy Duration: %s" % (end-start))
		
		inputOpts = ["-i",copyFile]
		videoOpts = []
		audioOpts = []
		subtitleOpts = []
		
		#Video encoding options
		vcodec = "libx264"
		vcompression = "veryfast"  #Testing shows "veryfast" is most efficient for time/compression ratio
		vquality = "20" #18 is supposedly "visually lossless", but still large file size. 20 still has good quality and much more reasonable file size
		
		videoOpts = ["-deinterlace","-vcodec",vcodec,"-preset",vcompression,"-crf",vquality,"-map","0:v"]
		
		#Audio encoding options
		audioStreamMap = None
		if title["settings"]["audio_stream_idx"] != None:
			audioStreamIdx = title["settings"]["audio_stream_idx"]
			audioStream = title["audio_streams"][audioStreamIdx]
			
			cmd = ["/usr/bin/ffprobe","-hide_banner",copyFile]
			debug("cmd=%s" %(cmd))
			pipe = subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
			outs,err = pipe.communicate()
			#debug("err=%s" %(err))
			
			lines = err.splitlines()
			for line in lines:
				debug("ffprobe line=%s" % (line))
				if "Stream" in line:
					if "Audio: %s" % (audioStream["format"]) in line:
						streamIdx = re.sub(r'.*Stream #([^\[]*).*',r'\1',line)
						streamId = int(re.sub(r'.*\[0x(.*)\]:.*',r'\1',line),16)
						
						streamChannels = re.sub(r'.*Hz, ([^\(, ]+).*',r'\1',line)
						if streamChannels == "mono":
							streamChannels = 1
						if streamChannels == "stereo":
							streamChannels = 2
						streamChannels = float(streamChannels)
						
						streamBitRate = int(re.sub(r'.* ([^ ]+) kb/s',r'\1',line))
						
						debug("streamIdx=%s, streamId=%s, streamChannels=%s, streamBitRate=%s" % (streamIdx,streamId,streamChannels,streamBitRate))
						if streamId == int(audioStream["id"]):
							#found a stream with the audio id we want
							
							tmpAudioStreamMap = {
								"number": streamIdx,
								"channels": streamChannels,
								"bitrate": streamBitRate
							}
							debug("setting tmpAudioStreamMap=%s" %(tmpAudioStreamMap))
							
							if audioStreamMap == None:
								audioStreamMap = tmpAudioStreamMap
								debug("setting audioStreamMap=%s" %(audioStreamMap))
								
							elif streamChannels >= audioStreamMap["channels"]:
								#select a stream with most channels and highest bitrate in that order
								
								if streamChannels > audioStreamMap["channels"]:
									audioStreamMap = tmpAudioStreamMap
									debug("using audioStreamMap=%s" %(audioStreamMap))
									
								elif streamBitRate > audioStreamMap["bitrate"]:
									audioStreamMap = tmpAudioStreamMap
									debug("using audioStreamMap=%s" %(audioStreamMap))
							
		if audioStreamMap != None:
			acodec = "aac"
			maxBitratePerChannel = 96
			channels = audioStreamMap["channels"]
			bitrate = audioStreamMap["bitrate"]
			
			bitratePerChannel = 1.0 * bitrate / channels
			if bitratePerChannel > maxBitratePerChannel:
				bitrate = maxBitratePerChannel * channels
			
			audioOpts = ["-acodec",acodec,"-strict","experimental","-b:a","%sk" % (bitrate),"-map",audioStreamMap["number"]]
		
		#Copy subtitles and set subtitle encoding options
		if title["settings"]["subtitle_idx"] != None:
			subtitleIdx = title["settings"]["subtitle_idx"]
			subtitle = title["subtitles"][subtitleIdx]

			if os.path.isfile("%s.idx" % (baseFile)):
				os.remove("%s.idx" % (baseFile))
				
			if os.path.isfile("%s.sub" % (baseFile)):
				os.remove("%s.sub" % (baseFile))
			
			subCopyCmd = list(mplayerCmd)
			subCopyCmd[0] = "/usr/bin/mencoder"
			subCopyCmd.extend(["-vobsubout",baseFile,"-slang",subtitle["lang"],"-nosound","-ovc","copy","-o","/dev/null"])
			
			print("  Copying Subtitles...")
			debug("subCopyCmd=%s" % (subCopyCmd))
			start = time.time()
			pipe = subprocess.Popen(subCopyCmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
			outs,err = pipe.communicate()
			end = time.time()
			debug("err=%s" %(err))
			print("    Copy Duration: %s" % (end-start))
			
			inputOpts.extend(["-i","%s.sub" %(baseFile),"-i","%s.idx" %(baseFile)])
			subtitleOpts = ["-filter_complex","[0:v][1:s]overlay[v]", "-map", "[v]"]
		
		encodeCmd = list(ffmpegCmd)
		encodeCmd.extend(inputOpts)
		encodeCmd.extend(videoOpts)
		encodeCmd.extend(audioOpts)
		encodeCmd.extend(subtitleOpts)
		encodeCmd.append(outFile)
		
		print("  Encoding...")
		debug("encodeCmd=%s" % (encodeCmd))
		start = time.time()
		pipe = subprocess.Popen(encodeCmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
		outs,err = pipe.communicate()
		end = time.time()
		debug("err=%s" %(err))
		print("    Encode Duration: %s" % (end-start))
		
		print("")
		print("  File complete: %s" % (outFile))
		
	def _playTitle(self,title={}):
		titleNum = title["number"]
		#cmdArgs = ["/usr/bin/mplayer","-dvd-device",self.device,"dvd://%s" % (titleNum)]
		cmdArgs = ["/usr/bin/mpv","-dvd-device",self.device,"dvd://%s" % (titleNum)]
		pipe = subprocess.Popen(cmdArgs,stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
		outs,err = pipe.communicate()
			
##### END RIPPER CLASS #####
	
def debug(msg=None):
	if DEBUG == True and msg != None:
		log("DEBUG: %s" % (msg))
		
def log(msg=None):
	if msg != None:
		tm = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
		
		if LOG_FILE != None:
			f = open(LOG_FILE,'a')
			f.write("%s: %s\n" % (tm,msg))
			f.close()
		else:
			print("%s: %s" % (tm,msg))
		
def getArgValue(arg=None):
	val = None

	if arg != None:
		for idx in range(1,len(sys.argv)):
			key = sys.argv[idx]
			if arg == key and len(sys.argv) > idx+1:
				val = sys.argv[idx+1]
				break

	return val
	
def main():
	device = getArgValue("--device")
	lang = getArgValue("--lang")
	
	log = getArgValue("--log")
	if log != None:
		global LOG_FILE
		LOG_FILE = log
		
	if "--debug" in sys.argv:
		global DEBUG
		DEBUG = True
	
	ripper = Ripper(device, "DVD", lang)
	ripper.showMainMenu()
	
if __name__ == "__main__":
	main()
