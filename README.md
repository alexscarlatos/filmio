# Effortless Video/Audio Syncing
If you're a filmmaker, videographer, or hobbyist who records their video and audio separately, then this is the tool for you!

This nifty utility will create a copy of each of your video files, where the audio is replaced with the separately recorded track at the correct time.
It does this by comparing the audio tracks of each video file with the external audio files, and will pick the best match for each.
The audio is trimmed, gained to its highest possible volume, and patched onto a new copy of the video.
It will be as if the recording was done on a single device!

## Usage
```
-h, --help          show this help message and exit
-v, --verbose       Print extra information while executing.
-d SRC_DIR, --src_dir SRC_DIR
                    Directory to search for source files. Default is the
                    current directory.
-o OUT_DIR, --out_dir OUT_DIR
                    Directory to place output files. Default is subdir of
                    the current directory "./Fixed"
-m {gain_calc,louden,extract_vid_audio,match,patch}, --mode {gain_calc,louden,extract_vid_audio,match,patch}
-g GAIN, --gain GAIN  Provide a gain to use on the audio files rather than
                    calculating one. If 1 is given, will not attempt to
                    modify audio file volume.
-f [FILES [FILES ...]], --files [FILES [FILES ...]]
                    Perform operations only on the provided files, rather
                    than searching the source directory.
```
### Modes Explained
- `gain_calc` - Calculate the maximum value that the volume of the source audio files can be multiplied by.
The scalar is chosen such that ALL source audio files can be multiplied by the scalar without peaking.
No files will be created by this option, but multiplying all source audio files by this scalar will ensure that none of the resulting files will peak.
- `louden` - Make a copy of each source audio file, where the volume is scaled by the maximum possible volume, unless -g is provided.
- `match` - Find the best matching audio files, with start/stop times, for each video file.
- `patch` - Create a copy of each video file, with the audio replaced with its best match after being optimally gained.

## References
Starting point for the implementation: http://www.dsg-bielefeld.de/dsg_wp/wp-content/uploads/2014/10/video_syncing_fun.pdf
- Credit to where I found the document, [The Bielefeld Dialogue Systems Group](http://www.dsg-bielefeld.de/dsg_wp/), David Schlangen

Praat: https://www.fon.hum.uva.nl/praat/
