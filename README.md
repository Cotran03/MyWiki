# MyWiki

회원마다 하나의 비공개 개인 위키를 제공하고, 선택한 문서만 다른 회원에게 `viewer` 또는 `editor` 권한으로 공유하는 Flask 기반 지식 관리 서비스입니다.

현재 구현된 첫 수직 기능:

- 이메일·비밀번호 회원가입, 이메일 인증, 로그인, 비밀번호 재설정
- 개발용 콘솔 메일과 Gmail 호환 SMTP 실발송
- 가입 시 개인 위키 하나 자동 생성
- 안전한 Markdown 문서 작성·열람·수정
- 태그, 최근 문서, 권한 범위 내 검색
- 문서별 viewer/editor 공유와 권한 회수
- 불변 revision 이력과 이전 버전 복구
- 낙관적 잠금을 통한 동시 편집 충돌 방지
- 30일 휴지통과 공유 접근 차단
- 라이트·다크·자동 테마와 키보드 탐색

## 빠른 시작 — Windows

Docker Desktop을 먼저 실행한 뒤 PowerShell에서 다음 명령을 실행합니다.

```powershell
docker compose up -d db
py -3.14 -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\flask --app wsgi:app db upgrade
.venv\Scripts\flask --app wsgi:app run --debug
```

브라우저에서 `http://127.0.0.1:5000`을 엽니다.

이 저장소에서는 Windows에 설치된 PostgreSQL의 기본 5432 포트와 충돌하지 않도록 Docker PostgreSQL을 `localhost:5433`에 연결합니다. 앱 연결 정보는 Git에서 제외되는 `.env`에 들어 있습니다.

기본 개발 설정은 이메일을 실제로 발송하지 않고 서버 터미널의 `DEV MAIL` 로그에 링크를 표시합니다. Gmail 실발송 설정은 [개발 환경 문서](docs/DEVELOPMENT.md#gmail-smtp로-실제-메일-보내기)를 참고하세요.

## 자주 쓰는 명령

```powershell
# DB 상태
docker compose ps

# PostgreSQL 콘솔
docker compose exec db psql -U mywiki -d mywiki

# SMTP 설정 확인 메일
.venv\Scripts\flask --app wsgi:app send-test-email 내주소@example.com

# 마이그레이션 적용 및 모델과 스키마 일치 확인
.venv\Scripts\flask --app wsgi:app db upgrade
.venv\Scripts\flask --app wsgi:app db check

# 테스트와 정적 검사
.venv\Scripts\python -m pytest
.venv\Scripts\ruff check .
.venv\Scripts\ruff format --check .

# DB 컨테이너 중지/재시작
docker compose stop db
docker compose start db
```

`docker compose down -v`는 개발 데이터베이스 볼륨까지 삭제하므로 데이터 초기화 의도가 있을 때만 사용하세요.

## 프로젝트 구조

```text
src/mywiki/            Flask 애플리케이션 패키지
├─ auth/               회원가입·로그인·이메일 토큰
├─ documents/          문서·공유·검색·이력 라우트
├─ main/               대문·대시보드·상태 확인
├─ services/           권한·문서 트랜잭션·Markdown·메일
├─ templates/          Jinja2 화면
└─ static/             CSS와 JavaScript
tests/                 pytest 자동 테스트
migrations/            Alembic 스키마 이력
docs/                  요구사항·아키텍처·로드맵·사용 설명
deploy/                운영 서버 설정
```

## 문서

- [확정 요구사항](docs/REQUIREMENTS.md)
- [아키텍처](docs/ARCHITECTURE.md)
- [개발 환경](docs/DEVELOPMENT.md)
- [사용 설명서](docs/USER_GUIDE.md)
- [운영과 백업](docs/OPERATIONS.md)
- [MVP 로드맵](docs/ROADMAP.md)
