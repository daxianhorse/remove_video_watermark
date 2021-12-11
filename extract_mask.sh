#!/bin/bash
ffmpeg -y -i $1 -an -vf "select=eq(n\\,0)" -vframes 1 .cache/mask.png
