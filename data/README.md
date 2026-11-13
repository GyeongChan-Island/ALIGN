# data

센서 측정 데이터(CSV)를 두는 폴더입니다.

## 파일 이름

```
<YYYYMMDD>_<참가자코드>_<세션>.csv      예: 20261120_P1_desk01.csv
<YYYYMMDD>_<참가자코드>_<세션>_labels.csv
```

참가자는 실명 대신 `P1`, `P2`, `P3` 같은 코드로 적습니다. 저장소가 Public입니다.

## 센서 CSV 열 (제안)

| 열 | 단위 | 설명 |
| --- | --- | --- |
| `time_s` | s | 기록 시작부터 경과 시간 |
| `upper_angle` | ° | 흉추(IMU 1, 0x68) pitch |
| `lower_angle` | ° | 요추(IMU 2, 0x69) pitch |
| `label` | - | 0 = 바른 자세, 1 = 불량 자세 (이후 2 = 물건 줍기, 3 = 기지개 등으로 확장) |

원시값이 필요하면 `upper_ax … upper_gz`, `lower_ax … lower_gz`(센서당 가속도 3축 + 자이로 3축, 총 12열)를 추가합니다. 샘플링은 50Hz 이상을 목표로 합니다.

## 라벨 CSV 열 (제안)

| 열 | 설명 |
| --- | --- |
| `start_s` | 동작 시작 시각 (센서 CSV의 `time_s` 기준) |
| `end_s` | 동작 끝 시각 |
| `action` | `slouch`, `turtle_neck`, `pick_up`, `tie_shoes`, `stretch`, `look_back` 등 |

영상과 센서는 기록 시작 때 몸통을 3번 두드린 가속도 스파이크로 맞춥니다.

## 올리지 않는 것

- 촬영 영상과 사진 (`.gitignore`에 등록됨). 영상은 팀 드라이브에 따로 보관합니다.
- 실명, 얼굴 등 개인을 알아볼 수 있는 정보
