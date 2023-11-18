Whisper script to be run on AWS to fetch files from S3, process (transcribe) them and upload them back to S3.

# Setup

- Create conda env: `conda create --name whisperx python=3.10`
- Activate conda env: `conda activate whisperx`
- Install dependencies: `pip install -r requirements.txt`
- Install pytorch: `conda install pytorch==2.0.0 torchaudio==2.0.0 pytorch-cuda=11.8 -c pytorch -c nvidia`