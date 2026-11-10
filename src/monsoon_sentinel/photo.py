"""Server-side photo verification: does a citizen's photo show flooding?

Runs the same ONNX model the browser uses (MobileNetV3-Small features + logistic head,
trained on Flood10k), so the control room sees an authoritative score.
"""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np

MAX_SIDE = 640  # photos are stored downscaled


def preprocess(img) -> np.ndarray:
    """PIL image -> float32 NCHW in [0, 1], short side 256 then centre crop 224."""
    img = img.convert("RGB")
    w, h = img.size
    s = 256 / min(w, h)
    img = img.resize((max(224, round(w * s)), max(224, round(h * s))))
    w, h = img.size
    left, top = (w - 224) // 2, (h - 224) // 2
    img = img.crop((left, top, left + 224, top + 224))
    x = np.asarray(img, dtype=np.float32) / 255.0
    return x.transpose(2, 0, 1)[None]


class PhotoVerifier:
    def __init__(self, model_path: Path):
        self.model_path = Path(model_path)
        self._sess = None

    @property
    def available(self) -> bool:
        return self.model_path.exists()

    def _session(self):
        if self._sess is None:
            import onnxruntime as ort

            opts = ort.SessionOptions()
            opts.intra_op_num_threads = 1
            opts.enable_mem_pattern = False
            self._sess = ort.InferenceSession(str(self.model_path), opts, providers=["CPUExecutionProvider"])
        return self._sess

    def score(self, image_bytes: bytes) -> float:
        from PIL import Image

        x = preprocess(Image.open(io.BytesIO(image_bytes)))
        sess = self._session()
        out = sess.run(None, {sess.get_inputs()[0].name: x})[0]
        return float(np.ravel(out)[0])


def downscale_jpeg(image_bytes: bytes) -> bytes:
    from PIL import Image, ImageOps

    img = ImageOps.exif_transpose(Image.open(io.BytesIO(image_bytes))).convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=78, optimize=True)  # also strips EXIF (GPS, device data)
    return buf.getvalue()
