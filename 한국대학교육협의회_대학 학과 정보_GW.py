import requests
from fastapi import FastAPI, Query
from typing import List, Optional

app = FastAPI()

# 제공된 서비스 키
SERVICE_KEY = "a6428411d2a2e278131a879838396d58c6659ab1a9e6af9fa43699cccd452c16"
ENDPOINT = "http://api.data.go.kr/openapi/tn_pubr_public_univ_major_info_api"

@app.get("/search")
async def search_major(
    univ_name: Optional[str] = None,
    major_name: Optional[str] = None,
    years: List[str] = Query(None)
):
    params = {
        "serviceKey": SERVICE_KEY,
        "type": "json",
        "numOfRows": 1000, # 충분한 양을 가져와서 후처리
        "pageNo": 1
    }
    
    # API 요청 조건 설정
    if univ_name:
        params["univNm"] = univ_name
    if major_name:
        params["majorNm"] = major_name
        
    try:
        response = requests.get(ENDPOINT, params=params)
        data = response.json()
        
        items = data.get("response", {}).get("body", {}).get("items", [])
        
        # 1. 조사년도 필터링
        if years:
            items = [item for item in items if item.get("stdYr") in years]
            
        # 2. 학교명 매칭 개선 (완전일치 우선 정렬)
        if univ_name:
            # 입력된 학교명과 정확히 일치하는 항목을 위로, 나머지는 아래로 정렬
            items.sort(key=lambda x: (x.get("univNm") != univ_name, x.get("univNm")))
            
        return {"status": "success", "count": len(items), "data": items}
    
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
