import glob
import subprocess
import os
import json
import time

input_dir = 'lossless' #Change this to set a custom input directory. Dot can be used to specify same directory as the script
output_dir = 'AV1' #Change this to set a custom input directory. Dot can be used to specify same directory as the script
#Changing both to a dot is not adviced since the original filename is reused in the output, meaning if they share the same extension, ffmpeg will either outright fail, or the script can delete the input file

input_extension = 'mp4' #Change this to set the container type that should be converted. A * (wildcard) can instead be used to ignore container type, but make sure there's only video files in the given directory then 
logical_cores = round(os.cpu_count() / 2) # get the amount of logical cores available on system.
max_attempt = 10 #Change this to set the max amount of allowed retries before quitting
VMAF_min_value = 90 #Change this to determine the minimum allowed VMAF quality
VMAF_max_value = 95 #Change this to determine the maximum allowed VMAF quality
VMAF_offset_threshold = 2 #Change this to determine how much the VMAF value can deviate from the minimum and maximum values, before it starts to exponentially inecrease the CRF value (crf_step is increased by 1 for every time the value is VMAF_offset_threshold off from the minimum or maxumum VMAF value)

if os.name == 'nt': #Visual Studio Code will complain about either one being unreachable, since os.name is a variable. Just ignore this
    pass_1_output = 'NUL'
else:
    pass_1_output = '/dev/null'

try:
    os.mkdir(output_dir)
except:
    pass
for file in glob.glob(f'{input_dir}{os.path.sep}*.{input_extension}'):
    vmaf_value = 0
    attempt = 0
    crf_value = 40 #Change this to set the default CRF value for ffmpeg to start converting with
    while True:
        crf_step = 1 #Change this to set the amount the CRF value should change per retry
        if attempt >= max_attempt:
            print('\nMaximum amount of allowed attempts exceeded. Stopping...')
            time.sleep(2)
            break
        attempt += 1
        if not glob.glob(f'{output_dir}{os.path.sep}{os.path.basename(os.path.splitext(file)[0])}.*'): #check if the same filename already exists in the output folder. Extension is ignored to allow custom input container types/extensions
            p1 = subprocess.run(['ffmpeg', '-n', '-i', file, '-c:a', 'aac', '-c:v', 'libsvtav1', '-crf', str(crf_value), '-b:v', '0', '-an', '-g', '600', '-preset', '8', '-movflags', '+faststart', '-pass', '1', '-f', 'null', pass_1_output])
            if p1.returncode == 0: #Skip on error
                p2 = subprocess.run(['ffmpeg', '-n', '-i', file, '-c:a', 'aac', '-c:v', 'libsvtav1', '-crf', str(crf_value), '-b:v', '0', '-b:a', '192k', '-g', '600', '-preset', '8', '-movflags', '+faststart', '-pass', '2', f'{output_dir}{os.path.sep}{os.path.basename(file)}'])
                if p2.returncode == 0: #Skip on error
                    subprocess.run(['ffmpeg', '-i', f'{output_dir}{os.path.sep}{os.path.basename(file)}', '-i', file, '-lavfi', f'libvmaf=log_path=log.json:log_fmt=json:n_threads={logical_cores}', '-f', 'null', '-'])
                    with open('log.json') as f: #Open the json file.
                        vmaf_value = float(json.loads(f.read())['pooled_metrics']['vmaf']['mean']) #Parse amd get the 'mean' vmaf value

                    if not VMAF_min_value <= vmaf_value <= VMAF_max_value: #If VMAF value is not inside the VMAF range
                        if vmaf_value < VMAF_min_value: #If VMAF value is below the minimum range
                            for _ in range(int((VMAF_min_value - vmaf_value) / VMAF_offset_threshold)): #add 1 to crf_step, for each +2 the VMAF value is under the VMAF minimum e.g. a VMAF value of 86, and a VMAF minimum of 90, would temporarily add 2 to the crf_step
                                crf_step += 1
                            print(f'\nVMAF value too low, retrying with a CRF decrease of {crf_step} ({crf_value - crf_step})...')
                            time.sleep(2)
                            crf_value -= crf_step
                            os.remove(f'{output_dir}{os.path.sep}{os.path.basename(file)}') #Delete converted file to avoid FFmpeg skipping it
                        elif vmaf_value > VMAF_max_value: #If VMAF value is above the maximum range
                            for _ in range(int((vmaf_value - VMAF_max_value) / VMAF_offset_threshold)): #add 1 to crf_step, for each +2 the VMAF value is above the VMAF maximum e.g. a VMAF value of 99, and a VMAF maximum of 95, would temporarily add 2 to the crf_step
                                crf_step += 1
                            print(f'\nVMAF value too high, retrying with a CRF increase of {crf_step} ({crf_value + crf_step})...')
                            time.sleep(2)
                            crf_value += crf_step
                            os.remove(f'{output_dir}{os.path.sep}{os.path.basename(file)}') #Delete converted file to avoid FFmpeg skipping it
                        continue
                    else:
                        print('\nVMAF score within acceptable range, continuing...')
                        time.sleep(2)
                        break
                else:
                    break
            else:
                break
        else:
            break
try:        
    os.remove('log.xml')
except:
    pass
try:
    os.remove('ffmpeg2pass-0.log')
except:
    pass
input('\nDone!\n\nPress enter to exit')