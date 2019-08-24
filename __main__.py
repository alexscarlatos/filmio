from os import listdir, path
import argparse
from audio_util import get_max_gain, louder, extract_audio, match, trim, MatchTuple, PRAAT_PATH
from shutil import copyfile

fixed_dir = "./Fixed"

def check_dependencies():
    res = True

    # Check PRAAT
    if not path.isfile(PRAAT_PATH):
        res = False
        print('Could not find Praat software in {} (needed for matching audio files). Can be downloaded from http://www.fon.hum.uva.nl/praat/.'.format(PRAAT_PATH))

    # Note: dependent on pip packages numpy and scipy

    return res

def get_all_files_of_type(cur_dir, ext):
    return [path.join(cur_dir, f) for f in listdir(cur_dir) if path.isfile(path.join(cur_dir, f)) and f.lower().endswith(ext.lower())]

def get_out_file_path(input_file, out_dir, suffix='', new_type=None):
    input_file_parts = input_file.rsplit('.', 1)
    output_filename = "{}{}.{}".format(input_file_parts[0], suffix, new_type or input_file_parts[1])
    return "{}/{}".format(out_dir, output_filename)

# Encapsulates all core functionality of the application
# Tried to make it only do things when it has to, so any piece can be used independently
class AudioFixer:
    def __init__(self, source_dir, out_dir, verbose):
        self.source_dir = source_dir
        # TODO: if out_dir doesn't exist, create it (if needed)
        self.out_dir = out_dir
        self.verbose = verbose
        self._src_audio_files = None
        self._new_audio_files = None
        self._video_files = None
        self._video_audio_extracted = False
        self._gain = None
        
    def overrideSrcAudioFiles(self, audio_files):
        if type(audio_files) is list:
            self._src_audio_files = audio_files

    # TODO: is this function necessary?
    def overrideNewAudioFiles(self, audio_files):
        if type(audio_files) is list:
            self._new_audio_files = audio_files

    def overrideSrcVideoFiles(self, video_files):
        if type(video_files) is list:
            self._video_files = [{'video': f for f in video_files}]

    def overrideGain(self, gain):
        self._gain = gain

    def srcAudioFiles(self):
        if self._src_audio_files is not None:
            return self._src_audio_files

        print("Gathering audio files...")
        self._src_audio_files = get_all_files_of_type(self.source_dir, '.wav')
        return self._src_audio_files

    def newAudioFiles(self):
        if self._new_audio_files is not None:
            return self._new_audio_files

        self.loudenAudio()
        return self._new_audio_files

    def videoFiles(self):
        if self._video_files is not None:
            return self._video_files

        print("Gathering video files...")
        self._video_files = [{'video': f} for f in get_all_files_of_type(self.source_dir, '.mp4')]
        return self._video_files

    def gain(self):
        if self._gain is not None:
            return self._gain

        print("Analyzing audio files for best possible gain increase...")
        best_gain = None
        for audio_file in self.srcAudioFiles():
            max_gain = get_max_gain(audio_file, self.verbose)
            if max_gain:
                best_gain = max_gain if best_gain is None else min(max_gain, best_gain)

        print("Optimal gain factor: {}".format(best_gain))
        self._gain = best_gain
        return self._gain

    def loudenAudio(self):
        if self.gain() == 1:
            print("Gain is 1... will copy audio files but not adjust volume")
        else:
            print("Scaling volume of audio files by {}...".format(self.gain()))
        
        self._new_audio_files = []
        for audio_file in self.srcAudioFiles():
            if self.verbose:
                print("\t{}".format(audio_file))
            new_audio_filepath = get_out_file_path(audio_file, self.out_dir, suffix='_louder')

            if self.gain() == 1:
                copyfile(audio_file, new_audio_filepath)
                self._new_audio_files.append(new_audio_filepath)
            else:
                if louder(audio_file, new_audio_filepath, self.gain()):
                    self._new_audio_files.append(new_audio_filepath)

        if self.verbose:
            print("Louder audio files:\n\t" + "\n\t".join(self._new_audio_files) + "\n")

    def extractAudioFromVideo(self):
        print("Extracting audio for each video file...")
        for video_tup in self.videoFiles():
            video_file = video_tup['video']
            if self.verbose:
                print("\t{}".format(video_file))
            
            video_audio_file = get_out_file_path(video_file, self.out_dir, new_type='wav')
            if extract_audio(video_file, video_audio_file, self.verbose):
                video_tup['audio'] = video_audio_file
            else:
                print("Couldn't extract audio from " + video_file)
        
        print("Audio from video files extracted!")
        self._video_audio_extracted = True

    def matchVideoToAudio(self):
        if not self._video_audio_extracted:
            self.extractAudioFromVideo()
        
        # Do matching, trimming and attaching for each video file
        print("Finding best match for video files...")
        patched_video_files = []
        for video_tup in self.videoFiles():
            video_file = video_tup['video']
            if 'audio' not in video_tup:
                print("\tSkipping {} - no audio extracted".format(video_file))
                continue
            elif self.verbose:
                print("\t{}".format(video_file))

            # Find best audio file to match video file
            video_audio_file = video_tup['audio']
            best_audio_file = ""
            best_match = MatchTuple(0, 0, 0)
            for audio_file in self.newAudioFiles():
                cur_match = match(audio_file, video_audio_file)
                if cur_match.score > best_match.score:
                    best_match = cur_match
                    best_audio_file = audio_file

            # Calculate the necessary times for stitching
            # TODO: convert samples to seconds
            start_time = best_match.start_sample
            end_time = best_match.end_sample
            duration = end_time - start_time
            if self.verbose:
                print("\t{0} matched with {1}, with {1} starting at {2} and ending at {3}"
                    .format(video_audio_file, best_audio_file, start_time, end_time))

            # Trim audio file based on match output
            trimmed_audio_file = get_out_file_path(best_audio_file, out_dir, suffix='_trimmed')
            if not trim(best_audio_file, trimmed_audio_file, start_time, end_time):
                print("\tCouldn't trim {}".format(best_audio_file))
                continue
            elif self.verbose:
                print("\tAudio trimmed to {}".format(trimmed_audio_file))

            # Finally, attach the trimmed audio file to the video file
            patched_video_file = get_out_file_path(video_file, out_dir, suffix='_patched')
            if attach(best_audio_file, video_file, patched_video_file):
                patched_video_files.append(patched_video_file)
            
        print("Created patched video files:" + "\n".join(patched_video_files))

if __name__ == "__main__":
    # Check any dependencies required for operations
    # TODO: maybe don't do this here?
    if not check_dependencies():
        exit(1)

    parser = argparse.ArgumentParser(description='A super rad utility to help you with audio for your films')
    parser.add_argument('-v', '--verbose', action='store_true',
        help='Print extra information while executing.')
    parser.add_argument('-d', '--src_dir', default='.',
        help='Directory to search for source files. Default is the current directory.')
    parser.add_argument('-o', '--out_dir', default='.',
        help='Directory to place output files. Default is the current directory.')

    # TODO: might want to combine these into one argument with a choice
    parser.add_argument('-c', '--calc', action='store_true',
        help='Perform optimal gain calculation on source audio files.')
    parser.add_argument('-l', '--louder', action='store_true',
        help='Perform gain adjustment on source audio files. Calculates optimal gain if not provided.')
    parser.add_argument('-e', '--extract', action='store_true',
        help='Extract audio from source video files.')
    parser.add_argument('-m', '--match', action='store_true',
        help='Perform full matching of audio and video files. Then combine results into new video files.')

    parser.add_argument('-g', '--gain', type=float,
        help='Provide a gain to use on the audio files rather than calculating one. If 1 is given, will not attempt to modify audio file volume.')
    parser.add_argument('-f', '--files', nargs='*',
        help='Perform operations only on the provided files, rather than searching the source directory. Not available for audio/video matching.')

    args = parser.parse_args()
    
    # Create worker class
    audioFixer = AudioFixer(args.src_dir, args.out_dir, args.verbose)

    # Set overrides (if not provided, will be None and this will be a no-op)
    audioFixer.overrideGain(args.gain)
    audioFixer.overrideSrcAudioFiles(args.files)
    audioFixer.overrideSrcVideoFiles(args.files)

    # Decide on action based on provided arguments
    if args.calc:
        audioFixer.gain()
    if args.louder:
        audioFixer.loudenAudio()
    if args.extract:
        audioFixer.extractAudioFromVideo()
    if args.match:
        audioFixer.matchVideoToAudio()

    print("All done!")
    exit(0)

    # ---- below this line being replaced -----
    if verbose:
        print("Will write temporary files to {}".format(out_dir))

    # Get all audio files in the working directory
    print("Gathering audio files...")
    src_audio_files = get_all_files_of_type('.', '.wav')
    new_audio_files = []

    if verbose:
        print("Audio files to process:\n\t" + "\n\t".join(src_audio_files) + "\n")

    # First find the highest gain that can be applied to all audio files
    if not gain_override:
        print("Analyzing audio files for best possible gain increase...")
        best_gain = None
        for audio_file in src_audio_files:
            if verbose:
                print("\t{}".format(audio_file))
            max_gain = get_max_gain(audio_file, verbose)
            if max_gain:
                best_gain = max_gain if best_gain is None else min(max_gain, best_gain)
    else:
        best_gain = gain_override

    print("Optimal gain factor: {}".format(best_gain))
    if gain_calc_only:
        exit(0)

    # Apply gain to audio files
    print("Scaling volume of audio files...")
    for audio_file in src_audio_files:
        if verbose:
            print("\t{}".format(audio_file))
        new_audio_filepath = get_out_file_path(audio_file, out_dir, suffix='_louder')
        if louder(audio_file, new_audio_filepath, best_gain):
            new_audio_files.append(new_audio_filepath)

    if verbose:
        print("Louder audio files:\n\t" + "\n\t".join(new_audio_files) + "\n")

    # Get all video files in the working directory
    print("Gathering video files...")
    video_files = [{'video': f} for f in get_all_files_of_type('.', '.MP4')]
    patched_video_files = []

    if verbose:
        print("Video files to process:\n\t" + "\n\t".join(video_files) + "\n")

    # Extract audio component from all video files
    print("Extracting audio for each video file...")
    for video_tup in video_files:
        video_file = video_tup['video']
        if verbose:
            print("\t{}".format(video_file))
        video_audio_file = get_out_file_path(video_file, out_dir, new_type='wav')
        if extract_audio(video_file, video_audio_file):
            video_tup['audio'] = video_audio_file
        else:
            print("Couldn't extract audio from " + video_file)
    
    # Do matching, trimming and attaching for each video file
    print("Finding best match for video files...")
    for video_tup in video_files:
        video_file = video_tup['video']
        if 'audio' not in video_tup:
            print("\tSkipping {} - no audio extracted".format(video_file))
            continue
        elif verbose:
            print("\t{}".format(video_file))

        # Find best audio file to match video file
        video_audio_file = video_tup['audio']
        best_audio_file = ""
        best_match = MatchTuple(0, 0, 0)
        for audio_file in new_audio_files:
            cur_match = match(audio_file, video_audio_file)
            if cur_match.score > best_match.score:
                best_match = cur_match
                best_audio_file = audio_file

        # TODO: convert samples to seconds
        start_time = best_match.start_sample
        end_time = best_match.end_sample
        duration = end_time - start_time
        if verbose:
            print("\t{0} matched with {1}, with {1} starting at {2} and ending at {3}"
                .format(video_audio_file, best_audio_file, start_time, end_time))

        # Trim audio file based on match output
        trimmed_audio_file = get_out_file_path(best_audio_file, out_dir, suffix='_trimmed')
        if not trim(best_audio_file, trimmed_audio_file, start_time, end_time):
            continue

        # Finally, attach the trimmed audio file to the video file
        patched_video_file = get_out_file_path(video_file, out_dir, suffix='_patched')
        if attach(best_audio_file, video_file, patched_video_file):
            patched_video_files.append(patched_video_file)
        
    print("Created patched video files:" + "\n".join(patched_video_files))
    print("All done!")
