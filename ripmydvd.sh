#!/bin/bash

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
		if [ $DRY_RUN -eq 0 ] ; then
			echo -n "    Angle $angle selected. Confirm? (Y/n): "
			read tmp

			if [ "$tmp" = "n" ] ; then
				echo -n "    Which angle? "
				read tmp
				angleIsNum=`echo -n "$tmp" | grep '^[0-9]*$'`
				if [ "$angleIsNum" != "" ] ; then
					if [ $tmp -gt 0 -a $tmp -le $angles ] ; then
						angle=$tmp
					else
						angle="1"
					fi
				else
					angle="1"
				fi
			fi
		fi
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
					if [ $(echo "$audChannels >= $audioChannels" | bc) -ne 0 ] ; then
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
	subtitleLang=""
	if [ $subtitleCount -gt 0 ] ; then
		#Use first subtitle by default
		subtitleLang=`echo $subtitles | grep -o "ID_SID_[^=]*=[^ ]*" | head -1 | sed 's/.*=//g'`

		if [ $subtitleCount -gt 1 ] ; then
			for subtitle in $subtitles
			do
				#Find the subtitle that matches preferred language
				subLang=`echo $subtitle | sed 's/.*=//g'`

				doPrint "    Subtitle: language=$subLang"
				if [ $subLang = $preferredLang ] ; then
					subtitleLang="$subLang"
				fi
			done
		fi

		#HARD CODE A SUBTITLE STREAM HERE IF YOU NEED TO OVERRIDE AUTOSELECTION
		#subtitleLang="en"

		if [ "$audioLang" = "$preferredLang" ] ; then
			subtitleLang=""
			doPrint "    Skipping subtitle, audio is in preferred language"
		elif [ "$subtitleLang" != "$preferredLang" ] ; then
			subtitleLang=""
			doPrint "    Skipping subtitle, no match in preferred language"
		else
			doPrint "    Using subtitle: language=$subtitleLang"
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

	subtitleBase="$outDir/$name""_title_$titleName""_orig"
	copyFile="$outDir/$name""_title_$titleName""_orig.mpeg"
	outFile="$outDir/$name""_title_$titleName.mp4"

	###
	# Copy Title
	###

	writeCopyFile=1
	if [ -e $copyFile ] ; then
		doPrint ""
		echo -n "Overwrite $copyFile? [Y/n]: ";
		read tmp
		if [ "$tmp" = "n" ] ; then
			writeCopyFile=0
		fi
	fi

	if [ $writeCopyFile -eq 1 ] ; then
		mencOpts="-msglevel all=2 -dvd-device $DEVICE dvd://$title"

		if [ "$angle" != "" ] ; then
			mencOpts="$mencOpts -dvdangle $angle"
		fi

		if [ "$subtitleId" != "" ] ; then
			mencOpts="$mencOpts -sid $subtitleId"
		fi

		cmd="mplayer $mencOpts -dumpstream -dumpfile $copyFile"
		echo "$cmd" >> $LOG
		copyStart=`date +%s`
		doPrint ""
		doPrint "  Copying..."
		`$cmd >> $LOG 2>&1`
		copyEnd=`date +%s`

		#if [ "$subtitleId" != "" ] ; then
			#doPrint "  Copying subtitles..."
			#cmd="mencoder $mencOpts -vobsubout $subtitleBase -vobsuboutid $subtitleLang -nosound -ovc copy -o /dev/null"
			#echo "$cmd" >> $LOG
			#`$cmd >> $LOG 2>&1`
		#fi

		copyDuration=`echo "$copyEnd - $copyStart" | bc -l`
		doPrint "  Copy duration: $copyDuration seconds"
	fi

	###
	# Encode Title
	###

	ffmpegOpts="-y -hide_banner -loglevel warning"

	vcodec="libx264"
	#vcodec="copy"
	ffmpegOpts="$ffmpegOpts -deinterlace -map 0:v -vcodec $vcodec"

	if [ "$vcodec" = "libx264" ] ; then
		#compression="veryslow"
		#compression="slower"
		#compression="slow"
		#compression="medium"
		#compression="fast"
		#compression="faster"
		compression="veryfast"  #Testing shows "veryfast" is most efficient for time/compression ratio
		#compression="superfast"
		#compression="ultrafast"
		quality="20" #18 is supposedly "visually lossless", but still large file size. 20 still has good quality and much more reasonable file size
		ffmpegOpts="$ffmpegOpts -preset $compression -crf $quality"
	fi

	acodec="aac"
	#acodec="copy"
	ffmpegOpts="$ffmpegOpts -acodec $acodec"
	if [ "$acodec" = "aac" ] ; then
		ffmpegOpts="$ffmpegOpts -strict experimental"

		actualAudioChannels=`echo $audioChannels | sed 's/\./+/g' | bc -l`
		#NOTE: AAC use maximum of 96 kbps per channel of audio output for good audio quality
		maxAudioBitRate=`echo "96 * $actualAudioChannels" | bc -l`

		cmd="ffprobe -hide_banner $copyFile"
		echo "$cmd" >> $LOG
		audioBitRate=`$cmd |& grep "Stream.*Audio" | sed 's/ *kb\/s.*//g' | sed 's/.* //g' | grep -v '^[^0-9]*$'`
		if [ $audioBitRate -gt $maxAudioBitRate ] ; then
			audioBitRate=$maxAudioBitRate
		fi
		ffmpegOpts="$ffmpegOpts -b:a $audioBitRate""k"
	fi

	if [ "$audioId" != "" ] ; then
		audioStreamIds=`ffprobe -hide_banner $copyFile |& grep Stream | grep Audio | sed 's/.*\[0x\(.*\)\].*/\1/g'`
		audioStreamIdx=0
		for audioStreamId in $audioStreamIds
		do
			audioStreamIdDec=`echo "ibase=16; $audioStreamId" | bc`

			if [ "x$audioId" = "x$audioStreamIdDec" ] ; then
				ffmpegOpts="$ffmpegOpts -map 0:a:$audioStreamIdx"
				break
			fi
			audioStreamIdx=`echo "$audioStreamIdx + 1" | bc -l`
		done
	fi

	doPrint ""
	doPrint "  Encoding..."

	cmd="ffmpeg -i $copyFile $ffmpegOpts $outFile"
	echo "$cmd" >> $LOG
	encStart=`date +%s`
	`$cmd >> $LOG 2>&1`
	end=`date +%s`

	encodingDuration=`echo "$end - $encStart" | bc -l`
	processDuration=`echo "$end - $start" | bc -l`

	doPrint "  Encoding duration: $encodingDuration seconds"
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
