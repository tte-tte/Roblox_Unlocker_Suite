import logging
from pathlib import Path
from typing import Optional
import cv2
import numpy as np
from PIL import Image, ImageGrab

logger: logging.Logger = logging.getLogger("roblox_suite.vision")


class VisionEngine:
    @staticmethod
    def capture_desktop_region(bbox: tuple[int, int, int, int] = (0, 0, 1280, 880)) -> Optional[np.ndarray]:
        try:
            pil_img: Image.Image = ImageGrab.grab(bbox=bbox)
            rgb_arr: np.ndarray = np.array(pil_img)
            bgr_arr: np.ndarray = cv2.cvtColor(rgb_arr, cv2.COLOR_RGB2BGR)
            return bgr_arr
        except Exception as exc:
            logger.error(f"Desktop screen capture failed: {exc}")
            return None

    @classmethod
    def save_desktop_screenshot(cls, save_path: str) -> None:
        try:
            img: Optional[np.ndarray] = cls.capture_desktop_region((0, 0, 1280, 860))
            if img is not None:
                cv2.imwrite(save_path, img)
        except Exception as exc:
            logger.warning(f"Failed to save desktop screenshot: {exc}")

    @classmethod
    def find_login_button_on_screen(cls) -> Optional[tuple[int, int]]:
        try:
            img: Optional[np.ndarray] = cls.capture_desktop_region((0, 0, 1280, 860))
            if img is None:
                return None

            bg_roi: np.ndarray = img[200:560, 60:340]
            bg_gray: np.ndarray = cv2.cvtColor(bg_roi, cv2.COLOR_BGR2GRAY)
            bg_std: float = float(np.std(bg_gray))
            if bg_std < 22.0:
                return None

            bottom_card_roi: np.ndarray = img[555:625, 490:770]
            bottom_gray: np.ndarray = cv2.cvtColor(bottom_card_roi, cv2.COLOR_BGR2GRAY)
            bottom_mean: float = float(np.mean(bottom_gray))
            if bottom_mean > 48.0 or bottom_mean < 10.0:
                return None

            return (630, 445)
        except Exception as exc:
            logger.error(f"Error locating Login button on screen: {exc}")
            return None

    @classmethod
    def find_press_and_hold_on_screen(cls) -> Optional[tuple[int, int]]:
        try:
            img: Optional[np.ndarray] = cls.capture_desktop_region((0, 0, 1280, 880))
            if img is None:
                return None

            roi_x1: int = 340
            roi_y1: int = 260
            roi_x2: int = 940
            roi_y2: int = 720
            roi: np.ndarray = img[roi_y1:roi_y2, roi_x1:roi_x2]

            hsv: np.ndarray = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
            lower_blue: np.ndarray = np.array([100, 110, 120], dtype=np.uint8)
            upper_blue: np.ndarray = np.array([140, 255, 255], dtype=np.uint8)
            mask: np.ndarray = cv2.inRange(hsv, lower_blue, upper_blue)

            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            best_center: Optional[tuple[int, int]] = None
            max_area: float = 0.0

            for cnt in contours:
                area: float = float(cv2.contourArea(cnt))
                if area > 1200.0 and area > max_area:
                    x, y, w, h = cv2.boundingRect(cnt)
                    if w > 90 and 22 <= h <= 95:
                        inner_box: np.ndarray = roi[y + 4:max(y + 5, y + h - 4), x + 15:max(x + 16, x + w - 15)]
                        gray_box: np.ndarray = cv2.cvtColor(inner_box, cv2.COLOR_BGR2GRAY)
                        _, white_mask = cv2.threshold(gray_box, 200, 255, cv2.THRESH_BINARY)
                        white_pixels: int = int(np.count_nonzero(white_mask))
                        if white_pixels > 160:
                            max_area = area
                            center_x: int = int(roi_x1 + x + (w // 2))
                            center_y: int = int(roi_y1 + y + (h // 2))
                            best_center = (center_x, center_y)

            return best_center
        except Exception as exc:
            logger.error(f"Error finding Press-and-Hold on screen: {exc}")
            return None

    @classmethod
    def find_continue_button_on_screen(cls) -> Optional[tuple[int, int]]:
        try:
            img: Optional[np.ndarray] = cls.capture_desktop_region((0, 0, 1280, 880))
            if img is None:
                return None

            roi_x1: int = 650
            roi_y1: int = 480
            roi_x2: int = 860
            roi_y2: int = 585
            roi: np.ndarray = img[roi_y1:roi_y2, roi_x1:roi_x2]

            hsv: np.ndarray = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
            lower_blue: np.ndarray = np.array([100, 110, 120], dtype=np.uint8)
            upper_blue: np.ndarray = np.array([140, 255, 255], dtype=np.uint8)
            mask: np.ndarray = cv2.inRange(hsv, lower_blue, upper_blue)

            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            best_center: Optional[tuple[int, int]] = None
            max_area: float = 0.0

            for cnt in contours:
                area: float = float(cv2.contourArea(cnt))
                if area > 900.0 and area > max_area:
                    x, y, w, h = cv2.boundingRect(cnt)
                    if w > 80 and 22 <= h <= 75:
                        max_area = area
                        center_x: int = int(roi_x1 + x + (w // 2))
                        center_y: int = int(roi_y1 + y + (h // 2))
                        best_center = (center_x, center_y)

            return best_center
        except Exception as exc:
            logger.error(f"Error finding Continue button on screen: {exc}")
            return None

    @classmethod
    def find_turnstile_on_screen(cls) -> Optional[tuple[int, int]]:
        try:
            img: Optional[np.ndarray] = cls.capture_desktop_region((0, 0, 1280, 880))
            if img is None:
                return None

            roi_x1: int = 440
            roi_y1: int = 380
            roi_x2: int = 840
            roi_y2: int = 620
            roi: np.ndarray = img[roi_y1:roi_y2, roi_x1:roi_x2]

            gray: np.ndarray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray, 225, 255, cv2.THRESH_BINARY)

            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in contours:
                area: float = float(cv2.contourArea(cnt))
                if area > 8000.0:
                    x, y, w, h = cv2.boundingRect(cnt)
                    if 220 <= w <= 340 and 48 <= h <= 85:
                        checkbox_x: int = int(roi_x1 + x + 28)
                        checkbox_y: int = int(roi_y1 + y + (h // 2))
                        return (checkbox_x, checkbox_y)
            return None
        except Exception as exc:
            logger.error(f"Error finding Turnstile on screen: {exc}")
            return None

    @classmethod
    def is_hold_bar_started(cls, screen_x: int, screen_y: int) -> bool:
        try:
            left_crop: Optional[np.ndarray] = cls.capture_desktop_region(
                (max(0, screen_x - 95), max(0, screen_y - 10), max(1, screen_x - 55), screen_y + 10)
            )
            right_crop: Optional[np.ndarray] = cls.capture_desktop_region(
                (screen_x + 55, max(0, screen_y - 10), screen_x + 95, screen_y + 10)
            )
            if left_crop is None or right_crop is None:
                return True

            left_mean: float = float(np.mean(left_crop))
            right_mean: float = float(np.mean(right_crop))
            if abs(right_mean - left_mean) > 6.5 or left_mean < 115.0:
                return True
            return False
        except Exception:
            return True

    @classmethod
    def is_hold_bar_completed(cls, screen_x: int, screen_y: int) -> bool:
        try:
            x1: int = max(0, screen_x - 75)
            y1: int = max(0, screen_y - 12)
            x2: int = screen_x + 75
            y2: int = screen_y + 12
            crop: Optional[np.ndarray] = cls.capture_desktop_region((x1, y1, x2, y2))
            if crop is None:
                return False

            gray: np.ndarray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            _, white_thresh = cv2.threshold(gray, 205, 255, cv2.THRESH_BINARY)
            white_count: int = int(np.count_nonzero(white_thresh))
            return white_count < 20
        except Exception:
            return False

    @staticmethod
    def sharpen_qr_crop(crop_bgr: np.ndarray) -> np.ndarray:
        upscaled: np.ndarray = cv2.resize(crop_bgr, (520, 520), interpolation=cv2.INTER_CUBIC)
        padded: np.ndarray = cv2.copyMakeBorder(
            upscaled, 24, 24, 24, 24, cv2.BORDER_CONSTANT, value=(255, 255, 255)
        )
        return padded

    @classmethod
    def capture_and_decode_qr_from_screen(cls, save_path: str) -> Optional[str]:
        try:
            img: Optional[np.ndarray] = cls.capture_desktop_region((0, 0, 1280, 860))
            if img is None:
                return None

            cv2.imwrite(save_path, img)
            return cls.decode_qr_from_image(save_path)
        except Exception as exc:
            logger.error(f"Screen QR capture error: {exc}")
            return None

    @classmethod
    def decode_qr_from_image(cls, image_path: str) -> Optional[str]:
        try:
            path_obj: Path = Path(image_path)
            if not path_obj.exists():
                return None

            file_bytes: np.ndarray = np.fromfile(str(path_obj), dtype=np.uint8)
            img: Optional[np.ndarray] = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
            if img is None:
                return None

            detector: cv2.QRCodeDetector = cv2.QRCodeDetector()
            h_img, w_img = img.shape[:2]

            modal_crop: np.ndarray = img[
                max(0, int(h_img * 0.22)):min(h_img, int(h_img * 0.80)),
                max(0, int(w_img * 0.32)):min(w_img, int(w_img * 0.68))
            ]

            gray_crop: np.ndarray = cv2.cvtColor(modal_crop, cv2.COLOR_BGR2GRAY)
            _, otsu_crop = cv2.threshold(gray_crop, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            up_2x: np.ndarray = cv2.resize(otsu_crop, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_NEAREST)

            decoded_url: Optional[str] = None
            qr_points: Optional[np.ndarray] = None
            used_scale: float = 1.0

            candidates: list[tuple[np.ndarray, float]] = [
                (modal_crop, 1.0),
                (gray_crop, 1.0),
                (otsu_crop, 1.0),
                (up_2x, 2.0)
            ]

            for candidate_img, scale_factor in candidates:
                data, points, _ = detector.detectAndDecode(candidate_img)
                if data and len(data.strip()) > 0:
                    decoded_url = data.strip()
                    if points is not None:
                        qr_points = points
                        used_scale = scale_factor
                    break

            if qr_points is not None:
                pts: np.ndarray = (qr_points[0] / used_scale).astype(int)
                min_x: int = max(0, int(np.min(pts[:, 0])) - 12)
                min_y: int = max(0, int(np.min(pts[:, 1])) - 12)
                max_x: int = min(modal_crop.shape[1], int(np.max(pts[:, 0])) + 12)
                max_y: int = min(modal_crop.shape[0], int(np.max(pts[:, 1])) + 12)
                tight_qr: np.ndarray = modal_crop[min_y:max_y, min_x:max_x]
                if tight_qr.size > 0:
                    crisp_qr: np.ndarray = cls.sharpen_qr_crop(tight_qr)
                    cv2.imwrite(str(path_obj), crisp_qr)
            else:
                mh, mw = modal_crop.shape[:2]
                center_qr: np.ndarray = modal_crop[
                    int(mh * 0.24):int(mh * 0.76),
                    int(mw * 0.22):int(mw * 0.78)
                ]
                crisp_center: np.ndarray = cls.sharpen_qr_crop(center_qr)
                cv2.imwrite(str(path_obj), crisp_center)

            if decoded_url:
                logger.info(f"Successfully decoded pure QR code: {decoded_url}")
            return decoded_url
        except Exception as exc:
            logger.error(f"OpenCV QR decoding and cropping error: {exc}")
            return None