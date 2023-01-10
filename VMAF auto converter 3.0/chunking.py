from json import loads
from math import floor
from multiprocessing import current_process
from pathlib import Path
from queue import Empty
from subprocess import DEVNULL, run


def calculate(settings: dict, file: str, chunk_calculate_queue, chunk_queue, chunk_range) -> None:
    print(f'\nStarting chunk calculations on {current_process().name}...')
    start_frame = 0
    ii = 0
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

    chunk_queue.set()
    return

def generate(settings: dict, file: str, chunk_calculate_queue, chunk_queue, chunk_range) -> None:
    ii = 0
    print(f'\nGenerating chunks on {current_process().name}...')
    try:
        while ii < chunk_range.value or not chunk_queue.is_set():
            start_frame, end_frame, i, chunk = chunk_calculate_queue.get(timeout=30)
            ii = i

            arg = ['ffmpeg', '-n', '-ss', str(start_frame / settings['fps']), '-to', str(end_frame / settings['fps']), '-i', file, '-c:v', 'libx264', '-preset', 'ultrafast', '-qp', '0', '-an', chunk]
            p = run(arg, stderr=DEVNULL)

            if p.returncode != 0:
                print(" ".join(arg))
                print(f'\nError generating chunk {i}')
                exit(1)
            
            print(f'\nGenerated chunk {i}')
    except Empty:
        print('Failed to get calculated timeframes after 30 seconds of waiting.')
        exit(1)

if __name__ == '__main__':
    print('This file should not be run as a standalone script!')