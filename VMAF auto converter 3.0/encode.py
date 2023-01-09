from threading import Thread
from pathlib import Path
from subprocess import DEVNULL, run
from time import sleep
from math import floor
from json import loads

from extractor import ExtractAudio, GetAudioMetadata, GetVideoMetadata
from temp import CreateTempFolder
from vmaf import CheckVMAF

def encoder(settings: dict, file: str) -> None:
    settings['attempt'] = 0
    settings = GetAudioMetadata(settings, file)
    settings = GetVideoMetadata(settings, file)

    if settings['chunk_mode'] == 0: #ENCODING WITHOUT CHUNKS
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
        start_frame = 0
        ii = 0
        if settings['chunk_mode'] == 1: # GENERATE TIMINGS FOR ENCODING WITH VIDEO SPLIT INTO n EQUAL SIZED CHUNKS
            #Iterate through the chunk_size shifted by 1, to start iter from 1
            for i in range(1, settings['chunk_size'] + 1):
                #Calculate end_frame by dividing it by the chunk_size and multiply with iter
                end_frame = floor((settings['total_frames']) / (settings['chunk_size']) * i)
                
                settings['frametimes'].append((start_frame, end_frame))

                start_frame = end_frame
                chunk = Path(settings['tmp_folder']) / 'prepared' / f'chunk{i}.{settings["output_extension"]}'
                settings['chunks'].append((i, chunk))
        
        elif settings['chunk_mode'] == 2: # GENERATE TIMINGS FOR ENCODING WITH VIDEO SPLIT INTO n LONG CHUNKS
            #Convert the total frames into seconds and iterate through them, with the step being the length of each chunk
            for i in range(0, int(settings['total_frames'] / settings['fps']), settings['chunk_length']):
                ii += 1
                #Calculate current iter + chunk length
                #If it exceeds or is equal to the total duration in decimal seconds
                #that will be the last chunk, and end_frame will instead be the last/total frames
                if not i + settings['chunk_length'] >= (settings['total_frames'] / settings['fps']):
                    end_frame = start_frame + (settings['chunk_length'] * settings['fps'])
                else:
                    end_frame = settings['total_frames']

                settings['frametimes'].append((start_frame, end_frame))

                start_frame = end_frame
                chunk = Path(settings['tmp_folder']) / 'prepared' / f'chunk{ii}.{settings["output_extension"]}'
                settings['chunks'].append((ii, chunk))

        elif settings['chunk_mode'] == 3: # GENERATE TIMINGS FOR ENCODING WITH VIDEO SPLIT BY EVERY KEYFRAME
            # TO DO: Reading keyframes from a 13 minute video takes like 3 minutes. Thread this and instead feed the chunk generator the frametimes and chunk names as they are calculated
            print('Reading keyframes, this might take a while...')
            # Use ffprobe to read each frame and it's flags. A flag of "K" means it's a keyframe.
            cmd = ['ffprobe', '-v', 'quiet', '-select_streams', 'v:0', '-show_entries', 'packet=pts_time,flags', '-of', 'json', file]
            p = run(cmd, capture_output=True)
            if p.returncode != 0:
                print('\nError reading keyframes!')
                exit(1)
            
            frames = loads(p.stdout.decode())
            # Iterate through each frame
            for frame in frames['packets']:
                # If the frame has the keyframe flag and is not the first keyframe
                if frame['flags'] == 'K_' and float(frame['pts_time']) > 0:
                    ii += 1
                    # Convert decimal seconds to frames
                    end_frame = int(float(frame['pts_time']) * settings['fps'])
                    settings['frametimes'].append((start_frame, end_frame))
                    start_frame = end_frame
                    chunk = Path(settings['tmp_folder']) / 'prepared' / f'chunk{ii}.{settings["output_extension"]}'
                    settings['chunks'].append((ii, chunk))
            end_frame = settings['total_frames']
            settings['frametimes'].append((start_frame, end_frame))
            chunk = Path(settings['tmp_folder']) / 'prepared' / f'chunk{ii + 1}.{settings["output_extension"]}'
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