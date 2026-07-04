import tkinter as tk
import mpv

def play_video(video_path):
    root = tk.Tk()
    root.title("MPV Video Player")

    # Create a container frame for the video
    video_frame = tk.Frame(root, bg="black", width=640, height=480)
    video_frame.pack(expand=True, fill="both")

    # Initialize mpv player, embedding it into the Tkinter widget's window ID
    # Note: The widget must be packed/configured before getting its window ID
    video_frame.pack_propagate(False)
    root.update() # Ensure the widget has been realized

    player = mpv.MPV(wid=str(video_frame.winfo_id()))

    # Load and play the video
    player.terminal = False  # Suppress mpv terminal output
    player.play(video_path)

    # Media controls via keyboard
    def toggle_pause(event):
        """Pause/resume playback with spacebar."""
        player.pause = not player.pause

    def seek_forward(event):
        """Skip forward 5 seconds with right arrow."""
        try:
            player.seek(5, reference="relative")
        except SystemError:
            pass  # seek past end of file

    def seek_backward(event):
        """Skip backward 5 seconds with left arrow."""
        try:
            player.seek(-5, reference="relative")
        except SystemError:
            pass  # seek past beginning of file

    root.bind("<space>", toggle_pause)
    root.bind("<Right>", seek_forward)
    root.bind("<Left>", seek_backward)

    root.mainloop()

# Usage
play_video("./samples/sample1.mkv")
