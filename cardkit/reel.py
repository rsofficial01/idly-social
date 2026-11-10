"""cardkit.reel: a post as a silent 9:16 Instagram Reel, from the same pages as the Story card (cardkit.vertical).

    render_reel(post, out_dir, details=None, report=[])   # <out_dir>/reel.mp4 + reel_cover.jpg (+ preview stills)
    python3 -m cardkit.reel POST.json OUT_DIR [--details 1,2] [--previews]    # exit 1 if anything is wrong

The reel: 1080x1920, 30 fps, H.264 yuv420p (BT.709), faststart, no edit lists, a silent AAC track
(Instagram wants an audio track; there is never anyone else's music or audio), 9-14 s, ffmpeg -preset veryfast:
  * cover ~3.5 s: a slow push-in on the photo (1.00 -> 1.06), the kicker and headline slide up and fade in from 0.4 s;
  * 1-2 of the post's detail slides, re-laid out vertically, ~3 s each, with 8-frame crossfades;
  * an end card ~1.5 s: the account's logo, "idly.news" and the handle.
  reel_cover.jpg (the finished cover frame) is saved for the thumbnail.

Needs ffmpeg (and ffprobe for the checks). probe_reel(path) checks a file against Instagram's Reels spec;
mp4_boxes(path) needs nothing but Python, for the publisher.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
from io import BytesIO

from PIL import Image

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cardkit.render import _hype_slides  # noqa: E402
from cardkit.vertical import (VBG_RGB, VH, VW, _render_pages, _save_jpg, load_post,  # noqa: E402
                              vertical_problems)

__all__ = ['render_reel', 'probe_reel', 'mp4_boxes', 'video_frame', 'timeline', 'pick_details', 'ffmpeg_cmd']

FPS = 30
XFADE = 8                                # frames per crossfade
PUSH_END = 1.06
TEXT_IN_AT, TEXT_IN_FOR, TEXT_SLIDE = 0.4, 0.6, 56
REEL_MIN_S, REEL_MAX_S = 9.0, 14.0
PREVIEW_TIMES = (0.5, 4.0, 7.0, 'last')


# ---- timeline and frames ---------------------------------------------------------------------------------------------------

def pick_details(post: dict, details: list[int] | None = None) -> list[dict]:
    """The detail slides for the reel: `details` are 1-based positions among the post's detail slides
    (default: the first two)."""
    pool = [s for s in _hype_slides(post)[1:] if s.get('type', 'cover') == 'detail']
    if details:
        bad = [n for n in details if not 1 <= int(n) <= len(pool)]
        if bad:
            raise ValueError(f"post {post.get('slug')}: no detail slide {bad} (it has {len(pool)})")
        picked = [pool[int(n) - 1] for n in details]
    else:
        picked = pool[:2]
    if len(picked) > 2:
        raise ValueError("a reel shows at most 2 detail slides")
    return picked


def timeline(n_details: int) -> list[tuple[str, int]]:
    """(segment, frames) at 30 fps. Always 9-14 s in total."""
    if n_details >= 2:
        return [('cover', 105), ('detail1', 90), ('detail2', 90), ('end', 45)]       # 11.0 s
    if n_details == 1:
        return [('cover', 120), ('detail1', 120), ('end', 45)]                       # 9.5 s
    return [('cover', 240), ('end', 45)]                                              # 9.5 s


def _ease_out(t: float) -> float:
    t = min(1.0, max(0.0, t))
    return 1 - (1 - t) ** 3


class ReelFrames:
    """Every frame of the reel, from the rendered pages."""

    def __init__(self, pages: dict, n_details: int):
        self.win = pages['window']
        self.overlay = pages['overlay']
        text = pages['text']
        bbox = text.split()[-1].getbbox() or (0, 0, 1, 1)
        self.text_box = bbox
        self.text = text.crop(bbox)
        self.text_alpha = self.text.split()[-1]
        self.static = {f'detail{i}': im.convert('RGB') for i, im in enumerate(pages['details'], 1)}
        self.static['end'] = pages['end'].convert('RGB')
        self.segments = timeline(n_details)
        self.total = sum(n for _, n in self.segments)
        self.cover_frames = self.segments[0][1]
        self._bg = Image.new('RGB', (VW, VH), VBG_RGB)

    def cover(self, local: int) -> Image.Image:
        t = local / FPS
        z = 1.0 + (PUSH_END - 1.0) * min(1.0, local / max(1, self.cover_frames - 1))
        frame = self._bg.copy()
        frame.paste(self.win.at(z), (0, 0))
        frame = Image.alpha_composite(frame.convert('RGBA'), self.overlay)
        p = (t - TEXT_IN_AT) / TEXT_IN_FOR
        if p > 0:
            a = _ease_out(p)
            dy = round(TEXT_SLIDE * (1 - a))
            layer = self.text
            if a < 1:
                layer = self.text.copy()
                layer.putalpha(self.text_alpha.point(lambda v: round(v * a)))
            frame.alpha_composite(layer, dest=(self.text_box[0], self.text_box[1] + dy))
        return frame.convert('RGB')

    def segment(self, name: str, local: int) -> Image.Image:
        return self.cover(local) if name == 'cover' else self.static[name]

    def frame(self, f: int) -> Image.Image:
        start = 0
        for i, (name, n) in enumerate(self.segments):
            end = start + n
            if f < end or i == len(self.segments) - 1:
                local = f - start
                img = self.segment(name, local)
                if i < len(self.segments) - 1 and f >= end - XFADE:
                    k = f - (end - XFADE) + 1
                    img = Image.blend(img, self.segment(self.segments[i + 1][0], 0), k / (XFADE + 1))
                return img
            start = end
        raise IndexError(f)


def _ffmpeg() -> str:
    exe = shutil.which('ffmpeg')
    if not exe:
        raise RuntimeError("ffmpeg is not installed (the lane-render workflow installs it)")
    return exe


def ffmpeg_cmd(duration: float, out_mp4: str, preset: str = 'veryfast') -> list[str]:
    """Raw RGB frames on stdin -> H.264 high, yuv420p BT.709, 30 fps, closed GOP, faststart, no edit lists, plus a
    silent stereo AAC track (48 kHz, 128 kbps) as long as the video."""
    return [_ffmpeg(), '-hide_banner', '-loglevel', 'error', '-y',
            '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{VW}x{VH}', '-framerate', str(FPS), '-i', 'pipe:0',
            '-f', 'lavfi', '-t', f'{duration:.3f}', '-i', 'anullsrc=channel_layout=stereo:sample_rate=48000',
            '-map', '0:v:0', '-map', '1:a:0',
            '-vf', 'scale=out_color_matrix=bt709:out_range=tv,format=yuv420p',
            '-c:v', 'libx264', '-preset', preset, '-crf', '19', '-profile:v', 'high', '-pix_fmt', 'yuv420p',
            '-g', str(2 * FPS), '-maxrate', '14M', '-bufsize', '28M', '-x264-params', 'open-gop=0',
            '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-color_range', 'tv',
            '-c:a', 'aac', '-b:a', '128k', '-ar', '48000', '-ac', '2',
            '-t', f'{duration:.3f}', '-movflags', '+faststart', '-use_editlist', '0', out_mp4]


def encode(frames: ReelFrames, out_mp4: str, preset: str = 'veryfast') -> None:
    """Pipe every frame to ffmpeg (see ffmpeg_cmd)."""
    cmd = ffmpeg_cmd(frames.total / FPS, out_mp4, preset)
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    static = {id(im): im.tobytes() for im in frames.static.values()}    # held slides: convert once
    try:
        for f in range(frames.total):
            img = frames.frame(f)
            proc.stdin.write(static.get(id(img)) or img.tobytes())
        proc.stdin.close()
    except BrokenPipeError:
        pass
    err = proc.stderr.read().decode(errors='replace')
    if proc.wait() != 0:
        raise RuntimeError(f"ffmpeg failed: {err.strip()[-500:]}")


def mp4_boxes(path: str) -> dict:
    """Top-level MP4 boxes in order, and whether an edit list (elst) is present (Instagram wants none)."""
    order, elst = [], False
    with open(path, 'rb') as f:
        data = f.read()
    i = 0
    while i + 8 <= len(data):
        size = int.from_bytes(data[i:i + 4], 'big')
        kind = data[i + 4:i + 8].decode('latin-1')
        if size == 1:
            size = int.from_bytes(data[i + 8:i + 16], 'big')
        elif size == 0:
            size = len(data) - i
        order.append(kind)
        if kind == 'moov' and b'elst' in data[i:i + size]:
            elst = True
        if size < 8:
            break
        i += size
    return {'boxes': order, 'elst': elst,
            'faststart': 'moov' in order and 'mdat' in order and order.index('moov') < order.index('mdat')}


def probe_reel(path: str) -> dict:
    """What Instagram's Reels spec cares about, and the problems with this file (empty when it's fine)."""
    info = {'path': path, 'bytes': os.path.getsize(path), **mp4_boxes(path)}
    problems = []
    exe = shutil.which('ffprobe')
    if exe:
        r = subprocess.run([exe, '-v', 'error', '-show_streams', '-show_format', '-of', 'json', path],
                           capture_output=True, text=True)
        doc = json.loads(r.stdout or '{}')
        v = next((s for s in doc.get('streams', []) if s.get('codec_type') == 'video'), {})
        a = next((s for s in doc.get('streams', []) if s.get('codec_type') == 'audio'), {})
        num, _, den = (v.get('r_frame_rate') or '0/1').partition('/')
        info.update(video_codec=v.get('codec_name'), width=v.get('width'), height=v.get('height'),
                    pix_fmt=v.get('pix_fmt'), fps=round(int(num) / int(den or 1), 3), profile=v.get('profile'),
                    color_space=v.get('color_space'), audio_codec=a.get('codec_name'),
                    sample_rate=int(a.get('sample_rate') or 0), channels=a.get('channels'),
                    duration=round(float((doc.get('format') or {}).get('duration') or 0), 3),
                    bit_rate=int((doc.get('format') or {}).get('bit_rate') or 0))
        if (info['video_codec'], info['width'], info['height'], info['pix_fmt']) != ('h264', VW, VH, 'yuv420p'):
            problems.append(f"video is {info['video_codec']} {info['width']}x{info['height']} {info['pix_fmt']} "
                            f"(needs h264 {VW}x{VH} yuv420p)")
        if info['fps'] != FPS:
            problems.append(f"{info['fps']} fps (needs {FPS})")
        if info['audio_codec'] != 'aac' or not 0 < info['sample_rate'] <= 48000:
            problems.append(f"audio is {info['audio_codec']} {info['sample_rate']} Hz (needs a silent AAC track, "
                            f"<= 48 kHz)")
        if not REEL_MIN_S - 0.05 <= info['duration'] <= REEL_MAX_S + 0.05:
            problems.append(f"{info['duration']} s long (needs {REEL_MIN_S:g}-{REEL_MAX_S:g} s)")
        if info['bit_rate'] > 25_000_000:
            problems.append(f"bitrate {info['bit_rate']} (max 25 Mbps)")
    else:
        info['note'] = 'ffprobe not installed: codec checks skipped'
    if not info['faststart']:
        problems.append("the moov atom is not at the front (faststart)")
    if info['elst']:
        problems.append("the file has an edit list (Instagram wants none)")
    if info['bytes'] > 300 * 1024 * 1024:
        problems.append("over 300 MB")
    info['problems'] = problems
    return info


def video_frame(path: str, n: int) -> Image.Image | None:
    """Frame n decoded from the encoded file (what viewers get), or None if ffmpeg can't."""
    exe = shutil.which('ffmpeg')
    if not exe:
        return None
    r = subprocess.run([exe, '-v', 'error', '-i', path, '-vf', f'select=eq(n\\,{int(n)})', '-fps_mode', 'passthrough',
                        '-frames:v', '1', '-f', 'image2pipe', '-c:v', 'png', 'pipe:1'], capture_output=True)
    if r.returncode != 0 or not r.stdout:
        return None
    im = Image.open(BytesIO(r.stdout))
    im.load()
    return im.convert('RGB')


def _preview_name(t) -> str:
    return 'preview_last.jpg' if t == 'last' else f'preview_{float(t):04.1f}s.jpg'


def render_reel(post: dict, out_dir: str, details: list[int] | None = None, report: list | None = None,
                previews=PREVIEW_TIMES, verbose: bool = True, base_dir: str | None = None,
                preset: str = 'veryfast') -> dict:
    """Render `post` as a silent 9:16 reel: <out_dir>/reel.mp4, reel_cover.jpg and (previews) stills at the given
    times in seconds ('last' = the last frame). Returns {'video', 'cover', 'previews', 'duration', 'frames',
    'problems'}; the report rows (pages + the reel's probe) go to `report`."""
    os.makedirs(out_dir, exist_ok=True)
    picked = pick_details(post, details)
    rows: list = []
    pages = asyncio.run(_render_pages(post, layers=True, details=picked, end_card=True, base_dir=base_dir,
                                      report=rows, verbose=verbose))
    frames = ReelFrames(pages, len(picked))
    video = os.path.join(out_dir, 'reel.mp4')
    encode(frames, video, preset=preset)
    cover = _save_jpg(pages['cover'], os.path.join(out_dir, 'reel_cover.jpg'))
    shots = []
    for t in previews or ():
        f = frames.total - 1 if t == 'last' else min(frames.total - 1, round(float(t) * FPS))
        shots.append(_save_jpg(video_frame(video, f) or frames.frame(f), os.path.join(out_dir, _preview_name(t))))
    probe = probe_reel(video)
    rows.append({'type': 'reel', 'page': 'reel', 'frames': frames.total, 'segments': frames.segments,
                 'details': len(picked), **probe})
    if report is not None:
        report.extend(rows)
    problems = vertical_problems(rows)
    if verbose:
        print(f"[cardkit:reel] {post['slug']}: {frames.total / FPS:.1f}s, {probe['bytes'] / 1e6:.1f} MB"
              + (f"  PROBLEMS: {'; '.join(problems)}" if problems else ''), file=sys.stderr)
    return {'video': video, 'cover': cover, 'previews': shots, 'duration': frames.total / FPS,
            'frames': frames.total, 'problems': problems}


# ---- CLI ---------------------------------------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog='python3 -m cardkit.reel', description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('post')
    ap.add_argument('out_dir')
    ap.add_argument('--details', help='which detail slides, 1-based, e.g. 1,2 (default: the first two)')
    ap.add_argument('--previews', action='store_true', help='also save stills at 0.5 s, 4 s, 7 s and the last frame')
    a = ap.parse_args(argv)
    details = [int(x) for x in a.details.split(',')] if a.details else None
    res = render_reel(load_post(a.post), a.out_dir, details=details, report=[],
                      base_dir=os.path.dirname(os.path.abspath(a.post)), previews=PREVIEW_TIMES if a.previews else ())
    print(json.dumps({**res, 'ok': not res['problems']}, indent=1))
    return 1 if res['problems'] else 0


if __name__ == '__main__':
    sys.exit(main())
