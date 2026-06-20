#!/usr/bin/env python3
"""Assemble tetris comparison recap video via ffmpeg."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
OUT = PROJECT / "out"
TMP = OUT / "_tmp"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"

# roxabi-production delivery presets — yuv444p for crisp UI text (Chrome/Firefox),
# yuv420p compat for Safari/iOS (High 4:4:4 breaks hardware decode there).
COLOR_ARGS = [
    "-colorspace", "bt709", "-color_primaries", "bt709",
    "-color_trc", "bt709", "-color_range", "tv",
]


def run(cmd: list[str], **kw) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, **kw)


def esc(text: str) -> str:
    text = text.replace("→", "-").replace("·", "-").replace("≠", "!=")
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "")


def scale_vf(extra: str = "") -> str:
    base = (
        "scale=1920:1080:force_original_aspect_ratio=decrease:flags=lanczos,"
        "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30"
    )
    return f"{base},{extra}" if extra else base


def x264_args(crf: int, pix_fmt: str, faststart: bool = False) -> list[str]:
    args = [
        "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
        "-pix_fmt", pix_fmt, *COLOR_ARGS,
    ]
    if faststart:
        args.extend(["-movflags", "+faststart"])
    return args


def panel_timer_vf(start: float, label: str, x: str) -> str:
    """Corner timer style A for one panel third."""
    t = esc(label)
    return (
        f"drawtext=fontfile={FONT_MONO}:text='{t}':x={x}:y=24:"
        f"fontsize=28:fontcolor=white:box=1:boxcolor=0x00000099:boxborderw=8:"
        f"enable='gte(t,{start})'"
    )


def caption_vf(text: str, start: float = 0.5, duration: float = 4) -> str:
    t = esc(text)
    end = start + duration
    return (
        f"drawtext=fontfile={FONT}:text='{t}':x=(w-text_w)/2:y=h-90:"
        f"fontsize=34:fontcolor=white:box=1:boxcolor=0x000000aa:boxborderw=12:"
        f"enable='between(t,{start},{end})'"
    )


def success_overlay_vf(timer: str, panel: str) -> str:
    """Success A: dark overlay + check + time on one panel."""
    zones = {
        "grok": ("0", "640", "240"),
        "opus": ("640", "640", "800"),
        "sonnet": ("1280", "640", "1360"),
    }
    x, w, tx = zones.get(panel, zones["grok"])
    t = esc(f"OK {timer}")
    return (
        f"drawbox=x={x}:y=0:w={w}:h=ih:color=0x000000bb:t=fill,"
        f"drawtext=fontfile={FONT}:text='{t}':x={tx}:y=(h-text_h)/2:"
        f"fontsize=52:fontcolor=0x4ade80"
    )


def fail_overlay_vf() -> str:
    """Fail B: STALL full screen on center panel (Opus)."""
    return (
        "drawbox=x=640:y=0:w=640:h=ih:color=0x000000cc:t=fill,"
        f"drawtext=fontfile={FONT}:text='STALL':x=(w-text_w)/2:y=(h-text_h)/2:"
        "fontsize=72:fontcolor=0xf87171"
    )


def extract_segment(src: Path, ss: float, t: float, out: Path, out_dur: float, extra_vf: str = "") -> None:
    speed = t / out_dur
    vf = scale_vf(f"setpts=PTS/{speed},{extra_vf}" if extra_vf else f"setpts=PTS/{speed}")
    run([
        "ffmpeg", "-y", "-ss", str(ss), "-i", str(src), "-t", str(t),
        "-vf", vf, "-an", "-t", str(out_dur),
        *x264_args(20, "yuv420p"), str(out),
    ])


def extract_segment_1x(src: Path, ss: float, t: float, out: Path, extra_vf: str = "") -> None:
    vf = scale_vf(extra_vf)
    run([
        "ffmpeg", "-y", "-ss", str(ss), "-i", str(src), "-t", str(t),
        "-vf", vf, "-an", *x264_args(20, "yuv420p"), str(out),
    ])


def make_intro(out: Path, duration: int = 12) -> None:
    """Intro B: retro tetris pixel style."""
    vf = (
        f"drawbox=x=200:y=200:w=40:h=40:color=0x00f0f0:t=fill,"
        f"drawbox=x=240:y=200:w=40:h=40:color=0x00f0f0:t=fill,"
        f"drawbox=x=280:y=200:w=40:h=40:color=0x00f0f0:t=fill,"
        f"drawbox=x=320:y=200:w=40:h=40:color=0x00f0f0:t=fill,"
        f"drawbox=x=880:y=320:w=40:h=40:color=0xf0f000:t=fill,"
        f"drawbox=x=920:y=320:w=40:h=40:color=0xf0f000:t=fill,"
        f"drawbox=x=880:y=360:w=40:h=40:color=0xf0f000:t=fill,"
        f"drawbox=x=920:y=360:w=40:h=40:color=0xf0f000:t=fill,"
        f"drawbox=x=1400:y=440+20*sin(2*PI*t):w=40:h=40:color=0xa000f0:t=fill,"
        f"drawtext=fontfile={FONT}:text='TETRIS HTML':x=(w-text_w)/2:y=120:fontsize=72:fontcolor=0xf0f0f0,"
        f"drawtext=fontfile={FONT}:text='meme brief - 3 IA':x=(w-text_w)/2:y=200:fontsize=36:fontcolor=0x8b95a8,"
        f"drawtext=fontfile={FONT_MONO}:text='Grok vs Opus vs Sonnet':x=(w-text_w)/2:y=h-100:fontsize=28:fontcolor=0xf97316"
    )
    run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=0x0c1020:s=1920x1080:d={duration}:r=30",
        "-vf", vf, "-an", *x264_args(20, "yuv420p"), str(out),
    ])


def make_ellipsis(out: Path, duration: int = 5) -> None:
    """Ellipsis B: accelerated timer 11:50 to 44:20."""
    vf = (
        "drawtext=fontfile=" + FONT + ":text='Pendant ce temps, Opus tourne encore...':x=(w-text_w)/2:y=h/2-80:fontsize=40:fontcolor=white,"
        "drawtext=fontfile=" + FONT_MONO + ":text='11:50':x=(w-text_w)/2-120:y=h/2+10:fontsize=56:fontcolor=0x8b95a8,"
        "drawtext=fontfile=" + FONT_MONO + ":text='44:20':x=(w-text_w)/2+120:y=h/2+10:fontsize=56:fontcolor=0xa855f7,"
        "drawtext=fontfile=" + FONT + ":text='>>':x=(w-text_w)/2:y=h/2+20:fontsize=48:fontcolor=0xa855f7"
    )
    run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=0x0c1020:s=1920x1080:d={duration}:r=30",
        "-vf", vf, "-an", *x264_args(20, "yuv420p"), str(out),
    ])


def make_outro(out: Path, duration: int = 12) -> None:
    lines = [
        ("Grok - 2 min - minimal, efficace", "0xf97316", 40),
        ("Sonnet - 2:10 - rapide, bon resultat", "0x22c55e", 40),
        ("Opus - 50 min - over-engineering", "0xa855f7", 40),
        ("Opus + Ultra != toujours la bonne solution", "0x8b95a8", 36),
        ("tetris.roxabi.dev", "0x5b8def", 52),
    ]
    vf_parts = []
    for i, (line, color, size) in enumerate(lines):
        y = 280 + i * 72
        vf_parts.append(
            f"drawtext=fontfile={FONT}:text='{esc(line)}':x=(w-text_w)/2:y={y}:"
            f"fontsize={size}:fontcolor={color}:enable='gte(t,{0.4 + i * 0.6})'"
        )
    run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=0x0c1020:s=1920x1080:d={duration}:r=30",
        "-vf", ",".join(vf_parts), "-an", *x264_args(20, "yuv420p"), str(out),
    ])


def concat(parts: list[Path], out: Path) -> None:
    list_file = TMP / "concat.txt"
    list_file.write_text("\n".join(f"file '{p}'" for p in parts))
    run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
        "-an", "-c", "copy", str(out),
    ])


def export_distribution(master: Path, hq: Path, compat: Path) -> None:
    """Master (yuv420p segments) → HQ yuv444p + Safari-safe yuv420p compat."""
    run([
        "ffmpeg", "-y", "-i", str(master),
        "-an", *x264_args(18, "yuv444p", faststart=True), str(hq),
    ])
    run([
        "ffmpeg", "-y", "-i", str(master),
        "-an", *x264_args(23, "yuv420p", faststart=True), str(compat),
    ])


def main() -> int:
    cfg = json.loads((ROOT / "video-config.json").read_text())
    src = Path(cfg["source"])
    if not src.is_absolute():
        src = PROJECT / src
    if not src.exists():
        print(f"Missing source: {src}", file=sys.stderr)
        return 1

    OUT.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)
    parts: list[Path] = []

    for seg in cfg["segments"]:
        sid = seg["id"]
        out = TMP / f"{sid}.mp4"

        if seg.get("type") == "generated":
            if sid == "intro":
                make_intro(out, seg["duration"])
            elif sid == "ellipsis":
                make_ellipsis(out, seg["duration"])
            elif sid == "outro":
                make_outro(out, seg["duration"])
            else:
                raise ValueError(sid)
            parts.append(out)
            continue

        extra = []
        if seg.get("caption"):
            extra.append(caption_vf(seg["caption"]))
        if seg.get("overlay") == "success":
            extra.append(success_overlay_vf(seg["timer"], seg["panel"]))
        elif seg.get("overlay") == "fail":
            extra.append(fail_overlay_vf())
        elif seg.get("overlay") == "reset":
            extra.append(caption_vf(seg.get("caption", "Reset"), 0.2, seg.get("out", 5) - 0.2))
        if seg.get("timers"):
            extra.extend([
                panel_timer_vf(0, "Grok", "500"),
                panel_timer_vf(0, "Opus", "1180"),
            ])

        vf = ",".join(extra)
        out_dur = seg.get("out", seg["t"])
        if abs(seg["t"] - out_dur) < 0.5:
            extract_segment_1x(src, seg["ss"], seg["t"], out, vf)
        else:
            extract_segment(src, seg["ss"], seg["t"], out, out_dur, vf)
        parts.append(out)

    master = TMP / "master.mp4"
    concat(parts, master)

    hq = PROJECT / cfg.get("output", "out/tetris-comparison.mp4")
    compat = PROJECT / cfg.get("output_compat", "out/tetris-comparison-compat.mp4")
    export_distribution(master, hq, compat)

    print(f"\n✓ {hq} ({hq.stat().st_size / 1024 / 1024:.1f} MB, yuv444p HQ)")
    print(f"✓ {compat} ({compat.stat().st_size / 1024 / 1024:.1f} MB, yuv420p compat)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())