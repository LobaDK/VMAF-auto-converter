import os
import pathlib
import multiprocessing
import signal
import threading
import time
import sys

from func.encode import encoder
from func.settings import CreateSettings, ReadSettings
from func.temp import cleanup
from func.logger import listener_process, create_logger
from func.manager import queue_manager, NamedQueue, ExceptionHandler

settings = None

# Create a queue for the manager to receive exceptions
manager_queue = multiprocessing.Queue()
# Create a queue for logs
log_queue = NamedQueue('log_queue')

handler = ExceptionHandler(log_queue, manager_queue)
sys.excepthook = handler.handle_exception


# Signal handler that catches all SIGINTs (CTRL + C) across the main script, threads and processes.
def signal_handler(sig, frame):
    logger = create_logger(log_queue, 'SignalHandler')
    logger.debug('Caught SIGINT')
    for proc in multiprocessing.active_children():
        proc.terminate()
        logger.debug(f'Terminated {proc.name}')
        proc.join()
    time.sleep(1)
    cleanup(settings['tmp_folder'], settings['keep_tmp_files'], log_queue)
    manager_queue.put(None)
    exit(1)


# Set the signal handler and a 0 process group
signal.signal(signal.SIGINT, signal_handler)


def main():
    # Make settings global, so they can be accessed from anywhere in the script
    global settings
    # Create a listener process that handles all logs sent to the queue
    listener = threading.Thread(target=listener_process, args=(log_queue,))
    listener.start()

    logger = create_logger(log_queue, 'main')

    queue_list = []

    # Create queues used to pass data between the chunk calculator, chunk generator, chunk converter and concatenator
    # Chunk calculator > Chunk generator
    chunk_calculate_queue = NamedQueue('chunk_calculate_queue')
    queue_list.append(chunk_calculate_queue)
    # Chunk generator > Chunk converter
    chunk_generator_queue = NamedQueue('chunk_generator_queue')
    queue_list.append(chunk_generator_queue)
    # Chunk converter > Concatenator
    chunk_concat_queue = NamedQueue('chunk_concat_queue')
    queue_list.append(chunk_concat_queue)

    qman = threading.Thread(target=queue_manager,
                            args=(queue_list, manager_queue, log_queue),
                            daemon=False,
                            name='QueueManager')
    qman.start()
    # Check if the settings file already exists, and if so, read it.
    # Otherwise, create one, and pause, to allow the user to edit the settings before continuing.
    if pathlib.Path('settings.ini').exists():
        logger.debug('Reading settings.ini')
        settings = ReadSettings(log_queue, manager_queue)
    else:
        logger.debug('Creating settings.ini')
        CreateSettings(log_queue)
        settings = ReadSettings(log_queue, manager_queue)
        input('New settings.ini has been created. Press enter when ready to continue...')

    settings['chunk_calculate_queue'] = chunk_calculate_queue
    settings['chunk_generator_queue'] = chunk_generator_queue
    settings['chunk_concat_queue'] = chunk_concat_queue
    settings['manager_queue'] = manager_queue

    # Attempt to create the output folder, and ignore if it already exists.
    try:
        os.mkdir(settings['output_dir'])
        logger.debug(f'Created {settings["output_dir"]}')
    except FileExistsError:
        logger.debug(f'Skipping creation of {settings["output_dir"]}, as it already exists.')
        pass

    # Get the physical core count, used in the VMAF library.
    settings['physical_cores'] = int(os.cpu_count() / 2)

    # Iterate through each file that ends with an extension matching the specified extension.
    files = list(pathlib.Path(settings['input_dir']).glob(f'*.{settings["input_extension"]}'))
    if len(files) > 0:
        logger.debug(f'Found {len(files)} files with the extension {settings["input_extension"]}')
        for file in files:
            settings['crf_value'] = settings['initial_crf_value']
            # Check if a file with the same filename already exists in the output folder, and assume it has already been converted.
            if not list(pathlib.Path(settings['output_dir']).glob(f'{pathlib.Path(file).stem}.*')):
                settings['log_queue'] = log_queue
                start = time.time()
                encoder(settings, file)
                end = time.time()
                logger.info(f'Took {end - start} seconds to convert {pathlib.Path(file).name}')
                if settings['use_intro'] or settings['use_outro']:
                    raise NotImplementedError('Intro and outro not yet implemented')
            else:
                logger.info(f'Already converted {pathlib.Path(file).name}. Skipping...')
                continue
    else:
        logger.info(f'No files found with the extension {settings["input_extension"]} in the input directory.')

    cleanup(settings['tmp_folder'], settings['keep_tmp_files'], log_queue)
    manager_queue.put(None)


if __name__ == '__main__':
    main()
