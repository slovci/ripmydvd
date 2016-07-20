#!/bin/sh

# Copyright 2016 Steve Lovci
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

#export DVDCSS_METHOD="key"
#export DVDCSS_METHOD="title"
export DVDCSS_VERBOSE="0"

#NOTE: if CSS decryption is not working correctly try umounting disc first then
# eject disc and retry or try changing DVDCSS_METHOD variable

#video bitrate calculation to acheive a filesize of 50MB per 10 minutes of video:
#(50 MB * 8192 [converts MB to kilobits]) / 600 seconds = ~683 kilobits/s total bitrate
#683k - 128k (desired audio bitrate) = 555k video bitrate
#
#512MB/hour: 512*8192/3600 = 1165 total bitrate
#1165 total bitrate - 192 audio bitrate = 973 video bitrate

preferredVideoBitRate="973" #kbits/sec
preferredAudioBitRate="192" #kbits/sec

preferredLang="en"

date=`date +%Y-%m-%d-%H-%M`
LOG="./rip-$date.log"
DRY_RUN=0
DEVICE="/dev/sr0"
if [ ! -e $DEVICE ] ; then
	DEVICE="/dev/dvd"
fi

if [ ! -e $DEVICE ] ; then
	echo "Could not find DVD device"
	exit 1
fi



doPrint() {
	newLine="1"
	if [ "$1" = "-n" ] ; then
		newLine="0"
		shift
	fi

	msg="$1"

	if [ $newLine -eq "1" ] ; then
		echo "$msg"
		echo "$msg" >> $LOG
	else
		echo -n "$msg"
		echo -n "$msg" >> $LOG
	fi
}

processTitle() {
	start=`date +%s`
	
	title=$1
	titleIdx=$2

	doPrint ""
	doPrint "Processing title $title: ($titleIdx of $titleCount)"
	cmd="mencoder -dvd-device $DEVICE dvd://$title -msgmodule -msglevel all=2:open=6:identify=6 -o /dev/null"
	echo "$cmd" >> $LOG
	out=`$cmd |& egrep "OPEN|IDENTIFY"`
	echo "$out" >> $LOG

	duration=`echo $out | grep -o "TITLE_$title""_LENGTH=[^ ]*" | sed 's/[^=]*=//g'`
	angles=`echo $out | grep -o "TITLE_$title""_ANGLES=[^ ]*" | sed 's/[^=]*=//g'`
	audioStreams=`echo $out | sed 's/OPEN: audio stream/\nOPEN: audio stream/g' | grep "OPEN: audio stream" | sed 's/.*format:.*(\(.*\)).*language: \([^ ]*\).*aid: \([0-9]*\).*/audio_stream:\1,\2,\3/g'`
	audioStreamCount=`echo $audioStreams | grep -o "audio_stream:" | wc -l`
	subtitles=`echo $out | grep -o "ID_SID_[^=]*=[^ ]*"`
	subtitleCount=`echo $subtitles | grep -o "ID_SID_" | wc -l`

	doPrint "  Duration: $duration seconds"

	#setup video
	doPrint "  Video Angles: $angles"
	angle=""
	if [ $angles -gt 1 ] ; then
		angle="1"
		doPrint "    Using video angle $angle"
	fi

	#setup audio	
	doPrint "  Audio Streams: $audioStreamCount"
	audioId=""
	audioLang=""
	audioChannels="0"
	
	if [ $audioStreamCount -gt 0 ] ; then
		#select the first audio stream by default
		
		audioStream=`echo $audioStreams | grep -o "audio_stream:[^ ]*" | head -1 | sed 's/audio_stream://g'`
		audioId=`echo $audioStream | cut -d, -f 3`
		audioLang=`echo $audioStream | cut -d, -f 2`
		audioChannels=`echo $audioStream | cut -d, -f 1`
		if [ "$audioChannels" = "mono" ] ; then
			audioChannels="1"
		elif [ "$audioChannels" = "stereo" ] ; then
			audioChannels="2"
		fi
	fi
	
	if [ $audioStreamCount -gt 1 ] ; then
		for audioStream in $audioStreams
		do
			#Find audio streams that match preferred language
			#select the one with the most channels

			audioStream=`echo $audioStream | sed 's/audio_stream://g'`
			audId=`echo $audioStream | cut -d, -f 3`
			audLang=`echo $audioStream | cut -d, -f 2`
			audChannels=`echo $audioStream | cut -d, -f 1`

			if [ "$audChannels" = "mono" ] ; then
				audChannels="1"
			elif [ "$audChannels" = "stereo" ] ; then
				audChannels="2"
			fi

			doPrint "    Audio Stream: id=$audId, language=$audLang, channels=$audChannels"

			if [ "$audLang" != "" ] ; then
				if [ $audLang = $preferredLang ] ; then
					if [ $(echo "$audChannels > $audioChannels" | bc) -ne 0 ] ; then
						audioId="$audId"
						audioLang="$audLang"
						audioChannels="$audChannels"
					fi
				fi
			fi
		done
		
		doPrint "    Using audio stream: id=$audioId, language=$audioLang, channels=$audioChannels"
	fi
	

	#setup subtitle
	doPrint "  Subtitles: $subtitleCount"
	subtitleId=""
	subtitleLang=""
	if [ $subtitleCount -gt 0 ] ; then
		if [ "$audioLang" = "$preferredLang" ] ; then
			doPrint "    Skipping subtitle, audio is in preferred language"
		else
			#Use first subtitle by default
			subtitleId=`echo $subtitles | grep -o "ID_SID_[^=]*=[^ ]*" | head -1 | sed 's/.*SID_\(.*\)_LANG.*/\1/g'`
			subtitleLang=`echo $subtitles | grep -o "ID_SID_[^=]*=[^ ]*" | head -1 | sed 's/.*=//g'`
				
			if [ $subtitleCount -gt 1 ] ; then
				for subtitle in $subtitles
				do
					#Find the subtitle that matches preferred language
					subId=`echo $subtitle | sed 's/.*SID_\(.*\)_LANG.*/\1/g'`
					subLang=`echo $subtitle | sed 's/.*=//g'`

					doPrint "    Subtitle: id=$subId, language=$subLang"
					if [ $subLang = $preferredLang ] ; then
						subtitleId="$subId"
						subtitleLang="$subLang"
					fi
				done
			fi
			
			#HARD CODE A SUBTITLE STREAM HERE TO OVERRIDE AUTOSELECTION
			#subtitleId="1"
			#subtitleLang="en"
			
			if [ "$subtitleLang" != "$preferredLang" ] ; then
				#Don't use subtitles if it is not in preferred language
				subtitleId=""
				subtitleLang=""
				doPrint "    Skipping subtitle, no match in preferred language"
			else
				doPrint "    Using subtitle: id=$subtitleId, language=$subtitleLang"
			fi
		fi
	fi
	
	if [ $DRY_RUN -eq 1 ] ; then
		#Don't actually copy or encode anything
		return
	fi
	
	titleName=$title
	if [ $title -lt 10 ] ; then
		titleName="0$title"
	fi

	videoFile="$outDir/$name""_title_$titleName.vid"
	audioFile="$outDir/$name""_title_$titleName.aud"
	subtitleFile="$outDir/$name""_title_$titleName"
	outFile="$outDir/$name""_title_$titleName.mp4"

	mencVideoOpts=""
	if [ "$angle" != "" ] ; then
		mencVideoOpts="-dvdangle $angle"
	fi

	mencOpts="-msglevel all=2 -dvd-device $DEVICE dvd://$title"
	doPrint ""
	doPrint "  Copying video..."
	cmd="mplayer $mencOpts $mencVideoOpts -dumpvideo -dumpfile $videoFile"
	echo "$cmd" >> $LOG
	`$cmd >> $LOG 2>&1`
	
	videoBitRate="$preferredVideoBitRate"
	videoFileSize="0"
	if [ -e $videoFile ] ; then
		videoFileSize=`ls -s $videoFile | cut -d" " -f1`
	fi
	
	if [ $videoFileSize -gt 0 ] ; then
		cmd="ffprobe -hide_banner $videoFile"
		echo "$cmd" >> $LOG
		vidBitRate=`$cmd |& grep Stream | sed 's/ *kb\/s.*//g' | sed 's/.* //g'`
		if [ $vidBitRate -lt $preferredVideoBitRate ] ; then
			videoBitRate="$vidBitRate"
		fi
		
		doPrint "    Video bitrate: $vidBitRate kb/s"
		if [ $videoBitRate -ne $vidBitRate ] ; then
			doPrint "    Using video bitrate: $videoBitRate kb/s"
		fi
	else
		doPrint "    No video stream found during copy"
	fi

	audioFileSize="0"
	audioBitRate="$preferredAudioBitRate"
	if [ "$audioId" != "" ] ; then
		doPrint "  Copying audio..."
		cmd="mplayer $mencOpts -aid $audioId -dumpaudio -dumpfile $audioFile"
		echo "$cmd" >> $LOG
		`$cmd >> $LOG 2>&1`
		
		
		audioFileSize=`ls -s $audioFile | cut -d" " -f1`
		if [ $audioFileSize -gt 0 ] ; then
			cmd="ffprobe -hide_banner $audioFile"
			echo "$cmd" >> $LOG
			audBitRate=`$cmd |& grep Stream | sed 's/ *kb\/s.*//g' | sed 's/.* //g'`
			if [ $audBitRate -lt $preferredAudioBitRate ] ; then
				audioBitRate="$audBitRate"
			fi
			
			doPrint "    Audio bitrate: $audBitRate kb/s"
			if [ $audioBitRate -ne $audBitRate ] ; then
				doPrint "    Using audio bitrate: $audioBitRate kb/s"
			fi
		else
			doPrint "    No audio stream found during copy" 
		fi
	fi
	
	if [ $videoFileSize -eq 0 -a $audioFileSize -eq 0 ] ; then
		doPrint ""
		doPrint "  Skipping encoding, no video or audio streams" 
		return
	fi
	
	ffmpegOpts="-y -hide_banner -loglevel warning"
	if [ $videoFileSize -gt 0 ] ; then 
		ffmpegOpts="$ffmpegOpts -i $videoFile"
	fi
	
	if [ $audioFileSize -gt 0 ] ; then 
		ffmpegOpts="$ffmpegOpts -i $audioFile"
	fi
	
	if [ "$subtitleId" != "" ] ; then
		doPrint "  Copying subtitles..."
		cmd="mencoder $mencOpts -vobsubout $subtitleFile -vobsubid $subtitleId -nosound -ovc copy -o /dev/null"
		echo "$cmd" >> $LOG
		`$cmd >> $LOG 2>&1`
		
		ffmpegOpts="$ffmpegOpts -i $subtitleFile.sub -i $subtitleFile.idx -filter_complex [0:v][2:s]overlay"
	fi
	
	if [ $videoFileSize -gt 0 ] ; then 
		ffmpegOpts="$ffmpegOpts -vcodec libx264 -preset medium -b:v $videoBitRate""k"
	fi
	
	if [ $audioFileSize -gt 0 ] ; then 
		ffmpegOpts="$ffmpegOpts -acodec aac -b:a $audioBitRate""k -strict experimental"
	fi
	
	#estimated fileSize (MB) = duration * totalBitRate [abitrate kbps + vbitrate kbps ] / 8192 [convert kbits to mbytes]
	fileSize=`echo "$duration * ($audioBitRate + $videoBitRate) / 8" | bc -l | sed 's/\(.*\...\).*/\1/g'`
	fileSizeUnit="KB"
	if [ $(echo "$fileSize > 1024" | bc) -ne 0 ] ; then
		fileSize=`echo "$fileSize / 1024" | bc -l | sed 's/\(.*\...\).*/\1/g'`
		fileSizeUnit="MB"
	fi
	
	doPrint ""
	doPrint "  Estimated file size: $fileSize $fileSizeUnit"
	
	doPrint ""
	doPrint "  Encoding pass 1..."
	cmd="ffmpeg $ffmpegOpts -pass 1 -f mp4 /dev/null"
	echo "$cmd" >> $LOG
	`$cmd >> $LOG 2>&1`

	doPrint "  Encoding pass 2..."
	cmd="ffmpeg $ffmpegOpts -pass 2 $outFile"
	echo "$cmd" >> $LOG
	`$cmd >> $LOG 2>&1`

	end=`date +%s`
	processDuration=`echo "$end - $start" | bc -l`
	doPrint ""
	doPrint "  Processing duration: $processDuration seconds"
}

#### START MAIN ####

doPrint "Reading disc..."
cmd="mencoder -dvd-device $DEVICE dvd://99 -msgmodule -msglevel all=2:identify=6 -o /dev/null"
echo "$cmd" >> $LOG
out=`$cmd |& grep IDENTIFY`
echo "$out" >> $LOG
	
id=`echo $out | grep -o "DISC_ID=[^ ]*" | sed 's/.*DISC_ID=//g'`
name=`echo $out | sed 's/.*VOLUME_ID=//g'`
titleCount=`echo $out | sed 's/.*TITLES=//g' | sed 's/ .*//g'`

doPrint ""
doPrint "Found disc volume: $name ($id)"

outDir="./$name"
if [ ! -d "$outDir" ] ; then
	mkdir -p $outDir
fi

doPrint ""
doPrint "Files will be written to $outDir"

titles=${1-""}
if [ "$titles" = "-n" ] ; then
	shift 1
	DRY_RUN="1"
fi

titles=${1-""}
if [ "$titles" != "" ] ; then
	titleCount="0"
	for title in $titles
	do
		titleCount=`echo "$titleCount + 1" | bc -l`
	done
else
	title="1"
	while [ $title -le $titleCount ]
	do
		titles="$titles $title"
		title=`echo "$title + 1" | bc -l`
	done
fi

titleIdx="1"
for title in $titles
do
	processTitle $title $titleIdx
	titleIdx=`expr $titleIdx + 1`
done
