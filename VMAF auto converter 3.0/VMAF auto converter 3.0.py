import os
from pathlib import Path
import signal
from time import sleep, time

from func.encode import encoder
from func.settings import CreateSettings, ReadSettings
from func.temp import cleanup


# Signal handler that catches all SIGINTs (CTRL + C) across the main script, threads and processes.
def signal_handler(sig, frame):
    # Send SIGTERM to the entire process group
    os.killpg(os.getpgid(0), signal.SIGTERM)
    sleep(1)
    settings = ReadSettings()
    cleanup(settings['tmp_folder'], settings['keep_tmp_files'])
    exit(1)


# Set the signal handler and a 0 process group
signal.signal(signal.SIGINT, signal_handler)
os.setpgrp()  # create new process group, become its leader


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
        os.mkdir(settings['output_dir'])
    except FileExistsError:
        pass

    # Get the physical core count, used in the VMAF library.
    settings['physical_cores'] = int(os.cpu_count() / 2)

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
                pass  # Add intro and/or outro
        else:
            print(f'\nAlready converted {Path(file).name}. Skipping...\n')
            continue

    cleanup(settings['tmp_folder'], settings['keep_tmp_files'])


if __name__ == '__main__':
    main()
    signal.pause()
