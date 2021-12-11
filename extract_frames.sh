#!/bin/bash
ffmpeg -y -i $1 -an -vf "select=gte(n\\,$2)" -vsync vfr -vframes $3 $4/im-%d.png
