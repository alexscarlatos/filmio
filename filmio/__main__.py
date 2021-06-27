import argparse
import sys
from .audio_fixer import AudioFixer
from .gui import create_gui

def process_cmd_line(audioFixer, args, parser):
    # Set overrides
    if args.gain is not None:
        audioFixer.overrideGain(args.gain)
    if args.files is not None:
        audioFixer.overrideSrcAudioFiles(args.files)
        audioFixer.overrideSrcVideoFiles(args.files)

    if not args.mode:
        parser.print_help()
        print("Please provide a mode!")
        sys.exit(1)

    # Decide on action based on provided arguments
    if args.mode == 'gain_calc':
        audioFixer.gain()
    elif args.mode == 'louden':
        audioFixer.loudenAudio()
    elif args.mode == 'extract_vid_audio':
        audioFixer.extractAudioFromVideo()
    elif args.mode == 'match':
        audioFixer.matchVideoToAudio()
    elif args.mode == 'patch':
        audioFixer.patch()

def main():
    parser = argparse.ArgumentParser(description='A super rad utility to help you with audio for your films')
    parser.add_argument('--gui', action='store_true', help='Use a GUI instead of command line to configure the run')

    parser.add_argument('-v', '--verbose', action='store_true',
        help='Print extra information while executing.')
    parser.add_argument('-d', '--src_dir', default='.',
        help='Directory to search for source files. Default is the current directory.')
    parser.add_argument('-o', '--out_dir', default='./Fixed',
        help='Directory to place output files. Default is subdir of the current directory "./Fixed"')

    parser.add_argument('-m', '--mode', choices=['gain_calc', 'louden', 'extract_vid_audio', 'match', 'patch'])

    parser.add_argument('-g', '--gain', type=float,
        help='Provide a gain to use on the audio files rather than calculating one. '
              'If 1 is given, will not attempt to modify audio file volume.')
    parser.add_argument('-f', '--files', nargs='*',
        help='Perform operations only on the provided files, rather than searching the source directory.')

    args = parser.parse_args()

    # Create worker class
    audioFixer = AudioFixer(args.verbose or args.gui)
    audioFixer.setSourceDir(args.src_dir)
    audioFixer.setOutputDir(args.out_dir)

    # Either create GUI or process cmd line args
    if args.gui:
        create_gui(audioFixer)
    else:
        process_cmd_line(audioFixer, args, parser)

    print("All done!")

if __name__ == "__main__":
    main()
