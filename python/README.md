# python

센서 데이터 처리와 자세 판정 AI 모델 노트북 폴더입니다. 지금은 Google Colab에서 실행합니다.

## 노트북

| 노트북 | 내용 |
| --- | --- |
| [01_Posture_AI_Data_Practice](01_Posture_AI_Data_Practice.ipynb) | 50Hz·20초짜리 가상 센서 데이터(흉추·요추 각도, 0 = 중립 / 1 = 전방 굽힘) 생성, 그래프, CSV 저장 |

예정:

- `02_Posture_AI_CNN_Practice`: 슬라이딩 윈도우(100샘플 = 2초, 간격 25샘플 = 0.5초) + 1D CNN 이진 분류
- 시리얼 로거: ESP32 출력 → 타임스탬프 포함 CSV 저장 (2차 실습 전)
- 판정 방식 ①②③ 비교와 사람 단위 교차 검증

## 실행

- Colab: GitHub의 노트북 주소에서 `github.com`을 `githubtocolab.com`으로 바꿔 열면 됩니다.
- 로컬: `pip install -r python/requirements.txt` 후 Jupyter로 엽니다. 마지막 셀의 `google.colab` 다운로드 코드는 Colab 전용이라 로컬에서는 건너뜁니다.

## 규칙

- 노트북 이름은 `NN_설명.ipynb`처럼 번호를 붙입니다.
- 커밋 전에 큰 출력(이미지·긴 로그)은 지웁니다 (Colab: 수정 → 모든 출력 지우기).
- 데이터 형식은 [data/README.md](../data/README.md)를 따릅니다.
