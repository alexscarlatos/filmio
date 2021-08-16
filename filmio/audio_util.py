from os import path
from collections import namedtuple
from functools import partial
from subprocess import Popen, PIPE
from cachetools import cached
from wave import Error as WavError
import numpy as np
from scipy.io import wavfile
import wavio
import parselmouth

FLOAT_SAMPWIDTH = -1

#  the start and end time relative to the audio file start time, in seconds,
#    that would correspond to the true start and end time of a video file
#  a score that is higher with a better match (should be a percentage for comparison purposes)
MatchTuple = namedtuple('MatchTuple', ['start_time', 'end_time', 'score'])

WavMetaData = namedtuple('WavMetaData', ['length', 'rate'])

def dtype_to_sampwidth(dtype):
    if str(dtype).startswith('float'):
        return FLOAT_SAMPWIDTH
    if dtype == np.int8:
        return 1
    if dtype == np.int16:
        return 2
    if dtype == np.int32:
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

@cached(cache={})
def get_wav_metadata(audio_file):
    wav_data = read_wav_file(audio_file)
    if not wav_data:
        return None
    return WavMetaData(len(wav_data.data) / float(wav_data.rate), wav_data.rate)

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
    elif 1 <= sampwidth <= 4:
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
def extract_audio(video_file, output_audio_file, output_samp_freq):
    cmd = [
        'ffmpeg',
        '-i', video_file,
        '-map', '0:a', # Select audio stream from first input
        '-acodec', 'pcm_s16le', # Encode output audio as default wav format (signed 16 bit little endian)
        '-ar', output_samp_freq, # Set output sampling frequency
        '-y', # Don't ask for confirmation
        output_audio_file
    ]
    proc = Popen(cmd, stdout=PIPE, stderr=PIPE)
    _, err = proc.communicate()
    if proc.returncode != 0:
        print(err)
    return proc.returncode == 0

# Match the separate audio with the audio from the video
# Return MatchTuple
def match(ext_audio_file, video_audio_file):
    # Call Praat to do the matching
    praat_path = path.join(path.dirname(__file__), 'cross_correlate.praat')
    out_str = parselmouth.praat.run_file(praat_path, video_audio_file, ext_audio_file, capture_output=True)[1]

    # Get offset and score from process output
    try:
        parts = out_str.split(' ')
        offset = float(parts[0])
        score = float(parts[1])
    except Exception as e:
        print('Error parsing Praat output:', e)
        return None

    vid_audio_len = get_wav_metadata(video_audio_file).length

    start_time = offset
    end_time = start_time + vid_audio_len

    # Scoring heuristic - if a large part of the video is left silent, it is likely not matched correctly
    ext_audio_len = get_wav_metadata(ext_audio_file).length
    silence_time = max(-1 * start_time, 0) + max(end_time - ext_audio_len, 0)
    silence_ratio = float(silence_time) / vid_audio_len

    return MatchTuple(start_time, end_time, score * (1 - silence_ratio))

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
    cmd = [
        'ffmpeg',
        '-i', video_file,
        '-i', audio_file,
        '-map', '0:v', # Take video stream from first input
        '-map_metadata', '0', # Take metadata from first input
        '-movflags', 'use_metadata_tags', # Keep .mov metadata
        '-map', '1:a', # Take audio stream from second input
        '-vcodec', 'copy', # Copy the video codec from the source for the output
        # Use default audio codec instead of copying to avoid error
        '-shortest', # The output length is the shortest of the video/audio streams
        '-y', # Don't ask for confirmation
        output_video_file
    ]
    proc = Popen(cmd, stdout=PIPE, stderr=PIPE)
    _, err = proc.communicate()
    if proc.returncode != 0:
        print(err)
    return proc.returncode == 0
