# arduino

ESP32 펌웨어(Arduino 스케치) 폴더입니다.

## 스케치

| 스케치 | 내용 | 필요한 라이브러리 |
| --- | --- | --- |
| [Dual_IMU_Test](Dual_IMU_Test/Dual_IMU_Test.ino) | 1차 실습 코드. MPU6050 2개를 레지스터로 직접 읽어 가속도·자이로 출력 (500ms 간격) | 없음 |
| [Posture_AI_Test](Posture_AI_Test/Posture_AI_Test.ino) | IMU 2개 + DRV2605L 초기화, 두 IMU의 X축 가속도 출력 (1초 간격) | Adafruit MPU6050, Adafruit DRV2605 Library |

## 보드 설정

- 보드: `ESP32 Dev Module` (esp32 by Espressif Systems 3.3.12)
- 시리얼 모니터: 115200 baud
- I2C: SDA = GPIO 21, SCL = GPIO 22, IMU 1 = `0x68`(흉추), IMU 2 = `0x69`(요추)

설치 방법은 [docs/dev-setup.md](../docs/dev-setup.md), 배선은 [docs/hardware.md](../docs/hardware.md)를 보세요.

## 규칙

- 스케치는 `arduino/<이름>/<이름>.ino`처럼 **폴더 이름 = 파일 이름**으로 둡니다. Arduino IDE도 이 구조만 열 수 있고, CI도 이 구조만 빌드합니다.
- 새 라이브러리를 쓰면 [libraries.txt](libraries.txt)에 추가합니다.
- PR을 올리면 GitHub Actions가 모든 스케치를 컴파일합니다 ([워크플로](../.github/workflows/arduino-ci.yml)).
