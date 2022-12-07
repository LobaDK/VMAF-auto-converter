import glob
import json
import os
import subprocess
import time
import signal
import math
import shutil
import tempfile

class main:
    def signal_handler(sig, frame):
        main.cleanup()
        exit()

    signal.signal(signal.SIGINT, signal_handler)

    def __init__(self):
        #Input & output parameters:
        self.input_dir = 'lossless' # Change this to set a custom input directory. Dot can be used to specify same directory as the script
        self.output_dir = 'AV1' # Change this to set a custom input directory. Dot can be used to specify same directory as the script
        # Changing both to a dot is not adviced since the original filename is reused in the output, meaning if they share the same extension, ffmpeg will either outright fail, or the script can delete the input file
        self.input_extension = 'mp4' # Change this to set the container type that should be converted. A * (wildcard) can instead be used to ignore container type, but make sure there's only video files in the given directory then 
        self.output_extension = 'mp4' # Can be changed to another extension, but only recommended if the encoder codec has been changed to another one
        self.use_intro = False
        self.use_outro = False
        self.intro_file = r''
        self.outro_file = r''

        #Scene split parameters:
        self.scene_splits = 5 # Change this to determine how many times the input video should be split, divided in equal chunks
        self.use_scene_splits = True # Whether or not the video should be split into chunks

        #Encoding parameters:
        self.AV1_preset = 6 # Preset level for AV1 encoder, supporting levels 1-8. Lower means smaller size + same or higher quality, but also goes exponentially slower, the lower the number is. 6 is a good ratio between size/quality and time
        self.max_attempts = 10 # Change this to set the max amount of allowed retries before continuing to the next file/chunk
        self.use_multipass_encoding = False # Change to True if ffmpeg should use multi-pass encoding. CRF mode in SVT-AV1 barely benefits from it, while doubling the encoding time
        self.initial_crf_value = 44 # Change this to set the default CRF value for ffmpeg to start converting with
        self.audio_bitrate = '192k'
        self.detect_audio_bitrate = False

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
        
            if not glob.glob(f'{self.output_dir}{os.path.sep}{os.path.basename(self.filename)}.*'): #check if the same filename already exists in the output folder. Extension is ignored to allow custom input container types/extensions
                if self.use_scene_splits:
                    self.scene_split()
                else:
                    self.no_scene_split()
                
                if self.use_intro or self.use_outro:
                    self.IntroOutro()
                
                continue

            else:
                continue
        
        main.cleanup()
        input('\nDone!\n\nPress enter to exit')
        exit()

    def scene_split(self):

        self.GetVideoMetadata(self.file)
        self.GetAudioMetadata(self.file)

        while True:
            try:
                os.mkdir('VMAF auto converter temp')
            except FileExistsError:
                main.tempcleanup()
            else:
                break
        
        if self.detected_audio_stream:
            audio_extract = subprocess.run(['ffmpeg', '-y', '-i', self.file, '-vn', '-c:a', 'copy', f'VMAF auto converter temp{os.path.sep}audio.{self.audio_codec_name}'])
            if audio_extract.returncode != 0:
                print('Error extracting audio track!')
                exit(1)
            
        self.start_frame = 0
        for self.i in range(self.scene_splits):
            self.crf_value = self.initial_crf_value
            self.attempt = self.initial_attempt
            self.end_frame = math.floor((self.total_frames / self.scene_splits) * (self.i + 1))
            
            while True:
                self.crf_step = self.initial_crf_step
                
                print(f'Cutting from frame {self.start_frame} to frame {self.end_frame}')
                
                if self.use_multipass_encoding:
                    multipass_p1 = subprocess.run(['ffmpeg', '-n', '-ss', str(self.start_frame / int(self.fps)), '-to', str(self.end_frame / int(self.fps)), '-i', self.file, '-c:v', 'libsvtav1', '-crf', str(self.crf_value), '-b:v', '0', '-an', '-g', '600', '-preset', str(self.AV1_preset), '-pass', '1', '-f', 'null', self.pass_1_output])
                    if multipass_p1.returncode == 0:
                        multipass_p2 = subprocess.run(['ffmpeg', '-n', '-ss', str(self.start_frame / int(self.fps)), '-to', str(self.end_frame / int(self.fps)), '-i', self.file, '-c:v', 'libsvtav1', '-crf', str(self.crf_value), '-b:v', '0', '-an', '-g', '600', '-preset', str(self.AV1_preset), '-pass', '2', f'VMAF auto converter temp{os.path.sep}scene{self.i + 1}.{self.output_extension}'])
                        if multipass_p2.returncode != 0:
                            break
                    else:
                        break
                else:
                    p1 = subprocess.run(['ffmpeg', '-n', '-ss', str(self.start_frame / int(self.fps)), '-to', str(self.end_frame / int(self.fps)), '-i', self.file, '-c:v', 'libsvtav1', '-crf', str(self.crf_value), '-b:v', '0', '-an', '-g', '600', '-preset', str(self.AV1_preset), f'VMAF auto converter temp{os.path.sep}scene{self.i + 1}.{self.output_extension}'])
                    if p1.returncode != 0:
                        print('Error converting video!')
                        break

                if self.attempt >= self.max_attempts:
                    print('\nMaximum amount of allowed attempts exceeded. skipping...')
                    time.sleep(2)
                    return
                self.attempt += 1

                if self.checkVMAF(f'VMAF auto converter temp{os.path.sep}scene{self.i + 1}.{self.output_extension}'):
                    if not self.i + 1 >= 5:
                        self.start_frame = self.end_frame + 1
                        break
                    else:
                        concat_file = open(f'VMAF auto converter temp{os.path.sep}concatlist.txt', 'a')
                        files = glob.glob(f'VMAF auto converter temp{os.path.sep}scene*.{self.output_extension}')
                        for file in files:
                            concat_file.write(f"file '{os.path.basename(file)}'\n")

                        concat_file.close()

                        if self.detected_audio_stream:
                            arg = ['ffmpeg', '-safe', '0', '-f', 'concat', '-i', f'VMAF auto converter temp{os.path.sep}concatlist.txt', '-i', f'VMAF auto converter temp{os.path.sep}audio.{self.audio_codec_name}', '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-c:a', 'aac', '-b:a', self.audio_bitrate, '-movflags', '+faststart', f'{self.output_dir}{os.path.sep}{os.path.basename(self.filename)}.{self.output_extension}']
                        else:
                            arg = ['ffmpeg', '-safe', '0', '-f', 'concat', '-i', f'VMAF auto converter temp{os.path.sep}concatlist.txt', '-i', f'VMAF auto converter temp{os.path.sep}audio.{self.audio_codec_name}', '-c:v', 'copy', '-an', '-movflags', '+faststart', f'{self.output_dir}{os.path.sep}{os.path.basename(self.filename)}.{self.output_extension}']
                        
                        p2 = subprocess.run(arg)

                        if p2.returncode == 0:
                            print('Scenes successfully concatenated!')
                            time.sleep(3)
                            return
                        else:
                            print('Error concatenating video. Please check output and video.')
                            input('\nPress enter to continue')
                            return
                else:
                    continue


    def no_scene_split(self):
        self.attempt = self.initial_attempt
        self.GetAudioMetadata(self.file)

        while True:

            self.crf_step = self.initial_crf_step
            if self.use_multipass_encoding:
                multipass_p1 = subprocess.run(['ffmpeg', '-n', '-i', self.file, '-c:a', 'aac', '-c:v', 'libsvtav1', '-crf', str(self.crf_value), '-b:v', '0', '-an', '-g', '600', '-preset', str(self.AV1_preset), '-movflags', '+faststart', '-pass', '1', '-f', 'null', self.pass_1_output])
                if multipass_p1.returncode == 0: # Skip on error
                    multipass_p2 = subprocess.run(['ffmpeg', '-n', '-i', self.file, '-c:a', 'aac', '-c:v', 'libsvtav1', '-crf', str(self.crf_value), '-b:v', '0', '-b:a', self.audio_bitrate, '-g', '600', '-preset', str(self.AV1_preset), '-movflags', '+faststart', '-pass', '2', f'{self.output_dir}{os.path.sep}{os.path.basename(self.filename)}.{self.output_extension}'])
                    if multipass_p2.returncode != 0: # Skip on error
                        print('Error converting pass-2 video!')
                        break
                else:
                    print('Error converting pass-1 video!')
                    break
            else:
                p1 = subprocess.run(['ffmpeg', '-n', '-i', self.file, '-c:a', 'aac', '-c:v', 'libsvtav1', '-crf', str(self.crf_value), '-b:v', '0', '-b:a', self.audio_bitrate, '-g', '600', '-preset', str(self.AV1_preset), '-movflags', '+faststart', f'{self.output_dir}{os.path.sep}{os.path.basename(self.filename)}.{self.output_extension}'])
                if p1.returncode != 0: # Skip on error
                    print('Error converting video!')
                    break
            
            if self.attempt >= self.max_attempts:
                print('\nMaximum amount of allowed attempts exceeded. skipping...')
                time.sleep(2)
                return
            self.attempt += 1

            if self.checkVMAF(f'{self.output_dir}{os.path.sep}{os.path.basename(self.filename)}.{self.output_extension}'):
                break
            else:
                continue

    def checkVMAF(self, output_filename : str):
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
                    self.crf_step += int((self.VMAF_min_value - self.vmaf_value) * self.VMAF_offset_multiplication) # increase the crf_step by multiplying the VMAF_offset_multiplication with how much the VMAF is offset from the minimum allowed value

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
                    self.crf_step += int((self.vmaf_value - self.VMAF_max_value) * self.VMAF_offset_multiplication) # increase the crf_step by multiplying the VMAF_offset_multiplication with how much the VMAF is offset from the maximum allowed value

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

    def GetVideoMetadata(self, output_filename):
        try:
            video_stream = subprocess.Popen(['ffprobe', '-v', 'quiet', '-show_streams', '-select_streams', 'v:0', '-of', 'json', output_filename], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = video_stream.communicate()
            self.video_metadata = json.loads(stdout)['streams'][0]
        except IndexError:
            print('No video stream detected!')
            exit(1)
        else:
            self.total_frames = int(self.video_metadata['nb_frames'])
            self.video_codec_name = self.video_metadata['codec_name']
        
        self.fps = '0'
        try:
            self.fps = self.video_metadata['avg_frame_rate'].split('/', 1)[0]
        except:
            print('Error getting video frame rate.')
            while not self.fps.isnumeric() or self.fps == '0':
                self.fps = input('Manual input required: ')

    def GetAudioMetadata(self, output_filename):
        try:
            audio_stream = subprocess.Popen(['ffprobe', '-v', 'quiet', '-show_streams', '-select_streams', 'a:0', '-of', 'json', output_filename], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = audio_stream.communicate()
            self.audio_metadata = json.loads(stdout)['streams'][0]
        except IndexError:
            self.detected_audio_stream = False
            print('No audio stream detected.')
        else:
            self.detected_audio_stream = True
            self.audio_codec_name = self.audio_metadata['codec_name']
       
        if self.detect_audio_bitrate:
                self.audio_bitrate = str(self.audio_metadata['bit_rate'])

    def IntroOutro(self):
        
        if self.use_intro:
            self.GetVideoMetadata(self.intro_file)
            self.GetAudioMetadata(self.intro_file)

            if self.detected_audio_stream:
                arg = (['ffmpeg', '-y', '-i', self.intro_file, '-c:v', 'libsvtav1', '-c:a', 'aac', '-crf', '30', '-b:v', '0', '-b:a', self.audio_bitrate, '-g', '600', '-preset', '8', f'{os.path.join(tempfile.gettempdir(), "VMAF intro.mp4")}'])
            else:
                arg = (['ffmpeg', '-y', '-i', self.intro_file, '-c:v', 'libsvtav1', '-crf', '30', '-b:v', '0', '-an', '-g', '600', '-preset', '8', f'{os.path.join(tempfile.gettempdir(), "VMAF intro.mp4")}'])
        if self.use_outro:
            self.GetVideoMetadata(self.outro_file)
            self.GetAudioMetadata(self.outro_file)

            if self.detected_audio_stream:
                arg = (['ffmpeg', '-y', '-i', self.outro_file, '-c:v', 'libsvtav1', '-c:a', 'aac', '-crf', '30', '-b:v', '0', '-b:a', self.audio_bitrate, '-g', '600', '-preset', '8', f'{os.path.join(tempfile.gettempdir(), "VMAF outro.mp4")}'])
            else:
                arg = (['ffmpeg', '-y', '-i', self.outro_file, '-c:v', 'libsvtav1', '-crf', '30', '-b:v', '0', '-an', '-g', '600', '-preset', '8', f'{os.path.join(tempfile.gettempdir(), "VMAF outro.mp4")}'])

        p = subprocess.run(arg)
        if p.returncode != 0:
            print(' '.join(arg))
            print('Error converting intro or outro file to suitable format!')
            exit(1)

        
        if self.use_intro and not self.use_outro:
            IntroOutro = open('IntroOutroList.txt', 'w')
            IntroOutro.write(f"file '{os.path.join(tempfile.gettempdir(), 'VMAF intro.mp4')}'\n")
            IntroOutro.write(f"file '{self.output_dir}{os.path.sep}{os.path.basename(self.filename)}.{self.output_extension}'")
        if self.use_outro and not self.use_intro:
            IntroOutro = open('IntroOutroList.txt', 'w')
            IntroOutro.write(f"file '{self.output_dir}{os.path.sep}{os.path.basename(self.filename)}.{self.output_extension}'\n")
            IntroOutro.write(f"file '{os.path.join(tempfile.gettempdir(), 'VMAF outro.mp4')}'")
        else:
            IntroOutro = open('IntroOutroList.txt', 'w')
            IntroOutro.write(f"file '{os.path.join(tempfile.gettempdir(), 'VMAF intro.mp4')}'\n")
            IntroOutro.write(f"file '{self.output_dir}{os.path.sep}{os.path.basename(self.filename)}.{self.output_extension}'\n")
            IntroOutro.write(f"file '{os.path.join(tempfile.gettempdir(), 'VMAF outro.mp4')}'")
        IntroOutro.close()

        self.GetAudioMetadata(f'{self.output_dir}{os.path.sep}{os.path.basename(self.filename)}.{self.output_extension}')
        if self.detected_audio_stream:
            arg = ['ffmpeg', '-safe', '0', '-f', 'concat', '-i', 'IntroOutroList.txt', '-map', '0', '-c', 'copy', '-movflags', '+faststart', f'{self.output_dir}{os.path.sep}{os.path.basename(self.filename)} with intro or outro.{self.output_extension}']
        else:
            arg = ['ffmpeg', '-safe', '0', '-f', 'concat', '-i', 'IntroOutroList.txt', '-map', '0', '-c:v', 'copy', '-an', '-movflags', '+faststart', f'{self.output_dir}{os.path.sep}{os.path.basename(self.filename)} with intro or outro.{self.output_extension}']        


        p = subprocess.run(arg)
        if p.returncode != 0:
            print(' '.join(arg))
            print('Error applying intro or outro to file!')
            exit(1)
        
    def cleanup():
        print('Cleaning up...')
        tempfile_list = ['IntroOutroList.txt', 'log.json', 'ffmpeg2pass-0.log', f'{os.path.join(tempfile.gettempdir(), "VMAF outro.mp4")}']
        for tempfile in tempfile_list:
            try:        
                os.remove(tempfile)
            except:
                pass

        if os.path.exists('VMAF auto converter temp'):
            main.tempcleanup()

    def tempcleanup():
        try:
            shutil.rmtree('VMAF auto converter temp')
        except:
            print('Error cleaning up temp directory')

if __name__ == '__main__':
    mainClass = main()
    mainClass.main()