import os
from pathlib import Path
import signal
import threading
import queue
from time import sleep, time
import platform

from func.encode import encoder
from func.settings import CreateSettings, ReadSettings
from func.temp import cleanup
from func.logger import listener_process, create_logger
from func.manager import queue_manager, NamedQueue

# Create a queue for logs
log_queue = queue.Queue()


# Signal handler that catches all SIGINTs (CTRL + C) across the main script, threads and processes.
def signal_handler(sig, frame):
    # Send SIGTERM to the entire process group
    os.killpg(os.getpgid(0), signal.SIGTERM)
    sleep(1)
    settings = ReadSettings(log_queue)
    cleanup(settings['tmp_folder'], settings['keep_tmp_files'])
    exit(1)


# Set the signal handler and a 0 process group
signal.signal(signal.SIGINT, signal_handler)


def main():
    # Create a listener process that handles all logs sent to the queue
    listener = threading.Thread(target=listener_process, args=(log_queue,))
    listener.start()

    logger = create_logger(log_queue, 'main')

    # Create a queue for exceptions
    manager_queue = queue.Queue()

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

    try:
        # Check if the settings file already exists, and if so, read it.
        # Otherwise, create one, and pause, to allow the user to edit the settings before continuing.
        if Path('settings.ini').exists():
            logger.debug('Reading settings.ini')
            settings = ReadSettings(log_queue)
        else:
            logger.debug('Creating settings.ini')
            CreateSettings(log_queue)
            input('New settings.ini has been created. Press enter when ready to continue...')
            settings = ReadSettings(log_queue)

        settings['chunk_calculate_queue'] = chunk_calculate_queue
        settings['chunk_generator_queue'] = chunk_generator_queue
        settings['chunk_concat_queue'] = chunk_concat_queue
        settings['manager_queue'] = manager_queue

        # Attempt to create the output folder, and ignore if it already exists.
        try:
            os.mkdir(settings['output_dir'])
        except FileExistsError:
            logger.debug(f'Skipping creation of {settings["output_dir"]}, as it already exists.')
            pass

        # Get the physical core count, used in the VMAF library.
        settings['physical_cores'] = int(os.cpu_count() / 2)

        # Iterate through each file that ends with an extension matching the specified extension.
        files = list(Path(settings['input_dir']).glob(f'*.{settings["input_extension"]}'))
        for file in files:
            settings['crf_value'] = settings['initial_crf_value']
            # Check if a file with the same filename already exists in the output folder, and assume it has already been converted.
            if not list(Path(settings['output_dir']).glob(f'{Path(file).stem}.*')):
                settings['log_queue'] = log_queue
                start = time()
                encoder(settings, file)
                end = time()
                print(f'\nTook {end - start} seconds')
                logger.info(f'Took {end - start} seconds to convert {Path(file).name}')
                if settings['use_intro'] or settings['use_outro']:
                    pass  # Add intro and/or outro
            else:
                print(f'\nAlready converted {Path(file).name}. Skipping...\n')
                logger.info(f'Already converted {Path(file).name}. Skipping...')
                continue

        log_queue.put(None)
        listener.join()
        cleanup(settings['tmp_folder'], settings['keep_tmp_files'], log_queue)
    except Exception as e:
        manager_queue.put(e)
        qman.join()
        listener.join()

        exit(1)


if __name__ == '__main__':
    main()
