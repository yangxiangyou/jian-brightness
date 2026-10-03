"""Windows 亮度调节：Fn+F6 调暗、Fn+F7 调亮（取决于键盘的 FnLock 状态）。"""

import base64
import ctypes
import queue
import struct
import threading
import tkinter as tk
import zlib
from ctypes import wintypes
from dataclasses import dataclass
from tkinter import messagebox


USER32 = ctypes.WinDLL("user32", use_last_error=True)
DXVA2 = ctypes.WinDLL("Dxva2", use_last_error=True)
KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)
MAGNIFICATION = ctypes.WinDLL("Magnification", use_last_error=True)
SHELL32 = ctypes.WinDLL("shell32", use_last_error=True)
HANDLE = wintypes.HANDLE
COLOR_EFFECT = ctypes.c_float * 25
MONITOR_CALLBACK = ctypes.WINFUNCTYPE(wintypes.BOOL, HANDLE, HANDLE, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)
WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, HANDLE, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
WM_NULL = 0x0000
WM_CLOSE = 0x0010
WM_LBUTTONUP = 0x0202
WM_RBUTTONUP = 0x0205
WM_TRAY = 0x8001
MOD_NOREPEAT = 0x4000
MAX_ALPHA = 250
ALPHA_STEP = 25


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", HANDLE),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", HANDLE),
        ("szTip", wintypes.WCHAR * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256),
        ("uVersion", wintypes.UINT),
        ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD),
    ]


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", HANDLE),
        ("hIcon", HANDLE),
        ("hCursor", HANDLE),
        ("hbrBackground", HANDLE),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


class ICONINFO(ctypes.Structure):
    _fields_ = [
        ("fIcon", wintypes.BOOL),
        ("xHotspot", wintypes.DWORD),
        ("yHotspot", wintypes.DWORD),
        ("hbmMask", HANDLE),
        ("hbmColor", HANDLE),
    ]


class MonitorInfo(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD),
        ("szDevice", wintypes.WCHAR * 32),
    ]


class DisplayDevice(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("DeviceName", wintypes.WCHAR * 32),
        ("DeviceString", wintypes.WCHAR * 128),
        ("StateFlags", wintypes.DWORD),
        ("DeviceID", wintypes.WCHAR * 128),
        ("DeviceKey", wintypes.WCHAR * 128),
    ]


class PhysicalMonitor(ctypes.Structure):
    _fields_ = [("handle", HANDLE), ("description", wintypes.WCHAR * 128)]


class BITMAPV5HEADER(ctypes.Structure):
    _fields_ = [
        ("bV5Size", wintypes.DWORD),
        ("bV5Width", wintypes.LONG),
        ("bV5Height", wintypes.LONG),
        ("bV5Planes", wintypes.WORD),
        ("bV5BitCount", wintypes.WORD),
        ("bV5Compression", wintypes.DWORD),
        ("bV5SizeImage", wintypes.DWORD),
        ("bV5XPelsPerMeter", wintypes.LONG),
        ("bV5YPelsPerMeter", wintypes.LONG),
        ("bV5ClrUsed", wintypes.DWORD),
        ("bV5ClrImportant", wintypes.DWORD),
        ("bV5RedMask", wintypes.DWORD),
        ("bV5GreenMask", wintypes.DWORD),
        ("bV5BlueMask", wintypes.DWORD),
        ("bV5AlphaMask", wintypes.DWORD),
        ("bV5CSType", wintypes.DWORD),
        ("bV5Endpoints", ctypes.c_byte * 36),
        ("bV5GammaRed", wintypes.DWORD),
        ("bV5GammaGreen", wintypes.DWORD),
        ("bV5GammaBlue", wintypes.DWORD),
        ("bV5Intent", wintypes.DWORD),
        ("bV5ProfileData", wintypes.DWORD),
        ("bV5ProfileSize", wintypes.DWORD),
        ("bV5Reserved", wintypes.DWORD),
    ]


USER32.EnumDisplayMonitors.argtypes = [HANDLE, ctypes.POINTER(wintypes.RECT), MONITOR_CALLBACK, wintypes.LPARAM]
USER32.EnumDisplayMonitors.restype = wintypes.BOOL
USER32.GetMonitorInfoW.argtypes = [HANDLE, ctypes.POINTER(MonitorInfo)]
USER32.GetMonitorInfoW.restype = wintypes.BOOL
USER32.EnumDisplayDevicesW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(DisplayDevice), wintypes.DWORD]
USER32.EnumDisplayDevicesW.restype = wintypes.BOOL
USER32.RegisterHotKey.argtypes = [HANDLE, ctypes.c_int, wintypes.UINT, wintypes.UINT]
USER32.RegisterHotKey.restype = wintypes.BOOL
USER32.UnregisterHotKey.argtypes = [HANDLE, ctypes.c_int]
USER32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), HANDLE, wintypes.UINT, wintypes.UINT]
USER32.GetMessageW.restype = ctypes.c_int
USER32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
USER32.PostThreadMessageW.restype = wintypes.BOOL
USER32.SetProcessDpiAwarenessContext.argtypes = [HANDLE]
USER32.SetProcessDpiAwarenessContext.restype = wintypes.BOOL
KERNEL32.GetCurrentThreadId.restype = wintypes.DWORD
KERNEL32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
KERNEL32.CreateMutexW.restype = HANDLE
KERNEL32.CloseHandle.argtypes = [HANDLE]
KERNEL32.CloseHandle.restype = wintypes.BOOL
KERNEL32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
KERNEL32.GetModuleHandleW.restype = HANDLE
MAGNIFICATION.MagInitialize.restype = wintypes.BOOL
MAGNIFICATION.MagUninitialize.restype = wintypes.BOOL
MAGNIFICATION.MagGetFullscreenColorEffect.argtypes = [ctypes.POINTER(COLOR_EFFECT)]
MAGNIFICATION.MagGetFullscreenColorEffect.restype = wintypes.BOOL
MAGNIFICATION.MagSetFullscreenColorEffect.argtypes = [ctypes.POINTER(COLOR_EFFECT)]
MAGNIFICATION.MagSetFullscreenColorEffect.restype = wintypes.BOOL
DXVA2.GetNumberOfPhysicalMonitorsFromHMONITOR.argtypes = [HANDLE, ctypes.POINTER(wintypes.DWORD)]
DXVA2.GetNumberOfPhysicalMonitorsFromHMONITOR.restype = wintypes.BOOL
DXVA2.GetPhysicalMonitorsFromHMONITOR.argtypes = [HANDLE, wintypes.DWORD, ctypes.POINTER(PhysicalMonitor)]
DXVA2.GetPhysicalMonitorsFromHMONITOR.restype = wintypes.BOOL
DXVA2.DestroyPhysicalMonitors.argtypes = [wintypes.DWORD, ctypes.POINTER(PhysicalMonitor)]
DXVA2.GetMonitorBrightness.argtypes = [HANDLE, ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD)]
DXVA2.GetMonitorBrightness.restype = wintypes.BOOL
DXVA2.SetMonitorBrightness.argtypes = [HANDLE, wintypes.DWORD]
DXVA2.SetMonitorBrightness.restype = wintypes.BOOL
DXVA2.GetVCPFeatureAndVCPFeatureReply.argtypes = [HANDLE, wintypes.BYTE, ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD)]
DXVA2.GetVCPFeatureAndVCPFeatureReply.restype = wintypes.BOOL
DXVA2.SetVCPFeature.argtypes = [HANDLE, wintypes.BYTE, wintypes.DWORD]
DXVA2.SetVCPFeature.restype = wintypes.BOOL
SHELL32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
SHELL32.Shell_NotifyIconW.restype = wintypes.BOOL
USER32.LoadIconW.restype = HANDLE
USER32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
USER32.RegisterClassW.restype = wintypes.ATOM
USER32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                                   ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                   HANDLE, HANDLE, HANDLE, ctypes.c_void_p]
USER32.CreateWindowExW.restype = HANDLE
USER32.DefWindowProcW.argtypes = [HANDLE, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
USER32.DefWindowProcW.restype = ctypes.c_ssize_t
USER32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
USER32.GetCursorPos.restype = wintypes.BOOL
USER32.SetForegroundWindow.argtypes = [HANDLE]
USER32.SetForegroundWindow.restype = wintypes.BOOL
USER32.TrackPopupMenu.argtypes = [HANDLE, wintypes.UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int, HANDLE, ctypes.c_void_p]
USER32.TrackPopupMenu.restype = ctypes.c_int
USER32.AppendMenuW.argtypes = [HANDLE, wintypes.UINT, ctypes.c_ssize_t, wintypes.LPCWSTR]
USER32.AppendMenuW.restype = wintypes.BOOL
USER32.CreatePopupMenu.restype = HANDLE
USER32.DestroyMenu.argtypes = [HANDLE]
USER32.DestroyMenu.restype = wintypes.BOOL
USER32.PostMessageW.argtypes = [HANDLE, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
USER32.PostMessageW.restype = wintypes.BOOL
USER32.RegisterWindowMessageW.argtypes = [wintypes.LPCWSTR]
USER32.RegisterWindowMessageW.restype = wintypes.UINT
GDI32 = ctypes.WinDLL("gdi32", use_last_error=True)
GDI32.CreateBitmap.argtypes = [ctypes.c_int, ctypes.c_int, wintypes.UINT, wintypes.UINT, ctypes.c_void_p]
GDI32.CreateBitmap.restype = HANDLE
GDI32.CreateDIBSection.argtypes = [HANDLE, ctypes.c_void_p, wintypes.UINT, ctypes.POINTER(ctypes.c_void_p), HANDLE, wintypes.DWORD]
GDI32.CreateDIBSection.restype = HANDLE
GDI32.DeleteObject.argtypes = [HANDLE]
GDI32.DeleteObject.restype = wintypes.BOOL
USER32.CreateIconIndirect.argtypes = [ctypes.POINTER(ICONINFO)]
USER32.CreateIconIndirect.restype = HANDLE
USER32.DestroyIcon.argtypes = [HANDLE]
USER32.DestroyIcon.restype = wintypes.BOOL
USER32.DestroyWindow.argtypes = [HANDLE]
USER32.DestroyWindow.restype = wintypes.BOOL
USER32.PostQuitMessage.argtypes = [ctypes.c_int]
USER32.PostQuitMessage.restype = None
USER32.GetDC.argtypes = [HANDLE]
USER32.GetDC.restype = HANDLE
USER32.ReleaseDC.argtypes = [HANDLE, HANDLE]
USER32.ReleaseDC.restype = ctypes.c_int
GDI32.CreateCompatibleDC.argtypes = [HANDLE]
GDI32.CreateCompatibleDC.restype = HANDLE
GDI32.CreateCompatibleBitmap.argtypes = [HANDLE, ctypes.c_int, ctypes.c_int]
GDI32.CreateCompatibleBitmap.restype = HANDLE
GDI32.SelectObject.argtypes = [HANDLE, HANDLE]
GDI32.SelectObject.restype = HANDLE
GDI32.CreateSolidBrush.argtypes = [wintypes.COLORREF]
GDI32.CreateSolidBrush.restype = HANDLE
GDI32.Ellipse.argtypes = [HANDLE, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]
GDI32.Ellipse.restype = wintypes.BOOL
GDI32.DeleteDC.argtypes = [HANDLE]
GDI32.DeleteDC.restype = wintypes.BOOL
USER32.FillRect.argtypes = [HANDLE, ctypes.POINTER(wintypes.RECT), HANDLE]
USER32.FillRect.restype = ctypes.c_int
DWMAPI = ctypes.WinDLL("dwmapi", use_last_error=True)
DWMAPI.DwmSetWindowAttribute.argtypes = [HANDLE, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
DWMAPI.DwmSetWindowAttribute.restype = ctypes.c_long
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWA_BORDER_COLOR = 34
DWMWCP_ROUND = 2
DWMWA_COLOR_NONE = 0xFFFFFFFE


@dataclass
class Screen:
    key: str
    name: str
    handle: int
    rect: tuple[int, int, int, int]
    wmi_id: str | None
    kind: str = "software"
    source: str = "software"
    ddc_mode: str = "highlevel"
    minimum: int = 0
    maximum: int = 100
    current: int | None = None
    original: int | None = None
    note: str = "仅软件调暗"

    def view(self):
        return (self.key, self.name, self.rect, self.kind, self.current, self.minimum, self.maximum, self.note)


def enumerate_screens():
    result = []

    @MONITOR_CALLBACK
    def receive(handle, _hdc, _rect, _data):
        info = MonitorInfo(cbSize=ctypes.sizeof(MonitorInfo))
        if not USER32.GetMonitorInfoW(handle, ctypes.byref(info)):
            return True
        device = DisplayDevice(cb=ctypes.sizeof(DisplayDevice))
        device_id = ""
        if USER32.EnumDisplayDevicesW(info.szDevice, 0, ctypes.byref(device), 1):
            device_id = device.DeviceID
        parts = device_id.split("#")
        wmi_id = f"DISPLAY\\{parts[1]}\\{parts[2]}".lower() if len(parts) > 2 else None
        box = info.rcMonitor
        key = device_id or info.szDevice
        result.append(Screen(key, device.DeviceString or info.szDevice, handle,
                             (box.left, box.top, box.right, box.bottom), wmi_id))
        return True

    if not USER32.EnumDisplayMonitors(None, None, receive, 0):
        raise ctypes.WinError(ctypes.get_last_error())
    return result


def with_physical_monitor(screen, operation):
    count = wintypes.DWORD()
    if not DXVA2.GetNumberOfPhysicalMonitorsFromHMONITOR(screen.handle, ctypes.byref(count)) or count.value != 1:
        return None
    monitors = (PhysicalMonitor * count.value)()
    if not DXVA2.GetPhysicalMonitorsFromHMONITOR(screen.handle, count, monitors):
        return None
    try:
        return operation(monitors[0].handle)
    finally:
        DXVA2.DestroyPhysicalMonitors(count, monitors)


def read_ddc(handle):
    minimum, current, maximum = wintypes.DWORD(), wintypes.DWORD(), wintypes.DWORD()
    if DXVA2.GetMonitorBrightness(handle, ctypes.byref(minimum), ctypes.byref(current), ctypes.byref(maximum)):
        if minimum.value <= current.value <= maximum.value and minimum.value < maximum.value:
            return "highlevel", minimum.value, current.value, maximum.value
    if DXVA2.GetVCPFeatureAndVCPFeatureReply(handle, 0x10, None, ctypes.byref(current), ctypes.byref(maximum)):
        if 0 <= current.value <= maximum.value and maximum.value:
            return "vcp", 0, current.value, maximum.value
    return None


class BrightnessWorker(threading.Thread):
    def __init__(self, commands, events):
        super().__init__(daemon=True)
        self.commands = commands
        self.events = events
        self.screens = {}
        self.originals = {}
        self.alpha = 0
        self.stopping = False

    def run(self):
        try:
            import pythoncom
            pythoncom.CoInitialize()
        except Exception as exc:
            self.events.put(("error", f"无法初始化 Windows 亮度接口：{exc}"))
            return
        try:
            self.refresh()
            while True:
                command = self.commands.get()
                try:
                    if command == "exit":
                        self.stopping = True
                        problems = self.restore()
                        self.events.put(("exit", problems))
                        break
                    if self.stopping:
                        continue
                    if command == "refresh":
                        self.refresh()
                    elif command in ("darker", "brighter"):
                        if command == "brighter" and self.alpha:
                            self.alpha = max(0, self.alpha - ALPHA_STEP)
                        elif command == "darker" and self.alpha:
                            self.alpha = min(MAX_ALPHA, self.alpha + ALPHA_STEP)
                        else:
                            for screen in self.screens.values():
                                self.adjust(screen, command)
                            if command == "darker" and all(
                                screen.kind == "software" or screen.current <= screen.minimum
                                for screen in self.screens.values()
                            ):
                                self.alpha = min(MAX_ALPHA, self.alpha + ALPHA_STEP)
                        self.publish()
                    elif command == "restore":
                        self.events.put(("restore", self.restore()))
                except Exception as exc:
                    self.events.put(("error", f"亮度操作失败：{exc}"))
        except Exception as exc:
            self.events.put(("error", f"无法初始化亮度控制：{exc}"))
        finally:
            pythoncom.CoUninitialize()

    def refresh(self):
        import wmi

        found = enumerate_screens()
        old = self.screens
        if [(s.key, s.rect) for s in found] == [(s.key, s.rect) for s in old.values()]:
            return
        try:
            client = wmi.WMI(namespace="wmi")
            readings = {name.removesuffix("_0").lower(): (levels, int(brightness))
                        for name, levels, brightness in client.fetch_as_lists(
                            "WmiMonitorBrightness", ["InstanceName", "Level", "CurrentBrightness"])}
            method_ids = {row[0].removesuffix("_0").lower() for row in client.fetch_as_lists(
                "WmiMonitorBrightnessMethods", ["InstanceName"])}
            del client
        except Exception:
            readings = {}
            method_ids = set()
        if len(found) == 1 and len(readings) == 1 and not found[0].wmi_id:
            found[0].wmi_id = next(iter(readings))
        updated = {}
        for screen in found:
            if screen.key in old:
                previous = old[screen.key]
                previous.handle = screen.handle
                previous.rect = screen.rect
                updated[screen.key] = previous
                continue
            reading = readings.get(screen.wmi_id)
            if reading and screen.wmi_id in method_ids:
                screen.kind = screen.source = "wmi"
                levels, brightness = reading
                screen.minimum = max(1, min(levels))
                screen.maximum = max(levels)
                screen.current = screen.original = brightness
                screen.note = "内屏背光可调"
            else:
                try:
                    levels = with_physical_monitor(screen, read_ddc)
                except Exception:
                    levels = None
                if levels:
                    screen.kind = screen.source = "ddc"
                    screen.ddc_mode, screen.minimum, screen.current, screen.maximum = levels
                    screen.original = screen.current
                    screen.note = "外屏背光可调"
                else:
                    screen.note = "背光不可控，仅软件调暗"
            if screen.kind != "software":
                if screen.key in self.originals:
                    original = self.originals[screen.key]
                    screen.original = original
                    if screen.current != original:
                        try:
                            self.set_hardware(screen, original)
                        except Exception:
                            screen.note = "重连后背光恢复失败，请手动检查"
                else:
                    self.originals[screen.key] = screen.original
            updated[screen.key] = screen
        self.screens = updated
        self.publish()

    def set_hardware(self, screen, value):
        if screen.source == "wmi":
            import wmi
            client = wmi.WMI(namespace="wmi")
            methods = client.WmiMonitorBrightnessMethods()
            method = next((m for m in methods if m.InstanceName.removesuffix("_0").lower() == screen.wmi_id), None)
            if method is None:
                raise RuntimeError("内屏 WMI 设备已断开")
            result = method.WmiSetBrightness(Brightness=value, Timeout=0)
            if result and result != (0,):
                raise RuntimeError(f"WMI 返回错误码 {result}")
            del method, methods, client
        else:
            def write(handle):
                if screen.ddc_mode == "vcp":
                    return bool(DXVA2.SetVCPFeature(handle, 0x10, value))
                return bool(DXVA2.SetMonitorBrightness(handle, value))

            if not with_physical_monitor(screen, write):
                raise RuntimeError("DDC/CI 无响应")
        screen.current = value

    def adjust(self, screen, direction):
        if direction == "darker":
            if screen.kind != "software" and screen.current > screen.minimum:
                step = max(1, round((screen.maximum - screen.minimum) / 10))
                value = max(screen.minimum, screen.current - step)
                try:
                    self.set_hardware(screen, value)
                except Exception:
                    screen.note = "背光调节失败，仅软件调暗"
                    screen.kind = "software"
        elif screen.kind != "software" and screen.current < screen.maximum:
            step = max(1, round((screen.maximum - screen.minimum) / 10))
            value = min(screen.maximum, screen.current + step)
            try:
                self.set_hardware(screen, value)
            except Exception:
                screen.note = "背光调节失败，仅软件调暗"
                screen.kind = "software"

    def restore(self):
        problems = []
        self.alpha = 0
        for screen in self.screens.values():
            if screen.original is not None:
                try:
                    self.set_hardware(screen, screen.original)
                except Exception as exc:
                    problems.append(f"{screen.name}：{exc}")
        self.publish()
        return problems

    def publish(self):
        self.events.put(("screens", ([s.view() for s in self.screens.values()], self.alpha)))


class HotkeyThread(threading.Thread):
    def __init__(self, commands, events):
        super().__init__(daemon=True)
        self.commands = commands
        self.events = events
        self.thread_id = None

    def run(self):
        self.thread_id = KERNEL32.GetCurrentThreadId()
        registered = []
        try:
            for identifier, key in ((1, 0x75), (2, 0x76)):
                if not USER32.RegisterHotKey(None, identifier, MOD_NOREPEAT, key):
                    raise RuntimeError(f"F{identifier + 5} 被系统或其他程序占用（错误 {ctypes.get_last_error()}）")
                registered.append(identifier)
            self.events.put(("hotkeys", None))
            msg = wintypes.MSG()
            while USER32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == WM_HOTKEY:
                    self.commands.put("darker" if msg.wParam == 1 else "brighter")
        except Exception as exc:
            self.events.put(("hotkey_error", f"Fn+F6/Fn+F7 热键不可用：{exc}；仍可使用下方按钮"))
        finally:
            for identifier in registered:
                USER32.UnregisterHotKey(None, identifier)

    def stop(self):
        if self.thread_id:
            USER32.PostThreadMessageW(self.thread_id, WM_QUIT, 0, 0)


class DesktopDimmer:
    def __init__(self):
        if not MAGNIFICATION.MagInitialize():
            raise ctypes.WinError(ctypes.get_last_error())
        self.original = COLOR_EFFECT()
        if not MAGNIFICATION.MagGetFullscreenColorEffect(ctypes.byref(self.original)):
            MAGNIFICATION.MagUninitialize()
            raise ctypes.WinError(ctypes.get_last_error())

        self.applied = None

    def set_alpha(self, value):
        factor = 1 - value / 255
        effect = COLOR_EFFECT(*(
            component * (factor if index % 5 < 3 else 1)
            for index, component in enumerate(self.original)
        ))
        if not MAGNIFICATION.MagSetFullscreenColorEffect(ctypes.byref(effect)):
            raise ctypes.WinError(ctypes.get_last_error())
        self.applied = effect

    def close(self):
        try:
            current = COLOR_EFFECT()
            if self.applied is not None and MAGNIFICATION.MagGetFullscreenColorEffect(ctypes.byref(current)):
                if bytes(current) == bytes(self.applied):
                    self.set_alpha(0)
        finally:
            MAGNIFICATION.MagUninitialize()


class TrayIcon:
    """系统托盘图标 + 消息窗口（独立线程）。左键唤出主窗，右键菜单操作。"""

    NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
    NIF_MESSAGE, NIF_ICON, NIF_TIP = 1, 2, 4
    NIN_POPUPMENU_IDS = {"darker": 2001, "brighter": 2002, "restore": 2003, "exit": 2004}
    TPM_RIGHTBUTTON, TPM_BOTTOMALIGN = 0x0002, 0x0020

    def __init__(self, actions):
        self.actions = actions
        self.hwnd = None
        self.hicon = None
        self.menu = None
        self.thread = None
        self.thread_id = None

    def start(self):
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def run(self):
        instance = KERNEL32.GetModuleHandleW(None)
        self.hicon = load_png_hicon()
        class_name = "JianBrightnessTray"
        window_class = WNDCLASSW()
        window_class.lpfnWndProc = WNDPROC(self.procedure)
        window_class.hInstance = instance
        window_class.lpszClassName = class_name
        if not USER32.RegisterClassW(ctypes.byref(window_class)) and ctypes.get_last_error() != 1410:
            return
        self.hwnd = USER32.CreateWindowExW(0, class_name, "极暗亮度", 0, 0, 0, 0, 0, None, None, instance, None)
        if not self.hwnd:
            return
        self.thread_id = KERNEL32.GetCurrentThreadId()
        self.add()
        msg = wintypes.MSG()
        while USER32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            pass

    def add(self):
        icon_data = NOTIFYICONDATAW()
        icon_data.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        icon_data.hWnd = self.hwnd
        icon_data.uID = 1
        icon_data.uFlags = self.NIF_MESSAGE | self.NIF_ICON | self.NIF_TIP
        icon_data.uCallbackMessage = WM_TRAY
        icon_data.hIcon = self.hicon
        icon_data.szTip = "极暗亮度（后台运行中）"
        SHELL32.Shell_NotifyIconW(self.NIM_ADD, ctypes.byref(icon_data))

    def show_menu(self):
        self.menu = USER32.CreatePopupMenu()
        for label, key in (("调暗（Fn+F6）", "darker"), ("调亮（Fn+F7）", "brighter"),
                           ("立即恢复", "restore"), ("退出", "exit")):
            USER32.AppendMenuW(self.menu, 0, self.NIN_POPUPMENU_IDS[key], label)
        point = wintypes.POINT()
        USER32.GetCursorPos(ctypes.byref(point))
        USER32.SetForegroundWindow(self.hwnd)
        chosen = USER32.TrackPopupMenu(self.menu, self.TPM_RIGHTBUTTON | self.TPM_BOTTOMALIGN | 0x0100,
                                       point.x, point.y, 0, self.hwnd, None)
        USER32.DestroyMenu(self.menu)
        self.menu = None
        if chosen:
            command = next((cmd for cmd, uid in self.NIN_POPUPMENU_IDS.items() if uid == chosen), None)
            if command:
                self.actions(command)

    def procedure(self, hwnd, message, wparam, lparam):
        if message == WM_TRAY:
            if lparam == WM_LBUTTONUP:
                self.actions("show")
            elif lparam == WM_RBUTTONUP:
                self.show_menu()
            return 0
        return USER32.DefWindowProcW(hwnd, message, wparam, lparam)

    def stop(self):
        icon_data = NOTIFYICONDATAW()
        icon_data.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        icon_data.hWnd = self.hwnd
        icon_data.uID = 1
        SHELL32.Shell_NotifyIconW(self.NIM_DELETE, ctypes.byref(icon_data))
        if self.thread_id:
            USER32.PostThreadMessageW(self.thread_id, WM_QUIT, 0, 0)


SUN_ICON_PNG = ("iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAABe0lEQVR42u2WW0sCURDH/Tw9"
                "hREEEQQVdHOzi1FUVhRCn8vHXiIiIqIkzBYN0SiRaou+QTfLdXf5N+NuIG1qNbtQsAM/GGbOnrmc"
                "w5wNhQIJJJD/Jg+bHQqRJDTCcNAcm+Jn4DCRQmkFuFwGzhdh5edc8Bpe60fVBq7WUKe8ClwsAYV5"
                "WGcxF05XFC8rN3BNgW8TNqyX4kCREshNw8xOuXCSCHuRQKoe7GYduN+wYZ1tBWo7BTPU6Jfwt+LW"
                "Ix+jdi9Q66ntdwkb1tlGPlOdQC0TaYroKPhmIzdJlc7SxaOA5bgN62wjX+1kDHp6tCm8hyQBzcqM"
                "A9koVTtjB2VYJxv79OPhlvAekgSMamoIZnoEOKVE1IgN6WxjXzt4D1ECb4cDYKpHg9BpQ4b1D3s7"
                "pAlorwf9kCA9gmRlvw8SpJdQqez1QoJ4IvIwedntwW8QD6LGUfy8042f4NkobnyMnra78B08fYw+"
                "P8ePW51ohS/P8Z/4IQkkkED8knetnRmwevUvvgAAAABJRU5ErkJggg==")


def load_png_hicon():
    """把内嵌 PNG 解码为 32bpp ARGB 图标句柄（托盘/窗口共用，抗锯齿透明底）。"""
    png = base64.b64decode(SUN_ICON_PNG)
    ihdr = png[16:29]
    width, height = struct.unpack(">II", ihdr[:8])
    position, idat = 8, b""
    while position < len(png):
        length = struct.unpack(">I", png[position:position + 4])[0]
        tag = png[position + 4:position + 8]
        if tag == b"IDAT":
            idat += png[position + 8:position + 8 + length]
        position += 12 + length
    raw = zlib.decompress(idat)
    stride = width * 4
    pixels = bytearray(width * height * 4)
    previous = bytearray(stride)
    offset = 0
    for row in range(height):
        filter_type = raw[offset]
        offset += 1
        line = bytearray(raw[offset:offset + stride])
        offset += stride
        bpp = 4
        if filter_type == 1:
            for index in range(bpp, stride):
                line[index] = (line[index] + line[index - bpp]) & 0xFF
        elif filter_type == 2:
            for index in range(stride):
                line[index] = (line[index] + previous[index]) & 0xFF
        elif filter_type == 3:
            for index in range(stride):
                left = line[index - bpp] if index >= bpp else 0
                line[index] = (line[index] + ((left + previous[index]) >> 1)) & 0xFF
        elif filter_type == 4:
            for index in range(stride):
                a = line[index - bpp] if index >= bpp else 0
                b = previous[index]
                c = previous[index - bpp] if index >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                predictor = a if (pa := abs(p - a)) <= pb and pa <= pc else (b if pb <= pc else c)
                line[index] = (line[index] + predictor) & 0xFF
        previous = line
        # PNG 行序自上而下，BGRA 位图自下而上
        target = (height - 1 - row) * stride
        for index in range(0, stride, 4):
            r, g, b, a = line[index:index + 4]
            pixels[target + index] = b
            pixels[target + index + 1] = g
            pixels[target + index + 2] = r
            pixels[target + index + 3] = a
    header = BITMAPV5HEADER()
    header.bV5Size = ctypes.sizeof(BITMAPV5HEADER)
    header.bV5Width = width
    header.bV5Height = height
    header.bV5Planes = 1
    header.bV5BitCount = 32
    header.bV5Compression = 0  # BI_RGB
    header.bV5SizeImage = len(pixels)
    header.bV5RedMask = 0x00FF0000
    header.bV5GreenMask = 0x0000FF00
    header.bV5BlueMask = 0x000000FF
    header.bV5AlphaMask = 0xFF000000
    header.bV5CSType = 0x73524742  # 'sRGB'
    pixel_pointer = ctypes.c_void_p()
    bitmap = GDI32.CreateDIBSection(None, ctypes.byref(header), 0, ctypes.byref(pixel_pointer), None, 0)
    if bitmap and pixel_pointer:
        ctypes.memmove(pixel_pointer, bytes(pixels), len(pixels))
    if not bitmap:
        return None
    info = ICONINFO(fIcon=True, xHotspot=0, yHotspot=0,
                    hbmMask=GDI32.CreateBitmap(width, height, 1, 1, None), hbmColor=bitmap)
    icon = USER32.CreateIconIndirect(ctypes.byref(info))
    GDI32.DeleteObject(bitmap)
    GDI32.DeleteObject(info.hbmMask)
    return icon


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("极暗亮度")
        self.root.configure(bg="#16191f")
        self.root.geometry("460x260")
        self.root.minsize(460, 240)
        self.root.protocol("WM_DELETE_WINDOW", self.hide)
        try:
            self.icon_photo = tk.PhotoImage(data=base64.b64decode(SUN_ICON_PNG))
            self.root.iconphoto(False, self.icon_photo)
        except Exception:
            self.icon_photo = None
        self.apply_window_style()

    def apply_window_style(self):
        """深色标题栏 + 隐藏边框色 + Win11 圆角。"""
        def window_handle():
            try:
                return int(self.root.wm_frame(), 16)
            except Exception:
                handle = USER32.FindWindowW(None, "极暗亮度")
                return handle
        handle = window_handle()
        if not handle:
            return
        true_value = wintypes.BOOL(1)
        DWMAPI.DwmSetWindowAttribute(handle, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(true_value), ctypes.sizeof(true_value))
        preference = wintypes.DWORD(DWMWCP_ROUND)
        DWMAPI.DwmSetWindowAttribute(handle, DWMWA_WINDOW_CORNER_PREFERENCE, ctypes.byref(preference), ctypes.sizeof(preference))
        border = wintypes.DWORD(DWMWA_COLOR_NONE)
        DWMAPI.DwmSetWindowAttribute(handle, DWMWA_BORDER_COLOR, ctypes.byref(border), ctypes.sizeof(border))
        self.commands = queue.Queue()
        self.hotkey_commands = queue.Queue()
        self.events = queue.Queue()
        self.dimmer = DesktopDimmer()
        self.alpha = 0
        self.ready = False
        self.detected = False
        self.hotkey_error = None
        self.closing = False
        self.destroyed = False
        self.info = tk.StringVar(value="正在检测显示器……")
        self.status = tk.StringVar(value="Fn+F6 调暗 · Fn+F7 调亮\nFnLock 开启时直接按 F6/F7")
        tk.Label(self.root, text="极暗亮度", bg="#16191f", fg="#f3f4f6", font=("Microsoft YaHei UI", 16, "bold")).pack(pady=(12, 4))
        tk.Label(self.root, textvariable=self.status, bg="#16191f", fg="#b2bac9",
                 font=("Microsoft YaHei UI", 10)).pack(pady=2)
        tk.Label(self.root, textvariable=self.info, bg="#16191f", fg="#dae0e8", justify="left",
                 wraplength=430, font=("Microsoft YaHei UI", 10)).pack(fill="both", expand=True, padx=16, pady=8)
        buttons = tk.Frame(self.root, bg="#16191f")
        buttons.pack(pady=(0, 15))
        self.controls = []
        for text, action in (("调暗", "darker"), ("调亮", "brighter"), ("立即恢复", "restore"), ("退出", "exit")):
            button = tk.Button(buttons, text=text, font=("Microsoft YaHei UI", 10, "bold"),
                               bg="#232833" if action != "exit" else "#16191f",
                               fg="#e8ecf2" if action != "exit" else "#8b93a3",
                               activebackground="#2e3440" if action != "exit" else "#232833",
                               activeforeground="#ffffff", relief="flat", bd=0, padx=14, pady=3,
                               cursor="hand2", command=lambda cmd=action: self.dispatch(cmd))
            button.pack(side="left", padx=5)
            self.controls.append(button)
            if action != "exit":
                button.configure(state="disabled", disabledforeground="#5b6270")
        self.worker = BrightnessWorker(self.commands, self.events)
        self.hotkeys = HotkeyThread(self.hotkey_commands, self.events)
        self.tray = TrayIcon(self.on_tray)
        self.worker.start()
        self.hotkeys.start()
        self.tray.start()
        self.root.after(50, self.poll)
        self.root.after(4000, self.refresh)

    def on_tray(self, command):
        self.root.after(0, lambda: self.dispatch_tray(command))

    def dispatch_tray(self, command):
        if command == "show":
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
        else:
            self.dispatch(command)

    def dispatch(self, command):
        if self.closing:
            return
        if command == "exit":
            self.close()
        elif self.ready and self.detected and command == "restore":
            self.clear_dimming()
            self.commands.put("restore")
        elif self.ready and self.detected:
            self.commands.put(command)

    def refresh(self):
        if not self.closing:
            self.commands.put("refresh")
            self.root.after(4000, self.refresh)

    def poll(self):
        try:
            while True:
                action = self.hotkey_commands.get_nowait()
                self.dispatch(action)
        except queue.Empty:
            pass
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "screens":
                    screens, alpha = value
                    self.show_screens(screens, alpha)
                elif kind == "hotkeys":
                    self.ready = True
                    for button in self.controls:
                        button.configure(state="normal")
                elif kind == "hotkey_error":
                    self.hotkey_error = value
                    self.ready = True
                    for button in self.controls:
                        button.configure(state="normal")
                    self.status.set(value)
                elif kind == "error":
                    if not self.closing:
                        self.close()
                    messagebox.showerror("极暗亮度", value, parent=self.root)
                    if not self.worker.is_alive():
                        self.hotkeys.stop()
                        self.tray.stop()
                        self.destroyed = True
                        self.root.destroy()
                        return
                elif kind in ("restore", "exit"):
                    if value:
                        messagebox.showwarning("亮度恢复提示", "以下屏幕的背光恢复失败：\n" + "\n".join(value), parent=self.root)
                    if kind == "exit":
                        self.hotkeys.stop()
                        self.destroyed = True
                        self.root.destroy()
                        return
                    self.status.set(self.hotkey_error or "已恢复启动时的背光亮度")
        except queue.Empty:
            pass
        if not self.destroyed:
            self.root.after(50, self.poll)

    def show_screens(self, screens, alpha):
        if self.closing:
            return
        self.detected = bool(screens)
        if alpha != self.alpha:
            self.dimmer.set_alpha(alpha)
            self.alpha = alpha
        lines = [f"全界面额外调暗 {round(alpha * 100 / 255)}%"]
        for index, (_key, name, _rect, kind, current, minimum, maximum, note) in enumerate(screens, 1):
            hardware = f"背光 {round((current - minimum) * 100 / (maximum - minimum))}%" if kind != "software" else "背光不可调"
            lines.append(f"屏幕 {index} {name}：{hardware} · {note}")
        self.info.set("\n".join(lines) if screens else "未检测到活动显示器")
        self.root.geometry(f"460x{max(260, 145 + 36 * len(lines))}")

    def clear_dimming(self):
        if self.alpha:
            self.dimmer.set_alpha(0)
            self.alpha = 0

    def hide(self):
        self.root.withdraw()

    def close(self):
        if self.closing:
            return
        self.closing = True
        self.ready = False
        for button in self.controls:
            button.configure(state="disabled")
        self.status.set("正在恢复启动时的背光亮度……")
        if self.worker.is_alive():
            self.commands.put("exit")
        else:
            self.hotkeys.stop()
            self.tray.stop()
            self.destroyed = True
            self.root.destroy()
        try:
            self.clear_dimming()
        except OSError:
            pass

    def run(self):
        try:
            self.root.mainloop()
        finally:
            self.tray.stop()
            self.hotkeys.stop()
            if not self.destroyed and self.worker.is_alive():
                self.commands.put("exit")
                self.worker.join(timeout=5)
            self.dimmer.close()


if __name__ == "__main__":
    mutex = KERNEL32.CreateMutexW(None, False, "Local\\ScreenDimBrightness")
    if not mutex:
        raise ctypes.WinError(ctypes.get_last_error())
    if ctypes.get_last_error() != 183:
        try:
            if not USER32.SetProcessDpiAwarenessContext(HANDLE(-4)) and ctypes.get_last_error() != 5:
                raise ctypes.WinError(ctypes.get_last_error())
            App().run()
        finally:
            KERNEL32.CloseHandle(mutex)
    else:
        KERNEL32.CloseHandle(mutex)
