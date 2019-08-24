from os import listdir, path
from audio_util import get_max_gain, louder, extract_audio, match, trim, MatchTuple, PRAAT_PATH
from shutil import copyfile

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
