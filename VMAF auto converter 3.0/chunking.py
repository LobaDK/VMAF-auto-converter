from json import loads
from math import floor
from multiprocessing import current_process, Value
from pathlib import Path
from queue import Empty
from subprocess import DEVNULL, run
from traceback import print_exc
from time import sleep

from vmaf import CheckVMAF


def calculate(settings: dict, file: str, chunk_calculate_queue, chunk_queue_event, chunk_range, process_failure, process_lock) -> None:
    """Calculates the start and end frame times for each chunk in three different ways depending on the chunk mode.
    Sends a tuple containing the frame_start, frame_end, iter and chunk filename to the queue for the generator to then pick up"""
    process_lock.acquire()
    print(f'\nStarting chunk calculations on {current_process().name}...')
    process_lock.release()
    start_frame = 0
    ii = 0
    try:
        if settings['chunk_mode'] == 1: # GENERATE TIMINGS FOR ENCODING WITH VIDEO SPLIT INTO n EQUAL SIZED CHUNKS
            #Iterate through the chunk_size shifted by 1, to start iter from 1
            for i in range(1, settings['chunk_size'] + 1):
                #Calculate end_frame by dividing it by the chunk_size and multiply with iter
                end_frame = floor((settings['total_frames']) / (settings['chunk_size']) * i)

                chunk = Path(settings['tmp_folder']) / 'prepared' / f'chunk{i}.{settings["output_extension"]}'
                chunk_calculate_queue.put((start_frame, end_frame, i, chunk))
        
                if not end_frame == settings['total_frames']:
                    start_frame = end_frame

                with chunk_range.get_lock():
                    chunk_range.value += 1

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

                chunk = Path(settings['tmp_folder']) / 'prepared' / f'chunk{ii}.{settings["output_extension"]}'
                chunk_calculate_queue.put((start_frame, end_frame, ii, chunk))
                
                if not end_frame == settings['total_frames']:
                    start_frame = end_frame

                with chunk_range.get_lock():
                    chunk_range.value += 1

        elif settings['chunk_mode'] == 3: # GENERATE TIMINGS FOR ENCODING WITH VIDEO SPLIT BY EVERY KEYFRAME
            # Use ffprobe to read each frame and it's flags. A flag of "K" means it's a keyframe.
            cmd = ['ffprobe', '-v', 'quiet', '-select_streams', 'v:0', '-show_entries', 'packet=pts_time,flags', '-of', 'json', file]
            p = run(cmd, capture_output=True)
            if p.returncode != 0:
                print('\nError reading keyframes!')
                process_failure.set()
                exit(1)
            
            frames = loads(p.stdout.decode())
            # Iterate through each frame
            for frame in frames['packets']:
                # If the frame has the keyframe flag and is not the first keyframe
                if 'K' in frame['flags'] and float(frame['pts_time']) > 0:
                    ii += 1
                    # Convert decimal seconds to frames
                    end_frame = int(float(frame['pts_time']) * settings['fps'])
                    chunk = Path(settings['tmp_folder']) / 'prepared' / f'chunk{ii}.{settings["output_extension"]}'
                    chunk_calculate_queue.put((start_frame, end_frame, ii, chunk))
                    
                    start_frame = end_frame

                    with chunk_range.get_lock():
                        chunk_range.value += 1

            ii += 1
            end_frame = settings['total_frames']
            chunk = Path(settings['tmp_folder']) / 'prepared' / f'chunk{ii}.{settings["output_extension"]}'
            chunk_calculate_queue.put((start_frame, end_frame, ii, chunk))
            with chunk_range.get_lock():
                chunk_range.value += 1
    
    except:
        print_exc()
        process_failure.set()

    chunk_queue_event.set()
    return

def generate(settings: dict, file: str, chunk_calculate_queue, chunk_queue_event, chunk_range, process_failure, process_lock, chunk_counter, chunk_generator_queue, chunk_generator_queue_event) -> None:
    """Creates a lossless H264 encoded chunk using the calculated start and end frame times from the calculatee thread. Frame times, iter and chunk name is delivered through a queue.
    When a chunk is generated, passes the same start and end frames, iter and a name for the generated and converted chunks"""
    print(f'\nGenerating chunks on {current_process().name}...')
    try:
        # Each calculated chunk increases the chunk_range.value by 1 
        # resulting in a constant loop until the generated chunks equal the amount of calculated chunks.
        # To prevent exiting in case the generated chunks has finished, but more frame times are still being calculated
        # the chunk_queue_event will prevent the loop from prematurely ending, as it is only set once calculations have finished.
        # If no data has been put in the queue within 30 seconds, it will be assumed that something has gone wrong in the calculate thread, and exit
        while chunk_counter.value != chunk_range.value or not chunk_queue_event.is_set():
            start_frame, end_frame, i, chunk = chunk_calculate_queue.get(timeout=30)
            with chunk_counter.get_lock():
                chunk_counter.value += 1

            arg = ['ffmpeg', '-n', '-ss', str(start_frame / settings['fps']), '-to', str(end_frame / settings['fps']), '-i', file, '-c:v', 'libx264', '-preset', 'faster', '-qp', '0', '-an', chunk]
            p = run(arg, stderr=DEVNULL)

            if p.returncode != 0:
                print(" ".join(arg))
                print(f'\nError generating chunk {i}')
                process_failure.set()
                exit(1)
            process_lock.acquire()
            print(f'\nGenerated chunk number {i} out of {chunk_range.value} chunks')
            process_lock.release()

            original_chunk = Path(settings['tmp_folder']) / 'prepared' / f'chunk{i}.{settings["output_extension"]}'
            converted_chunk = Path(settings['tmp_folder']) / 'converted' / f'chunk{i}.{settings["output_extension"]}'
            chunk_generator_queue.put((start_frame, end_frame, i, original_chunk, converted_chunk))

        chunk_generator_queue_event.set()

    except Empty:
        print('Failed to get calculated timeframes after 30 seconds of waiting.')
        process_failure.set()
        exit(1)

def convert(settings: dict, file: str, chunk_generator_queue, converted_counter, chunk_range, chunk_generator_queue_event, process_failure):
    print(f'\nConverting chunks on {current_process().name}...')
    attempt = 0
    try:
        while converted_counter.value != chunk_range.value or not chunk_generator_queue_event.is_set():
            crf_value = settings['initial_crf_value']
            crf_step = settings['initial_crf_step']
            start_frame, end_frame, i, original_chunk, converted_chunk = chunk_generator_queue.get(timeout=30)
            while True:
                with converted_counter.get_lock():
                    converted_counter.value += 1
                
                print(f'Converting chunk {i} out of {chunk_range.value}')

                arg = ['ffmpeg', '-ss', str(start_frame / int(settings['fps'])), '-to', str(end_frame / int(settings['fps'])), '-i', file, '-c:v', 'libsvtav1', '-crf', str(crf_value), '-b:v', '0', '-an', '-g', str(settings['keyframe_interval']), '-preset', str(settings['av1_preset']), '-pix_fmt', settings['pixel_format'], '-svtav1-params', f'tune={str(settings["tune_mode"])}', converted_chunk]
                if settings['ffmpeg_verbose_level'] == 0:
                    p = run(arg, stderr=DEVNULL, stdout=DEVNULL)
                else:
                    arg[1:1] = settings['ffmpeg_print']
                    p = run(arg)

                if p.returncode != 0:
                    print(" ".join(arg))
                    print('Error converting video!')
                    process_failure.set()
                    exit(1)

                if attempt >= settings['max_attempts']:
                    print('\nMaximum amount of allowed attempts exceeded. skipping...')
                    sleep(2)
                    break
                attempt += 1

                if CheckVMAF(settings, crf_value, crf_step, original_chunk, converted_chunk):
                    print(f'\nFinished processing chunk {i} out of {chunk_range.value}!')
                    break
                else:
                    continue


    except Empty:
        print('Failed to get calculated timeframes after 30 seconds of waiting.')
        process_failure.set()
        exit(1)

if __name__ == '__main__':
    print('This file should not be run as a standalone script!')