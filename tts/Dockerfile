FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 5002

CMD ["tts-server", "--model_name", "tts_models/en/ljspeech/tacotron2-DDC", "--port", "5002"]
