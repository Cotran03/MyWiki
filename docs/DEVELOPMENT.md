# 개발 환경 설정

## 현재 구성

- Python 3.14.6
- Flask 3.1 계열
- PostgreSQL 18 Docker 컨테이너
- SQLAlchemy 2와 Alembic
- pytest와 Ruff

Windows에 별도로 설치된 PostgreSQL 18은 `localhost:5432`를 사용합니다. MyWiki의 Docker PostgreSQL은 충돌을 피하기 위해 `localhost:5433`을 사용합니다.

## 1. Docker PostgreSQL 시작

Docker Desktop을 실행하고 프로젝트 루트에서 다음 명령을 실행합니다.

```powershell
docker compose up -d db
docker compose ps
```

정상 상태는 `mywiki-db-1`의 STATUS가 `healthy`로 표시되는 것입니다.

DB 설정은 `compose.yaml`에 정의되어 있습니다.

| 항목 | 값 |
|---|---|
| Host | `localhost` |
| Host port | `5433` |
| Container port | `5432` |
| Database | `mywiki` |
| User | `mywiki` |
| Password | `mywiki` — 개발 전용 |

PostgreSQL 콘솔은 로컬 `psql` PATH 설정 없이 컨테이너를 통해 열 수 있습니다.

```powershell
docker compose exec db psql -U mywiki -d mywiki
```

종료는 `\q`입니다.

## 2. Python 환경 설치

PowerShell 활성화 정책에 영향을 받지 않도록 가상환경 실행 파일을 직접 호출합니다.

```powershell
py -3.14 -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
```

## 3. 환경 변수

`.env.example`을 복사한 `.env`가 로컬 설정입니다. `.env`는 Git에 포함되지 않습니다.

```dotenv
APP_ENV=development
SECRET_KEY=dev-local-only-change-before-deploy
DATABASE_URL=postgresql+psycopg://mywiki:mywiki@localhost:5433/mywiki
BASE_URL=http://127.0.0.1:5000
MAIL_BACKEND=console
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USE_SSL=false
MAIL_USERNAME=
MAIL_PASSWORD=
MAIL_DEFAULT_SENDER=
MAIL_FROM_NAME=MyWiki
MAIL_TIMEOUT_SECONDS=10
RATELIMIT_STORAGE_URI=memory://
```

운영 환경에서는 반드시 강한 `SECRET_KEY`와 별도 DB 비밀번호를 사용해야 합니다.

## 4. 데이터베이스 마이그레이션

```powershell
.venv\Scripts\flask --app wsgi:app db upgrade
.venv\Scripts\flask --app wsgi:app db current
.venv\Scripts\flask --app wsgi:app db check
```

모델을 변경했다면 다음 순서를 따릅니다.

```powershell
.venv\Scripts\flask --app wsgi:app db migrate -m "변경 설명"
# 생성된 migrations/versions 파일을 직접 검토
.venv\Scripts\flask --app wsgi:app db upgrade
.venv\Scripts\flask --app wsgi:app db check
```

## 5. 앱 실행

```powershell
.venv\Scripts\flask --app wsgi:app run --debug
```

- 웹: `http://127.0.0.1:5000`
- 생존 확인: `http://127.0.0.1:5000/health/live`
- DB 준비 확인: `http://127.0.0.1:5000/health/ready`

개발용 이메일 인증·재설정 링크는 앱을 실행한 터미널에 `DEV MAIL`로 출력됩니다.

## Gmail SMTP로 실제 메일 보내기

개인 개발과 소규모 테스트에는 Gmail SMTP를 사용할 수 있습니다. 운영 서비스로 커지면 도메인 인증, 반송 처리와 발송 관측 기능을 제공하는 전용 트랜잭션 메일 공급자의 SMTP 자격 증명으로 교체하는 것을 권장합니다. 애플리케이션 코드는 표준 SMTP를 사용하므로 공급자를 바꿀 때 코드를 수정할 필요가 없습니다.

1. Gmail 계정에서 2단계 인증을 켭니다.
2. Google 계정의 [앱 비밀번호](https://support.google.com/accounts/answer/185833?hl=ko)를 열어 MyWiki용 16자리 앱 비밀번호를 만듭니다.
3. 실제 비밀번호를 채팅이나 Git에 올리지 말고 로컬 `.env`에만 다음 값을 입력합니다. 앱 비밀번호에 표시된 공백은 빼고 입력합니다.

```dotenv
MAIL_BACKEND=smtp
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USE_SSL=false
MAIL_USERNAME=내계정@gmail.com
MAIL_PASSWORD=16자리앱비밀번호
MAIL_DEFAULT_SENDER=내계정@gmail.com
MAIL_FROM_NAME=MyWiki
MAIL_TIMEOUT_SECONDS=10
```

Gmail은 일반 계정 비밀번호를 SMTP 비밀번호로 받지 않습니다. 발신 주소는 인증한 Gmail 주소와 같게 두는 것이 안전합니다. Google의 서버·포트 안내는 [Gmail SMTP 공식 문서](https://support.google.com/a/answer/176600?hl=ko)에서 확인할 수 있습니다.

앱을 다시 시작한 다음 자신에게 테스트 메일을 보냅니다.

```powershell
.venv\Scripts\flask --app wsgi:app send-test-email 내주소@example.com
```

`Test email accepted`가 출력되면 SMTP 서버가 메시지를 접수한 것입니다. 받은편지함에 보이지 않으면 스팸함을 확인합니다. 오류가 발생하면 Gmail 주소, 앱 비밀번호, 2단계 인증 상태를 다시 확인하세요.

## 6. 품질 검사

```powershell
.venv\Scripts\python -m pytest
.venv\Scripts\ruff check .
.venv\Scripts\ruff format --check .
```

테스트는 격리된 SQLite DB를 사용합니다. PostgreSQL 마이그레이션은 실제 Docker DB에서 별도로 검사합니다.

## 문제 해결

### Docker 명령이 엔진에 연결되지 않음

Docker Desktop을 실행하고 작업 표시줄에서 엔진 시작이 완료될 때까지 기다립니다.

```powershell
docker info
```

여전히 실패하면 Windows에서 로그아웃 후 다시 로그인하거나 재부팅하여 `docker-users` 그룹 변경을 반영합니다.

### 5432 포트가 이미 사용 중

정상입니다. 로컬 PostgreSQL이 5432를 사용하고 MyWiki Docker DB는 5433을 사용하도록 구성되어 있습니다.

### DB 연결 실패

```powershell
docker compose ps
docker compose logs --tail 100 db
docker compose exec db pg_isready -U mywiki -d mywiki
```

### SMTP 설정 오류

- 앱 비밀번호는 Google 계정 일반 비밀번호와 다릅니다.
- `.env`를 수정한 후 Flask 서버를 다시 시작해야 합니다.
- `MAIL_USERNAME`과 `MAIL_DEFAULT_SENDER`에는 전체 Gmail 주소를 입력합니다.
- STARTTLS는 `MAIL_PORT=587`, `MAIL_USE_TLS=true`, `MAIL_USE_SSL=false` 조합입니다.
- 인증 링크의 도메인이 외부 서비스 주소와 다르면 `BASE_URL`을 실제 HTTPS 주소로 바꿉니다.
