# 손 기울기 연습 분석 재현

저장소 루트에서 실행합니다. 원본 데이터는 `data/hand_tilt_practice_01`의 10세션이며, 결과는 Git 추적에서 제외한 `results/hand_tilt_analysis`에 새로 만듭니다.

```powershell
py -m pip install -r python/analysis/requirements.txt
py python/analysis/analyze_align.py
py python/analysis/plot_align.py
```

이 스크립트는 최초 5+5세션 실험을 재현하며 세션 수를 검증합니다. 새로운 데이터 학습은 `python/ALIGN_live_demo/train_model.py`를 사용합니다.

저장소에 포함한 [분석 보고서](../../docs/research/hand_tilt_practice_01/분석보고서.md)는 원본을 변경하지 않은 요약입니다. 보고서의 `analysis.json`은 세션별 통계·평가 기록만 포함하며, 원시 12채널과 시간 배열은 원본 CSV에 한 번만 보관합니다. 위 스크립트의 임시 분석 출력에는 그래프 생성용 배열도 포함됩니다.
