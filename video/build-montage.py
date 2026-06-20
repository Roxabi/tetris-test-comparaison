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

COLOR_ARGS = [
    "-colorspace", "bt709", "-color_primaries", "bt709",
    "-color_trc", "bt709", "-color_range", "tv",
]

# Panel x-offset and width (px) per layout — source is 2560x1440, 3 or 4 equal columns.
LAYOUTS: dict[str, dict[str, tuple[int, int]]] = {
    "grok_md_opus": {
        "grok": (0, 640),
        "prompt": (640, 640),
        "opus": (1280, 640),
    },
    "grok_md_opus_sonnet": {
        "grok": (0, 480),
        "prompt": (480, 480),
        "opus": (960, 480),
        "sonnet": (1440, 480),
    },
    "grok_opus_sonnet": {
        "grok": (0, 640),
        "opus": (640, 640),
        "sonnet": (1280, 640),
    },
}


def run(cmd: list[str], **kw) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, **kw)


def esc(text: str) -> str:
    text = text.replace("→", "-").replace("·", "-").replace("≠", "!=")
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "")


def panel(layout: str, name: str) -> tuple[int, int]:
    zones = LAYOUTS[layout]
    if name not in zones:
        raise KeyError(f"panel {name!r} not in layout {layout!r}")
    return zones[name]


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


def speed_badge_vf(multiplier: float, start: float = 0) -> str:
    label = f"x{int(multiplier)}" if multiplier >= 10 else f"x{multiplier:.1f}"
    t = esc(label)
    return (
        f"drawtext=fontfile={FONT_MONO}:text='{t}':x=w-150:y=24:"
        f"fontsize=38:fontcolor=0xf97316:box=1:boxcolor=0x000000cc:boxborderw=10:"
        f"enable='gte(t,{start})'"
    )


def panel_timer_vf(layout: str, panel_name: str, label: str, start: float = 0) -> str:
    x, w = panel(layout, panel_name)
    t = esc(label)
    tx = x + w // 2 - 40
    return (
        f"drawtext=fontfile={FONT_MONO}:text='{t}':x={tx}:y=24:"
        f"fontsize=26:fontcolor=white:box=1:boxcolor=0x00000099:boxborderw=8:"
        f"enable='gte(t,{start})'"
    )


def opus_elapsed_timer_vf(layout: str, start_sec: float, speed_mult: float) -> str:
    """Accelerated Opus clock — counts source-time while footage is sped up."""
    x, w = panel(layout, "opus")
    tx = x + w // 2 - 50
    total = f"{start_sec}+t*{speed_mult}"
    return (
        f"drawtext=fontfile={FONT_MONO}:"
        f"text='Opus %{{eif\\:floor(({total})/60)\\:d}}\\:"
        f"%{{eif\\:mod(floor({total}),60)\\:d\\:2}}':"
        f"x={tx}:y=24:fontsize=30:fontcolor=white:"
        f"box=1:boxcolor=0xa855f7cc:boxborderw=8"
    )


def caption_vf(text: str, start: float = 0.5, duration: float = 4) -> str:
    t = esc(text)
    end = start + duration
    return (
        f"drawtext=fontfile={FONT}:text='{t}':x=(w-text_w)/2:y=h-90:"
        f"fontsize=34:fontcolor=white:box=1:boxcolor=0x000000aa:boxborderw=12:"
        f"enable='between(t,{start},{end})'"
    )


def success_overlay_vf(timer: str, panel_name: str, layout: str) -> str:
    x, w = panel(layout, panel_name)
    tx = f"{x}+({w}-text_w)/2"
    t = esc(f"OK {timer}")
    return (
        f"drawbox=x={x}:y=0:w={w}:h=ih:color=0x000000bb:t=fill,"
        f"drawtext=fontfile={FONT}:text='{t}':x={tx}:y=(h-text_h)/2:"
        f"fontsize=48:fontcolor=0x4ade80"
    )


def fail_overlay_vf(layout: str, panel_name: str = "opus") -> str:
    x, w = panel(layout, panel_name)
    tx = f"{x}+({w}-text_w)/2"
    return (
        f"drawbox=x={x}:y=0:w={w}:h=ih:color=0x000000cc:t=fill,"
        f"drawtext=fontfile={FONT}:text='STALL':x={tx}:y=(h-text_h)/2:"
        f"fontsize=56:fontcolor=0xf87171"
    )


def tetris_labels_vf(layout: str) -> str:
    labels = {"grok": "Grok", "opus": "Opus", "sonnet": "Sonnet"}
    parts = []
    for panel_name, name in labels.items():
        if panel_name not in LAYOUTS[layout]:
            continue
        x, w = panel(layout, panel_name)
        parts.append(
            f"drawtext=fontfile={FONT}:text='{esc(name)}':x={x + 16}:y=h-56:"
            f"fontsize=30:fontcolor=white:box=1:boxcolor=0x000000bb:boxborderw=10"
        )
    return ",".join(parts)


def build_extra_vf(seg: dict) -> str:
    extra: list[str] = []
    layout = seg.get("layout", "grok_md_opus")

    if seg.get("caption"):
        dur = seg.get("out", seg["t"]) - 0.3
        extra.append(caption_vf(seg["caption"], 0.3, max(dur, 2)))

    if seg.get("overlay") == "success":
        extra.append(success_overlay_vf(seg["timer"], seg["panel"], layout))
    elif seg.get("overlay") == "fail":
        extra.append(fail_overlay_vf(layout, seg.get("panel", "opus")))
    elif seg.get("overlay") == "reset":
        extra.append(caption_vf(seg.get("caption", "Reset"), 0.2, seg.get("out", 5) - 0.2))

    if seg.get("speed"):
        extra.append(speed_badge_vf(seg["speed"]))

    if seg.get("opus_timer"):
        extra.append(opus_elapsed_timer_vf(
            layout, seg["opus_timer"]["start"], seg["opus_timer"]["mult"],
        ))

    if seg.get("timers"):
        if "grok" in LAYOUTS[layout]:
            extra.append(panel_timer_vf(layout, "grok", "Grok"))
        if "opus" in LAYOUTS[layout]:
            extra.append(panel_timer_vf(layout, "opus", "Opus"))
        if "sonnet" in LAYOUTS[layout]:
            extra.append(panel_timer_vf(layout, "sonnet", "Sonnet"))

    if seg.get("tetris_labels"):
        extra.append(tetris_labels_vf(layout))

    return ",".join(extra)


def extract_segment(
    src: Path, ss: float, t: float, out: Path, out_dur: float, extra_vf: str = "",
) -> None:
    speed = t / out_dur
    pts = f"setpts=PTS/{speed}"
    vf = scale_vf(f"{pts},{extra_vf}" if extra_vf else pts)
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


def extract_speed_ramp(src: Path, parts: list[dict], out: Path, layout: str) -> None:
    """Multi-part segment with increasing speed + cumulative Opus timer."""
    temps: list[Path] = []
    for i, part in enumerate(parts):
        mult = part["t"] / part["out"]
        vf_parts = [speed_badge_vf(mult)]
        if part.get("opus_timer", True):
            vf_parts.append(opus_elapsed_timer_vf(layout, part["timer_start"], mult))
        if part.get("caption"):
            vf_parts.append(caption_vf(part["caption"], 0.2, part["out"] - 0.3))
        vf = scale_vf(f"setpts=PTS/{mult}," + ",".join(vf_parts))
        tmp = TMP / f"_ramp_{out.stem}_{i}.mp4"
        run([
            "ffmpeg", "-y", "-ss", str(part["ss"]), "-i", str(src), "-t", str(part["t"]),
            "-vf", vf, "-an", "-t", str(part["out"]),
            *x264_args(20, "yuv420p"), str(tmp),
        ])
        temps.append(tmp)

    list_file = TMP / f"_ramp_{out.stem}.txt"
    list_file.write_text("\n".join(f"file '{p}'" for p in temps))
    run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
        "-an", "-c", "copy", str(out),
    ])


def make_intro(out: Path, duration: int = 6) -> None:
    """Animated intro — 5-7s with motion + staggered copy."""
    d = duration
    vf = ",".join([
        f"drawbox=x=180+40*sin(2*PI*t/1.2):y=380+20*cos(2*PI*t):w=44:h=44:color=0x00f0f0:t=fill",
        f"drawbox=x=260+40*sin(2*PI*t/1.5+1):y=420+20*sin(2*PI*t):w=44:h=44:color=0x00f0f0:t=fill",
        f"drawbox=x=340+40*cos(2*PI*t/1.1):y=360+30*sin(2*PI*t/0.9):w=44:h=44:color=0x00f0f0:t=fill",
        f"drawbox=x=1500+35*sin(2*PI*t/1.3):y=500+25*cos(2*PI*t):w=44:h=44:color=0xf0f000:t=fill",
        f"drawbox=x=1580+35*cos(2*PI*t):y=540+25*sin(2*PI*t/1.4):w=44:h=44:color=0xf0f000:t=fill",
        f"drawbox=x=900+50*sin(2*PI*t/0.8):y=300+40*cos(2*PI*t/1.6):w=44:h=44:color=0xa000f0:t=fill",
        (
            f"drawtext=fontfile={FONT}:text='TETRIS HTML':x=(w-text_w)/2:y=140:"
            f"fontsize=80:fontcolor=0xf0f0f0:enable='between(t,0.15,{d})'"
        ),
        (
            f"drawtext=fontfile={FONT}:text='Meme brief - 4 modeles':x=(w-text_w)/2:y=230:"
            f"fontsize=38:fontcolor=0x8b95a8:enable='between(t,0.6,{d})'"
        ),
        (
            f"drawtext=fontfile={FONT_MONO}:text='Grok - Opus - Sonnet':x=(w-text_w)/2:y=290:"
            f"fontsize=32:fontcolor=0xf97316:enable='between(t,1.1,{d})'"
        ),
        (
            f"drawtext=fontfile={FONT_MONO}:text='Qui livre le plus vite ?':x=(w-text_w)/2:y=h-120:"
            f"fontsize=30:fontcolor=0x5b8def:enable='between(t,1.8,{d})'"
        ),
        f"drawbox=x=360:y=h-70:w=min(1200\\,t*200):h=5:color=0xf97316:t=fill",
    ])
    run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=0x0c1020:s=1920x1080:d={duration}:r=30",
        "-vf", vf, "-an", *x264_args(20, "yuv420p"), str(out),
    ])


def make_outro(out: Path, duration: int = 10) -> None:
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
            f"fontsize={size}:fontcolor={color}:enable='gte(t,{0.3 + i * 0.5})'"
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
    run([
        "ffmpeg", "-y", "-i", str(master),
        "-an", *x264_args(18, "yuv444p", faststart=True), str(hq),
    ])
    run([
        "ffmpeg", "-y", "-i", str(master),
        "-an", *x264_args(23, "yuv420p", faststart=True), str(compat),
    ])


def process_segment(src: Path, seg: dict, out: Path) -> None:
    if seg.get("type") == "speed_ramp":
        extract_speed_ramp(src, seg["parts"], out, seg.get("layout", "grok_opus_sonnet"))
        return

    extra = build_extra_vf(seg)
    out_dur = seg.get("out", seg["t"])
    if abs(seg["t"] - out_dur) < 0.5:
        extract_segment_1x(src, seg["ss"], seg["t"], out, extra)
    else:
        extract_segment(src, seg["ss"], seg["t"], out, out_dur, extra)


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
            elif sid == "outro":
                make_outro(out, seg["duration"])
            else:
                raise ValueError(f"unknown generated segment: {sid}")
            parts.append(out)
            continue

        process_segment(src, seg, out)
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