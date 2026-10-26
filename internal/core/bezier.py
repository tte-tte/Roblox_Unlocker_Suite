import asyncio
import ctypes
import logging
import random
import time
from typing import Callable
from playwright.async_api import Page, Locator

logger: logging.Logger = logging.getLogger("roblox_suite.bezier")

MOUSEEVENTF_LEFTDOWN: int = 0x0002
MOUSEEVENTF_LEFTUP: int = 0x0004
INPUT_KEYBOARD: int = 1
KEYEVENTF_UNICODE: int = 0x0004
KEYEVENTF_KEYUP: int = 0x0002
SW_RESTORE: int = 9

try:
    ctypes.windll.user32.SetProcessDPIAware()
except Exception:
    pass


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", ctypes.c_ulong),
        ("wParamL", ctypes.c_short),
        ("wParamH", ctypes.c_ushort)
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("ki", KEYBDINPUT),
        ("mi", MOUSEINPUT),
        ("hi", HARDWAREINPUT)
    ]


class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("union", INPUT_UNION)
    ]


WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)


class HumanMouseController:
    @staticmethod
    def get_os_cursor_pos() -> tuple[int, int]:
        pt: POINT = POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
        return (int(pt.x), int(pt.y))

    @staticmethod
    def snap_pid_window_to_work_area(target_pid: int) -> bool:
        found_hwnds: list[int] = []

        def enum_callback(hwnd: int, _lparam: int) -> bool:
            if ctypes.windll.user32.IsWindowVisible(hwnd):
                pid_val = ctypes.c_ulong(0)
                ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid_val))
                if int(pid_val.value) == target_pid:
                    length: int = int(ctypes.windll.user32.GetWindowTextLengthW(hwnd))
                    if length > 0:
                        found_hwnds.append(int(hwnd))
            return True

        cb_func = WNDENUMPROC(enum_callback)
        ctypes.windll.user32.EnumWindows(cb_func, 0)

        if not found_hwnds:
            return False

        for hwnd in found_hwnds:
            try:
                ctypes.windll.user32.ShowWindow(hwnd, SW_RESTORE)
                ctypes.windll.user32.MoveWindow(hwnd, 0, 0, 1280, 860, True)
                ctypes.windll.user32.SetForegroundWindow(hwnd)
            except Exception:
                pass
        return True

    @staticmethod
    def send_unicode_char(char: str) -> None:
        code: int = ord(char)
        extra = ctypes.c_ulong(0)

        down_in: INPUT = INPUT()
        down_in.type = INPUT_KEYBOARD
        down_in.union.ki = KEYBDINPUT(0, code, KEYEVENTF_UNICODE, 0, ctypes.pointer(extra))

        up_in: INPUT = INPUT()
        up_in.type = INPUT_KEYBOARD
        up_in.union.ki = KEYBDINPUT(0, code, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0, ctypes.pointer(extra))

        ctypes.windll.user32.SendInput(1, ctypes.byref(down_in), ctypes.sizeof(INPUT))
        ctypes.windll.user32.SendInput(1, ctypes.byref(up_in), ctypes.sizeof(INPUT))

    @classmethod
    async def win32_type_text(cls, text: str) -> None:
        for ch in text:
            cls.send_unicode_char(ch)
            await asyncio.sleep(random.uniform(0.014, 0.032))

    @staticmethod
    def generate_curve(
        start_x: float,
        start_y: float,
        end_x: float,
        end_y: float,
        steps: int = 16
    ) -> list[tuple[float, float]]:
        ctrl1_x: float = start_x + (end_x - start_x) * random.uniform(0.2, 0.4) + random.uniform(-25.0, 25.0)
        ctrl1_y: float = start_y + (end_y - start_y) * random.uniform(0.2, 0.4) + random.uniform(-25.0, 25.0)
        ctrl2_x: float = start_x + (end_x - start_x) * random.uniform(0.6, 0.8) + random.uniform(-25.0, 25.0)
        ctrl2_y: float = start_y + (end_y - start_y) * random.uniform(0.6, 0.8) + random.uniform(-25.0, 25.0)

        points: list[tuple[float, float]] = []
        for i in range(steps + 1):
            t: float = i / float(steps)
            inv_t: float = 1.0 - t
            x: float = (
                (inv_t ** 3) * start_x
                + 3.0 * (inv_t ** 2) * t * ctrl1_x
                + 3.0 * inv_t * (t ** 2) * ctrl2_x
                + (t ** 3) * end_x
            )
            y: float = (
                (inv_t ** 3) * start_y
                + 3.0 * (inv_t ** 2) * t * ctrl1_y
                + 3.0 * inv_t * (t ** 2) * ctrl2_y
                + (t ** 3) * end_y
            )
            points.append((round(x), round(y)))
        return points

    @classmethod
    async def move_and_click(
        cls,
        page: Page,
        locator: Locator,
        current_pos: tuple[float, float] = (100.0, 100.0)
    ) -> tuple[float, float]:
        try:
            box: dict[str, float] | None = await locator.bounding_box()
            if box is None:
                await locator.click()
                return current_pos

            target_x: float = round(box["x"] + box["width"] * random.uniform(0.38, 0.62))
            target_y: float = round(box["y"] + box["height"] * random.uniform(0.38, 0.62))
            return await cls.move_and_click_coords(page, target_x, target_y, current_pos)
        except Exception as exc:
            logger.warning(f"Bezier click fallback triggered: {exc}")
            await locator.click()
            return current_pos

    @classmethod
    async def move_and_click_coords(
        cls,
        page: Page,
        target_x: float,
        target_y: float,
        current_pos: tuple[float, float] = (100.0, 100.0)
    ) -> tuple[float, float]:
        dest_x: float = round(target_x)
        dest_y: float = round(target_y)
        curve_points: list[tuple[float, float]] = cls.generate_curve(
            current_pos[0], current_pos[1], dest_x, dest_y, steps=random.randint(12, 18)
        )
        for point_x, point_y in curve_points:
            await page.mouse.move(point_x, point_y)
            await asyncio.sleep(random.uniform(0.003, 0.007))

        await asyncio.sleep(random.uniform(0.04, 0.09))
        await page.mouse.down()
        await asyncio.sleep(random.uniform(0.04, 0.08))
        await page.mouse.up()
        return (dest_x, dest_y)

    @classmethod
    async def win32_move_and_click(cls, screen_x: int, screen_y: int) -> None:
        start_x, start_y = cls.get_os_cursor_pos()
        curve_points: list[tuple[float, float]] = cls.generate_curve(
            float(start_x), float(start_y), float(screen_x), float(screen_y), steps=random.randint(14, 20)
        )
        for pt_x, pt_y in curve_points:
            ctypes.windll.user32.SetCursorPos(int(pt_x), int(pt_y))
            await asyncio.sleep(random.uniform(0.003, 0.007))

        await asyncio.sleep(random.uniform(0.04, 0.08))
        ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        await asyncio.sleep(random.uniform(0.04, 0.08))
        ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

    @classmethod
    async def win32_move_and_hold_until_complete(
        cls,
        screen_x: int,
        screen_y: int,
        is_completed_fn: Callable[[int, int], bool],
        is_started_fn: Callable[[int, int], bool] | None = None,
        max_hold_seconds: float = 16.0
    ) -> float:
        start_x, start_y = cls.get_os_cursor_pos()
        curve_points: list[tuple[float, float]] = cls.generate_curve(
            float(start_x), float(start_y), float(screen_x), float(screen_y), steps=random.randint(20, 26)
        )
        for pt_x, pt_y in curve_points:
            ctypes.windll.user32.SetCursorPos(int(pt_x), int(pt_y))
            await asyncio.sleep(random.uniform(0.004, 0.008))

        await asyncio.sleep(0.08)
        ctypes.windll.user32.SetCursorPos(int(screen_x - 12), int(screen_y))
        await asyncio.sleep(0.06)
        ctypes.windll.user32.SetCursorPos(int(screen_x), int(screen_y))
        await asyncio.sleep(0.12)

        ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)

        start_time: float = time.monotonic()
        verified_start: bool = False

        while (time.monotonic() - start_time) < max_hold_seconds:
            await asyncio.sleep(0.12)
            elapsed: float = time.monotonic() - start_time

            if not verified_start and elapsed >= 1.05 and is_started_fn is not None:
                verified_start = True
                if not is_started_fn(screen_x, screen_y):
                    ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                    await asyncio.sleep(0.15)
                    ctypes.windll.user32.SetCursorPos(int(screen_x - 180), int(screen_y - 60))
                    await asyncio.sleep(0.25)
                    re_curve: list[tuple[float, float]] = cls.generate_curve(
                        float(screen_x - 180), float(screen_y - 60), float(screen_x), float(screen_y), steps=16
                    )
                    for rx, ry in re_curve:
                        ctypes.windll.user32.SetCursorPos(int(rx), int(ry))
                        await asyncio.sleep(0.005)
                    await asyncio.sleep(0.15)
                    ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                    start_time = time.monotonic()
                    continue

            if elapsed > 1.8 and is_completed_fn(screen_x, screen_y):
                await asyncio.sleep(random.uniform(0.08, 0.14))
                break

        total_held: float = time.monotonic() - start_time
        ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        await asyncio.sleep(0.08)
        ctypes.windll.user32.SetCursorPos(int(screen_x - 210), int(screen_y - 90))
        return total_held