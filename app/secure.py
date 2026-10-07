"""Protects saved secrets (sign-in keys) with Windows' own account encryption (DPAPI).
Only this Windows user on this PC can decrypt them. On other systems, or if anything fails, text is stored as before."""
import base64
import sys

PREFIX = "dpapi:"


def _win_call(data, protect):
    import ctypes
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    crypt32, kernel32 = ctypes.windll.crypt32, ctypes.windll.kernel32
    fn = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    fn.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
                   wintypes.DWORD, ctypes.POINTER(Blob)]
    fn.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    buf = ctypes.create_string_buffer(data, len(data))
    inb = Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    out = Blob()
    if not fn(ctypes.byref(inb), None, None, None, None, 0, ctypes.byref(out)):
        raise OSError("DPAPI call failed")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        kernel32.LocalFree(ctypes.cast(out.pbData, ctypes.c_void_p))


def protect(text):
    if not text or sys.platform != "win32":
        return text
    try:
        return PREFIX + base64.b64encode(_win_call(text.encode("utf-8"), True)).decode()
    except Exception:
        return text


def unprotect(text):
    if not isinstance(text, str) or not text.startswith(PREFIX):
        return text
    try:
        return _win_call(base64.b64decode(text[len(PREFIX):]), False).decode("utf-8")
    except Exception:
        return ""
