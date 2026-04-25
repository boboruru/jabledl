import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
import sys
import json
from datetime import datetime

CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'gui_config.json')


def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_config(data):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

# 將 jabledl 模組加入路徑
sys.path.insert(0, os.path.dirname(__file__))

from jabledl.video import Video
from jabledl.downloader import Downloader
from jabledl.segments import Segments


REQUESTS_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (X11; Linux x86_64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/90.0.4430.212 Safari/537.36'
    )
}


class JabledlGUI:

    def __init__(self, root):
        self.root = root
        self.root.title('Jabledl 下載器')
        self.root.resizable(False, False)

        padding = {'padx': 10, 'pady': 5}

        # URL 輸入
        tk.Label(root, text='Jable 網址：').grid(row=0, column=0, sticky='w', **padding)
        self.url_var = tk.StringVar()
        url_entry = tk.Entry(root, textvariable=self.url_var, width=55)
        url_entry.grid(row=0, column=1, columnspan=2, sticky='ew', **padding)
        url_entry.focus()

        # 輸出資料夾
        cfg = load_config()
        default_output = cfg.get('last_output_dir') or os.path.expanduser('~/Downloads')
        tk.Label(root, text='儲存位置：').grid(row=1, column=0, sticky='w', **padding)
        self.output_var = tk.StringVar(value=default_output)
        tk.Entry(root, textvariable=self.output_var, width=45).grid(row=1, column=1, sticky='ew', **padding)
        tk.Button(root, text='選擇…', command=self._pick_folder).grid(row=1, column=2, **padding)

        # 下載按鈕
        self.dl_btn = tk.Button(root, text='開始下載', width=15, command=self._start_download)
        self.dl_btn.grid(row=2, column=0, columnspan=3, pady=8)

        # 進度條
        self.progress = ttk.Progressbar(root, length=480, mode='determinate')
        self.progress.grid(row=3, column=0, columnspan=3, padx=10, pady=4)

        # 狀態訊息
        self.status_var = tk.StringVar(value='等待輸入網址…')
        tk.Label(root, textvariable=self.status_var, anchor='w', width=60).grid(
            row=4, column=0, columnspan=3, sticky='w', padx=10, pady=(0, 8))

    def _pick_folder(self):
        folder = filedialog.askdirectory(title='選擇儲存資料夾')
        if folder:
            self.output_var.set(folder)
            save_config({'last_output_dir': folder})

    def _log(self, msg):
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.root.after(0, lambda: self.status_var.set(f'[{timestamp}] {msg}'))

    def _set_progress(self, value, maximum):
        self.root.after(0, lambda: self._update_progress(value, maximum))

    def _update_progress(self, value, maximum):
        self.progress['maximum'] = maximum
        self.progress['value'] = value

    def _start_download(self):
        url = self.url_var.get().strip()
        output_dir = self.output_var.get().strip()

        if not url:
            messagebox.showwarning('缺少網址', '請先貼上 Jable 影片網址！')
            return
        if not url.startswith('http'):
            messagebox.showwarning('網址錯誤', '請輸入正確的 https:// 網址')
            return
        if not os.path.isdir(output_dir):
            messagebox.showwarning('資料夾不存在', f'找不到資料夾：{output_dir}')
            return

        self.dl_btn.config(state='disabled')
        self.progress['value'] = 0
        save_config({'last_output_dir': output_dir})
        threading.Thread(target=self._download_thread, args=(url, output_dir), daemon=True).start()

    def _download_thread(self, url, output_dir):
        original_dir = os.getcwd()
        try:
            # 切換到輸出資料夾（segments 會在當前目錄產生臨時檔）
            os.chdir(output_dir)

            self._log('取得影片資訊…')
            video = Video(url)
            video.get_metadata()

            total = len(video.segments)
            downloaded = [0]

            def callback():
                downloaded[0] += 1
                self._set_progress(downloaded[0], total)

            self._log(f'下載中：{video.car_number}（共 {total} 個片段）')
            downloader = Downloader(video.segments, REQUESTS_HEADERS, callback)
            downloader.download()

            self._log('解密 AES…')
            segments = Segments(total)
            segments.decrypt(video.aes_key, video.aes_iv)

            self._log('合併片段…')
            segments.merge()

            output_file = (video.full_title or video.car_number) + '.mp4'
            self._log('轉換 MP4…')
            segments.convert(output_file)

            self._log('清理暫存檔…')
            segments.clean()

            full_path = os.path.join(output_dir, output_file)
            self.root.after(0, lambda: messagebox.showinfo('完成', f'已儲存：\n{full_path}'))
            self._log(f'完成！{output_file}')

        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror('錯誤', str(e)))
            self._log(f'錯誤：{e}')
        finally:
            os.chdir(original_dir)
            self.root.after(0, lambda: self.dl_btn.config(state='normal'))


if __name__ == '__main__':
    root = tk.Tk()
    JabledlGUI(root)
    root.mainloop()
