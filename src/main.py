import mimetypes
import tkinter as tk
from tkinter import ttk
import os

import mpv


def is_video_file(path):
    """Check if a file is a video by its MIME type."""
    mime, _ = mimetypes.guess_type(path)
    return mime is not None and mime.startswith('video/')


class MediaApp:
    def __init__(self, root, dirs):
        self.root = root
        self.root.title('Media Folder Processing')
        self.root.geometry('840x480')

        # Use PanedWindow for resizable panes — it handles the sash
        # and resize cursor automatically.
        self.paned = ttk.PanedWindow(self.root, orient='horizontal')
        self.paned.pack(fill='both', expand=True)

        # Create the Treeview
        self.tree = ttk.Treeview(self.paned, columns=('path',), displaycolumns=())
        self.tree.heading('#0', text='Directory Structure', anchor='w')
        self.tree.column('#0', width=200)  # Initial tree width

        # Give the treeview a pane weight so it can shrink.
        # 0 = minimum size; 1 = fills remaining space.
        self.paned.add(self.tree, weight=0)

        # Create the video frame
        self.video_frame = tk.Frame(self.paned, bg='black', width=640, height=480)
        self.paned.add(self.video_frame, weight=1)

        # Track the current player so we can stop it before playing a new file
        self.current_player = None

        self.folder_icon = tk.PhotoImage(width=16, height=16)
        self.folder_icon.put(
            ('yellow',), to=(2, 4, 14, 14)
        )  # Simple yellow box for folders

        self.file_icon = tk.PhotoImage(width=16, height=16)
        self.file_icon.put(('white',), to=(4, 2, 12, 14))  # Simple white box for files

        # Bind the expansion event to our lazy loader function
        self.tree.bind('<<TreeviewOpen>>', self.on_expand)

        # Bind double-click on tree items to play videos
        self.tree.bind('<Double-1>', self.on_file_select)

        # Load initial root directory (Change this path to test different folders)
        for d in dirs:
            root_path = os.path.abspath(d)  # Defaults to system root (e.g., C:\ or /)
            self.insert_node('', d, os.path.basename(root_path))

    def insert_node(self, parent, path, text):
        """Inserts a node into the tree. If it's a folder, adds a dummy child."""
        is_dir = os.path.isdir(path)
        icon = self.folder_icon if is_dir else self.file_icon

        # Insert the item
        node = self.tree.insert(parent, 'end', text=text, image=icon, values=(path,))

        # If it's a directory, add a dummy child so the UI displays the expand arrow
        if is_dir:
            try:
                # Check if directory is empty; if not, add placeholder
                if os.listdir(path):
                    self.tree.insert(node, 'end', text='loading...')
            except PermissionError:
                # Handle folders we don't have permission to read
                pass

    def on_expand(self, event):
        """Triggered when a user clicks the expand arrow."""
        node = self.tree.focus()
        path = self.tree.item(node, 'values')[0]

        # Get all immediate children of the expanded node
        children = self.tree.get_children(node)

        # If the first child is our "loading..." placeholder, perform the dynamic load
        if children and self.tree.item(children[0], 'text') == 'loading...':
            # Delete the placeholder
            self.tree.delete(children[0])

            try:
                # Loop through the actual directory contents and insert them
                for item in sorted(os.listdir(path), key=lambda s: s.lower()):
                    full_path = os.path.join(path, item)
                    if is_video_file(full_path) or os.path.isdir(full_path):
                        self.insert_node(node, full_path, item)
            except PermissionError:
                # Insert a visual cue if access is denied
                self.tree.insert(node, 'end', text='[Access Denied]', values=('',))

    def on_file_select(self, event):
        """Double-click handler: play video files in the video frame."""
        node = self.tree.focus()
        if not node:
            return
        path = self.tree.item(node, 'values')[0]
        if path and os.path.isfile(path) and is_video_file(path):
            self.play_video(path)

    def play_video(self, video_path):
        """Load and play a video file embedded in the video_frame."""
        # Stop any currently playing file
        if self.current_player is not None:
            self.current_player.terminate()
            self.current_player = None

        self.video_frame.pack_propagate(False)
        self.root.update()  # Ensure the widget has been realized

        player = mpv.MPV(wid=str(self.video_frame.winfo_id()))

        # Media controls via keyboard
        def toggle_pause(ev):
            """Pause/resume playback with spacebar."""
            player.pause = not player.pause

        def seek_forward(ev):
            """Skip forward 5 seconds with right arrow."""
            try:
                player.seek(5, reference='relative')
            except SystemError:
                pass  # seek past end of file

        def seek_backward(ev):
            """Skip backward 5 seconds with left arrow."""
            try:
                player.seek(-5, reference='relative')
            except SystemError:
                pass  # seek past beginning of file

        # Bind media keys on video frame (not root, so they don't collide)
        self.video_frame.bind('<space>', toggle_pause)

        # Focus the video frame so it receives key events
        self.video_frame.focus_set()

        # Load and play the video
        player.play(video_path)
        self.current_player = player


if __name__ == '__main__':
    import sys

    root = tk.Tk()
    MediaApp(root, sys.argv[1:])
    root.mainloop()
