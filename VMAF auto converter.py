import glob
import subprocess
import os
import xml.etree.ElementTree as ET
import time

try:
    os.mkdir('converted')
except:
    pass
for file in glob.glob('*.mp4'):
    vmaf_value = 0
    crf_value = 34
    while True:
        subprocess.run(['ffmpeg', '-n', '-i', file, '-c:a', 'aac', '-c:v', 'libsvtav1', '-crf', str(crf_value), '-b:v', '0', '-b:a', '192k', f'converted/{os.path.splitext(file)[0]} converted{os.path.splitext(file)[1]}'])
        subprocess.run(['ffmpeg', '-i', f'converted/{os.path.splitext(file)[0]} converted{os.path.splitext(file)[1]}', '-i', file, '-lavfi', 'libvmaf=log_path=log.xml', '-f', 'null', '-'], stdout=subprocess.PIPE)
        root = ET.parse('log.xml').getroot()
        vmaf_value = float(root.findall('pooled_metrics/metric')[-1].get('mean'))

        if not 90 <= vmaf_value <= 95:
            if vmaf_value < 90:
                print('\nVMAF value too low, retrying with a CRF decrease of 1...')
                time.sleep(2)
                crf_value = crf_value - 1
                os.remove(f'converted/{os.path.splitext(file)[0]} converted{os.path.splitext(file)[1]}')
            elif vmaf_value > 95:
                print('\nVMAF value too high, retrying with a CRF increase of 1...')
                time.sleep(2)
                crf_value = crf_value + 1
                os.remove(f'converted/{os.path.splitext(file)[0]} converted{os.path.splitext(file)[1]}')
            continue
        else:
            break
os.remove('log.xml')
input('Done!')