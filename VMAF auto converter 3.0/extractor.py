from subprocess import Popen
from subprocess import PIPE
from json import loads
from pathlib import Path

def GetAudioMetadata(settings: dict, output_filename: str):
    try:
        cmd = ['ffprobe', '-v', 'quiet', '-show_streams', '-select_streams', 'a:0', '-of', 'json', str(output_filename)]
        audio_stream = Popen(cmd, stdout=PIPE, stderr=PIPE)
        stdout, stderr = audio_stream.communicate()
        audio_metadata = loads(stdout)['streams'][0]
    except IndexError:
        detected_audio_stream = False
        print('\nNo audio stream detected.')
    else:
        detected_audio_stream = True
        audio_codec_name = audio_metadata['codec_name']
    
    if settings['detect_audio_bitrate']:
            settings['audio_bitrate'] = audio_metadata['bit_rate']

    return bool(detected_audio_stream), str(audio_codec_name)

def GetVideoMetadata(settings: dict, output_filename: str):
    try:
        arg = ['ffprobe', '-v', 'quiet', '-show_streams', '-select_streams', 'v:0', '-of', 'json', output_filename]
        video_stream = Popen(arg, stdout=PIPE, stderr=PIPE)
        stdout, stderr = video_stream.communicate()
        video_metadata = loads(stdout)['streams'][0]
    except IndexError:
        print(" ".join(arg))
        print('\nNo video stream detected!')
        exit(1)
    else:
        total_frames = int(video_metadata['nb_frames'])
        video_codec_name = video_metadata['codec_name']
    
    fps = '0'
    try:
        fps = video_metadata['avg_frame_rate'].split('/', 1)[0]
    except:
        print('\nError getting video frame rate.')
        while not fps.isnumeric() or fps == '0':
            fps = input('Manual input required: ')

    return total_frames, video_codec_name, fps

def ExtractAudio(settings: dict, file: str, audio_codec_name: str):
    arg = ['ffmpeg', '-v', 'quiet', '-i', file, '-vn', '-c:a', 'copy', Path(settings['tmp_folder']) / f'audio.{audio_codec_name}']
    print('\nExtracting audio...\n')
    audio_extract = Popen(arg)
    if audio_extract.returncode != 0:
        print(" ".join(arg))
        print('\nError extracting audio track!')
        exit(1)

if __name__ == '__main__':
    print('This file should not be run as a standalone script!')