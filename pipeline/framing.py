"""Face-aware framing for the official image lane's 1080x1350 hype covers.

    plan = framing.plan_image(img)            # img: PIL RGB, EXIF already applied
    photo, focal, zoom = framing.render_input(img, plan, work_dir)   # what cardkit's hype cover gets

Rules (output pixels of the final 1080x1350 cover):
  * every detected face (padded a little for hair and chin) sits inside y in [FACE_TOP, FACE_BOTTOM]
    = [190, 0.52 * 1350 = 702], fully inside the frame, at least EDGE_MARGIN px from the left/right edges;
  * nothing salient sits under the centred logo (LOGO_BOX, the top ~170 px);
  * no more than MAX_UPSCALE (1.2x) upscaling.

Compositions, in order:
  1. cover:     cardkit's own 4:5 crop (focal + zoom). Zoom only goes up to what MAX_UPSCALE allows.
  2. letterbox: the whole image fitted to 1080 px wide, placed below the logo on a blurred, darkened copy
                of itself (used for 16:9 trailer stills, or when no crop satisfies the rules).
If neither works the spec fails with the reasons.

Faces come from OpenCV's YuNet detector (opencv_zoo, face_detection_yunet_2023mar.onnx), downloaded once
and cached (sha256-checked). Tests use synthetic boxes; nothing here needs a real face to be tested.
"""
from __future__ import annotations

import hashlib
import math
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter

REPO = Path(__file__).resolve().parent.parent

OUT_W, OUT_H = 1080, 1350
ASPECT = OUT_W / OUT_H                     # 0.8
FACE_TOP = 190
FACE_BOTTOM = round(0.52 * OUT_H)          # 702
LOGO_BOX = (330, 0, 750, 170)              # x0, y0, x1, y1: the centred logo (cardkit measures the same box)
LOGO_CLEAR = 170                           # letterbox: the image band starts below this
EDGE_MARGIN = 12                           # px between a face and the left/right edge
FACE_PAD = 0.12                            # pad each face box by 12% of its size on every side
MAX_UPSCALE = 1.2
MIN_SOURCE_W = math.ceil(OUT_W / MAX_UPSCALE)   # 900: below this nothing can pass
ZOOM_STEP = 0.02
MAX_ZOOM = 3.0
SALIENT_LOGO = 2.2                         # logo-box saliency / crop mean above this = "salient under the logo"
LETTERBOX_PREF_TOP = 200                   # preferred band top (just under the logo)

MODEL_NAME = "face_detection_yunet_2023mar.onnx"
MODEL_SHA256 = "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"
MODEL_URLS = (   # the official opencv_zoo repo (the file is in Git LFS, so media.githubusercontent.com serves it)
    "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/" + MODEL_NAME,
    "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/" + MODEL_NAME,
)
MODEL_DIR = Path(os.environ.get("IDLY_MODEL_DIR") or REPO / ".cache" / "models")
SCORE_THRESHOLD = 0.75


class FramingError(Exception):
    """No composition satisfies the rules; .reasons lists why for each one."""

    def __init__(self, reasons: list[str]):
        super().__init__("; ".join(reasons))
        self.reasons = reasons


@dataclass
class Face:
    x: float
    y: float
    w: float
    h: float
    score: float = 1.0

    def box(self) -> tuple[float, float, float, float]:
        return self.x, self.y, self.x + self.w, self.y + self.h


@dataclass
class Plan:
    mode: str                                   # "cover" | "letterbox"
    focal: tuple[float, float] = (0.5, 0.5)     # cover: what cardkit gets
    zoom: float = 1.0
    upscale: float = 1.0                        # output px per source px
    crop: tuple[float, float, float, float] | None = None   # cover: left, top, width, height (source px)
    band_top: int | None = None                 # letterbox: y of the image band
    band_height: int | None = None
    faces_out: list[list[int]] = field(default_factory=list)   # padded face boxes in output px
    logo_saliency: float | None = None
    notes: list[str] = field(default_factory=list)
    faces_src: list[list[float]] = field(default_factory=list)   # detected faces: x, y, w, h, score (source px)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["focal"] = [round(v, 4) for v in self.focal]
        d["zoom"] = round(self.zoom, 3)
        d["upscale"] = round(self.upscale, 3)
        if self.crop:
            d["crop"] = [round(v, 1) for v in self.crop]
        if self.logo_saliency is not None:
            d["logo_saliency"] = round(self.logo_saliency, 2)
        return d


# ---- the face detector ------------------------------------------------------------------------

def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_model(model_dir: Path | None = None) -> Path:
    """The YuNet ONNX model, downloaded from opencv_zoo on first use and cached; sha256-checked."""
    import requests

    model_dir = Path(model_dir or MODEL_DIR)
    path = model_dir / MODEL_NAME
    if path.is_file() and _sha256(path) == MODEL_SHA256:
        return path
    model_dir.mkdir(parents=True, exist_ok=True)
    errors = []
    for url in MODEL_URLS:
        try:
            r = requests.get(url, timeout=60, headers={"User-Agent": "idly-social-lane/1.0"})
            r.raise_for_status()
            if hashlib.sha256(r.content).hexdigest() != MODEL_SHA256:
                errors.append(f"{url}: sha256 mismatch")
                continue
            fd, tmp = tempfile.mkstemp(dir=model_dir, suffix=".tmp")
            with os.fdopen(fd, "wb") as f:
                f.write(r.content)
            os.replace(tmp, path)
            return path
        except Exception as e:  # noqa: BLE001 - try the next mirror
            errors.append(f"{url}: {type(e).__name__}")
    raise RuntimeError("could not download the YuNet face model: " + "; ".join(errors))


def detect_faces(img: Image.Image) -> list[Face]:
    """YuNet face boxes in source pixels. Large images are scaled down for detection and mapped back."""
    import cv2
    import numpy as np

    model = ensure_model()
    scale = min(1.0, 1600 / max(img.size))
    small = img if scale == 1.0 else img.resize((round(img.width * scale), round(img.height * scale)),
                                                Image.LANCZOS)
    bgr = cv2.cvtColor(np.asarray(small.convert("RGB")), cv2.COLOR_RGB2BGR)
    det = cv2.FaceDetectorYN.create(str(model), "", (small.width, small.height), SCORE_THRESHOLD, 0.3, 5000)
    det.setInputSize((small.width, small.height))
    _, faces = det.detect(bgr)
    out = []
    for row in (faces if faces is not None else []):
        x, y, w, h, score = (float(v) for v in (row[0], row[1], row[2], row[3], row[-1]))
        out.append(Face(x / scale, y / scale, w / scale, h / scale, score))
    return out


DETECTOR = detect_faces      # tests swap this for synthetic boxes


# ---- saliency (spectral residual, Hou & Zhang 2007) ---------------------------------------------

def saliency_map(img: Image.Image, width: int = 96):
    """A coarse saliency map (numpy, mean 1.0) and its scale relative to the source."""
    import cv2
    import numpy as np

    h = max(8, round(width * img.height / img.width))
    g = np.asarray(img.convert("L").resize((width, h), Image.BILINEAR), dtype=np.float64)
    f = np.fft.fft2(g)
    log_amp = np.log(np.abs(f) + 1e-9)
    residual = log_amp - cv2.blur(log_amp, (3, 3))
    sal = np.abs(np.fft.ifft2(np.exp(residual + 1j * np.angle(f)))) ** 2
    sal = cv2.GaussianBlur(sal, (0, 0), 2.0)
    mean = sal.mean()
    return (sal / mean if mean > 0 else sal + 1.0), width / img.width


def _region_mean(sal, scale: float, x0: float, y0: float, x1: float, y1: float) -> float:
    h, w = sal.shape
    a, b = max(0, int(x0 * scale)), min(w, max(int(x0 * scale) + 1, math.ceil(x1 * scale)))
    c, d = max(0, int(y0 * scale)), min(h, max(int(y0 * scale) + 1, math.ceil(y1 * scale)))
    region = sal[c:d, a:b]
    return float(region.mean()) if region.size else 0.0


def logo_saliency(sal, scale: float, crop: tuple[float, float, float, float]) -> float:
    """Saliency under the logo box, relative to the whole crop (1.0 = average)."""
    left, top, cw, ch = crop
    s = OUT_W / cw
    lx0, ly0, lx1, ly1 = LOGO_BOX
    under = _region_mean(sal, scale, left + lx0 / s, top + ly0 / s, left + lx1 / s, top + ly1 / s)
    whole = _region_mean(sal, scale, left, top, left + cw, top + ch)
    return under / whole if whole > 0 else 0.0


# ---- geometry -----------------------------------------------------------------------------------

def padded(face: Face, w: int, h: int) -> tuple[float, float, float, float]:
    """The face box padded by FACE_PAD on every side, clipped to the image."""
    x0, y0, x1, y1 = face.box()
    px, py = face.w * FACE_PAD, face.h * FACE_PAD
    return max(0.0, x0 - px), max(0.0, y0 - py), min(float(w), x1 + px), min(float(h), y1 + py)


def cut_by_source_edge(face: Face, w: int, h: int, tol: float = 1.0) -> bool:
    x0, y0, x1, y1 = face.box()
    return x0 <= tol or y0 <= tol or x1 >= w - tol or y1 >= h - tol


def base_crop(w: int, h: int) -> tuple[float, float]:
    """cardkit's largest 4:5 crop at zoom 1 (see cardkit.render._hype_crop)."""
    return (h * ASPECT, float(h)) if w / h > ASPECT else (float(w), w / ASPECT)


def cardkit_crop(w: int, h: int, focal: tuple[float, float], zoom: float) -> tuple[float, float, float, float]:
    """The exact crop cardkit.render._hype_crop takes (left, top, width, height), rounding included."""
    cw0, ch0 = base_crop(w, h)
    zoom = max(1.0, float(zoom or 1.0))
    cw, ch = cw0 / zoom, ch0 / zoom
    fx, fy = focal
    left = min(max(fx * w - cw / 2, 0), w - cw)
    top = min(max(fy * h - ch / 2, 0), h - ch)
    l, t, r, b = round(left), round(top), round(left + cw), round(top + ch)
    return float(l), float(t), float(r - l), float(b - t)


def map_cover(box, crop) -> list[int]:
    left, top, cw, ch = crop
    sx, sy = OUT_W / cw, OUT_H / ch
    x0, y0, x1, y1 = box
    return [round((x0 - left) * sx), round((y0 - top) * sy), round((x1 - left) * sx), round((y1 - top) * sy)]


def face_ok(box_out) -> bool:
    x0, y0, x1, y1 = box_out
    return x0 >= EDGE_MARGIN and x1 <= OUT_W - EDGE_MARGIN and y0 >= FACE_TOP and y1 <= FACE_BOTTOM


def _interval(lo: float, hi: float, constraints: list[tuple[float, float]]) -> tuple[float, float]:
    for a, b in constraints:
        lo, hi = max(lo, a), min(hi, b)
    return lo, hi


def plan_cover(w: int, h: int, faces: list[Face], sal=None, sal_scale: float = 1.0) -> tuple[Plan | None, str]:
    """The least-zoomed cardkit crop that satisfies every rule, or (None, why)."""
    cw0, ch0 = base_crop(w, h)
    zmax = min(MAX_ZOOM, cw0 * MAX_UPSCALE / OUT_W)
    if zmax < 1.0:
        return None, (f"cover: a 4:5 crop is only {cw0:.0f}px wide, {OUT_W / cw0:.2f}x upscale "
                      f"(max {MAX_UPSCALE}x)")
    boxes = [padded(f, w, h) for f in faces]
    if any(cut_by_source_edge(f, w, h) for f in faces):
        return None, "cover: a face is cut off by the edge of the source image"
    why = "cover: no crop keeps every face inside y 190-702 and clear of the edges"
    steps = int(round((zmax - 1.0) / ZOOM_STEP)) + 1
    for i in range(steps):
        z = min(zmax, 1.0 + i * ZOOM_STEP)
        cw, ch = cw0 / z, ch0 / z
        s = OUT_W / cw
        x_lo, x_hi = _interval(0.0, w - cw, [(b[2] - (OUT_W - EDGE_MARGIN) / s, b[0] - EDGE_MARGIN / s)
                                             for b in boxes])
        y_lo, y_hi = _interval(0.0, h - ch, [(b[3] - FACE_BOTTOM / s, b[1] - FACE_TOP / s) for b in boxes])
        if x_lo > x_hi + 1e-6 or y_lo > y_hi + 1e-6:
            continue
        if boxes:
            bx = (min(b[0] for b in boxes) + max(b[2] for b in boxes)) / 2
            by = (min(b[1] for b in boxes) + max(b[3] for b in boxes)) / 2
            pref_left, pref_top = bx - cw / 2, by - ((FACE_TOP + FACE_BOTTOM) / 2) / s
        else:
            pref_left, pref_top = (w - cw) / 2, (h - ch) / 2
        left = min(max(pref_left, x_lo), x_hi)
        tops = [min(max(pref_top, y_lo), y_hi)]
        if sal is not None and y_hi - y_lo > 1:            # alternatives if the logo would sit on something
            tops += [y_lo + (y_hi - y_lo) * k / 6 for k in range(7)]
        best = None
        for top in tops:
            focal = ((left + cw / 2) / w, (top + ch / 2) / h)
            crop = cardkit_crop(w, h, focal, z)
            out = [map_cover(b, crop) for b in boxes]
            if not all(face_ok(o) for o in out):           # rounding pushed a face over a line
                continue
            ls = logo_saliency(sal, sal_scale, crop) if sal is not None else None
            if best is None or (ls is not None and ls < best[3]):
                best = (focal, crop, out, ls if ls is not None else 0.0)
            if ls is None or ls <= SALIENT_LOGO:
                break
        if best is None:
            continue
        focal, crop, out, ls = best
        if sal is not None and ls > SALIENT_LOGO:
            why = (f"cover: something salient sits under the logo in every crop that fits the faces "
                   f"(saliency {ls:.2f}, max {SALIENT_LOGO})")
            continue
        return Plan("cover", focal=focal, zoom=round(z, 3), upscale=OUT_W / crop[2], crop=crop,
                    faces_out=out, logo_saliency=ls if sal is not None else None), ""
    return None, why


def plan_letterbox(w: int, h: int, faces: list[Face]) -> tuple[Plan | None, str]:
    """The whole image fitted to width, below the logo, on a blurred copy of itself."""
    s = OUT_W / w
    if s > MAX_UPSCALE + 1e-9:
        return None, f"letterbox: {w}px wide needs {s:.2f}x upscale (max {MAX_UPSCALE}x)"
    bh = round(h * s)
    if bh > OUT_H - LOGO_CLEAR:
        return None, f"letterbox: the image is too tall to fit below the logo ({bh}px band)"
    if any(cut_by_source_edge(f, w, h) for f in faces):
        return None, "letterbox: a face is cut off by the edge of the source image"
    boxes = [padded(f, w, h) for f in faces]
    if any(b[0] * s < EDGE_MARGIN or b[2] * s > OUT_W - EDGE_MARGIN for b in boxes):
        return None, "letterbox: a face is too close to the left or right edge"
    lo, hi = _interval(float(LOGO_CLEAR), float(OUT_H - bh),
                       [(FACE_TOP - b[1] * s, FACE_BOTTOM - b[3] * s) for b in boxes])
    if lo > hi + 1e-6:
        return None, "letterbox: no band position keeps every face inside y 190-702"
    y0 = round(min(max(LETTERBOX_PREF_TOP, lo), hi))
    out = [[round(b[0] * s), round(b[1] * s) + y0, round(b[2] * s), round(b[3] * s) + y0] for b in boxes]
    if not all(face_ok(o) for o in out):
        y0 = math.ceil(lo) if math.ceil(lo) <= hi else y0
        out = [[round(b[0] * s), round(b[1] * s) + y0, round(b[2] * s), round(b[3] * s) + y0] for b in boxes]
        if not all(face_ok(o) for o in out):
            return None, "letterbox: no band position keeps every face inside y 190-702"
    return Plan("letterbox", upscale=s, band_top=y0, band_height=bh, faces_out=out), ""


def plan_image(img: Image.Image, faces: list[Face] | None = None, use_saliency: bool = True) -> Plan:
    """Detect faces (unless given) and choose a composition; raises FramingError if none fits."""
    faces = DETECTOR(img) if faces is None else faces
    w, h = img.size
    if w < MIN_SOURCE_W:
        raise FramingError([f"image is {w}px wide: below {MIN_SOURCE_W}px nothing fits 1080px "
                            f"at <= {MAX_UPSCALE}x upscale"])
    sal, sal_scale = saliency_map(img) if use_saliency else (None, 1.0)
    found = [[round(f.x, 1), round(f.y, 1), round(f.w, 1), round(f.h, 1), round(f.score, 3)] for f in faces]
    reasons = []
    cover, why = plan_cover(w, h, faces, sal, sal_scale)
    if cover:
        cover.notes.append(f"{len(faces)} face(s) detected")
        cover.faces_src = found
        return cover
    reasons.append(why)
    box, why = plan_letterbox(w, h, faces)
    if box:
        box.notes += [f"{len(faces)} face(s) detected", f"cover rejected: {reasons[0]}"]
        box.faces_src = found
        return box
    reasons.append(why)
    raise FramingError(reasons)


# ---- what cardkit renders ------------------------------------------------------------------------

def compose_letterbox(img: Image.Image, plan: Plan) -> Image.Image:
    """1080x1350: the image fitted to width at plan.band_top, on a blurred, darkened copy of itself."""
    img = img.convert("RGB")
    cover_s = max(OUT_W / img.width, OUT_H / img.height)
    bg = img.resize((math.ceil(img.width * cover_s), math.ceil(img.height * cover_s)), Image.LANCZOS)
    bx, by = (bg.width - OUT_W) // 2, (bg.height - OUT_H) // 2
    bg = bg.crop((bx, by, bx + OUT_W, by + OUT_H))
    bg = bg.resize((OUT_W // 8, OUT_H // 8), Image.BILINEAR).filter(ImageFilter.GaussianBlur(5)) \
        .resize((OUT_W, OUT_H), Image.BICUBIC).filter(ImageFilter.GaussianBlur(12))
    bg = ImageEnhance.Brightness(ImageEnhance.Color(bg).enhance(0.75)).enhance(0.5)
    band = img.resize((OUT_W, plan.band_height), Image.LANCZOS)
    if plan.upscale > 1.15:
        band = band.filter(ImageFilter.UnsharpMask(radius=1.4, percent=55, threshold=2))
    bg.paste(band, (0, plan.band_top))
    return bg


def render_input(img: Image.Image, plan: Plan, work_dir: Path) -> tuple[Path, tuple[float, float], float]:
    """(photo path, focal, zoom) for cardkit's hype cover slide."""
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    if plan.mode == "letterbox":
        path = work_dir / "cover_letterbox.png"
        compose_letterbox(img, plan).save(path)
        return path, (0.5, 0.5), 1.0
    path = work_dir / "cover_source.png"
    img.convert("RGB").save(path)
    return path, plan.focal, plan.zoom
