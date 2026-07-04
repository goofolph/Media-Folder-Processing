import mimetypes
import traceback
import platform
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
import os
import shutil

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

        # Track the player (single reusable instance)
        self.player = None
        self.current_video_path = None

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
        self.tree_menu.add_command(label='Copy path', command=self._copy_selected_path)
        self.tree_menu.add_separator()
        self.tree_menu.add_command(
            label='Delete', command=self._delete_selected, foreground='red'
        )

        # Create video frame context menu
        self.video_menu = tk.Menu(self.video_frame, tearoff=0)
        self.video_menu.add_command(label='Pause', command=self._toggle_pause_video)
        self.video_menu.add_separator()
        self.video_menu.add_command(label='Stop', command=self._stop_video)

        # Bind right-click on video frame to context menu
        self.video_frame.bind('<Button-3>', self._on_video_context)

        # Terminate mpv and let Tk handle the destroy (default is also destroy)
        self.root.protocol('WM_DELETE_WINDOW', self._on_close)

        # Register X11 error handler to ignore BadWindow/RenderBadPicture protocol errors
        self._register_x11_error_handler()

        # Ensure the widget has been realized before creating MPV
        self.video_frame.pack_propagate(False)
        self.root.update()

        try:
            # Force the x11 video output backend on Linux to ensure stable window embedding with Tkinter
            if platform.system() == 'Linux':
                self.player = mpv.MPV(wid=str(self.video_frame.winfo_id()), vo='x11')
            else:
                self.player = mpv.MPV(wid=str(self.video_frame.winfo_id()))
        except Exception as e:
            messagebox.showerror('Player Error', f'Failed to initialize mpv player:\n{e}')

        # Media controls via keyboard
        def toggle_pause(ev):
            if self.current_video_path and self.player:
                self.player.pause = not self.player.pause

        def seek_forward(ev):
            if self.current_video_path and self.player:
                try:
                    self.player.seek(5, reference='relative')
                except SystemError:
                    pass

        def seek_backward(ev):
            if self.current_video_path and self.player:
                try:
                    self.player.seek(-5, reference='relative')
                except SystemError:
                    pass

        # Bind media keys on video frame (not root, so they don't collide)
        self.video_frame.bind('<space>', toggle_pause)
        self.video_frame.bind('<Right>', seek_forward)
        self.video_frame.bind('<Left>', seek_backward)
        self.video_frame.bind('<Escape>', self._on_escape)

        # Load initial root directory (Change this path to test different folders)
        self._initial_dirs = []
        for d in dirs:
            root_path = os.path.abspath(d)  # Defaults to system root (e.g., C:\ or /)
            self._initial_dirs.append(root_path)
            self.insert_node('', root_path, os.path.basename(root_path))

    def _register_x11_error_handler(self):
        """Register a custom X11 error handler to ignore non-fatal protocol errors like BadWindow or RenderBadPicture."""
        if platform.system() == 'Linux':
            try:
                import ctypes
                from ctypes import c_int, c_void_p, POINTER, Structure, c_ulong, c_ubyte

                class XErrorEvent(Structure):
                    _fields_ = [
                        ('type', c_int),
                        ('display', c_void_p),
                        ('serial', c_ulong),
                        ('error_code', c_ubyte),
                        ('request_code', c_ubyte),
                        ('minor_code', c_ubyte),
                        ('resourceid', c_ulong),
                    ]

                def _x_error_handler(display, error_event_ptr):
                    # Ignore non-fatal X11 protocol errors (BadWindow, RenderBadPicture, etc.)
                    return 0

                self._x_handler_type = ctypes.CFUNCTYPE(c_int, c_void_p, POINTER(XErrorEvent))
                self._x_handler = self._x_handler_type(_x_error_handler)

                xlib = ctypes.cdll.LoadLibrary('libX11.so.6')
                xlib.XSetErrorHandler(self._x_handler)
            except Exception:
                pass

    def insert_node(self, parent, path, text, is_dir=None):
        """Inserts a node into the tree. If it's a folder, adds a dummy child."""
        if is_dir is None:
            is_dir = os.path.isdir(path)
        icon = self.folder_icon if is_dir else self.file_icon

        # Insert the item
        node = self.tree.insert(parent, 'end', text=text, image=icon, values=(path,))

        # If it's a directory, add a dummy child so the UI displays the expand arrow
        if is_dir:
            self.tree.insert(node, 'end', text='loading...')

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
                # Use os.scandir for fast, stat-efficient directory scanning
                entries = []
                with os.scandir(path) as it:
                    for entry in it:
                        try:
                            is_dir = entry.is_dir(follow_symlinks=True)
                            is_file = entry.is_file(follow_symlinks=True)
                        except OSError:
                            # Handle cases where the entry is broken/inaccessible
                            continue

                        if is_dir or (is_file and is_video_file(entry.path)):
                            entries.append((entry.name.lower(), entry.name, entry.path, is_dir))

                # Sort entries by name case-insensitively
                entries.sort(key=lambda x: x[0])

                for _, name, full_path, is_dir in entries:
                    self.insert_node(node, full_path, name, is_dir=is_dir)
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
        if not path:
            return
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(path)
            self.root.update()
        except tk.TclError:
            # Root window already destroyed — nothing to do.
            pass

    def _delete_selected(self):
        """Delete the selected file or directory after confirmation."""
        selection = self.tree.selection()
        print(f'Deteting selected {selection}')
        if not selection:
            return
        path = self._selected_path()
        print(f'Deteting path {path}')
        if not path:
            return

        # Confirm before mutating UI or disk
        target = 'directory' if os.path.isdir(path) else 'file'
        if not messagebox.askokcancel('Delete', f'Remove this {target}?\n\n{path}'):
            return

        node = selection[0]
        print(f'Selected node {node}')

        # Stop playback before disk deletion to release locks and avoid player crash states
        if self.current_video_path:
            current_abs = os.path.abspath(self.current_video_path)
            target_abs = os.path.abspath(path)
            is_same_or_child = False
            if current_abs == target_abs:
                is_same_or_child = True
            elif os.path.isdir(target_abs):
                try:
                    is_same_or_child = (
                        os.path.commonpath([target_abs, current_abs]) == target_abs
                    )
                except ValueError:
                    pass
            if is_same_or_child:
                print('Stopping video')
                self.play_video('')

        try:
            if os.path.isdir(path):
                print(f'Delting directory {path}')
                shutil.rmtree(path)
            else:
                print(f'Delting file {path}')
                os.remove(path)
        except (PermissionError, OSError) as exc:
            # Disk deletion failed; leave the node so the UI matches reality
            messagebox.showerror('Delete Failed', f'Failed to delete:\n{exc}')
            return

        # Remove from the tree only after disk deletion succeeds
        print(f'Deleting node {node}')
        self.tree.delete(node)

    def _refresh_tree(self):
        """Remove all items and reload the root directories."""
        self.tree.delete(*self.tree.get_children())
        for d in self._initial_dirs:
            self.insert_node('', d, os.path.basename(os.path.abspath(d)))

    def _toggle_pause_video(self):
        """Pause/resume playback via context menu."""
        if self.player is not None and self.current_video_path:
            self.player.pause = not self.player.pause

    def _on_video_context(self, event):
        """Show video playback context menu."""
        self.video_menu.tk_popup(event.x_root, event.y_root)

    def _stop_video(self):
        """Stop playback cleanly."""
        self.current_video_path = None
        if self.player is not None:
            self.player.stop()

    def _on_close(self):
        """Handle window close: stop mpv, then destroy the root."""
        if self.player is not None:
            self.player.terminate()
            self.player = None
        self.root.destroy()

    def _on_escape(self, event):
        """Stop playback and release player on ESC key."""
        self.play_video('')

    def play_video(self, video_path):
        """Load and play a video file embedded in the video_frame."""
        try:
            if not self.root.winfo_exists():
                return
        except tk.TclError:
            return

        # Stopping playback when called with empty string
        if not video_path:
            self._stop_video()
            return

        # Stop previous playback cleanly before starting new video
        if self.player is not None:
            self.player.stop()

        self.video_frame.focus_set()

        # Load and play the video
        mpv_file_path = os.path.abspath(video_path)
        self.current_video_path = mpv_file_path
        if self.player is not None:
            self.player.play(mpv_file_path)


if __name__ == '__main__':
    try:
        import sys

        root = tk.Tk()
        MediaApp(root, sys.argv[1:])
        root.mainloop()
    except Exception:
        traceback.print_exc()
