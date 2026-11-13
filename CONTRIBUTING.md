# 협업 규칙

원본 저장소 `GyeongChan-Island/ALIGN`(upstream)을 두고, 각자 자기 fork(origin)에서 작업한 뒤 PR로 합칩니다.

## 꼭 지킬 것

- 원본(upstream)에는 직접 push하지 않습니다. push는 항상 내 fork(`origin`)로 하고, 원본에는 PR로만 들어갑니다.
- main에 합치려면 **다른 팀원 1명의 승인**이 필요합니다. 내 PR은 내가 승인할 수 없습니다.
- 승인된 PR은 팀원 누구나 머지할 수 있습니다.
- 저장소가 Public이므로 이름·학번·연락처 같은 개인정보, 얼굴이 나온 사진·영상은 올리지 않습니다.

## 최초 세팅 (한 번)

1. `https://github.com/GyeongChan-Island/ALIGN`에서 **Fork** (Owner는 내 개인 계정)
2. 빈 상위 폴더에서 내 fork를 clone

   ```bash
   git clone https://github.com/<내ID>/ALIGN.git
   ```

3. 생긴 `ALIGN` 폴더를 VS Code로 열고 upstream 등록

   ```bash
   git remote add upstream https://github.com/GyeongChan-Island/ALIGN.git
   git remote -v
   ```

## 작업 루프 (기능마다)

```bash
# 1. 원본 최신화 (작업 시작 전 항상)
git switch main
git fetch upstream
git merge upstream/main
git push origin main

# 2. 브랜치 만들고 작업
git switch -c feat/imu-read
git add .
git commit -m "IMU 값 읽기 구현"

# 3. 내 fork에 올리기
git push -u origin feat/imu-read
```

4. fork 페이지의 `Compare & pull request` → base가 `GyeongChan-Island/ALIGN`의 `main`인지 확인 → PR 생성
5. 다른 팀원이 `Files changed`에서 리뷰 후 `Approve`
6. 승인되면 머지하고 1번으로 돌아가 최신화

## 브랜치 이름

기능이 드러나게 짓습니다.

| 접두사 | 용도 | 예 |
| --- | --- | --- |
| `feat/` | 새 기능 | `feat/complementary-filter`, `feat/csv-logger` |
| `fix/` | 버그 수정 | `fix/imu2-address` |
| `docs/` | 문서 | `docs/wiring` |
| `ci/` | 빌드·자동화 | `ci/arduino-build` |

## 파일 규칙

- **Arduino 스케치**는 `arduino/<이름>/<이름>.ino`처럼 폴더 이름과 파일 이름을 같게 둡니다. 다르면 Arduino IDE와 CI가 스케치로 인식하지 않습니다.
- 새 Arduino 라이브러리를 쓰면 [arduino/libraries.txt](arduino/libraries.txt)에 이름을 추가합니다. 추가하지 않으면 CI 빌드가 실패합니다.
- **노트북**은 `python/NN_설명.ipynb`처럼 번호를 붙이고, 커밋 전에 큰 출력(이미지·긴 로그)은 지웁니다.
- 같은 파일을 두 명이 동시에 고치면 충돌이 나기 쉬우니, 기능별로 담당 파일을 나눕니다.
- 커밋 전에 `git status`로 무엇이 올라가는지 확인합니다.

## 자동 빌드 (CI)

`arduino/` 아래를 바꾼 PR을 올리면 GitHub Actions가 모든 스케치를 ESP32 Dev Module 기준으로 컴파일합니다. 빨간 X가 뜨면 PR의 `Checks` 탭에서 오류를 확인하세요. 빌드된 펌웨어(`.bin`)는 Actions 실행 페이지의 Artifacts에서 내려받을 수 있습니다.

## 자주 막히는 부분

| 증상 | 해결 |
| --- | --- |
| push가 거부된다 | `git push origin 브랜치이름`처럼 내 fork로만 push한다 |
| `git remote -v`에 upstream이 없다 | ALIGN 폴더에서 `git remote add upstream ...`을 다시 실행한다 |
| `ALIGN/ALIGN` 폴더가 생겼다 | 빈 상위 폴더에서 clone하고 그 안의 `ALIGN`을 연다 |
| 원본이 바뀐 걸 모르고 작업했다 | 작업 시작 전에 최신화(1번)를 항상 한다 |
