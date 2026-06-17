# 내부 파이썬 코딩 표준 가이드라인 (PEP8 기반)

## 1. 네이밍 규칙

- 함수명, 변수명: `snake_case` (영문만 사용, 한글 금지)
- 클래스명: `PascalCase`
- 상수: `UPPER_SNAKE_CASE`
- Private 멤버: 언더스코어 prefix (`_private_method`)

```python
# 올바른 예시
MAX_RETRY_COUNT = 3
class UserManager:
    def validate_password(self, password: str) -> bool:
        _hashed = self._hash_password(password)
```

## 2. 타입 힌트 (필수)

모든 함수에 타입 힌트를 명시합니다.

```python
def register_user(username: str, password: str, email: str) -> dict:
    ...

def get_user_by_id(user_id: int) -> dict | None:
    ...
```

## 3. Docstring (필수)

```python
def validate_password(password: str) -> dict:
    """
    비밀번호 유효성을 검사합니다.

    Args:
        password: 검사할 비밀번호 문자열

    Returns:
        dict: {"valid": bool, "message": str}

    Raises:
        ValueError: password가 None인 경우
    """
```

## 4. 라인 길이 및 포맷

- 최대 79자
- 긴 문자열: 괄호 또는 백슬래시로 줄바꿈
- import는 파일 최상단에 위치 (함수 내부 import 금지)

## 5. 예외 처리

```python
# 올바른 예시: 구체적인 예외, 사용자에게 내부 오류 미노출
try:
    result = db.execute(query, params)
except sqlite3.IntegrityError:
    return {"success": False, "message": "이미 존재하는 사용자입니다."}
except Exception:
    logger.error("DB 오류", exc_info=True)
    return {"success": False, "message": "처리 중 오류가 발생했습니다."}
```

## 6. Redis 캐싱 정책

- TTL은 데이터 특성에 따라 결정: 사용자 세션 1800초, 설정값 3600초
- 캐시 키 형식: `{서비스명}:{리소스}:{id}` 예: `user:profile:1234`
- 캐시 미스 시 DB 조회 후 반드시 캐시 갱신

```python
import redis

REDIS_TTL_SESSION = 1800

def get_user_cached(user_id: int, redis_client: redis.Redis) -> dict | None:
    cache_key = f"user:profile:{user_id}"
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)
    user = db_get_user(user_id)
    if user:
        redis_client.setex(cache_key, REDIS_TTL_SESSION, json.dumps(user))
    return user
```
