from argparse import ArgumentTypeError
from pathlib import Path
def IntOrFloat(s: str): # Return value from settings.ini or arg as int or float
    """Attempts to convert the given string to an int or float value.
    Raises argparse.ArgumentTypeError if unsuccessful"""
    
    if s.isnumeric(): # Check if the string is numeric i.e. int
        value = int(s)
    else:
        try:
            value = float(s) # Attempt to convert to float, and if it fails, assume value is not int nor float
        except:
            raise ArgumentTypeError(f'{s} is not a valid number or decimal') # Use argparse's TypeError exception to notify the user of a bad value
    return value

def custombool(s: str): # Return value from settings.ini or arg as bool
    """Attempts to convert the given string into a boolean value.
    Raises argparse.ArgumentTypeError if unsuccessful"""

    if s.lower() in ['yes', 'enable', 'on', 'y', '1', 'true']: # Check if the string is any of the positive values in the list, and return True if so
        return True
    elif s.lower() in ['no', 'disable', 'off', 'n', '0', 'false']: # Check if the string is any of the negative values in the list, and return False if so
        return False
    else:
        raise ArgumentTypeError(f'{s} is not a valid True/False flag. Please use "yes", "enable", "on", "y", "1", or "true" for True, and "no", "disable", "off", "n", "0", or "false" for False') # Use argparse's TypeError exception to notify the user of a bad value

def IsPath(s: str):
    """Attempts to validate if the given string representation of a path exists and is a directory.
    Raises argparse.ArgumentTypeError if unsuccessful"""
    
    p = Path(s)
    if p.exists():
        if p.is_dir():
            return str(p)
    raise ArgumentTypeError(f'{s} does not exist or is not a path')

def ParentExists(s: str):
    """Attempts to validate if the given string representation of a path's parent exists.
    Raises argparse.ArgumentTypeError if unsuccessful"""
    
    p = Path(s).parent
    if p.exists():
        return str(s)
    raise ArgumentTypeError(f"{s}'s parent folder does not exist")