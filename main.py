import os
import cv2
import json
import time
import math
import subprocess
import multiprocessing
import threading
from pathlib import Path

ffmpeg_bin = 'ffmpeg'  # ffmpeg路径
ffprobe_bin = 'ffprobe'  # ffprobe路径
video_path = 'input.mp4'  # 源文件路径
dst_file_name = 'out.mkv'  # 目标文件名

# 获取视频信息
ffprobe_head = ffprobe_bin + " -v error -show_streams -select_streams v:0 -of json "

# 用json方式记录捕获到的信息
cat_info = subprocess.run(ffprobe_head.split() + [video_path],
                          capture_output=True)

video_info = json.loads(cat_info.stdout.decode('utf8'))
video_stream_info = video_info['streams'][0]

# 帧率
video_frame_rate = int(eval(video_stream_info['r_frame_rate']))

# 提取音频
extract_audio = subprocess.Popen([ffmpeg_bin,
                                  '-i', video_path,
                                  '-vn',
                                  '-c:a', 'copy',
                                  '.cache/src-audio.mkv'],
                                 )

# 载入mask
extract_mask = subprocess.run(['./extract_mask.sh',
                               video_path
                               ],
                              capture_output=True)

mask = cv2.imread('.cache/mask.png', cv2.IMREAD_GRAYSCALE)


# 去除水印函数
def remove_watermark(file_path):
    src = cv2.imread(file_path)
    dst = cv2.inpaint(src, mask, 5, cv2.INPAINT_TELEA)
    cv2.imwrite(file_path, dst)


frames_per_seq = 256

start = time.time()


# 去水印进程
def remove_watermark_process(seq_num, frames_num):
    # 提取帧序列
    folder_path = '.cache/' + str(seq_num)
    Path(folder_path).mkdir(parents=True)

    # 起始帧
    start_frame = int(seq_num * frames_per_seq)
    extract_frames = subprocess.Popen(['./extract_frames.sh',
                                       video_path,
                                       str(start_frame),
                                       str(frames_num),
                                       folder_path])

    threads = []

    old_frames_list = set([])
    flag = 0

    while True:
        if extract_frames.poll() is not None:
            flag = 1

        frames_list = set(list(Path(folder_path).glob('*.png')))
        newly_frames = frames_list - old_frames_list
        # print(newly_frames)

        for frame in newly_frames:
            thread = threading.Thread(target=remove_watermark, args=(frame.as_posix(),))
            threads.append(thread)
            thread.start()

        if flag == 1:
            break

        old_frames_list = frames_list

    for thread in threads:
        thread.join()

    merge_frames = subprocess.Popen([ffmpeg_bin, '-y',
                                     '-vsync', '0',
                                     '-hwaccel', 'cuda',
                                     '-hwaccel_output_format', 'cuda',
                                     '-framerate', str(video_frame_rate),
                                     '-i', folder_path + '/im-%d.png',
                                     '-b:v', video_stream_info['bit_rate'],
                                     # '-c:v', video_stream_info['codec_name'],
                                     '-c:v', 'hevc_nvenc',
                                     '-pix_fmt', video_stream_info['pix_fmt'],
                                     'dst/' + str(seq_num) + '.mkv'])

    merge_frames.wait()

    os.system('rm -rf ' + folder_path)


# 多进程对帧序列去水印
pool = multiprocessing.Pool(processes=3)

seq_count = math.ceil(eval(video_stream_info['nb_frames']) / frames_per_seq)

for i in range(seq_count - 1):
    pool.apply_async(remove_watermark_process, (i, frames_per_seq,))

pool.apply_async(remove_watermark_process,
                 (seq_count - 1, (eval(video_stream_info['nb_frames']) % frames_per_seq),))

pool.close()
pool.join()

end = time.time()
print(end - start)

merge_file = subprocess.run(['./merge.sh'], capture_output=True)

extract_audio.wait()

merge_video = subprocess.run([ffmpeg_bin, '-y',
                              '-i', 'output.mkv',
                              '-i', '.cache/src-audio.mkv',
                              '-c:v', 'copy',
                              '-c:a', 'copy',
                              dst_file_name]
                             )

os.system('rm output.mkv')
os.system('rm -rf .cache/*')
