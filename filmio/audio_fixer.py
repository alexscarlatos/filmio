from os import listdir, path, makedirs
from .audio_util import get_max_gain, louder, extract_audio, match, trim, attach, MatchTuple

AUDIO_FILE_EXTS = ['.wav']
VID_FILE_EXTS = ['.mp4', '.mov']

def get_all_files_of_type_in_list(file_list, ext_list):
    return [f for f in file_list if any(f.lower().endswith(ext.lower()) for ext in ext_list)]

def get_all_files_of_type_in_dir(cur_dir, ext_list):
    file_list = (path.join(cur_dir, f) for f in listdir(cur_dir) if path.isfile(path.join(cur_dir, f)))
    return get_all_files_of_type_in_list(file_list, ext_list)

def get_out_file_path(input_file, out_dir, suffix='', new_type=None):
    input_file_parts = path.basename(input_file).rsplit('.', 1)
    output_filename = "{}{}.{}".format(input_file_parts[0], suffix, new_type or input_file_parts[1])
    return "{}/{}".format(out_dir, output_filename)

# Encapsulates all core functionality of the application
# Tried to make it only do things when it has to, so any piece can be used independently
class AudioFixer:
    def __init__(self, verbose):
        self.verbose = verbose
        self.source_dir = None
        self.out_dir = None
        self._src_audio_files = None
        self._new_audio_files = None
        self._video_files = None
        self._video_audio_extracted = False
        self._gain = None

        # List of tuples (audio_file, video_file, MatchTuple)
        self._matches = None

        # List of tuples (audio_file, video_file)
        self._matches_trimmed = None

    def setSourceDir(self, source_dir):
        self.source_dir = source_dir

    def setOutputDir(self, out_dir):
        makedirs(out_dir, exist_ok=True) # Create out_dir if it doesn't already exist
        self.out_dir = out_dir

    def overrideSrcAudioFiles(self, audio_files):
        '''
        Set the list of source audio files to use rather than calculate it
        '''
        self._src_audio_files = get_all_files_of_type_in_list(audio_files, AUDIO_FILE_EXTS)

    def overrideSrcVideoFiles(self, video_files):
        '''
        Set the list of source video files to use rather than calculate it
        '''
        self._video_files = [{'video': f} for f in get_all_files_of_type_in_list(video_files, VID_FILE_EXTS)]

    def overrideGain(self, gain):
        '''
        Set the gain to use rather than calculate it
        '''
        self._gain = gain

    def srcAudioFiles(self):
        '''
        If the source audio file list is already set, return it
        Otherwise, gather file list from source directory and return
        '''
        if self._src_audio_files is not None:
            return self._src_audio_files

        print("Gathering audio files...")
        self._src_audio_files = get_all_files_of_type_in_dir(self.source_dir, AUDIO_FILE_EXTS)
        return self._src_audio_files

    def newAudioFiles(self):
        '''
        If new audio file list is already set, return it
        Otherwise, copy and louden the source audio files and return the new list
        '''
        if self._new_audio_files is not None:
            return self._new_audio_files

        self.loudenAudio()
        return self._new_audio_files

    def videoFiles(self):
        '''
        If video file list is already set, return it
        Otherwise, gather files from source directory and return
        '''
        if self._video_files is not None:
            return self._video_files

        print("Gathering video files...")
        self._video_files = [{'video': f} for f in get_all_files_of_type_in_dir(self.source_dir, VID_FILE_EXTS)]
        return self._video_files

    def gain(self):
        '''
        If gain is already set, return it
        Otherwise, calculate gain from srcAudioFiles and return
        '''
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
        '''
        Sets newAudioFiles
        Creates a copy of each file in srcAudioFiles and applies gain
        If gain == 1 then skips copying and just assigns newAudioFiles to srcAudioFiles
        '''
        if self.gain() == 1:
            print("Gain is 1... no loudening needed")
            self._new_audio_files = self.srcAudioFiles()
            return

        print("Scaling volume of audio files by {}...".format(self.gain()))

        self._new_audio_files = []
        for audio_file in self.srcAudioFiles():
            if self.verbose:
                print("\t{}".format(audio_file))
            new_audio_filepath = get_out_file_path(audio_file, self.out_dir, suffix='_louder')

            if louder(audio_file, new_audio_filepath, self.gain()):
                self._new_audio_files.append(new_audio_filepath)

        if self.verbose:
            print("Louder audio files:\n\t" + "\n\t".join(self._new_audio_files) + "\n")

    def extractAudioFromVideo(self):
        '''
        Sets the audio property on each of the videoFiles
        Extracts the audio track for each video file
        '''
        print("Extracting audio for each video file...")
        for video_tup in self.videoFiles():
            video_file = video_tup['video']
            video_audio_file = get_out_file_path(video_file, self.out_dir, new_type='wav')
            if self.verbose:
                print("\t{} -> {}".format(video_file, video_audio_file))

            if extract_audio(video_file, video_audio_file):
                video_tup['audio'] = video_audio_file
            else:
                print("Couldn't extract audio from " + video_file)

        print("Audio from video files extracted!")
        self._video_audio_extracted = True

    def matchVideoToAudio(self):
        '''
        Sets the matches array
        Find the best audio match for each video file, along with start/stop times and score
        '''
        if not self._video_audio_extracted:
            self.extractAudioFromVideo()
        self.newAudioFiles() # Pre-gain audio

        # Do matching, trimming and attaching for each video file
        print("Finding best match for video files...")
        self._matches = []
        for video_tup in self.videoFiles():
            video_file = video_tup['video']
            if 'audio' not in video_tup:
                print("\tSkipping {} - no audio extracted".format(video_file))
                continue

            if self.verbose:
                print(f'\n{video_file}')

            # Find best audio file to match video file
            video_audio_file = video_tup['audio']
            best_audio_file = ""
            best_match = MatchTuple(0, 0, 0)
            for audio_file in self.newAudioFiles():
                cur_match = match(audio_file, video_audio_file)
                if self.verbose:
                    print('\t', audio_file, cur_match)
                if cur_match and cur_match.score > best_match.score:
                    best_match = cur_match
                    best_audio_file = audio_file

            if best_audio_file:
                self._matches.append((best_audio_file, video_file, best_match))
                print("\t{0} matched with {1}, with {1} starting at {2} and ending at {3}"
                    .format(video_audio_file, best_audio_file, best_match.start_time, best_match.end_time))
            else:
                print("No match found for", video_audio_file)

        print("\nMatched videos to source audio files")

    def patch(self):
        '''
        First run the matching
        Then, for each video file, create a trimmed copy of the best matching audio and attach to a new copy of the video
        '''
        self.matchVideoToAudio()

        patched_video_files = []
        for audio_file, video_file, match_props in self._matches:
            if self.verbose:
                print("Trimming matched audio file", audio_file)

            # Trim audio file based on match output
            # Note that the same audio files may be trimmed multiple times, so they will be overwritten
            trimmed_audio_file = get_out_file_path(audio_file, self.out_dir, suffix='_trimmed')
            if not trim(audio_file, trimmed_audio_file, match_props.start_time, match_props.end_time):
                print(f"Couldn't trim {audio_file}")
                continue

            if self.verbose:
                print("Audio trimmed to {}".format(trimmed_audio_file))

            # Finally, attach the trimmed audio file to the video file
            if self.verbose:
                print(f"Attaching {trimmed_audio_file} to {video_file}")
            patched_video_file = get_out_file_path(video_file, self.out_dir, suffix='_patched')
            if attach(trimmed_audio_file, video_file, patched_video_file):
                patched_video_files.append(patched_video_file)

        print("\nCreated patched video files:\n", "\n".join(patched_video_files))
