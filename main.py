import os
import cv2
import json
import time
import math
import subprocess
import multiprocessing
import threading
from pathlib import Path

# 提取帧
ffmpeg_bin = 'ffmpeg'
ffprobe_bin = 'ffprobe'
video_path = '/mnt/nvme0n1p1/Videos/down_bili/in.mp4'

# 获取视频信息
ffprobe_head = ffprobe_bin + " -v error -show_streams -select_streams v:0 -of json "

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

extract_audio.wait()

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


frames_per_seq = 128

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
                                     '-framerate', str(video_frame_rate),
                                     '-i', folder_path + '/im-%d.png',
                                     '-b:v', video_stream_info['bit_rate'],
                                     '-c:v', video_stream_info['codec_name'],
                                     '-pix_fmt', video_stream_info['pix_fmt'],
                                     'dst/' + str(seq_num) + '.mkv'])

    merge_frames.wait()

    os.system('rm -rf ' + folder_path)


# 多进程对帧序列去水印
pool = multiprocessing.Pool(processes=1)

seq_count = math.ceil(eval(video_stream_info['nb_frames']) / frames_per_seq)

for i in range(seq_count - 5):
    pool.apply_async(remove_watermark_process, (i, frames_per_seq,))

# pool.apply_async(remove_watermark_process,
#                  (seq_count - 1, (eval(video_stream_info['nb_frames']) % frames_per_seq),))

pool.close()
pool.join()

end = time.time()
print(end - start)

# 目标文件名
dst_file_name = '3'

extract_audio.wait()

# merge_frame = subprocess.Popen([ffmpeg_bin, '-y',
#                                  # '-f', 'image2',
#                                  '-framerate', str(video_frame_rate),
#                                  '-i', '.cache/im-%d.png',
#                                  '-i', '.cache/src-audio.mkv',
#                                  '-b:v', video_stream_info['bit_rate'],
#                                  '-c:v', video_stream_info['codec_name'],
#                                  '-pix_fmt', video_stream_info['pix_fmt'],
#                                  '-c:a', 'copy',
#                                  'dst/nice.mkv'])
#
# merge_frame.wait()

# os.system('rm -rf .cache/*')
