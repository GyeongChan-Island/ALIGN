"""Evaluate a saved ALIGN model on new recordings without retraining it."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile

from common import load_model, predict
from train_model import load_sessions, metrics


def training_manifest(model):
    """Fail closed: a model without provenance cannot establish a fresh test."""
    ids = model.get("training_sessions")
    files = model.get("training_files")
    if (not isinstance(ids, list) or not ids
            or any(not isinstance(x, str) or not x.strip() for x in ids)
            or len(set(ids)) != len(ids)
            or not isinstance(files, list) or not files):
        raise ValueError("모델에 학습 세션/파일 기록이 없습니다. train_model.py로 만든 모델을 사용하세요.")
    recorded_ids, hashes, signal_hashes = set(), set(), set()
    for entry in files:
        if not isinstance(entry, dict) or entry.get("session_id") not in ids:
            raise ValueError("모델의 학습 파일 목록과 세션 목록이 일치하지 않습니다.")
        if entry["session_id"] in recorded_ids:
            raise ValueError("모델의 학습 파일 목록에 세션이 중복되어 있습니다.")
        recorded_ids.add(entry["session_id"])
        for key, dest in (("sha256", hashes), ("signal_sha256", signal_hashes)):
            value = entry.get(key)
            if not isinstance(value, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", value):
                raise ValueError(f"모델의 학습 기록에 유효한 {key}가 없습니다. 새 모델을 학습하세요.")
            dest.add(value.lower())
    if recorded_ids != set(ids):
        raise ValueError("모델의 학습 파일 기록이 일부 누락되어 독립 평가를 확인할 수 없습니다.")
    return set(ids), hashes, signal_hashes


def evaluate_saved(model, sessions):
    train_ids, train_hashes, train_signals = training_manifest(model)
    for session in sessions:
        overlap = []
        if session["session_id"] in train_ids:
            overlap.append("학습 세션 ID")
        if session["sha256"] in train_hashes:
            overlap.append("학습 CSV 파일")
        if session["signal_sha256"] in train_signals:
            overlap.append("학습 센서 기록")
        if overlap:
            raise ValueError(f"{session['file']}: {', '.join(overlap)}와 겹칩니다. 새로 측정한 테스트 CSV만 사용하세요.")
    predictions = []
    for session in sessions:
        for index, feature in enumerate(session["features"]):
            result = predict(feature, model["params"])
            predictions.append({"session_id": session["session_id"],
                                "subject_id": session["subject_id"], "window_index": index,
                                "end_seq": session["window_ends"][index]["seq"],
                                "end_time_us": session["window_ends"][index]["time_us"],
                                "true_label": session["label"],
                                "predicted_label": result["label"],
                                "distance_to_0": result["distances"][0],
                                "distance_to_1": result["distances"][1]})
    votes = []
    for session in sessions:
        rows = [p for p in predictions if p["session_id"] == session["session_id"]]
        positives = sum(p["predicted_label"] for p in rows)
        vote = int(positives * 2 > len(rows)) if positives * 2 != len(rows) else None
        votes.append({"session_id": session["session_id"], "true_label": session["label"],
                      "predicted_label": vote, "tie": vote is None,
                      "windows": len(rows), "votes_label1": positives})
    training_subjects = model.get("training_subjects", [])
    overlap_subjects = sorted({s["subject_id"] for s in sessions} & set(training_subjects))
    return {"evaluation_type": "new_recordings_without_refit", "kind": model["kind"],
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "training_record_overlap": False, "overlapping_subject_ids": overlap_subjects,
            **metrics(predictions), "session_votes_correct": sum(v["predicted_label"] == v["true_label"] for v in votes),
            "session_votes_total": len(votes), "session_votes_tied": sum(v["tie"] for v in votes),
            "session_votes": votes,
            "input_sessions": [{k: v for k, v in s.items() if k not in ("features", "window_ends")}
                               for s in sessions],
            "predictions": predictions,
            "notes": ["재학습 없이 저장된 모델 파라미터로 평가했습니다.",
                      "학습 세션 ID, CSV 해시, 센서값 해시와 일치하는 기록은 거부합니다.",
                      "학습과 같은 피험자 ID가 포함되면 새로운 사람에 대한 성능으로 해석할 수 없습니다.",
                      "해시 비교만으로 CSV의 편집이나 실험 절차의 독립성까지 보증할 수 없습니다.",
                      "라벨 중심까지의 거리는 정답 확률이 아닙니다."]}


def run(args):
    model_path = Path(args.model).expanduser().resolve()
    source = Path(args.data).expanduser().resolve()
    out = Path(args.out).expanduser().resolve()
    if any((out / name).exists() for name in ("evaluation.json", "predictions.csv")):
        raise ValueError("결과 파일이 이미 있습니다. 새로운 --out 폴더를 지정하세요.")
    model = load_model(model_path)
    training_manifest(model)
    sessions = load_sessions(source)
    result = evaluate_saved(model, sessions)
    result["model_sha256"] = hashlib.sha256(model_path.read_bytes()).hexdigest()
    result["model_file"] = model_path.name
    out.mkdir(parents=True, exist_ok=True)
    with (out / "predictions.csv").open("x", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(result["predictions"][0]))
        writer.writeheader()
        writer.writerows(result["predictions"])
    with (out / "evaluation.json").open("x", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, allow_nan=False, indent=2)
        f.write("\n")
    print(f"독립 기록 평가 완료: {len(sessions)}세션, {result['windows']}개의 약 1초 구간")
    print(f"정확도: {result['correct']}/{result['windows']} ({result['accuracy']:.1%})")
    print("혼동행렬 (행=실제 0/1, 열=예측 0/1):")
    for row in result["confusion_matrix_true_rows_predicted_columns"]:
        print(f"  {row}")
    if model["kind"] == "hand":
        print("모델 종류: hand / 손 기울기 상태 구분 연습. 실제 자세 성능이 아닙니다.")
    else:
        print("모델 종류: body / 착용 데이터로 학습한 실험 모델.")
    if result["overlapping_subject_ids"]:
        print("학습과 같은 피험자 ID가 포함됩니다: " + ", ".join(result["overlapping_subject_ids"]))
    if result["recall_label0"] is None or result["recall_label1"] is None:
        print("한쪽 라벨만 평가했습니다. 양쪽 라벨의 새 기록을 추가해 평가하세요.")
    print(f"평가 저장: {out}")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="저장된 ALIGN 모델을 새로운 CSV로 독립 평가")
    parser.add_argument("--model", required=True)
    parser.add_argument("--data", required=True, help="새 테스트 CSV 폴더 또는 ZIP")
    parser.add_argument("--out", required=True, help="새 결과 폴더")
    args = parser.parse_args(argv)
    try:
        run(args)
        return 0
    except (ValueError, TypeError, OSError, csv.Error, zipfile.BadZipFile, RuntimeError) as exc:
        print(f"평가를 완료하지 못했습니다: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
