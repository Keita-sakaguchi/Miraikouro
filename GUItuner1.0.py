
import pygame
import pyaudio
import numpy as np
import math
import threading
import time

# ==========================================
# 1. 基本設定
# ==========================================

chans = 1
samp_rate = 48000
N = 8192
chunk = 4096

# USBマイクのデバイス番号
# Noneなら既定のマイクを使用
dev_index = None

# 音名
scale_name = [
    "C", "C#", "D", "D#", "E", "F",
    "F#", "G", "G#", "A", "A#", "B"
]

# 音声解析結果
peak_freq = 0.0
name_1 = "--"
change_number = 0.0

# スレッド制御
running = False
audio_thread = None
stop_event = threading.Event()

# データ共有用
data_lock = threading.Lock()

# マイク入力データ
wave_1 = np.zeros(N, dtype=np.float32)

# ==========================================
# 2. PyAudioの準備
# ==========================================

audio = pyaudio.PyAudio()
stream = None


# ==========================================
# 3. 音声解析スレッド
# ==========================================

def tuner_thread():

    global peak_freq
    global name_1
    global change_number
    global wave_1

    buffer_data = np.zeros(N, dtype=np.float32)

    while not stop_event.is_set():

        try:
            # マイクから音声を取得
            audio_data = stream.read(
                chunk,
                exception_on_overflow=False
            )

            # バイトデータを数値配列に変換
            ndarray = np.frombuffer(
                audio_data,
                dtype=np.int16
            )

            ndarray = ndarray.astype(np.float32) / 32768.0

            # 古いデータを左にずらして新しいデータを追加
            buffer_data = np.roll(buffer_data, -chunk)
            buffer_data[-chunk:] = ndarray

            # FFT解析
            window = np.hanning(N)
            fft_data = np.abs(
                np.fft.rfft(buffer_data * window)
            )

            freqs = np.fft.rfftfreq(
                N,
                d=1 / samp_rate
            )

            # 解析する周波数範囲
            min_index = np.searchsorted(freqs, 30)
            max_index = np.searchsorted(freqs, 2000)

            # 最大ピークを取得
            peak = np.argmax(
                fft_data[min_index:max_index]
            ) + min_index

            current_peak_freq = freqs[peak]

            # 音量が小さすぎる場合は無視
            if np.max(np.abs(buffer_data)) < 0.01:
                continue

            if current_peak_freq <= 0:
                continue

            # ==================================
            # 4. 周波数から音名を判定
            # ==================================

            # A4 = 440Hzを基準に音程を計算
            number = 69 + 12 * math.log2(
                current_peak_freq / 440
            )

            # 最も近い音階番号
            note_number = round(number)

            # 音名を取得
            note_index = note_number % 12
            current_name = scale_name[note_index]

            # 基準音の周波数
            target_freq = 440 * (
                2 ** ((note_number - 69) / 12)
            )

            # セント差を計算
            cents = 1200 * math.log2(
                current_peak_freq / target_freq
            )

            # 共有データを更新
            with data_lock:

                peak_freq = current_peak_freq
                name_1 = current_name
                change_number = cents

                wave_1 = buffer_data.copy()

        except Exception as e:

            if not stop_event.is_set():
                print("音声解析エラー:", e)

            break


# ==========================================
# 5. チューナーの開始・停止
# ==========================================

def start_tuner():

    global stream
    global audio_thread
    global running

    if running:
        return

    try:

        stream = audio.open(
            format=pyaudio.paInt16,
            channels=chans,
            rate=samp_rate,
            input=True,
            input_device_index=dev_index,
            frames_per_buffer=chunk
        )

        stop_event.clear()

        audio_thread = threading.Thread(
            target=tuner_thread,
            daemon=True
        )

        audio_thread.start()

        running = True

    except Exception as e:

        print("マイク開始エラー:", e)


def stop_tuner():

    global stream
    global audio_thread
    global running

    if not running:
        return

    stop_event.set()

    if audio_thread is not None:
        audio_thread.join(timeout=2)

    if stream is not None:

        if stream.is_active():
            stream.stop_stream()

        stream.close()
        stream = None

    audio_thread = None
    running = False


# ==========================================
# 6. Pygameの準備
# ==========================================

pygame.init()

screen = pygame.display.set_mode((800, 550))
pygame.display.set_caption("Raspberry Pi Tuner")

clock = pygame.time.Clock()

font = pygame.font.SysFont(
    "notosanscjkjp",
    30
)

small_font = pygame.font.SysFont(
    "notosanscjkjp",
    20
)

# 画面の中心
CENTER_X = 400
CENTER_Y = 430

# 目盛りの半径
RADIUS = 200


# ==========================================
# 7. 文字表示関数
# ==========================================

def draw_text(text, x, y, size=30):

    if size == 20:
        use_font = small_font
    else:
        use_font = font

    surface = use_font.render(
        str(text),
        True,
        (0, 0, 0)
    )

    rect = surface.get_rect(
        center=(x, y)
    )

    screen.blit(surface, rect)


# ==========================================
# 8. 目盛りの描画
# ==========================================

def draw_scale():

    for cents in range(-50, 51, 10):

        # セント差から角度に変換
        angle = cents * 45 / 50

        rad = math.radians(angle)

        # 目盛りの外側
        x1 = CENTER_X + RADIUS * math.sin(rad)
        y1 = CENTER_Y - RADIUS * math.cos(rad)

        # 目盛りの内側
        tick_length = 25 if cents == 0 else 15

        x2 = CENTER_X + (
            RADIUS - tick_length
        ) * math.sin(rad)

        y2 = CENTER_Y - (
            RADIUS - tick_length
        ) * math.cos(rad)

        # 目盛りを描画
        width = 4 if cents == 0 else 2

        pygame.draw.line(
            screen,
            (0, 0, 0),
            (x1, y1),
            (x2, y2),
            width
        )

        # 数値を表示
        tx = CENTER_X + (
            RADIUS + 30
        ) * math.sin(rad)

        ty = CENTER_Y - (
            RADIUS + 30
        ) * math.cos(rad)

        draw_text(
            cents,
            int(tx),
            int(ty),
            20
        )


# ==========================================
# 9. 針の描画
# ==========================================

def draw_needle(cents):

    # 表示範囲を-50～50に制限
    cents = max(-50, min(50, cents))

    angle = cents * 45 / 50
    rad = math.radians(angle)

    # 針の先端
    needle_x = CENTER_X + (
        RADIUS - 35
    ) * math.sin(rad)

    needle_y = CENTER_Y - (
        RADIUS - 35
    ) * math.cos(rad)

    pygame.draw.line(
        screen,
        (220, 30, 30),
        (CENTER_X, CENTER_Y),
        (needle_x, needle_y),
        5
    )

    pygame.draw.circle(
        screen,
        (0, 0, 0),
        (CENTER_X, CENTER_Y),
        8
    )


# ==========================================
# 10. ボタンの描画
# ==========================================

button_rect = pygame.Rect(
    330, 470, 140, 50
)


def draw_button():

    color = (200, 80, 80) if running else (70, 150, 90)

    pygame.draw.rect(
        screen,
        color,
        button_rect,
        border_radius=10
    )

    button_text = "STOP" if running else "START"

    draw_text(
        button_text,
        400,
        495,
        30
    )


# ==========================================
# 11. メインループ
# ==========================================

try:

    while True:

        screen.fill((255, 255, 255))

        # イベント処理
        for event in pygame.event.get():

            if event.type == pygame.QUIT:
                raise KeyboardInterrupt

            # ボタン操作
            if event.type == pygame.MOUSEBUTTONDOWN:

                if button_rect.collidepoint(event.pos):

                    if running:
                        stop_tuner()
                    else:
                        start_tuner()

            # スペースキーでも開始・停止
            if event.type == pygame.KEYDOWN:

                if event.key == pygame.K_SPACE:

                    if running:
                        stop_tuner()
                    else:
                        start_tuner()

        # 共有データを取得
        with data_lock:

            current_freq = peak_freq
            current_name = name_1
            current_cents = change_number

        # タイトル
        draw_text(
            "TUNER",
            400,
            35,
            30
        )

        # 音名
        draw_text(
            current_name,
            400,
            100,
            30
        )

        # 周波数
        draw_text(
            f"{current_freq:.2f} Hz",
            400,
            145,
            30
        )

        # セント差
        draw_text(
            f"{current_cents:+.1f} cent",
            400,
            185,
            30
        )

        # 目盛り
        draw_scale()

        # 針
        if running and current_freq > 0:
            draw_needle(current_cents)

        # ボタン
        draw_button()

        pygame.display.update()

        clock.tick(30)

except KeyboardInterrupt:
    print("プログラムを終了します")

finally:

    stop_tuner()

    audio.terminate()

    pygame.quit()
