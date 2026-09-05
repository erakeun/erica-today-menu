# ERICA 오늘의 메뉴

한양대학교 ERICA 공식 홈페이지의 식당 정보를 정해진 시각에 수집해 보여주는 초경량 GitHub Pages 사이트입니다.

- 프레임워크, 외부 폰트, 데이터베이스 없음
- 방문자는 작은 `menu.json`만 읽고, 공식 메뉴 사진이 있을 때만 해당 이미지를 지연 로딩
- 한국시간 07~08시·10~12시·16~18시에 30분 간격으로 자동 확인
- GitHub Actions에서 수집에 실패하면 기존에 정상 배포된 페이지가 유지됨
- 공식 페이지가 `no-img` 자리표시자를 쓰는 동안에는 빈 사진 영역도 표시하지 않음
- 식당에서 실제 사진을 올리면 다음 자동 확인·배포 때 메뉴와 함께 표시됨
- 학생식당·창업보육센터·교직원식당은 메뉴 날짜가 주말/대한민국 공휴일이고 하루 전체 메뉴가 없으면 “주말 및 공휴일에는 운영하지 않습니다.”로 표시
- 평일 메뉴 미등록, 특정 끼니 필터의 빈 결과, 창의인재원식당·푸드코트는 휴무로 추정하지 않으며 실제 등록 메뉴가 있으면 우선 표시
- 공휴일(음력·대체공휴일 포함)은 `scripts/kr_public_holidays.json`의 2026~2035년 자료로 판단. `holidays` v0.103에서 생성한 날짜와 출처를 기록했으며, 새 임시공휴일 지정/법령 변경 시 자료를 갱신해야 함. 지원 연도 밖의 날짜는 수집 오류로 알려 잘못된 평일 판정을 방지
- 기존 Python 표준 라이브러리만 사용하며 브라우저나 배포 과정에 추가 라이브러리/API 요청 없음

## 데이터 출처

- 교직원식당: <https://www.hanyang.ac.kr/re11>
- 학생식당: <https://www.hanyang.ac.kr/re12>
- 창의인재원식당: <https://www.hanyang.ac.kr/re13>
- 푸드코트: <https://www.hanyang.ac.kr/re14>
- 창업보육센터: <https://www.hanyang.ac.kr/re15>

푸드코트 페이지는 일일 식단이 아니라 고정 운영 매장과 대표 메뉴를 제공합니다. 사이트에서도 별도 화면으로 구분합니다.

## GitHub Pages 배포

1. GitHub에서 `erica-today-menu` 공개 저장소를 만듭니다.
2. 이 폴더 안의 파일을 저장소 `main` 브랜치에 올립니다.
3. 저장소 `Settings → Pages → Build and deployment`에서 Source를 `GitHub Actions`로 선택합니다.
4. `Actions → ERICA 메뉴 갱신 및 배포 → Run workflow`를 한 번 실행합니다.

저장소가 `erakeun/erica-today-menu`라면 기본 주소는 아래와 같습니다.

<https://erakeun.github.io/erica-today-menu/>

식당을 바로 선택해 여는 링크도 지원합니다. `restaurant`에는 `student`, `dormitory`,
`incubator`, `faculty`, `food-court` 중 하나를 사용합니다.

<https://erakeun.github.io/erica-today-menu/?restaurant=student>

## 수동 갱신

GitHub의 `Actions → ERICA 메뉴 갱신 및 배포 → Run workflow`를 누르면 즉시 다시 수집하고 배포합니다.

## 파일 구조

```text
.
├── .github/workflows/pages.yml  # 예약 수집과 Pages 배포
├── dist/index.html              # 화면 전체
├── dist/menu.json               # 자동 생성되는 메뉴 데이터
├── scripts/fetch_menu.py        # 공식 홈페이지 수집기
└── README.md
```

공식 홈페이지의 HTML 구조가 바뀌면 수집기도 함께 수정해야 합니다.

```sh
python3 -m unittest discover -s tests
python3 scripts/fetch_menu.py
```
