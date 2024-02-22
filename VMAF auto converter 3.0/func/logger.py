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

    # Create a FileHandler in append mode
    file_handler = logging.FileHandler('logfile.log', 'w')

    # Create a StreamHandler for console output
    stream_handler = logging.StreamHandler()

    # Create a Formatter
    file_formatter = logging.Formatter('%(asctime)s - %(name)-15s - %(levelname)s - %(message)s')
    stream_formatter = logging.Formatter('\n%(name)s[%(levelname)s]: %(message)s')

    # Set the Formatter on the Handlers
    file_handler.setFormatter(file_formatter)
    stream_handler.setFormatter(stream_formatter)

    # Set the log level on the Handlers
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
    handler = logging.handlers.QueueHandler(log_queue)
    logger = logging.getLogger(logger_name)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    logger.debug(f'Logger for {logger_name} created')

    return logger


if __name__ == '__main__':
    print('This file should not be run as a standalone script!')
