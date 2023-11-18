#!/bin/bash

. /home/ubuntu/whisper-server-script/init-conda.sh
conda activate whisperx
cd /home/ubuntu/whisper-server-script; python run.py