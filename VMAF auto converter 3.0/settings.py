import argparse
from configparser import ConfigParser, Error
from pathlib import Path
from tempfile import gettempdir


class EmptySettings(Exception):
    pass

def IntOrFloat(s: str): # Return value from settings.ini or arg as int or float
    """Attempts to convert the given string to an int or float value.
    Raises argparse.ArgumentTypeError if unsuccessful"""
    
    if s.isnumeric(): # Check if the string is numeric i.e. int
        value = int(s)
    else:
        try:
            value = float(s) # Attempt to convert to float, and if it fails, assume value is not int nor float
        except:
            raise argparse.ArgumentTypeError(f'{s} is not a valid number or decimal') # Use argparse's TypeError exception to notify the user of a bad value
    return value

def custombool(s: str): # Return value from settings.ini or arg as bool
    """Attempts to convert the given string into a boolean value.
    Raises argparse.ArgumentTypeError if unsuccessful"""

    if s.lower() in ['yes', 'enable', 'on', 'y', '1', 'true']: # Check if the string is any of the positive values in the list, and return True if so
        return True
    elif s.lower() in ['no', 'disable', 'off', 'n', '0', 'false']: # Check if the string is any of the negative values in the list, and return False if so
        return False
    else:
        raise argparse.ArgumentTypeError(f'{s} is not a valid True/False flag. Please use "yes", "enable", "on", "y", "1", or "true" for True, and "no", "disable", "off", "n", "0", or "false" for False') # Use argparse's TypeError exception to notify the user of a bad value

def IsPath(s: str):
    """Attempts to validate if the given string representation of a path exists and is a directory.
    Raises argparse.ArgumentTypeError if unsuccessful"""
    
    p = Path(s)
    if p.exists():
        if p.is_dir():
            return str(p)
    raise argparse.ArgumentTypeError(f'{s} does not exist or is not a path')

def ParentExists(s: str):
    """Attempts to validate if the given string representation of a path's parent exists.
    Raises argparse.ArgumentTypeError if unsuccessful"""
    
    p = Path(s).parent
    if p.exists():
        return str(s)
    raise argparse.ArgumentTypeError(f"{s}'s parent folder does not exist")

config = ConfigParser()

def CreateSettings(): # Simple method to create a settings file, either if missing or potentially broken
    """Creates settings.ini file using hardcoded default values. Overwrites if the file already exists."""
    
    config['Input/Output settings'] = {'input_dir': 'lossless',
                              'output_dir': 'AV1',
                              'input_extension': 'mp4',
                              'output_extension': 'mp4',
                              'use_intro': 'no',
                              'use_outro': 'no',
                              'intro_file': 'intro.mp4',
                              'outro_file': 'outro.mp4'}
    
    config['File chunking settings'] = {'chunk_size': '5',
                               'chunk_length': '10',
                               'chunk_mode': '2'}

    config['Encoder settings'] = {'AV1_preset': '6',
                         'max_attempts': '10',
                         'initial_crf_value': '44',
                         'audio_bitrate': '192k',
                         'detect_audio_bitrate': 'no',
                         'pixel_format': 'yuv420p10le',
                         'tune_mode': '0',
                         'keyframe_interval': '300'}

    config['VMAF settings'] = {'VMAF_min_value': '90.5',
                      'VMAF_max_value': '93',
                      'VMAF_offset_threshold': '2',
                      'VMAF_offset_multiplication': '1.3',
                      'VMAF_offset_mode': '2',
                      'initial_crf_step': '1'}

    config['Multiprocessor settings'] = {'file_threads': '1',
                                         'chunk_threads': '2'}

    config['Verbosity settings'] = {'ffmpeg_verbose_level': '0'}

    config['Temporary settings'] = {'tmp_folder': Path(gettempdir()) / 'VMAF auto converter 3.0',
                                    'keep_tmp_files': 'no'}

    try:
        with open('settings.ini', 'w') as configfile: # Write or overwrite the settings file, with the dictionary data previously created and added to config
            config.write(configfile)
    except IOError as e:
        print(f'Error writting settings.ini!\n{type(e).__name__} {e}')
        exit(1)

def ReadSettings() -> dict: # Simple method that reads and parses the settings file into a dictionary, and returns it
    """Reads settings.ini, iterating through each setting and assigning it to a dictionary named 'settings'.
    Uses Argparse to both validate the values and allow arguments from the terminal, using the settings dictionary as the default values.
    
    Returns a dictionary named 'settings' with all loaded settings."""
    settings = {}
    try:
        config.read('settings.ini')
    except Error as e: # Error is the baseclass exception of ConfigParser
        print(f'Error reading settings.ini!\n{type(e).__name__} {e}')
        exit(1)

    try:
        for section in config: # Loop through each [Section] in the settings file
            for setting in config[section]: # Loop through each key= in each [Section]
                settings[setting] = config.get(section, setting) # Use key= to both find the value in the settings file, and create a new key with the same name in the dictionary variable
        if not settings: # If the settings dictionary variable is empty e.g. due to the file being empty, or incorrectly being parsed, raise an exception
            raise EmptySettings('No settings found in settings.ini!')
    
        parser = argparse.ArgumentParser(description='AV1 converter script using VMAF to control the quality, version 3', formatter_class=argparse.ArgumentDefaultsHelpFormatter)

        # Use the loaded settings dictionary as a default value for each parameter.
        # and likewise save any parameter value to a variable of the same name in it's namespace.
        # Use Type= to check and convert the string values to their correct types.
        # Throws ArgumentTypeError if one of the values is of incorrect type.
        # Throws KeyError if one of the settings are missing from the settings file.
        parser.add_argument('-v', '--verbosity', metavar='0-2', dest='ffmpeg_verbose_level', default=settings['ffmpeg_verbose_level'], help='0 = hide, 1 = basic, 2 = full', type=int)
        parser.add_argument('-i', '--input', metavar='PATH', dest='input_dir', default=settings['input_dir'], help='Absolute or relative path to the files', type=IsPath)
        parser.add_argument('-o', '--output', metavar='PATH', dest='output_dir',  default=settings['output_dir'], help='Absolute or relative path to where the file should be written', type=str)
        parser.add_argument('-iext', '--input-extension', metavar='ext', dest='input_extension', default=settings['input_extension'], help='Container extension to convert from. Use * to specify all', type=str)
        parser.add_argument('-oext', '--output-extension', metavar='ext', dest='output_extension', default=settings['output_extension'], help='Container extension to convert to', type=str)
        parser.add_argument('-ui', '--use-intro', metavar='yes/no',  dest='use_intro', default=settings['use_intro'], help='Add intro', type=custombool)
        parser.add_argument('-uo', '--use-outro', metavar='yes/no', dest='use_outro', default=settings['use_outro'], help='Add outro' , type=custombool)
        parser.add_argument('-if', '--intro-file', metavar='FILE', dest='intro_file', default=settings['intro_file'], help='Absolute or relative path to the intro file, including filename', type=str)
        parser.add_argument('-of', '--outro-file', metavar='FILE', dest='outro_file', default=settings['outro_file'], help='Absolute or relative path to the outro file, including filename', type=str)
        parser.add_argument('-cm', '--chunk-mode', metavar='0-3', dest='chunk_mode', default=settings['chunk_mode'], help='Disable, split N amount of times, split into N second long chunks or split by the input keyframe interval', type=int)
        parser.add_argument('-cs', '--chunk-splits', metavar='N splits', dest='chunk_size', default=settings['chunk_size'], help='How many chunks the video should be divided into', type=int)
        parser.add_argument('-cd', '--chunk-duration', metavar='N seconds', dest='chunk_length', default=settings['chunk_length'], help='Chunk duration in seconds', type=int)
        parser.add_argument('-pr', '--av1-preset', metavar='0-12', dest='av1_preset', default=settings['av1_preset'], help='Encoding preset for the AV1 encoder', type=int)
        parser.add_argument('-ma', '--max-attempts', metavar='N', dest='max_attempts', default=settings['max_attempts'], help='Max attempts before the script skips (but keeps) the file', type=int)
        parser.add_argument('-crf', metavar='1-63', dest='initial_crf_value', default=settings['initial_crf_value'], help='Encoder CRF value to be used', type=int)
        parser.add_argument('-ab', '--audio-bitrate', metavar='bitrate(B/K/M)', dest='audio_bitrate', default=settings['audio_bitrate'], help='Encoder audio bitrate. Use B/K/M to specify bits, kilobits, or megabits', type=str)
        parser.add_argument('-dab', '--detect-audio-bitrate', metavar='yes/no', dest='detect_audio_bitrate', default=settings['detect_audio_bitrate'], help='If the script should detect and instead use the audio bitrate from input file', type=custombool)
        parser.add_argument('-pxf', '--pixel-format', metavar='pix_fmt', dest='pixel_format', default=settings['pixel_format'], help='Encoder pixel format to use. yuv420p for 8-bit, and yuv420p10le for 10-bit', type=str)
        parser.add_argument('-tune', metavar='0-1', dest='tune_mode', default=settings['tune_mode'], help='Encoder tune mode. 0 = VQ (subjective), 1 = PSNR (objective)', type=int)
        parser.add_argument('-g', '--keyframe-interval', metavar='N frames', dest='keyframe_interval', default=settings['keyframe_interval'], help='Encoder keyframe interval in frames', type=int)
        parser.add_argument('-minq', '--minimum-quality', metavar='N', dest='vmaf_min_value', default=settings['vmaf_min_value'], help='Minimum allowed quality for the output file/chunk, calculated using VMAF. Allows decimal for precision', type=IntOrFloat)
        parser.add_argument('-maxq', '--maximum-quality', metavar='N', dest='vmaf_max_value', default=settings['vmaf_max_value'], help='Maximum allowed quality for the output file/chunk, calculated using VMAF. Allows decimal for precision', type=IntOrFloat)
        parser.add_argument('-vomode', '--vmaf-offset-mode', metavar='0-1', dest='vmaf_offset_mode', default=settings['vmaf_offset_mode'], help='Algorithm to use to exponentially adjust the CRF value. 0 = standard and slow threshold-based, 1 = aggressive but can overshoot multiplier-based', type=int)
        parser.add_argument('-vot', '--vmaf-offset-threshold', metavar='N', dest='vmaf_offset_threshold', default=settings['vmaf_offset_threshold'], help='How many whole percent the VMAF should deviate before CRF value will exponentially increase or decrease', type=int)
        parser.add_argument('-vom', '--vmaf-offset-multiplier', metavar='N', dest='vmaf_offset_multiplication', default=settings['vmaf_offset_multiplication'], help='How much to multiply the VMAF deviation with, exponentially increasing/decreasing the CRF value. Allows decimal for precision', type=IntOrFloat)
        parser.add_argument('--crf-step', metavar='N', dest='initial_crf_step', default=settings['initial_crf_step'], help='How much it should adjust the CRF value on each retry', type=int)
        parser.add_argument('--file-threads', metavar='N', dest='file_threads', default=settings['file_threads'], help="Control how many files should be processed at the same time, with multiprocessing. Higher = more CPU usage", type=int)
        parser.add_argument('--chunk-threads', metavar='N', dest='chunk_threads', default=settings['chunk_threads'], help='Control how many chunks should be processed at the same time, with multiprocessing. Higher = more CPU usage', type=int)
        parser.add_argument('--tmp-dir', metavar='PATH', dest='tmp_folder', default=settings['tmp_folder'], help='Folder to store the temporary files used by the script. Note: Folder and all content will be deleted on exit, if keep_tmp_files is off', type=ParentExists)
        parser.add_argument('--keep-tmp-files', metavar='yes/no', dest='keep_tmp_files', default=settings['keep_tmp_files'], help='If 0/False, delete when done. If 1/True, keep when done', type=custombool)
        
        #Take dictionary-formated variables from it's namespace and overwrite the settings. Non-specified args simply re-use the value from the settings, through the default= flag in add_argument
        settings = vars(parser.parse_args())

    except Exception as e:
        if type(e).__name__ == 'KeyError':
            print(f'Error applying settings from settings.ini!\n{type(e).__name__} {e}')
        elif type(e).__name__ == 'EmptySettings':
            print(e)
        else:
            print(type(e).__name__, e)
        
        EmptySettings_menu = None
        while EmptySettings_menu != 'Y' or EmptySettings_menu != 'N':
            EmptySettings_menu = input('Create new settings.ini? Y/N: ').upper()
            if EmptySettings_menu == 'Y':
                CreateSettings()
                print('\nNew settings.ini created! Please start the program again to load the new settings.')
                exit(0)
            elif EmptySettings_menu == 'N':
                exit(1)
            else:
                print(f'\nOnly "y" and "n" are supported\n')

    if settings['ffmpeg_verbose_level'] == 0:
        settings['ffmpeg_print'] = ['-n', '-hide_banner', '-v', 'quiet']
    elif settings['ffmpeg_verbose_level'] == 1:
        settings['ffmpeg_print'] = ['-n', '-hide_banner', '-v', 'quiet', '-stats']
    else:
        settings['ffmpeg_print'] = None

    return settings

if __name__ == '__main__':
    print('This file should not be run as a standalone script!')