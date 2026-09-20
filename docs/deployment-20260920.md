# 2026-09-20 공개 검토판 배포

사용자 요청에 따라 GitHub 저장소를 공개로 변경하고 기존 Vercel `sam14-db` 서비스를 CE r4 검토판으로 교체했다.

- 사이트: https://sam14-db.vercel.app
- 공개 저장소: https://github.com/jskim414/002-sam14-ce
- Vercel 연결 저장소: `jskim414/002-sam14-ce`, `master`
- 배포 코드: `fe375038fa2b0a5bcf192ac97efc33c08a868fde`
- 배포 ID: `dpl_6uDy9C7LrVw11qPK9Xc6Fp4Xvd2E`
- 배포 URL: https://sam14-dvarv2lq7-jskiming-gmailcoms-projects.vercel.app
- 로컬 보관 패키지: `.artifacts/packages/ce-vercel-20260920-public-v7`
- DB SHA-256: `5a9e938d5d0132c034a2d5c2faacdeb474fb266088a33741e1274d509c533ee9`
- 모드: `public-review`; 데이터의 정식 출시 판정 `release_ready=false` 유지
- Python 함수 런타임: 3.12, Vercel Hobby 기본 빌드 환경

원격 빌드의 패키지 검증을 통과했다. 보호된 배포에서 홈페이지·JavaScript 모듈·시나리오·무장 검색·비공개 파일 경로를 검사한 뒤 프로덕션으로 승격했다. 로그인이나 우회 토큰 없는 공개 주소에서 11개 HTTP 검사를 모두 통과했다. 화면 파일은 로컬 파일과 바이트 단위로 일치했고, 시나리오는 52개였으며 DB·패키지 manifest·서버 소스 직접 요청은 404였다. 결과는 [원격 검증 보고서](../reports/deployment-vercel-20260920.json)에 있다.

실제 DB 통합 검사 38개와 JavaScript/문법 검사, GitHub의 Python 3.12·3.14 검사가 통과했다. 최종 코드의 [GitHub Actions 실행](https://github.com/jskim414/002-sam14-ce/actions/runs/35495440127)은 성공했다. 실제 브라우저 화면 검사와 공개 후 1시간·다음 날 관찰은 수행하지 않았다.

기존 배포 `dpl_71uXND2Len1ayRkVfxwSnHNSKkMT`와 이번 작업에서 실패한 배포 6개를 삭제했다. 프로젝트와 공개 도메인은 유지했다. 예전 GitHub 저장소 `001-sam14-db` 자체는 삭제하지 않았다.

DB와 게임 설치 원본은 공개 GitHub에 넣지 않는다. DB가 없는 코드 push가 서비스 배포를 덮어쓰지 않도록 `git.deploymentEnabled=false`를 설정했다. 이후 업데이트는 [배포 절차](deployment-runbook.md)의 검증·패키지·CLI 배포 명령을 사용한다.
