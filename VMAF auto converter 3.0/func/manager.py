import queue
import multiprocessing
from func.logger import create_logger
from argparse import ArgumentTypeError


class NamedQueue:
    """A wrapper for the multiprocessing.Queue class that adds a name attribute to the queue."""
    def __init__(self, name):
        self.queue = multiprocessing.Queue()
        self.name = name

    def put(self, item):
        self.queue.put(item)

    def get(self):
        return self.queue.get()

    def join_thread(self):
        self.queue.join_thread()

    def close(self):
        self.queue.close()


def queue_manager(queue_list: list[NamedQueue], manager_queue: queue.Queue, log_queue: queue.Queue) -> None:
    """
    Manages the queues and handles exceptions from the manager queue.

    Args:
        queue_list (list[NamedQueue]): List of named queues to be managed.
        manager_queue (queue.Queue): Queue for receiving exceptions.
        log_queue (queue.Queue): Queue for logging exceptions.

    Returns:
        None
    """
    logger = create_logger(log_queue, 'QueueManager')
    while True:
        exception = manager_queue.get(block=True)
        if exception is not ArgumentTypeError or exception is not None:
            logger.exception(f'Exception ocurred {exception.__class__.__name__}: {exception}')
        for _queue in queue_list:
            logger.debug(f'Closing {_queue.name}...')
            _queue.put(None)
            _queue.close()
            _queue.join_thread()
        log_queue.put(None)
        break


if __name__ == '__main__':
    print('This file should not be run as a standalone script!')
