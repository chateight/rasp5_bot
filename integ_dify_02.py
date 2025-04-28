# -*- coding: utf-8 -*-
import vosk
import pyaudio
import json
import numpy as np
import sounddevice as sd
import queue
import threading
import time
import subprocess
import requests
import spacy
import jaconv
from langdetect import detect
import re
import datetime

API_KEY = 'app-2P9J3KhhMzPGJKrJ1dqXHhIN'
BASE_URL = 'http://localhost/v1/chat-messages'
USER_ID = 'user0'

NLP = spacy.load("ja_ginza")

def greet_and_adjust_eyes():
    # 現在の時間帯に応じて挨拶を行う
    current_hour = datetime.datetime.now().hour
    if 5 <= current_hour < 11:
        greeting = "おはようございます！"
    elif 11 <= current_hour < 17:
        greeting = "こんにちは！"
    else:
        greeting = "こんばんは！"

    # 挨拶の音声合成
    threaded_speak(greeting)

    # 瞼を80度から130度に変化させる
    control_servo_by_sentiment(-1.0, 1.0)  # 感情スコアを-1にして、角度を80度にセット
    time.sleep(1)  # 少し待機してから
    control_servo_by_sentiment(0.0, 1.0)  # 再度130度に調整

def check_for_person_and_greet():
    while True:
        try:
            # 物体認識APIにリクエスト
            result = requests.get('http://localhost:5000/detect').json()

            # 「person」ラベルを検出した場合に挨拶
            if any(item['label'] == 'person' for item in result):
                threaded_speak("アノニマスさん、ご機嫌いかがですか？")
                break
            else:
                print(".")
        except Exception as e:
            print(f"物体認識エラー: {e}")
        
        #time.sleep(1)

def load_combined_sentiment_dict(paths):
    sentiment = {}
    for path in paths:
        with open(path, encoding='UTF-8') as f:
            for line in f:
                cols = line.strip().split('\t')
                if len(cols) < 2:
                    continue
                label = cols[0]
                word = cols[1]
                score = -1.0 if "ネガ" in label else 1.0 if "ポジ" in label else 0.0
                sentiment[word] = score
    return sentiment

SENTIMENT_DICT = load_combined_sentiment_dict(["wago.121808.pn"])

def analyze_sentiment(text):
    doc = NLP(text)
    pos = sum(1 for token in doc if SENTIMENT_DICT.get(token.lemma_, 0) > 0)
    neg = sum(1 for token in doc if SENTIMENT_DICT.get(token.lemma_, 0) < 0)
    total = len([t for t in doc if not t.is_punct])
    score = max(-1, min(1, (pos - neg) / total * 10 if total > 0 else 0))
    return score

def control_servo_by_sentiment(score, duration):
    angle = max(80, min(181, 130 + 50 * score))
    process = subprocess.run(
        ["sudo", "python3", "servo_control.py", str(angle), str(duration)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    #print(f"サーボ動作時間: {duration:.2f}秒")
    subprocess.run(["sudo", "python3", "servo_control.py", "130", "0.5"])
    if process.stdout:
        print(process.stdout.decode())
    if process.stderr:
        print(process.stderr.decode())

def split_text_for_speech(text, max_len=25):
    phrases = re.split(r'(?<=[。！？])', text)
    result = []
    current = ""
    for p in phrases:
        if len(current + p) > max_len:
            result.append(current.strip())
            current = p
        else:
            current += p
    if current:
        result.append(current.strip())
    return result

def speak(text):
    path = "/dev/shm/out.wav"
    cmd_base = [
        '/usr/bin/open_jtalk',
        '-x', '/var/lib/mecab/dic/open-jtalk/naist-jdic',
        '-m', '/usr/share/hts-voice/nitech-jp-atr503-m001/nitech_jp_atr503_m001.htsvoice',
        '-r', '1.1',
        '-ow', path
    ]

    try:
        print(f"[speak] 最終読み上げテキスト: {text}")
        chunks = split_text_for_speech(text)

        for chunk in chunks:
            chunk = chunk.strip()
            if not chunk:
                continue
            #print(f"[speak] チャンク読み上げ: {chunk}")
            start = time.time()
            proc = subprocess.Popen(cmd_base, stdin=subprocess.PIPE)
            proc.stdin.write(chunk.encode('utf-8'))
            proc.stdin.close()
            proc.wait()
            #print(f"[speak] open_jtalk 終了: {(time.time() - start):.2f}s")

            #print(f"[speak] aplay 再生開始")
            subprocess.run(['aplay', path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            #print(f"[speak] aplay 再生終了")
            time.sleep(0.2)
    except Exception as e:
        print(f"音声合成エラー: {e}")

"""
def safe_speak(text):
    # 数字、アルファベット、漢字、記号（例えば「、」や「。」）を残すように修正
    cleaned_text = re.sub(r'[^\w\s、。！？ぁ-んァ-ヶ一-龯]', '', text)  # 不要な記号のみ削除
    cleaned_text = re.sub(r'[^\x00-\x7F]+', '', cleaned_text)  # ASCII範囲外の文字（絵文字）を削除

    # 数字のみがある場合、除外（例えば「2600」など）
    cleaned_text = re.sub(r'^\d+$', '', cleaned_text)

    # 改行やスペースを適切に整理
    cleaned_text = cleaned_text.strip()  # 前後の空白を削除
    
    # 空白や不要な部分を削除
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text)  # 複数の空白を1つにまとめる

    # 不正な文字列（例えば「すすす」など）を除去
    cleaned_text = re.sub(r'すすす+', '', cleaned_text)

    # テキストが空でない場合に処理を進める
    if cleaned_text:
        speak(cleaned_text)
"""

def threaded_speak(text, on_complete=None):
    #print(f"[threaded_speak] 入力テキスト: {text}")  # ログを追加
    def run():
        #print("[threaded_speak] safe_speak を呼び出し")
        speak(text)
        #safe_speak(text)
        if on_complete:
            on_complete()
    threading.Thread(target=run).start()

def play_sound_effect(path="./sounds/click.wav"):
    try:
        subprocess.run(['aplay', path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    except Exception as e:
        print(f"効果音再生エラー: {e}")

def query_dify(prompt):
    headers = {
        'Authorization': f'Bearer {API_KEY}',
        'Content-Type': 'application/json'
    }
    data = {
        "inputs": {},
        "query": prompt,
        "response_mode": "streaming",
        "conversation_id": "",
        "user": USER_ID,
        "files": []
    }

    try:
        response = requests.post(BASE_URL, headers=headers, json=data, stream=True)
        response.raise_for_status()
        response.encoding = 'utf-8'
        chunks = []
        for line in response.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')
                if decoded_line.startswith("data: "):
                    json_data = json.loads(decoded_line[6:])
                    if json_data.get("event") == "message":
                        chunk = json_data.get("answer", "")
                        print(f"Difyチャンク: {chunk!r}")
                        if chunk:
                            chunks.append(chunk)
                            threading.Thread(target=play_sound_effect).start()
        return ''.join(chunks).strip()
    except Exception as e:
        print(f"Difyエラー: {e}")
        return "エラーが発生しました。もう一度試してください。"

def estimate_speech_duration(text, rate=1.0):
    num_chars = len(text.replace('。', '').replace('、', ''))
    base_time = num_chars * 0.15
    return base_time / rate

def clean_text_for_jtalk(text):
    text = re.sub(r'[^\x20-\x7Eぁ-んァ-ヶ一-龥ー。、！？\n\r]', '', text)
    text = re.sub(r'[\u3000\u200B-\u200D\uFEFF]', '', text)
    text = re.sub(r'[。、]{2,}', lambda m: m.group(0)[0], text)
    text = re.sub(r'\s{2,}', ' ', text)
    return text.strip()

class VoskSpeechRecognizer:
    def __init__(self, model_path='./vosk-model-ja-0.22'):
        vosk.SetLogLevel(-1)
        self.model = vosk.Model(model_path)
        self.recognizer = vosk.KaldiRecognizer(self.model, 16000)
        self.audio_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.speech_lock = threading.Event()
        self.sample_rate = 16000
        self.channels = 1
        self.stream = None
        self.recording_thread = threading.Thread(target=self._record_audio)
        self.recognition_thread = threading.Thread(target=self._recognize_audio)

    def pause_recording(self):
        if self.stream:
            self.stream.stop()

    def resume_recording(self):
        if self.stream:
            self.stream.start()

    def clear_audio_queue(self):
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break

    def _record_audio(self):
        with sd.InputStream(samplerate=self.sample_rate, channels=self.channels, dtype='int16', callback=self._audio_callback) as stream:
            self.stream = stream
            while not self.stop_event.is_set():
                sd.sleep(100)

    def _audio_callback(self, indata, frames, time, status):
        if status:
            print(status)
        self.audio_queue.put(indata.copy())

    def _recognize_audio(self):
        while not self.stop_event.is_set():
            try:
                self.speech_lock.wait()
                audio_chunk = self.audio_queue.get(timeout=0.5)
                if self.recognizer.AcceptWaveform(audio_chunk.tobytes()):
                    result = json.loads(self.recognizer.Result())
                    text = result.get('text', '').strip()
                    if text and len(text) > 4:
                        print(f"認識結果: {text}")
                        self.speech_lock.clear()
                        response_text = query_dify(text)
                        self.clear_audio_queue()

                        if not response_text or len(response_text) < 2:
                            print("レスポンスが短すぎるか空です。スキップします。")
                            self.speech_lock.set()
                            continue

                        try:
                            lang = detect(response_text)
                        except Exception:
                            lang = "unknown"

                        if lang == "en":
                            print("英語レスポンスなので読み上げをスキップします")
                            self.pause_recording()
                            threaded_speak("英語のため読み上げをスキップします。", on_complete=self.resume_recording)
                            self.speech_lock.set()
                        else:
                            response_text = (
                                response_text
                                .replace('\r', '')
                                .replace('\n', '。')
                                .replace('！。', '！')
                                .replace('？。', '？')
                                .replace('。。', '。')
                                .strip()
                            )
                            if not response_text.endswith(('。', '！', '？')):
                                response_text += '。'

                            duration = estimate_speech_duration(response_text)

                            def analyze_and_control():
                                score = analyze_sentiment(response_text)
                                print(f"感情スコア: {score:.2f}")
                                control_servo_by_sentiment(score, duration)

                            threading.Thread(target=analyze_and_control).start()

                            self.pause_recording()
                            cleaned_text = clean_text_for_jtalk(response_text)

                            def on_speak_complete():
                                self.resume_recording()
                                self.speech_lock.set()

                            threaded_speak(cleaned_text, on_complete=on_speak_complete)

            except queue.Empty:
                continue

    def start_recognition(self):
        self.stop_event.clear()
        self.speech_lock.set()
        self.recording_thread.start()
        self.recognition_thread.start()

    def stop_recognition(self):
        self.stop_event.set()
        self.recording_thread.join()
        self.recognition_thread.join()

def main():
    # 起動時に挨拶と瞼調整
    greet_and_adjust_eyes()

    # person認識のスレッドを開始
    recognition_thread = threading.Thread(target=check_for_person_and_greet)
    recognition_thread.start()
    recognition_thread.join()

    recognizer = VoskSpeechRecognizer()
    try:
        print("音声認識を開始します。Ctrl+Cで終了できます。")
        recognizer.start_recognition()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n音声認識を終了します...")
    finally:
        recognizer.stop_recognition()

if __name__ == "__main__":
    main()
