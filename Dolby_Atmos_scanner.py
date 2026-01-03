import os
import sys
import json
import csv
import subprocess
import threading
import traceback
import time
import webbrowser
from pathlib import Path

import ttkbootstrap as tb
from ttkbootstrap.constants import *
import tkinter as tk
from tkinter import filedialog, messagebox

# ==========================================================
# CONFIG
# ==========================================================
VERSION = "1.0"
VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi", ".mov", ".ts", ".m2ts"}
CACHE_FILE = "scan_cache.json"
DEFAULT_LANG = "en"
GITHUB_REPO = "https://github.com/Liozon/Dolby-Atmos-scanner"

# ==========================================================
# PYINSTALLER RESOURCE PATH
# ==========================================================
def resource_path(relative):
    """
    Returns the absolute path to a resource, compatible with PyInstaller.
    When the app is bundled, PyInstaller extracts files to a temporary folder
    (_MEIPASS). This function ensures the correct path is returned whether
    running from source or as a bundled executable.
    
    Args:
        relative: Relative path to the resource file
    
    Returns:
        Absolute path to the resource
    """
    try:
        base = sys._MEIPASS
    except Exception:
        base = os.path.abspath(".")
    return os.path.join(base, relative)

FFPROBE = resource_path("ffmpeg/ffprobe.exe")
ICON_PATH = resource_path("icon.ico")
TRANSLATIONS_PATH = resource_path("translations")

# ==========================================================
# TRANSLATIONS
# ==========================================================
def load_translation(lang):
    """
    Loads translation strings from a JSON file for the specified language.
    
    Args:
        lang: Language code (e.g., "en", "fr")
    
    Returns:
        Dictionary containing translation key-value pairs, or empty dict if file not found
    """
    try:
        with open(os.path.join(TRANSLATIONS_PATH, f"{lang}.json"), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

# ==========================================================
# CACHE
# ==========================================================
def load_cache():
    """
    Loads the scan cache from disk. The cache stores previously scanned video
    file information to avoid rescanning unchanged files.
    
    Returns:
        Dictionary containing cached scan results, or empty dict if cache doesn't exist
    """
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_cache(cache):
    """
    Saves the scan cache to disk as a JSON file.
    
    Args:
        cache: Dictionary containing scan results to be cached
    """
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)

def file_signature(path):
    """
    Creates a unique signature for a file based on its size and modification time.
    This is used to detect if a file has changed since it was last scanned.
    
    Args:
        path: Path to the file
    
    Returns:
        String signature in format "size_mtime"
    """
    st = os.stat(path)
    return f"{st.st_size}_{st.st_mtime}"

# ==========================================================
# AUDIO SCAN
# ==========================================================
def scan_video(path, cache):
    """
    Scans a video file to detect spatial audio formats (Dolby Atmos, DTS:X).
    Uses ffprobe to analyze audio streams and identifies advanced audio codecs.
    Results are cached to avoid rescanning unchanged files.
    
    Args:
        path: Path to the video file
        cache: Cache dictionary to store/retrieve results
    
    Returns:
        List of tuples containing (format, language, codec, profile) for each spatial audio track
    """
    sig = file_signature(path)
    key = str(path)

    # Return cached result if file hasn't changed
    if key in cache and cache[key]["sig"] == sig:
        return cache[key]["tracks"]

    # Build ffprobe command to extract audio stream information
    cmd = [
        FFPROBE, "-v", "error",
        "-select_streams", "a",  # Select only audio streams
        "-show_streams",
        "-of", "json",
        str(path)
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        data = json.loads(proc.stdout)
    except Exception:
        return []

    tracks = []
    for s in data.get("streams", []):
        codec = s.get("codec_name", "").lower()
        profile = s.get("profile", "").lower()
        lang = s.get("tags", {}).get("language", "unknown")

        # Detect Dolby Atmos (TrueHD with Atmos profile)
        if "atmos" in profile or (codec == "truehd" and "atmos" in profile):
            tracks.append(("Dolby Atmos", lang, codec, profile))
        # Detect Dolby Atmos (E-AC-3 with JOC - Joint Object Coding)
        elif codec in {"eac3", "e-ac-3"} and "joc" in profile:
            tracks.append(("Dolby Atmos", lang, codec, profile))
        # Detect DTS:X
        elif codec == "dts" and "x" in profile:
            tracks.append(("DTS:X", lang, codec, profile))

    # Cache the results
    cache[key] = {"sig": sig, "tracks": tracks}
    return tracks

# ==========================================================
# FOLDER SCAN
# ==========================================================
def scan_folders(folders, progress_cb):
    """
    Scans multiple folders recursively for video files and analyzes their audio tracks.
    Calls the progress callback function to update the UI during scanning.
    
    Args:
        folders: List of folder paths to scan
        progress_cb: Callback function called with (current, total) to report progress
    
    Returns:
        List of tuples containing (file_path, format, language, codec, profile) for all detected tracks
    """
    cache = load_cache()
    results = []

    # Collect all video files from all folders
    files = []
    for folder in folders:
        files.extend(
            f for f in Path(folder).rglob("*")
            if f.suffix.lower() in VIDEO_EXTENSIONS
        )

    total = len(files)

    # Scan each file and collect results
    for i, file in enumerate(files, 1):
        tracks = scan_video(file, cache)
        for t in tracks:
            results.append((str(file), *t))
        progress_cb(i, total)

    save_cache(cache)
    return results

# ==========================================================
# GUI
# ==========================================================
class ScannerGUI:
    def __init__(self, root):
        """
        Initializes the GUI application.
        
        Args:
            root: The main tkinter window
        """
        self.root = root
        self.folders = []  # List of folders to scan
        self.results = []  # Scan results
        self.scan_start_time = None  # Track scan duration
        self.last_update_time = None  # For throttling time display updates

        # UI language and language filter variables
        self.lang_ui = tb.StringVar(value=DEFAULT_LANG)
        self.lang_filter = tb.StringVar()

        self.trans = load_translation(DEFAULT_LANG)
        self.build_ui()

    def tr(self, key):
        """
        Translates a key using the loaded translation dictionary.
        
        Args:
            key: Translation key
        
        Returns:
            Translated string, or the key itself if translation not found
        """
        return self.trans.get(key, key)

    def build_ui(self):
        """
        Builds the entire user interface including:
        - Top toolbar with language selector and folder management
        - Folder list display
        - Scan button
        - Results treeview
        - Progress bar with time estimate
        - Export buttons
        - Status bar with About link
        """
        self.root.title(f"{self.tr('title')} - v{VERSION}")
        try:
            self.root.iconbitmap(ICON_PATH)
        except Exception:
            pass

        # TOP BAR
        top = tb.Frame(self.root, padding=10)
        top.pack(fill=X)

        tb.Button(top, text=self.tr("add_folder"),
                  command=self.add_folder).pack(side=LEFT)

        tb.Label(top, text="UI language:").pack(side=LEFT, padx=10)
        lang_sel = tb.Combobox(
            top, values=["en", "fr"],
            textvariable=self.lang_ui,
            width=5, state="readonly"
        )
        lang_sel.pack(side=LEFT)
        lang_sel.bind("<<ComboboxSelected>>", self.change_language)

        tb.Label(top, text=self.tr("language_filter")).pack(side=LEFT, padx=10)
        tb.Entry(top, textvariable=self.lang_filter, width=10).pack(side=LEFT)

        # FOLDER LIST
        lf = tb.Labelframe(self.root, text="Folders to scan", padding=10)
        lf.pack(fill=X, padx=10, pady=5)

        self.folder_list = tk.Listbox(lf, height=4)
        self.folder_list.pack(side=LEFT, fill=X, expand=True)

        sb = tb.Scrollbar(lf, orient=VERTICAL, command=self.folder_list.yview)
        sb.pack(side=RIGHT, fill=Y)
        self.folder_list.config(yscrollcommand=sb.set)

        tb.Button(
            lf,
            text=self.tr("remove_selected"),
            bootstyle=DANGER,
            command=self.remove_folder
        ).pack(side=RIGHT, padx=5)

        # SCAN BUTTON
        tb.Button(self.root, text=self.tr("scan"),
                  bootstyle=SUCCESS,
                  command=self.run_scan).pack(pady=5)

        # RESULTS TREEVIEW
        cols = (self.tr("col_file"), self.tr("col_format"), self.tr("col_lang"), self.tr("col_codec"), self.tr("col_profile"))
        self.tree = tb.Treeview(self.root, columns=cols, show="headings")

        for c, w in zip(cols, (550, 120, 80, 100, 200)):
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=w)

        self.tree.pack(fill=BOTH, expand=True, padx=10)

        # PROGRESS BAR AND TIME ESTIMATE
        progress_frame = tb.Frame(self.root)
        progress_frame.pack(fill=X, padx=10, pady=5)

        self.progress = tb.Progressbar(progress_frame)
        self.progress.pack(side=LEFT, fill=X, expand=True)

        self.time_label = tb.Label(progress_frame, text="", width=20, anchor=E)
        self.time_label.pack(side=RIGHT, padx=(10, 0))

        # EXPORT BUTTONS
        bottom = tb.Frame(self.root, padding=10)
        bottom.pack(fill=X)

        tb.Button(bottom, text=self.tr("export_txt"),
                  command=self.export_txt).pack(side=LEFT)
        tb.Button(bottom, text=self.tr("export_csv"),
                  command=self.export_csv).pack(side=LEFT, padx=5)

        # STATUS BAR WITH ABOUT LINK
        status_frame = tb.Frame(self.root)
        status_frame.pack(fill=X, padx=10)
        
        self.status = tb.Label(status_frame, text=self.tr("ready"), anchor=W)
        self.status.pack(side=LEFT, fill=X, expand=True)
        
        # About link (styled as a link)
        self.about_link = tb.Label(
            status_frame, 
            text=self.tr("about"),
            foreground="#3498db",
            cursor="hand2",
            anchor=E
        )
        self.about_link.pack(side=RIGHT, padx=5)
        self.about_link.bind("<Button-1>", lambda e: self.show_about())

    def show_about(self):
        """
        Displays the About dialog with application information, author,
        GitHub link, and update check functionality.
        """
        about_win = tk.Toplevel(self.root)
        about_win.title(self.tr("about"))
        about_win.geometry("400x250")
        about_win.resizable(False, False)
        about_win.transient(self.root)
        about_win.grab_set()
        
        # Center the window
        about_win.update_idletasks()
        x = (about_win.winfo_screenwidth() // 2) - (about_win.winfo_width() // 2)
        y = (about_win.winfo_screenheight() // 2) - (about_win.winfo_height() // 2)
        about_win.geometry(f"+{x}+{y}")
        
        try:
            about_win.iconbitmap(ICON_PATH)
        except Exception:
            pass
        
        # Content frame
        content = tb.Frame(about_win, padding=20)
        content.pack(fill=BOTH, expand=True)
        
        # Title
        title = tb.Label(
            content,
            text=f"Dolby Atmos Scanner",
            font=("Segoe UI", 16, "bold")
        )
        title.pack(pady=(0, 5))
        
        # Version
        version = tb.Label(
            content,
            text=self.tr("about_version").format(version=VERSION),
            font=("Segoe UI", 10)
        )
        version.pack(pady=5)
        
        # Author
        author = tb.Label(
            content,
            text=self.tr("about_author"),
            font=("Segoe UI", 10)
        )
        author.pack(pady=5)
        
        # GitHub link
        github_frame = tb.Frame(content)
        github_frame.pack(pady=5)
        
        github_label = tb.Label(
            github_frame,
            text=self.tr("about_github"),
            foreground="#3498db",
            cursor="hand2",
            font=("Segoe UI", 10, "underline")
        )
        github_label.pack()
        github_label.bind("<Button-1>", lambda e: webbrowser.open(GITHUB_REPO))
        
        # Check for updates button
        update_btn = tb.Button(
            content,
            text=self.tr("about_check_update"),
            command=lambda: self.check_for_updates(about_win),
            bootstyle=INFO
        )
        update_btn.pack(pady=5)
        
        # Close button
        close_btn = tb.Button(
            content,
            text=self.tr("about_close"),
            command=about_win.destroy,
            bootstyle=SECONDARY
        )
        close_btn.pack(pady=0)

    def check_for_updates(self, parent_win):
        """
        Checks for application updates by opening the GitHub releases page.
        
        Args:
            parent_win: Parent window for displaying messages
        """
        try:
            webbrowser.open(f"{GITHUB_REPO}/releases/latest")
        except Exception:
            messagebox.showerror(
                self.tr("error"),
                self.tr("about_update_error"),
                parent=parent_win
            )

    def change_language(self, _=None):
        """
        Changes the UI language by reloading translations and rebuilding the interface.
        Preserves the current state (folders, results, filters) during the transition.
        
        Args:
            _: Event parameter (unused, from combobox selection event)
        """
        # Save current state
        saved_folders = self.folders.copy()
        saved_results = self.results.copy()
        saved_lang_filter = self.lang_filter.get()
        saved_lang_ui = self.lang_ui.get()
        
        # Load new translation
        self.trans = load_translation(saved_lang_ui)
        
        # Destroy all widgets
        for widget in self.root.winfo_children():
            widget.destroy()
        
        # Recreate variables (they're bound to destroyed widgets)
        self.lang_ui = tb.StringVar(value=saved_lang_ui)
        self.lang_filter = tb.StringVar(value=saved_lang_filter)
        
        # Rebuild interface
        self.build_ui()
        
        # Restore state
        self.folders = saved_folders
        self.results = saved_results
        
        # Repopulate folder list
        for folder in self.folders:
            self.folder_list.insert(tk.END, folder)
        
        # Repopulate results if present
        if self.results:
            self.populate()

    def add_folder(self):
        """
        Opens a folder selection dialog and adds the selected folder to the scan list.
        Prevents duplicate folders from being added.
        """
        folder = filedialog.askdirectory()
        if folder and folder not in self.folders:
            self.folders.append(folder)
            self.folder_list.insert(tk.END, folder)

    def remove_folder(self):
        """
        Removes the currently selected folder from the scan list.
        """
        sel = self.folder_list.curselection()
        if sel:
            idx = sel[0]
            self.folder_list.delete(idx)
            del self.folders[idx]

    def format_time(self, seconds):
        """
        Formats a duration in seconds to a human-readable string.
        
        Args:
            seconds: Number of seconds
        
        Returns:
            Formatted string (e.g., "45s", "2m 30s", "1h 15m")
        """
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            mins = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{mins}m {secs}s"
        else:
            hours = int(seconds // 3600)
            mins = int((seconds % 3600) // 60)
            return f"{hours}h {mins}m"

    def run_scan(self):
        """
        Initiates the scanning process in a separate thread to keep the UI responsive.
        Shows a warning if no folders are selected.
        """
        if not self.folders:
            messagebox.showwarning("Warning", self.tr("no_folder"))
            return
        threading.Thread(target=self._scan, daemon=True).start()

    def _scan(self):
        """
        Performs the actual scanning operation. This runs in a background thread.
        Clears previous results, updates progress bar, calculates time estimates,
        and populates the results when complete.
        """
        self.tree.delete(*self.tree.get_children())
        self.results.clear()
        self.status.config(text=self.tr("scanning"))
        self.progress["value"] = 0
        self.scan_start_time = time.time()
        self.last_update_time = self.scan_start_time

        def prog(cur, tot):
            """
            Progress callback that updates the progress bar and time estimate.
            
            Args:
                cur: Current file number
                tot: Total number of files
            """
            self.progress["maximum"] = tot
            self.progress["value"] = cur
            
            # Calculate remaining time
            now = time.time()
            elapsed = now - self.scan_start_time
            
            if cur > 0:
                avg_time_per_file = elapsed / cur
                remaining_files = tot - cur
                estimated_remaining = avg_time_per_file * remaining_files
                
                # Update time display (throttled to every 0.5s to avoid flickering)
                if now - self.last_update_time > 0.5:
                    self.root.after(0, lambda: self.time_label.config(
                        text=f"~{self.format_time(estimated_remaining)}"
                    ))
                    self.last_update_time = now

        self.results = scan_folders(self.folders, prog)
        self.root.after(0, self.populate)
        self.root.after(0, lambda: self.time_label.config(text=""))

    def populate(self):
        """
        Populates the results treeview with scan results.
        Applies the language filter if one is specified.
        Updates the status bar with the count of displayed results.
        """
        lf = self.lang_filter.get().lower().strip()
        count = 0
        for r in self.results:
            # Apply language filter if specified
            if lf and r[2].lower() != lf:
                continue
            self.tree.insert("", END, values=r)
            count += 1
        self.status.config(text=f"{self.tr('done')} — {count}")

    def export_txt(self):
        """
        Exports scan results to a plain text file.
        Each result is written as a pipe-separated line.
        """
        if not self.results:
            return
        p = filedialog.asksaveasfilename(defaultextension=".txt")
        if not p:
            return
        with open(p, "w", encoding="utf-8") as f:
            for r in self.results:
                f.write(" | ".join(r) + "\n")

    def export_csv(self):
        """
        Exports scan results to a CSV file with headers.
        Includes columns: File, Format, Language, Codec, Profile.
        """
        if not self.results:
            return
        p = filedialog.asksaveasfilename(defaultextension=".csv")
        if not p:
            return
        with open(p, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["File", "Format", "Language", "Codec", "Profile"])
            w.writerows(self.results)

# ==========================================================
# MAIN
# ==========================================================
if __name__ == "__main__":
    """
    Application entry point. Creates the main window with a dark theme
    and handles any uncaught exceptions by printing them and waiting for user input.
    """
    try:
        app = tb.Window(
            title=f"Dolby Atmos scanner - v{VERSION}",
            themename="darkly",
            size=(1200, 600),
            resizable=(True, True)
        )
        ScannerGUI(app)
        app.mainloop()
    except Exception:
        traceback.print_exc()
        input("Press ENTER to exit...")