import argparse
from os import path
from audio_fixer import AudioFixer
from audio_util import PRAAT_PATH

def check_dependencies():
    res = True

    # Check PRAAT
    if not path.isfile(PRAAT_PATH):
        res = False
        print('Could not find Praat software in {} (needed for matching audio files). Can be downloaded from http://www.fon.hum.uva.nl/praat/.'.format(PRAAT_PATH))

    # Note: dependent on pip packages numpy and scipy

    return res

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
    parser.add_argument('-o', '--out_dir', default='./Fixed',
        help='Directory to place output files. Default is subdir of the current directory "./Fixed"')

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
        help='Perform operations only on the provided files, rather than searching the source directory.')

    args = parser.parse_args()

    # Create worker class
    audioFixer = AudioFixer(args.src_dir, args.out_dir, args.verbose)

    # Set overrides
    if args.gain is not None:
        audioFixer.overrideGain(args.gain)
    if args.files is not None:
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
