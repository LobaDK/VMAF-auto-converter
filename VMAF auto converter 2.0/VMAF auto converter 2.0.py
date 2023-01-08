import glob
import json
import os
import subprocess
import time
import signal
import math
import shutil
import tempfile
import tqdm
import argparse

class main:
    def signal_handler(sig, frame):
        main.cleanup()
        exit()

    signal.signal(signal.SIGINT, signal_handler)

    def IntOrFloat(self, s: str):
        if s.isnumeric():
            value = int(s)
        else:
            try:
                value = float(s)
            except:
                raise argparse.ArgumentTypeError(f'{s} is not a valid number or decimal')
        return value

    def __init__(self):
        parser = argparse.ArgumentParser(description='AV1 converter script using VMAF to control the quality', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
        
        #Input & output parameters:
        input_dir = 'lossless' # Change this to set a custom input directory. Dot can be used to specify same directory as the script
        output_dir = 'AV1' # Change this to set a custom output directory. Dot can be used to specify same directory as the script
        # Changing both to the same directory is not adviced since the original filename is reused in the output, meaning if they share the same extension, ffmpeg will either outright fail, or the script can delete the input file
        input_extension = 'mp4' # Change this to set the container type that should be converted. A * (wildcard) can instead be used to ignore container type, but make sure there's only video files in the given directory then 
        output_extension = 'mp4' # Can be changed to another extension, but only recommended if the encoder codec has been changed to another one
        use_intro = False
        use_outro = False
        intro_file = r''
        outro_file = r''

        #File chunking parameters:
        file_chunks = 5 # Change this to determine how many times the input video should be split, divided in equal chunks. file_chunking_mode = 1
        chunk_frequency = 10 # Change this to determine how long the video chunks should be in seconds. file_chunking_mode = 2
        file_chunking_mode = 2 # 0 = Disabled, 1 = Split file into N file_chunks amount, 2 = Split file into N chunk_frequency second long chunks

        #Encoding parameters:
        AV1_preset = 6 # Preset level for AV1 encoder, supporting levels 1-8. Lower means smaller size + same or higher quality, but also goes exponentially slower, the lower the number is. 6 is a good ratio between size/quality and time
        max_attempts = 10 # Change this to set the max amount of allowed retries before continuing to the next file/chunk
        initial_crf_value = 44 # Change this to set the default CRF value for ffmpeg to start converting with
        audio_bitrate = '192k'
        detect_audio_bitrate = False
        pixel_format = 'yuv420p10le' # Pixel format for the output. yuv420p for 8-bit, yuv420p10le for 10-bit. 10-bit can slightly boost quality, especially with minimizing color banding, but can increase encoder and decoder complexity
        tune_mode = 1 # Tune mode for the encoder. 0 = VQ (subjective measuring), 1 = PSNR (objective measuring). Subjective measuring can produce sharper frames and results that appear higher quality to human vision
        GOP_size = 300 # Group Of Pictures, or keyframe size. i.e. every N GOP_size, add a keyframe. if fps is 60 and GOP_size is 300, a keyframe will be added every 5 seconds

        #VMAF parameters:
        VMAF_min_value = 90.5 # Change this to determine the minimum allowed VMAF quality
        VMAF_max_value = 93 # Change this to determine the maximum allowed VMAF quality
        VMAF_offset_threshold = 2 # Change this to determine how much the VMAF value can deviate from the minimum and maximum values, before it starts to exponentially inecrease the CRF value (crf_step is increased by 1 for every time the value is VMAF_offset_threshold off from the minimum or maxumum VMAF value)
                                    #^
                                    # Decimal numbers are not supported
        VMAF_offset_multiplication = 1.3 # Change this to determine how much it should multiply the CRF, based on the difference between the VMAF_min or max value, and the vmaf_value. 2 and above is considered too aggressive, and will overshoot way too much
        VMAF_offset_mode = 1 # Change this to set the VMAF mode used to calculate exponential increase/decrease. 0 for threshold based increase, 1 for multiplication based increase
        # 0 (threshold based) is less aggressive, and will use more attempts as it's exponential increase is limited, but can also be slightly more accurate. Very good for low deviations
        # 1 (multiplication based) is way more aggressive, but also more flexible, resulting in less attempts, but can also over- and undershoot the target, and may be less accurate. Very good for high deviations
        # If the VMAF offset is 5 or more, it will automatically switch to a multiplication based exponential increase regardless of user settings
        initial_crf_step = 1 # Change this to set the amount the CRF value should change per retry. Is overwritten if VMAF_offset_mode is NOT 0

        #Verbosity parameters:
        ffmpeg_verbose_level = 1 # 0 = Display none of ffmpeg's output, 1 = Display only ffmpeg stats, 2 = Display ffmpeg stats and encoder-specific information


        self.tempdir = os.path.join(tempfile.gettempdir(), 'VMAF auto converter')

        parser.add_argument('-v', '--verbosity', metavar='0-2', dest='ffmpeg_verbose_level', default=ffmpeg_verbose_level, help='0 = hide, 1 = basic, 2 = full', type=int)
        parser.add_argument('-i', '--input', metavar='path', dest='input_dir', default=input_dir, help='Absolute or relative path to the files', type=str)
        parser.add_argument('-o', '--output', metavar='path', dest='output_dir',  default=output_dir, help='Absolute or relative path to where the file should be written', type=str)
        parser.add_argument('-iext', '--input-extension', metavar='ext', dest='input_extension', default=input_extension, help='Container extension to convert from. Use * to specify all', type=str)
        parser.add_argument('-oext', '--output-extension', metavar='ext', dest='output_extension', default=output_extension, help='Container extension to convert to', type=str)
        parser.add_argument('-ui', '--use-intro', metavar='0-1',  dest='use_intro', default=use_intro, help='Add intro', type=int)
        parser.add_argument('-uo', '--use-outro', metavar='0-1', dest='use_outro', default=use_outro, help='Add outro' , type=int)
        parser.add_argument('-if', '--intro-file', metavar='path', dest='intro_file', default=intro_file, help='Absolute or relative path to the intro file, including filename', type=str)
        parser.add_argument('-of', '--outro-file', metavar='path', dest='outro_file', default=outro_file, help='Absolute or relative path to the outro file, including filename', type=str)
        parser.add_argument('-cm', '--chunk-mode', metavar='0-2', dest='file_chunking_mode', default=file_chunking_mode, help='Disable, split N amount of times, or split into N second long chunks', type=int)
        parser.add_argument('-cs', '--chunk-splits', metavar='N splits', dest='file_chunks', default=file_chunks, help='How many chunks the video should be divided into', type=int)
        parser.add_argument('-cd', '--chunk-duration', metavar='N seconds', dest='chunk_frequency', default=chunk_frequency, help='Chunk duration in seconds', type=int)
        parser.add_argument('-pr', '--av1-preset', metavar='0-12', dest='AV1_preset', default=AV1_preset, help='Encoding preset for the AV1 encoder', type=int)
        parser.add_argument('-ma', '--max-attempts', metavar='N', dest='max_attempts', default=max_attempts, help='Max attempts before the script skips (but keeps) the file', type=int)
        parser.add_argument('-crf', metavar='1-63', dest='initial_crf_value', default=initial_crf_value, help='Encoder CRF value to be used', type=int)
        parser.add_argument('-ab', '--audio-bitrate', metavar='bitrate(B/K/M)', dest='audio_bitrate', default=audio_bitrate, help='Encoder audio bitrate. Use B/K/M to specify bits, kilobits, or megabits', type=str)
        parser.add_argument('-dab', '--detect-audio-bitrate', metavar='0-1', dest='detect_audio_bitrate', default=detect_audio_bitrate, help='If the script should detect and instead use the audio bitrate from input file', type=int)
        parser.add_argument('-pxf', '--pixel-format', metavar='pix_fmt', dest='pixel_format', default=pixel_format, help='Encoder pixel format to use. yuv420p for 8-bit, and yuv420p10le for 10-bit', type=str)
        parser.add_argument('-tune', metavar='0-1', dest='tune_mode', default=tune_mode, help='Encoder tune mode. 0 = VQ (subjective), 1 = PSNR (objective)', type=int)
        parser.add_argument('-g', '--keyframe-interval', metavar='N frames', dest='GOP_size', default=GOP_size, help='Encoder keyframe interval in frames', type=int)
        parser.add_argument('-minq', '--minimum-quality', metavar='N', dest='VMAF_min_value', default=VMAF_min_value, help='Minimum allowed quality for the output file/chunk, calculated using VMAF. Allows decimal for precision', type=self.IntOrFloat)
        parser.add_argument('-maxq', '--maximum-quality', metavar='N', dest='VMAF_max_value', default=VMAF_max_value, help='Maximum allowed quality for the output file/chunk, calculated using VMAF. Allows decimal for precision', type=self.IntOrFloat)
        parser.add_argument('-vomode', '--vmaf-offset-mode', metavar='0-1', dest='VMAF_offset_mode', default=VMAF_offset_mode, help='Algorithm to use to exponentially adjust the CRF value. 0 = standard and slow threshold-based, 1 = aggressive but can overshoot multiplier-based', type=int)
        parser.add_argument('-vot', '--vmaf-offset-threshold', metavar='N', dest='VMAF_offset_threshold', default=VMAF_offset_threshold, help='How many whole percent the VMAF should deviate before CRF value will exponentially increase or decrease', type=int)
        parser.add_argument('-vom', '--vmaf-offset-multiplier', metavar='N', dest='VMAF_offset_multiplication', default=VMAF_offset_multiplication, help='How much to multiply the VMAF deviation with, exponentially increasing/decreasing the CRF value. Allows decimal for precision', type=self.IntOrFloat)
        parser.add_argument('--crf-step', metavar='N', dest='initial_crf_step', default=initial_crf_step, help='How much it should adjust the CRF value on each retry', type=int)
        self.args = parser.parse_args()

        self.InitCheck()

        if self.args.ffmpeg_verbose_level == 0:
            self.arg_start = ['ffmpeg', '-n', '-hide_banner', '-v', 'quiet']
        elif self.args.ffmpeg_verbose_level == 1:
            self.arg_start = ['ffmpeg', '-n', '-hide_banner', '-v', 'quiet', '-stats']
        else:
            self.arg_start = ['ffmpeg', '-n']

        self.physical_cores = int(os.cpu_count() / 2) # get the amount of physical cores available on system.
    
        if os.name == 'nt': # Visual Studio Code will complain about either one being unreachable, since os.name is a variable. Just ignore this
            self.pass_1_output = 'NUL'
        else:
            self.pass_1_output = '/dev/null'
    
    def InitCheck(self):
        param_issues = []
        if not isinstance(self.args.input_dir, str):
            param_issues.append('Input_dir is not a string')
        elif not self.args.input_dir:
            param_issues.append('No specified input folder')
        if not isinstance(self.args.output_dir, str):
            param_issues.append('output_dir is not a string, or is not specified')
        elif not self.args.output_dir:
            param_issues.append('No specified output folder')
        if isinstance(self.args.input_dir, str) and isinstance(self.args.output_dir, str) and self.args.input_dir == self.args.output_dir:
            param_issues.append('Input and output folder cannot be the same')

        if not isinstance(self.args.input_extension, str):
            param_issues.append('Input_extension is not a string')
        elif not self.args.input_extension:
            param_issues.append('No specified input extension')
        if not isinstance(self.args.output_extension, str):
            param_issues.append('Output_extension is not a string')
        elif not self.args.output_extension:
            param_issues.append('No specified output extension')

        if not isinstance(self.args.use_intro, bool):
            param_issues.append('Use_intro is not True, False, 0 or 1')
        elif self.args.use_intro and not isinstance(self.args.intro_file, str):
            param_issues.append('Intro enabled but intro_file is not a string')
        elif self.args.use_intro and not self.args.intro_file:
            param_issues.append('Intro enabled but no intro file specified')
        if not isinstance(self.args.use_outro, bool):
            param_issues.append('Use_outro is not True, False, 0 or 1')
        elif self.args.use_outro and not isinstance(self.args.outro_file, str):
            param_issues.append('Outro enabled but outro_file is not a string')
        elif self.args.use_outro and not self.args.outro_file:
            param_issues.append('Outro enabled but no outro file specified')

        if not isinstance(self.args.file_chunks, int):
            param_issues.append('File_chunks is not a whole number')
        if not isinstance(self.args.chunk_frequency, int):
            param_issues.append('Chunk_frequency is not a whole number')
        if not isinstance(self.args.file_chunking_mode, int):
            param_issues.append('File_chunking_mode is not a whole number')
        elif not 0 <= self.args.file_chunking_mode <= 2:
            param_issues.append('File_chunking_mode is out of range (0-2)')
        
        if not isinstance(self.args.AV1_preset, int):
            param_issues.append('AV1 preset is not a whole number')
        elif not 0 <= self.args.AV1_preset <= 12:
            param_issues.append('AV1_preset is out of range (0-12')
        if not isinstance(self.args.max_attempts, int):
            param_issues.append('Max_attempts is not a whole number')
        if not isinstance(self.args.initial_crf_value, int):
            param_issues.append('Initial_crf_value is not a whole number')
        elif not 1 <= self.args.initial_crf_value <= 63:
            param_issues.append('Initial_crf_value is out of range (1-63)')
        if not isinstance(self.args.audio_bitrate, (int, str)):
            param_issues.append('Audio_bitrate is not a string or whole number')
        if not isinstance(self.args.detect_audio_bitrate, bool):
            param_issues.append('Detect_audio_bitrate is not True, False, 0 or 1')
        if not isinstance(self.args.pixel_format, str):
            param_issues.append('Pixel_format is not a string')
        if not isinstance(self.args.tune_mode, int):
            param_issues.append('Tune_mode is not a whole number')
        elif not 0 <= self.args.tune_mode <= 1:
            param_issues.append('Tune_mode is out of range (0-1)')
        if not isinstance(self.args.GOP_size, int):
            param_issues.append('GOP_size is not a whole number')
        
        if not isinstance(self.args.VMAF_min_value, (int, float)):
            param_issues.append('VMAF_min_value is not a whole or decimal number')
        elif not 0 <= self.args.VMAF_min_value <= 100:
            param_issues.append('VMAF_min_value is not in range (0-100)')
        if not isinstance(self.args.VMAF_max_value, (int, float)):
            param_issues.append('VMAF_max_value is not a whole or decimal number')
        elif not 0 <= self.args.VMAF_max_value <= 100:
            param_issues.append('VMAF_max_value is not in range (0-100)')
        if isinstance(self.args.VMAF_min_value, (int, float)) and isinstance(self.args.VMAF_max_value, (int, float)) and self.args.VMAF_min_value > self.args.VMAF_max_value:
            param_issues.append('VMAF_min_value is higher than VMAF_max_value')
        if not isinstance(self.args.VMAF_offset_threshold, int):
            param_issues.append('VMAF_offset_threshold is not a whole number')
        if not isinstance(self.args.VMAF_offset_multiplication, (int, float)):
            param_issues.append('VMAF_offset_multiplication is not a whole or decimal number')
        if not isinstance(self.args.VMAF_offset_mode, int):
            param_issues.append('VMAF_offset_mode is not a whole number')
        elif not 0 <= self.args.VMAF_offset_mode <= 1:
            param_issues.append('VMAF_offset_mode is not in range (0-1)')
        if not isinstance(self.args.initial_crf_step, int):
            param_issues.append('Initial_crf_step is not a whole number')

        if not isinstance(self.args.ffmpeg_verbose_level, int):
            param_issues.append('FFmpeg_verbose_level is not a whole number')
        elif not 0 <= self.args.ffmpeg_verbose_level <= 2:
            param_issues.append('FFmpeg_verbose_level is not in range (0-2)')
        
        if param_issues:
            print('\n'.join(param_issues))
            exit(1)
            
    def main(self):
        try:
            os.mkdir(self.args.output_dir)
        except FileExistsError:
            pass

        for self.file in glob.glob(f'{self.args.input_dir}{os.path.sep}*.{self.args.input_extension}'):
            self.filename, self.extension = os.path.splitext(self.file)
            self.vmaf_value = 0 # Reset the VMAF value for each new file. Technically not needed, but nice to have I guess
            self.crf_value = self.args.initial_crf_value
        
            if not glob.glob(f'{self.args.output_dir}{os.path.sep}{os.path.basename(self.filename)}.*'): #check if the same filename already exists in the output folder. Extension is ignored to allow custom input container types/extensions
                if self.args.file_chunking_mode == 0:
                    self.no_chunk_split()
                elif self.args.file_chunking_mode == 1:
                    self.chunk_split()
                elif self.args.file_chunking_mode == 2:
                    self.chunk_frequency_split()
                
                if self.args.use_intro or self.args.use_outro:
                    self.IntroOutro()
                
                continue

            else:
                continue
        
        main.cleanup()
        input('\nDone!\n\nPress enter to exit')
        exit()

    def chunk_frequency_split(self):
        
        self.GetVideoMetadata(self.file)
        self.GetAudioMetadata(self.file)
        self.total_chunks = math.ceil(self.total_frames / int(self.fps) / self.args.chunk_frequency)

        self.CreateTempFolder()
        
        if self.detected_audio_stream:
            self.ExtractAudio()

        print('\nPreparing chunks...\n')
        self.chunks = []
        self.start_frame = 0
        self.ii = 0
        for self.i in tqdm.tqdm(range(0, int(self.total_frames / int(self.fps)), self.args.chunk_frequency)):
            self.ii += 1
            if not self.i + self.args.chunk_frequency >= int(self.total_frames / int(self.fps)):
                self.end_frame = self.start_frame + (self.args.chunk_frequency * int(self.fps))
            else:
                self.end_frame = (self.total_frames - self.start_frame) + self.start_frame
            
            arg = ['ffmpeg', '-n', '-ss', str(self.start_frame / int(self.fps)), '-to', str(self.end_frame / int(self.fps)), '-i', self.file, '-c:v', 'libx264', '-preset', 'ultrafast', '-qp', '0', '-an', os.path.join(self.tempdir, os.path.join('prepared', f'chunk{self.ii}.{self.args.output_extension}'))]
            p = subprocess.run(arg, stderr=subprocess.DEVNULL)
            
            if p.returncode != 0:
                print(" ".join(arg))
                print(f'\nError preparing chunk {self.ii}')
                exit(1)
            self.start_frame = self.end_frame
            self.chunks.append(os.path.join(self.tempdir, os.path.join('prepared', f'chunk{self.ii}.{self.args.output_extension}')))

        self.start_frame = 0
        self.ii = 0
        for self.i in range(0, int(self.total_frames / int(self.fps)), self.args.chunk_frequency):
            self.ii += 1
            self.crf_value = self.args.initial_crf_value
            self.attempt = 0 #reset attempts after each file

            if not self.i + self.args.chunk_frequency >= int(self.total_frames / int(self.fps)):
                self.end_frame = self.start_frame + (self.args.chunk_frequency * int(self.fps))
            else:
                self.end_frame = (self.total_frames - self.start_frame) + self.start_frame

            while True:
                if self.split():
                    if self.checkVMAF(os.path.join(self.tempdir, os.path.join('converted', f'chunk{self.ii}.{self.args.output_extension}'))):
                        self.start_frame = self.end_frame
                        break
                    else:
                        continue
                else:
                    break
        
        self.concat()

    def chunk_split(self):

        self.GetVideoMetadata(self.file)
        self.GetAudioMetadata(self.file)
        self.total_chunks = self.args.file_chunks

        self.CreateTempFolder()
        
        if self.detected_audio_stream:
            self.ExtractAudio()
        
        print('\nPreparing chunks...\n')
        self.chunks = []
        self.start_frame = 0
        self.ii = 0
        for self.i in tqdm.tqdm(range(self.args.file_chunks)):
            self.ii += 1
            self.crf_value = self.args.initial_crf_value
            self.attempt = 0 #reset attempts after each file
            self.end_frame = math.floor((self.total_frames / self.args.file_chunks) * (self.ii))
            arg = ['ffmpeg', '-n', '-ss', str(self.start_frame / int(self.fps)), '-to', str(self.end_frame / int(self.fps)), '-i', self.file, '-c:v', 'libx264', '-preset', 'ultrafast', '-qp', '0', '-an', os.path.join(self.tempdir, os.path.join('prepared', f'chunk{self.ii}.{self.args.output_extension}'))]
            p = subprocess.run(arg, stderr=subprocess.DEVNULL)
            
            if p.returncode != 0:
                print(" ".join(arg))
                print(f'\nError preparing chunk {self.ii}')
                exit(1)
            self.start_frame = self.end_frame
            self.chunks.append(os.path.join(self.tempdir, os.path.join('prepared', f'chunk{self.ii}.{self.args.output_extension}')))
        
        self.start_frame = 0
        self.ii = 0
        for self.i in range(self.args.file_chunks):
            self.ii += 1
            self.crf_value = self.args.initial_crf_value
            self.attempt = 0 #reset attempts after each file
            self.end_frame = math.floor((self.total_frames / self.args.file_chunks) * (self.ii))
            
            while True:

                if self.split():
                    if self.checkVMAF(os.path.join(self.tempdir, os.path.join('converted', f'chunk{self.ii}.{self.args.output_extension}'))):
                        if not self.ii >= self.args.file_chunks:
                            self.start_frame = self.end_frame
                            break
                        else:
                            self.concat()
                            break
                    else:
                        continue
                else:
                    break

    def no_chunk_split(self):
        self.attempt = 0 #reset attempts after each file
        self.GetAudioMetadata(self.file)

        while True:

            self.crf_step = self.args.initial_crf_step
            arg = ['-i', self.file, '-c:a', 'aac', '-c:v', 'libsvtav1', '-crf', str(self.crf_value), '-b:v', '0', '-b:a', self.args.audio_bitrate, '-g', str(self.args.GOP_size), '-preset', str(self.args.AV1_preset), '-pix_fmt', self.args.pixel_format, '-svtav1-params', f'tune={str(self.args.tune_mode)}', '-movflags', '+faststart', f'{self.args.output_dir}{os.path.sep}{os.path.basename(self.filename)}.{self.args.output_extension}']
            arg[0:0] = self.arg_start
            print('\nPerforming video encode...\n')
            p1 = subprocess.run(arg)
            if p1.returncode != 0: # Skip on error
                print('\nError converting video!')
                break
            print('\nVideo encoding finished!')
            
            if self.attempt >= self.args.max_attempts:
                print('\nMaximum amount of allowed attempts exceeded. skipping...')
                time.sleep(2)   
                return
            self.attempt += 1

            if self.checkVMAF(f'{self.args.output_dir}{os.path.sep}{os.path.basename(self.filename)}.{self.args.output_extension}'):
                break
            else:
                continue

    def checkVMAF(self, output_filename : str):
        print('\ncomparing video quality...\n')
        if self.args.file_chunking_mode != 0:
            arg = ['-i', output_filename, '-i', os.path.join(self.tempdir, os.path.join('prepared', f'chunk{self.ii}.{self.args.output_extension}')), '-lavfi', f'libvmaf=log_path=log.json:log_fmt=json:n_threads={self.physical_cores}', '-f', 'null', '-']
        else:
            arg = ['-i', output_filename, '-i', self.file, '-lavfi', f'libvmaf=log_path=log.json:log_fmt=json:n_threads={self.physical_cores}', '-f', 'null', '-']
        arg[0:0] = self.arg_start
        p = subprocess.run(arg)
        if p.returncode != 0:
            print(" ".join(arg))
            print('\nError comparing quality!')
            exit(1)
        with open('log.json') as f: # Open the json file.
            self.vmaf_value = float(json.loads(f.read())['pooled_metrics']['vmaf']['harmonic_mean']) # Parse amd get the 'mean' vmaf value

        print(f'\nVMAF range: {self.args.VMAF_min_value} - {self.args.VMAF_max_value}')
        if not self.args.VMAF_min_value <= self.vmaf_value <= self.args.VMAF_max_value: # If VMAF value is not inside the VMAF range
            if self.vmaf_value < self.args.VMAF_min_value: # If VMAF value is below the minimum range
                print(f'\nVMAF harmonic mean score of {self.vmaf_value}... VMAF value too low')
                if self.args.VMAF_offset_mode == 0 and not (self.args.VMAF_min_value - self.vmaf_value) >= 5: # If VMAF offset mode is set to 0 (threshold based) and NOT off by 5 compared to the VMAF min value
                    print('\nUsing threshold based increase')
                    for _ in range(int((self.args.VMAF_min_value - self.vmaf_value) / self.args.VMAF_offset_threshold)): # add 1 to crf_step, for each +2 the VMAF value is under the VMAF minimum e.g. a VMAF value of 86, and a VMAF minimum of 90, would temporarily add 2 to the crf_step
                        self.crf_step += 1
                else:
                    print('\nUsing multiplicative based increase')
                    self.crf_step += int((self.args.VMAF_min_value - self.vmaf_value) * self.args.VMAF_offset_multiplication) # increase the crf_step by multiplying the VMAF_offset_multiplication with how much the VMAF is offset from the minimum allowed value

                print(f'Retrying with a CRF decrease of {self.crf_step}. New CRF: ({self.crf_value - self.crf_step})...')
                time.sleep(2)
                self.crf_value -= self.crf_step
                if not 1 <= self.crf_value <= 63:
                    print('CRF value out of range (1-63). Skipping...')
                    return True #Return True instead of False to skip the file and continue with the next one
                os.remove(output_filename) # Delete converted file to avoid FFmpeg skipping it

            elif self.vmaf_value > self.args.VMAF_max_value: # If VMAF value is above the maximum range
                print(f'\nVMAF harmonic mean score of {self.vmaf_value}... VMAF value too high')
                if self.args.VMAF_offset_mode == 0 and not (self.vmaf_value - self.args.VMAF_max_value) >= 5: # If VMAF offset mode is set to 0 (threshold based) and NOT off by 5 compared to the VMAF max value
                    print('\nUsing threshold based increase')
                    for _ in range(int((self.vmaf_value - self.args.VMAF_max_value) / self.args.VMAF_offset_threshold)): # add 1 to crf_step, for each +2 the VMAF value is above the VMAF maximum e.g. a VMAF value of 99, and a VMAF maximum of 95, would temporarily add 2 to the crf_step
                        self.crf_step += 1
                else:
                    print('\nUsing multiplicative based increase')
                    self.crf_step += int((self.vmaf_value - self.args.VMAF_max_value) * self.args.VMAF_offset_multiplication) # increase the crf_step by multiplying the VMAF_offset_multiplication with how much the VMAF is offset from the maximum allowed value

                print(f'Retrying with a CRF increase of {self.crf_step}. New CRF: ({self.crf_value + self.crf_step})...')
                time.sleep(2)
                self.crf_value += self.crf_step
                if not 1 <= self.crf_value <= 63:
                    print('CRF value out of range (1-63). Skipping...')
                    return True #Return True instead of False to skip the file and continue with the next one
                os.remove(output_filename) # Delete converted file to avoid FFmpeg skipping it
                
            return False
        else:
            print(f'\nVMAF harmonic mean score of {self.vmaf_value}...\nVMAF score within acceptable range, continuing...\nTook {self.attempt} attempt(s)!\n')
            if self.args.file_chunking_mode != 0:
                print(f'Completed chunk {self.ii} out of {self.total_chunks}')
            time.sleep(3)
            return True

    def split(self):
        self.crf_step = self.args.initial_crf_step
        
        print(f'\nProcessing chunk {self.ii} out of {self.total_chunks}\n')

        arg = ['-ss', str(self.start_frame / int(self.fps)), '-to', str(self.end_frame / int(self.fps)), '-i', self.file, '-c:v', 'libsvtav1', '-crf', str(self.crf_value), '-b:v', '0', '-an', '-g', str(self.args.GOP_size), '-preset', str(self.args.AV1_preset), '-pix_fmt', self.args.pixel_format, '-svtav1-params', f'tune={str(self.args.tune_mode)}', os.path.join(self.tempdir, os.path.join('converted', f'chunk{self.ii}.{self.args.output_extension}'))]
        arg[0:0] = self.arg_start
        p1 = subprocess.run(arg)
        if p1.returncode != 0:
            print(" ".join(arg))
            print('Error converting video!')
            exit(1)
        print(f'\nFinished processing chunk {self.ii}!')

        if self.attempt >= self.args.max_attempts:
            print('\nMaximum amount of allowed attempts exceeded. skipping...')
            time.sleep(2)
            return False
        self.attempt += 1
        return True

    def concat(self):
        concat_file = open(os.path.join(self.tempdir, 'concatlist.txt'), 'a')
        for i in range(self.ii):
            concat_file.write(f"file '{os.path.join(self.tempdir, os.path.join('converted', f'chunk{i+1}.{self.args.output_extension}'))}'\n")

        concat_file.close()

        if self.detected_audio_stream:
            arg = ['-safe', '0', '-f', 'concat', '-i', os.path.join(self.tempdir, 'concatlist.txt'), '-i', os.path.join(self.tempdir, f'audio.{self.audio_codec_name}'), '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-c:a', 'aac', '-b:a', self.args.audio_bitrate, '-movflags', '+faststart', f'{self.args.output_dir}{os.path.sep}{os.path.basename(self.filename)}.{self.args.output_extension}']
        else:
            arg = ['-safe', '0', '-f', 'concat', '-i', os.path.join(self.tempdir, 'concatlist.txt'), '-c:v', 'copy', '-an', '-movflags', '+faststart', f'{self.args.output_dir}{os.path.sep}{os.path.basename(self.filename)}.{self.args.output_extension}']
        
        arg[0:0] = self.arg_start
        print('\nCombining chunks...\n')
        p2 = subprocess.run(arg)

        if p2.returncode == 0:
            print('\nChunks successfully combined!')
            time.sleep(3)
        else:
            print('Error combining video chunks. Please check output and video.')
            input('\nPress enter to continue')

    def ExtractAudio(self):
        arg = ['-i', self.file, '-vn', '-c:a', 'copy', os.path.join(self.tempdir, f'audio.{self.audio_codec_name}')]
        arg[0:0] = self.arg_start
        print('\nExtracting audio...\n')
        audio_extract = subprocess.run(arg)
        if audio_extract.returncode != 0:
            print(" ".join(arg))
            print('\nError extracting audio track!')
            exit(1)

    def GetVideoMetadata(self, output_filename):
        try:
            arg = ['ffprobe', '-v', 'quiet', '-show_streams', '-select_streams', 'v:0', '-of', 'json', output_filename]
            video_stream = subprocess.Popen(arg, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = video_stream.communicate()
            self.video_metadata = json.loads(stdout)['streams'][0]
        except IndexError:
            print(" ".join(arg))
            print('\nNo video stream detected!')
            exit(1)
        else:
            self.total_frames = int(self.video_metadata['nb_frames'])
            self.video_codec_name = self.video_metadata['codec_name']
        
        self.fps = '0'
        try:
            self.fps = self.video_metadata['avg_frame_rate'].split('/', 1)[0]
        except:
            print('\nError getting video frame rate.')
            while not self.fps.isnumeric() or self.fps == '0':
                self.fps = input('Manual input required: ')

    def GetAudioMetadata(self, output_filename):
        try:
            audio_stream = subprocess.Popen(['ffprobe', '-v', 'quiet', '-show_streams', '-select_streams', 'a:0', '-of', 'json', output_filename], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = audio_stream.communicate()
            self.audio_metadata = json.loads(stdout)['streams'][0]
        except IndexError:
            self.detected_audio_stream = False
            print('\nNo audio stream detected.')
        else:
            self.detected_audio_stream = True
            self.audio_codec_name = self.audio_metadata['codec_name']
       
        if self.args.detect_audio_bitrate:
                self.args.audio_bitrate = str(self.audio_metadata['bit_rate'])

    def IntroOutro(self):
        
        self.CreateTempFolder()

        if self.use_intro:
            self.GetVideoMetadata(self.args.intro_file)
            self.GetAudioMetadata(self.args.intro_file)

            if self.detected_audio_stream:
                arg = ['-i', self.args.intro_file, '-c:v', 'libsvtav1', '-c:a', 'aac', '-crf', '30', '-b:v', '0', '-b:a', self.args.audio_bitrate, '-g', '600', '-preset', '8', f'{os.path.join(self.tempdir, "VMAF intro.mp4")}']
            else:
                arg = ['-i', self.args.intro_file, '-c:v', 'libsvtav1', '-crf', '30', '-b:v', '0', '-an', '-g', '600', '-preset', '8', f'{os.path.join(self.tempdir, "VMAF intro.mp4")}']
            arg[0:0] = self.arg_start
            print('\nEncoding intro...\n')
            p = subprocess.run(arg)
            if p.returncode != 0:
                print(' '.join(arg))
                print('\nError converting intro file to suitable format!')
                exit(1)

        if self.use_outro:
            self.GetVideoMetadata(self.args.outro_file)
            self.GetAudioMetadata(self.args.outro_file)

            if self.detected_audio_stream:
                arg = ['-i', self.args.outro_file, '-c:v', 'libsvtav1', '-c:a', 'aac', '-crf', '30', '-b:v', '0', '-b:a', self.args.audio_bitrate, '-g', '600', '-preset', '8', f'{os.path.join(self.tempdir, "VMAF outro.mp4")}']
            else:
                arg = ['-i', self.args.outro_file, '-c:v', 'libsvtav1', '-crf', '30', '-b:v', '0', '-an', '-g', '600', '-preset', '8', f'{os.path.join(self.tempdir, "VMAF outro.mp4")}']
            arg[0:0] = self.arg_start
            print('\nEncoding outro...\n')
            p = subprocess.run(arg)
            if p.returncode != 0:
                print(' '.join(arg))
                print('\nError converting outro file to suitable format!')
                exit(1)
        
        if self.args.use_intro and not self.args.use_outro:
            IntroOutro = open('IntroOutroList.txt', 'w')
            IntroOutro.write(f"file '{os.path.join(self.tempdir, 'VMAF intro.mp4')}'\n")
            IntroOutro.write(f"file '{self.args.output_dir}{os.path.sep}{os.path.basename(self.filename)}.{self.args.output_extension}'")
        if self.args.use_outro and not self.args.use_intro:
            IntroOutro = open('IntroOutroList.txt', 'w')
            IntroOutro.write(f"file '{self.args.output_dir}{os.path.sep}{os.path.basename(self.filename)}.{self.args.output_extension}'\n")
            IntroOutro.write(f"file '{os.path.join(self.tempdir, 'VMAF outro.mp4')}'")
        else:
            IntroOutro = open('IntroOutroList.txt', 'w')
            IntroOutro.write(f"file '{os.path.join(self.tempdir, 'VMAF intro.mp4')}'\n")
            IntroOutro.write(f"file '{self.args.output_dir}{os.path.sep}{os.path.basename(self.filename)}.{self.args.output_extension}'\n")
            IntroOutro.write(f"file '{os.path.join(self.tempdir, 'VMAF outro.mp4')}'")
        IntroOutro.close()

        self.GetAudioMetadata(f'{self.args.output_dir}{os.path.sep}{os.path.basename(self.filename)}.{self.args.output_extension}')
        if self.detected_audio_stream:
            arg = ['-safe', '0', '-f', 'concat', '-i', 'IntroOutroList.txt', '-map', '0', '-c', 'copy', '-movflags', '+faststart', f'{self.args.output_dir}{os.path.sep}{os.path.basename(self.filename)} with intro or outro.{self.args.output_extension}']
        else:
            arg = ['-safe', '0', '-f', 'concat', '-i', 'IntroOutroList.txt', '-map', '0', '-c:v', 'copy', '-an', '-movflags', '+faststart', f'{self.args.output_dir}{os.path.sep}{os.path.basename(self.filename)} with intro or outro.{self.args.output_extension}']        
        arg[0:0] = self.arg_start

        print('\nCombining intro/outro with video...\n')
        p = subprocess.run(arg)
        if p.returncode != 0:
            print(' '.join(arg))
            print('\nError applying intro or outro to file!')
            exit(1)
        print('\nSuccess!')
        
    def CreateTempFolder(self):
        try:
            os.mkdir(self.tempdir)
            os.mkdir(os.path.join(self.tempdir, 'prepared'))
            os.mkdir(os.path.join(self.tempdir, 'converted'))
        except FileExistsError:
            main.tempcleanup()
            os.mkdir(self.tempdir)
            os.mkdir(os.path.join(self.tempdir, 'prepared'))
            os.mkdir(os.path.join(self.tempdir, 'converted'))

    def cleanup():
        print('Cleaning up...')
        tempfile_list = ['IntroOutroList.txt', 'log.json', 'ffmpeg2pass-0.log']
        for temp in tempfile_list:
            try:        
                os.remove(temp)
            except:
                pass

        if os.path.exists(os.path.join(tempfile.gettempdir(), 'VMAF auto converter')):
            main.tempcleanup()

    def tempcleanup():
        try:
            shutil.rmtree(os.path.join(tempfile.gettempdir(), 'VMAF auto converter'))
        except:
            print('\nError cleaning up temp directory')

if __name__ == '__main__':
    mainClass = main()
    mainClass.main()