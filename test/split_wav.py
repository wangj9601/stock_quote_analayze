#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将单个 WAV 文件按固定时长或均分份数切割，并可直接转为 MP3（压缩）。
也支持将 AAC 文件直接转为 MP3（仅压缩模式）。

依赖：
  - Python 标准库（wave）
  - 若输出 mp3，需要系统已安装 ffmpeg（并在 PATH 中可执行）

用法示例：
  python split_wav.py input.wav -s 30 -o ./out -p clip
      → 默认输出 MP3：./out/clip_001.mp3, clip_002.mp3, ...
  python split_wav.py input.wav -n 5 -o ./out --format wav
      → 输出 WAV：./out/part_001.wav ... part_005.wav（均分为 5 段）
  python split_wav.py input.wav --bitrate 64k
      → 输出更高压缩率 MP3（码率 64k）
  python split_wav.py input.wav --compress-only -o ./out -p voice
      → 不切割，仅压缩生成 ./out/voice.mp3
  python split_wav.py input.aac --compress-only -o ./out -p voice
      → 将 AAC 直接转为 ./out/voice.mp3
  python split_wav.py input.aac --compress-only -o ./out
      → 默认同名输出 ./out/input.mp3
  python split_wav.py --merge a.wav b.aac c.m4a -o ./out -p merged
      → 按顺序合并后输出 ./out/merged.mp3（输入可为 wav/aac/m4a/mp3 等 ffmpeg 可解码格式）
"""

from __future__ import annotations

import argparse
import math
import subprocess
import wave
from pathlib import Path
from typing import List, Tuple


def _num_width(total_parts: int) -> int:
    return max(3, len(str(total_parts)))


def _build_segment_stem(prefix: str, idx: int, width: int) -> str:
    return f"{prefix}_{idx:0{width}d}"


def _ensure_ffmpeg() -> None:
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit(
            "未检测到 ffmpeg，无法输出 mp3。\n"
            "请先安装 ffmpeg 并确保 `ffmpeg` 命令可在终端执行。"
        ) from exc


def _write_wav_file(
    out_path: Path,
    frames: bytes,
    nchannels: int,
    sampwidth: int,
    framerate: int,
    comptype: str,
    compname: str,
) -> None:
    with wave.open(str(out_path), "wb") as out:
        out.setnchannels(nchannels)
        out.setsampwidth(sampwidth)
        out.setframerate(framerate)
        out.setcomptype(comptype, compname)
        out.writeframes(frames)


def _convert_wav_to_mp3(wav_path: Path, mp3_path: Path, bitrate: str) -> None:
    cmd = [
        "ffmpeg",
        "-y",
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(wav_path),
        "-vn",
        "-acodec",
        "libmp3lame",
        "-b:a",
        bitrate,
        str(mp3_path),
    ]
    try:
        subprocess.run(cmd, check=True, timeout=1800)
    except subprocess.TimeoutExpired as exc:
        raise SystemExit(f"ffmpeg 转换超时（>1800秒）：{wav_path.name}") from exc
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"ffmpeg 转换失败：{wav_path.name}") from exc


def compress_only_to_mp3(input_path: Path, output_dir: Path, prefix: str, bitrate: str) -> Path:
    """仅压缩，不切割。"""
    out_path = output_dir / f"{prefix}.mp3"
    _convert_wav_to_mp3(input_path, out_path, bitrate)
    return out_path


def _build_merge_filter_complex(num_inputs: int) -> str:
    """将多路音频统一到 44100Hz 立体声 fltp 后再 concat，避免采样率/声道不一致导致拼接失败。"""
    if num_inputs < 1:
        raise ValueError("合并至少需要 1 个输入")
    branches: List[str] = []
    labels: List[str] = []
    for i in range(num_inputs):
        lab = f"m{i}"
        branches.append(
            f"[{i}:a]aresample=44100:async=1:first_pts=0,"
            f"aformat=sample_fmts=fltp:channel_layouts=stereo[{lab}]"
        )
        labels.append(f"[{lab}]")
    concat = f"{''.join(labels)}concat=n={num_inputs}:v=0:a=1[outa]"
    return ";".join(branches + [concat])


def merge_inputs_to_mp3(
    input_paths: List[Path],
    output_dir: Path,
    prefix: str,
    bitrate: str,
) -> Path:
    """按顺序合并多个音频文件（ffmpeg 可解码的格式），输出单个 MP3。"""
    if not input_paths:
        raise ValueError("未提供任何输入文件")
    _ensure_ffmpeg()
    for p in input_paths:
        if not p.is_file():
            raise SystemExit(f"找不到文件: {p}")
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{prefix}.mp3"
    if len(input_paths) == 1:
        _convert_wav_to_mp3(input_paths[0], out_path, bitrate)
        return out_path
    cmd: List[str] = [
        "ffmpeg",
        "-y",
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
    ]
    for p in input_paths:
        cmd.extend(["-i", str(p)])
    cmd.extend(
        [
            "-filter_complex",
            _build_merge_filter_complex(len(input_paths)),
            "-map",
            "[outa]",
            "-vn",
            "-acodec",
            "libmp3lame",
            "-b:a",
            bitrate,
            str(out_path),
        ]
    )
    try:
        subprocess.run(cmd, check=True, timeout=7200)
    except subprocess.TimeoutExpired as exc:
        raise SystemExit("ffmpeg 合并/编码超时（>7200秒）") from exc
    except subprocess.CalledProcessError as exc:
        raise SystemExit("ffmpeg 合并或转码失败，请确认各文件为有效音频且 ffmpeg 支持该格式") from exc
    return out_path


def _emit_segment(
    output_dir: Path,
    stem: str,
    frames: bytes,
    audio_meta: Tuple[int, int, int, str, str],
    out_format: str,
    mp3_bitrate: str,
) -> None:
    nchannels, sampwidth, framerate, comptype, compname = audio_meta
    wav_path = output_dir / f"{stem}.wav"
    _write_wav_file(wav_path, frames, nchannels, sampwidth, framerate, comptype, compname)
    if out_format == "wav":
        return
    mp3_path = output_dir / f"{stem}.mp3"
    _convert_wav_to_mp3(wav_path, mp3_path, mp3_bitrate)
    wav_path.unlink(missing_ok=True)


def split_wav_by_seconds(
    input_path: Path,
    output_dir: Path,
    prefix: str,
    chunk_seconds: float,
    out_format: str,
    mp3_bitrate: str,
) -> int:
    with wave.open(str(input_path), "rb") as wf:
        nchannels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        nframes = wf.getnframes()
        comptype = wf.getcomptype()
        compname = wf.getcompname()

        if chunk_seconds <= 0:
            raise ValueError("每段时长必须大于 0")

        frames_per_chunk = int(round(framerate * chunk_seconds))
        if frames_per_chunk <= 0:
            raise ValueError("每段过短，请增大 --seconds 或检查采样率")

        total_parts = max(1, math.ceil(nframes / frames_per_chunk))
        width = _num_width(total_parts)
        written = 0
        audio_meta = (nchannels, sampwidth, framerate, comptype, compname)

        for i in range(total_parts):
            start = i * frames_per_chunk
            count = min(frames_per_chunk, nframes - start)
            if count <= 0:
                break
            wf.setpos(start)
            frames = wf.readframes(count)

            stem = _build_segment_stem(prefix, i + 1, width)
            _emit_segment(output_dir, stem, frames, audio_meta, out_format, mp3_bitrate)
            written += 1

        return written


def split_wav_into_parts(
    input_path: Path,
    output_dir: Path,
    prefix: str,
    parts: int,
    out_format: str,
    mp3_bitrate: str,
) -> int:
    if parts < 2:
        raise ValueError("--parts 至少为 2")

    with wave.open(str(input_path), "rb") as wf:
        nchannels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        nframes = wf.getnframes()
        comptype = wf.getcomptype()
        compname = wf.getcompname()

        frames_per_chunk = nframes // parts
        remainder = nframes % parts
        width = _num_width(parts)
        written = 0
        pos = 0
        audio_meta = (nchannels, sampwidth, framerate, comptype, compname)

        for i in range(parts):
            # 余数帧分摊到前几段，使各段尽量均匀
            extra = 1 if i < remainder else 0
            count = frames_per_chunk + extra
            wf.setpos(pos)
            frames = wf.readframes(count)
            pos += count

            stem = _build_segment_stem(prefix, i + 1, width)
            _emit_segment(output_dir, stem, frames, audio_meta, out_format, mp3_bitrate)
            written += 1

        return written


def main() -> None:
    parser = argparse.ArgumentParser(
        description="将 WAV 切割为多个顺序编号的小文件；支持仅压缩、多文件合并转 MP3（依赖 ffmpeg）"
    )
    parser.add_argument(
        "inputs",
        type=Path,
        nargs="+",
        help="输入音频路径：切割模式仅 1 个且须为 .wav；--compress-only 为 1 个 .wav/.aac；"
        "--merge 为多个（顺序合并），格式可为 wav/aac/m4a/mp3 等 ffmpeg 可解码格式",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("."),
        help="输出目录（默认当前目录）",
    )
    parser.add_argument(
        "-p",
        "--prefix",
        default="part",
        help="输出文件名前缀（切割默认 part；仅压缩模式默认输入文件同名；--merge 生成 <前缀>.mp3）",
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=["mp3", "wav"],
        default="mp3",
        help="输出格式（默认 mp3）",
    )
    parser.add_argument(
        "-b",
        "--bitrate",
        default="96k",
        help="MP3 码率（默认 96k；越小越压缩，如 64k）",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--compress-only",
        action="store_true",
        help="仅压缩为一个 mp3 文件，不切割（单输入）",
    )
    mode.add_argument(
        "--merge",
        action="store_true",
        help="将多个输入文件按顺序合并为一个 mp3（支持 wav/aac/m4a/mp3 等）",
    )
    g = parser.add_mutually_exclusive_group()
    g.add_argument(
        "-s",
        "--seconds",
        type=float,
        default=None,
        help="每段时长（秒）；与 --parts 二选一，都不写则默认 60 秒",
    )
    g.add_argument(
        "-n",
        "--parts",
        type=int,
        default=None,
        help="均分为 n 段；与 --seconds 二选一",
    )
    args = parser.parse_args()

    input_paths: List[Path] = list(args.inputs)
    for p in input_paths:
        if not p.is_file():
            raise SystemExit(f"找不到文件: {p}")

    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    out_format: str = args.format
    mp3_bitrate: str = str(args.bitrate).strip() or "96k"

    if out_format == "mp3":
        _ensure_ffmpeg()

    if args.merge:
        if out_format != "mp3":
            raise SystemExit("--merge 模式下 --format 必须为 mp3")
        if len(input_paths) < 2:
            raise SystemExit("--merge 至少需要 2 个输入文件")
        out_mp3 = merge_inputs_to_mp3(input_paths, output_dir, args.prefix, mp3_bitrate)
        print(f"完成：已合并 {len(input_paths)} 个文件 → {out_mp3.resolve()}，码率={mp3_bitrate}")
        return

    input_path = input_paths[0]
    if len(input_paths) > 1:
        raise SystemExit("切割或 --compress-only 模式仅支持单个输入；多文件请使用 --merge")

    ext = input_path.suffix.lower()

    if args.compress_only:
        if out_format != "mp3":
            raise SystemExit("--compress-only 模式下 --format 必须为 mp3")
        if ext not in {".wav", ".aac"}:
            raise SystemExit("--compress-only 仅支持输入 .wav 或 .aac 文件")
        # 原则上同名：仅压缩模式下，若前缀仍为默认值 part，则使用输入文件名（不含扩展名）作为输出名
        output_name = input_path.stem if args.prefix == "part" else args.prefix
        out_mp3 = compress_only_to_mp3(input_path, output_dir, output_name, mp3_bitrate)
        print(f"完成：仅压缩生成 {out_mp3.resolve()}，码率={mp3_bitrate}")
        return

    if ext != ".wav":
        raise SystemExit("切割模式仅支持 .wav 输入；若是 .aac 请使用 --compress-only 转 mp3")

    if args.parts is not None:
        n = split_wav_into_parts(
            input_path,
            output_dir,
            args.prefix,
            args.parts,
            out_format,
            mp3_bitrate,
        )
    else:
        sec = args.seconds if args.seconds is not None else 60.0
        n = split_wav_by_seconds(
            input_path,
            output_dir,
            args.prefix,
            sec,
            out_format,
            mp3_bitrate,
        )

    print(
        f"完成：共写入 {n} 个文件，格式={out_format}，目录：{output_dir.resolve()}"
        + (f"，码率={mp3_bitrate}" if out_format == "mp3" else "")
    )


if __name__ == "__main__":
    main()
