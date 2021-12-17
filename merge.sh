#!/bin/bash
ls dst/ -v | grep .mkv | awk '{printf "file '\''dst/%s'\''\n", $0}' > list.txt
ffmpeg -y -f concat -safe 0 -i list.txt -c copy output.mkv
rm *.txt
