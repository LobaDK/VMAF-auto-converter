from os import cpu_count, mkdir
from pathlib import Path
from signal import SIGINT, signal
from multiprocessing import active_children
from time import sleep

from encode import encoder
from settings import CreateSettings, ReadSettings
from temp import cleanup


def signal_handler(sig, frame):
    for p in active_children():
        p.terminate()
    sleep(1)
    settings = ReadSettings()
    cleanup(settings)
    exit(1)

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
            encoder(settings, file)
            
            if settings['use_intro'] or settings['use_outro']:
                pass # Add intro and/or outro
        else:
            print(f'\nAlready converted {Path(file).name}. Skipping...\n')
            continue

    cleanup(settings)
    
if __name__ == '__main__':
    main()