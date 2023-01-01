import glob
import json
import os
import subprocess
import time
import signal

def signal_handler(sig, frame):
    print('Cleaning up...')
    try:        
        os.remove('log.json')
    except:
        pass
    try:
        os.remove('ffmpeg2pass-0.log')
    except:
        pass
    exit()

signal.signal(signal.SIGINT, signal_handler)

#Input & output parameters:
input_dir = 'lossless' # Change this to set a custom input directory. Dot can be used to specify same directory as the script
output_dir = 'AV1' # Change this to set a custom input directory. Dot can be used to specify same directory as the script
# Changing both to a dot is not adviced since the original filename is reused in the output, meaning if they share the same extension, ffmpeg will either outright fail, or the script can delete the input file
input_extension = 'mp4' # Change this to set the container type that should be converted. A * (wildcard) can instead be used to ignore container type, but make sure there's only video files in the given directory then 
output_extension = 'mp4' # Can be changed to another extension, but only recommended if the encoder codec has been changed to another one

#Scene split parameters:
scene_splits = 5
use_scene_splits = True

#Encoding parameters:
AV1_preset = 6 # Preset level for AV1 encoder, supporting levels 1-8. Lower means smaller size + same or higher quality, but also goes exponentially slower, the lower the number is. 6 is a good ratio between size/quality and time
max_attempts = 10 # Change this to set the max amount of allowed retries before quitting
use_multipass_encoding = False # Change to True if ffmpeg should use multi-pass encoding. CRF mode in SVT-AV1 barely benefits from it, while doubling the encoding time
initial_crf_value = 45 # Change this to set the default CRF value for ffmpeg to start converting with

#VMAF parameters:
VMAF_min_value = 90 # Change this to determine the minimum allowed VMAF quality
VMAF_max_value = 93 # Change this to determine the maximum allowed VMAF quality
VMAF_offset_threshold = 2 # Change this to determine how much the VMAF value can deviate from the minimum and maximum values, before it starts to exponentially inecrease the CRF value (crf_step is increased by 1 for every time the value is VMAF_offset_threshold off from the minimum or maxumum VMAF value)
                       #^
                       # Decimal numbers are not supported
VMAF_offset_multiplication = 1.3 # Change this to determine how much it should multiply the CRF, based on the difference between the VMAF_min or max value, and the vmaf_value. 2 and above is considered too aggressive, and will overshoot way too much
VMAF_offset_mode = 0 # Change this to set the VMAF mode used to calculate exponential increase/decrease. 0 for threshold based increase, any other number for multiplication based increase
# 0 (threshold based) is less aggressive, and will use more attempts as it's exponential increase is limited, but can also be slightly more accurate. Very good for low deviations
# Secondary option (multiplication based) is way more aggressive, but also more flexible, resulting in less attempts, but can also over- and undershoot the target, and may be less accurate. Very good for high deviations
# If the VMAF offset is 5 or more, it will automatically switch to a multiplication based exponential increase regardless of user settings
initial_crf_step = 1 # Change this to set the amount the CRF value should change per retry. Is overwritten if VMAF_offset_mode is NOT 0

physical_cores = int(os.cpu_count() / 2) # get the amount of physical cores available on system.

if os.name == 'nt': # Visual Studio Code will complain about either one being unreachable, since os.name is a variable. Just ignore this
    pass_1_output = 'NUL'
else:
    pass_1_output = '/dev/null'

try:
    os.mkdir(output_dir)
except:
    pass
for file in glob.glob(f'{input_dir}{os.path.sep}*.{input_extension}'):
    filename, extension = os.path.splitext(file)
    vmaf_value = 0 # Reset the VMAF value for each new file. Technically not needed, but nice to have I guess
    attempt = 0 # Reset the attempts for each new file
    crf_value = initial_crf_value
    while True:
        crf_step = initial_crf_step
        if attempt >= max_attempts:
            print('\nMaximum amount of allowed attempts exceeded. skipping...')
            time.sleep(2)
            break
        attempt += 1
        if not glob.glob(f'{output_dir}{os.path.sep}{os.path.basename(filename)}.*'): #check if the same filename already exists in the output folder. Extension is ignored to allow custom input container types/extensions
            if use_multipass_encoding:
                multipass_p1 = subprocess.run(['ffmpeg', '-n', '-i', file, '-c:a', 'aac', '-c:v', 'libsvtav1', '-crf', str(crf_value), '-b:v', '0', '-an', '-g', '600', '-preset', str(AV1_preset), '-movflags', '+faststart', '-pass', '1', '-f', 'null', pass_1_output])
                if multipass_p1.returncode == 0: # Skip on error
                    multipass_p2 = subprocess.run(['ffmpeg', '-n', '-i', file, '-c:a', 'aac', '-c:v', 'libsvtav1', '-crf', str(crf_value), '-b:v', '0', '-b:a', '192k', '-g', '600', '-preset', str(AV1_preset), '-movflags', '+faststart', '-pass', '2', f'{output_dir}{os.path.sep}{os.path.basename(filename)}.{output_extension}'])
                    if multipass_p2.returncode != 0: # Skip on error
                        break
                else:
                    break
            else:
                p1 = subprocess.run(['ffmpeg', '-n', '-i', file, '-c:a', 'aac', '-c:v', 'libsvtav1', '-crf', str(crf_value), '-b:v', '0', '-b:a', '192k', '-g', '600', '-preset', str(AV1_preset), '-movflags', '+faststart', f'{output_dir}{os.path.sep}{os.path.basename(filename)}.{output_extension}'])
                if p1.returncode != 0: # Skip on error
                    break

            subprocess.run(['ffmpeg', '-i', f'{output_dir}{os.path.sep}{os.path.basename(filename)}.{output_extension}', '-i', file, '-lavfi', f'libvmaf=log_path=log.json:log_fmt=json:n_threads={physical_cores}', '-f', 'null', '-'])
            with open('log.json') as f: # Open the json file.
                vmaf_value = float(json.loads(f.read())['pooled_metrics']['vmaf']['mean']) # Parse amd get the 'mean' vmaf value

            if not VMAF_min_value <= vmaf_value <= VMAF_max_value: # If VMAF value is not inside the VMAF range
                if vmaf_value < VMAF_min_value: # If VMAF value is below the minimum range
                    if VMAF_offset_mode == 0 and not (VMAF_min_value - vmaf_value) >= 5: # If VMAF offset mode is set to 0 (threshold based) and NOT off by 5 compared to the VMAF min value
                        print('\nUsing threshold based increase')
                        for _ in range(int((VMAF_min_value - vmaf_value) / VMAF_offset_threshold)): # add 1 to crf_step, for each +2 the VMAF value is under the VMAF minimum e.g. a VMAF value of 86, and a VMAF minimum of 90, would temporarily add 2 to the crf_step
                            crf_step += 1
                    else:
                        print('\nUsing multiplicative based increase')
                        crf_step += int((VMAF_min_value - vmaf_value) * VMAF_offset_multiplication)

                    print(f'VMAF value too low, retrying with a CRF decrease of {crf_step}. New CRF: ({crf_value - crf_step})...')
                    time.sleep(2)
                    crf_value -= crf_step
                    os.remove(f'{output_dir}{os.path.sep}{os.path.basename(filename)}.{output_extension}') # Delete converted file to avoid FFmpeg skipping it

                elif vmaf_value > VMAF_max_value: # If VMAF value is above the maximum range
                    if VMAF_offset_mode == 0 and not (vmaf_value - VMAF_max_value) >= 5: # If VMAF offset mode is set to 0 (threshold based) and NOT off by 5 compared to the VMAF max value
                        print('\nUsing threshold based increase')
                        for _ in range(int((vmaf_value - VMAF_max_value) / VMAF_offset_threshold)): # add 1 to crf_step, for each +2 the VMAF value is above the VMAF maximum e.g. a VMAF value of 99, and a VMAF maximum of 95, would temporarily add 2 to the crf_step
                            crf_step += 1
                    else:
                        print('\nUsing multiplicative based increase')
                        crf_step += int((vmaf_value - VMAF_max_value) * VMAF_offset_multiplication)

                    print(f'VMAF value too high, retrying with a CRF increase of {crf_step}. New CRF: ({crf_value + crf_step})...')
                    time.sleep(2)
                    crf_value += crf_step
                    os.remove(f'{output_dir}{os.path.sep}{os.path.basename(filename)}.{output_extension}') # Delete converted file to avoid FFmpeg skipping it
                    
                continue
            else:
                print(f'\nVMAF score within acceptable range, continuing...\nTook {attempt} attempt(s)!')
                time.sleep(3)
                break

        else:
            break
try:        
    os.remove('log.json')
except:
    pass
try:
    os.remove('ffmpeg2pass-0.log')
except:
    pass
input('\nDone!\n\nPress enter to exit')