from __future__ import annotations
from json import loads
from os import remove
from pathlib import Path
from subprocess import DEVNULL, run
from time import sleep
from func.logger import create_logger


class VMAFError(Exception):
    pass


def CheckVMAF(settings: dict,
              crf_value: int,
              crf_step: int,
              input_file: str,
              output_file: str,
              attempt: int) -> bool:
    """
    Check the VMAF (Video Multimethod Assessment Fusion) value of a video file and adjust the CRF (Constant Rate Factor) value based on the VMAF range.

    Args:
        settings (dict): A dictionary containing various settings for the VMAF check.
        crf_value (int): The current CRF value.
        crf_step (int): The step size for adjusting the CRF value.
        input_file (str): The path to the input video file.
        output_file (str): The path to the output video file.
        attempt (int): The number of attempts made to adjust the CRF value.

    Returns:
        bool: True if the CRF value was adjusted and the file should be reprocessed, False if the file should be skipped and the next one should be processed.
    """
    logger = create_logger(settings['log_queue'], 'VMAF')

    logger.info(f'Comparing video quality of {Path(output_file).stem}...')
    arg = ['ffmpeg', '-i', output_file, '-i', input_file, '-lavfi', f'libvmaf=log_path=log.json:log_fmt=json:n_threads={settings["physical_cores"]}', '-f', 'null', '-']
    if settings['ffmpeg_verbose_level'] == 0:
        p = run(arg, stderr=DEVNULL, stdout=DEVNULL)
    else:
        arg[1:1] = settings['ffmpeg_print']
        p = run(arg)
    if p.returncode != 0:
        logger.error(f'Error comparing quality of {Path(output_file).stem} with {Path(input_file).stem} using arg: {" ".join(str(item) for item in arg)}')
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

            message = f"""
                      File {Path(output_file).stem} too low:
                      Min: {settings["vmaf_min_value"]}, Max: {settings["vmaf_max_value"]},
                      Current: {vmaf_value}, Deviation: {round(settings["vmaf_min_value"] - vmaf_value, 2)}
                      Current CRF: {crf_value}, New CRF: {crf_value - crf_step},
                      Offset_mode: {"Slow, precise" if settings["vmaf_offset_mode"] == 0 and not (settings["vmaf_min_value"] - vmaf_value) >= 5 else "Fast, can overshoot"}
                      Attempt: {attempt}
                      """
            logger.info(message.strip())

            sleep(2)
            crf_value -= crf_step
            if not 1 <= crf_value <= 63:
                logger.info('CRF value out of range (1-63). Skipping...')
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
            message = f"""
                      File {Path(output_file).stem} too high:
                      Min: {settings["vmaf_min_value"]}, Max: {settings["vmaf_max_value"]},
                      Current: {vmaf_value}, Deviation: {round(vmaf_value - settings["vmaf_max_value"], 2)}
                      Current CRF: {crf_value}, New CRF: {crf_value + crf_step},
                      Offset_mode: {"Slow, precise" if settings["vmaf_offset_mode"] == 0 and not (settings["vmaf_min_value"] - vmaf_value) >= 5 else "Fast, can overshoot"}
                      Attempt: {attempt}
                      """
            logger.info(message.strip())

            sleep(2)
            crf_value += crf_step
            if not 1 <= crf_value <= 63:
                logger.info('CRF value out of range (1-63). Skipping...')
                # Return False instead of True to skip the file and continue with the next one
                return False
            # Delete converted file to avoid FFmpeg skipping it
            remove(output_file)
            return True
    else:
        message = f"""
                  File {Path(output_file).stem} complete:
                  Min: {settings["vmaf_min_value"]}, Max: {settings["vmaf_max_value"]}, Current: {vmaf_value}
                  attempts: {attempt}
                  """
        logger.info(message.strip())
        sleep(3)
        return False


if __name__ == '__main__':
    print('This file should not be run as a standalone script!')
