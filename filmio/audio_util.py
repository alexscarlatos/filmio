import numpy as np
from scipy.io import wavfile
from wave import Error as WavError
import wavio
from collections import namedtuple
import subprocess
from functools import partial

PRAAT_PATH = '/Applications/Praat.app/Contents/MacOS/Praat'

FLOAT_SAMPWIDTH = -1

#  the start and end time relative to the audio file start time, in seconds,
#    that would correspond to the true start and end time of a video file
#  a score that is higher with a better match (should be a percentage for comparison purposes)
MatchTuple = namedtuple('MatchTuple', ['start_time', 'end_time', 'score'])

def dtype_to_sampwidth(dtype):
    if str(dtype).startswith('float'):
        return FLOAT_SAMPWIDTH
    elif dtype == np.int8:
        return 1
    elif dtype == np.int16:
        return 2
    elif dtype == np.int32:
        return 4
    return 0

# Given a wav file, return a wavio.Wav object
def read_wav_file(wav_file):
    # Try to read file with wavio
    try:
        return wavio.read(wav_file)
    # May have failed due to wav being floating-point encoded
    except WavError as e:
        pass
    except Exception as e:
        print("\tERR: Couldn't read data: {}".format(e))
        return None

    # Use scipy.io.wavfile as fallback
    try:
        rate, data = wavfile.read(wav_file)
        return wavio.Wav(data, rate, dtype_to_sampwidth(data.dtype))
    except Exception as e:
        print("\tERR: Couldn't read data: {}".format(e))
        return None

# Get the maximum amount that a audio file's samples may be scaled by
# Such that the result will not peak
def get_max_gain(audio_file, verbose=True):
    if verbose:
        print(audio_file)

    wav_data = read_wav_file(audio_file)
    if not wav_data:
        return None
    sampwidth = wav_data.sampwidth

    if verbose:
        print(f"\t{wav_data}")

    # Get data format to find the maximum possible gain
    if sampwidth == FLOAT_SAMPWIDTH:
        max_value = 1
    elif sampwidth >= 1 and sampwidth <= 4:
        bits_per_sample = 8 * sampwidth
        max_value = 2 ** bits_per_sample
    else:
        print(f"\tERR: Unknown data format for {wav_data} from {audio_file}")
        return None

    # Get loudest sample in the file
    max_sample = np.amax(wav_data.data)

    # Get maximum amount samples can be multiplied by
    max_gain = max_value / max_sample

    if verbose:
        print("\tmax possible sample value: {}".format(max_value))
        print("\tmax sample found: {}".format(max_sample))
        print("\tmax possible gain increase: {}".format(max_gain))

    return max_gain

def modify_wav_file(input_file, output_file, data_processor):
    # Get source samples
    wav_data = read_wav_file(input_file)
    if not wav_data:
        return False
    data = wav_data.data

    # Process the samples
    data = data_processor(data, wav_data.rate)

    # Make sure dtype doesn't change since this can happen with certain operations
    dtype = str(data.dtype)
    data = np.asarray(data, dtype)

    # Write the modified sample array to the new file
    try:
        sampwidth = 4 if wav_data.sampwidth == FLOAT_SAMPWIDTH else wav_data.sampwidth
        wavio.write(output_file, data, wav_data.rate, sampwidth=sampwidth)
    except Exception as e:
        print("\tERR: Couldn't write data: {}".format(e))
        return False

    return True

# Scale the audio file's samples by the given amount
# Write out new file to desired location
# Returns if successful
def louder(audio_file, new_audio_file, scale):
    return modify_wav_file(audio_file, new_audio_file, lambda data, rate: data * scale)

# Extract the audio of the given video file and place in output_audio_file
# Return True for success and False for failure
def extract_audio(video_file, output_audio_file, verbose=True):
    # TODO: divert stdout unless verbose
    # TODO: force overwrite of files
    # TODO: should we do 32 bit instead?
    cmd = ['ffmpeg', '-i', video_file, '-map', '0:1', '-acodec', 'pcm_s16le', '-ar', '44100', '-ac', '2', '-y', output_audio_file]
    rc = subprocess.call(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return rc == 0

def get_audio_len(audio_file):
    wav_data = read_wav_file(audio_file)
    if not wav_data:
        return None

    return len(wav_data.data) / float(wav_data.rate)

# Match the separate audio with the audio from the video
# Return MatchTuple
def match(ext_audio_file, video_audio_file):
    # Call Praat to do the matching
    # TODO: 30 second limit should be configurable
    # Note that file order matters here
    cmd = [PRAAT_PATH, 'cross_correlate.praat', video_audio_file, ext_audio_file]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    if err:
        print('Error from Praat:', err)
        return None

    out_str = out.decode('utf-8').strip()

    # Get offset and score from process output
    try:
        parts = out_str.split(' ')
        offset = float(parts[0])
        score = float(parts[1])
    except Exception as e:
        print('Error parsing Praat output:', e)
        return None

    vid_audio_len = get_audio_len(video_audio_file)

    start_time = offset
    end_time = start_time + vid_audio_len

    return MatchTuple(start_time, end_time, score)

def apply_trim_to_data(start_time, end_time, data, rate):
    data_len = len(data)
    data_shape = list(data.shape)

    # TODO: can optimize, proabably only have to reassign data once

    # Convert seconds to samples
    start_sample = int(round(start_time * rate))
    end_sample = int(round(end_time * rate))

    # Add silence or trim beginning of clip
    if start_sample < 0:
        data_shape[0] = start_sample * -1
        starting_silence = np.zeros(tuple(data_shape), data.dtype)
        data = np.concatenate((starting_silence, data), axis=0)
    else:
        data = data[start_sample:]

    # Add silence or trim end of clip
    if end_sample > data_len:
        data_shape[0] = end_sample - data_len
        ending_silence = np.zeros(tuple(data_shape), data.dtype)
        data = np.concatenate((data, ending_silence), axis=0)
    else:
        data = data[:(end_sample - start_sample)]

    return data

# Output the audio file, trimmed at the start and end times
# Exported samples outside the original range will be silent
def trim(audio_file, output_audio_file, start_time, end_time):
    if start_time > end_time:
        print("start_time must be <= end_time")
        return None
    return modify_wav_file(audio_file, output_audio_file, partial(apply_trim_to_data, start_time, end_time))

# Attach the audio file to the video file and write to new file
def attach(audio_file, video_file, output_video_file):
    # TODO: verbosity
    cmd = [
        'ffmpeg',
        '-i', video_file,
        '-i', audio_file,
        '-map', '0:v',
        '-map', '1:a',
        '-vcodec', 'copy',
        '-shortest', '-y', output_video_file
    ]
    rc = subprocess.call(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return rc == 0
