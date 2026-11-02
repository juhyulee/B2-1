# 콘솔 가계부

Python 표준 라이브러리만 사용한 파일 기반 콘솔 가계부입니다. 거래는 JSONL에 한 줄씩 추가되며, 조회와 검색은 제너레이터로 처리합니다. 수정과 삭제는 임시 파일을 완전히 기록하고 `os.replace`로 교체해 원본 파일이 중간 상태로 남지 않게 했습니다.

## 실행 환경

- Python 3.10 이상
- 외부 패키지 없음

프로젝트 폴더에서 다음과 같이 실행합니다.

```bash
python -m budget_app --help
python -m budget_app <command> --help
```

데이터 위치를 바꾸려면 하위 명령 앞에 `--data-dir`을 둡니다.

```bash
python -m budget_app --data-dir ./my-data list
```

## 빠른 시작

처음 실행하면 `./data` 폴더와 저장 파일 3개가 자동 생성됩니다. 기본 카테고리는 식비, 교통, 주거, 급여, 공과금, 건강, 기타입니다.

### 거래 추가

추가는 대화형입니다.

```bash
python -m budget_app add
```

날짜, 유형(`income` 또는 `expense`), 카테고리, 금액, 메모, 태그를 차례대로 입력합니다. 성공하면 고유 ID가 출력됩니다.

### 목록과 검색

```bash
python -m budget_app list
python -m budget_app list --limit 10
python -m budget_app search --from 2026-11-01 --to 2026-11-30
python -m budget_app search --category 식비 --type expense --tag 점심
python -m budget_app search --q 편의점
```

목록과 검색 결과는 마지막에 추가된 거래부터 표시됩니다. 전체 파일을 메모리에 올리지 않고 제너레이터로 한 건씩 처리합니다.

### 월 요약과 예산

```bash
python -m budget_app summary --month 2026-11 --top 3
python -m budget_app budget set --month 2026-11 --amount 500000
python -m budget_app budget get --month 2026-11
python -m budget_app budget list
```

요약은 수입, 지출, 잔액, 지출 상위 카테고리, 예산 사용률을 표시합니다. 지출이 예산을 넘으면 초과 경고가 나옵니다.

### 카테고리

```bash
python -m budget_app category list
python -m budget_app category add --name 교육
python -m budget_app category remove --name 교육
```

거래에서 사용 중인 카테고리는 삭제할 수 없습니다.

### 수정과 삭제

수정 방식은 **옵션 기반**으로 고정했습니다. 지정한 필드만 바뀌며, 태그를 모두 지우려면 빈 문자열을 전달합니다.

```bash
python -m budget_app update --id TX-000001 --amount 18000 --memo "저녁 식사"
python -m budget_app update --id TX-000001 --tags ""
python -m budget_app delete --id TX-000001
```

수정 가능한 옵션은 `--date`, `--type`, `--category`, `--amount`, `--memo`, `--tags`입니다.

### CSV 가져오기와 내보내기

CSV 스키마는 다음 6개 열로 고정됩니다.

| 열 | 형식 |
|---|---|
| date | `YYYY-MM-DD` |
| type | `income` 또는 `expense` |
| category | 등록된 카테고리 |
| amount | 0보다 큰 정수 |
| memo | 문자열, 비워도 됨 |
| tags | `|`로 구분한 태그, 비워도 됨 |

```csv
date,type,category,amount,memo,tags
2026-11-01,expense,식비,12000,점심,회사|점심
2026-11-05,income,급여,3000000,11월 급여,
```

```bash
python -m budget_app import --from ./sample.csv
python -m budget_app import --from ./sample.csv --atomic
python -m budget_app export --out ./november.csv --month 2026-11
python -m budget_app export --out ./period.csv --from 2026-11-01 --to 2026-11-30
```

기본 가져오기는 유효한 행만 저장하고 성공/실패 건수를 출력하는 부분 반영 정책입니다. `--atomic`을 지정하면 모든 행을 먼저 검증하고, 하나라도 실패할 경우 0건을 저장하며 전체 취소 사실을 출력합니다. 모든 행이 유효하면 기존 거래와 신규 배치를 같은 디렉터리의 임시 파일에 기록하고 `fsync`한 뒤 `os.replace`로 한 번에 교체합니다. 기록 또는 교체 전에 오류가 나면 임시 파일만 삭제되므로 기존 거래 파일은 유지됩니다. 내보내기는 `--month` 또는 `--from`과 `--to` 조합 중 하나를 사용합니다.

## 저장 형식

기본 저장 위치는 `./data`입니다.

- `transactions.jsonl`: 거래
- `categories.jsonl`: 카테고리
- `budgets.jsonl`: 월 예산

각 줄은 독립적인 UTF-8 JSON 객체입니다. 거래 예시는 다음과 같습니다.

```json
{"id":"TX-000001","type":"expense","date":"2026-11-01","amount":12000,"category":"식비","memo":"점심","tags":["회사","점심"]}
```

## JSONL을 선택한 이유

내부 저장 형식은 JSONL, 외부 교환 형식은 CSV로 역할을 나눴습니다.

| 기준 | JSONL | CSV |
|---|---|---|
| 한 건 추가 | 파일 끝에 JSON 한 줄을 바로 추가할 수 있음 | 가능하지만 태그 같은 중첩 값을 별도 규칙으로 인코딩해야 함 |
| 자료형 | 숫자와 태그 배열을 원래 자료형으로 보존 | 모든 값이 셀 문자열이며 배열 구분자 규칙이 필요 |
| 스트리밍 | 한 줄씩 순방향·역방향 처리 가능 | 한 행씩 처리 가능 |
| 사람이 편집 | JSON 문법을 지켜야 함 | 표 형태라 편집과 다른 도구 연동이 쉬움 |
| 스키마 변화 | 선택 필드를 추가하기 비교적 쉬움 | 열 순서와 헤더 호환성 관리가 필요 |

거래는 태그 배열을 포함하고 추가가 빈번하므로 JSONL이 내부 저장에 적합합니다. CSV는 스프레드시트 호환성이 좋으므로 가져오기·내보내기에만 사용합니다. JSONL도 수정과 삭제에는 파일 재작성이 필요하고, 조건 검색용 인덱스를 자체 제공하지 않는다는 한계가 있습니다.

## 10만 건 처리 분석

현재 구현은 목록의 `--limit` 조회에서 파일 끝부터 필요한 레코드까지만 읽으므로 메모리 사용량이 파일 전체 크기에 비례하지 않습니다. 검색과 월 요약도 제너레이터로 한 건씩 처리해 메모리는 일정하게 유지되지만, JSON 디코딩과 디스크 전체 읽기가 필요합니다.

| 동작 | 현재 비용과 예상 병목 | 10만 건 이상 개선 방안 |
|---|---|---|
| 최신 목록 | `O(limit)`, 역방향 블록 읽기 | 현재 방식을 유지하고 블록 크기를 측정해 조정 |
| 검색·월 요약 | `O(n)`, 전체 파일 읽기와 JSON 디코딩 | 월·유형·카테고리별 오프셋 인덱스 또는 SQLite 인덱스 도입 |
| 다음 ID 생성 | `O(n)`, 추가할 때마다 최대 ID 탐색 | 별도 메타데이터 파일에 마지막 ID를 원자적으로 저장 |
| 수정·삭제 | `O(n)`, 전체 파일을 임시 파일로 재작성 | ID→바이트 오프셋 인덱스 또는 SQLite 기본 키 사용 |
| 대량 가져오기 | 유효 행을 메모리에 모은 뒤 한 번에 추가 | 일정 크기 배치 검증, 배치별 임시 파일 작성과 원자적 교체 |
| 반복 요약 | 요청마다 같은 월을 다시 집계 | 월별 집계 캐시를 저장하고 거래 변경 시 해당 월만 갱신 |

10만 건 규모에서 첫 병목은 메모리보다 디스크 전체 읽기와 JSON 파싱입니다. 단일 사용자 콘솔 프로그램이라는 현재 범위에서는 파일 방식이 단순성과 이식성에 유리합니다. 조회 지연이 실제 사용 기준을 넘으면 동일한 서비스 인터페이스를 유지한 채 저장소 구현을 SQLite로 교체하는 것이 우선 개선안입니다. 병렬 처리는 디스크 경합과 결과 병합 비용이 있어 인덱스 적용 후 프로파일링 결과에 따라 검토합니다.

## 공통 관심사 데코레이터

`budget_app/decorators.py`에는 세 책임을 분리한 데코레이터가 있습니다.

- `handle_cli_errors`: 예상 가능한 예외를 사용자 메시지와 종료 코드로 변환
- `log_command`: 명령 시작·완료·실패를 `budget_app` 로거에 기록
- `measure_execution_time`: `time.perf_counter()`로 실행 시간을 측정해 로거에 기록

세 데코레이터는 CLI의 `main()`에 실제 적용됩니다. 라이브러리 사용자가 `budget_app` 로거에 핸들러를 설정하면 명령 로그와 밀리초 단위 실행 시간을 수집할 수 있습니다.

## 구조

- `budget_app/cli.py`: 명령행 파싱, 대화형 입력, 화면 출력
- `budget_app/service.py`: 검증과 가계부 업무 규칙
- `budget_app/repository.py`: JSONL 저장, 역방향 스트리밍, 원자적 수정/삭제
- `budget_app/models.py`: 거래 및 요약 데이터 클래스
- `budget_app/decorators.py`: 예외 처리, 명령 로그, 실행 시간 측정 데코레이터

## 테스트

```bash
python -m unittest discover -s tests -v
```
