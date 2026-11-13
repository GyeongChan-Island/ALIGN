"""ALIGN serial collector. Python 3.10+, pyserial. See README_ko.md."""
import argparse
import csv
from datetime import datetime
import json
import math
from pathlib import Path
import re
import time
import uuid

CHANNELS = [f"imu{i}_{axis}_{unit}" for i in (1, 2)
            for axis, unit in (("ax", "g"), ("ay", "g"), ("az", "g"),
                               ("gx", "dps"), ("gy", "dps"), ("gz", "dps"))]
HEADER = ["seq", "time_us"] + CHANNELS


def parse_sample(line):
    parts = line.split(",")
    if len(parts) != 14 or not all(re.fullmatch(r"[0-9]+", x) for x in parts[:2]):
        raise ValueError("column count or integer format")
    seq, ts = map(int, parts[:2])
    values = list(map(float, parts[2:]))
    if not all(math.isfinite(v) for v in values):
        raise ValueError("non-finite value")
    if any(abs(v) > (2.001 if i % 6 < 3 else 250.01) for i, v in enumerate(values)):
        raise ValueError("value outside configured full scale")
    return seq, ts, values


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--list-ports", action="store_true")
    p.add_argument("--port", help="Actual Windows port, e.g. COM5")
    p.add_argument("--label", type=int, choices=(0, 1))
    p.add_argument("--subject", default="P01", help="Anonymous subject ID")
    p.add_argument("--seconds", type=float, default=60)
    p.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "data")
    args = p.parse_args()
    import serial
    from serial.tools import list_ports
    if args.list_ports:
        for port in list_ports.comports():
            print(f"{port.device}: {port.description}")
        return 0
    if not args.port or args.label is None:
        p.error("--port and --label are required (use --list-ports first)")
    if not math.isfinite(args.seconds) or args.seconds <= 0:
        p.error("--seconds must be positive and finite")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", args.subject):
        p.error("--subject: use 1-40 ASCII letters, numbers, _ or -")
    args.out = args.out.expanduser().resolve()
    args.out.mkdir(parents=True, exist_ok=True)
    session = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
    base = args.out / f"{args.subject}_{session}_label{args.label}"
    stats = dict(rows=0, missing_slots=0, malformed=0, read_fail_messages=0,
                 timing_anomalies=0, near_full_scale_rows=0, max_backlog_bytes=0)
    first = last = previous_seq = None
    reason = "duration_complete"
    started = False
    wall_start = None
    ser = None
    print(f"CSV: {base.with_suffix('.csv')}")
    try:
        ser = serial.Serial(args.port, 115200, timeout=0.2, write_timeout=1)
        # Opening a port may reset ESP32. Allow boot/init to finish.
        time.sleep(3)
        ser.write(b"X\n")
        time.sleep(0.2)
        ser.reset_input_buffer()  # only before the session; never inside collection
        with base.with_suffix(".csv").open("x", newline="", encoding="utf-8") as f, \
                base.with_suffix(".events.txt").open("x", encoding="utf-8") as events:
            writer = csv.writer(f)
            writer.writerow(["session_id", "subject_id", "label"] + HEADER)
            ser.write(b"S\n")
            command_time = time.monotonic()
            last_data = command_time
            next_report = command_time + 1
            pending = bytearray()
            while True:
                now = time.monotonic()
                if wall_start is not None and now - wall_start >= args.seconds:
                    break
                if now - last_data > 5:
                    raise RuntimeError("No valid data for 5s; inspect events, power and firmware")
                stats["max_backlog_bytes"] = max(stats["max_backlog_bytes"], ser.in_waiting)
                chunk = ser.read_until(b"\n", 512)
                pending.extend(chunk)
                if len(pending) > 2048:
                    raise RuntimeError("Oversized serial line; check firmware/baud")
                if not pending.endswith(b"\n"):
                    continue
                try:
                    line = pending.decode("ascii").strip()
                except UnicodeDecodeError:
                    stats["malformed"] += 1
                    pending.clear()
                    continue
                pending.clear()
                if line.startswith("#"):
                    events.write(f"{time.monotonic()-command_time:.3f} {line}\n")
                    if line.startswith("#FATAL"):
                        raise RuntimeError(line)
                    if line.startswith("#START"):
                        if started:
                            raise RuntimeError("Unexpected restart: split into a new session")
                        started = True
                    if line.startswith("#READ_FAIL"):
                        stats["read_fail_messages"] += 1
                    continue
                if line == ",".join(HEADER):
                    continue
                if not started:
                    continue
                try:
                    seq, ts, values = parse_sample(line)
                except ValueError:
                    stats["malformed"] += 1
                    events.write(f"INVALID {line}\n")
                    continue
                if previous_seq is not None:
                    if seq <= previous_seq or ts <= last:
                        raise RuntimeError("Sequence/time reversed or duplicated; possible reset")
                    steps = seq - previous_seq
                    stats["missing_slots"] += steps - 1
                    if abs((ts-last) - steps*20000) > 5000:
                        stats["timing_anomalies"] += 1
                else:
                    stats["missing_slots"] += seq
                    first = ts
                    wall_start = time.monotonic()
                previous_seq, last = seq, ts
                last_data = time.monotonic()
                stats["near_full_scale_rows"] += int(any(
                    abs(v) >= (1.98 if i % 6 < 3 else 247.5) for i, v in enumerate(values)))
                writer.writerow([session, args.subject, args.label, seq, ts] + values)
                stats["rows"] += 1
                if time.monotonic() >= next_report:
                    f.flush()
                    events.flush()
                    print(f"rows={stats['rows']} gaps={stats['missing_slots']} invalid={stats['malformed']}")
                    next_report = time.monotonic()+1
    except KeyboardInterrupt:
        reason = "user_stopped"
    except (OSError, RuntimeError, serial.SerialException) as exc:
        reason = f"error: {exc}"
        print(reason)
    finally:
        if ser is not None:
            try:
                ser.write(b"X\n")
            except (OSError, serial.SerialException):
                pass
            ser.close()
        hz = ((stats["rows"]-1)*1e6/(last-first)
              if stats["rows"] > 1 and last > first else None)
        warnings = [k for k in ("missing_slots", "malformed", "read_fail_messages",
                    "timing_anomalies", "near_full_scale_rows") if stats[k]]
        if hz is None or not 49 <= hz <= 51:
            warnings.append("received_rate_outside_49_to_51Hz")
        if stats["max_backlog_bytes"] > 4096:
            warnings.append("serial_backlog_over_4096_bytes")
        summary = dict(session_id=session, subject_id=args.subject, label=args.label,
                       port=args.port, baud=115200, target_hz=50, requested_seconds=args.seconds,
                       reason=reason, received_hz=hz, first_time_us=first, last_time_us=last,
                       units={"acceleration":"g (includes gravity)","gyroscope":"deg/s"},
                       warnings=warnings, **stats)
        base.with_suffix(".summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if reason.startswith("error:") or stats["rows"] == 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
