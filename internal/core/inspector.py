import asyncio
import json
import logging
import os
import random
import shutil
import subprocess
import urllib.request
from pathlib import Path
from typing import Optional
from config.settings import settings
from core.bezier import HumanMouseController
from core.vision import VisionEngine
from database.models import AccountModel
from database.repository import AccountRepository
from web.ws_manager import ws_manager

logger: logging.Logger = logging.getLogger("roblox_suite.inspector")

DEMO_LOCK_ENABLED: bool = False
ALLOWED_DEMO_ACCOUNTS: frozenset[str] = frozenset({
    "bl0xfrui1_2025",
    "plikcog3190",
    "plixgale6817"
})


class RobloxInspector:
    def __init__(self) -> None:
        self.max_workers: int = 1 if DEMO_LOCK_ENABLED else max(1, settings.max_concurrent_browsers)
        self.semaphore: asyncio.Semaphore = asyncio.Semaphore(self.max_workers)
        self.input_lock: asyncio.Lock = asyncio.Lock()

    def set_concurrency(self, workers: int) -> int:
        if DEMO_LOCK_ENABLED:
            self.max_workers = 1
        else:
            self.max_workers = max(1, min(workers, 15))
        self.semaphore = asyncio.Semaphore(self.max_workers)
        return self.max_workers

    async def log_and_broadcast(self, username: str, message: str, level: str = "INFO") -> None:
        formatted: str = f"[{username}] {message}"
        if level == "ERROR":
            logger.error(formatted)
        elif level == "WARNING":
            logger.warning(formatted)
        else:
            logger.info(formatted)
        await ws_manager.broadcast_log(username=username, message=message, level=level)

    @staticmethod
    def find_chrome_executable() -> str:
        candidates: list[str] = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")
        ]
        for path_str in candidates:
            if Path(path_str).exists():
                return path_str
        return "chrome.exe"

    @staticmethod
    def prepare_clean_profile(profile_dir: Path) -> None:
        if profile_dir.exists():
            shutil.rmtree(profile_dir, ignore_errors=True)
        default_dir: Path = profile_dir / "Default"
        default_dir.mkdir(parents=True, exist_ok=True)
        prefs_data: dict[str, object] = {
            "credentials_enable_service": False,
            "profile": {
                "password_manager_enabled": False,
                "exit_type": "Normal"
            }
        }
        prefs_file: Path = default_dir / "Preferences"
        try:
            prefs_file.write_text(json.dumps(prefs_data), encoding="utf-8")
        except Exception:
            pass

    @staticmethod
    def get_active_tab_url_no_cdp(debug_port: int) -> str:
        try:
            req_url: str = f"http://127.0.0.1:{debug_port}/json"
            with urllib.request.urlopen(req_url, timeout=1.0) as resp:
                raw_data: str = resp.read().decode("utf-8")
                tabs: list[dict[str, object]] = json.loads(raw_data)
                for tab in tabs:
                    if str(tab.get("type", "")) == "page":
                        url_val: str = str(tab.get("url", ""))
                        if "roblox.com" in url_val:
                            return url_val
        except Exception:
            pass
        return ""

    @staticmethod
    def kill_chrome_tree(proc: Optional[subprocess.Popen[bytes]]) -> None:
        if proc is None:
            return
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=3.0
            )
        except Exception:
            try:
                proc.terminate()
            except Exception:
                pass

    async def process_account(self, account_id: int) -> None:
        async with self.semaphore:
            account: Optional[AccountModel] = await AccountRepository.get_account_by_id(account_id)
            if account is None:
                return

            username: str = account.username
            password: str = account.password
            proxy_server: Optional[str] = account.proxy

            if DEMO_LOCK_ENABLED and username.lower() not in ALLOWED_DEMO_ACCOUNTS:
                await self.log_and_broadcast(
                    username,
                    "TEST PACKAGE LIMIT: Only the 3 demo accounts are enabled in the test build.",
                    level="ERROR"
                )
                locked_upd: Optional[dict[str, Optional[str | int]]] = await AccountRepository.update_account_state(
                    account_id=account_id,
                    status="DEMO_LOCKED",
                    lock_type="UPGRADE_REQUIRED",
                    challenge_metadata="Locked in Test Package"
                )
                if locked_upd:
                    await ws_manager.broadcast_account_update(locked_upd)
                return

            updated: Optional[dict[str, Optional[str | int]]] = await AccountRepository.update_account_state(
                account_id=account_id,
                status="RUNNING",
                lock_type="QUEUED",
                last_error=""
            )
            if updated:
                await ws_manager.broadcast_account_update(updated)

            chrome_proc: Optional[subprocess.Popen[bytes]] = None

            try:
                async with self.input_lock:
                    await self.log_and_broadcast(
                        username,
                        "Launching fast stock Chrome (100% Zero-CDP Native Win32 Pipeline)..."
                    )

                    profile_dir: Path = Path("data") / f"chrome_profile_{username}"
                    self.prepare_clean_profile(profile_dir)

                    shared_cache_dir: Path = Path("data") / "shared_chrome_cache"
                    shared_cache_dir.mkdir(parents=True, exist_ok=True)

                    debug_port: int = random.randint(9225, 9550)
                    chrome_exe: str = self.find_chrome_executable()

                    chrome_cmd: list[str] = [
                        chrome_exe,
                        f"--remote-debugging-port={debug_port}",
                        f"--user-data-dir={profile_dir.resolve()}",
                        "--window-position=0,0",
                        "--window-size=1280,860",
                        "--no-first-run",
                        "--no-default-browser-check"
                    ]
                    if proxy_server and proxy_server.lower() != "direct":
                        chrome_cmd.append(f"--proxy-server={proxy_server}")
                    chrome_cmd.append(settings.roblox_login_url)

                    chrome_proc = subprocess.Popen(
                        chrome_cmd,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )

                    await asyncio.sleep(2.0)

                    login_btn_coords: Optional[tuple[int, int]] = None
                    for _ in range(45):
                        await asyncio.sleep(0.5)
                        login_btn_coords = VisionEngine.find_login_button_on_screen()
                        if login_btn_coords is not None:
                            await asyncio.sleep(2.8)
                            login_btn_coords = VisionEngine.find_login_button_on_screen() or login_btn_coords
                            break

                    if login_btn_coords is None:
                        login_btn_coords = (630, 445)

                    btn_x, btn_y = login_btn_coords
                    user_field_x: int = btn_x
                    user_field_y: int = btn_y - 105
                    pass_field_x: int = btn_x
                    pass_field_y: int = btn_y - 52

                    await self.log_and_broadcast(
                        username,
                        f"Login form ready at ({btn_x}, {btn_y}). Typing credentials..."
                    )

                    await HumanMouseController.win32_move_and_click(user_field_x, user_field_y)
                    await asyncio.sleep(0.12)
                    await HumanMouseController.win32_type_text(username)
                    await asyncio.sleep(0.15)

                    await HumanMouseController.win32_move_and_click(pass_field_x, pass_field_y)
                    await asyncio.sleep(0.12)
                    await HumanMouseController.win32_type_text(password)
                    await asyncio.sleep(0.18)

                    await self.log_and_broadcast(username, "Clicking Login button...")
                    await HumanMouseController.win32_move_and_click(btn_x, btn_y)

                    detected_lock_type: str = await self.solve_challenges_zero_cdp(
                        account_id=account_id,
                        username=username,
                        debug_port=debug_port,
                        login_btn_coords=(btn_x, btn_y)
                    )

                    tab_url: str = self.get_active_tab_url_no_cdp(debug_port)
                    await self.log_and_broadcast(username, f"Post-captcha URL: {tab_url}")

                    if settings.roblox_not_approved_path in tab_url:
                        await self.handle_not_approved_win32(
                            account_id=account_id,
                            username=username
                        )
                    elif settings.roblox_home_path in tab_url:
                        home_shot: str = f"{settings.screenshots_dir}/{username}_state.png"
                        VisionEngine.save_desktop_screenshot(home_shot)
                        await self.log_and_broadcast(username, "Account is UNLOCKED and reached /home!")
                        unl_upd: Optional[dict[str, Optional[str | int]]] = await AccountRepository.update_account_state(
                            account_id=account_id,
                            status="UNLOCKED",
                            lock_type="NONE",
                            challenge_metadata="Active Session",
                            screenshot_path=f"/screenshots/{username}_state.png"
                        )
                        if unl_upd:
                            await ws_manager.broadcast_account_update(unl_upd)
                    else:
                        end_shot: str = f"{settings.screenshots_dir}/{username}_state.png"
                        VisionEngine.save_desktop_screenshot(end_shot)
                        upd_end: Optional[dict[str, Optional[str | int]]] = await AccountRepository.update_account_state(
                            account_id=account_id,
                            status="LOCKED",
                            lock_type=detected_lock_type,
                            challenge_metadata=f"URL: {tab_url}",
                            screenshot_path=f"/screenshots/{username}_state.png"
                        )
                        if upd_end:
                            await ws_manager.broadcast_account_update(upd_end)

                    await self.log_and_broadcast(username, "Closing Chrome window via [X] button and moving to next account...")
                    await HumanMouseController.win32_move_and_click(1258, 18)
                    await asyncio.sleep(0.5)

            except asyncio.CancelledError:
                logger.info(f"Task cancelled for {username}")
            except Exception as exc:
                err_msg: str = f"Inspector exception: {exc}"
                await self.log_and_broadcast(username, err_msg, level="ERROR")
                err_update: Optional[dict[str, Optional[str | int]]] = await AccountRepository.update_account_state(
                    account_id=account_id,
                    status="ERROR",
                    lock_type="INSPECTION_FAILED",
                    last_error=str(exc)
                )
                if err_update:
                    await ws_manager.broadcast_account_update(err_update)
            finally:
                self.kill_chrome_tree(chrome_proc)
                try:
                    if profile_dir.exists():
                        shutil.rmtree(profile_dir, ignore_errors=True)
                except Exception:
                    pass
                await asyncio.sleep(0.3)

    async def solve_challenges_zero_cdp(
        self,
        account_id: int,
        username: str,
        debug_port: int,
        login_btn_coords: tuple[int, int] = (630, 445)
    ) -> str:
        detected_type: str = "LOGIN_CHALLENGE"
        hold_attempts: int = 0
        turnstile_clicked: bool = False
        cooldown_until_tick: int = 0
        reclicked_login: bool = False

        for tick in range(45):
            await asyncio.sleep(0.8)

            curr_url: str = self.get_active_tab_url_no_cdp(debug_port)
            if settings.roblox_not_approved_path in curr_url or settings.roblox_home_path in curr_url:
                await self.log_and_broadcast(username, f"Challenge passed! Navigated to {curr_url}")
                return detected_type

            if tick < cooldown_until_tick:
                continue

            screen_btn: Optional[tuple[int, int]] = VisionEngine.find_press_and_hold_on_screen()
            if screen_btn is not None and hold_attempts < 3:
                hold_attempts += 1
                detected_type = "CAPTCHA_V2_PRESS_HOLD"
                await asyncio.sleep(0.85)
                fresh_btn: Optional[tuple[int, int]] = VisionEngine.find_press_and_hold_on_screen() or screen_btn
                await self.log_and_broadcast(
                    username,
                    f"[Captcha V2] Holding Press & Hold at {fresh_btn} until 100% (Attempt {hold_attempts})...",
                    level="WARNING"
                )
                held_sec: float = await HumanMouseController.win32_move_and_hold_until_complete(
                    screen_x=fresh_btn[0],
                    screen_y=fresh_btn[1],
                    is_completed_fn=VisionEngine.is_hold_bar_completed,
                    is_started_fn=VisionEngine.is_hold_bar_started,
                    max_hold_seconds=16.0
                )
                await self.log_and_broadcast(
                    username,
                    f"[Captcha V2] Released at 100% ({held_sec:.2f}s held)! Verifying..."
                )
                shot_v2: str = f"{settings.screenshots_dir}/{username}_after_v2.png"
                VisionEngine.save_desktop_screenshot(shot_v2)
                upd_v2: Optional[dict[str, Optional[str | int]]] = await AccountRepository.update_account_state(
                    account_id=account_id,
                    status="RUNNING",
                    lock_type="CAPTCHA_V2_PRESS_HOLD",
                    challenge_metadata=f"Zero-CDP Win32 Hold ({held_sec:.2f}s)",
                    screenshot_path=f"/screenshots/{username}_after_v2.png"
                )
                if upd_v2:
                    await ws_manager.broadcast_account_update(upd_v2)

                cooldown_until_tick = tick + 8
                continue

            if not turnstile_clicked:
                ts_coords: Optional[tuple[int, int]] = VisionEngine.find_turnstile_on_screen()
                if ts_coords is not None:
                    turnstile_clicked = True
                    detected_type = "CAPTCHA_V1_TURNSTILE"
                    await asyncio.sleep(1.2)
                    await self.log_and_broadcast(
                        username,
                        f"[Captcha V1] Clicking Turnstile at {ts_coords}...",
                        level="WARNING"
                    )
                    await HumanMouseController.win32_move_and_click(ts_coords[0], ts_coords[1])
                    shot_v1: str = f"{settings.screenshots_dir}/{username}_after_v1.png"
                    await asyncio.sleep(1.5)
                    VisionEngine.save_desktop_screenshot(shot_v1)
                    upd_v1: Optional[dict[str, Optional[str | int]]] = await AccountRepository.update_account_state(
                        account_id=account_id,
                        status="RUNNING",
                        lock_type="CAPTCHA_V1_TURNSTILE",
                        challenge_metadata="Zero-CDP Win32 Turnstile Click",
                        screenshot_path=f"/screenshots/{username}_after_v1.png"
                    )
                    if upd_v1:
                        await ws_manager.broadcast_account_update(upd_v1)
                    cooldown_until_tick = tick + 10
                    continue

            if not reclicked_login and hold_attempts == 0 and tick == 7:
                reclicked_login = True
                await self.log_and_broadcast(username, "Re-clicking Login button...", level="WARNING")
                await HumanMouseController.win32_move_and_click(login_btn_coords[0], login_btn_coords[1])

        return detected_type

    async def handle_not_approved_win32(
        self,
        account_id: int,
        username: str
    ) -> None:
        await self.log_and_broadcast(
            username,
            "Reached /not-approved! Waiting for Account Locked modal to render...",
            level="WARNING"
        )
        await asyncio.sleep(2.0)

        continue_coords: Optional[tuple[int, int]] = None
        reloaded_once: bool = False

        for tick in range(45):
            await asyncio.sleep(0.5)
            continue_coords = VisionEngine.find_continue_button_on_screen()
            if continue_coords is not None:
                break

            if not reloaded_once and tick == 16:
                reloaded_once = True
                await self.log_and_broadcast(
                    username,
                    "White screen detected on /not-approved. Clicking Chrome Reload button...",
                    level="WARNING"
                )
                await HumanMouseController.win32_move_and_click(85, 52)
                await asyncio.sleep(2.5)

        target_continue: tuple[int, int] = continue_coords if continue_coords is not None else (750, 539)
        await asyncio.sleep(0.5)
        await self.log_and_broadcast(
            username,
            f"Clicking 'Continue' button at {target_continue} via Win32 Mouse to open Mobile QR..."
        )
        await HumanMouseController.win32_move_and_click(target_continue[0], target_continue[1])

        await asyncio.sleep(2.6)

        for retry_idx in range(2):
            retry_btn: Optional[tuple[int, int]] = VisionEngine.find_continue_button_on_screen()
            if retry_btn is not None:
                await self.log_and_broadcast(
                    username,
                    f"Detected 'Try unlocking again' prompt. Clicking 'Continue' again at {retry_btn} (Retry {retry_idx + 1})...",
                    level="WARNING"
                )
                await HumanMouseController.win32_move_and_click(retry_btn[0], retry_btn[1])
                await asyncio.sleep(2.8)
            else:
                break

        qr_shot_path: str = f"{settings.screenshots_dir}/{username}_qr_modal.png"
        await self.log_and_broadcast(username, "Capturing & decoding Mobile QR code directly from screen...")

        decoded_qr: Optional[str] = VisionEngine.capture_and_decode_qr_from_screen(qr_shot_path)
        if not decoded_qr:
            await asyncio.sleep(2.0)
            decoded_qr = VisionEngine.capture_and_decode_qr_from_screen(qr_shot_path)

        if decoded_qr:
            await self.log_and_broadcast(username, f"DECODED MOBILE QR URL: {decoded_qr}")
        else:
            await self.log_and_broadcast(
                username,
                "QR code cropped and displayed in Dashboard!",
                level="WARNING"
            )

        updated: Optional[dict[str, Optional[str | int]]] = await AccountRepository.update_account_state(
            account_id=account_id,
            status="LOCKED",
            lock_type="MOBILE_QR_LOCK",
            qr_code_url=decoded_qr or "Scan zoomed QR image in preview",
            challenge_metadata="Mobile App QR Verification Ready",
            screenshot_path=f"/screenshots/{username}_qr_modal.png"
        )
        if updated:
            await ws_manager.broadcast_account_update(updated)

        await asyncio.sleep(1.2)


inspector_service: RobloxInspector = RobloxInspector()