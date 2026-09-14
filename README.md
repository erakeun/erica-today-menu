# ERICA 오늘의 메뉴

HY-SQUARE의 공개 식단을 자동 수집하는 정적 GitHub Pages 사이트입니다.
[운영 페이지](https://erakeun.github.io/erica-today-menu/) · [학교 원본](https://life.hanyang.ac.kr/theme/pages/home.php)

## 수집·배포 구조

- **코드 push / Pages 화면 배포**: 테스트 → 현재 운영 menu.json 다운로드·검증 → UI와 함께 배포. 학교 서버는 호출하지 않으며, 운영 데이터를 구하지 못하면 배포를 중단합니다.
- **메뉴 자동 갱신**: 검증된 Firebase 중계 → 오늘(KST) 데이터 검증 → Pages 배포. 소스 오류/미등록/지난 날짜/전체 빈 메뉴는 새 배포를 건너뛰고 Step Summary에 기록합니다. 설정 오류·코드 결함은 실패합니다.
- **중계**: 서울 Firebase 2세대 함수가 HY-SQUARE 고정 주소를 GET 한 번으로 읽습니다. dbMenus와 dbFacilitiesList에서 식단에 필요한 필드만 반환합니다. 리디렉션은 임의 외부 주소로 따라가지 않습니다.
- **보존/요청 제한**: 전용 Firestore 문서 한 개에 마지막 정상 JSON과 갱신 상태를 저장합니다. 원본 요청 전에 시도 시각을 트랜잭션으로 기록하여 재시작/중복 호출에도 최소 15분 간격을 지킵니다. minInstances=0, maxInstances=1, concurrency=1.
- **화면**: 메뉴 미등록·휴무·식당별 조회 실패·오래된 메뉴를 구분합니다. 가벼운 상태 전용 요청 한 번을 추가해 원본 실패와 마지막 정상 시각을 안내합니다. 상태 조회는 학교 요청을 유발하지 않습니다. 기존 필터·모바일 레이아웃·GA4는 유지합니다.

현재 초기 배포 단계에서는 예약이 일시 중지되어 있습니다. 수동 갱신에서 실제 수집과 Pages 배포를 검증한 뒤 refresh.yml에 예약을 활성화합니다. 최종 활성화 상태는 해당 파일 및 운영 복구 보고서를 확인하세요.

## 데이터

학생식당(id=1), 교직원식당(2), 창업보육센터식당(3), 창의인재원식당(4)의 조식·중식·석식, 이름·설명·가격·이미지·날짜를 보존합니다. 원본의 facility_status=inactive는 실제 메뉴와 함께 나오므로 휴무 판정에 쓰지 않습니다.

푸드코트는 시설 목록의 기존 학생복지관 2층 매장 7곳(id=12~18)입니다. 원본에 이 매장들의 일별 메뉴/가격이 없으므로 **매장명·위치·업종**을 표시합니다. 다른 카페를 임의로 푸드코트에 추가하지 않습니다.

일부 식당의 잘못된 데이터는 그 식당만 오류 처리합니다. 원본에서 시설은 확인되지만 오늘 메뉴가 없으면 미등록입니다. 학생식당·창업보육센터·교직원식당은 실제 메뉴가 없고 주말/대한민국 공휴일인 경우 휴무로 분류합니다. 기숙사/푸드코트는 별도 운영이므로 휴무를 추정하지 않습니다. 실제 메뉴가 있으면 휴무 추정보다 우선합니다.

공휴일 자료는 scripts/kr_public_holidays.json(2026~2035)이며 새 임시공휴일/법령 변경 시 갱신해야 합니다. 지원 연도 밖의 날짜는 조용히 잘못 분류하지 않고 오류를 냅니다.

dist/menu.json은 생성 산출물이며 Git에 저장하지 않습니다. 과거 정적 스냅샷을 오늘 메뉴로 강제 배포하는 입력/경로는 없습니다.

## 중계 배포 및 운영

프로젝트: erica-student-promoters-v4-dev

전용 codebase: erica-menu-relay

함수: ericaMenuRelay / asia-northeast3

전용 Firestore 문서: _erica_public_menu/cache

[공개 메뉴 JSON](https://asia-northeast3-erica-student-promoters-v4-dev.cloudfunctions.net/ericaMenuRelay)

[상태 JSON](https://asia-northeast3-erica-student-promoters-v4-dev.cloudfunctions.net/ericaMenuRelay/status)

GET / 및 GET /status만 지원하며 URL 파라미터/다른 메서드를 거절합니다. 공개 메뉴 외 다른 데이터는 읽거나 반환하지 않습니다. 기존 프로젝트의 다른 함수·컬렉션·보안 규칙은 수정하지 않습니다. 함수의 기존 프로젝트 서비스 계정 권한에 의존하므로 프로젝트 IAM 변경 시 함께 점검해야 합니다.

기존 Firebase 로그인 권한이 있는 관리자는 다음만 실행합니다.

```sh
cd relay/functions
npm ci
cd ..
npx firebase-tools deploy --only functions:erica-menu-relay --project erica-student-promoters-v4-dev
```

**전체 functions 배포/삭제는 하지 마세요.** 이 저장소는 다른 기존 서비스들의 코드를 포함하지 않습니다. 공개 엔드포인트는 인증 비밀이 없으며 workflow/화면의 고정 URL만 사용합니다. URL 변경 시 refresh.yml과 dist/index.html을 함께 갱신합니다.

Firestore/함수 실행 비용은 사용량 기반이며 무료를 보장하지 않습니다. 1개 인스턴스/짧은 캐시/15분 원본 제한으로 제한하지만 공개 엔드포인트 남용 비용을 완전히 막지는 못합니다. 기존 프로젝트 과금·할당량·시험 크레딧 만료를 관리자가 점검해야 합니다.

GAS는 실제 배포 시험에서 원본 HTTP 403으로 실패하여 **사용하지 않습니다**. scripts/google_apps_script_proxy.js는 조사 기록용입니다. HTML/페이지 스크립트 조사에서 별도 공식 공개 메뉴 API는 찾지 못했습니다. 이것이 API의 부재를 증명하는 것은 아닙니다.

## 실행과 테스트

```sh
python3 -m unittest discover -s tests
node --test relay/functions/test/*.test.js
# UI만 로컬 확인: 운영 메뉴를 보존해 준비
python3 scripts/prepare_pages.py
# 검증된 중계에서 실제 오늘 메뉴 수집(수동 입력 아님)
MENU_PROXY_URL=https://asia-northeast3-erica-student-promoters-v4-dev.cloudfunctions.net/ericaMenuRelay python3 scripts/fetch_menu.py
python3 scripts/validate_menu.py
```

테스트는 2026-09-14 실제 공개 HTML fixture를 사용하고 학교에 요청하지 않습니다.
HTTP403/timeout/redirect/차단HTML/누락/부분실패/전체실패/미등록/휴일/캐시보존/빈배포차단/KST경계를 포함합니다.

수동 운영 갱신: GitHub Actions → **메뉴 자동 갱신** → Run workflow(main).
UI 배포: **Pages 화면 배포**. 두 배포는 같은 concurrency 그룹을 사용해 서로 충돌하지 않습니다.

딥링크: ?restaurant=student, dormitory, incubator, faculty, food-court.
