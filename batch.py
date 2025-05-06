# %%
# 新增导入
from mutagen.id3 import ID3, TIT2, TPE1, TALB, APIC
from io import BytesIO

# %%
import csv
import os
import time
import requests
from mutagen.id3 import ID3, TIT2, TPE1, TALB, APIC
from io import BytesIO
from source_main import ids, url_v1, name_v1, lyric_v1, parse_cookie, read_cookie, music_level1, size

# 配置参数
CSV_FILE = "music_urls.csv"
OUTPUT_DIR = "downloaded_music"
LEVEL = "lossless"  # 可选音质：standard/exhigh/lossless/hires/sky/jyeffect/jymaster
COOKIE = parse_cookie(read_cookie())  # 自动读取cookie.txt
DELAY = 1  # 请求间隔时间(秒)

def sanitize_filename(name):
    """清理文件名中的非法字符"""
    invalid_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
    for char in invalid_chars:
        name = name.replace(char, '')
    return name.strip()

def add_metadata(filepath, song_info, cover_url):
    """添加元数据到MP3文件"""
    try:
        audio = ID3(filepath)
        
        # 添加基础信息
        audio["TIT2"] = TIT2(encoding=3, text=song_info['name'])
        audio["TPE1"] = TPE1(encoding=3, text='/'.join(ar['name'] for ar in song_info['ar']))
        audio["TALB"] = TALB(encoding=3, text=song_info['al']['name'])
        
        # 添加封面
        if cover_url:
            try:
                response = requests.get(cover_url, timeout=10)
                audio["APIC"] = APIC(
                    encoding=3,
                    mime='image/jpeg',
                    type=3,
                    data=response.content
                )
            except Exception as e:
                print(f"封面下载失败: {str(e)}")
                
        audio.save()
    except Exception as e:
        print(f"元数据写入失败: {str(e)}")

def process_url(url):
    """处理单个音乐URL"""
    try:
        # 获取音乐ID
        song_id = ids(url)
        if not song_id.isdigit():
            raise ValueError("无效的音乐ID")

        # 获取下载地址
        url_data = url_v1(song_id, LEVEL, COOKIE)
        if not url_data['data'][0].get('url'):
            raise Exception("无法获取下载地址")

        # 获取元数据
        detail_data = name_v1(song_id)
        song_info = detail_data['songs'][0]
        
        # 获取歌词
        lyric_data = lyric_v1(song_id, COOKIE)
        lrc_content = lyric_data.get('lrc', {}).get('lyric', '')
        tlyric = lyric_data.get('tlyric', {}).get('lyric', '')

        # 生成标准化文件名
        artist = sanitize_filename('/'.join(ar['name'] for ar in song_info['ar']))
        song_name = sanitize_filename(song_info['name'])
        album = sanitize_filename(song_info['al']['name'])
        filename_base = f"{artist}-{song_name}-{album}"

        # 下载音乐文件
        mp3_path = os.path.join(OUTPUT_DIR, f"{filename_base}.mp3")
        download_url = url_data['data'][0]['url']
        response = requests.get(download_url, stream=True)
        with open(mp3_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)

        # 添加元数据
        add_metadata(mp3_path, song_info, song_info['al']['picUrl'])

        # 保存歌词文件
        lrc_path = os.path.join(OUTPUT_DIR, f"{filename_base}.lrc")
        with open(lrc_path, 'w', encoding='utf-8') as f:
            f.write(f"{lrc_content}\n{tlyric}".strip())

        return True, filename_base
    except Exception as e:
        return False, str(e)

def batch_download():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    failed_records = []
    success_count = 0

    # 读取并备份原始CSV
    with open(CSV_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)
        
        # 添加success列（如果不存在）
        if 'success' not in fieldnames:
            fieldnames.append('success')
            for row in rows:
                row['success'] = '0'

    # 处理每条记录
    for row in rows:
        url = row['url'].strip()
        if not url or row.get('success') == '1':
            continue

        print(f"\n正在处理: {url}")
        try:
            status, result = process_url(url)
            if status:
                row['success'] = '1'
                success_count += 1
                print(f"下载成功: {result}")
            else:
                failed_records.append((url, result))
                print(f"下载失败: {result}")
            
            time.sleep(DELAY)
        except Exception as e:
            failed_records.append((url, str(e)))
            print(f"处理异常: {str(e)}")

    # 写回更新后的CSV
    with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # 输出统计信息
    print("\n处理完成！")
    print(f"成功下载: {success_count} 首")
    if failed_records:
        print("\n失败记录:")
        for url, error in failed_records:
            print(f"{url} | 错误原因: {error}")

if __name__ == "__main__":
    batch_download()


