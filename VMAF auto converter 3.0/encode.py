from threading import Thread
from pathlib import Path
from subprocess import DEVNULL, run
from time import sleep
from math import floor

from extractor import ExtractAudio, GetAudioMetadata, GetVideoMetadata
from temp import CreateTempFolder
from vmaf import CheckVMAF

def encoder(settings: dict, file: str) -> None:
    settings['attempt'] = 0
    settings = GetAudioMetadata(settings, file)
    settings = GetVideoMetadata(settings, file)

    if settings['chunk_mode'] == 0:
        while True:
            settings['crf_step'] = settings['initial_crf_step']
            arg = ['ffmpeg', '-i', file, '-c:a', 'aac', '-c:v', 'libsvtav1', '-crf', str(settings['crf_value']), '-b:v', '0', '-b:a', str(settings['audio_bitrate']), '-g', str(settings['keyframe_interval']), '-preset', str(settings['av1_preset']), '-pix_fmt', settings['pixel_format'], '-svtav1-params', f'tune={str(settings["tune_mode"])}', '-movflags', '+faststart', f'{Path(settings["output_dir"]) / Path(file).stem}.{settings["output_extension"]}']
            if settings['ffmpeg_verbose_level'] == 0:
                p = run(arg, stderr=DEVNULL, stdout=DEVNULL)
            else:
                arg[1:1] = settings['ffmpeg_print']
                p = run(arg)
            if p.returncode != 0:
                print(" ".join(arg))
                print('\nError converting video! Skipping...')
                return
            print('\nVideo encoding finished!')

            if settings['attempt'] >= settings['max_attempts']:
                print('\nMaximum amount of allowed attempts exceeded. skipping...')
                sleep(2)   
                return
            settings['attempt'] += 1

            output_file = Path(settings['output_dir']) / f'{Path(file).stem}.{settings["output_extension"]}'
            if CheckVMAF(settings, file, output_file):
                break
            else:
                continue
    else:
        CreateTempFolder(settings)
    
        if settings['detected_audio_stream']:
            print('\nExtracting audio on secondary thread...')
            AudioExtractThread = Thread(target=ExtractAudio, args=(settings, file))
            AudioExtractThread.start()
        
        settings['chunks'] = []
        settings['frametimes'] = []
        ii = 0
        start_frame = 0
        if settings['chunk_mode'] == 1:
            for _ in range(settings['chunk_size']):
                ii += 1
                end_frame = floor((int(settings['total_frames']) / int(settings['chunk_size']) * ii))
                
                settings['frametimes'].append((start_frame, end_frame))

                start_frame = end_frame + 1
                chunk = Path(settings['tmp_folder']) / 'prepared' / f'chunk{ii}.{settings["output_extension"]}'
                settings['chunks'].append((ii, chunk))

    print('\nPreparing chunks on main thread...')

def encode_without_chunks(settings: dict, file: str) -> None:
    settings['attempt'] = 0
    settings = GetAudioMetadata(settings, file)
    
    while True:
        settings['crf_step'] = settings['initial_crf_step']
        arg = ['ffmpeg', '-i', file, '-c:a', 'aac', '-c:v', 'libsvtav1', '-crf', str(settings['crf_value']), '-b:v', '0', '-b:a', str(settings['audio_bitrate']), '-g', str(settings['keyframe_interval']), '-preset', str(settings['av1_preset']), '-pix_fmt', settings['pixel_format'], '-svtav1-params', f'tune={str(settings["tune_mode"])}', '-movflags', '+faststart', f'{Path(settings["output_dir"]) / Path(file).stem}.{settings["output_extension"]}']
        if settings['ffmpeg_verbose_level'] == 0:
            p = run(arg, stderr=DEVNULL, stdout=DEVNULL)
        else:
            arg[1:1] = settings['ffmpeg_print']
            p = run(arg)
        if p.returncode != 0:
            print(" ".join(arg))
            print('\nError converting video! Skipping...')
            return
        print('\nVideo encoding finished!')

        if settings['attempt'] >= settings['max_attempts']:
            print('\nMaximum amount of allowed attempts exceeded. skipping...')
            sleep(2)   
            return
        settings['attempt'] += 1

        output_file = Path(settings['output_dir']) / f'{Path(file).stem}.{settings["output_extension"]}'
        if CheckVMAF(settings, file, output_file):
            break
        else:
            continue

def encode_with_divided_chunks(settings: dict, file: str) -> None:
    settings['attempt'] = 0
    detected_audio_stream, audio_codec_name = GetAudioMetadata(settings, file)
    total_frames, fps = GetVideoMetadata(file)
    total_chunks = settings['chunk_size']

    CreateTempFolder(settings)

    if detected_audio_stream:
        sleep(0.1)
        print('\nExtracting audio on secondary thread...')
        AudioExtractThread = Thread(target=ExtractAudio, args=(settings, file, audio_codec_name))
        AudioExtractThread.start()

    print('\nPreparing chunks on main thread...')
    sleep(20)

def encode_with_length_chunks(settings: dict, file: str) -> None:
    settings['attempt'] = 0

def encode_with_keyframe_interval_chunks(settings: dict, file: str) -> None:
    settings['attempt'] = 0

if __name__ == '__main__':
    print('This file should not be run as a standalone script!')