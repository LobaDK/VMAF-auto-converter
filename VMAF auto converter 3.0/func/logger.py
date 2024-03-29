import logging
import logging.handlers
import multiprocessing


def listener_process(log_queue: multiprocessing.Queue) -> None:
    """
    Process that listens to a log queue and handles log messages.

    Args:
        log_queue (Queue): The queue to listen to for log messages.

    Returns:
        None
    """
    # Create a logger
    logger = logging.getLogger('Listener')

    # Set the log level
    logger.setLevel(logging.DEBUG)  # Set to lowest level

    # Create a FileHandler in write mode
    file_handler = logging.FileHandler('logfile.log', 'w')

    # Create a StreamHandler for console output
    stream_handler = logging.StreamHandler()

    # Create a Formatter
    file_formatter = logging.Formatter('%(asctime)s - %(name)-16s - %(levelname)s - %(message)s')
    stream_formatter = logging.Formatter('\n%(levelname)s: [%(name)s] %(message)s')

    # Set the Formatter on the Handlers
    file_handler.setFormatter(file_formatter)
    stream_handler.setFormatter(stream_formatter)

    # Set the log level on the Handlers so that debugging messages are not printed to the console
    file_handler.setLevel(logging.DEBUG)  # Will handle all messages
    stream_handler.setLevel(logging.INFO)  # Will handle only INFO and above

    # Add the handlers to the logger
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

    logger.debug('Listener thread started')

    while True:
        log = log_queue.get(block=True)

        if log is None:
            log_queue.close()
            log_queue.join_thread()
            # This doesn't use the queue, so it can still be logged after closing
            logger.debug('Listener thread stopped')
            break

        logger.handle(log)


def create_logger(log_queue: multiprocessing.Queue, logger_name: str) -> logging.Logger:
    """
    Create a logger with a specified name and a queue handler.

    Args:
        log_queue (multiprocessing.Queue): The queue used for logging.
        logger_name (str): The name of the logger.

    Returns:
        logging.Logger: The created logger object.
    """
    # Check if the logger already exists to avoid creating duplicate handlers
    if logger_name in logging.Logger.manager.loggerDict:
        logger = logging.getLogger(logger_name)
    else:
        handler = logging.handlers.QueueHandler(log_queue)
        logger = logging.getLogger(logger_name)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

    return logger


if __name__ == '__main__':
    print('This file should not be run as a standalone script!')
