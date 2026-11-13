# ALIGN

> Align the body, align the world.

등(흉추)과 허리(요추)에 IMU를 하나씩 달아 두 지점의 **상대 각도**로 자세를 추정하고, 구부정한 자세가 **일정 시간 이상 이어질 때만** 진동으로 알려 주는 착용형 자세 교정 조끼입니다.

기존 제품은 센서 하나의 기울기와 지속시간만 보기 때문에, 물건 줍기·신발 끈 묶기·기지개처럼 잠깐 몸을 숙이는 동작에도 알림이 울립니다. ALIGN의 목표는 이런 **오탐을 줄이는 것**입니다. 같은 데이터로 세 가지 판정 방식을 비교합니다.

| 방식 | 내용 |
| --- | --- |
| ① 기준선 | 센서 1개의 각도 + 지속시간 (기존 제품과 같은 방식) |
| ② 상대 각도 규칙 | 흉추 − 요추 상대 각도 + 지속시간 |
| ③ AI 분류기 | 시계열 윈도우 특징 / 1D CNN 기반 분류 |

## 시스템 구성

```
IMU 1 (흉추, 0x68) ─┐               50Hz, 12채널
                    ├─ I2C ─ ESP32 ─ USB 시리얼 ─ PC 로거 (CSV) ─ 판정 (규칙 / AI, 약 1초 구간)
IMU 2 (요추, 0x69) ─┘          │
                               └─ DRV2605L ─ 진동 모터 (불량 자세 알림)
```

- MCU: ESP32-WROOM-32 (보드 설정 `ESP32 Dev Module`)
- IMU: MPU6050 (GY-521) × 2, AD0 핀으로 I2C 주소 분리
- 피드백: DRV2605L 햅틱 드라이버 + ERM 진동 모터

부품과 배선은 [docs/hardware.md](docs/hardware.md)에 있습니다.

## 저장소 구조

```
ALIGN/
├── arduino/                  ESP32 펌웨어 (Arduino 스케치)
│   ├── Dual_IMU_Test/          1차 실습: IMU 2개 동시 읽기 (라이브러리 없이 레지스터 직접 접근)
│   ├── Posture_AI_Test/        IMU 2개 + 진동 드라이버 초기화 테스트 (Adafruit 라이브러리)
│   ├── ALIGN_logger/           50Hz·12채널 실측 로거 (S/X 명령)
│   └── libraries.txt           CI가 설치하는 Arduino 라이브러리 목록
├── python/                   데이터 처리·AI 모델 (Colab 노트북)
│   ├── 01_Posture_AI_Data_Practice.ipynb
│   ├── data_logger/           Windows CSV 수집기
│   ├── ALIGN_live_demo/       재학습·실시간 0/1 판정·CSV 재생
│   ├── analysis/              손 기울기 분석 재현 스크립트
│   └── requirements.txt
├── data/                     측정 데이터 (CSV + summary.json + events.txt)와 형식 안내
├── docs/                     하드웨어, 개발환경, 실습 계획 문서
└── .github/workflows/        스케치 자동 빌드 (GitHub Actions)
```

## 진행 상황

| 실습 | 단계 | 상태 |
| --- | --- | --- |
| 1차 (11/08) | 개발환경 세팅, MPU6050 2개 동시 연결·데이터 수신 | ✅ 완료 |
| 실습 밖 (11/13) | 50Hz 데이터 로거, 손 기울기 수집 연습 10세션, 실시간 0/1 판정 데모 | ✅ 손 기울기 연습 검증 완료 (착용 실험 전) |
| 2차 | 자이로 바이어스 보정, 상보 필터, 상대 각도 계산 | ⏳ 예정 |
| 3차 | 조끼 장착, 라벨 붙은 착용 데이터 수집 (60분 이상) | ⏳ 예정 |
| 실습 밖 | 판정 방식 ①②③ 구현 및 비교 | ⏳ 예정 |
| 4차 | 평가(오탐률·재현율), 진동 피드백 실시간 데모 | ⏳ 예정 |

세부 계획과 목표 지표는 [docs/roadmap.md](docs/roadmap.md)에 정리되어 있습니다.

## 시작하기

1. 개발환경 설치: [docs/dev-setup.md](docs/dev-setup.md) (Arduino IDE, ESP32 보드 패키지, 라이브러리, USB 드라이버, Colab)
2. 펌웨어: [arduino/README.md](arduino/README.md)
3. 데이터·AI: [python/README.md](python/README.md)

### Windows에서 바로 실행

저장소를 내려받은 뒤 `python/ALIGN_live_demo` 폴더에서 PowerShell을 엽니다.

```powershell
py -m pip install -r requirements.txt
py live_predict.py --port COM13
```

COM13은 실제 ESP32 포트로 바꿉니다. Arduino 시리얼 모니터와 CSV 수집기는 닫고, 창에서 **실시간 연결**을 누릅니다. ESP32에는 [ALIGN_logger.ino](arduino/ALIGN_logger/ALIGN_logger.ino)가 업로드되어 있어야 합니다. 다음부터는 같은 폴더의 `run_demo.cmd`를 실행해도 됩니다.

학습 모델이 포함되어 있어 재학습 없이 시험할 수 있습니다. **현재 모델은 손으로 센서를 기울인 상태 0/1 구분용**입니다. 실제 착용 데이터로 바꾸는 방법은 [데모 안내](python/ALIGN_live_demo/README_ko.md), 실측 저장은 [로거 안내](python/data_logger/README_ko.md)를 참고합니다.

## 협업

팀원은 각자 fork에서 작업한 뒤 PR로 합칩니다. main에 합치려면 다른 팀원 1명의 승인이 필요합니다. 자세한 규칙은 [CONTRIBUTING.md](CONTRIBUTING.md)를 보세요.
