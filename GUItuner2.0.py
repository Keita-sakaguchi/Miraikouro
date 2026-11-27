
import pygame
import pyaudio
import numpy as np
import math
import threading
import time
import RPi.GPIO as GPIO


# ==========================================
# 1. 基本設定
# ==========================================

chans = 1
samp_rate = 48000
N = 8192
chunk = 4096

# USBマイクのデバイス番号
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

wave_1 = np.zeros(N, dtype=np.float32)


# ==========================================
# 2. スピーカー設定
# ==========================================

speaker_pin = 18

GPIO.setmode(GPIO.BCM)
GPIO.setup(speaker_pin, GPIO.OUT)

speaker_pwm = None
speaker_on = False

# 初期音：A4（440Hz）
speaker_note = 69

speaker_volume = 20


# ==========================================
# 3. PyAudioの準備
# ==========================================

audio = pyaudio.PyAudio()
stream = None


# ==========================================
# 4. 音声解析スレッド
# ==========================================

def tuner_thread():

    global peak_freq
    global name_1
    global change_number
    global wave_1

    buffer_data = np.zeros(N, dtype=np.float32)

    while not stop_event.is_set():

        try:

            audio_data = stream.read(
                chunk,
                exception_on_overflow=False
            )

            ndarray = np.frombuffer(
                audio_data,
                dtype=np.int16
            )

            ndarray = ndarray.astype(np.float32) / 32768.0

            # データを更新
            buffer_data = np.roll(buffer_data, -chunk)
            buffer_data[-chunk:] = ndarray

            # 音量が小さすぎる場合は無視
            if np.max(np.abs(buffer_data)) < 0.01:
                continue

            # FFT解析
            window = np.hanning(N)

            fft_data = np.abs(
                np.fft.rfft(buffer_data * window)
            )

            freqs = np.fft.rfftfreq(
                N,
                d=1 / samp_rate
            )

            # 解析範囲
            min_index = np.searchsorted(freqs, 30)
            max_index = np.searchsorted(freqs, 2000)

            # 最大ピーク
            peak = np.argmax(
                fft_data[min_index:max_index]
            ) + min_index

            current_peak_freq = freqs[peak]

            if current_peak_freq <= 0:
                continue

            # ==================================
            # 周波数から音名を判定
            # ==================================

            number = 69 + 12 * math.log2(
                current_peak_freq / 440
            )

            note_number = round(number)

            note_index = note_number % 12

            current_name = scale_name[note_index]

            # 基準周波数
            target_freq = 440 * (
                2 ** ((note_number - 69) / 12)
            )

            # セント差
            cents = 1200 * math.log2(
                current_peak_freq / target_freq
            )

            # データ更新
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
# 5. チューナー開始・停止
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
# 6. スピーカー制御
# ==========================================

def get_speaker_frequency():

    return 440 * (
        2 ** ((speaker_note - 69) / 12)
    )


def get_speaker_name():

    note_names = [
        "C", "C#", "D", "D#", "E", "F",
        "F#", "G", "G#", "A", "A#", "B"
    ]

    note_index = speaker_note % 12

    octave = speaker_note // 12 - 1

    return note_names[note_index] + str(octave)


def toggle_speaker():

    global speaker_on
    global speaker_pwm

    if speaker_on:

        if speaker_pwm is not None:
            speaker_pwm.stop()
            speaker_pwm = None

        speaker_on = False

    else:

        frequency = get_speaker_frequency()

        speaker_pwm = GPIO.PWM(
            speaker_pin,
            frequency
        )

        speaker_pwm.start(speaker_volume)

        speaker_on = True


def change_speaker_note(value):

    global speaker_note

    speaker_note += value

    if speaker_on and speaker_pwm is not None:

        frequency = get_speaker_frequency()

        speaker_pwm.ChangeFrequency(frequency)


# ==========================================
# 7. Pygameの準備
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

CENTER_X = 400
CENTER_Y = 430

RADIUS = 200


# ==========================================
# 8. 文字表示関数
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
# 9. 目盛りの描画
# ==========================================

def draw_scale():

    for cents in range(-50, 51, 10):

        angle = cents * 45 / 50

        rad = math.radians(angle)

        x1 = CENTER_X + RADIUS * math.sin(rad)
        y1 = CENTER_Y - RADIUS * math.cos(rad)

        tick_length = 25 if cents == 0 else 15

        x2 = CENTER_X + (
            RADIUS - tick_length
        ) * math.sin(rad)

        y2 = CENTER_Y - (
            RADIUS - tick_length
        ) * math.cos(rad)

        width = 4 if cents == 0 else 2

        pygame.draw.line(
            screen,
            (0, 0, 0),
            (x1, y1),
            (x2, y2),
            width
        )

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
# 10. 針の描画
# ==========================================

def draw_needle(cents):

    cents = max(-50, min(50, cents))

    angle = cents * 45 / 50

    rad = math.radians(angle)

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
# 11. チューナーボタン
# ==========================================

button_rect = pygame.Rect(
    330, 470, 140, 50
)


def draw_button():

    color = (
        (200, 80, 80)
        if running
        else (70, 150, 90)
    )

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
# 12. メインループ
# ==========================================

try:

    while True:

        screen.fill((255, 255, 255))

        # イベント処理
        for event in pygame.event.get():

            if event.type == pygame.QUIT:
                raise KeyboardInterrupt

            # マウス操作
            if event.type == pygame.MOUSEBUTTONDOWN:

                # 左クリック：チューナーON/OFF
                if event.button == 1:

                    if button_rect.collidepoint(event.pos):

                        if running:
                            stop_tuner()
                        else:
                            start_tuner()

                # 右クリック：スピーカーON/OFF
                if event.button == 3:

                    toggle_speaker()

            # キーボード操作
            if event.type == pygame.KEYDOWN:

                # スペース：チューナーON/OFF
                if event.key == pygame.K_SPACE:

                    if running:
                        stop_tuner()
                    else:
                        start_tuner()

                # 上：半音上げる
                if event.key == pygame.K_UP:

                    if speaker_on:
                        change_speaker_note(1)

                # 下：半音下げる
                if event.key == pygame.K_DOWN:

                    if speaker_on:
                        change_speaker_note(-1)

        # ==================================
        # 音声解析結果の取得
        # ==================================

        with data_lock:

            current_freq = peak_freq
            current_name = name_1
            current_cents = change_number

        # ==================================
        # チューナー表示
        # ==================================

        draw_text(
            "TUNER",
            400,
            35,
            30
        )

        draw_text(
            current_name,
            400,
            100,
            30
        )

        draw_text(
            f"{current_freq:.2f} Hz",
            400,
            145,
            30
        )

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

        # ==================================
        # スピーカー表示
        # ==================================

        if speaker_on:

            draw_text(
                "Speaker: ON",
                400,
                225,
                20
            )

            draw_text(
                "Sound: " + get_speaker_name(),
                400,
                255,
                20
            )

            draw_text(
                f"Frequency: {get_speaker_frequency():.2f} Hz",
                400,
                285,
                20
            )

        else:

            draw_text(
                "Speaker: OFF",
                400,
                225,
                20
            )

        # ボタン
        draw_button()

        pygame.display.update()

        clock.tick(30)


except KeyboardInterrupt:

    print("プログラムを終了します")


finally:

    stop_tuner()

    # スピーカー停止
    if speaker_on and speaker_pwm is not None:

        speaker_pwm.stop()
        speaker_pwm = None
        speaker_on = False

    # GPIO解放
    GPIO.cleanup()

    audio.terminate()

    pygame.quit()
