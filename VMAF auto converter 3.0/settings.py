from configparser import ConfigParser, Error
from os import path
from tempfile import gettempdir
import argparse

class EmptySettings(Exception):
    pass

def IntOrFloat(s: str):
        if s.isnumeric():
            value = int(s)
        else:
            try:
                value = float(s)
            except:
                raise argparse.ArgumentTypeError(f'{s} is not a valid number or decimal')
        return value

config = ConfigParser()

def CreateSettings():
    config['Input/Output settings'] = {'input_dir': 'lossless',
                              'output_dir': 'AV1',
                              'input_extension': 'mp4',
                              'output_extension': 'mp4',
                              'use_intro': 'False',
                              'use_outro': 'False',
                              'intro_file': 'intro.mp4',
                              'outro_file': 'outro.mp4'}
    
    config['File chunking settings'] = {'chunk_size': '5',
                               'chunk_length': '10',
                               'chunk_mode': '2'}

    config['Encoder settings'] = {'AV1_preset': '6',
                         'max_attempts': '10',
                         'initial_crf_value': '44',
                         'audio_bitrate': '192k',
                         'detect_audio_bitrate': 'False',
                         'pixel_format': 'yuv420p10le',
                         'tune_mode': '0',
                         'keyframe_interval': '300'}

    config['VMAF settings'] = {'VMAF_min_value': '90.5',
                      'VMAF_max_value': '93',
                      'VMAF_offset_threshold': '2',
                      'VMAF_offset_multiplication': '1.3',
                      'VMAF_offset_mode': '2',
                      'initial_crf_step': '1'}

    config['Multiprocessor settings'] = {'enable_multiprocessing_for_single_files': 'False',
                                         'enable_multiprocessing_for_chunks': 'True',
                                         'number_of_processed_files': '2',
                                         'number_of_processed_chunks': '2'}

    config['Verbosity settings'] = {'ffmpeg_verbose_level': '1'}

    config['Temporary settings'] = {'tmp_folder': path.join(gettempdir(), 'VMAF auto converter 3.0'),
                                    'keep_tmp_files': 'False'}

    try:
        with open('settings.ini', 'w') as configfile:
            config.write(configfile)
    except IOError as e:
        print(f'Error writting settings.ini!\n{type(e).__name__} {e}')
        exit(1)

def ReadSettings() -> dict:
    settings = {}
    try:
        config.read('settings.ini')
    except Error as e: # Error is the baseclass exception of ConfigParser
        print(f'Error reading settings.ini!\n{type(e).__name__} {e}')
        exit(1)

    try:
        for section in config:
            for setting in config[section]:
                settings[setting] = config.get(section, setting)
        if not settings:
            raise EmptySettings('No settings found!')
    except Exception as e:
        if type(e).__name__ == 'KeyError':
            print(f'Error applying settings from settings.ini!\n{type(e).__name__} {e}')
        elif type(e).__name__ == 'EmptySettings':
            print(e)
        else:
            print(type(e).__name__, e)
        
        while True:
            EmptySettings_menu = input('Create new settings.ini? Y/N: ').upper()
            if EmptySettings_menu == 'Y':
                CreateSettings()
                print('\nNew settings.ini created! Please start the program again to load the new settings.')
                exit(0)
            elif EmptySettings_menu == 'N':
                exit(1)
            else:
                print(f'\n{EmptySettings_menu} is not a valid choice.\n')
    
    parser = argparse.ArgumentParser(description='AV1 converter script using VMAF to control the quality, version 3', formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument('-v', '--verbosity', metavar='0-2', dest='ffmpeg_verbose_level', default=settings['ffmpeg_verbose_level'], help='0 = hide, 1 = basic, 2 = full', type=int)
    parser.add_argument('-i', '--input', metavar='path', dest='input_dir', default=settings['input_dir'], help='Absolute or relative path to the files', type=str)
    parser.add_argument('-o', '--output', metavar='path', dest='output_dir',  default=settings['output_dir'], help='Absolute or relative path to where the file should be written', type=str)
    parser.add_argument('-iext', '--input-extension', metavar='ext', dest='input_extension', default=settings['input_extension'], help='Container extension to convert from. Use * to specify all', type=str)
    parser.add_argument('-oext', '--output-extension', metavar='ext', dest='output_extension', default=settings['output_extension'], help='Container extension to convert to', type=str)
    parser.add_argument('-ui', '--use-intro', metavar='0-1',  dest='use_intro', default=settings['use_intro'], help='Add intro', type=bool)
    parser.add_argument('-uo', '--use-outro', metavar='0-1', dest='use_outro', default=settings['use_outro'], help='Add outro' , type=bool)
    parser.add_argument('-if', '--intro-file', metavar='path', dest='intro_file', default=settings['intro_file'], help='Absolute or relative path to the intro file, including filename', type=str)
    parser.add_argument('-of', '--outro-file', metavar='path', dest='outro_file', default=settings['outro_file'], help='Absolute or relative path to the outro file, including filename', type=str)
    parser.add_argument('-cm', '--chunk-mode', metavar='0-2', dest='chunk_mode', default=settings['chunk_mode'], help='Disable, split N amount of times, or split into N second long chunks', type=int)
    parser.add_argument('-cs', '--chunk-splits', metavar='N splits', dest='chunk_size', default=settings['chunk_size'], help='How many chunks the video should be divided into', type=int)
    parser.add_argument('-cd', '--chunk-duration', metavar='N seconds', dest='chunk_length', default=settings['chunk_length'], help='Chunk duration in seconds', type=int)
    parser.add_argument('-pr', '--av1-preset', metavar='0-12', dest='av1_preset', default=settings['av1_preset'], help='Encoding preset for the AV1 encoder', type=int)
    parser.add_argument('-ma', '--max-attempts', metavar='N', dest='max_attempts', default=settings['max_attempts'], help='Max attempts before the script skips (but keeps) the file', type=int)
    parser.add_argument('-crf', metavar='1-63', dest='initial_crf_value', default=settings['initial_crf_value'], help='Encoder CRF value to be used', type=int)
    parser.add_argument('-ab', '--audio-bitrate', metavar='bitrate(B/K/M)', dest='audio_bitrate', default=settings['audio_bitrate'], help='Encoder audio bitrate. Use B/K/M to specify bits, kilobits, or megabits', type=str)
    parser.add_argument('-dab', '--detect-audio-bitrate', metavar='0-1', dest='detect_audio_bitrate', default=settings['detect_audio_bitrate'], help='If the script should detect and instead use the audio bitrate from input file', type=bool)
    parser.add_argument('-pxf', '--pixel-format', metavar='pix_fmt', dest='pixel_format', default=settings['pixel_format'], help='Encoder pixel format to use. yuv420p for 8-bit, and yuv420p10le for 10-bit', type=str)
    parser.add_argument('-tune', metavar='0-1', dest='tune_mode', default=settings['tune_mode'], help='Encoder tune mode. 0 = VQ (subjective), 1 = PSNR (objective)', type=int)
    parser.add_argument('-g', '--keyframe-interval', metavar='N frames', dest='keyframe_interval', default=settings['keyframe_interval'], help='Encoder keyframe interval in frames', type=int)
    parser.add_argument('-minq', '--minimum-quality', metavar='N', dest='vmaf_min_value', default=settings['vmaf_min_value'], help='Minimum allowed quality for the output file/chunk, calculated using VMAF. Allows decimal for precision', type=IntOrFloat)
    parser.add_argument('-maxq', '--maximum-quality', metavar='N', dest='vmaf_max_value', default=settings['vmaf_max_value'], help='Maximum allowed quality for the output file/chunk, calculated using VMAF. Allows decimal for precision', type=IntOrFloat)
    parser.add_argument('-vomode', '--vmaf-offset-mode', metavar='0-1', dest='vmaf_offset_mode', default=settings['vmaf_offset_mode'], help='Algorithm to use to exponentially adjust the CRF value. 0 = standard and slow threshold-based, 1 = aggressive but can overshoot multiplier-based', type=int)
    parser.add_argument('-vot', '--vmaf-offset-threshold', metavar='N', dest='vmaf_offset_threshold', default=settings['vmaf_offset_threshold'], help='How many whole percent the VMAF should deviate before CRF value will exponentially increase or decrease', type=int)
    parser.add_argument('-vom', '--vmaf-offset-multiplier', metavar='N', dest='vmaf_offset_multiplication', default=settings['vmaf_offset_multiplication'], help='How much to multiply the VMAF deviation with, exponentially increasing/decreasing the CRF value. Allows decimal for precision', type=IntOrFloat)
    parser.add_argument('--crf-step', metavar='N', dest='initial_crf_step', default=settings['initial_crf_step'], help='How much it should adjust the CRF value on each retry', type=int)
    settings = vars(parser.parse_args())

    return settings

if __name__ == '__main__':
    print('This file should not be run as a standalone script!')