import requests
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# 제공된 서비스 키
SERVICE_KEY = "a6428411d2a2e278131a879838396d58c6659ab1a9e6af9fa43699cccd452c16"
# API 엔드포인트 기초 URL
BASE_URL = "https://apis.data.go.kr/B340014/BasicInformationService_1"

def fetch_major_info(school_nm, major_nm, year):
    """API를 호출하여 학과 정보를 가져오는 함수"""
    endpoint = f"{BASE_URL}/getUniversityMajorCode"
    params = {
        "serviceKey": SERVICE_KEY,
        "pageNo": "1",
        "numOfRows": "1000", # 충분한 데이터를 가져오기 위해 설정
        "korSchlNm": school_nm,
        "korMjrNm": major_nm,
        "svyYr": year,
        "format": "json"
    }
    try:
        response = requests.get(endpoint, params=params, timeout=15)
        if response.status_code == 200:
            data = response.json()
            # API 응답 구조에 따라 데이터 추출
            items = data.get("body", {}).get("items", {}).get("item", [])
            if isinstance(items, dict): items = [items] # 결과가 1개일 때 처리
            return items
        return []
    except Exception as e:
        print(f"Error fetching data: {e}")
        return []

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/search')
def search():
    school_name = request.args.get('schoolName', '').strip()
    major_name = request.args.get('majorName', '').strip()
    survey_years = request.args.get('svyYr', '2025').replace(' ', '').split(',')

    all_results = []
    
    for year in survey_years:
        items = fetch_major_info(school_name, major_name, year)
        
        if school_name:
            # 학교명 매칭 개선: 완전 일치하는 항목을 상단으로, 나머지는 포함된 항목 유지
            exact_match = [item for item in items if item.get('korSchlNm') == school_name]
            partial_match = [item for item in items if item.get('korSchlNm') != school_name]
            items = exact_match + partial_match
            
        all_results.extend(items)

    return jsonify({
        "totalCount": len(all_results),
        "items": all_results,
        "surveyYears": survey_years,
        "resolvedSchoolName": school_name if school_name else "전국"
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)
