# 내부 보안 정책 (OWASP Top 10 기반)

## 1. 비밀번호 정책

- 최소 12자 이상
- 대문자, 소문자, 숫자, 특수문자 각 1개 이상 포함
- bcrypt 또는 argon2 해싱 필수 (MD5/SHA1 금지)

```python
import re
import bcrypt

PASSWORD_MIN_LENGTH = 12
PASSWORD_PATTERN = re.compile(
    r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*]).{12,}$'
)

def validate_password(password: str) -> dict:
    if not PASSWORD_PATTERN.match(password):
        return {
            "valid": False,
            "message": "비밀번호는 12자 이상, 대소문자·숫자·특수문자 포함 필요"
        }
    return {"valid": True, "message": "유효한 비밀번호"}

def hash_password(password: str) -> bytes:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

def verify_password(password: str, hashed: bytes) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed)
```

## 2. SQL Injection 방지

파라미터 바인딩을 항상 사용합니다.

```python
# 금지: f-string SQL
query = f"SELECT * FROM users WHERE username = '{username}'"  # ❌

# 필수: 파라미터 바인딩
query = "SELECT * FROM users WHERE username = ? AND password = ?"
cursor.execute(query, (username, hashed_password))  # ✅
```

## 3. 민감 정보 관리

- API 키, 비밀번호는 소스코드에 절대 하드코딩 금지
- 환경변수 또는 AWS Secrets Manager 사용

```python
import os

# 금지
JIRA_TOKEN = "ATxxxxxxxxxxxxxxxx"  # ❌

# 필수
JIRA_TOKEN = os.environ.get("JIRA_API_TOKEN")  # ✅
```

## 4. 난수 생성

보안 목적의 난수는 `secrets` 모듈 사용 (`random` 모듈 금지).

```python
import secrets

def generate_temp_password(length: int = 16) -> str:
    chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$"
    return "".join(secrets.choice(chars) for _ in range(length))
```

## 5. 에러 메시지 정책

사용자에게 내부 구조 정보를 노출하지 않습니다.

```python
# 금지: DB 오류 그대로 노출
return {"error": str(e)}  # ❌

# 필수: 일반 메시지 반환, 상세 내용은 서버 로그
logger.error("DB 오류 발생", exc_info=True)
return {"error": "처리 중 오류가 발생했습니다. 관리자에게 문의하세요."}  # ✅
```

## 6. 인증/권한 검증

role 값은 반드시 서버 DB에서 직접 조회합니다.

```python
# 금지: 클라이언트 입력값으로 권한 판단
def delete_post(post_id: int, role: str) -> dict:  # ❌
    if role == "admin": ...

# 필수: DB에서 role 조회
def delete_post(post_id: int, username: str) -> dict:
    cursor.execute("SELECT role FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    if not row or row[0] != "admin":
        return {"success": False, "message": "권한 없음"}
```
