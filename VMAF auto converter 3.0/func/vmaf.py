from __future__ import annotations
from json import loads
from os import remove
from pathlib import Path
from subprocess import DEVNULL, run
from time import sleep
import logging
import logging.handlers


class VMAFError(Exception):
    pass


def CheckVMAF(settings: dict,
              crf_value: int,
              crf_step: int,
              input_file: str,
              output_file: str,
              attempt: int) -> bool:
    """Compare the converted video or chunk to the original.
    Returns False if the quality is above or below the required score.
    Returns True if the quality is within the required score or the CRF value is above or below the supported values.
    Raises a VMAFError if an error was encountered
    """
    handler = logging.handlers.QueueHandler(settings['log_queue'])
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(logging.INFO)

    print(f'\nComparing video quality of {Path(output_file).stem}...')
    logging.info(f'Comparing video quality of {Path(output_file).stem}...')
    arg = ['ffmpeg', '-i', output_file, '-i', input_file, '-lavfi', f'libvmaf=log_path=log.json:log_fmt=json:n_threads={settings["physical_cores"]}', '-f', 'null', '-']
    if settings['ffmpeg_verbose_level'] == 0:
        p = run(arg, stderr=DEVNULL, stdout=DEVNULL)
    else:
        arg[1:1] = settings['ffmpeg_print']
        p = run(arg)
    if p.returncode != 0:
        print(" ".join(arg))
        print('\nError comparing quality!')
        logging.error(f'Error comparing quality of {Path(output_file).stem} with {Path(input_file).stem} using arg: {" ".join(arg)}')
        raise VMAFError('Error comparing quality')

    # Open the json file and get the "mean" VMAF value
    with open('log.json') as f:
        vmaf_value = float(loads(f.read())['pooled_metrics']['vmaf']['harmonic_mean'])

    # If VMAF value is not inside the VMAF range
    if not settings["vmaf_min_value"] <= vmaf_value <= settings["vmaf_max_value"]:
        # If VMAF value is below the minimum range
        if vmaf_value < settings["vmaf_min_value"]:
            # If VMAF offset mode is set to 0 (threshold based) and NOT off by 5 compared to the VMAF min value
            if settings["vmaf_offset_mode"] == 0 and not (settings["vmaf_min_value"] - vmaf_value) >= 5:
                # add 1 to crf_step, for each +2 the VMAF value is under the VMAF minimum e.g. a VMAF value of 86, and a VMAF minimum of 90, would temporarily add 2 to the crf_step
                for _ in range(int((settings["vmaf_min_value"] - vmaf_value) / settings["vmaf_offset_threshold"])):
                    crf_step += 1
            else:
                # increase the crf_step by multiplying the VMAF_offset_multiplication with how much the VMAF is offset from the minimum allowed value
                crf_step += int((settings["vmaf_min_value"] - vmaf_value) * settings["vmaf_offset_multiplication"])

            print((f'\nFile {Path(output_file).stem} too low:\n'
                   f'Min: {settings["vmaf_min_value"]}, Max: {settings["vmaf_max_value"]}, '
                   f'Current: {vmaf_value}, Deviation: {round(settings["vmaf_min_value"] - vmaf_value, 2)}\n'
                   f'Current CRF: {crf_value}, New CRF: {crf_value - crf_step}, '
                   f'Offset_mode: {"Slow, precise" if settings["vmaf_offset_mode"] == 0 and not (settings["vmaf_min_value"] - vmaf_value) >= 5 else "Fast, can overshoot"}\n'
                   f'Attempt: {attempt}'))

            sleep(2)
            crf_value -= crf_step
            if not 1 <= crf_value <= 63:
                print('CRF value out of range (1-63). Skipping...')
                # Return False instead of True to skip the file and continue with the next one
                return False
            # Delete converted file to avoid FFmpeg skipping it
            remove(output_file)
            return True

        # If VMAF value is above the maximum range
        elif vmaf_value > settings["vmaf_max_value"]:
            # If VMAF offset mode is set to 0 (threshold based) and NOT off by 5 compared to the VMAF max value
            if settings["vmaf_offset_mode"] == 0 and not (vmaf_value - settings["vmaf_max_value"]) >= 5:
                # add 1 to crf_step, for each +2 the VMAF value is above the VMAF maximum e.g. a VMAF value of 99, and a VMAF maximum of 95, would temporarily add 2 to the crf_step
                for _ in range(int((vmaf_value - settings["vmaf_max_value"]) / settings["vmaf_offset_threshold"])):
                    crf_step += 1
            else:
                # increase the crf_step by multiplying the VMAF_offset_multiplication with how much the VMAF is offset from the maximum allowed value
                crf_step += int((vmaf_value - settings["vmaf_max_value"]) * settings["vmaf_offset_multiplication"])

            print((f'\nFile {Path(output_file).stem} too high:\n'
                   f'Min: {settings["vmaf_min_value"]}, Max: {settings["vmaf_max_value"]}, '
                   f'Current: {vmaf_value}, Deviation: {round(vmaf_value - settings["vmaf_max_value"], 2)}\n'
                   f'Current CRF: {crf_value}, New CRF: {crf_value + crf_step}, '
                   f'Offset_mode: {"Slow, precise" if settings["vmaf_offset_mode"] == 0 and not (settings["vmaf_min_value"] - vmaf_value) >= 5 else "Fast, can overshoot"}\n'
                   f'Attempt: {attempt}'))

            sleep(2)
            crf_value += crf_step
            if not 1 <= crf_value <= 63:
                print('CRF value out of range (1-63). Skipping...')
                # Return False instead of True to skip the file and continue with the next one
                return False
            # Delete converted file to avoid FFmpeg skipping it
            remove(output_file)
            return True
    else:
        print((f'\nFile {Path(output_file).stem} complete:\n'
               f'Min: {settings["vmaf_min_value"]}, Max: {settings["vmaf_max_value"]}, '
               f'Current: {vmaf_value}\n'
               f'attempts: {attempt}'))
        sleep(3)
        return False


if __name__ == '__main__':
    print('This file should not be run as a standalone script!')
