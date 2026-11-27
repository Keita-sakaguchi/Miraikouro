import pyaudio
import wave
import numpy as np
import pandas as pd

chans = 1
samp_rate = 48000
N = 2
chunk = 1024*N

dev_index = 2
wav_output_filename = "test.wav"
sleepTime = 0.0001



scale_name = ["A#","B","C","C#","D","D#","E","F","F#","G","G#","A","A#"]

scale = [466.164,493.883,523.251,554.365,587.330,622.254,659.255,698.456,739.989,783.991/
              830.609,880.000,932.328]

data_scale = pd.DataFrame({
    'scale_list': [466.164,493.883,523.251,554.365,587.330,622.254,659.255,698.456,739.989,783.991/
              830.609,880.000,932.328]})

audio = pyaudio.PyAudio()

stream = audio.open(format = pyaudio.paInt16,channels = chans,rate = samp_rate,\
                    input = True,input_device_index = dev_index, \
                    frames_per_buffer = chunk)

chunk2 = int(chunk /2)

print("start recording")

while True:
    try:
        data = stream.read(chunk * 4,exception_on_overflow=False)
        ndarray = np.frombuffer(data,dtype = "int16")
        
        wave_1 = np.fft.fft(ndarray)
        wave_1 = np.abs(wave_1[:N//2])
        
        N = len(data)
        
        freqs = np.fft.fftfreq(N,1/samp_rate)[:N//2]
        
        change_number = 0
        
        number = None
        
        peak = np.argmax(wave_1)
        
        peak_freq = freqs[peak]
            
        
        
        if peak < 932.328 :
            if number != change_number:
                
                 name_1 = data_scale[data_scale['scale_list'] > 1.9 * peak_freq]
        
                 name_2 = name_1['scale_list'].min()
        
                 number = data_scale['scale_list'].tolist().index(name_2)
                 
                 print(scale_name[number])
            
                 change_number = number
            else:
                pass
        else:
            pass
        
        
        
    except KeyboardInterrupt:
        print("stop")
        break

print("finished")

stream.stop_stream()
stream.close()
audio.terminate()