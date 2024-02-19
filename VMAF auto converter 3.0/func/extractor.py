from json import loads
from pathlib import Path
from subprocess import DEVNULL, PIPE, Popen, run
from threading import current_thread
import multiprocessing


def GetAudioMetadata(detect_audio_bitrate: bool, file: str) -> dict[str, int | str | bool]:
    """
    Use ffprobe to get metadata from the input file's audio stream.
    Returns a dictionary with the included audio metadata.

    The returned dictionary will always contain the key "detected_audio_stream".
    If an audio stream is detected, the dictionary will also contain the key "audio_codec_name".
    If detect_audio_bitrate is True and an audio stream is detected, the dictionary will also contain the key "audio_bitrate".
    """
    audio_metadata_settings = {}
    try:
        cmd = ['ffprobe', '-v', 'quiet', '-show_streams', '-select_streams', 'a:0', '-of', 'json', file]
        audio_stream = Popen(cmd, stdout=PIPE, stderr=PIPE)
        stdout, stderr = audio_stream.communicate()
        audio_metadata = loads(stdout)['streams'][0]
    except IndexError:
        audio_metadata_settings["detected_audio_stream"] = False
        print('\nNo audio stream detected.')
    else:
        audio_metadata_settings["detected_audio_stream"] = True
        audio_metadata_settings['audio_codec_name'] = audio_metadata['codec_name']
        if detect_audio_bitrate:
            audio_metadata_settings['audio_bitrate'] = audio_metadata['bit_rate']

    return audio_metadata_settings


def GetVideoMetadata(file: str) -> dict[str, int]:
    """Use ffprobe to get metadata from the input file's video stream.
    Returns a dictionary with the included video metadata."""
    video_metadata_settings = {}
    try:
        arg = ['ffprobe', '-v', 'quiet', '-show_streams', '-select_streams', 'v:0', '-of', 'json', file]
        video_stream = Popen(arg, stdout=PIPE, stderr=PIPE)
        stdout, stderr = video_stream.communicate()
        video_metadata = loads(stdout)['streams'][0]
    except IndexError:
        print(" ".join(arg))
        print('\nNo video stream detected!')
        exit(1)
    else:
        video_metadata_settings['total_frames'] = int(video_metadata['nb_frames'])
        fps = '0'
        try:
            fps = video_metadata['avg_frame_rate'].split('/', 1)[0]
            if not fps.isnumeric() or int(fps) <= 0:
                raise KeyError
        except KeyError:
            print('\nError getting video frame rate.')
            while not fps.isnumeric() or int(fps) <= 0:
                fps = input('Manual input required: ')
        video_metadata_settings['fps'] = int(fps)

    return video_metadata_settings


def ExtractAudio(settings: dict, file: str, process_failure: multiprocessing.Event, audio_extract_finished: multiprocessing.Event, color: str) -> None:
    """Use ffmpeg to extract the first audio stream from the input video."""
    print(f'\n{color}Extracting audio on secondary thread...')
    arg = ['ffmpeg', '-i', str(file), '-vn', '-c:a', 'copy', str(Path(settings['tmp_folder']) / f'audio.{settings["audio_codec_name"]}')]
    if settings['ffmpeg_verbose_level'] == 0:
        run(arg, stderr=DEVNULL, stdout=DEVNULL)
    else:
        arg[1:1] = settings['ffmpeg_print']
        run(arg)

    if not Path(Path(settings['tmp_folder']) / f'audio.{settings["audio_codec_name"]}').exists():
        print(" ".join(arg))
        print(f'\n{color}Error extracting audio track!')
        process_failure.set()
        exit(1)

    print(f'\n{color}Audio extraction completed on {current_thread().name}!')
    audio_extract_finished.set()


if __name__ == '__main__':
    print('This file should not be run as a standalone script!')
