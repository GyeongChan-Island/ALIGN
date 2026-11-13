# python

센서 데이터 처리와 자세 판정 AI 모델 노트북 폴더입니다. 지금은 Google Colab에서 실행합니다.

## 노트북

| 노트북 | 내용 |
| --- | --- |
| [01_Posture_AI_Data_Practice](01_Posture_AI_Data_Practice.ipynb) | 50Hz·20초짜리 가상 센서 데이터(흉추·요추 각도, 0 = 중립 / 1 = 전방 굽힘) 생성, 그래프, CSV 저장 |

PR #3에서 리뷰 중:

- `collect_csv.py`: ESP32 로거 출력 → CSV + `summary.json` + `events.txt` 저장 (pyserial)
- 실시간 판정 데모: `train_model.py`(세션 분리 평가 + 학습), `live_predict.py`(시리얼 실시간 판정·CSV 재생), `evaluate_model.py`

예정:

- `02_Posture_AI_CNN_Practice`: 1D CNN 이진 분류. 노션 정리본은 100샘플(2초) 윈도우·25샘플 간격 기준이고, 데모는 겹치지 않는 50샘플(1초) 구간을 씀. 어느 쪽으로 맞출지 정할 것
- 판정 방식 ①②③ 비교와 사람 단위 교차 검증

## 실행

- Colab: GitHub의 노트북 주소에서 `github.com`을 `githubtocolab.com`으로 바꿔 열면 됩니다.
- 로컬: `pip install -r python/requirements.txt` 후 Jupyter로 엽니다. 마지막 셀의 `google.colab` 다운로드 코드는 Colab 전용이라 로컬에서는 건너뜁니다.

## 규칙

- 노트북 이름은 `NN_설명.ipynb`처럼 번호를 붙입니다.
- 커밋 전에 큰 출력(이미지·긴 로그)은 지웁니다 (Colab: 수정 → 모든 출력 지우기).
- 데이터 형식은 [data/README.md](../data/README.md)를 따릅니다. 노트북 01의 가상 데이터(`time_s`, `upper_angle`, `lower_angle`, `label`)는 연습용이고, 실제 로거 CSV는 12채널 원시값입니다.
