# CE 원천 분석과 보존 기록

작성: 2026-09-19 KST. 관측 build: 24966116. 상태: LOCAL_REVIEW_ONLY / 원천 clean_state UNVERIFIED.

## 보존 결정

사용자는 게임 데이터를 수정한 적이 없으며 업데이트 전 설치본을 별도로 보관하지 않았다고 답했다. 추가 드라이브 백업 필요성을 설명한 뒤 진행 승인을 받았다. D: 등의 두 번째 드라이브에 추가 사본을 만들지 않았다.

Legacy 복구본은 `../001-sam14-db/.artifacts/releases/legacy-baseline-20260919-213954`에 있다. `working-tree.zip`은 Git 제외 계획·스크립트·테스트·DB 및 미커밋 CSS를 포함한 52개 파일을 보존하며, `history.bundle`은 Git 이력을 보존한다. ZIP 해시: `dcf1f2f114cd618e9c71b682e9c1836e727f6f565b03356965fbd4cf66370b40`. 제외한 캐시·키·환경 파일 등의 내역은 해당 manifest를 따른다.

CE `.artifacts/legacy-restore-check`에 실제 복원하고 Legacy 테스트 15개를 통과했다. 원본 DB 해시는 작업 후에도 `0f4405d309fd86f84174a5608c4eb78fb9529a578cd57addf402f00753f37118`이다. 기존 `web/static/notion-theme.css`의 미커밋 변경을 그대로 유지했다. 이 복구본은 기존 웹 제품 복구용이며 **업데이트 전 게임 설치본의 복구본은 아니다**.

## 설치 inventory

- 설치 경로: `C:\Program Files (x86)\Steam\steamapps\common\Romance_of_the_Three_Kingdoms_14`
- Steam app 872410 / build 24966116
- 전체 812개 설치 파일의 SHA-256, 크기, 수정 시각, 파일 접두부 기록
- 한국어 CE 실행 파일 `SAN14CE_KO.exe`, `0010_KO` 원천 확인
- manifest에 CE 관련 DLC 4508240, 특전 4598950·4598960 등 설치 depot 기록 확인
- depot 기록은 독립적인 계정 소유권 검증을 대신하지 않음
- 캡처 중 파일 집합·크기·mtime·manifest 안정성 확인, 보존 사본 해시 대조

전체 설치 폴더 약 25GB를 추가 복제하지 않고 KO/JP 분석용 `.s14`, 공통 `.bin`, readme 등 30,510,769바이트를 선택 보존했다. 메시지는 별도 supplement에 추가 보존했다. manifest는 계정 식별 정보가 포함될 수 있어 비공개 영역에만 둔다. 원천 폴더에 쓰기, 무결성 복구, 게임 데이터 편집은 수행하지 않았다.

사용자 진술은 기록하되 공식 설치 해시와의 비교가 없으므로 CLEAN으로 승격하지 않는다. 기존 조사에서 `fixdataex.s14`에 있었던 의심 기록을 현재 CE 파일의 변조 확정으로 확대하지 않는다.

## 파일 구조

일반 CE 파일에서 little-endian version 102, `SN14SCEXVER0001\0` 서명, offset 754의 `LWC\x1a` 스트림을 확인했다. LWC는 원본 길이·payload 길이·256바이트 literal permutation과 MSB 우선 비트 코드/중첩 backreference를 가진다. 자체 bounded decoder는 길이, permutation, history, 최대 출력 크기를 검사한다.

형식 연구에 [기존 LWC 구현의 형식 정보](https://github.com/tenshoukijp/nobu_src_koeilw)를 참고했다. 외부 DLL이나 실행 파일을 실행하지 않았으며 Python 해제기를 직접 구현했다. 공유·배포 전 원천 데이터와 코드의 사용 범위 검토는 별도 작업이다.

공통 `fixdataexce.s14`와 시나리오 50개를 해제했다. 시나리오 32·33은 해당 외부 서명과 스트림 구조가 없어 `UNRECOGNIZED_OUTER_HEADER`로 분류했다. 표시는 메시지 catalog의 ‘조조의 오산’·‘패기웅심’ 후보 이름을 사용하지만 시작일과 모드·본문은 미확인이다. 이 두 파일을 정상 일반 시나리오에 섞지 않는다.

파일 헤더 모드 코드로 일반 37개, 전기 10개, 튜토리얼 3개를 분리했다. 의미는 한국어 게임 메뉴 대조 전 잠정 판정이다. 모든 파일의 처리/제외 상태는 DB source_file에 있으며 catalog 요약으로 내보낸다.

## ID와 비교

무장 배열은 count가 있는 316바이트 레코드 블록이다. 각 시나리오의 실제 count와 이름 있는 원천 ID 집합으로 적재한다. 원천 ID 0 sentinel을 제외한 이름 있는 ID 1,400개가 관측되었다. 신규 build의 기대 무장 수를 1,000명으로 고정하지 않는다.

현재 분류는 잠정 범위 판정으로 사실 후보 1,000, 고대·특전 후보 88, NPC 후보 232, 이름에 특전·범용 표기가 있는 임시 슬롯 80개다. 모드별 실제 사용 가능 여부는 아직 확정하지 않았다. 이 분류를 소유권 판정으로 사용하지 않는다.

Legacy와 단일 이름으로 비교 가능한 907건 중 831건은 비교 필드가 같고 76건은 다르다. 동명이인 등 102건은 모호하고, 391건은 일치 이름이 없다. 907건 중 내부 ID가 다른 사례는 597건이다. 이는 이름 비교 힌트이며 실제 동일인 매핑 승인이 아니다. 예를 들어 CE 원천 조조 ID는 521, Legacy는 522다. CE는 원천 ID를 사용하며 Legacy ID 자동 변환·즐겨찾기 이관을 하지 않는다.

## 미해결

후속 구현에서 내면 5종의 부호 있는 델타, 혼인·의형제 그룹, 전법 배열, 사전 설명·정책 구성요소를 해석했다. 위치와 검증 수준은 [필드 사전](field-dictionary.md)에 기록했다. 내면은 원 연구와 교차 확인한 1~5값이며 게임 화면 검증 완료를 뜻하지 않는다.

시나리오 32·33은 전체 파일 서명, 앞 1,024바이트의 유효 zlib 헤더 및 제한된 단일 바이트 XOR 가설을 추가 검사했으나 지원 가능한 wrapper를 찾지 못했다. 높은 엔트로피만으로 암호화라고 확정하지 않았다. [분석 결과](../reports/unread-wrappers-24966116.json)에 범위와 한계를 남겼다. 이 둘의 해독 자료/정상 추출본, 정책 레벨별 수치 효과 구조, raw state 5의 의미는 여전히 미해결이다.

[공식 인간관계 도움말](https://www.gamecity.ne.jp/manual/sangokushi14-pk/ce/jp/5300.html)과 [공식 편집 기능 안내](https://www.gamecity.ne.jp/manual/sangokushi14-pk/ce/jp/1100.html)는 화면 대조의 참고 자료다. 최초 작업에서는 화면 도구 연결에 실패했으며 후속 사용자 지시 ‘남은 작업 수행 (화면검증 제외)’에 따라 이번에는 게임·브라우저·실기기 화면 검증을 시도하지 않았다. 파일 전수 대조와 DOM 상태 검사는 시각 검증을 대체하지 않는다.
