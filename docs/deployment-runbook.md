# CE 패키지·배포·복구 절차

2026-09-20 사용자 요청으로 공개 검토판 배포를 지원한다. 정식 출시 판정과 데이터 검증 표시는 유지한다. 아래 명령은 CE 폴더에서 실행한다.

## 공개 검토판 업데이트

GitHub `jskim414/002-sam14-ce`는 공개 코드 저장소다. DB는 Git에 포함하지 않으므로 Git push 자동 배포는 비활성화하고, 검증된 DB를 포함한 패키지를 CLI로 배포한다. 기존 `sam14-db` 프로젝트와 도메인을 사용한다.

```powershell
python scripts/run_checks.py --database db/ce-24966116-r4.final.db --report reports/checks-next-deployment.json
python scripts/package_release.py --database db/ce-24966116-r4.final.db --mode public-review --output .artifacts/packages/ce-next-public
python .artifacts/packages/ce-next-public/check_package.py --deploy
npx vercel deploy .artifacts/packages/ce-next-public --project sam14-db --scope jskiming-gmailcoms-projects --archive=tgz --prod --skip-domain --yes
npx vercel promote <검증한-배포-URL> --scope jskiming-gmailcoms-projects --yes
```

`public-review`는 구조 검증과 파일 해시 검사를 통과해야 하며, 실행 시 DB 해시도 확인한다. `release_ready`를 참으로 바꾸지 않는다. 기존 `review` 모드는 계속 로컬 전용이고 `--release`는 미해결 정식 출시 조건을 거부한다. `CE_MAINTENANCE=1`은 모든 모드에서 점검 응답을 강제한다. 원격 배포 후 홈페이지·API·모듈 MIME과 DB/소스 직접 다운로드 차단을 확인하고 도메인을 전환한다.

## 허용 파일 패키지

```powershell
python scripts/package_release.py --database db/ce-24966116-r4.final.db --mode review --output .artifacts/packages/ce-r4-review
python .artifacts/packages/ce-r4-review/check_package.py
python .artifacts/packages/ce-r4-review/run.py --port 8142
```

고정 허용 목록의 Python 코드, HTML/CSS/JS, 로컬 QR 모듈·라이선스, SQLite DB, 실행·검사 스크립트만 담는다. 원천·Steam manifest·테스트·node_modules·Git·환경값은 포함하지 않는다. `package-manifest.json`은 코드 커밋, 파일별 SHA/크기, DB SHA를 기록한다. 보수적으로 전체 450 MiB 미만을 요구한다.

`check_package.py --release`는 구조 검사만 통과한 검토 패키지를 거부한다. `package_release.py`의 기본 모드도 release이며 현재 DB로는 실패해야 한다. 기존 경로는 덮어쓰지 않는다. 프로젝트 루트에서 Vercel CLI를 실행하지 말고 게이트 통과 후 생성한 release 패키지 디렉터리만 사용한다.

## 점검과 복원

```powershell
python scripts/package_release.py --mode maintenance --output .artifacts/packages/ce-maintenance
python scripts/restore_package.py --source .artifacts/packages/ce-r4-review --output .artifacts/packages/ce-r4-restored
python .artifacts/packages/ce-r4-restored/run.py --port 8143
```

복원은 `.artifacts/packages` 안의 검증된 보존본을 새 경로에 복사하고 해시를 다시 확인한다. 현재 서비스 DB·Legacy·기존 패키지를 교체하지 않는다. 점검 패키지는 데이터 없이 503·Retry-After·점검 메시지를 반환한다. 배포 진입점도 DB 부재, 공개 게이트 미충족, `CE_MAINTENANCE=1`이면 점검 응답을 선택한다.

첫 공개 전에는 점검 패키지를 CE 전용 프로젝트에 별도 배포해 배포 ID/URL을 복구 대상으로 남겨야 한다. 이후 장애는 마지막 검증된 CE 배포로 rollback하고, CE 배포 전력이 없으면 점검 배포로 전환한다. Legacy를 CE 도메인의 대체 데이터로 사용하지 않는다. 실제 프로젝트가 아직 없으므로 임의 배포 ID나 명령의 성공 기록은 만들지 않았다.

## 실제 공개 전 조건

1. 남은 원천·의미 검증, 인수 확인표와 사용자 제외 범위의 처리 결정을 완료한다.
2. 승인된 코드 SHA에서 DB를 두 번 빌드해 내용/파일 해시를 비교하고 원천 전수 대조한다.
3. 공개 가능 프로필과 릴리스 검증 절차를 별도 코드 변경으로 승인한다. 현재 빌더는 release_ready=true 입력도 거부하므로 DB 플래그만 수동 변경해서 공개하지 않는다.
4. release 패키지를 만들고 게이트·해시·허용 목록 검사 후 CE 전용 프로젝트에 Preview 배포한다.
5. 원격 API·라우팅·번들·cold/warm 표본 검증 후 공개한다. 공개 직후·1시간 후·다음 날 오류와 응답 시간을 기록한다.

`api/index.py`는 기존 읽기 전용 서버 handler를 공유한다. `/api`의 BaseHTTPRequestHandler 지원과 bundle 기준은 [Vercel 공식 Python 함수 문서](https://vercel.com/docs/functions/runtimes/python/api-directory), [Python 런타임 문서](https://vercel.com/docs/functions/runtimes/python)를 확인했다. 해당 플랫폼의 실제 배포·라우팅 검사는 미실시다. 로컬 기본 Python은 3.14, 배포 설정은 3.12이므로 Preview에서 해당 버전도 검증해야 한다.
