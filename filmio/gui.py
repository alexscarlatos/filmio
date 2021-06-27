from tkinter import Tk, Frame, BOTH, Button, Text, Entry, END, NORMAL, DISABLED, filedialog
import os
from .audio_fixer import VID_FILE_EXTS, AUDIO_FILE_EXTS

def updateText(item, new_text):
    item.configure(state=NORMAL)
    item.delete(1.0, END)
    item.insert(END, new_text)
    item.configure(state=DISABLED)

class Window(Frame):
    def __init__(self, master, audioFixer):
        Frame.__init__(self, master)

        self.audioFixer = audioFixer

        # Let widget take up whole window
        self.pack(fill=BOTH, expand=1)

        self.items = []

        # Create interface
        self.createText(x=0, y=0, text="First select your source video/audio files, either by parent folder or pick the files individually")
        self.createButton(x=0, y=20, text="Source Folder", command=self.setSourceDir)
        self.createButton(x=100, y=20, text="Source Files", command=self.setSourceFiles)
        self.srcDisplay = self.createText(x=0, y=40, text=f"Source: {os.path.realpath(audioFixer.source_dir)}")

        self.createText(x=0, y=80, text="Select the folder where the resulting files should be placed")
        self.createButton(x=0, y=100, text="Output Folder", command=self.setOutputDir)
        self.outputDisplay = self.createText(x=0, y=120, text=f"Output location: {os.path.realpath(audioFixer.out_dir)}")

        self.gainOverride = Entry(self, width=8)
        self.gainOverride.place(x=0, y=160)
        self.items.append(self.gainOverride)
        self.createText(x=90, y=160, text="Select a gain multiplier; if not set, will be calculated to maximize volume")

        self.createText(x=0, y=200, text="Choose one of the following options:")
        self.createButton(x=0, y=220, text="Calculate Gain", command=self.run(audioFixer.gain))
        self.createButton(x=0, y=245, text="Louden Source Audio", command=self.run(audioFixer.loudenAudio))
        self.createButton(x=0, y=270, text="Extract Audio from Video", command=self.run(audioFixer.extractAudioFromVideo))
        self.createButton(x=0, y=295, text="Calculate Video/Source Audio Matches", command=self.run(audioFixer.matchVideoToAudio))
        self.createButton(x=0, y=320, text="Patch Source Audio onto Videos", command=self.run(audioFixer.patch))

    def createText(self, x, y, text):
        item = Text(self, height=1, width=100)
        item.place(x=x, y=y)
        item.insert(END, text)
        item.configure(state=DISABLED)
        self.items.append(item)
        return item

    def createButton(self, x, y, **options):
        item = Button(self, **options)
        item.place(x=x, y=y)
        self.items.append(item)
        return item

    def setSourceDir(self):
        src_dir = filedialog.askdirectory(initialdir=os.path.dirname(os.path.realpath(__file__)))
        if src_dir:
            self.audioFixer.setSourceDir(src_dir)
            updateText(self.srcDisplay, f"Source: {src_dir}")

    def setSourceFiles(self):
        files = filedialog.askopenfilenames(
            initialdir=os.path.dirname(os.path.realpath(__file__)),
            filetypes=[(file_type, file_type) for file_type in VID_FILE_EXTS + AUDIO_FILE_EXTS]
        )
        if files:
            files = list(files)
            self.audioFixer.overrideSrcAudioFiles(files)
            self.audioFixer.overrideSrcVideoFiles(files)
            updateText(self.srcDisplay, f"Source: {len(files)} files selected")

    def setOutputDir(self):
        out_dir = filedialog.askdirectory(initialdir=os.path.dirname(os.path.realpath(__file__)))
        if out_dir:
            self.audioFixer.setOutputDir(out_dir)
            updateText(self.outputDisplay, f"Output location: {out_dir}")

    def destroyEverything(self):
        for item in self.items:
            item.destroy()

    def run(self, execute):
        def execute_job():
            # Set gain override if provided
            try:
                gain_override = self.gainOverride.get()
                if gain_override:
                    self.audioFixer.overrideGain(float(gain_override))
            except ValueError as exc:
                print(exc)

            execute()

            self.destroyEverything()
            self.createText(x=0, y=0, text="Done!")
            self.createText(x=0, y=20, text="Examine console output for results")

        return execute_job

def create_gui(audioFixer):
    root = Tk()
    Window(root, audioFixer)
    root.wm_title("filmio")
    root.geometry("800x400")
    root.mainloop()
