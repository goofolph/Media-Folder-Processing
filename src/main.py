import mimetypes
import platform
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

        # Bind right-click to show context menu
        self.tree.bind('<Button-3>', self.on_tree_context)

        # Create treeview context menu
        self.tree_menu = tk.Menu(self.tree, tearoff=0)
        self.tree_menu.add_command(label='Play', command=self._play_selected)
        self.tree_menu.add_separator()
        self.tree_menu.add_command(
            label='Open folder', command=self._open_selected_folder
        )
        self.tree_menu.add_separator()
        self.tree_menu.add_command(label='Copy path', command=self._copy_selected_path)

        # Create video frame context menu
        self.video_menu = tk.Menu(self.video_frame, tearoff=0)
        self.video_menu.add_command(label='Pause', command=self._toggle_pause_video)
        self.video_menu.add_separator()
        self.video_menu.add_command(label='Stop', command=self._stop_video)

        # Bind right-click on video frame to context menu
        self.video_frame.bind('<Button-3>', self._on_video_context)

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
        self.video_frame.focus()
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
        self.video_frame.focus_set()
        if not node:
            return
        path = self.tree.item(node, 'values')[0]
        if path and os.path.isfile(path) and is_video_file(path):
            self.play_video(path)

    def on_tree_context(self, event):
        """Right-click on treeview: determine item type and show appropriate menu."""
        node = self.tree.identify_row(event.y)
        if not node:
            return
        self.tree.selection_set(node)
        self.tree.focus(node)
        path = self.tree.item(node, 'values')[0]
        if path and os.path.isfile(path) and is_video_file(path):
            # Video file: show full menu
            self.tree_menu.tk_popup(event.x_root, event.y_root)
        elif os.path.isdir(path):
            # Directory: show folder menu without Play
            self.tree_menu.entryconfig('Play', state='disabled')
            self.tree_menu.tk_popup(event.x_root, event.y_root)
            self.tree_menu.entryconfig('Play', state='normal')
        else:
            self.tree_menu.tk_popup(event.x_root, event.y_root)

    def _selected_path(self):
        """Return the path of the currently selected tree item, or None."""
        selection = self.tree.selection()
        if not selection:
            return None
        item = self.tree.item(selection[0], 'values')[0]
        return item if item else None

    def _play_selected(self):
        """Play the selected video file."""
        path = self._selected_path()
        if path and os.path.isfile(path) and is_video_file(path):
            self.play_video(path)

    def _open_selected_folder(self):
        """Open the selected item's folder in the system file manager."""
        path = self._selected_path()
        if not path:
            return
        folder = os.path.dirname(path) if os.path.isfile(path) else path
        if platform.system() == 'Windows':
            os.startfile(folder)  # noqa: S606
        elif platform.system() == 'Darwin':
            os.system(f'open "{folder}"')  # noqa: S602
        else:
            os.system(f'xdg-open "{folder}"')  # noqa: S602

    def _copy_selected_path(self):
        """Copy the selected item's path to the clipboard."""
        path = self._selected_path()
        if path:
            self.root.clipboard_clear()
            self.root.clipboard_append(path)
            self.root.update()

    def _toggle_pause_video(self):
        """Pause/resume playback via context menu."""
        if self.current_player is not None:
            self.current_player.pause = not self.current_player.pause

    def _on_video_context(self, event):
        """Show video playback context menu."""
        self.video_menu.tk_popup(event.x_root, event.y_root)

    def _stop_video(self):
        """Stop playback and release the player."""
        self.play_video('')  # Clear the video

    def play_video(self, video_path):
        """Load and play a video file embedded in the video_frame."""
        # Stopping playback when called with empty string
        if not video_path:
            if self.current_player is not None:
                self.current_player.terminate()
                self.current_player = None
            self.video_frame.unbind('<Space>')
            self.video_frame.unbind('<Right>')
            self.video_frame.unbind('<Left>')
            return

        # Clean up any previous bindings before setting up new ones
        self.video_frame.unbind('<Space>')
        self.video_frame.unbind('<Right>')
        self.video_frame.unbind('<Left>')

        # Stop any previously playing video to avoid overlapping playback
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
        self.video_frame.bind('<Right>', seek_forward)
        self.video_frame.bind('<Left>', seek_backward)

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
