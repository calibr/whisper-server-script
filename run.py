from dotenv import load_dotenv

load_dotenv()


import yt_dlp
import boto3
import subprocess
import os
import sys
import re
from filelock import FileLock, Timeout
import time
import whisperx_transcribe
import json
bucket = os.environ['BUCKET']
hf_token = os.environ['HF_TOKEN']

# init boto3 S3
s3 = boto3.client('s3', region_name='us-east-1')
s3_res = boto3.resource('s3')
ec2 = boto3.resource('ec2', region_name='us-east-1')

# extracts model type from file name, model type is located after substring model_ and ends with _
def extract_model_name(filename):
    regex = r"model_([a-z]+)_"
    match = re.search(regex, filename)
    model_name = match.group(1) if match else None
    if model_name == "large":
        model_name = "large-v1"
    if model_name == None:
        model_name = "medium"
    return model_name

# extracts language from file name, language is located after substring lang_ and ends with _
def extract_language(filename):
    regex = r"lang_([a-z]+)_"
    match = re.search(regex, filename)
    return match.group(1) if match else None

def extract_video_id(url):
    # Regular expression to extract the video id
    regex = r"(?<=v=)[^&#]+|(?<=be/)[^&#]+"
    match = re.search(regex, url)
    return match.group(0) if match else None

def extract_audio(video_path, audio_path):
    command = ['ffmpeg', '-i', video_path, '-vn', '-y', audio_path]
    subprocess.run(command, check=True)


def runffmpeg(input_path, output_path):
    command = ['ffmpeg', '-i', input_path, '-y', output_path]
    subprocess.run(command, check=True)

def list_s3_files():
    files = []
    paginator = s3.get_paginator('list_objects_v2')

    for page in paginator.paginate(Bucket=bucket, Prefix='input/'):
        if 'Contents' in page:
            for obj in page['Contents']:
                files.append(obj['Key'])

    return files

# downloads youtube video by its id
def download(video_id: str) -> str:
    video_id = video_id.strip()
    video_url = f'https://www.youtube.com/watch?v={video_id}'
    ydl_opts = {
        'format': 'm4a/bestaudio/best',
        'paths': {'home': 'audio/'},
        'outtmpl': {'default': '%(id)s.%(ext)s'},
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'm4a',
        }]
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        error_code = ydl.download([video_url])
        if error_code != 0:
            raise Exception('Failed to download video')

    return f'audio/{video_id}.m4a'

def process():
    whisper_models = {}

    for file in list_s3_files():
        print("Processing", file)

        model_type_needed = extract_model_name(file)
        language = extract_language(file)

        input_file = 'input.' + file.split('.').pop()
        try:
            s3.download_file(bucket, file, input_file)
        except FileNotFoundError as e:
            print("Fail downloading file", file, e, "Skipping the file and going to the next one")
            continue

        audio_file = 'audio/audio.m4a'
        audio_file_mp3 = 'audio/audio.mp3'
        if os.path.isfile(audio_file):
            os.remove(audio_file)

        # if file starts with url_ then process it as an url
        if file.startswith('input/url_'):
            with open(input_file, 'r') as fp:
                # Read the contents of the file
                file_contents = fp.read()
            youtube_url = file_contents
            print("Processing youtube url", youtube_url)
            video_id = extract_video_id(youtube_url)
            try:
                audio_file = download(video_id)
            except Exception as e:
                print("Fail processing file", file, e)
                s3_res.Object(bucket, file).delete()
                continue
        else:
            try:
                extract_audio(input_file, audio_file)
            except Exception as e:
                print("Fail processing file", file, e)
                s3_res.Object(bucket, file).delete()
                continue

        runffmpeg(audio_file, audio_file_mp3)

        print("use model", model_type_needed, "language", language)

        transcription = whisperx_transcribe.transcribe(audio_file_mp3, model_type_needed, language=language)

        s3_res.Object(bucket, 'output/' + os.path.basename(file) + '.txt').put(Body=json.dumps(transcription))
        s3_res.Object(bucket, file).delete()
try:
    with FileLock("/tmp/transcribe.lock", 3):
        process()
        print("Done")
except Timeout:
    print(f"Another instance of this script is running. Exiting.")
    sys.exit()
