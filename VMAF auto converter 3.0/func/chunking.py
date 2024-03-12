from json import loads
from math import floor
import multiprocessing
from pathlib import Path
from subprocess import DEVNULL, run
from time import sleep
import sys
import os
import signal

from func.logger import create_logger
from func.vmaf import CheckVMAF, VMAFError
from func.manager import ExceptionHandler

EQUAL_SIZE_CHUNKS = 1
FIXED_LENGTH_CHUNKS = 2
KEYFRAME_BASED_CHUNKS = 3


def calculate(settings: dict,
              file: str,
              chunk_range: multiprocessing.Value,
              process_failure: multiprocessing.Event,) -> None:
    """
    Calculate the timings for encoding with video split into chunks based on the given settings.

    Args:
        settings (dict): A dictionary containing the configuration settings.
        file (str): The path to the video file.
        chunk_range (multiprocessing.Value): A shared value for tracking the number of calculated chunks.
        process_failure (multiprocessing.Event): An event indicating if an error has occurred across a process.

    Returns:
        None
    """
    handler = ExceptionHandler(settings['log_queue'], settings['manager_queue'])
    sys.excepthook = handler.handle_exception
    logger = create_logger(settings['log_queue'], 'chunk_calculate')

    logger.info('Calculating chunks')
    start_frame = 0
    chunk_count = 0
    try:
        while not process_failure.is_set():
            if settings['chunk_mode'] == EQUAL_SIZE_CHUNKS:  # GENERATE TIMINGS FOR ENCODING WITH VIDEO SPLIT INTO n EQUAL SIZED CHUNKS
                logger.debug(f'Calculating {settings["chunk_size"]} chunks')
                # Iterate through the chunk_size shifted by 1, to start iter from 1
                for i in range(1, settings['chunk_size'] + 1):
                    # Calculate end_frame by dividing it by the chunk_size and multiply with iter
                    end_frame = floor((settings['total_frames']) / (settings['chunk_size']) * i)

                    # Create chunk variable with the folder structure and filename
                    # and put it, alongside start_frame, end_frame and iter, in the queue for the chunk generator to use
                    chunk = Path(settings['tmp_folder']) / 'prepared' / f'chunk{i}.{settings["output_extension"]}'
                    logger.debug(f'Adding chunk {i} to queue with start_frame {start_frame} and end_frame {end_frame}')
                    settings['chunk_calculate_queue'].put((start_frame, end_frame, i, chunk))

                    # Turn new start_frame into the old end_frame value, if end frame has not yet reached the end of the video
                    if not end_frame == settings['total_frames']:
                        start_frame = end_frame

                    # Increase calculated chunks by one
                    with chunk_range.get_lock():
                        chunk_range.value += 1
                break

            elif settings['chunk_mode'] == FIXED_LENGTH_CHUNKS:  # GENERATE TIMINGS FOR ENCODING WITH VIDEO SPLIT INTO n LONG CHUNKS
                logger.debug(f'Calculating chunks with length {settings["chunk_length"]} seconds')
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
                    logger.debug(f'Adding chunk {chunk_count} to queue with start_frame {start_frame} and end_frame {end_frame}')
                    settings['chunk_calculate_queue'].put((start_frame, end_frame, chunk_count, chunk))

                    # Turn new start_frame into the old end_frame value, if end frame has not yet reached the end of the video
                    if not end_frame == settings['total_frames']:
                        start_frame = end_frame

                    # Increase calculated chunks by one
                    with chunk_range.get_lock():
                        chunk_range.value += 1
                break

            elif settings['chunk_mode'] == KEYFRAME_BASED_CHUNKS:  # GENERATE TIMINGS FOR ENCODING WITH VIDEO SPLIT BY EVERY KEYFRAME
                # Use ffprobe to read each frame and it's flags. A flag of "K" means it's a keyframe.
                logger.debug('Calculating chunks based on keyframes')
                arg = ['ffprobe', '-v', 'quiet', '-select_streams', 'v:0', '-show_entries', 'packet=pts_time,flags', '-of', 'json', file]
                try:
                    p = run(arg, capture_output=True)
                except KeyboardInterrupt:
                    process_failure.set()
                if p.returncode != 0:
                    logger.error(f'Error calculating keyframes: {p.stderr.decode()} with command: {" ".join(str(item) for item in arg)}')
                    process_failure.set()
                    os.kill(os.getpid(), signal.SIGINT)

                frames = loads(p.stdout.decode())
                # Iterate through each frame
                for frame in frames['packets']:
                    # If the frame has the keyframe flag and is not the first keyframe
                    if 'K' in frame['flags'] and float(frame['pts_time']) > 0:
                        logger.debug(f'Found keyframe at {frame["pts_time"]}')
                        chunk_count += 1
                        # Convert decimal seconds to frames
                        end_frame = int(float(frame['pts_time']) * settings['fps'])

                        # Create chunk variable with the folder structure and filename
                        # and put it, alongside start_frame, end_frame and iter, in the queue for the chunk generator to use
                        chunk = Path(settings['tmp_folder']) / 'prepared' / f'chunk{chunk_count}.{settings["output_extension"]}'
                        logger.debug(f'Adding chunk {chunk_count} to queue with start_frame {start_frame} and end_frame {end_frame}')
                        settings['chunk_calculate_queue'].put((start_frame, end_frame, chunk_count, chunk))

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
                logger.debug(f'Adding chunk {chunk_count} to queue with start_frame {start_frame} and end_frame {end_frame}')
                settings['chunk_calculate_queue'].put((start_frame, end_frame, chunk_count, chunk))
                with chunk_range.get_lock():
                    chunk_range.value += 1
                break
        else:
            if process_failure.is_set():
                os.kill(os.getpid(), signal.SIGINT)

    except Exception as e:
        logger.error(f'Error calculating chunks: {e}')
        # Set a global event indicating an error has occurred across a process
        process_failure.set()
        os.kill(os.getpid(), signal.SIGINT)
    else:
        # Ensure each chunk generator process is stopped
        for _ in range(settings['chunk_threads']):
            settings['chunk_calculate_queue'].put(None)
        logger.info('Finished calculating chunks')
        return


def generate(settings: dict,
             file: str,
             chunk_range: multiprocessing.Value,
             process_failure: multiprocessing.Event,
             i: int) -> None:
    """
    Generates chunks of a video file based on the given settings and queues them for further processing.

    Args:
        settings (dict): A dictionary containing the configuration settings.
        file (str): The path to the video file.
        chunk_range (multiprocessing.Value): A shared value representing the total number of chunks.
        process_failure (multiprocessing.Event): An event indicating if a failure has occurred in the process.
        i (int): The process number.

    Returns:
        None
    """
    handler = ExceptionHandler(settings['log_queue'], settings['manager_queue'])
    sys.excepthook = handler.handle_exception

    logger = create_logger(settings['log_queue'], f'chunk_generator({i})')

    logger.info('Generating chunk')
    try:
        while not process_failure.is_set():
            item = settings['chunk_calculate_queue'].get(block=True)
            if isinstance(item, tuple) and len(item) == 4:
                logger.debug(f'Received item {item}')
                start_frame, end_frame, i, chunk = item
            elif isinstance(item, None.__class__):
                settings['chunk_generator_queue'].put(None)
                logger.info(f'Stopping {multiprocessing.current_process().name}: No more chunks to generate')
                break
            else:
                logger.error(f'Invalid item received from chunk_calculate_queue: {item}')
                process_failure.set()
                os.kill(os.getpid(), signal.SIGINT)

            arg = ['ffmpeg', '-nostdin', '-n', '-ss', str(start_frame / settings['fps']), '-to', str(end_frame / settings['fps']), '-i', str(file), '-c:v', 'libx264', '-preset', 'ultrafast', '-qp', '0', '-an', str(chunk)]
            try:
                p = run(arg, stderr=DEVNULL)
            except KeyboardInterrupt:
                process_failure.set()

            if p.returncode != 0:
                logger.error(f'Error generating chunk {i} with command: {" ".join(str(item) for item in arg)}')
                # Set a global event indicating an error has occurred across a process
                process_failure.set()
                os.kill(os.getpid(), signal.SIGINT)

            logger.info(f'Finished generating chunk {i} out of {chunk_range.value}')

            # Combine folder paths to create chunk path and name for the original and converted chunk
            # and add them to the queue alongside the start_frame, end_frame and iter
            original_chunk = Path(settings['tmp_folder']) / 'prepared' / f'chunk{i}.{settings["output_extension"]}'
            converted_chunk = Path(settings['tmp_folder']) / 'converted' / f'chunk{i}.{settings["output_extension"]}'
            logger.debug(f'Adding chunk {i} to queue with start_frame {start_frame} and end_frame {end_frame}')
            settings['chunk_generator_queue'].put((start_frame, end_frame, i, original_chunk, converted_chunk))
        else:
            if process_failure.is_set():
                os.kill(os.getpid(), signal.SIGINT)

    except Exception as e:
        logger.error(f'Error generating chunks: {e}')
        # Set a global event indicating an error has occurred across a process
        process_failure.set()
        os.kill(os.getpid(), signal.SIGINT)
    else:
        return


def convert(settings: dict,
            file: str,
            chunk_range: multiprocessing.Value,
            process_failure: multiprocessing.Event,
            i: int) -> None:
    """
    Converts video chunks using FFmpeg with specified settings.

    Args:
        settings (dict): A dictionary containing various conversion settings.
        file (str): The path to the input video file.
        chunk_range (multiprocessing.Value): A shared value representing the total number of chunks.
        process_failure (multiprocessing.Event): An event indicating if the conversion process has failed.
        i (int): The process number.

    Returns:
        None
    """
    handler = ExceptionHandler(settings['log_queue'], settings['manager_queue'])
    sys.excepthook = handler.handle_exception
    logger = create_logger(settings['log_queue'], f'chunk_converter({i})')
    vmaf_logger = create_logger(settings['log_queue'], f'VMAF({i})')  # Create a new logger for VMAF and pass it to avoid duplicate log messages

    try:
        while not process_failure.is_set():
            attempt = 0
            crf_value = settings['initial_crf_value']
            item = settings['chunk_generator_queue'].get(block=True)
            if isinstance(item, tuple) and len(item) == 5:
                start_frame, end_frame, i, original_chunk, converted_chunk = item
            elif isinstance(item, None.__class__):
                logger.info(f'Stopping {multiprocessing.current_process().name}: No more chunks to convert')
                break
            else:
                logger.error(f'Invalid item received from chunk_generator_queue: {item}')
                process_failure.set()
                os.kill(os.getpid(), signal.SIGINT)

            crf_step = settings['initial_crf_step']
            while True:
                logger.info(f'Converting chunk {i} with CRF value {crf_value} on attempt {attempt + 1} out of {settings["max_attempts"]}')

                # TODO: Longer/Larger chunks, or a high preset, can cause the process to take a very long time.
                # Maybe add some code that occasionally prints the progress of the conversion process?
                arg = ['ffmpeg', '-nostdin', '-ss', str(start_frame / int(settings['fps'])), '-to', str(end_frame / int(settings['fps'])), '-i', file, '-c:v', 'libsvtav1', '-crf', str(crf_value), '-b:v', '0', '-an', '-g', str(settings['keyframe_interval']), '-preset', str(settings['av1_preset']), '-pix_fmt', settings['pixel_format'], '-svtav1-params', f'tune={str(settings["tune_mode"])}', converted_chunk]
                try:
                    if settings['ffmpeg_verbose_level'] == 0:
                        p = run(arg, stderr=DEVNULL, stdout=DEVNULL)
                    else:
                        arg[1:1] = settings['ffmpeg_print']
                        p = run(arg)
                except KeyboardInterrupt:
                    process_failure.set()

                if p.returncode != 0:
                    logger.error(f'Error converting chunk {i} with command: {" ".join(str(item) for item in arg)}')
                    process_failure.set()
                    os.kill(os.getpid(), signal.SIGINT)

                if attempt >= settings['max_attempts']:
                    logger.error(f'Failed to convert chunk {i} after {settings["max_attempts"]} attempts. Skipping...')
                    sleep(2)
                    break
                attempt += 1

                try:
                    retry, crf_value = CheckVMAF(settings, crf_value, crf_step, original_chunk, converted_chunk, attempt, vmaf_logger)
                except VMAFError:
                    logger.error(f'Error calculating VMAF for chunk {i} with CRF value {crf_value}. Skipping...')
                    break
                if retry is False:
                    logger.info(f'Finished converting chunk {i} out of {chunk_range.value} with CRF value {crf_value}')
                    # Add a dictionary containing the iter and the chunk path and filename combined
                    # Using the iter as the key allows for an easy way to use them in the correct order later on
                    settings['chunk_concat_queue'].put({i: converted_chunk})
                    break
                else:
                    continue
        else:
            if process_failure.is_set():
                os.kill(os.getpid(), signal.SIGINT)
    except Exception as e:
        logger.error(f'Error converting chunks: {e}')
        # Set a global event indicating an error has occurred across a process
        process_failure.set()
        os.kill(os.getpid(), signal.SIGINT)
    else:
        return


if __name__ == '__main__':
    print('This file should not be run as a standalone script!')
