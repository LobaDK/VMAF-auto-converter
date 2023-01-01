from configparser import ConfigParser, Error
from os import path
from tempfile import gettempdir
import argparse

class EmptySettings(Exception):
    pass

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

def ReadSettings():
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
    
    print(settings)

def CheckSettings():
    pass

def ParseArgs():
    pass

if __name__ == '__main__':
    print('This file should not be run as a standalone script!')