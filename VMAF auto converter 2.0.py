import glob
import json
import os
import subprocess
import time
import signal
import math
import shutil

class main:
    def signal_handler(sig, frame):
        print('Cleaning up...')
        main.cleanup()
        exit()

    signal.signal(signal.SIGINT, signal_handler)

    def __init__(self):
        #Input & output parameters:
        self.input_dir = '.' # Change this to set a custom input directory. Dot can be used to specify same directory as the script
        self.output_dir = 'AV1' # Change this to set a custom input directory. Dot can be used to specify same directory as the script
        # Changing both to a dot is not adviced since the original filename is reused in the output, meaning if they share the same extension, ffmpeg will either outright fail, or the script can delete the input file
        self.input_extension = 'mp4' # Change this to set the container type that should be converted. A * (wildcard) can instead be used to ignore container type, but make sure there's only video files in the given directory then 
        self.output_extension = 'mp4' # Can be changed to another extension, but only recommended if the encoder codec has been changed to another one

        #Scene split parameters:
        self.scene_splits = 5
        self.use_scene_splits = True

        #Encoding parameters:
        self.AV1_preset = 6 # Preset level for AV1 encoder, supporting levels 1-8. Lower means smaller size + same or higher quality, but also goes exponentially slower, the lower the number is. 6 is a good ratio between size/quality and time
        self.max_attempts = 10 # Change this to set the max amount of allowed retries before quitting
        self.use_multipass_encoding = False # Change to True if ffmpeg should use multi-pass encoding. CRF mode in SVT-AV1 barely benefits from it, while doubling the encoding time
        self.initial_crf_value = 44 # Change this to set the default CRF value for ffmpeg to start converting with

        #VMAF parameters:
        self.VMAF_min_value = 90 # Change this to determine the minimum allowed VMAF quality
        self.VMAF_max_value = 93 # Change this to determine the maximum allowed VMAF quality
        self.VMAF_offset_threshold = 2 # Change this to determine how much the VMAF value can deviate from the minimum and maximum values, before it starts to exponentially inecrease the CRF value (crf_step is increased by 1 for every time the value is VMAF_offset_threshold off from the minimum or maxumum VMAF value)
                            #^
                            # Decimal numbers are not supported
        self.VMAF_offset_multiplication = 1.3 # Change this to determine how much it should multiply the CRF, based on the difference between the VMAF_min or max value, and the vmaf_value. 2 and above is considered too aggressive, and will overshoot way too much
        self.VMAF_offset_mode = 0 # Change this to set the VMAF mode used to calculate exponential increase/decrease. 0 for threshold based increase, any other number for multiplication based increase
        # 0 (threshold based) is less aggressive, and will use more attempts as it's exponential increase is limited, but can also be slightly more accurate. Very good for low deviations
        # Secondary option (multiplication based) is way more aggressive, but also more flexible, resulting in less attempts, but can also over- and undershoot the target, and may be less accurate. Very good for high deviations
        # If the VMAF offset is 5 or more, it will automatically switch to a multiplication based exponential increase regardless of user settings
        self.initial_crf_step = 1 # Change this to set the amount the CRF value should change per retry. Is overwritten if VMAF_offset_mode is NOT 0

        self.physical_cores = int(os.cpu_count() / 2) # get the amount of physical cores available on system.
    
        if os.name == 'nt': # Visual Studio Code will complain about either one being unreachable, since os.name is a variable. Just ignore this
            self.pass_1_output = 'NUL'
        else:
            self.pass_1_output = '/dev/null'

        self.initial_attempt = 0 # Reset the attempts for each new file
    
    def main(self):
        try:
            os.mkdir(self.output_dir)
        except FileExistsError:
            pass

        for self.file in glob.glob(f'{self.input_dir}{os.path.sep}*.{self.input_extension}'):
            self.filename, self.extension = os.path.splitext(self.file)
            self.vmaf_value = 0 # Reset the VMAF value for each new file. Technically not needed, but nice to have I guess
            self.crf_value = self.initial_crf_value
            
            self.crf_step = self.initial_crf_step
            if not glob.glob(f'{self.output_dir}{os.path.sep}{os.path.basename(self.filename)}.*'): #check if the same filename already exists in the output folder. Extension is ignored to allow custom input container types/extensions
                
                if self.use_scene_splits:
                    self.scene_split()
                else:
                    self.no_scene_split()
                continue

            else:
                continue
        
        self.cleanup()
        input('\nDone!\n\nPress enter to exit')
        exit()

    def scene_split(self):
        stream = subprocess.Popen(['ffprobe', '-v', 'quiet', '-show_streams', '-select_streams', 'v:0', '-of', 'json', self.file], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = stream.communicate()
        video_metadata = json.loads(stdout)['streams'][0]
        total_frames = int(video_metadata['nb_frames'])

        try:
            os.mkdir('VMAF auto converter temp')
        except FileExistsError:
            main.tempcleanup()
        
        self.start_frame = 0
        for self.i in range(self.scene_splits):
            self.crf_value = self.initial_crf_value
            self.attempt = self.initial_attempt
            self.end_frame = math.floor((total_frames / self.scene_splits) * (self.i + 1))
            
            while True:
                if self.attempt >= self.max_attempts:
                    print('\nMaximum amount of allowed attempts exceeded. skipping...')
                    time.sleep(2)
                    return
                self.attempt += 1
                
                print(f'Cutting from frame {self.start_frame} to frame {self.end_frame}')
                
                if self.use_multipass_encoding:
                    multipass_p1 = subprocess.run(['ffmpeg', '-n', '-ss', str(self.start_frame / 60), '-to', str(self.end_frame / 60), '-i', self.file, '-c:v', 'libsvtav1', '-crf', str(self.crf_value), '-b:v', '0', '-an', '-g', '600', '-preset', str(self.AV1_preset), '-movflags', '+faststart', '1', '-f', 'null', self.pass_1_output])
                    if multipass_p1.returncode == 0:
                        multipass_p2 = subprocess.run(['ffmpeg', '-n', '-ss', str(self.start_frame / 60), '-to', str(self.end_frame / 60), '-i', self.file, '-c:a', 'aac', '-c:v', 'libsvtav1', '-crf', str(self.crf_value), '-b:v', '0', '-b:a', '192k', '-g', '600', '-preset', str(self.AV1_preset), '-movflags', '+faststart', '-pass', '2', f'VMAF auto converter temp{os.path.sep}scene{self.i + 1}.{self.output_extension}'])
                        if multipass_p2.returncode != 0:
                            break
                    else:
                        break
                else:
                    p1 = subprocess.run(['ffmpeg', '-n', '-ss', str(self.start_frame / 60), '-to', str(self.end_frame / 60), '-i', self.file, '-c:a', 'aac', '-c:v', 'libsvtav1', '-crf', str(self.crf_value), '-b:v', '0', '-b:a', '192k', '-g', '600', '-preset', str(self.AV1_preset), '-movflags', '+faststart', f'VMAF auto converter temp{os.path.sep}scene{self.i + 1}.{self.output_extension}'])
                    if p1.returncode != 0:
                        break

                if self.checkVMAF(f'VMAF auto converter temp{os.path.sep}scene{self.i + 1}.{self.output_extension}'):
                    if not self.i + 1 >= 5:
                        self.start_frame = self.end_frame + 1
                        break
                    else:
                        concat_file = open(f'VMAF auto converter temp{os.path.sep}concatlist.txt', 'a')
                        files = glob.glob(f'VMAF auto converter temp{os.path.sep}scene*.{self.output_extension}')
                        for file in files:
                            concat_file.write(f"file '{file}'\n")

                        concat_file.close()

                        p2 = subprocess.run(['ffmpeg', '-safe', '0', '-f', 'concat', '-i', 'concatlist.txt', '-c:v', 'copy', '-c:a', 'aac',f'{self.output_dir}{os.path.sep}{os.path.basename(self.filename)}.{self.output_extension}'])
                        if p2.returncode == 0:
                            print('Scenes successfully concatenated! Video should be complete')
                            time.sleep(3)
                            return
                else:
                    continue


    def no_scene_split(self):
        pass

    def checkVMAF(self, output_filename):
        if self.use_scene_splits:
            subprocess.run(['ffmpeg', '-i', output_filename, '-i', self.file, '-lavfi', f'[0:v]trim=start=0[distorted];[1:v]trim=start_frame={self.start_frame}:end_frame={self.end_frame},setpts=PTS-STARTPTS[reference];[distorted][reference]libvmaf=log_path=log.json:log_fmt=json:n_threads={self.physical_cores}', '-f', 'null', '-'])
        else:
            subprocess.run(['ffmpeg', '-i', output_filename, '-i', self.file, '-lavfi', f'libvmaf=log_path=log.json:log_fmt=json:n_threads={self.physical_cores}', '-f', 'null', '-'])
        with open('log.json') as f: # Open the json file.
            self.vmaf_value = float(json.loads(f.read())['pooled_metrics']['vmaf']['mean']) # Parse amd get the 'mean' vmaf value

        if not self.VMAF_min_value <= self.vmaf_value <= self.VMAF_max_value: # If VMAF value is not inside the VMAF range
            if self.vmaf_value < self.VMAF_min_value: # If VMAF value is below the minimum range
                if self.VMAF_offset_mode == 0 and not (self.VMAF_min_value - self.vmaf_value) >= 5: # If VMAF offset mode is set to 0 (threshold based) and NOT off by 5 compared to the VMAF min value
                    print('\nUsing threshold based increase')
                    for _ in range(int((self.VMAF_min_value - self.vmaf_value) / self.VMAF_offset_threshold)): # add 1 to crf_step, for each +2 the VMAF value is under the VMAF minimum e.g. a VMAF value of 86, and a VMAF minimum of 90, would temporarily add 2 to the crf_step
                        self.crf_step += 1
                else:
                    print('\nUsing multiplicative based increase')
                    self.crf_step += int((self.VMAF_min_value - self.vmaf_value) * self.VMAF_offset_multiplication)

                print(f'VMAF value too low, retrying with a CRF decrease of {self.crf_step}. New CRF: ({self.crf_value - self.crf_step})...')
                time.sleep(2)
                self.crf_value -= self.crf_step
                os.remove(output_filename) # Delete converted file to avoid FFmpeg skipping it

            elif self.vmaf_value > self.VMAF_max_value: # If VMAF value is above the maximum range
                if self.VMAF_offset_mode == 0 and not (self.vmaf_value - self.VMAF_max_value) >= 5: # If VMAF offset mode is set to 0 (threshold based) and NOT off by 5 compared to the VMAF max value
                    print('\nUsing threshold based increase')
                    for _ in range(int((self.vmaf_value - self.VMAF_max_value) / self.VMAF_offset_threshold)): # add 1 to crf_step, for each +2 the VMAF value is above the VMAF maximum e.g. a VMAF value of 99, and a VMAF maximum of 95, would temporarily add 2 to the crf_step
                        self.crf_step += 1
                else:
                    print('\nUsing multiplicative based increase')
                    self.crf_step += int((self.vmaf_value - self.VMAF_max_value) * self.VMAF_offset_multiplication)

                print(f'VMAF value too high, retrying with a CRF increase of {self.crf_step}. New CRF: ({self.crf_value + self.crf_step})...')
                time.sleep(2)
                self.crf_value += self.crf_step
                os.remove(output_filename) # Delete converted file to avoid FFmpeg skipping it
                
            return False
        else:
            if self.use_scene_splits:
                print(f'\nScene {self.i + 1} out of {self.scene_splits}\nTook {self.attempt} attempt(s)!')
            else:
                print(f'\nVMAF score within acceptable range, continuing...\nTook {self.attempt} attempt(s)!')
            time.sleep(3)
            return True

    def cleanup():
        try:        
            os.remove('log.json')
        except:
            pass
        try:
            os.remove('ffmpeg2pass-0.log')
        except:
            pass

        main.tempcleanup()

    def tempcleanup():
        try:
            shutil.rmtree('VMAF auto converter temp')
        except:
            print('Error cleaning up temp directory')

if __name__ == '__main__':
    mainClass = main()
    mainClass.main()