from os import mkdir, remove
from pathlib import Path
from shutil import rmtree


def cleanup(settings: dict) -> None:
    """Removes the leftover files generated by the script or ffmpeg from the working directory."""
    print('\ncleaning up...')
    tmpfile_list = ['IntroOutroList.txt', 'log.json', 'ffmpeg2pass-0.log']
    for tmp in tmpfile_list:
        try:
            remove(tmp)
        except:
            pass
    
    if Path(settings['tmp_folder']).exists() and not settings['keep_tmp_files']:
        tmpcleanup(settings)

def tmpcleanup(settings: dict) -> None:
    try:
        rmtree(settings['tmp_folder'])
    except:
        print('\nError cleaning up temp directory')

def CreateTempFolder(settings: dict) -> None:
    """Creates the temporary folder used for chunk-based encoding and audio extraction.
    If the folder already exists, it will be wiped first."""
    try:
        mkdir(settings['tmp_folder'])
        mkdir(Path(settings['tmp_folder']) / 'prepared')
        mkdir(Path(settings['tmp_folder']) / 'converted')
    except FileExistsError:
        tmpcleanup(settings)
        mkdir(settings['tmp_folder'])
        mkdir(Path(settings['tmp_folder']) / 'prepared')
        mkdir(Path(settings['tmp_folder']) / 'converted')

if __name__ == '__main__':
    print('This file should not be run as a standalone script!')