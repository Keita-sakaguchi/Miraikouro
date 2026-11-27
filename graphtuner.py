import pyaudio
import wave
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

chans = 1
samp_rate = 48000
N = 2
chunk = 1024*N
chunk2 = int(chunk / 2)
dev_index = 2
wav_output_filename = "test.wav"
sleepTime = 0.0001


audio = pyaudio.PyAudio()

stream = audio.open(format = pyaudio.paInt16,channels = chans,rate = samp_rate,\
                    input = True,input_device_index = dev_index, \
                    frames_per_buffer = chunk)

wave_x = np.linspace(0,samp_rate,chunk)
chunk2 = int(chunk / 2)
wave_x2 = wave_x[0:chunk2]


print("start recording")

while True:
    try:
        data = stream.read(chunk,exception_on_overflow=False)
        ndarray = np.frombuffer(data,dtype = "int16")
        
        wave_y = np.fft.fft(ndarray)
        wave_y = np.abs(wave_y)
        wave_y2 = wave_y[0:chunk2]
        
        plt.plot(wave_x2,wave_y2)
        plt.draw()
        plt.pause(sleepTime)
        plt.cla()
        
        
        
    except KeyboardInterrupt:
        print("stop")
        break

print("finished")

stream.stop_stream()
stream.close()
audio.terminate()
