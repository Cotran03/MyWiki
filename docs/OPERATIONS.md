# 운영과 데이터베이스

## 개발 DB 시작과 중지

```powershell
docker compose up -d db
docker compose stop db
docker compose start db
docker compose ps
```

컨테이너를 다시 만들어도 `postgres18-data` 볼륨에 데이터가 유지됩니다.

`docker compose down -v`는 볼륨과 모든 개발 데이터를 삭제하므로 초기화가 명확히 필요한 경우에만 사용합니다.

## 스키마 배포

코드를 배포한 뒤 웹 프로세스를 시작하기 전에 한 번만 실행합니다.

```powershell
.venv\Scripts\flask --app wsgi:app db upgrade
.venv\Scripts\flask --app wsgi:app db current
```

여러 웹 인스턴스가 동시에 migration을 실행하지 않도록 배포 단계에서 분리해야 합니다.

## 개발 DB 백업

`backups` 폴더를 만든 뒤 다음 명령을 실행합니다.

```powershell
New-Item -ItemType Directory -Force backups
docker compose exec -T db pg_dump -U mywiki -d mywiki -Fc -f /tmp/mywiki.dump
docker compose cp db:/tmp/mywiki.dump backups/mywiki.dump
```

운영에서는 셸 리디렉션 대신 공급자의 자동 백업과 암호화된 별도 저장소를 사용합니다.

## 복구 예시

복구는 기존 데이터를 덮을 수 있으므로 운영에서 바로 실행하지 않습니다. 먼저 빈 검증 DB에 복원하고 확인합니다.

```powershell
docker compose cp backups/mywiki.dump db:/tmp/mywiki.dump
docker compose exec -T db createdb -U mywiki mywiki_restore_test
docker compose exec -T db pg_restore -U mywiki -d mywiki_restore_test --clean --if-exists /tmp/mywiki.dump
```

검증 후 테스트 DB를 삭제하는 작업은 별도 승인을 거쳐 수행합니다.

## 초기 운영 기준

- 데이터베이스와 객체 저장소 매일 자동 백업
- 백업 30일 보관
- 월 1회 실제 복구 시험
- RPO 24시간, RTO 4시간
- 외부 공개 전 HTTPS 필수
- `SECRET_KEY`, DB 비밀번호, SMTP 사용자명·비밀번호는 비밀 저장소에서 주입
- 운영에서는 `MAIL_BACKEND=smtp`, 공개 HTTPS `BASE_URL`, 인증된 발신 주소 사용
- `/health/live`, `/health/ready`, 5xx, 응답 지연, DB 용량, 백업 실패 모니터링

## 운영 배포 전 남은 결정

- PaaS/컨테이너 공급자
- 관리형 PostgreSQL 공급자
- 트랜잭션 이메일 공급자
- 이미지용 비공개 S3 호환 객체 저장소
- 커스텀 도메인
