import logging


def listener_process(log_queue):
    # Create a logger
    logger = logging.getLogger()

    # Set the log level
    logger.setLevel(logging.INFO)

    # Create a FileHandler in append mode
    handler = logging.FileHandler('logfile.log', 'a')

    # Create a Formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Set the Formatter on the Handler
    handler.setFormatter(formatter)

    # Add the handler to the logger
    logger.addHandler(handler)

    while True:
        log = log_queue.get()

        if log is None:
            break

        logger.handle(log)
