"""
aws_rag_reviewer: 대규모 프로젝트 파일 일괄 스캔 및 마크다운 리포트 생성 모듈
"""
from pathlib import Path
import sys
from .reviewer import style_check, check_security

def full_project_review(project_path, kb_id):
    """특정 디렉토리 내 모든 파이썬 파일 스캔 및 마크다운 리포트 생성"""
    results = {}
    total_lines = 0
    path_obj = Path(project_path)

    if not path_obj.exists():
        print(f"⚠️ 경고: 리뷰할 디렉토리가 존재하지 않습니다: {project_path}")
        return

    exclude_dirs = {'.venv', 'venv', '__pycache__', '.git'}

    for py_file in path_obj.glob('**/*.py'):
        if any(part in exclude_dirs for part in py_file.parts):
            continue

        code = None
        for encoding in ['utf-8', 'cp949', 'latin-1']:
            try:
                with open(py_file, 'r', encoding=encoding) as f:
                    code = f.read()
                break
            except Exception:
                continue

        if code is None or len(code.splitlines()) < 5:
            continue

        print(f"🔄 분석 중: {py_file.name}")
        
        try:
            style_result = style_check(code, kb_id)
            security_result = check_security(code, kb_id)
            file_lines = len(code.splitlines())
            total_lines += file_lines

            results[py_file.name] = {
                'style': style_result,
                'security': security_result,
                'lines': file_lines
            }
        except Exception as e:
            print(f"❌ {py_file.name} 처리 중 오류 발생: {e}", file=sys.stderr)

    print(f"\n📊 총 검사된 코드 라인 수: {total_lines}줄")

    # 리포트 내 제목 명칭도 함께 수정되었습니다.
    report_output_path = path_obj / "project_review_report.md"
    report_content = f"""# 🚀 AWS RAG Reviewer 통합 코드 리뷰 리포트

- **총 검사 라인 수:** {total_lines}줄
- **검사 도구:** Amazon Bedrock (Claude 3.5 Sonnet)
- **기반 문서:** Knowledge Base (PEP8 가이드라인 & OWASP Top 10)

---

"""
    for filename, data in results.items():
        report_content += f"""## 📄 파일: {filename} ({data['lines']}줄)

### 🔹 1. 스타일 검사 결과 (PEP8)
{data['style']}

### 🔹 2. 보안 취약점 검사 결과
{data['security']}

---
"""

    with open(report_output_path, 'w', encoding='utf-8') as f:
        f.write(report_content)

    print(f"✅ 종합 마크다운 리포트 생성 완료!\n👉 경로: {report_output_path}")
    return results
