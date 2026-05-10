from flask import Flask, render_template, request, jsonify
import requests

app = Flask(__name__)

# [설정] 제공해주신 서비스 인증키 내장
SERVICE_KEY = 'a6428411d2a2e278131a879838396d58c6659ab1a9e6af9fa43699cccd452c16'
# API 엔드포인트 (HTML 가이드 기반)
BASE_URL = 'http://api.data.go.kr/openapi/tn_pubr_public_univ_mdept_info_api'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['GET'])
def search_dept():
    # 검색 키워드 (학과명)
    keyword = request.args.get('keyword', '')
    
    # API 요청 파라미터 구성
    params = {
        'serviceKey': SERVICE_KEY,
        'pageNo': '1',
        'numOfRows': '20', # 한 번에 보여줄 결과 수
        'type': 'json',    # JSON 응답 요청
        'mdeptNm': keyword # 학과명 검색 파라미터
    }

    try:
        # 공공데이터 API 호출
        response = requests.get(BASE_URL, params=params, timeout=10)
        
        # HTTP 상태 코드 확인
        if response.status_code == 200:
            data = response.json()
            return jsonify(data)
        else:
            return jsonify({
                'resultCode': 'ERROR',
                'message': f'API 호출 실패 (Status: {response.status_code})'
            }), 500
            
    except Exception as e:
        return jsonify({
            'resultCode': 'EXCEPTION',
            'message': f'서버 내부 오류: {str(e)}'
        }), 500

if __name__ == '__main__':
    # 5000번 포트로 서버 실행
    app.run(host='0.0.0.0', port=5000, debug=True)
