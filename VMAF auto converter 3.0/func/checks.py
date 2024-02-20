from argparse import ArgumentTypeError
from pathlib import Path


def IntOrFloat(s: str) -> int | float:
    """
    Convert a string to either an integer or a float.

    Parameters:
    s (str): The input string to be converted.

    Returns:
    int or float: The converted value.

    Raises:
    ArgumentTypeError: If the input string is not a valid number or decimal.
    """
    if s.isnumeric():
        value = int(s)
    else:
        try:
            value = float(s)
        except ValueError:
            raise ArgumentTypeError(f'{s} is not a valid number or decimal')
    return value


def custombool(s: str) -> bool:
    """
    Convert a string to a boolean value.

    Args:
        s (str): The string to be converted.

    Returns:
        bool: The boolean value corresponding to the input string.

    Raises:
        ArgumentTypeError: If the input string is not a valid True/False flag.

    """
    if s.lower() in ['yes', 'enable', 'on', 'y', '1', 'true']:
        return True
    elif s.lower() in ['no', 'disable', 'off', 'n', '0', 'false']:
        return False
    else:
        raise ArgumentTypeError(
            f'{s} is not a valid True/False flag. Please use "yes", "enable", "on", "y", "1", '
            'or "true" for True, and "no", "disable", "off", "n", "0", or "false" for False')


def IsPath(s: str) -> str:
    """
    Check if the given string represents an existing directory path.

    Args:
        s (str): The string to check.

    Returns:
        str: The validated directory path.

    Raises:
        ArgumentTypeError: If the string does not exist or is not a path.
    """
    p = Path(s)
    if p.exists():
        if p.is_dir():
            return str(p)
    raise ArgumentTypeError(f'{s} does not exist or is not a path')


def ParentExists(s: str) -> str:
    """
    Check if the parent folder of the given path exists.

    Args:
        s (str): The path to check.

    Returns:
        str: The input path if the parent folder exists.

    Raises:
        ArgumentTypeError: If the parent folder does not exist.
    """
    p = Path(s).parent
    if p.exists():
        return str(s)
    raise ArgumentTypeError(f"{s}'s parent folder does not exist")
