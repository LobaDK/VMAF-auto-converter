from json import loads
from pathlib import Path
from subprocess import DEVNULL, PIPE, Popen, run


def GetAudioMetadata(settings: dict, file: str) -> bool | str:
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
        audio_codec_name = audio_metadata['codec_name']
    
    if settings['detect_audio_bitrate']:
            settings['audio_bitrate'] = audio_metadata['bit_rate']

    return bool(settings["detected_audio_stream"]), str(audio_codec_name)

def GetVideoMetadata(file: str) -> int:
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
        total_frames = int(video_metadata['nb_frames'])
    
    fps = '0'
    try:
        fps = video_metadata['avg_frame_rate'].split('/', 1)[0]
    except:
        print('\nError getting video frame rate.')
        while not fps.isnumeric() or fps == '0':
            fps = input('Manual input required: ')

    return int(total_frames), int(fps)

def ExtractAudio(settings: dict, file: str, audio_codec_name: str) -> None:
    arg = ['ffmpeg', '-i', str(file), '-vn', '-c:a', 'copy', str(Path(settings['tmp_folder']) / f'audio.{audio_codec_name}')]
    if settings['ffmpeg_verbose_level'] == 0:
        audio_extract = run(arg, stderr=DEVNULL, stdout=DEVNULL)
    else:
        arg[1:1] = settings['ffmpeg_print']
        audio_extract = run(arg)

    if not Path(Path(settings['tmp_folder']) / f'audio.{audio_codec_name}').exists():
        print(" ".join(arg))
        print('\nError extracting audio track!')
        exit(1)

if __name__ == '__main__':
    print('This file should not be run as a standalone script!')