from pathlib import Path
from threading import Thread

from extractor import ExtractAudio, GetAudioMetadata, GetVideoMetadata


def encode_without_chunks(settings: dict, physical_cores: int, file: str):
    attempt = 0
    Thread(target=GetAudioMetadata, name='AudioMetadataExtractor', args=(settings, file)).start()
    #print(detected_audio_stream, audio_codec_name)

def encode_with_divided_chunks(settings: dict, physical_cores: int, file: str):
    attempt = 0

def encode_with_length_chunks(settings: dict, physical_cores: int, file: str):
    attempt = 0

def encode_with_keyframe_interval_chunks(settings: dict, physical_cores: int, file: str):
    attempt = 0

if __name__ == '__main__':
    print('This file should not be run as a standalone script!')