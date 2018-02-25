#!/usr/bin/python

import sys
import os
import subprocess
import re
import time

LOG_FILE = "rip.log"
DEBUG = False


class Ripper:
    def __init__(self, device=None, devType="DVD", preferredLang="en"):
        self.device = self._get_device(device)

        self.devType = devType
        self.preferredLang = preferredLang

        self.discInfo = {}
        self.selectedTitles = {}

    def _get_device(self, device=None):
        if device is None or os.path.exists(device) is False:
            device = "/dev/dvd"

        if os.path.exists(device) is False:
            device = "/dev/sr0"

        if os.path.exists(device) is False:
            device = "/dev/sr1"

        if os.path.exists(device) is False:
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

        cmdArgs = ["/usr/bin/mencoder", "-msgmodule", "-msglevel", "all=-1:identify=6", "-dvd-device", self.device, "dvd://99", "-o", "/dev/null"]
        pipe = subprocess.Popen(cmdArgs, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        outs, err = pipe.communicate()
        lines = outs.splitlines()
        for line in lines:
            debug("_getDVDInfo: %s" % (line))

            if "IDENTIFY: ID_DVD_DISC_ID" in line:
                discId = re.sub(r'.*=(.*)', r'\1', line)

            elif "IDENTIFY: ID_DVD_VOLUME_ID" in line:
                discName = re.sub(r'.*=(.*)', r'\1', line)

            elif "IDENTIFY: ID_DVD_TITLE_" in line:
                titleNum = int(re.sub(r'.*IDENTIFY: ID_DVD_TITLE_(.*)_.*', r'\1', line))

                title = {}
                if titleNum in titles:
                    title = titles[titleNum]

                title["number"] = titleNum

                if "_ANGLES" in line:
                    angles = int(re.sub(r'.*=(.*)', r'\1', line))
                    title["angle_count"] = angles

                elif "_LENGTH" in line:
                    duration = float(re.sub(r'.*=(.*)', r'\1', line))
                    title["duration"] = duration

                titles[titleNum] = title

        for titleNum in range(1, len(titles)+1):
            title = titles[titleNum]
            title = self._getAdditionalTitleInfo(title)
            titles[titleNum] = title

        self.discInfo = {
            "disc_id": discId,
            "volume_id": discName,
            "titles": titles
        }

    def _getAdditionalTitleInfo(self, title):
        debug("_getAdditionalTitleInfo(): title=%s" % (title))

        titleNum = title["number"]

        cmdArgs = ["/usr/bin/mencoder", "-msgmodule", "-msglevel", "all=-1:open=6:identify=6", "-dvd-device", self.device, "dvd://%s" % (titleNum), "-o", "/dev/null"]
        pipe = subprocess.Popen(cmdArgs, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        outs, err = pipe.communicate()
        lines = outs.splitlines()

        for line in lines:
            debug(line)

            if "IDENTIFY: ID_SID_" in line:
                subtitleId = int(re.sub(r'.*ID_SID_(\d+)_.*', r'\1', line))
                subtitleLang = re.sub(r'.*=(.*)', r'\1', line)

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
                        chapters = title["chapters"]
                        chapters.append(chapter)

                    title["chapters"] = chapters

            if "OPEN: audio stream: " in line:
                # Example: 	OPEN: audio stream: 0 format: ac3 (5.1) language: en aid: 128.

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
                    audioStreams = title["audio_streams"]
                    audioStreams.append(audioStream)

                title["audio_streams"] = audioStreams

            # TODO: maybe get video format
            # DECVIDEO: VIDEO:  MPEG2  720x480  (aspect 3)  29.970 fps  7500.0 kbps (937.5 kbyte/s)

        if "chapters" not in title:
            chapter = {"start_time": "00:00:00.000"}
            chapters = [chapter]
            title["chapters"] = chapters

        title["settings"] = self._getTitleSettings(title)

        debug("_getAdditionalTitleInfo(): returns %s" % (title))
        return title

    def showMainMenu(self):
        if self.device is None:
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
            print("%s (%s)" % (self.discInfo["volume_id"], self.discInfo["disc_id"]))
            print("")

            for title_idx in range(1, titleCount+1):
                selectedText = ""
                if str(title_idx) in selected:
                    selectedText = "Selected"

                title = self.discInfo["titles"][title_idx]
                seconds = title["duration"]
                chapters = len(title["chapters"])
                angles = title["angle_count"]

                audio_text = ""
                audio_streams = title.get("audio_streams", [])
                for audio_stream_idx, audio_stream in enumerate(audio_streams):
                    aud_id = audio_stream["id"]
                    aud_lang = audio_stream["lang"]
                    aud_format = audio_stream["format"]
                    aud_channels = audio_stream["channels"]

                    audio_text += "\n        id=%s, lang=%s, format=%s, channels=%s " % (
                        aud_id, aud_lang, aud_format, aud_channels
                    )

                    selected_audio_idx = title.get("settings", {}).get("audio_stream_idx", None)
                    if selected_audio_idx is not None:
                        if int(selected_audio_idx) == audio_stream_idx:
                            audio_text += " (selected)"

                subtitles_text = ""
                subtitles = title.get("subtitles", [])
                for subtitle_idx, subtitle in enumerate(subtitles):
                    subId = subtitle.get("id")
                    subLang = subtitle.get("lang")
                    subtitles_text += "\n        id=%s, lang=%s" % (subId, subLang)

                    selected_subtitle_idx = title.get("settings", {}).get("subtitle_idx", None)
                    if selected_subtitle_idx is not None:
                        if int(selected_subtitle_idx) == subtitle_idx:
                            subtitles_text += " (selected)"

                print("%s) %s" % (title_idx, selectedText))
                print("    Duration: %s seconds" % (seconds))
                print("    Video Angles: %s" % (angles))
                print("    Audio Streams: %s" % (audio_text))
                print("    Subtitles: %s" % (subtitles_text))

            print("")
            print("1-%s) Select/Unselect a title" % (titleCount))
            print("a) Select all titles")
            print("u) Unselect all titles")
            print("m) Modify title settings")
            print("p) Process selected titles (Currently :%s)" % (sorted(selected.keys())))
            print("q) Quit")
            print("")

            userInput = raw_input("Select an option: ")

            if re.match(r'^[Qq].*', userInput) is not None:
                exit(0)

            elif re.match(r'^[Aa].*', userInput) is not None:
                selected = {}
                for t in range(1, titleCount+1):
                    selected[str(t)] = self.discInfo["titles"][t]

            elif re.match(r'^[Uu].*', userInput) is not None:
                selected = {}

            elif re.match(r'^[1-9][0-9]*', userInput) is not None:
                if userInput in selected:
                    selected.pop(userInput)
                else:
                    selected[userInput] = self.discInfo["titles"][int(userInput)]

            elif re.match(r'^[Mm].*', userInput) is not None:
                userInput = raw_input("Select an title [1-%s]: " % (titleCount))
                if re.match(r'^[1-9][0-9]*', userInput) is not None:
                    title = self._showTitleMenu(self.discInfo["titles"][int(userInput)])
                    # self.discInfo["titles"][int(userInput)] = title

                    if userInput in selected:
                        # make sure to update the selected titles
                        selected[userInput] = self.discInfo["titles"][int(userInput)]

            elif re.match(r'^[Pp].*', userInput) is not None:
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
                for audIdx in range(0, len(title["audio_streams"])):
                    aud = title["audio_streams"][audIdx]
                    audId = aud["id"]
                    audLang = aud["lang"]
                    audFormat = aud["format"]
                    audChannels = aud["channels"]
                    s = "Audio Stream: id=%s, lang=%s, format=%s, channels=%s" % (audId, audLang, audFormat, audChannels)

                    if audIdx == settings["audio_stream_idx"]:
                        s = "%s (selected)" % (s)

                    print("    %s" % (s))

            if "subtitles" in title:
                print("")
                print("Subtitles")
                for subIdx in range(0, len(title["subtitles"])):
                    sub = title["subtitles"][subIdx]
                    subId = sub["id"]
                    subLang = sub["lang"]
                    s = "Subtitle: id=%s, lang=%s" % (subId, subLang)

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
            # print("c) Select chapters")
            print("p) Preview title")
            print("b) Back to main menu")
            print("")

            done = False
            userInput = raw_input("Select an option: ")

            if re.match(r'^[Vv].*', userInput) is not None:
                userInput = raw_input("Select an angle [1-%s]: " % (angles))
                if re.match(r'^[1-9][0-9]*', userInput) is not None:
                    angle = int(userInput)
                    if angle > 0 and angle <= angles:
                        title["settings"]["angle"] = angle

            elif re.match(r'^[Aa].*', userInput) is not None:
                audioStreamCount = len(title["audio_streams"])
                userInput = raw_input("Select an audio stream [1-%s, N=None]: " % (audioStreamCount))
                if re.match(r'^[1-9][0-9]*', userInput) is not None:
                    audioStream = int(userInput)
                    if audioStream > 0 and audioStream <= audioStreamCount:
                        title["settings"]["audio_stream_idx"] = audioStream-1
                elif re.match(r'^[Nn]*', userInput) is not None:
                    title["settings"]["audio_stream_idx"] = None

            elif re.match(r'^[Ss].*', userInput) is not None:
                subtitleCount = len(title["subtitles"])
                userInput = raw_input("Select a subtitle [1-%s, N=None]: " % (subtitleCount))
                if re.match(r'^[1-9][0-9]*', userInput) is not None:
                    subtitle = int(userInput)
                    if subtitle > 0 and subtitle <= subtitleCount:
                        title["settings"]["subtitle_idx"] = subtitle-1
                elif re.match(r'^[Nn]*', userInput) is not None:
                    title["settings"]["subtitle_idx"] = None

            '''
            elif re.match(r'^[Cc].*',userInput) is not None:
                chapterCount = len(title["chapters"])
                userInput = raw_input("Select a chapter [1-%s, N=None]: " % (chapterCount))
                if re.match(r'^[1-9][0-9]*',userInput) is not None:
                    chapter = int(userInput)
                    if chapter > 0 and chapter <= chapterCount and chapter not in settings["selected_chapters"]:
                        title["settings"]["selected_chapters"].append(chapter)

                elif re.match(r'^[Nn]*',userInput) is not None:
                    title["settings"]["selected_chapters"] = []
            '''

            if re.match(r'^[Pp].*', userInput) is not None:
                self._playTitle(title)

            elif re.match(r'^[Bb].*', userInput) is not None:
                done = True

            if done:
                break

        return title

    def _getTitleSettings(self, title={}):
        settings = title.get("settings", None)

        if settings is not None:
            return settings

        settings = {
            "angle": 1,
            "audio_stream_idx": None,
            "subtitle_idx": None,
            "selected_chapters": []
        }

        audio_streams = title.get("audio_streams", [])
        if len(audio_streams) > 0:
            # use the first audio stream by default
            settings["audio_stream_idx"] = 0

        if self.preferredLang is not None and self.preferredLang != "":
            # audio/subtitle defaults based on preferred lang

            most_audio_channels = 0
            selected_audio_idx = None

            for audio_stream_idx, audio_stream in enumerate(audio_streams):
                aud_id = audio_stream.get("id")
                aud_lang = audio_stream.get("lang")
                aud_format = audio_stream.get("format")
                aud_channels = int(audio_stream.get("channels"))

                """
                debug("preferred_lang=%s, most_channels=%s, aud_lang=%s, aud_channels=%s" % (
                    self.preferredLang, most_audio_channels, aud_lang, aud_channels
                ))
                """

                if aud_lang == self.preferredLang and aud_channels > most_audio_channels:
                    # matched the preferred language with the most audio channels

                    most_audio_channels = aud_channels
                    selected_audio_idx = audio_stream_idx
                    settings["audio_stream_idx"] = selected_audio_idx

            if selected_audio_idx is not None:
                # we have a an audio stream in the preferred language, dump the subtitles
                settings["subtitle_idx"] = None
            else:
                # no match on audio stream for preferred languag
                subtitles = title.get("subtitles", [])
                for subtitle_idx, subtitle in enumerate(subtitles):
                    sub_id = subtitle.get("id")
                    sub_lang = subtitle.get("lang")
                    if sub_lang == self.preferredLang:
                        # matched the preferred language for subtitles
                        settings["subtitle_idx"] = subtitle_idx
                        break

        return settings

    def _processTitles(self, selectedTitles={}):
        for titleId in selectedTitles:
            title = selectedTitles[titleId]
            self._processTitle(title)

    def _processTitle(self, title):
        volumeName = self.discInfo["volume_id"]
        titleNumber = title["number"]
        if titleNumber < 10:
            titleNumber = "0%s" % (titleNumber)

        baseFile = "%s_title_%s" % (volumeName, titleNumber)
        copyFile = "%s.mpeg" % (baseFile)
        outFile = "%s.mp4" % (baseFile)

        ffmpegCmd = ["/usr/bin/ffmpeg", "-hide_banner", "-y", "-loglevel", "warning"]
        mplayerCmd = ["/usr/bin/mplayer", "-msgmodule", "-msglevel", "all=2", "-dvd-device", self.device, "dvd://%s" % (titleNumber)]

        print("\nTitle %s" % (titleNumber))

        # Copy source
        copy = True
        if os.path.isfile(copyFile):
            copy = False
            userInput = raw_input("Overwrite %s (y/[n]): " % (copyFile))
            if re.match(r'^[Yy].*', userInput) is not None:
                copy = True

        if copy is True:
            copyCmd = list(mplayerCmd)
            copyCmd.extend(["-dvdangle", str(title["settings"]["angle"]), "-dumpstream", "-dumpfile", copyFile])

            print("  Copying Audio/Video...")
            debug("copyCmd=%s" % (copyCmd))
            start = time.time()
            pipe = subprocess.Popen(copyCmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            outs, err = pipe.communicate()
            end = time.time()
            debug("err=%s" % (err))
            print("    Copy Duration: %s" % (end-start))

        inputOpts = ["-i", copyFile]
        videoOpts = []
        audioOpts = []
        subtitleOpts = []

        # Video encoding options
        vcodec = "libx264"
        vcompression = "veryfast"  # Testing shows "veryfast" is most efficient for time/compression ratio
        vquality = "20"  # 18 is supposedly "visually lossless", but still large file size. 20 still has good quality and much more reasonable file size

        videoOpts = ["-deinterlace", "-vcodec", vcodec, "-preset", vcompression, "-crf", vquality, "-map", "0:v"]

        # Audio encoding options
        audioStreamMap = None
        if title["settings"]["audio_stream_idx"] is not None:
            audioStreamIdx = title["settings"]["audio_stream_idx"]
            audioStream = title["audio_streams"][audioStreamIdx]

            cmd = ["/usr/bin/ffprobe", "-hide_banner", copyFile]
            debug("cmd=%s" % (cmd))
            pipe = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            outs, err = pipe.communicate()
            # debug("err=%s" %(err))

            lines = err.splitlines()
            for line in lines:
                debug("ffprobe line=%s" % (line))
                if "Stream" in line:
                    if "Audio: %s" % (audioStream["format"]) in line:
                        streamIdx = re.sub(r'.*Stream #([^\[]*).*', r'\1', line)
                        streamId = int(re.sub(r'.*\[0x(.*)\]:.*', r'\1', line), 16)

                        streamChannels = re.sub(r'.*Hz, ([^\(, ]+).*', r'\1', line)
                        if streamChannels == "mono":
                            streamChannels = 1
                        if streamChannels == "stereo":
                            streamChannels = 2
                        streamChannels = float(streamChannels)

                        streamBitRate = int(re.sub(r'.* ([^ ]+) kb/s', r'\1', line))

                        debug("streamIdx=%s, streamId=%s, streamChannels=%s, streamBitRate=%s" % (streamIdx, streamId, streamChannels, streamBitRate))
                        if streamId == int(audioStream["id"]):
                            # found a stream with the audio id we want

                            tmpAudioStreamMap = {
                                "number": streamIdx,
                                "channels": streamChannels,
                                "bitrate": streamBitRate
                            }
                            debug("setting tmpAudioStreamMap=%s" % (tmpAudioStreamMap))

                            if audioStreamMap is None:
                                audioStreamMap = tmpAudioStreamMap
                                debug("setting audioStreamMap=%s" % (audioStreamMap))

                            elif streamChannels >= audioStreamMap["channels"]:
                                # select a stream with most channels and highest bitrate in that order

                                if streamChannels > audioStreamMap["channels"]:
                                    audioStreamMap = tmpAudioStreamMap
                                    debug("using audioStreamMap=%s" % (audioStreamMap))

                                elif streamBitRate > audioStreamMap["bitrate"]:
                                    audioStreamMap = tmpAudioStreamMap
                                    debug("using audioStreamMap=%s" % (audioStreamMap))

        if audioStreamMap is not None:
            acodec = "aac"
            maxBitratePerChannel = 96
            channels = audioStreamMap["channels"]
            bitrate = audioStreamMap["bitrate"]

            bitratePerChannel = 1.0 * bitrate / channels
            if bitratePerChannel > maxBitratePerChannel:
                bitrate = maxBitratePerChannel * channels

            audioOpts = ["-acodec", acodec, "-strict", "experimental", "-b:a", "%sk" % (bitrate), "-map", audioStreamMap["number"]]

        # Copy subtitles and set subtitle encoding options
        if title["settings"]["subtitle_idx"] is not None:
            subtitleIdx = title["settings"]["subtitle_idx"]
            subtitle = title["subtitles"][subtitleIdx]

            if os.path.isfile("%s.idx" % (baseFile)):
                os.remove("%s.idx" % (baseFile))

            if os.path.isfile("%s.sub" % (baseFile)):
                os.remove("%s.sub" % (baseFile))

            subCopyCmd = list(mplayerCmd)
            subCopyCmd[0] = "/usr/bin/mencoder"
            subCopyCmd.extend(["-vobsubout", baseFile, "-slang", subtitle["lang"], "-nosound", "-ovc", "copy", "-o", "/dev/null"])

            print("  Copying Subtitles...")
            debug("subCopyCmd=%s" % (subCopyCmd))
            start = time.time()
            pipe = subprocess.Popen(subCopyCmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            outs, err = pipe.communicate()
            end = time.time()
            debug("err=%s" % (err))
            print("    Copy Duration: %s" % (end-start))

            inputOpts.extend(["-i", "%s.sub" % (baseFile), "-i", "%s.idx" % (baseFile)])
            subtitleOpts = ["-filter_complex", "[0:v][1:s]overlay[v]", "-map", "[v]"]

        encodeCmd = list(ffmpegCmd)
        encodeCmd.extend(inputOpts)
        encodeCmd.extend(videoOpts)
        encodeCmd.extend(audioOpts)
        encodeCmd.extend(subtitleOpts)
        encodeCmd.append(outFile)

        print("  Encoding...")
        debug("encodeCmd=%s" % (encodeCmd))
        start = time.time()
        pipe = subprocess.Popen(encodeCmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        outs, err = pipe.communicate()
        end = time.time()
        debug("err=%s" % (err))
        print("    Encode Duration: %s" % (end-start))

        print("")
        print("  File complete: %s" % (outFile))

    def _playTitle(self, title={}):
        titleNum = title["number"]
        # cmdArgs = ["/usr/bin/mplayer","-dvd-device",self.device,"dvd://%s" % (titleNum)]
        cmdArgs = ["/usr/bin/mpv", "-dvd-device", self.device, "dvd://%s" % (titleNum)]
        pipe = subprocess.Popen(cmdArgs, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        outs, err = pipe.communicate()


def debug(msg=None):
    if DEBUG is True and msg is not None:
        log("DEBUG: %s" % (msg))


def log(msg=None):
    if msg is not None:
        tm = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

        if LOG_FILE is not None:
            f = open(LOG_FILE, 'a')
            f.write("%s: %s\n" % (tm, msg))
            f.close()
        else:
            print("%s: %s" % (tm, msg))


def getArgValue(arg=None):
    val = None

    if arg is not None:
        for idx in range(1, len(sys.argv)):
            key = sys.argv[idx]
            if arg == key and len(sys.argv) > idx+1:
                val = sys.argv[idx+1]
                break

    return val


def main():
    device = getArgValue("--device")
    lang = getArgValue("--lang")

    log = getArgValue("--log")
    if log is not None:
        global LOG_FILE
        LOG_FILE = log

    if "--debug" in sys.argv:
        global DEBUG
        DEBUG = True

    ripper = Ripper(device, "DVD", lang)
    ripper.showMainMenu()


if __name__ == "__main__":
    main()
