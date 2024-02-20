import logging
import logging.handlers
from queue import Queue


def listener_process(log_queue: Queue) -> None:
    """
    Process that listens to a log queue and handles log messages.

    Args:
        log_queue (Queue): The queue to listen to for log messages.

    Returns:
        None
    """
    # Create a logger
    logger = logging.getLogger()

    # Set the log level
    logger.setLevel(logging.DEBUG)  # Set to lowest level

    # Create a FileHandler in append mode
    file_handler = logging.FileHandler('logfile.log', 'a')

    # Create a StreamHandler for console output
    stream_handler = logging.StreamHandler()

    # Create a Formatter
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    stream_formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')

    # Set the Formatter on the Handlers
    file_handler.setFormatter(file_formatter)
    stream_handler.setFormatter(stream_formatter)

    # Set the log level on the Handlers
    file_handler.setLevel(logging.DEBUG)  # Will handle all messages
    stream_handler.setLevel(logging.INFO)  # Will handle only INFO and above

    # Add the handlers to the logger
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

    while True:
        log = log_queue.get(block=True)

        if log is None:
            break

        logger.handle(log)


def create_logger(log_queue: Queue, logger_name: str) -> logging.Logger:
    """
    Create a logger with a specified name and a queue handler for logging messages.

    Args:
        log_queue (Queue): The queue used for logging messages.
        logger_name (str): The name of the logger.

    Returns:
        logging.Logger: The created logger object.
    """
    handler = logging.handlers.QueueHandler(log_queue)
    logger = logging.getLogger(logger_name)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    return logger


if __name__ == '__main__':
    print('This file should not be run as a standalone script!')
