from json import loads
from pathlib import Path
from subprocess import DEVNULL, PIPE, Popen, run
from threading import current_thread


def GetAudioMetadata(settings: dict, file: str) -> dict:
    """Use ffprobe to get metadata from the input file's audio stream.
    Returns an updated settings dictionary with the included audio metadata"""
    try:
        cmd = ['ffprobe', '-v', 'quiet', '-show_streams', '-select_streams', 'a:0', '-of', 'json', file]
        audio_stream = Popen(cmd, stdout=PIPE, stderr=PIPE)
        stdout, stderr = audio_stream.communicate()
        audio_metadata = loads(stdout)['streams'][0]
    except IndexError:
        settings["detected_audio_stream"] = False
        print('\nNo audio stream detected.')
    else:
        settings["detected_audio_stream"] = True
        settings['audio_codec_name'] = audio_metadata['codec_name']
    
    if settings['detect_audio_bitrate']:
            settings['audio_bitrate'] = audio_metadata['bit_rate']

    return settings

def GetVideoMetadata(settings: dict, file: str) -> dict:
    """Use ffprobe to get metadata from the input file's video stream.
    Returns an updated settings dictionary with the included video metadata"""
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
        settings['total_frames'] = int(video_metadata['nb_frames'])
    
    settings['fps'] = '0'
    try:
        settings['fps'] = video_metadata['avg_frame_rate'].split('/', 1)[0]
    except:
        print('\nError getting video frame rate.')
        while not settings['fps'].isnumeric() or settings['fps'] == '0':
            settings['fps'] = input('Manual input required: ')
    settings['fps'] = int(settings['fps'])

    return settings

def ExtractAudio(settings: dict, file: str, process_failure) -> None:
    """Use ffmpeg to extract the first audio stream from the input video."""
    print('\nExtracting audio on secondary thread...')
    arg = ['ffmpeg', '-i', str(file), '-vn', '-c:a', 'copy', str(Path(settings['tmp_folder']) / f'audio.{settings["audio_codec_name"]}')]
    if settings['ffmpeg_verbose_level'] == 0:
        run(arg, stderr=DEVNULL, stdout=DEVNULL)
    else:
        arg[1:1] = settings['ffmpeg_print']
        run(arg)

    if not Path(Path(settings['tmp_folder']) / f'audio.{settings["audio_codec_name"]}').exists():
        print(" ".join(arg))
        print('\nError extracting audio track!')
        process_failure.set()
        exit(1)
    
    print(f'\nAudio extraction completed on {current_thread().name}!')

if __name__ == '__main__':
    print('This file should not be run as a standalone script!')