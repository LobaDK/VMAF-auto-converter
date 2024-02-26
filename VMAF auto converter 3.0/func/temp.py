import os
from pathlib import Path
from shutil import rmtree
import multiprocessing
from func.logger import create_logger


def cleanup(tmp_folder: str, keep_tmp_files: bool, log_queue: multiprocessing.Queue) -> None:
    """
    Cleans up temporary files.

    Args:
        tmp_folder (str): The path to the temporary folder.
        keep_tmp_files (bool): Flag indicating whether to keep temporary files.
        log_queue (Queue): The queue used for logger.

    Returns:
        None
    """
    logger = create_logger(log_queue, 'cleanup')

    logger.info('Cleaning up temp files...')
    tmpfile_list = ['IntroOutroList.txt', 'log.json', 'ffmpeg2pass-0.log']
    for tmp in tmpfile_list:
        try:
            os.remove(tmp)
        except FileNotFoundError:
            logger.debug(f"The file {tmp} does not exist.")
        except PermissionError:
            logger.error(f"Insufficient permissions to delete the file {tmp}.")
        except IsADirectoryError:
            logger.error(f"{tmp} is a directory, not a file.")
        except OSError as e:
            logger.error(f"Error deleting file {tmp}: {e.strerror}")

    if Path(tmp_folder).exists() and not keep_tmp_files:
        tmpcleanup(tmp_folder, log_queue)


def tmpcleanup(tmp_folder: str, log_queue: multiprocessing.Queue) -> None:
    """
    Clean up the temporary folder.

    Args:
        tmp_folder (str): The path to the temporary folder.
        log_queue (Queue): The queue used for logging.

    Returns:
        None
    """
    logger = create_logger(log_queue, 'tmpcleanup')

    try:
        rmtree(tmp_folder)
    except FileNotFoundError:
        logger.debug(f"Error cleaning up temp directory: {tmp_folder} does not exist.")
    except PermissionError:
        logger.error(f"Error cleaning up temp directory: Insufficient permissions to delete {tmp_folder}.")
    except OSError as e:
        logger.error(f"Error cleaning up temp directory: {e.strerror}")


def CreateTempFolder(tmp_folder: str, log_queue: multiprocessing.Queue) -> None:
    """
    Create temporary folders for processing.

    Args:
        tmp_folder (str): The path to the temporary folder.

    Returns:
        None
    """
    logger = create_logger(log_queue, 'CreateTempFolder')
    directories = [tmp_folder, Path(tmp_folder) / 'prepared', Path(tmp_folder) / 'converted']

    for directory in directories:
        if Path(directory).exists():
            logger.debug(f"Deleting existing directory: {directory}...")
            tmpcleanup(tmp_folder, log_queue)
        logger.debug(f"Creating directory: {directory}...")
        os.mkdir(directory)


if __name__ == '__main__':
    print('This file should not be run as a standalone script!')
