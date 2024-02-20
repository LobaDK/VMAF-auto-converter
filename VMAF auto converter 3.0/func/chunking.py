from json import loads
from math import floor
import multiprocessing
from pathlib import Path
from subprocess import DEVNULL, run
from time import sleep
from signal import signal, SIG_IGN, SIGINT
from sys import exit as sysexit

from func.logger import create_logger
from func.vmaf import CheckVMAF, VMAFError

EQUAL_SIZE_CHUNKS = 1
FIXED_LENGTH_CHUNKS = 2
KEYFRAME_BASED_CHUNKS = 3


def calculate(settings: dict,
              file: str,
              chunk_calculate_queue: multiprocessing.Queue,
              chunk_range: multiprocessing.Value,
              process_failure: multiprocessing.Event,) -> None:
    """
    Calculate the timings for encoding with video split into chunks based on the given settings.

    Args:
        settings (dict): A dictionary containing the configuration settings.
        file (str): The path to the video file.
        chunk_calculate_queue (multiprocessing.Queue): A queue for passing chunk information to the chunk generator.
        chunk_range (multiprocessing.Value): A shared value for tracking the number of calculated chunks.
        process_failure (multiprocessing.Event): An event indicating if an error has occurred across a process.

    Returns:
        None
    """
    # Ignore SIGINT from process running this method
    signal(SIGINT, SIG_IGN)
    logger = create_logger(settings['log_queue'], 'chunk_calculate')
    logger.info(f'Calculating chunks on {multiprocessing.current_process().name}.')
    start_frame = 0
    chunk_count = 0
    try:
        if settings['chunk_mode'] == EQUAL_SIZE_CHUNKS:  # GENERATE TIMINGS FOR ENCODING WITH VIDEO SPLIT INTO n EQUAL SIZED CHUNKS
            # Iterate through the chunk_size shifted by 1, to start iter from 1
            for i in range(1, settings['chunk_size'] + 1):
                # Calculate end_frame by dividing it by the chunk_size and multiply with iter
                end_frame = floor((settings['total_frames']) / (settings['chunk_size']) * i)

                # Create chunk variable with the folder structure and filename
                # and put it, alongside start_frame, end_frame and iter, in the queue for the chunk generator to use
                chunk = Path(settings['tmp_folder']) / 'prepared' / f'chunk{i}.{settings["output_extension"]}'
                chunk_calculate_queue.put((start_frame, end_frame, i, chunk))

                # Turn new start_frame into the old end_frame value, if end frame has not yet reached the end of the video
                if not end_frame == settings['total_frames']:
                    start_frame = end_frame

                # Increase calculated chunks by one
                with chunk_range.get_lock():
                    chunk_range.value += 1

        elif settings['chunk_mode'] == FIXED_LENGTH_CHUNKS:  # GENERATE TIMINGS FOR ENCODING WITH VIDEO SPLIT INTO n LONG CHUNKS
            # Convert the total frames into seconds and iterate through them, with the step being the length of each chunk
            for i in range(0, int(settings['total_frames'] / settings['fps']), settings['chunk_length']):
                chunk_count += 1
                # Calculate current iter + chunk length
                # If it exceeds or is equal to the total duration in decimal seconds
                # that will be the final chunk, and end_frame will instead be the last/total frames
                # This avoids end_frame stepping over the total amount of frames there are
                if not i + settings['chunk_length'] >= (settings['total_frames'] / settings['fps']):
                    end_frame = start_frame + (settings['chunk_length'] * settings['fps'])
                else:
                    end_frame = settings['total_frames']

                # Create chunk variable with the folder structure and filename
                # and put it, alongside start_frame, end_frame and iter, in the queue for the chunk generator to use
                chunk = Path(settings['tmp_folder']) / 'prepared' / f'chunk{chunk_count}.{settings["output_extension"]}'
                chunk_calculate_queue.put((start_frame, end_frame, chunk_count, chunk))

                # Turn new start_frame into the old end_frame value, if end frame has not yet reached the end of the video
                if not end_frame == settings['total_frames']:
                    start_frame = end_frame

                # Increase calculated chunks by one
                with chunk_range.get_lock():
                    chunk_range.value += 1

        elif settings['chunk_mode'] == KEYFRAME_BASED_CHUNKS:  # GENERATE TIMINGS FOR ENCODING WITH VIDEO SPLIT BY EVERY KEYFRAME
            # Use ffprobe to read each frame and it's flags. A flag of "K" means it's a keyframe.
            cmd = ['ffprobe', '-v', 'quiet', '-select_streams', 'v:0', '-show_entries', 'packet=pts_time,flags', '-of', 'json', file]
            p = run(cmd, capture_output=True)
            if p.returncode != 0:
                logger.error(f'Error calculating keyframes: {p.stderr.decode()}')
                process_failure.set()
                sysexit(1)

            frames = loads(p.stdout.decode())
            # Iterate through each frame
            for frame in frames['packets']:
                # If the frame has the keyframe flag and is not the first keyframe
                if 'K' in frame['flags'] and float(frame['pts_time']) > 0:
                    chunk_count += 1
                    # Convert decimal seconds to frames
                    end_frame = int(float(frame['pts_time']) * settings['fps'])

                    # Create chunk variable with the folder structure and filename
                    # and put it, alongside start_frame, end_frame and iter, in the queue for the chunk generator to use
                    chunk = Path(settings['tmp_folder']) / 'prepared' / f'chunk{chunk_count}.{settings["output_extension"]}'
                    chunk_calculate_queue.put((start_frame, end_frame, chunk_count, chunk))

                    # Set new start_frame as old end_frame.
                    # No check is done since the iterator will exit on the last keyframe regardless
                    start_frame = end_frame

                    # Increase calculated chunks by one
                    with chunk_range.get_lock():
                        chunk_range.value += 1

            chunk_count += 1
            end_frame = settings['total_frames']
            chunk = Path(settings['tmp_folder']) / 'prepared' / f'chunk{chunk_count}.{settings["output_extension"]}'
            # Put the last chunk in the queue for the chunk generator to use
            chunk_calculate_queue.put((start_frame, end_frame, chunk_count, chunk))
            with chunk_range.get_lock():
                chunk_range.value += 1

    except Exception as e:
        logger.error(f'Error calculating chunks: {e}')
        # Set a global event indicating an error has occurred across a process
        process_failure.set()

    chunk_calculate_queue.put(None, None, None, None)
    logger.info(f'Finished calculating chunks on {multiprocessing.current_process().name}.')
    return


def generate(settings: dict,
             file: str,
             chunk_calculate_queue: multiprocessing.Queue,
             chunk_range: multiprocessing.Value,
             process_failure: multiprocessing.Event,
             chunk_generator_queue: multiprocessing.Queue) -> None:
    """
    Generates chunks of a video file based on the given settings and queues them for further processing.

    Args:
        settings (dict): A dictionary containing the configuration settings.
        file (str): The path to the video file.
        chunk_calculate_queue (multiprocessing.Queue): A queue for receiving chunk calculation information.
        chunk_range (multiprocessing.Value): A shared value representing the total number of chunks.
        process_failure (multiprocessing.Event): An event indicating if a failure has occurred in the process.
        chunk_generator_queue (multiprocessing.Queue): A queue for sending chunk generation information.

    Returns:
        None
    """
    signal(SIGINT, SIG_IGN)

    logger = create_logger(settings['log_queue'], 'chunk_generator')

    logger.info(f'Generating chunks on {multiprocessing.current_process().name}.')

    while not process_failure.is_set():
        start_frame, end_frame, i, chunk = chunk_calculate_queue.get(block=True)

        # If the chunk is None, the calculation process has finished and the generator can exit
        if chunk is None:
            logger.info(f'Stopping {multiprocessing.current_process().name}.: No more chunks to generate')
            break

        arg = ['ffmpeg', '-n', '-ss', str(start_frame / settings['fps']), '-to', str(end_frame / settings['fps']), '-i', str(file), '-c:v', 'libx264', '-preset', 'ultrafast', '-qp', '0', '-an', str(chunk)]
        p = run(arg, stderr=DEVNULL)

        if p.returncode != 0:
            logger.error(f'Error generating chunk {i} with command: {" ".join(arg)}')
            # Set a global event indicating an error has occurred across a process
            process_failure.set()
            sysexit(1)

        logger.info(f'Finished generating chunk {i} out of {chunk_range.value}')

        # Combine folder paths to create chunk path and name for the original and converted chunk
        # and add them to the queue alongside the start_frame, end_frame and iter
        original_chunk = Path(settings['tmp_folder']) / 'prepared' / f'chunk{i}.{settings["output_extension"]}'
        converted_chunk = Path(settings['tmp_folder']) / 'converted' / f'chunk{i}.{settings["output_extension"]}'
        chunk_generator_queue.put((start_frame, end_frame, i, original_chunk, converted_chunk))

    chunk_generator_queue.put(None, None, None, None, None)
    return


def convert(settings: dict,
            file: str,
            chunk_generator_queue: multiprocessing.Queue,
            chunk_range: multiprocessing.Value,
            process_failure: multiprocessing.Event,
            chunk_concat_queue: multiprocessing.Queue) -> None:
    """
    Converts video chunks using FFmpeg with specified settings.

    Args:
        settings (dict): A dictionary containing various conversion settings.
        file (str): The path to the input video file.
        chunk_generator_queue (multiprocessing.Queue): A queue for receiving video chunks to convert.
        chunk_range (multiprocessing.Value): A shared value representing the total number of chunks.
        process_failure (multiprocessing.Event): An event indicating if the conversion process has failed.
        chunk_concat_queue (multiprocessing.Queue): A queue for storing the converted chunks.

    Returns:
        None
    """
    signal(SIGINT, SIG_IGN)
    logger = create_logger(settings['log_queue'], 'chunk_converter')

    logger.info(f'Converting chunks on {multiprocessing.current_process().name}.')

    while not process_failure.is_set():
        attempt = 0
        crf_value = settings['initial_crf_value']
        start_frame, end_frame, i, original_chunk, converted_chunk = chunk_generator_queue.get(block=True)
        if original_chunk is None:
            logger.info(f'Stopping {multiprocessing.current_process().name}: No more chunks to convert')
            break

        while not process_failure.is_set():
            crf_step = settings['initial_crf_step']
            logger.info(f'Converting chunk {i} with CRF value {crf_value} on attempt {attempt + 1} out of {settings["max_attempts"]}')

            arg = ['ffmpeg', '-ss', str(start_frame / int(settings['fps'])), '-to', str(end_frame / int(settings['fps'])), '-i', file, '-c:v', 'libsvtav1', '-crf', str(crf_value), '-b:v', '0', '-an', '-g', str(settings['keyframe_interval']), '-preset', str(settings['av1_preset']), '-pix_fmt', settings['pixel_format'], '-svtav1-params', f'tune={str(settings["tune_mode"])}', converted_chunk]
            if settings['ffmpeg_verbose_level'] == 0:
                p = run(arg, stderr=DEVNULL, stdout=DEVNULL)
            else:
                arg[1:1] = settings['ffmpeg_print']
                p = run(arg)

            if p.returncode != 0:
                logger.error(f'Error converting chunk {i} with command: {" ".join(arg)}')
                process_failure.set()
                sysexit(1)

            if attempt >= settings['max_attempts']:
                logger.error(f'Failed to convert chunk {i} after {settings["max_attempts"]} attempts. Skipping...')
                sleep(2)
                break
            attempt += 1

            try:
                retry = CheckVMAF(settings, crf_value, crf_step, original_chunk, converted_chunk, attempt)
            except VMAFError:
                logger.error(f'Error calculating VMAF for chunk {i} with CRF value {crf_value}. Skipping...')
                break
            if retry is False:
                logger.info(f'Finished converting chunk {i} out of {chunk_range.value} with CRF value {crf_value}')
                # Add a dictionary containing the iter and the chunk path and filename combined
                # Using the iter as the key allows for an easy way to use them in the correct order
                chunk_concat_queue.put({i: converted_chunk})
                break
            else:
                continue


if __name__ == '__main__':
    print('This file should not be run as a standalone script!')
