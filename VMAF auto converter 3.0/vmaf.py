from json import loads
from os import remove
from pathlib import Path
from subprocess import DEVNULL, run
from time import sleep


def CheckVMAF(settings: dict, input_file: str, output_file: str, physical_cores: int) -> bool | str:
    print(f'\nComparing video quality between {Path(input_file).stem} and {Path(output_file).stem}...\n')
    arg = ['ffmpeg', '-i', output_file, '-i', input_file, '-lavfi', f'libvmaf=log_path=log.json:log_fmt=json:n_threads={physical_cores}', '-f', 'null', '-']
    if settings['ffmpeg_verbose_level'] == 0:
            p = run(arg, stderr=DEVNULL, stdout=DEVNULL)
    else:
        arg[1:1] = settings['ffmpeg_print']
        p = run(arg)
    if p.returncode != 0:
        print(" ".join(arg))
        print('\nError comparing quality!')
        return str('error')
    
    with open('log.json') as f: # Open the json file.
            vmaf_value = float(loads(f.read())['pooled_metrics']['vmaf']['harmonic_mean']) # Parse amd get the 'mean' vmaf value

    print(f'\nVMAF range: {settings["vmaf_min_value"]} - {settings["vmaf_max_value"]}')
    if not settings["vmaf_min_value"] <= vmaf_value <= settings["vmaf_max_value"]: # If VMAF value is not inside the VMAF range
        if vmaf_value < settings["vmaf_min_value"]: # If VMAF value is below the minimum range
            print(f'\nVMAF harmonic mean score of {vmaf_value}... VMAF value too low')
            if settings["vmaf_offset_mode"] == 0 and not (settings["vmaf_min_value"] - vmaf_value) >= 5: # If VMAF offset mode is set to 0 (threshold based) and NOT off by 5 compared to the VMAF min value
                print('\nUsing threshold based increase')
                for _ in range(int((settings["vmaf_min_value"] - vmaf_value) / settings["vmaf_offset_threshold"])): # add 1 to crf_step, for each +2 the VMAF value is under the VMAF minimum e.g. a VMAF value of 86, and a VMAF minimum of 90, would temporarily add 2 to the crf_step
                    settings['crf_step'] += 1
            else:
                print('\nUsing multiplicative based increase')
                settings['crf_step'] += int((settings["vmaf_min_value"] - vmaf_value) * settings["vmaf_offset_multiplication"]) # increase the crf_step by multiplying the VMAF_offset_multiplication with how much the VMAF is offset from the minimum allowed value

            print(f'Retrying with a CRF decrease of {settings["crf_step"]}. New CRF: ({settings["crf_value"] - settings["crf_step"]})...')
            sleep(2)
            settings['crf_value'] -= settings['crf_step']
            if not 1 <= settings['crf_value'] <= 63:
                print('CRF value out of range (1-63). Skipping...')
                return bool(True) #Return True instead of False to skip the file and continue with the next one
            remove(output_file) # Delete converted file to avoid FFmpeg skipping it

        elif vmaf_value > settings["vmaf_max_value"]: # If VMAF value is above the maximum range
            print(f'\nVMAF harmonic mean score of {vmaf_value}... VMAF value too high')
            if settings["vmaf_offset_mode"] == 0 and not (vmaf_value - settings["vmaf_max_value"]) >= 5: # If VMAF offset mode is set to 0 (threshold based) and NOT off by 5 compared to the VMAF max value
                print('\nUsing threshold based increase')
                for _ in range(int((vmaf_value - settings["vmaf_max_value"]) / settings["vmaf_offset_threshold"])): # add 1 to crf_step, for each +2 the VMAF value is above the VMAF maximum e.g. a VMAF value of 99, and a VMAF maximum of 95, would temporarily add 2 to the crf_step
                    settings['crf_step'] += 1
            else:
                print('\nUsing multiplicative based increase')
                settings['crf_step'] += int((vmaf_value - settings["vmaf_max_value"]) * settings["vmaf_offset_multiplication"]) # increase the crf_step by multiplying the VMAF_offset_multiplication with how much the VMAF is offset from the maximum allowed value

            print(f'Retrying with a CRF increase of {settings["crf_step"]}. New CRF: ({settings["crf_value"] + settings["crf_step"]})...')
            sleep(2)
            settings['crf_value'] += settings['crf_step']
            if not 1 <= settings['crf_value'] <= 63:
                print('CRF value out of range (1-63). Skipping...')
                return bool(True) #Return True instead of False to skip the file and continue with the next one
            remove(output_file) # Delete converted file to avoid FFmpeg skipping it
    else:
        print(f'\nVMAF harmonic mean score of {vmaf_value}...\nVMAF score within acceptable range, continuing...\nTook {settings["attempt"]} attempt(s)!\n')
        if settings['chunk_mode'] != 0:
            print(f'Completed chunk {ii} out of {total_chunks}')
        sleep(3)
        return bool(True)

if __name__ == '__main__':
    print('This file should not be run as a standalone script!')