"""
aws_rag_reviewer 실행을 위한 메인 엔트리포트 스크립트
"""
from aws_rag_reviewer import init_aws_credentials, style_check, generate_security_report_json, full_project_review

def main():
    KB_ID = init_aws_credentials()
    
    print("\n=== [1] 단일 취약 코드 테스트 및 JSON 생성 ===")
    vulnerable_sample = "\ndef get_user_by_name(username):\n    query = \"SELECT * FROM users WHERE name = '\" + username + \"'\"\n    return query\n"
    
    print("\n[스타일 검사 결과]")
    print(style_check(vulnerable_sample, KB_ID))
    
    print("\n[JSON 리포트 추출 및 저장]")
    json_report = generate_security_report_json(vulnerable_sample, KB_ID)
    with open('security_report.json', 'w', encoding='utf-8') as json_f:
        json_f.write(json_report)
    print("✅ 로컬 파일 저장 완료: security_report.json")

    print("\n=== [2] 전체 프로젝트 일괄 파일 스캔 테스트 ===")
    TARGET_DIR = "./" 
    full_project_review(TARGET_DIR, KB_ID)

if __name__ == "__main__":
    main()
