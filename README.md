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
IMU 1 (흉추, 0x68) ─┐
                    ├─ I2C ─ ESP32 ─ USB 시리얼 ─ PC 로거 (CSV) ─ 판정 (규칙 / AI)
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
│   └── libraries.txt           CI가 설치하는 Arduino 라이브러리 목록
├── python/                   데이터 처리·AI 모델 (Colab 노트북)
│   ├── 01_Posture_AI_Data_Practice.ipynb
│   └── requirements.txt
├── data/                     측정 데이터 (CSV) 형식 안내
├── docs/                     하드웨어, 개발환경, 실습 계획 문서
└── .github/workflows/        스케치 자동 빌드 (GitHub Actions)
```

## 진행 상황

| 실습 | 단계 | 상태 |
| --- | --- | --- |
| 1차 (11/08) | 개발환경 세팅, MPU6050 2개 동시 연결·데이터 수신 | ✅ 완료 |
| 2차 | 자이로 바이어스 보정, 상보 필터, 상대 각도 계산, CSV 로거 | ⏳ 예정 |
| 3차 | 조끼 장착, 라벨 붙은 착용 데이터 수집 (60분 이상) | ⏳ 예정 |
| 실습 밖 | 판정 방식 ①②③ 구현 및 비교 | ⏳ 예정 |
| 4차 | 평가(오탐률·재현율), 진동 피드백 실시간 데모 | ⏳ 예정 |

세부 계획과 목표 지표는 [docs/roadmap.md](docs/roadmap.md)에 정리되어 있습니다.

## 시작하기

1. 개발환경 설치: [docs/dev-setup.md](docs/dev-setup.md) (Arduino IDE, ESP32 보드 패키지, 라이브러리, USB 드라이버, Colab)
2. 펌웨어: [arduino/README.md](arduino/README.md)
3. 데이터·AI: [python/README.md](python/README.md)

## 협업

팀원은 각자 fork에서 작업한 뒤 PR로 합칩니다. main에 합치려면 다른 팀원 1명의 승인이 필요합니다. 자세한 규칙은 [CONTRIBUTING.md](CONTRIBUTING.md)를 보세요.
