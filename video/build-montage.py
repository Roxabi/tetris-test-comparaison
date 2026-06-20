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
INTRO_HF = ROOT / "intro-hyperframes"
OUTRO_HF = ROOT / "outro-hyperframes"
BUMPER_HF = ROOT / "bumper-hyperframes"
BADGE_HF = ROOT / "overlay-hyperframes" / "speed-badge"
AUDIO_DIR = ROOT / "assets" / "audio"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"

# OpenMontage color_grade profiles — tools/enhancement/color_grade.py
COLOR_GRADE_PROFILES = {
    "moody_dark": (
        "curves=all='0/0.05 0.15/0.12 0.5/0.45 0.85/0.82 1/0.95',"
        "eq=contrast=1.12:saturation=0.8:brightness=-0.03"
    ),
    "cinematic_cool": (
        "colorbalance=rs=-0.02:gs=-0.03:bs=0.08:rh=0.06:gh=-0.02:bh=-0.06,"
        "curves=all='0/0.02 0.25/0.20 0.5/0.48 0.75/0.78 1/0.98',"
        "eq=contrast=1.08:saturation=1.05"
    ),
}

# Roxabi v1.5 tokens — ~/.roxabi/production/roxabi-presentation/DESIGN.md
ROXABI = {
    "bg": "0x0d1117",
    "panel": "0x13191f",
    "accent": "0xf0b429",
    "text": "0xf0ede6",
    "muted": "0x9ca3af",
    "dim": "0x6b7280",
    "border": "0x21262d",
}

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


def color_grade_vf(profile: str, intensity: float) -> str:
    chain = COLOR_GRADE_PROFILES.get(profile, COLOR_GRADE_PROFILES["moody_dark"])
    if intensity >= 0.99:
        return chain
    return (
        f"split[orig][tg];[tg]{chain}[graded];"
        f"[orig][graded]blend=all_mode=normal:all_opacity={intensity:.2f}"
    )


def build_vf(
    extra: str = "",
    speed: float | None = None,
    grade: dict | None = None,
) -> str:
    parts = [
        "scale=1920:1080:force_original_aspect_ratio=decrease:flags=lanczos",
        "pad=1920:1080:(ow-iw)/2:(oh-ih)/2",
        "setsar=1",
        "fps=30",
    ]
    if speed and abs(speed - 1.0) > 0.01:
        parts.append(f"setpts=PTS/{speed}")
    if grade:
        parts.append(color_grade_vf(grade["profile"], grade.get("intensity", 0.55)))
    if extra:
        parts.append(extra)
    return ",".join(parts)


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
        f"fontsize=38:fontcolor={ROXABI['accent']}:box=1:boxcolor=0x000000cc:boxborderw=10:"
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
        f"fontsize=34:fontcolor=white:box=1:boxcolor=0x000000dd:boxborderw=14:"
        f"enable='between(t,{start},{end})'"
    )


def caption_panel_vf(
    text: str, layout: str, panel_name: str, start: float = 0.3, duration: float = 2,
) -> str:
    """Caption centered on a panel — renders above STALL underlay."""
    x, w = panel(layout, panel_name)
    tx = f"{x}+({w}-text_w)/2"
    t = esc(text)
    end = start + duration
    return (
        f"drawtext=fontfile={FONT}:text='{t}':x={tx}:y=(h-text_h)/2+40:"
        f"fontsize=30:fontcolor=white:box=1:boxcolor=0x000000ee:boxborderw=16:"
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


def build_extra_vf(seg: dict, static_speed_badge: bool = False) -> str:
    """Underlays first, captions last — captions stay above STALL panels."""
    under: list[str] = []
    captions: list[str] = []
    layout = seg.get("layout", "grok_md_opus")

    if seg.get("overlay") == "success":
        under.append(success_overlay_vf(seg["timer"], seg["panel"], layout))
    elif seg.get("overlay") == "fail":
        under.append(fail_overlay_vf(layout, seg.get("panel", "opus")))
    elif seg.get("overlay") == "reset":
        under.append(caption_vf(seg.get("caption", "Reset"), 0.2, seg.get("out", 5) - 0.2))

    if seg.get("opus_timer"):
        under.append(opus_elapsed_timer_vf(
            layout, seg["opus_timer"]["start"], seg["opus_timer"]["mult"],
        ))

    if seg.get("timers"):
        if "grok" in LAYOUTS[layout]:
            under.append(panel_timer_vf(layout, "grok", "Grok"))
        if "opus" in LAYOUTS[layout]:
            under.append(panel_timer_vf(layout, "opus", "Opus"))
        if "sonnet" in LAYOUTS[layout]:
            under.append(panel_timer_vf(layout, "sonnet", "Sonnet"))

    if seg.get("tetris_labels"):
        under.append(tetris_labels_vf(layout))

    if static_speed_badge and seg.get("speed"):
        under.append(speed_badge_vf(seg["speed"]))

    if seg.get("caption") and seg.get("overlay") != "reset":
        dur = seg.get("out", seg["t"]) - 0.3
        if seg.get("caption_panel"):
            captions.append(caption_panel_vf(
                seg["caption"], layout, seg["caption_panel"], 0.3, max(dur, 2),
            ))
        else:
            captions.append(caption_vf(seg["caption"], 0.3, max(dur, 2)))

    return ",".join(under + captions)


def extract_segment(
    src: Path, ss: float, t: float, out: Path, out_dur: float,
    extra_vf: str = "", grade: dict | None = None,
) -> None:
    speed = t / out_dur
    vf = build_vf(extra_vf, speed=speed, grade=grade)
    run([
        "ffmpeg", "-y", "-ss", str(ss), "-i", str(src), "-t", str(t),
        "-vf", vf, "-an", "-t", str(out_dur),
        *x264_args(20, "yuv420p"), str(out),
    ])


def extract_segment_1x(
    src: Path, ss: float, t: float, out: Path,
    extra_vf: str = "", grade: dict | None = None,
) -> None:
    vf = build_vf(extra_vf, grade=grade)
    run([
        "ffmpeg", "-y", "-ss", str(ss), "-i", str(src), "-t", str(t),
        "-vf", vf, "-an", *x264_args(20, "yuv420p"), str(out),
    ])


def speed_label(multiplier: float) -> str:
    return f"x{int(multiplier)}" if multiplier >= 10 else f"x{multiplier:.1f}"


def extract_speed_ramp(
    src: Path, parts: list[dict], out: Path, layout: str, grade: dict | None = None,
) -> None:
    """Multi-part segment with increasing speed + cumulative Opus timer."""
    temps: list[Path] = []
    for i, part in enumerate(parts):
        mult = part["t"] / part["out"]
        under: list[str] = []
        caps: list[str] = []
        if part.get("opus_timer", True):
            under.append(opus_elapsed_timer_vf(layout, part["timer_start"], mult))
        if part.get("caption"):
            caps.append(caption_vf(part["caption"], 0.2, part["out"] - 0.3))
        vf = build_vf(",".join(under + caps), speed=mult, grade=grade)
        tmp = TMP / f"_ramp_{out.stem}_{i}.mp4"
        run([
            "ffmpeg", "-y", "-ss", str(part["ss"]), "-i", str(src), "-t", str(part["t"]),
            "-vf", vf, "-an", "-t", str(part["out"]),
            *x264_args(20, "yuv420p"), str(tmp),
        ])
        composited = TMP / f"_ramp_{out.stem}_{i}_badge.mp4"
        composite_speed_badge(tmp, speed_label(mult), composited)
        temps.append(composited)

    list_file = TMP / f"_ramp_{out.stem}.txt"
    list_file.write_text("\n".join(f"file '{p}'" for p in temps))
    run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
        "-an", "-c", "copy", str(out),
    ])


def render_hyperframes(
    hf_dir: Path,
    out: Path,
    duration: float,
    label: str,
    *,
    variables: dict | None = None,
    fmt: str = "mp4",
) -> bool:
    """HyperFrames: HTML/GSAP → Puppeteer → FFmpeg (roxabi-production stack)."""
    if not (hf_dir / "index.html").exists():
        return False
    ext = "webm" if fmt == "webm" else "mp4"
    raw = TMP / f"{label}_hyperframes_raw.{ext}"
    cmd = [
        "npx", "hyperframes", "render", str(hf_dir),
        "-o", str(raw), "-f", "30", "-q", "high", "--crf", "18", "--quiet",
        "--format", fmt,
    ]
    if variables:
        cmd.extend(["--variables", json.dumps(variables)])
    try:
        run(cmd)
        trim = ["ffmpeg", "-y", "-i", str(raw), "-t", str(duration), "-an"]
        if fmt == "mp4":
            trim.extend(x264_args(20, "yuv420p"))
        else:
            trim.extend(["-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "2M"])
        trim.append(str(out))
        run(trim)
        return True
    except subprocess.CalledProcessError as exc:
        print(f"HyperFrames {label} failed ({exc})", file=sys.stderr)
        return False


_BADGE_CACHE: dict[str, Path] = {}


def ensure_speed_badge_overlay(label: str) -> Path | None:
    if label in _BADGE_CACHE and _BADGE_CACHE[label].exists():
        return _BADGE_CACHE[label]
    out_webm = TMP / f"badge_{label.replace('.', '_')}.webm"
    if render_hyperframes(
        BADGE_HF, out_webm, 2.0, f"badge_{label}",
        variables={"label": label}, fmt="webm",
    ):
        _BADGE_CACHE[label] = out_webm
        return out_webm
    out_mp4 = TMP / f"badge_{label.replace('.', '_')}.mp4"
    if render_hyperframes(
        BADGE_HF, out_mp4, 2.0, f"badge_{label}",
        variables={"label": label}, fmt="mp4",
    ):
        _BADGE_CACHE[label] = out_mp4
        return out_mp4
    return None


def composite_speed_badge(segment: Path, label: str, out: Path) -> None:
    badge = ensure_speed_badge_overlay(label)
    if not badge:
        vf = speed_badge_vf(float(label.lstrip("x")))
        run([
            "ffmpeg", "-y", "-i", str(segment),
            "-vf", vf, "-an", *x264_args(20, "yuv420p"), str(out),
        ])
        return
    if badge.suffix == ".webm":
        filt = (
            "[1]format=rgba,colorchannelmixer=aa=1[badge];"
            "[0][badge]overlay=W-w-30:24:shortest=1"
        )
    else:
        filt = "[0][1]overlay=W-w-30:24:shortest=1"
    run([
        "ffmpeg", "-y", "-i", str(segment),
        "-stream_loop", "-1", "-i", str(badge),
        "-filter_complex", filt,
        "-an", "-shortest",
        *x264_args(20, "yuv420p"), str(out),
    ])


def _probe_duration(path: Path) -> float:
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path),
    ], text=True).strip()
    return float(out)


def make_bumper(out: Path, duration: float = 0.5) -> None:
    if not render_hyperframes(BUMPER_HF, out, duration, "bumper"):
        r = ROXABI
        run([
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", f"color=c={r['bg']}:s=1920x1080:d={duration}:r=30",
            "-vf", (
                f"drawtext=fontfile={FONT}:text='/':x=(w-text_w)/2:y=(h-text_h)/2:"
                f"fontsize=120:fontcolor={r['accent']}"
            ),
            "-an", *x264_args(20, "yuv420p"), str(out),
        ])


def generate_audio_assets() -> dict[str, Path]:
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    assets: dict[str, Path] = {}

    def synth(name: str, cmd: list[str]) -> Path:
        path = AUDIO_DIR / f"{name}.wav"
        if not path.exists():
            run(cmd)
        assets[name] = path
        return path

    dur = 70
    synth("bgm", [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"sine=frequency=55:duration={dur}",
        "-f", "lavfi", "-i", f"sine=frequency=82.5:duration={dur}",
        "-f", "lavfi", "-i", f"anoisesrc=d={dur}:color=brown:amplitude=0.015",
        "-filter_complex",
        "[0][1]amix=inputs=2:duration=first[tones];"
        "[tones][2]amix=inputs=2:duration=first,"
        "lowpass=f=400,volume=0.09,afade=t=in:d=2,afade=t=out:st=68:d=2",
        "-ar", "48000", "-ac", "2", str(AUDIO_DIR / "bgm.wav"),
    ])
    synth("tap", [
        "ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=1400:duration=0.05",
        "-f", "lavfi", "-i", "sine=frequency=2100:duration=0.03",
        "-filter_complex",
        "[0][1]amix=inputs=2:duration=first,afade=t=out:st=0.02:d=0.03,volume=0.45",
        "-ar", "48000", str(AUDIO_DIR / "tap.wav"),
    ])
    synth("whoosh", [
        "ffmpeg", "-y", "-f", "lavfi", "-i", "anoisesrc=d=0.25:color=pink:amplitude=0.12",
        "-af", "lowpass=f=1800,highpass=f=200,afade=t=in:d=0.03,afade=t=out:st=0.15:d=0.1,volume=0.35",
        "-ar", "48000", str(AUDIO_DIR / "whoosh.wav"),
    ])
    synth("chime", [
        "ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=880:duration=0.35",
        "-f", "lavfi", "-i", "sine=frequency=1320:duration=0.25",
        "-filter_complex",
        "[0][1]amix=inputs=2:duration=first,afade=t=out:st=0.15:d=0.2,volume=0.3",
        "-ar", "48000", str(AUDIO_DIR / "chime.wav"),
    ])
    synth("tension", [
        "ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=220:duration=0.4",
        "-af", "afade=t=out:st=0.2:d=0.2,volume=0.22",
        "-ar", "48000", str(AUDIO_DIR / "tension.wav"),
    ])
    return assets


def build_timeline(segments: list[dict]) -> tuple[list[dict], float]:
    timeline: list[dict] = []
    t = 0.0
    for seg in segments:
        if seg.get("type") == "generated":
            dur = float(seg["duration"])
        elif seg.get("type") == "speed_ramp":
            dur = sum(p["out"] for p in seg["parts"])
        else:
            dur = float(seg.get("out", seg["t"]))
        timeline.append({"id": seg["id"], "start": t, "duration": dur})
        t += dur
    return timeline, t


def mix_audio(
    video: Path, out: Path, timeline: list[dict],
    audio_cfg: dict, assets: dict[str, Path],
) -> None:
    bgm_vol = audio_cfg.get("bgm_volume", 0.08)
    bgm = assets["bgm"]
    total = _probe_duration(video)

    seg_start = {row["id"]: row["start"] for row in timeline}
    sfx_events: list[tuple[float, Path, float]] = []
    for ev in audio_cfg.get("sfx", []):
        sid = ev["segment"]
        if sid not in seg_start:
            continue
        t0 = seg_start[sid] + ev.get("offset", 0)
        sound = assets.get(ev["sound"])
        if sound:
            sfx_events.append((t0, sound, ev.get("volume", 0.4)))

    inputs = ["-i", str(video), "-i", str(bgm)]
    for _, sfx, _ in sfx_events:
        inputs.extend(["-i", str(sfx)])

    filters = [f"[1]atrim=0:{total},asetpts=PTS-STARTPTS,volume={bgm_vol}[bgm]"]
    mix_labels = ["[bgm]"]
    for i, (t0, _, vol) in enumerate(sfx_events):
        idx = i + 2
        delay = int(t0 * 1000)
        filters.append(f"[{idx}]adelay={delay}|{delay},volume={vol}[s{i}]")
        mix_labels.append(f"[s{i}]")

    n = len(mix_labels)
    filters.append(
        f"{''.join(mix_labels)}amix=inputs={n}:duration=first:dropout_transition=0[aout]"
    )

    run([
        "ffmpeg", "-y", *inputs,
        "-filter_complex", ";".join(filters),
        "-map", "0:v:0", "-map", "[aout]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
        "-shortest", str(out),
    ])


def make_intro_ffmpeg_fallback(out: Path, duration: int) -> None:
    """Roxabi-styled FFmpeg fallback when HyperFrames is unavailable."""
    d = duration
    r = ROXABI
    vf = ",".join([
        f"drawbox=x=0:y=0:w=iw:h=ih:color={r['bg']}:t=fill",
        (
            f"drawtext=fontfile={FONT_MONO}:text='ROXABI BENCHMARK':x=120:y=72:"
            f"fontsize=22:fontcolor={r['dim']}:enable='between(t,0.1,{d})'"
        ),
        (
            f"drawtext=fontfile={FONT}:text='/':x=120:y=280:"
            f"fontsize=110:fontcolor={r['accent']}:enable='between(t,0.2,{d})'"
        ),
        (
            f"drawtext=fontfile={FONT}:text='Qui livre le plus vite ?':x=220:y=300:"
            f"fontsize=64:fontcolor={r['text']}:enable='between(t,0.4,{d})'"
        ),
        (
            f"drawtext=fontfile={FONT}:text='Meme brief - 3 IA':x=220:y=390:"
            f"fontsize=30:fontcolor={r['muted']}:enable='between(t,0.7,{d})'"
        ),
        (
            f"drawtext=fontfile={FONT_MONO}:text='Grok':x=120:y=520:"
            f"fontsize=36:fontcolor=0xf97316:enable='between(t,1.0,{d})'"
        ),
        (
            f"drawtext=fontfile={FONT_MONO}:text='Opus':x=520:y=520:"
            f"fontsize=36:fontcolor=0xa855f7:enable='between(t,1.2,{d})'"
        ),
        (
            f"drawtext=fontfile={FONT_MONO}:text='Sonnet':x=920:y=520:"
            f"fontsize=36:fontcolor=0x22c55e:enable='between(t,1.4,{d})'"
        ),
        (
            f"drawtext=fontfile={FONT_MONO}:text='tetris.roxabi.dev':x=120:y=h-80:"
            f"fontsize=24:fontcolor={r['accent']}:enable='between(t,1.8,{d})'"
        ),
        f"drawbox=x=120:y=h-50:w=min(600\\,t*120):h=4:color={r['accent']}:t=fill",
    ])
    run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c={r['bg']}:s=1920x1080:d={duration}:r=30",
        "-vf", vf, "-an", *x264_args(20, "yuv420p"), str(out),
    ])


def make_intro(out: Path, duration: int = 5) -> None:
    if not render_hyperframes(INTRO_HF, out, duration, "intro"):
        make_intro_ffmpeg_fallback(out, duration)


def make_outro_ffmpeg_fallback(out: Path, duration: int) -> None:
    r = ROXABI
    rows = [
        ("Grok", "2:00", "Minimal, efficace", "0xf97316", 0.3),
        ("Sonnet", "2:10", "Rapide, bon resultat", "0x22c55e", 0.8),
        ("Opus", "50:30", "Over-engineering", "0xa855f7", 1.3),
    ]
    vf = [
        f"drawbox=x=0:y=0:w=iw:h=ih:color={r['bg']}:t=fill",
        (
            f"drawtext=fontfile={FONT}:text='Le verdict':x=(w-text_w)/2:y=200:"
            f"fontsize=56:fontcolor={r['text']}:enable='between(t,0.2,{duration})'"
        ),
    ]
    for name, timer, note, color, start in rows:
        y = 320 + int(start * 80)
        vf.append(
            f"drawtext=fontfile={FONT}:text='{esc(name)}  {timer}  {note}':"
            f"x=(w-text_w)/2:y={y}:fontsize=34:fontcolor={color}:"
            f"enable='between(t,{start},{duration})'"
        )
    vf.extend([
        (
            f"drawtext=fontfile={FONT}:text='Opus + Ultra != toujours la bonne solution':"
            f"x=(w-text_w)/2:y=620:fontsize=28:fontcolor={r['dim']}:"
            f"enable='between(t,2.0,{duration})'"
        ),
        (
            f"drawtext=fontfile={FONT_MONO}:text='tetris.roxabi.dev':x=(w-text_w)/2:y=h-100:"
            f"fontsize=28:fontcolor={r['accent']}:enable='between(t,2.5,{duration})'"
        ),
    ])
    run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c={r['bg']}:s=1920x1080:d={duration}:r=30",
        "-vf", ",".join(vf), "-an", *x264_args(20, "yuv420p"), str(out),
    ])


def make_outro(out: Path, duration: int = 6) -> None:
    if not render_hyperframes(OUTRO_HF, out, duration, "outro"):
        make_outro_ffmpeg_fallback(out, duration)


def concat(parts: list[Path], out: Path) -> None:
    list_file = TMP / "concat.txt"
    list_file.write_text("\n".join(f"file '{p}'" for p in parts))
    run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
        "-an", "-c", "copy", str(out),
    ])


def export_distribution(master: Path, hq: Path, compat: Path) -> None:
    has_audio = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries",
         "stream=codec_type", "-of", "csv=p=0", str(master)],
        capture_output=True, text=True,
    ).stdout.strip() == "audio"

    audio_args = ["-c:a", "aac", "-b:a", "128k"] if has_audio else ["-an"]
    run([
        "ffmpeg", "-y", "-i", str(master),
        *x264_args(18, "yuv444p", faststart=True), *audio_args, str(hq),
    ])
    run([
        "ffmpeg", "-y", "-i", str(master),
        *x264_args(23, "yuv420p", faststart=True), *audio_args, str(compat),
    ])


def process_segment(src: Path, seg: dict, out: Path, grade: dict | None = None) -> None:
    if seg.get("type") == "speed_ramp":
        extract_speed_ramp(
            src, seg["parts"], out, seg.get("layout", "grok_opus_sonnet"), grade=grade,
        )
        return

    extra = build_extra_vf(seg)
    out_dur = seg.get("out", seg["t"])
    tmp = TMP / f"_{seg['id']}_raw.mp4"
    if abs(seg["t"] - out_dur) < 0.5:
        extract_segment_1x(src, seg["ss"], seg["t"], tmp, extra, grade=grade)
    else:
        extract_segment(src, seg["ss"], seg["t"], tmp, out_dur, extra, grade=grade)

    if seg.get("speed"):
        composite_speed_badge(tmp, speed_label(seg["speed"]), out)
        tmp.unlink(missing_ok=True)
    else:
        out.unlink(missing_ok=True)
        tmp.rename(out)


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
            variant = seg.get("variant", sid)
            if variant == "intro":
                make_intro(out, seg["duration"])
            elif variant == "outro":
                make_outro(out, seg["duration"])
            elif variant == "bumper":
                make_bumper(out, seg["duration"])
            else:
                raise ValueError(f"unknown generated segment: {variant}")
            parts.append(out)
            continue

        grade = cfg.get("color_grade") if not seg.get("no_grade") else None
        process_segment(src, seg, out, grade=grade)
        parts.append(out)

    master_silent = TMP / "master_silent.mp4"
    concat(parts, master_silent)

    timeline, _ = build_timeline(cfg["segments"])
    audio_assets = generate_audio_assets()
    master = TMP / "master.mp4"
    if cfg.get("audio"):
        mix_audio(master_silent, master, timeline, cfg["audio"], audio_assets)
    else:
        master = master_silent

    hq = PROJECT / cfg.get("output", "out/tetris-comparison.mp4")
    compat = PROJECT / cfg.get("output_compat", "out/tetris-comparison-compat.mp4")
    export_distribution(master, hq, compat)

    print(f"\n✓ {hq} ({hq.stat().st_size / 1024 / 1024:.1f} MB, yuv444p HQ)")
    print(f"✓ {compat} ({compat.stat().st_size / 1024 / 1024:.1f} MB, yuv420p compat)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())