import multiprocessing
from func.logger import create_logger
import traceback
from types import TracebackType
from typing import Type


class NamedQueue:
    """A wrapper for the multiprocessing.Queue class that adds a name attribute to the queue."""
    def __init__(self, name):
        self.queue = multiprocessing.Queue()
        self.name = name

    def put(self, item):
        self.queue.put(item)

    def put_nowait(self, item):
        self.queue.put_nowait(item)

    def get(self, block=True):
        return self.queue.get(block=block)

    def join_thread(self):
        self.queue.join_thread()

    def close(self):
        self.queue.close()


class ExceptionHandler:
    """
    Class to handle unhandled exceptions and log them.

    Args:
        log_queue (NamedQueue): A queue for logging messages.
        manager_queue (multiprocessing.Queue): A queue for communication with the manager process.

    """

    def __init__(self, log_queue: NamedQueue, manager_queue: multiprocessing.Queue):
        self.log_queue = log_queue
        self.manager_queue = manager_queue
        self.logger = create_logger(self.log_queue, 'ExceptionHandler')

    def handle_exception(self, exc_type: Type[BaseException], exc_value: BaseException, exc_traceback: TracebackType):
        """
        Handles an unhandled exception.

        Args:
            exc_type (type): The type of the exception.
            exc_value (Exception): The exception object.
            exc_traceback (traceback): The traceback object.

        """
        self.logger.debug('Caught unhandled exception')
        formatted_traceback = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        self.manager_queue.put((exc_type, exc_value, formatted_traceback))


def custom_exit(manager_queue: multiprocessing.Queue) -> None:
    """
    Exits the program and sends a None to the manager queue to stop the queue manager.

    Args:
        manager_queue (multiprocessing.Queue): The queue used for receiving exceptions.

    Returns:
        None
    """
    manager_queue.put(None)
    exit(1)


def queue_manager(queue_list: list[NamedQueue], manager_queue: multiprocessing.Queue, log_queue: NamedQueue) -> None:
    """
    Manages the queues used in the VMAF auto converter.

    Args:
        queue_list (list[NamedQueue]): A list of custom NamedQueue queues to be managed.
        manager_queue (multiprocessing.Queue): The queue used for receiving exceptions.
        log_queue (NamedQueue): The queue used for logging.

    Returns:
        None
    """
    logger = create_logger(log_queue, 'QueueManager')
    logger.debug('Queue manager started')
    # Blocks until an exception is received
    e = manager_queue.get(block=True)
    if isinstance(e, tuple):
        exception, args, traceback = e
    else:
        exception = e  # If the exception is not a tuple, it is a None, which acts as our sentinel value
    if exception != 'ArgumentTypeError' and exception is not None:
        logger.error(f'An exception occurred: {exception} with args {args} and traceback {traceback}')
    for q in queue_list:
        logger.debug(f'Closing queue {q.name}')
        q.close()
    logger.debug('Telling the listener to stop')
    # Send a None to the log queue to stop the listener
    log_queue.put(None)
    return


if __name__ == '__main__':
    print('This file should not be run as a standalone script!')
