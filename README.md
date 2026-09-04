# ERICA 오늘의 메뉴

한양대학교 ERICA 공식 홈페이지의 식당 정보를 정해진 시각에 수집해 보여주는 초경량 GitHub Pages 사이트입니다.

- 프레임워크, 외부 폰트, 데이터베이스 없음
- 방문자는 작은 `menu.json`만 읽고, 공식 메뉴 사진이 있을 때만 해당 이미지를 지연 로딩
- 한국시간 07~08시·10~12시·16~18시에 30분 간격으로 자동 확인
- GitHub Actions에서 수집에 실패하면 기존에 정상 배포된 페이지가 유지됨
- 공식 페이지가 `no-img` 자리표시자를 쓰는 동안에는 빈 사진 영역도 표시하지 않음
- 식당에서 실제 사진을 올리면 다음 자동 확인·배포 때 메뉴와 함께 표시됨

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
