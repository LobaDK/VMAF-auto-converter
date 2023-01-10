from multiprocessing import Event, Process, Queue, Value
from pathlib import Path
from subprocess import DEVNULL, run
from threading import Thread
from time import sleep

from chunking import calculate, generate
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
            AudioExtractThread = Thread(target=ExtractAudio, args=(settings, file))
            AudioExtractThread.start()
            
        chunk_calculate_queue = Queue()
        chunk_generator_queue = Queue()
        
        chunk_range = Value('i', 0)
        chunk_queue = Event()

        chunk_calculate_process = Process(target=calculate, args=(settings, file, chunk_calculate_queue, chunk_queue, chunk_range))
        chunk_calculate_process.start()
        
        chunk_generator_process = Process(target=generate, args=(settings, file, chunk_calculate_queue, chunk_queue, chunk_range))
        chunk_generator_process.start()
        
        chunk_calculate_process.join()
        chunk_generator_process.join()

        print('Converting...')

if __name__ == '__main__':
    print('This file should not be run as a standalone script!')