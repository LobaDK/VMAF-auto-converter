from os import path
from settings import CreateSettings, ReadSettings

if path.exists('settings.ini'):
    settings = ReadSettings()
else:
    CreateSettings()
    settings = ReadSettings()

print('\n', settings)