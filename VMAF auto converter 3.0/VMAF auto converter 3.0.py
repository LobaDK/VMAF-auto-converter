from os import cpu_count, mkdir
from os import name as OSname
from os import path
from pathlib import Path
from signal import SIGINT, signal
from time import sleep

from cleanup import cleanup, tmpcleanup
from encode import (encode_with_divided_chunks,
                    encode_with_keyframe_interval_chunks,
                    encode_with_length_chunks, encode_without_chunks)
from settings import CreateSettings, ReadSettings


def signal_handler(sig, frame):
    settings = ReadSettings()
    cleanup(settings)
    exit()

signal(SIGINT, signal_handler)

def main():

    physical_cores = int(cpu_count() / 2)

    if path.exists('settings.ini'):
        settings = ReadSettings()
    else:
        CreateSettings()
        settings = ReadSettings()

    try:
        mkdir(settings['output_dir'])
    except FileExistsError:
        pass

    files = list(Path(settings['input_dir']).glob(f'*.{settings["input_extension"]}'))
    for file in files:
        if not list(Path(settings['output_dir']).glob(f'{Path(file).stem}.*')):
            if settings['chunk_mode'] == 0:
                encode_without_chunks(settings, physical_cores, file) # Encode without chunks
            elif settings['chunk_mode'] == 1:
                encode_with_divided_chunks(settings, physical_cores, file) # Encode with input split into x chunks
            elif settings['chunk_mode'] == 2:
                encode_with_length_chunks(settings, physical_cores, file) # Encode with chunks split into x length
            elif settings['chunk_mode'] == 3:
                encode_with_keyframe_interval_chunks(settings, physical_cores, file) # Encode with chunks the length of the input keyframe intervals
            else:
                print('chunk mode it out of range (0-3)!')
                exit(1)
            if settings['use_intro'] or settings['use_outro']:
                pass # Add intro and/or outro
        else:
            print(f'\nAlready converted {Path(file).name}. Skipping...\n')
            continue

if __name__ == '__main__':
    main()