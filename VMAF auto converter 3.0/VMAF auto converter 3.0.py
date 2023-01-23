from os import cpu_count, mkdir
from pathlib import Path
from signal import SIGINT, signal
from multiprocessing import active_children
from time import sleep, time

from func.encode import encoder
from func.settings import CreateSettings, ReadSettings
from func.temp import cleanup

    # Signal handler that catches all SIGINTs (CTLR + C) across the script, threads and processes.
# TODO: Further test signal handling across processes running ffmpeg, and handle them accordingly
def signal_handler(sig, frame):
    for p in active_children():
        p.terminate()
    sleep(1)
    settings = ReadSettings()
    cleanup(settings)
    exit(1)

signal(SIGINT, signal_handler)

def main():

    # Check if the settings file already exists, and if so, read it. 
    # Otherwise, create one, and pause, to allow the user to edit the settings before continuing.
    if Path('settings.ini').exists():
        settings = ReadSettings()
    else:
        CreateSettings()
        input('New settings.ini has been created. Press enter when ready to continue...')
        settings = ReadSettings()
    
    # Attempt to create the output folder, and ignore if it already exists.
    try:
        mkdir(settings['output_dir'])
    except FileExistsError:
        pass

    # Get the physical core count, used in the VMAF library.
    settings['physical_cores'] = int(cpu_count() / 2)

    # Iterate through each file that ends with an extension matching the specified extension.
    files = list(Path(settings['input_dir']).glob(f'*.{settings["input_extension"]}'))
    for file in files:
        settings['crf_value'] = settings['initial_crf_value']
        # Check if a file with the same filename already exists in the output folder, and assume it has already been converted.
        if not list(Path(settings['output_dir']).glob(f'{Path(file).stem}.*')):
            start = time()
            encoder(settings, file)
            end = time()
            print(f'\nTook {end - start} seconds')
            if settings['use_intro'] or settings['use_outro']:
                pass # Add intro and/or outro
        else:
            print(f'\nAlready converted {Path(file).name}. Skipping...\n')
            continue

    cleanup(settings)
    
if __name__ == '__main__':
    main()