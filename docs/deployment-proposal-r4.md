# r4 외부 배포 검토안

기준일: 2026-09-20 KST. 로컬 제품과 자동 검증은 완료했다. 외부 계정 연결·접근 범위 결정과 실제 원격 검증은 남아 있다. 비공개 GitHub와 웹서비스의 공개 여부는 별개다.

## 준비된 대상

- 코드: `10038a2e02cb7ead1c3e03b035172f76088ab2ea`
- DB SHA-256: `5a9e938d5d0132c034a2d5c2faacdeb474fb266088a33741e1274d509c533ee9`
- 검토판: `.artifacts/packages/ce-r4-review`, 허용 파일 17개 합계 111,091,905바이트(별도 manifest 제외).
- 압축 보관본: `.artifacts/packages/ce-r4-review.tgz`, 34,404,188바이트. 18개 항목을 원본과 해시 대조했다. SHA-256: `60e9388868f44d115eb888f4d99fc14e877f6ff5677948c6f85f3e992d53ebd5`.
- 복원본: `.artifacts/packages/ce-r4-restored`.
- 점검 패키지: `.artifacts/packages/ce-r4-maintenance`, 28,509바이트, DB 없음. HTTP 503 검증 완료.
- 근거: [패키지 보고서](../reports/package-24966116-r4-final.json), [후보 판정](../reports/assessment-24966116-r4.json).

검토판은 현재 로컬 실행용이다. 공개 build와 진입점은 차단되어 있어 그대로 Vercel에 올려 사용할 수 없다. 보호된 원격 검토판을 선택하면 인증을 강제하는 별도 실행 조건을 구현하고 비인증 요청 차단을 검증한다. 정식 공개 판정은 유지한다.

## 결정할 사항

1. **본인만 접근하는 원격 검토판**: Vercel 인증 보호, 개인 프로젝트, 무료 범위만 사용. 유료 전환 없음. 화면 제외를 유지하고 HTTP·데이터·인증·복구를 검사한다.
2. **로컬 사용으로 완료**: `http://127.0.0.1:8141`을 사용하고 R07 외부 운영을 후속 선택 사항으로 남긴다.

현재 Vercel 로그인과 연결 프로젝트가 확인되지 않았다. 원격 선택 시 사용자 로그인으로 연결하고 실제 계정 요금제·보호 옵션을 확인한다. 토큰·비밀번호를 문서나 대화에 붙여 넣지 않는다.

## 용량과 외부 완료 조건

Vercel 공식 문서의 일반 Python 함수 번들 한도는 500MB, CLI 소스 업로드 한도는 Hobby 100MB·Pro 1GB이다. 비압축 패키지는 Hobby 업로드 한도를 초과한다. CLI의 `--archive=tgz` 옵션을 검토할 수 있지만 위 보관본 생성만으로 플랫폼 한도 통과가 검증된 것은 아니다. 무료 범위에서 수용되지 않으면 유료 변경 없이 대안을 결정한다.

근거: [Python 런타임](https://vercel.com/docs/functions/runtimes/python), [플랫폼 한도](https://vercel.com/docs/limits), [CLI deploy archive](https://vercel.com/docs/cli/deploy), [인증 보호](https://vercel.com/docs/deployment-protection/methods-to-protect-deployments/vercel-authentication).

업로드 후보는 웹 실행 코드·정적 파일·추출 DB다. 게임 설치본·실행 파일·분석 도구·스냅샷·Legacy·백업·계정 정보는 포함하지 않는다. 추출 DB는 GitHub에 올리지 않았으며 외부 호스팅을 선택할 때만 업로드 대상이 된다.

외부 완료 조건은 인증 보호 확인 → 점검 배포 ID 확보 → 보호된 검토판 배포 → DB/버전 일치 → 비인증 요청 차단 → API·모듈 MIME·DB 다운로드 차단 → warm/cold 측정 → 점검판 전환·복구다. 정식 공개는 화면 제외 수용과 공개 범위를 별도로 확정하고 공개 후 관찰을 수행한다. 현재 원격 절차는 미실행이며 로컬 성공을 원격 성공으로 기록하지 않는다.
