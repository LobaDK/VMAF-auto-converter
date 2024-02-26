from json import loads
from pathlib import Path
from subprocess import DEVNULL, PIPE, Popen, run
from func.logger import create_logger
from func.manager import ExceptionHandler
import sys
import multiprocessing


def GetAudioMetadata(file: str, settings: dict) -> dict[str, int | str | bool]:
    """
    Retrieves audio metadata from a given file.

    Args:
        detect_audio_bitrate (bool): Flag indicating whether to detect audio bitrate.
        file (str): Path to the input file.
        log_queue (Queue): Queue for logging messages.

    Returns:
        dict[str, int | str | bool]: Dictionary containing audio metadata settings.
            - 'detected_audio_stream' (bool): Flag indicating whether an audio stream was detected.
            - 'audio_codec_name' (str): Name of the audio codec.
            - 'audio_bitrate' (int): Bitrate of the audio stream (if detect_audio_bitrate is True).

    """
    handler = ExceptionHandler(settings['log_queue'], settings['manager_queue'])
    sys.excepthook = handler.handle_exception
    logger = create_logger(settings['log_queue'], 'audio_metadata')

    audio_metadata_settings = {}
    try:
        cmd = ['ffprobe', '-v', 'quiet', '-show_streams', '-select_streams', 'a:0', '-of', 'json', file]
        logger.debug(f'Running command: {" ".join(cmd)}')
        audio_stream = Popen(cmd, stdout=PIPE, stderr=PIPE)
        stdout, _ = audio_stream.communicate()
        audio_metadata = loads(stdout)['streams'][0]
    except IndexError:
        audio_metadata_settings["detected_audio_stream"] = False
        logger.debug('No audio stream detected.')
    else:
        audio_metadata_settings["detected_audio_stream"] = True
        audio_metadata_settings['audio_codec_name'] = audio_metadata['codec_name']
        logger.debug(f'Found audio stream: {audio_metadata["codec_name"]}')
        if settings['detect_audio_bitrate']:
            audio_metadata_settings['audio_bitrate'] = audio_metadata['bit_rate']
            logger.debug(f'Found audio stream: {audio_metadata["codec_name"]}, with {audio_metadata["bit_rate"]} bitrate.')

    return audio_metadata_settings


def GetVideoMetadata(file: str, settings: dict) -> dict[str, int]:
    """
    Retrieves metadata of a video file.

    Args:
        file (str): The path to the video file.
        log_queue (Queue): The queue used for logging.

    Returns:
        dict[str, int]: A dictionary containing the video metadata, including the total number of frames and the average frame rate.
    """
    handler = ExceptionHandler(settings['log_queue'], settings['manager_queue'])
    sys.excepthook = handler.handle_exception
    logger = create_logger(settings['log_queue'], 'video_metadata')
    video_metadata_settings = {}
    arg = ['ffprobe', '-v', 'quiet', '-show_streams', '-select_streams', 'v:0', '-of', 'json', file]
    logger.debug(f'Running command: {" ".join(arg)}')
    video_stream = Popen(arg, stdout=PIPE, stderr=PIPE)
    stdout, stderr = video_stream.communicate()
    try:
        video_metadata = loads(stdout)['streams'][0]
    except IndexError as e:
        raise IndexError(f'No video stream detected in {file}. Error: {e}')
    else:
        video_metadata_settings['total_frames'] = int(video_metadata['nb_frames'])
        fps = '0'
        try:
            fps = video_metadata['avg_frame_rate'].split('/', 1)[0]
            if not fps.isnumeric() or int(fps) <= 0:
                raise KeyError  # Force manual input
        except KeyError:
            logger.warning('Could not detect the video stream\'s average frame rate.')
            while not fps.isnumeric() or int(fps) <= 0:
                fps = input('\nManual input required: ')
        video_metadata_settings['fps'] = int(fps)

    return video_metadata_settings


def ExtractAudio(settings: dict, file: str, process_failure: multiprocessing.Event) -> None:
    """
    Extracts audio from a video file using FFmpeg.

    Args:
        settings (dict): A dictionary containing various settings for the audio extraction process.
        file (str): The path to the video file from which audio needs to be extracted.
        process_failure (multiprocessing.Event): Event to signal that an error occurred during the audio extraction process.

    Returns:
        None
    """
    # TODO: Add support for multiple audio streams. Maybe dynamically create the FFmpeg mapping for the audio streams?
    handler = ExceptionHandler(settings['log_queue'], settings['manager_queue'])
    sys.excepthook = handler.handle_exception
    logger = create_logger(settings['log_queue'], 'audio_extractor')

    arg = ['ffmpeg', '-i', str(file), '-vn', '-c:a', 'copy', str(Path(settings['tmp_folder']) / f'audio.{settings["audio_codec_name"]}')]
    logger.debug(f'Extracting audio with command: {" ".join(arg)}')
    if settings['ffmpeg_verbose_level'] == 0:
        run(arg, stderr=DEVNULL, stdout=DEVNULL)
    else:
        arg[1:1] = settings['ffmpeg_print']
        run(arg)

    if not Path(Path(settings['tmp_folder']) / f'audio.{settings["audio_codec_name"]}').exists():
        process_failure.set()
        raise FileNotFoundError(f'Could not find audio file. Did audio extraction fail for {file}?')

    logger.info(f'Extracted audio from {file}.')


if __name__ == '__main__':
    print('This file should not be run as a standalone script!')
