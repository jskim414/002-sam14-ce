# 삼국지14 CE 무장 참조

독립 CE 원천을 사용하는 **로컬 검토판**입니다. 내면 5종, 정책·구성 효과, 방향별 친애·혐오, 혼인·의형제, 전법을 제공합니다. 조조의 오산·패기웅심을 포함한 52개 시나리오를 해독했습니다. 외부 서비스 공개 조건과 원격 운영 검증이 남아 정식 공개는 Hold입니다. 화면 검증은 사용자 요청으로 제외했습니다.

## 실행

Python 3.12 이상, 외부 Python 패키지 없이 실행합니다. 확인 환경은 Windows / Python 3.14입니다.

```powershell
cd C:/Users/jskim/Documents/projects/02-build/002-sam14-ce
python scripts/run_web.py --no-browser
```

주소: <http://127.0.0.1:8141>. 기본 DB는 `db/ce-24966116-r4.final.db`이며 이 PC의 loopback에만 바인딩합니다. Git에는 게임 원천·DB를 넣지 않습니다.

## 구현 범위

- 별도 CE 저장소와 Legacy 복구본, 원본 출력 경로 보호
- build 24966116 전체 812개 파일 inventory, 선택 원천 스냅샷, 계보·재현 빌드
- 시나리오 52개 catalog / 52개 본문 해석 / 일반 탐색 39개
- 이름 있는 ID 1,400개, 무장 상태 72,800행, 관계 157,105행
- 내면 값 364,000개와 raw·offset 증거, 전법·사전 설명·정책 구성요소
- 이름·자 자동완성, 복수 개성 AND/OR, 세력·상태·정책·주의·진형·전법 필터
- 데스크톱 표·상세 패널, 모바일 카드·상세, 관계 탐색·URL 문맥 복원
- 2~3명 비교, 저장 검색, 등장 예정 모아보기, 보관함 개별·전체 삭제
- 로컬 QR 생성, 테마, 조회 캐시·실패 시 기존 응답 안내·재시도
- 허용 파일만 담는 패키지, 해시 검증·로컬 복원·점검 응답·공개 차단

1,400개 ID는 NPC·임시 슬롯을 포함하며 플레이 가능한 무장 수가 아닙니다. 기본 시나리오는 `ce-05`입니다. 내면은 `CROSS_CHECKED`이며 게임 화면 검증을 완료한 값과 구분합니다. 정책 효과별 10단계 기본 수치·단위와 개방 조건, 전법 종류·효과 명칭, 명승 100개·방책 79개·시문 20개·공로 6등급를 제공합니다. 기본 효과표와 진행 게임의 현재 세력 효과는 구분합니다.

## 검사

```powershell
npm ci --ignore-scripts
python scripts/run_checks.py --report reports/checks-synthetic-new.json
python scripts/run_checks.py --database db/ce-24966116-r4.final.db --report reports/checks-integration-new.json
python scripts/validate_db.py --database db/ce-24966116-r4.final.db
python scripts/validate_db.py --database db/ce-24966116-r4.final.db --release
```

Git의 게임 데이터 없는 복제본에서도 첫 검사 명령은 합성 데이터로 실행됩니다. 실제 원천 검사는 제외 사유를 기록하며, `--database`를 지정한 통합 검사는 skip을 허용하지 않습니다. 마지막 명령은 현재 공개 게이트 때문에 실패하는 것이 정상입니다. Node/jsdom은 개발 검사에만 필요합니다. DOM 검사는 브라우저 렌더링·화면 검증을 포함하지 않습니다.

## 다음 후보 생성

도구는 기존 결과를 덮어쓰지 않습니다. 매 실행 새 출력 이름을 지정합니다.

```powershell
python scripts/build_db.py --snapshot .artifacts/source-snapshots/ce-ko-build-24966116 --profile profiles/ce-ko-24966116.json --output db/ce-next.candidate.db --report reports/build-next.json
python scripts/verify_source.py --database db/ce-next.candidate.db --snapshot .artifacts/source-snapshots/ce-ko-build-24966116 --profile profiles/ce-ko-24966116.json --report reports/source-next.json
python scripts/export_catalog.py --database db/ce-next.candidate.db --output reports/catalog-next.json
python scripts/benchmark_local.py --database db/ce-next.candidate.db --report reports/performance-next.json
```

신규 원천은 `scripts/inventory_install.py --help`를 참조합니다. Legacy·`.git`·프로젝트 루트의 서비스 `db/sam14.db` 출력은 거부합니다. 배포 준비·복원 명령은 [배포 절차](docs/deployment-runbook.md)에 있습니다.

## 근거

- [r4 최종 실행 결과](plan/13-ce-r4-completion.md), [최종 검증 JSON](reports/completion-24966116-r4.json)
- [외부 배포 검토안](docs/deployment-proposal-r4.md)
- [DLC·신분·정책·추가 도감 분석](docs/dlc-and-catalog-analysis.md)
- [릴리스 판정 규칙](docs/release-gates.md)
- [구현 결과·미해결 항목](docs/implementation-status.md)
- [원천·보존 결정](docs/source-analysis.md), [필드 사전](docs/field-dictionary.md)
- [화면 검증 제외 및 인수 확인표](docs/acceptance-checklist.md)
- [상세계획 11](plan/11-ce-product-redevelopment-plan.md)
- [잔여 작업 수행 계획 12](plan/12-ce-remaining-work-plan.md)

GitHub: [jskim414/002-sam14-ce](https://github.com/jskim414/002-sam14-ce) — 비공개 CE 전용 저장소입니다. 코드·계획·테스트·검증 보고서를 보존합니다.

원천·메시지 전문·해제 바이너리·Steam manifest·DB·백업은 GitHub 업로드에서 제외하고 로컬에 보관합니다. Vercel 프로젝트·도메인 연결·공개 배포는 만들지 않았습니다.
