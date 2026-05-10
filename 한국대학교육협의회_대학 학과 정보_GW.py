from flask import Flask, render_template, request, jsonify
import requests

app = Flask(__name__)

# 요청하신 서비스 인증키 내장
SERVICE_KEY = 'a6428411d2a2e278131a879838396d58c6659ab1a9e6af9fa43699cccd452c16'
# API 요청 URL (HTML 파일 기반)
BASE_URL = 'http://api.data.go.kr/openapi/tn_pubr_public_univ_mdept_info_api'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['GET'])
def search_dept():
    # 검색어 (학과명 등)
    keyword = request.args.get('keyword', '')
    
    params = {
        'serviceKey': SERVICE_KEY,
        'pageNo': '1',
        'numOfRows': '10',
        'type': 'json', # JSON 형식으로 응답 받기
        'mdeptNm': keyword # 학과명으로 검색
    }

    try:
        response = requests.get(BASE_URL, params=params)
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({'error': '데이터를 가져오는데 실패했습니다.'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
