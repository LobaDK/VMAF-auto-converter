from os import cpu_count
from os import name as OSname
from os import path
from os import mkdir
from signal import SIGINT, signal
from time import sleep
from pathlib import Path

from cleanup import cleanup, tmpcleanup
from settings import CreateSettings, ReadSettings


def signal_handler(sig, frame):
    settings = ReadSettings()
    cleanup(settings)
    exit()

signal(SIGINT, signal_handler)

def main():

    physical_cores = int(cpu_count() / 2)

    if OSname == 'nt': # Visual Studio Code will complain about either one being unreachable, since os.name is a variable. Just ignore this
        pass_1_output = 'NUL'
    else:
        pass_1_output = '/dev/null'

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
                pass # Encode without chunks
            elif settings['chunk_mode'] == 1:
                pass # Encode with input split into x chunks
            elif settings['chunk_mode'] == 2:
                pass # Encode with chunks split into x length
            elif settings['chunk_mode'] == 3:
                pass # Encode with chunks the length of the input keyframe intervals
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