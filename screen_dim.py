"""Windows 亮度调节：Fn+F6 调暗、Fn+F7 调亮（取决于键盘的 FnLock 状态）。"""

import ctypes
import queue
import threading
import tkinter as tk
from ctypes import wintypes
from dataclasses import dataclass
from tkinter import messagebox


USER32 = ctypes.WinDLL("user32", use_last_error=True)
DXVA2 = ctypes.WinDLL("Dxva2", use_last_error=True)
KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)
MAGNIFICATION = ctypes.WinDLL("Magnification", use_last_error=True)
HANDLE = wintypes.HANDLE
COLOR_EFFECT = ctypes.c_float * 25
MONITOR_CALLBACK = ctypes.WINFUNCTYPE(wintypes.BOOL, HANDLE, HANDLE, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
MOD_NOREPEAT = 0x4000
MAX_ALPHA = 250
ALPHA_STEP = 25


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


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("极暗亮度")
        self.root.configure(bg="#16191f")
        self.root.geometry("460x260")
        self.root.minsize(460, 240)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
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
            button = tk.Button(buttons, text=text, font=("Microsoft YaHei UI", 10), padx=10,
                               command=lambda cmd=action: self.dispatch(cmd))
            button.pack(side="left", padx=4)
            self.controls.append(button)
            if action != "exit":
                button.configure(state="disabled")
        self.worker = BrightnessWorker(self.commands, self.events)
        self.hotkeys = HotkeyThread(self.hotkey_commands, self.events)
        self.worker.start()
        self.hotkeys.start()
        self.root.after(50, self.poll)
        self.root.after(4000, self.refresh)

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
