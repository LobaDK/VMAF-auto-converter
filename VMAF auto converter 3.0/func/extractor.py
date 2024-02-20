from json import loads
from pathlib import Path
from subprocess import DEVNULL, PIPE, Popen, run
import multiprocessing
from queue import Queue
from func.logger import create_logger


def GetAudioMetadata(detect_audio_bitrate: bool, file: str, log_queue: Queue) -> dict[str, int | str | bool]:
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
    logger = create_logger(log_queue, 'audio_metadata')

    audio_metadata_settings = {}
    try:
        cmd = ['ffprobe', '-v', 'quiet', '-show_streams', '-select_streams', 'a:0', '-of', 'json', file]
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
        if detect_audio_bitrate:
            audio_metadata_settings['audio_bitrate'] = audio_metadata['bit_rate']
            logger.debug(f'Found audio stream: {audio_metadata["codec_name"]}, with {audio_metadata["bit_rate"]} bitrate.')

    return audio_metadata_settings


def GetVideoMetadata(file: str, log_queue: Queue) -> dict[str, int]:
    """
    Retrieves metadata of a video file.

    Args:
        file (str): The path to the video file.
        log_queue (Queue): The queue used for logging.

    Returns:
        dict[str, int]: A dictionary containing the video metadata, including the total number of frames and the average frame rate.
    """
    logger = create_logger(log_queue, 'video_metadata')
    video_metadata_settings = {}
    try:
        arg = ['ffprobe', '-v', 'quiet', '-show_streams', '-select_streams', 'v:0', '-of', 'json', file]
        video_stream = Popen(arg, stdout=PIPE, stderr=PIPE)
        stdout, stderr = video_stream.communicate()
        video_metadata = loads(stdout)['streams'][0]
    except IndexError:
        logger.error('No video stream detected.')
        exit(1)
    else:
        video_metadata_settings['total_frames'] = int(video_metadata['nb_frames'])
        fps = '0'
        try:
            fps = video_metadata['avg_frame_rate'].split('/', 1)[0]
            if not fps.isnumeric() or int(fps) <= 0:
                raise KeyError
        except KeyError:
            logger.warning('Could not detect the video stream\'s average frame rate.')
            while not fps.isnumeric() or int(fps) <= 0:
                fps = input('\nManual input required: ')
        video_metadata_settings['fps'] = int(fps)

    return video_metadata_settings


def ExtractAudio(settings: dict, file: str, process_failure: multiprocessing.Event, audio_extract_finished: multiprocessing.Event) -> None:
    """
    Extracts audio from a video file using FFmpeg.

    Args:
        settings (dict): A dictionary containing various settings for the audio extraction process.
        file (str): The path to the video file from which audio needs to be extracted.
        process_failure (multiprocessing.Event): An event to indicate if the audio extraction process failed.
        audio_extract_finished (multiprocessing.Event): An event to indicate that the audio extraction process has finished.

    Returns:
        None
    """
    # TODO: Add support for multiple audio streams. Dynamically create the FFmpeg mapping for the audio streams?
    logger = create_logger(settings['log_queue'], 'audio_extractor')

    logger.info(f'Extracting audio from {file} on secondary thread...')
    arg = ['ffmpeg', '-i', str(file), '-vn', '-c:a', 'copy', str(Path(settings['tmp_folder']) / f'audio.{settings["audio_codec_name"]}')]
    if settings['ffmpeg_verbose_level'] == 0:
        run(arg, stderr=DEVNULL, stdout=DEVNULL)
    else:
        arg[1:1] = settings['ffmpeg_print']
        run(arg)

    if not Path(Path(settings['tmp_folder']) / f'audio.{settings["audio_codec_name"]}').exists():
        logger.error(f'Failed to extract audio from {file}')
        process_failure.set()
        exit(1)

    logger.info(f'Extracted audio from {file}.')
    audio_extract_finished.set()


if __name__ == '__main__':
    print('This file should not be run as a standalone script!')
