from multiprocessing import Pool
from os import cpu_count, mkdir
from pathlib import Path
from signal import SIGINT, signal

from temp import cleanup, tmpcleanup
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


    if Path('settings.ini').exists():
        settings = ReadSettings()
    else:
        CreateSettings()
        input('New settings.ini has been created. Press enter when ready to continue...')
        settings = ReadSettings()
    try:
        mkdir(settings['output_dir'])
    except FileExistsError:
        pass

    settings['physical_cores'] = int(cpu_count() / 2)

    files = list(Path(settings['input_dir']).glob(f'*.{settings["input_extension"]}'))
    for file in files:
        settings['crf_value'] = settings['initial_crf_value']
        if not list(Path(settings['output_dir']).glob(f'{Path(file).stem}.*')):
            if settings['chunk_mode'] == 0:
                encode_without_chunks(settings, file) # Encode without chunks
            
            elif settings['chunk_mode'] == 1:
                encode_with_divided_chunks(settings, file) # Encode with input split into x chunks
            
            elif settings['chunk_mode'] == 2:
                encode_with_length_chunks(settings, file) # Encode with chunks split into x length
            
            elif settings['chunk_mode'] == 3:
                encode_with_keyframe_interval_chunks(settings, file) # Encode with chunks the length of the input keyframe intervals
            
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