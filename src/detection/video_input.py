from typing import Optional
import cv2
import numpy as np


class VideoInput:
    def __init__(self, source, frame_skip: int = 2, loop: bool = True):
        self.source = source
        self.frame_skip = frame_skip
        self.loop = loop
        self.cap: Optional[cv2.VideoCapture] = None
        self._open()

    def _open(self):
        self.cap = cv2.VideoCapture(self.source)
        if not self.cap.isOpened():
            raise RuntimeError(f"Cannot open video source: {self.source}")

    @property
    def fps(self) -> float:
        return self.cap.get(cv2.CAP_PROP_FPS) or 25.0

    @property
    def width(self) -> int:
        return int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))

    @property
    def height(self) -> int:
        return int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    def read(self) -> Optional[np.ndarray]:
        frame = None
        for _ in range(self.frame_skip):
            ret, frame = self.cap.read()
            if not ret:
                if self.loop:
                    self._open()
                    ret, frame = self.cap.read()
                    if not ret:
                        return None
                else:
                    return None
        return frame

    def get_first_frame(self) -> Optional[np.ndarray]:
        saved = self.cap.get(cv2.CAP_PROP_POS_FRAMES)
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        ret, frame = self.cap.read()
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, saved)
        return frame if ret else None

    def release(self):
        if self.cap:
            self.cap.release()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.release()
