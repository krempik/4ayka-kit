"""File upload guards: MIME allow/deny lists and unsafe extension blacklist.

Usage:
    guard = FileGuard()
    if not guard.check_extension(filename) or not guard.check_mime(content_type):
        raise HTTPException(400, "File type not allowed")
"""
import os

# MIME types we never accept, even if extension says otherwise
BLOCKED_UPLOAD_MIMES = {
    "text/html",
    "text/xml",
    "application/xhtml+xml",
    "image/svg+xml",
}

# HTML/active-content extensions that are always rejected
UNSAFE_UPLOAD_EXTS = {
    ".html", ".htm", ".svg", ".php", ".phtml", ".php5", ".php7",
    ".asp", ".aspx", ".jsp", ".js", ".mjs", ".cgi", ".pl", ".py",
    ".sh", ".bat", ".cmd", ".vbs", ".lnk", ".msi", ".exe", ".dll",
    ".scr", ".ps1", ".jar", ".war", ".apk", ".hta", ".htaccess",
}

# MIME types accepted for image-heavy endpoints (avatars, chat icons)
IMAGE_MIMES = {
    "image/png", "image/jpeg", "image/gif", "image/webp",
}


class FileGuard:
    def __init__(
        self,
        blocked_mimes: set = BLOCKED_UPLOAD_MIMES,
        unsafe_exts: set = UNSAFE_UPLOAD_EXTS,
        max_size_bytes: int = 50 * 1024 * 1024,
    ):
        self.blocked_mimes = blocked_mimes
        self.unsafe_exts = unsafe_exts
        self.max_size_bytes = max_size_bytes

    def check_extension(self, filename: str) -> bool:
        ext = os.path.splitext(filename or "")[1].lower()
        return ext not in self.unsafe_exts

    def check_mime(self, content_type: str) -> bool:
        mime = (content_type or "").split(";")[0].strip().lower()
        if not mime:
            return False
        return mime not in self.blocked_mimes and not mime.startswith("text/html")

    def check_size(self, size: int) -> bool:
        return size <= self.max_size_bytes

    def validate(self, filename: str, content_type: str, size: int) -> str:
        """Return an error message, or '' if the upload is allowed."""
        if not self.check_extension(filename):
            return f"Extension not allowed: {os.path.splitext(filename)[1]}"
        if not self.check_mime(content_type):
            return f"MIME type not allowed: {content_type}"
        if not self.check_size(size):
            return f"File too large (max {self.max_size_bytes} bytes)"
        return ""


__all__ = [
    "FileGuard",
    "BLOCKED_UPLOAD_MIMES",
    "UNSAFE_UPLOAD_EXTS",
    "IMAGE_MIMES",
]