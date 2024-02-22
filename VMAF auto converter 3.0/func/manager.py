import multiprocessing
from func.logger import create_logger


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
        exception = e
        args = None
        traceback = None
    if exception != 'ArgumentTypeError' and exception is not None:
        logger.error(f'An exception occurred: {exception} with args {args} and traceback {traceback}')
    for q in queue_list:
        logger.debug(f'Closing queue {q.name}')
        q.close()
    # Send a None to the log queue to stop the listener
    logger.debug('Telling the listener to stop')
    log_queue.put(None)
    return


if __name__ == '__main__':
    print('This file should not be run as a standalone script!')
