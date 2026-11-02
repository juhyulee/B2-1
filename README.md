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
python -m budget_app export --out ./november.csv --month 2026-11
python -m budget_app export --out ./period.csv --from 2026-11-01 --to 2026-11-30
```

가져오기는 유효한 행만 저장하고 성공/실패 건수를 출력합니다. 내보내기는 `--month` 또는 `--from`과 `--to` 조합 중 하나를 사용합니다.

## 저장 형식

기본 저장 위치는 `./data`입니다.

- `transactions.jsonl`: 거래
- `categories.jsonl`: 카테고리
- `budgets.jsonl`: 월 예산

각 줄은 독립적인 UTF-8 JSON 객체입니다. 거래 예시는 다음과 같습니다.

```json
{"id":"TX-000001","type":"expense","date":"2026-11-01","amount":12000,"category":"식비","memo":"점심","tags":["회사","점심"]}
```

## 구조

- `budget_app/cli.py`: 명령행 파싱, 대화형 입력, 화면 출력
- `budget_app/service.py`: 검증과 가계부 업무 규칙
- `budget_app/repository.py`: JSONL 저장, 역방향 스트리밍, 원자적 수정/삭제
- `budget_app/models.py`: 거래 및 요약 데이터 클래스
- `budget_app/decorators.py`: 사용자 오류 처리 데코레이터

## 테스트

```bash
python -m unittest discover -s tests -v
```
