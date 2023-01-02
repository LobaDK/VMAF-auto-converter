from os import remove
from pathlib import Path
from shutil import rmtree


def cleanup(settings: dict):
    print('cleaning up...')
    tmpfile_list = ['IntroOutroList.txt', 'log.json', 'ffmpeg2pass-0.log']
    for tmp in tmpfile_list:
        try:
            remove(tmp)
        except:
            pass
    
    if Path(settings['tmp_folder']).exists():
        tmpcleanup(settings)

def tmpcleanup(settings: dict):
    try:
        rmtree(settings['tmp_folder'])
    except:
        print('\nError cleaning up temp directory')

if __name__ == '__main__':
    print('This file should not be run as a standalone script!')