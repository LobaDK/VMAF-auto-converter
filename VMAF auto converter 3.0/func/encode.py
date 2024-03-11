from multiprocessing import Event, Process, Value
from pathlib import Path
from subprocess import DEVNULL, run
from threading import Thread
from time import sleep
import sys

from func.chunking import calculate, generate, convert
from func.extractor import ExtractAudio, GetAudioMetadata, GetVideoMetadata
from func.temp import CreateTempFolder
from func.vmaf import CheckVMAF, VMAFError
from func.logger import create_logger
from func.manager import ExceptionHandler, custom_exit

NO_CHUNK = 0


def encoder(settings: dict, file: str) -> None:
    handler = ExceptionHandler(settings['log_queue'], settings['manager_queue'])
    sys.excepthook = handler.handle_exception

    logger = create_logger(settings['log_queue'], 'encoder')

    settings['attempt'] = 0
    # Get and add metadata from the input file, to settings
    settings.update(GetAudioMetadata(file, settings))
    settings.update(GetVideoMetadata(file, settings))

    if settings['chunk_mode'] == NO_CHUNK:  # ENCODING WITHOUT CHUNKS
        crf_value = settings['initial_crf_value']

        # Run infinite loop that only breaks if the quality is within range
        # max attempts has exceeded, or an error has occurred
        while True:
            logger.info(f'Converting {Path(file).stem}...')
            crf_step = settings['initial_crf_step']
            arg = ['ffmpeg', '-nostdin', '-i', file, '-c:a', 'aac', '-c:v', 'libsvtav1', '-crf', str(crf_value), '-b:v', '0', '-b:a', str(settings['audio_bitrate']), '-g', str(settings['keyframe_interval']), '-preset', str(settings['av1_preset']), '-pix_fmt', settings['pixel_format'], '-svtav1-params', f'tune={str(settings["tune_mode"])}', '-movflags', '+faststart', f'{Path(settings["output_dir"]) / Path(file).stem}.{settings["output_extension"]}']
            if settings['ffmpeg_verbose_level'] == 0:
                p = run(arg, stderr=DEVNULL, stdout=DEVNULL)
            else:
                arg[1:1] = settings['ffmpeg_print']
                p = run(arg)
            if p.returncode != 0:
                logger.error(f'Error converting {Path(file).stem} with arguments: {arg}')
                custom_exit(settings['manager_queue'])
            print('\nVideo encoding finished!')

            if settings['attempt'] >= settings['max_attempts']:
                logger.info(f'Maximum amount of allowed attempts exceeded for {Path(file).stem}. Skipping...')
                sleep(2)
                return
            settings['attempt'] += 1

            converted_file = Path(settings['output_dir']) / f'{Path(file).stem}.{settings["output_extension"]}'
            try:
                retry = CheckVMAF(settings, crf_value, crf_step, file, converted_file, settings['attempt'])
                if not retry:
                    logger.info(f'Finished converting file {Path(converted_file).stem}')
                    break
                else:
                    continue
            except VMAFError:
                break
    else:
        CreateTempFolder(settings['tmp_folder'], settings['log_queue'])
        # Create empty list for starting and joining processes
        processlist = []

        # Create event used to signal that a process ran into an error
        process_failure = Event()

        # Create process-safe int variable for storing the amount of calculated chunks
        chunk_range = Value('i', 0)

        while not process_failure.is_set():
            # If audio is detected, run separate thread that extracts the audio
            if settings['detected_audio_stream']:
                AudioExtractThread = Thread(target=ExtractAudio,
                                            args=(settings,
                                                  file,
                                                  process_failure))
                AudioExtractThread.start()

            # Create, start and add chunk calculator process to process list
            chunk_calculate_process = Process(target=calculate,
                                              args=(settings,
                                                    file,
                                                    chunk_range,
                                                    process_failure))
            chunk_calculate_process.start()
            processlist.append(chunk_calculate_process)

            # Create, start and add N chunk generator processes to the process list
            for _ in range(settings['chunk_threads']):
                chunk_generator_process = Process(target=generate,
                                                  args=(settings,
                                                        file,
                                                        chunk_range,
                                                        process_failure))
                chunk_generator_process.start()
                processlist.append(chunk_generator_process)

            # Clear process list and create, start and add N chunk converter processes to the process list
            for _ in range(settings['chunk_threads']):
                chunk_converter_process = Process(target=convert,
                                                  args=(settings,
                                                        file,
                                                        chunk_range,
                                                        process_failure))
                chunk_converter_process.start()
                processlist.append(chunk_converter_process)

            # Join and wait for all processes to finish
            for p in processlist:
                p.join()

            # Wait for the audio extraction to finish before combining the chunks and audio
            if AudioExtractThread.is_alive():
                logger.info('Waiting for audio extraction to finish...')
                AudioExtractThread.join()
            break
        else:
            if process_failure.is_set():
                logger.error('An error occurred during chunking. Exiting...')
                custom_exit(settings['manager_queue'])

        concat(settings, file)


def concat(settings: dict, file: str) -> None:
    """
    Concatenates video chunks into a single video file.

    Args:
        settings (dict): A dictionary containing various settings for the concatenation process.
        file (str): The name of the output file.

    Returns:
        None
    """
    logger = create_logger(settings['log_queue'], 'concat')

    # Create empty dictionary for storing the iter as key and filename as value, from queue
    file_list = {}

    logger.info('Getting the chunks from the queue...')
    # As long as the queue is not empty, grab the next item in the queue
    while not settings['chunk_concat_queue'].empty():
        _file_list = settings['chunk_concat_queue'].get()
        file_list.update(_file_list)
        logger.debug(f'Added {_file_list} to file list')

    logger.info('Creating file list...')
    # Create a file that contains the list of files to concatenate
    concat_file = open(Path(settings['tmp_folder']) / 'concatlist.txt', 'a')
    for i in range(1, len(file_list) + 1):
        concat_file.write(f"file '{file_list[i]}'\n")
        logger.debug(f'Wrote {file_list[i]} to concatlist.txt')
    concat_file.close()

    if settings['detected_audio_stream']:
        arg = ['ffmpeg', '-nostdin', '-safe', '0', '-f', 'concat', '-i', Path(settings['tmp_folder']) / 'concatlist.txt', '-i', Path(settings['tmp_folder']) / f'audio.{settings["audio_codec_name"]}', '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-c:a', 'aac', '-b:a', str(settings['audio_bitrate']), '-movflags', '+faststart', f'{Path(settings["output_dir"]) / Path(file).stem}.{settings["output_extension"]}']
    else:
        arg = ['ffmpeg', '-nostdin', '-safe', '0', '-f', 'concat', '-i', Path(settings['tmp_folder']) / 'concatlist.txt', '-c:v', 'copy', '-an', '-movflags', '+faststart', f'{Path(settings["output_dir"]) / Path(file).stem}.{settings["output_extension"]}']

    logger.info('Combining chunks...')

    if settings['ffmpeg_verbose_level'] == 0:
        p = run(arg, stderr=DEVNULL, stdout=DEVNULL)
    else:
        arg[1:1] = settings['ffmpeg_print']
        p = run(arg)

    if p.returncode != 0:
        logger.error(f'Error combining chunks with arguments: {arg}')
        custom_exit(settings['manager_queue'])

    logger.info('Chunks successfully combined!')
    sleep(3)


if __name__ == '__main__':
    print('This file should not be run as a standalone script!')
