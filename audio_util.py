import os
import numpy as np
import struct
from scipy.io import wavfile
from shutil import copyfile
from collections import namedtuple
import subprocess

PRAAT_PATH = '/Applications/Praat.app/Contents/MacOS/Praat'

#  the start and end time relative to the audio file start time, in samples,
#    that would correspond to the true start and end time of a video file
#  a score that is higher with a better match (should be a percentage for comparison purposes)
MatchTuple = namedtuple('MatchTuple', ['start_sample', 'end_sample', 'score'])

# Get the maximum amount that a audio file's samples may be scaled by
# Such that the result will not peak
def get_max_gain(audio_file, verbose=True):
    try:
        # TODO: deal with 24-bit depth
        fs, data = wavfile.read(audio_file)
    except Exception as e:
        print("\tERR: Couldn't read data: {}".format(e))
        return None
    
    dtype = str(data.dtype)
    if verbose:
        print(audio_file)
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
        max_value = 2 ** (bps - 1)
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

# Scale the audio file's samples by the given amount
# Write out new file to desired location
# Returns if successful
def louder(audio_file, new_audio_file, scale):
    # Get source samples
    try:
        fs, data = wavfile.read(audio_file)
    except Exception as e:
        print("\tERR: Couldn't read data: {}".format(e))
        return False

    # Multiply each sample by scale
    data *= scale

    # Copy audio_file to new_audio_file
    copyfile(audio_file, new_audio_file)

    # Write the modified sample array to the new file
    try:
        wavfile.write(new_audio_file, fs, data)
    except Exception as e:
        print("\tERR: Couldn't write data: {}".format(e))
        return False

    return True

# Extract the audio of the given video file and place in output_audio_file
# Return True for success and False for failure
def extract_audio(video_file, output_audio_file, verbose=True):
    # TODO: divert stdout unless verbose
    # TODO: force overrite of files
    rc = subprocess.call(['ffmpeg', '-i', video_file, '-map', '0:1', '-acodec', 'pcm_s16le', '-ac', '2', output_audio_file])
    return rc == 0

# Match the separate audio with the audio from the video
# Return MatchTuple
def match(ext_audio_file, video_audio_file):
    # Try to find some external utility that does this

    # If not...

    # Get fft of both files

    # Calculate peaks of both files

    # NOTE: we should cache the peaks if we have already seen this file

    # Iterate over all positions,
    #  starting with the end of the video at the start of the audio
    #  and ending with the start of the video at the end of the audio

    # At each point, do exact match on peaks and keep track of highest match number and position of best match

    # To optimize, we can widen the fft time band
    # Or sqaush the peaks into larger buckets after generation
    pass

# Output the audio file, trimmed at the start and end sample times
# Exported samples outside the original range will be silent
# start_sample must be < end_sample
def trim(audio_file, output_audio_file, start_sample, end_sample):
    # TODO
    pass

# Attach the audio file to the video file and write to new file
def attach(audio_file, video_file, output_video_file):
    # TODO
    pass


if __name__ == "__main__":

    # Test get max gain and louder
    '''
    filename = 'AudioTest/FrozenOneSuperQuiet.wav'
    gain = get_max_gain(filename)
    new_audio_file = "AudioTest/FrozenOneSuperQuiet_louder.wav"
    louder(filename, new_audio_file, gain)
    get_max_gain(new_audio_file)
    '''

    # Test extract audio and match
    video_file = './Greg-Daddy/MVI_0194.MP4'
    video_audio_file = './Greg-Daddy/MVI_0194.wav'
    extract_audio(video_file, video_audio_file)
