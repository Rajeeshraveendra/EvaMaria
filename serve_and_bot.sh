#!/bin/bash
cd /EvaMaria
python3 -m http.server ${PORT:-10000} --directory /tmp &
python3 bot.py
wait
