from multiprocessing import Event, Process, Queue, Value, Lock
from pathlib import Path
from subprocess import DEVNULL, run
from threading import Thread
from time import sleep
from sys import exit as sysexit
from colorama import init, Fore
from random import randrange

from func.chunking import calculate, generate, convert
from func.extractor import ExtractAudio, GetAudioMetadata, GetVideoMetadata
from func.temp import CreateTempFolder
from func.vmaf import CheckVMAF

init(autoreset=True)
colors = [Fore.RED, Fore.GREEN, Fore.YELLOW, Fore.BLUE, Fore.MAGENTA, Fore.CYAN]

def encoder(settings: dict, file: str) -> None:
    settings['attempt'] = 0
    # Get and add metadata from the input file, to settings
    settings = GetAudioMetadata(settings, file)
    settings = GetVideoMetadata(settings, file)

    if settings['chunk_mode'] == 0: #ENCODING WITHOUT CHUNKS
        crf_value = settings['initial_crf_value']
        
        # Run infinite loop that only breaks if the quality is within range 
        # max attempts has exceeded, or an error has occured
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
        # Create empty list for starting and joining processes
        processlist = []
        
        # Create lock used for printing and avoiding race conditions
        process_lock = Lock()

        # Create event used to check for process errors
        process_failure = Event()
    
        # Create queues used to pass data between the chunk calculator, chunk generator, chunk converter and concatenator
        chunk_calculate_queue = Queue()
        chunk_generator_queue = Queue()
        chunk_concat_queue = Queue()
        
        # Create process-safe int variable for storing the amount of calculated chunks
        chunk_range = Value('i', 0)
        
        # Create events for audio extractor, chunk calculator and chunk generator starting/finishing
        audio_extract_finished = Event()
        chunk_calculation_started = Event()
        chunk_calculation_finished = Event()
        chunk_generator_started = Event()
        chunk_generator_finished = Event()

        # If audio is detected, run separate non-blocking thread that extracts the audio
        if settings['detected_audio_stream']:
            AudioExtractThread = Thread(target=ExtractAudio, args=(settings, file, process_failure, audio_extract_finished, colors.pop(randrange(len(colors)))))
            AudioExtractThread.start()
            
        if process_failure.is_set():
            with process_lock:
                print('\nOne or more critical errors encountered in other threads/processes, exiting...')
            sysexit(1)

        # Create, start and add chunk calculator process to process list
        chunk_calculate_process = Process(target=calculate, args=(settings, file, chunk_calculate_queue, chunk_calculation_started, chunk_calculation_finished, chunk_range, process_failure, process_lock, colors.pop(randrange(len(colors)))))
        chunk_calculate_process.start()
        processlist.append(chunk_calculate_process)
        
        # Create, start and add N chunk generator processes to the process list
        for i in range(settings['chunk_threads']):
            chunk_generator_process = Process(target=generate, args=(settings, file, chunk_calculate_queue, chunk_calculation_started, chunk_calculation_finished, chunk_range, process_failure, process_lock, chunk_generator_queue, chunk_generator_started, chunk_generator_finished, colors[i]))
            chunk_generator_process.start()
            processlist.append(chunk_generator_process)

        # Join and wait for each process to complete
        for p in processlist:
            p.join()

        if process_failure.is_set():
            with process_lock:
                print('\nOne or more critical errors encountered in other threads/processes, exiting...')
            sysexit(1)

        # Clear process list and create, start and add N chunk converter processes to the process list
        processlist.clear()
        for i in range(settings['chunk_threads']):
            chunk_converter_process = Process(target=convert, args=(settings, file, chunk_generator_queue, chunk_range, chunk_generator_started, process_failure, process_lock, chunk_generator_finished, chunk_concat_queue, colors[i]))
            chunk_converter_process.start()
            processlist.append(chunk_converter_process)

        # Join and wait for each process to complete
        for p in processlist:
            p.join()

        if process_failure.is_set():
            with process_lock:
                print('\nOne or more critical errors encountered in other threads/processes, exiting...')
            sysexit(1)

        # Wait for the audio extraction to finish before combining the chunks and audio
        if not audio_extract_finished.is_set():
            with process_lock:
                print('\nWaiting for audio to be extracted...')
            audio_extract_finished.wait()

        concat(settings, file, chunk_concat_queue)

def concat(settings: dict, file: str, chunk_concat_queue) -> None:
    # Create empty dictionary for storing the iter as key and filename as value, from queue
    file_list = {}

    # As long as the queue is not empty, grab the next item in the queue
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