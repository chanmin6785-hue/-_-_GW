import requests
from fastapi import FastAPI, Query
from typing import List, Optional
from urllib.parse import unquote

app = FastAPI()

# 제공된 서비스 키 (인코딩 문제 방지를 위해 unquote 처리)
RAW_SERVICE_KEY = "a6428411d2a2e278131a879838396d58c6659ab1a9e6af9fa43699cccd452c16"
SERVICE_KEY = unquote(RAW_SERVICE_KEY)

# 엔드포인트 URL (명세서에 따른 정확한 주소 확인 필요)
ENDPOINT = "http://api.data.go.kr/openapi/tn_pubr_public_univ_major_info_api"

@app.get("/search")
async def search_major(
    univ_name: Optional[str] = None,
    major_name: Optional[str] = None,
    years: List[str] = Query(None)
):
    # 필수 파라미터 구성
    params = {
        "serviceKey": SERVICE_KEY,
        "type": "json",
        "numOfRows": 100,
        "pageNo": 1
    }
    
    # 조건별 파라미터 추가
    if univ_name:
        params["univNm"] = univ_name
    if major_name:
        params["majorNm"] = major_name

    try:
        # API 호출
        response = requests.get(ENDPOINT, params=params, timeout=10)
        data = response.json()
        
        # 공공데이터 API 특유의 에러 응답 처리
        header = data.get("response", {}).get("header", {})
        if header.get("resultCode") != "00":
            return {"status": "error", "message": header.get("resultMsg")}

        items = data.get("response", {}).get("body", {}).get("items", [])
        
        # 1. 조사년도 필터링 (복수 입력 가능 처리)
        if years and items:
            items = [item for item in items if item.get("stdYr") in years]
            
        # 2. 학교명 매칭 개선 (완전 일치 우선 정렬)
        if univ_name and items:
            # univNm이 입력값과 정확히 일치하면 0순위, 포함만 되면 1순위로 정렬
            items.sort(key=lambda x: (x.get("univNm") != univ_name, x.get("univNm")))
            
        return {"status": "success", "count": len(items), "data": items}
    
    except Exception as e:
        return {"status": "error", "message": f"서버 연결 오류: {str(e)}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
