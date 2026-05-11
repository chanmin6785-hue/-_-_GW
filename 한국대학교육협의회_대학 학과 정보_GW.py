from flask import Flask, render_template, request, jsonify
import requests
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# 서비스 키 설정
SERVICE_KEY = "a6428411d2a2e278131a879838396d58c6659ab1a9e6af9fa43699cccd452c16"
BASE_URL = "https://apis.data.go.kr/B340014/BasicInformationService_1/getUniversityMajorCode"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/search')
def search():
    school_name = request.args.get('schoolName', '').strip()
    major_name = request.args.get('majorName', '').strip()
    # 쉼표로 구분된 년도를 리스트로 변환
    survey_years = [y.strip() for y in request.args.get('svyYr', '2025').split(',') if y.strip()]
    
    combined_items = []
    
    for year in survey_years:
        params = {
            "serviceKey": SERVICE_KEY,
            "pageNo": "1",
            "numOfRows": "1000",
            "svyYr": year,
            "korSchlNm": school_name,
            "korMjrNm": major_name,
            "format": "json"
        }
        
        try:
            response = requests.get(BASE_URL, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                items = data.get("body", {}).get("items", {}).get("item", [])
                
                # 데이터가 단일 객체(dict)인 경우 리스트로 변환
                if isinstance(items, dict):
                    items = [items]
                
                # 학교명 매칭 개선: 완전 일치 우선 정렬
                if school_name:
                    items.sort(key=lambda x: x.get('korSchlNm') != school_name)
                
                combined_items.extend(items)
        except Exception as e:
            print(f"Error fetching data for year {year}: {e}")

    return jsonify({
        "totalCount": len(combined_items),
        "items": combined_items,
        "surveyYears": survey_years,
        "resolvedSchoolName": school_name
    })

if __name__ == '__main__':
    # 반드시 포트 5000번으로 실행
    app.run(host='127.0.0.1', port=5000, debug=True)
