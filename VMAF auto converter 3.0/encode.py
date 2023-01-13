from multiprocessing import Event, Process, Queue, Value, Lock
from pathlib import Path
from subprocess import DEVNULL, run
from threading import Thread
from time import sleep
from sys import exit as sysexit

from chunking import calculate, generate, convert
from extractor import ExtractAudio, GetAudioMetadata, GetVideoMetadata
from temp import CreateTempFolder
from vmaf import CheckVMAF


def encoder(settings: dict, file: str) -> None:
    settings['attempt'] = 0
    settings = GetAudioMetadata(settings, file)
    settings = GetVideoMetadata(settings, file)

    if settings['chunk_mode'] == 0: #ENCODING WITHOUT CHUNKS
        crf_value = settings['initial_crf_value']
        while True:
            print(f'\nConverting {Path(file).stem}...')
            crf_step = settings['initial_crf_step']
            arg = ['ffmpeg', '-i', file, '-c:a', 'aac', '-c:v', 'libsvtav1', '-crf', str(crf_value), '-b:v', '0', '-b:a', str(settings['audio_bitrate']), '-g', str(settings['keyframe_interval']), '-preset', str(settings['av1_preset']), '-pix_fmt', settings['pixel_format'], '-svtav1-params', f'tune={str(settings["tune_mode"])}', '-movflags', '+faststart', f'{Path(settings["output_dir"]) / Path(file).stem}.{settings["output_extension"]}']
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

            converted_file = Path(settings['output_dir']) / f'{Path(file).stem}.{settings["output_extension"]}'
            retry, crf_value, crf_step = CheckVMAF(settings, crf_value, crf_step, file, converted_file, settings['attempt'])
            if retry == False:   
                print(f'\nFinished converting file {Path(converted_file).stem}')
                break
            elif retry == 'error':
                process_failure.set()
            else:
                continue
    else:
        CreateTempFolder(settings)
        processlist = []
        process_lock = Lock()

        process_failure = Event()
    
        chunk_calculate_queue = Queue()
        chunk_generator_queue = Queue()
        chunk_concat_queue = Queue()
        
        chunk_range = Value('i', 0)
        
        audio_extract_finished = Event()
        chunk_calculation_started = Event()
        chunk_calculation_finished = Event()
        chunk_generator_started = Event()
        chunk_generator_finished = Event()

        if settings['detected_audio_stream']:
            AudioExtractThread = Thread(target=ExtractAudio, args=(settings, file, process_failure, audio_extract_finished))
            AudioExtractThread.start()
            
        if process_failure.is_set():
            with process_lock:
                print('\nOne or more critical errors encountered in other threads/processes, exiting...')
            sysexit(1)

        chunk_calculate_process = Process(target=calculate, args=(settings, file, chunk_calculate_queue, chunk_calculation_started, chunk_calculation_finished, chunk_range, process_failure, process_lock))
        chunk_calculate_process.start()
        processlist.append(chunk_calculate_process)
        
        for _ in range(settings['chunk_threads']):
            chunk_generator_process = Process(target=generate, args=(settings, file, chunk_calculate_queue, chunk_calculation_started, chunk_calculation_finished, chunk_range, process_failure, process_lock, chunk_generator_queue, chunk_generator_started, chunk_generator_finished))
            chunk_generator_process.start()
            processlist.append(chunk_generator_process)

        for p in processlist:
            p.join()

        if process_failure.is_set():
            with process_lock:
                print('\nOne or more critical errors encountered in other threads/processes, exiting...')
            sysexit(1)

        processlist.clear()
        for _ in range(settings['chunk_threads']):
            chunk_converter_process = Process(target=convert, args=(settings, file, chunk_generator_queue, chunk_range, chunk_generator_started, process_failure, process_lock, chunk_generator_finished, chunk_concat_queue))
            chunk_converter_process.start()
            processlist.append(chunk_converter_process)

        for p in processlist:
            p.join()

        if process_failure.is_set():
            with process_lock:
                print('\nOne or more critical errors encountered in other threads/processes, exiting...')
            sysexit(1)

        #Wait for the audio extraction to finish before combining the chunks and audio
        if not audio_extract_finished.is_set():
            with process_lock:
                print('\nWaiting for audio to be extracted...')
            audio_extract_finished.wait()

        concat(settings, file, chunk_concat_queue)

def concat(settings: dict, file: str, chunk_concat_queue) -> None:
    file_list = {}
    while not chunk_concat_queue.empty():
        file_list.update(chunk_concat_queue.get())
    
    concat_file = open(Path(settings['tmp_folder']) / 'concatlist.txt', 'a')
    for i in range(len(file_list)):
        concat_file.write(f"file '{file_list[i + 1]}'\n")
    concat_file.close()

    if settings['detected_audio_stream']:
        arg = ['ffmpeg', '-safe', '0', '-f', 'concat', '-i', Path(settings['tmp_folder']) / 'concatlist.txt', '-i', Path(settings['tmp_folder']) / f'audio.{settings["audio_codec_name"]}', '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-c:a', 'aac', '-b:a', str(settings['audio_bitrate']), '-movflags', '+faststart', f'{Path(settings["output_dir"]) / Path(file).stem}.{settings["output_extension"]}']
    else:
        arg = ['ffmpeg', '-safe', '0', '-f', 'concat', '-i', Path(settings['tmp_folder']) / 'concatlist.txt', '-c:v', 'copy', '-an', '-movflags', '+faststart', f'{Path(settings["output_dir"]) / Path(file).stem}.{settings["output_extension"]}']

    print('\nCombining chunks...')

    if settings['ffmpeg_verbose_level'] == 0:
        p = run(arg, stderr=DEVNULL, stdout=DEVNULL)
    else:
        arg[1:1] = settings['ffmpeg_print']
        p = run(arg)

    if p.returncode != 0:  
        print(" ".join(arg))
        print('\nError converting video!')
        sysexit(1)

    print('\nChunks successfully combined!')
    sleep(3)

if __name__ == '__main__':
    print('This file should not be run as a standalone script!')