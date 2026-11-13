# 개발환경 설정

## Arduino (펌웨어)

| 항목 | 설정 |
| --- | --- |
| Arduino IDE | 2.3.10 |
| 보드 패키지 | esp32 by Espressif Systems **3.3.12** |
| 보드 | Tools → Board → esp32 → `ESP32 Dev Module` |
| 시리얼 속도 | 115200 baud |

1. **보드 패키지**: Boards Manager(왼쪽 보드 아이콘)에서 `esp32`를 검색해 *by Espressif Systems* 3.3.12를 설치합니다.
2. **라이브러리**: Library Manager(책 아이콘)에서 아래를 설치합니다. 의존 라이브러리(Adafruit Unified Sensor, Adafruit BusIO)도 함께 설치하겠냐고 물으면 `Install all`을 누릅니다.
   - `Adafruit MPU6050`
   - `Adafruit DRV2605 Library`
3. **컴파일 확인**: 보드가 없어도 왼쪽 위 체크(Verify) 버튼으로 컴파일은 됩니다. 코드를 먼저 짜 볼 수 있습니다.

스케치 저장 경로를 바꾸려면 `Win + R` → `%USERPROFILE%\.arduinoIDE`를 열어 `arduino-cli.yaml`에서 직접 고치는 게 빠릅니다.

### USB 드라이버 (Windows)

ESP32를 꽂아도 COM 포트가 안 보이면 USB-UART 칩 드라이버가 없는 것입니다.

1. 장치 관리자 → 기타 장치의 알 수 없는 장치 → 하드웨어 ID가 `USB\VID_10C4&PID_EA60`이면 Silicon Labs CP210x 칩입니다.
2. Silicon Labs 공식 사이트에서 **CP210x Universal Windows Driver**를 받아 압축을 풀고 `silabser.inf`를 우클릭 → 설치합니다.
3. USB를 뺐다 다시 꽂으면 `포트(COM 및 LPT)` 아래에 `Silicon Labs CP210x USB to UART Bridge (COMx)`가 보입니다.

### 자주 막히는 부분

| 증상 | 원인 | 해결 |
| --- | --- | --- |
| `Could not open COM4, the port is busy or doesn't exist` | 드라이버 미설치 또는 포트 오선택 | 위 드라이버 설치 후 Tools → Port 다시 선택 |
| USB 재연결 후 `not connected` | COM 번호가 바뀜 | 장치 관리자에서 번호 확인 후 Tools → Port 다시 선택 |
| 시리얼 모니터에 아무것도 안 나옴 | 속도 불일치, 업로드 실패 | 115200 baud 확인. LED·센서 없이 `Serial.println`만 하는 코드로 ESP32부터 따로 확인 |
| 센서 `ERROR` / `FAILED` | SDA·SCL 뒤바뀜, 전원, 납땜, 주소 | [hardware.md](hardware.md)의 배선표와 비교 |

## Python (데이터·AI)

당분간은 **Google Colab**을 씁니다. 설치 없이 브라우저에서 바로 실행됩니다.

1. GitHub에서 노트북을 열고, 주소의 `github.com`을 `githubtocolab.com`으로 바꾸면 Colab에서 바로 열립니다.
2. 또는 Colab → 파일 → 노트북 업로드로 `.ipynb`를 올립니다.

로컬에서 돌리려면 Python 3.10 이상에서:

```bash
pip install -r python/requirements.txt
```

ESP32에서 데이터를 받는 로거(`collect_csv.py`)와 실시간 데모는 Windows PC에서 직접 실행하며 `pyserial`이 필요합니다 (`py -m pip install "pyserial>=3.5,<4"`). 실행 전에 Arduino 시리얼 모니터를 닫아야 COM 포트를 열 수 있습니다.
