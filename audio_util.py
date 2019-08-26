import os
import numpy as np
import struct
from scipy.io import wavfile
from shutil import copyfile
from collections import namedtuple
import subprocess
from functools import partial

PRAAT_PATH = '/Applications/Praat.app/Contents/MacOS/Praat'

#  the start and end time relative to the audio file start time, in seconds,
#    that would correspond to the true start and end time of a video file
#  a score that is higher with a better match (should be a percentage for comparison purposes)
MatchTuple = namedtuple('MatchTuple', ['start_time', 'end_time', 'score'])

def standardize_wav(audio_file, output_audio_file):
    cmd = ['ffmpeg', '-i', audio_file, '-acodec', 'pcm_s16le', '-ar', '44100', '-y', output_audio_file]
    rc = subprocess.call(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return rc == 0

# Get the maximum amount that a audio file's samples may be scaled by
# Such that the result will not peak
def get_max_gain(audio_file, verbose=True):
    if verbose:
        print(audio_file)

    try:
        # TODO: deal with 24-bit depth - our audio is in that format...
        fs, data = wavfile.read(audio_file)
    except Exception as e:
        print("\tERR: Couldn't read data: {}".format(e))
        return None

    dtype = str(data.dtype)
    if verbose:
        print("\tsample rate: {}".format(fs))
        print("\tnum samples: {}".format(len(data)))
        print("\tdata format: {}".format(dtype))

    # Get data format to find the maximum possible gain
    if dtype.startswith('float'):
        max_value = 1
    elif dtype.startswith('int'):
        bps = 0
        if dtype == 'int16':
            bps = 16
        elif dtype == 'int32':
            bps = 32
        max_value = 2 ** bps
    else:
        print("\tERR: Unknown data format {}, {}".format(dtype, audio_file))
        return None

    # Get loudest sample in the file
    max_sample = np.amax(data)
    
    # Get maximum amount samples can be multiplied by
    max_gain = max_value / max_sample
    
    if verbose:
        print("\tmax possible sample value: {}".format(max_value))
        print("\tmax sample found: {}".format(max_sample))
        print("\tmax possible gain increase: {}".format(max_gain))

    return max_gain

def modify_wav_file(input_file, output_file, data_processor):
    # Get source samples
    try:
        fs, data = wavfile.read(input_file)
    except Exception as e:
        print("\tERR: Couldn't read data: {}".format(e))
        return False

    # TODO: verbose
    dtype = str(data.dtype)
    if True:
        print("\tsample rate: {}".format(fs))
        print("\tnum samples: {}".format(len(data)))
        print("\tdata format: {}".format(dtype))

    # Process the samples
    data = data_processor(data, fs)

    # Make sure dtype doesn't change since this can happen with certain operations
    data = np.asarray(data, dtype)

    # Copy audio_file to new_audio_file
    # TODO: why do we need to copy before we assign the samples?
    copyfile(input_file, output_file)

    # Write the modified sample array to the new file
    try:
        wavfile.write(output_file, fs, data)
    except Exception as e:
        print("\tERR: Couldn't write data: {}".format(e))
        return False

    return True

# Scale the audio file's samples by the given amount
# Write out new file to desired location
# Returns if successful
def louder(audio_file, new_audio_file, scale):
    return modify_wav_file(audio_file, new_audio_file, lambda data, fs: data * scale)

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
    try:
        # TODO: deal with 24-bit depth - our audio is in that format...
        fs, data = wavfile.read(audio_file)
    except Exception as e:
        print("\tERR: Couldn't read data: {}".format(e))
        return None

    return len(data) / float(fs)

# Match the separate audio with the audio from the video
# Return MatchTuple
def match(ext_audio_file, video_audio_file):
    # Call Praat to do the matching
    # TODO: add verbosity
    # TODO: 30 second limit should be configurable
    # TODO: get Praat to output some kind of match score
    # Note that order matters here
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
        score = 100
        # score = float(parts[1])
    except Exception as e:
        print('Error parsing Praat output:', e)
        return None

    vid_audio_len = get_audio_len(video_audio_file)

    start_time = offset
    end_time = start_time + vid_audio_len

    print(start_time, end_time)

    return MatchTuple(start_time, end_time, score)

def apply_trim_to_data(start_time, end_time, data, fs):
    data_len = len(data)

    # TODO: can optimize, proabably only have to reassign data once

    # TODO: second arg to zeros should be from shape of data

    # Convert seconds to samples
    start_sample = int(round(start_time * fs))
    end_sample = int(round(end_time * fs))

    # Add silence or trim beginning of clip
    if start_sample < 0:
        starting_silence = np.zeros((start_sample * -1, 2), data.dtype)
        data = np.concatenate((starting_silence, data), axis=0)
    else:
        data = data[start_sample:]

    # Add silence or trim end of clip
    if end_sample > data_len:
        ending_silence = np.zeros((end_sample - data_len, 2), data.dtype)
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
