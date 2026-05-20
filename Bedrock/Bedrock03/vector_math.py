import numpy as np

def cosine_similarity(vec1: list, vec2: list) -> float:
    """
    두 벡터 간의 코사인 유사도를 계산하여 -1.0 ~ 1.0 사이의 값을 반환합니다.
    1.0에 가까울수록 문맥상 아주 유사한 의미를 가집니다.
    """
    v1 = np.array(vec1)
    v2 = np.array(vec2)
    
    # 0으로 나누는 오류(Division by Zero)를 방지하기 위한 예외 처리
    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
        
    return float(np.dot(v1, v2) / (norm1 * norm2))
