# MyWiki 아키텍처

## 1. 목표

MyWiki는 회원마다 하나의 비공개 개인 위키를 제공하고, 소유자가 선택한 문서만 다른 회원에게 `viewer` 또는 `editor` 권한으로 공유하는 서비스다.

아키텍처의 최우선 원칙은 다음과 같다.

1. 다른 회원의 데이터는 기본적으로 보이지 않는다.
2. 문서 본문뿐 아니라 목록, 검색, 이력, 첨부에도 같은 권한 정책을 적용한다.
3. 관리자 역할은 비공개 문서 열람 권한을 자동으로 부여하지 않는다.
4. 현재 문서와 변경 이력은 항상 하나의 트랜잭션으로 저장한다.
5. 공급자에 종속되는 이메일·파일 저장·배포 기능은 인터페이스와 환경 설정으로 분리한다. 이메일은 콘솔과 범용 SMTP 백엔드를 제공하며 공급자 자격 증명은 환경 변수로 주입한다.

## 2. 시스템 구성

첫 버전은 하나의 저장소와 배포 단위로 운영하는 모듈식 Flask 모놀리스를 사용한다.

```text
Browser
  │ HTTPS
  ▼
Flask + Jinja2 + Bootstrap
  ├─ auth          회원가입, 로그인, 인증, 비밀번호 재설정
  ├─ documents     문서 CRUD, 휴지통, 이력
  ├─ sharing       문서별 viewer/editor 권한
  ├─ search        권한 범위 내 검색
  └─ admin         계정 및 서비스 상태 관리
  │
  ├─ PostgreSQL    계정, 위키, 문서, revision, 권한, 감사 로그
  ├─ Object Store  비공개 이미지 파일(후속/스트레치)
  └─ Mail Provider 이메일 인증과 비밀번호 재설정
```

개발과 단위 테스트에서는 SQLite를 사용할 수 있지만, 운영과 권한·동시성 통합 테스트의 기준은 PostgreSQL이다.

## 3. 애플리케이션 구조

```text
src/mywiki/
├─ __init__.py             # create_app 애플리케이션 팩토리
├─ config.py               # 환경별 설정
├─ extensions.py           # DB, migration, login, CSRF
├─ models.py               # SQLAlchemy 모델
├─ auth/                   # 인증 Blueprint와 폼
├─ documents/              # 위키 문서 Blueprint와 폼
├─ main/                   # 대문과 상태 확인
├─ services/
│  ├─ authorization.py     # 중앙 권한 정책
│  ├─ documents.py         # 문서/revision 트랜잭션
│  ├─ mail.py              # 이메일 공급자 경계
│  └─ tokens.py            # 일회용 인증 토큰
├─ templates/              # Jinja2 템플릿
└─ static/                 # CSS와 JavaScript
tests/                     # pytest 단위·통합 테스트
migrations/                # Alembic 스키마 이력
docs/                      # 요구사항·설계·로드맵
```

라우트는 입력 검증과 응답에 집중하고 권한 판정과 트랜잭션은 서비스 계층에 둔다.

## 4. 핵심 데이터 모델

### users

- 고정 UUID
- 고유 사용자명과 정규화된 이메일
- 표시 이름과 Argon2id 비밀번호 해시
- 이메일 인증 시각, 비활성화 시각
- 플랫폼 역할 `member | admin`

### wikis

- 고정 UUID
- `owner_id`에 UNIQUE 제약을 두어 회원당 위키 하나를 보장
- 가입과 개인 위키 생성은 하나의 트랜잭션으로 처리

### documents

- URL에 사용하는 고정 UUID
- 소속 `wiki_id`와 최초 작성자
- 현재 제목, Markdown 본문, revision 번호
- 생성·수정 시각
- 휴지통 시각과 영구 삭제 예정 시각

문서 소유자는 별도 필드로 중복 저장하지 않고 `document.wiki.owner_id`에서 계산한다.

### document_revisions

- 문서별 증가하는 revision 번호
- 제목과 Markdown 본문의 불변 전체 스냅샷
- 편집자, 편집 요약, 작업 종류 `create | edit | restore`
- 복구 대상 revision 참조

복구는 과거 행을 변경하지 않고 새 revision을 만든다.

### document_permissions

- `(document_id, grantee_id)` 복합 기본 키
- `viewer | editor` 접근 수준
- 권한을 부여한 소유자와 부여 시각

소유자 권한은 별도 permission 행으로 저장하지 않는다.

### 보조 모델

- `tags`, `document_tags`: 위키별 태그
- `favorites`: 회원별 즐겨찾기(스트레치)
- `auth_tokens`: 이메일 인증·재설정용 일회성 토큰의 해시
- `audit_events`: 공유, 삭제, 복구, 인증, 관리자 행위
- `attachments`: 객체 저장소 메타데이터(스트레치)

## 5. 권한 정책

| 작업 | 무관한 회원 | viewer | editor | 소유자 | 플랫폼 관리자 |
|---|---:|---:|---:|---:|---:|
| 활성 문서 열람·검색 | X | O | O | O | 별도 권한 필요 |
| 자기 위키에 문서 생성 | X | X | X | O | 자기 위키만 |
| 문서 수정 | X | X | O | O | 별도 권한 필요 |
| 공유 부여·회수 | X | X | X | O | X |
| 이력 열람·복구 | X | X | X | O | X |
| 휴지통 이동·복구 | X | X | X | O | X |

- 무관한 사용자의 직접 URL 접근은 문서 존재를 감추기 위해 `404`로 응답한다.
- 문서를 알고 있는 viewer가 수정 URL에 접근하면 `403`으로 응답할 수 있다.
- 휴지통 문서는 소유자에게만 보이며 기존 공유 접근은 즉시 중단한다.
- UUID는 식별자일 뿐 권한 검사를 대체하지 않는다.

## 6. 문서 저장과 동시 편집

편집 폼은 편집 시작 시점의 `base_revision`을 함께 전송한다. 저장은 다음 조건을 만족할 때만 수행한다.

```sql
UPDATE documents
SET current_revision_no = current_revision_no + 1, ...
WHERE id = :id
  AND current_revision_no = :base_revision
  AND trashed_at IS NULL;
```

갱신된 행이 없으면 `409 Conflict`를 반환한다. 성공하면 같은 트랜잭션에서 새 `document_revisions` 행을 추가한다.

## 7. 검색

MVP는 제목·현재 본문·태그의 부분 검색을 제공한다.

1. 먼저 현재 사용자의 소유 문서와 공유받은 문서로 범위를 제한한다.
2. 휴지통 문서를 제외한다.
3. PostgreSQL에서는 문서 수 증가 시 `pg_trgm` 인덱스를 추가한다.
4. 초성·형태소·오타 교정 검색은 후속 범위로 둔다.

## 8. 보안 기준

- Markdown 원시 HTML 비활성화 및 렌더링 결과 정제
- Argon2id 비밀번호 해시
- CSRF 방어와 `HttpOnly`, `Secure`, `SameSite` 세션 쿠키
- 인증·재설정 토큰은 원문 대신 해시 저장, 1회 사용, 만료 적용
- 로그인·재설정·초대·업로드 요청 속도 제한
- 운영 HTTPS 필수, 개발 서버와 디버거 운영 사용 금지
- 감사 로그에 비밀번호, 토큰, 이메일, 문서 본문을 기록하지 않음

## 9. 운영 기준

- 구조화된 애플리케이션 로그
- `/health/live`, `/health/ready` 상태 확인
- 매일 자동 백업, 30일 보관, 월 1회 복구 시험
- 초기 RPO 24시간, RTO 4시간
- Linux 컨테이너, 관리형 PostgreSQL, 비공개 객체 저장소 권장
- 이메일은 범용 SMTP 경계를 사용하고 운영 공급자와 객체 저장소는 배포 전에 결정

## 10. 기술 결정 기록

| 결정 | 선택 | 이유 |
|---|---|---|
| 백엔드 | Flask 3.1 계열 | 서버 렌더링 MVP와 Windows 개발에 적합 |
| 화면 | Jinja2 + Bootstrap 5.3 + 전용 CSS | 빠른 구현, 접근성, 반응형과 다크 모드 |
| ORM | SQLAlchemy 2 + Alembic | 명시적 모델과 스키마 변경 이력 |
| 운영 DB | PostgreSQL | 다중 사용자, 권한 검색, 동시 편집 |
| 구조 | 모듈식 모놀리스 | 현재 규모에서 가장 단순한 배포와 트랜잭션 |
| 식별자 | UUID | 제목 변경과 무관한 안정된 URL |
| 파일 | DB 메타데이터 + 객체 저장소 | 대용량 바이너리와 접근 제어 분리 |
