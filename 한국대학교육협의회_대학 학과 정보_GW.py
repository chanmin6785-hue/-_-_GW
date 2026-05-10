from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any
from urllib.parse import unquote
import xml.etree.ElementTree as ET

import requests
from flask import Flask, jsonify, render_template, request


SERVICE_KEY = "a6428411d2a2e278131a879838396d58c6659ab1a9e6af9fa43699cccd452c16"
BASE_URL = "https://apis.data.go.kr/B340014/BasicInformationService_1"
CACHE_PATH = Path(__file__).with_name("school_cache.json")

SCHOOL_ID_SCAN_LIMIT = 800
SCHOOL_ID_SCAN_WORKERS = 32
DEFAULT_ROWS = "500"

SCHOOL_NAME_SEEDS = {
    "가천대학교": "0000063",
    "서울대학교": "0000019",
    "연세대학교": "0000149",
    "강릉원주대학교": "0000001",
    "국립강릉원주대학교": "0000001",
}

ENDPOINTS: dict[str, dict[str, Any]] = {
    "getUniversityMajorCode": {
        "label": "학과 정보 조회",
        "required": ["svyYr"],
        "optional": ["schoolName", "majorName", "schlId"],
    }
}

app = Flask(__name__)


@app.after_request
def add_cors_headers(response: Any) -> Any:
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


def normalized_name(value: str) -> str:
    return "".join(value.split()).lower()


def parse_survey_years(value: str) -> list[str]:
    years = [
        year.strip()
        for year in value.replace("\n", ",").replace(" ", ",").split(",")
        if year.strip()
    ]
    if not years:
        raise ValueError("조사년도를 입력해 주세요.")
    if any(not year.isdigit() or len(year) != 4 for year in years):
        raise ValueError("조사년도는 2025 또는 2025,2024처럼 입력해 주세요.")
    return list(dict.fromkeys(years))


def load_school_cache() -> dict[str, str]:
    cache = dict(SCHOOL_NAME_SEEDS)
    if CACHE_PATH.exists():
        try:
            raw_cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
            cache.update({str(name): str(school_id) for name, school_id in raw_cache.items()})
        except (OSError, json.JSONDecodeError):
            pass
    return cache


def save_school_cache(cache: dict[str, str]) -> None:
    CACHE_PATH.write_text(
        json.dumps(dict(sorted(cache.items())), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def choose_school_match(
    school_name: str,
    candidates: list[tuple[str, str]],
) -> tuple[str, str] | None:
    target = normalized_name(school_name)
    if not target:
        return None

    exact_matches = [
        (name, school_id)
        for name, school_id in candidates
        if target == normalized_name(name)
    ]
    if exact_matches:
        exact_matches.sort(key=lambda item: len(item[0]))
        return exact_matches[0][1], exact_matches[0][0]

    prefix_matches = [
        (name, school_id)
        for name, school_id in candidates
        if normalized_name(name).startswith(target)
    ]
    if prefix_matches:
        prefix_matches.sort(key=lambda item: len(item[0]))
        return prefix_matches[0][1], prefix_matches[0][0]

    contains_matches = [
        (name, school_id)
        for name, school_id in candidates
        if target in normalized_name(name)
    ]
    if contains_matches:
        contains_matches.sort(key=lambda item: len(item[0]))
        return contains_matches[0][1], contains_matches[0][0]

    return None


def strip_namespace(tag: str) -> str:
    return tag.split("}", 1)[-1]


def element_to_data(element: ET.Element) -> dict[str, Any] | str:
    children = list(element)
    if not children:
        return element.text or ""

    data: dict[str, Any] = {}
    for child in children:
        key = strip_namespace(child.tag)
        value = element_to_data(child)
        if key in data:
            if not isinstance(data[key], list):
                data[key] = [data[key]]
            data[key].append(value)
        else:
            data[key] = value
    return data


def normalize_items(body: dict[str, Any]) -> list[dict[str, Any]]:
    items = body.get("items", {})
    if not isinstance(items, dict):
        return []

    item = items.get("item", [])
    if isinstance(item, list):
        return [row for row in item if isinstance(row, dict)]
    if isinstance(item, dict):
        return [item]
    return []


def request_public_api(endpoint: str, params: dict[str, str], timeout: float = 15) -> dict[str, Any]:
    query = {
        "serviceKey": unquote(SERVICE_KEY),
        "pageNo": params.get("pageNo") or "1",
        "numOfRows": params.get("numOfRows") or DEFAULT_ROWS,
    }
    query.update({name: value for name, value in params.items() if value})

    response = requests.get(f"{BASE_URL}/{endpoint}", params=query, timeout=timeout)
    response.raise_for_status()

    root = ET.fromstring(response.content)
    parsed = element_to_data(root)
    if not isinstance(parsed, dict):
        return {"header": {}, "items": [], "totalCount": "0"}

    body = parsed.get("body", {})
    if not isinstance(body, dict):
        body = {}

    return {
        "endpoint": endpoint,
        "label": ENDPOINTS.get(endpoint, {}).get("label", endpoint),
        "header": parsed.get("header", {}),
        "totalCount": body.get("totalCount", "0"),
        "pageNo": body.get("pageNo", query["pageNo"]),
        "numOfRows": body.get("numOfRows", query["numOfRows"]),
        "items": normalize_items(body),
    }


def major_matches(item: dict[str, Any], major_name: str) -> bool:
    if not major_name:
        return True
    return normalized_name(major_name) in normalized_name(str(item.get("korMjrNm") or ""))


def get_school_major_items(school_id: str, survey_year: str) -> list[dict[str, Any]]:
    data = request_public_api(
        "getUniversityMajorCode",
        {
            "svyYr": survey_year,
            "schlId": school_id,
            "pageNo": "1",
            "numOfRows": DEFAULT_ROWS,
        },
        timeout=8,
    )
    return data.get("items", [])


def lookup_school_by_id(school_id: str, survey_year: str) -> dict[str, str] | None:
    items = request_public_api(
        "getUniversityMajorCode",
        {
            "svyYr": survey_year,
            "schlId": school_id,
            "pageNo": "1",
            "numOfRows": "1",
        },
        timeout=5,
    ).get("items", [])
    if not items:
        return None

    item = items[0]
    school_name = str(item.get("korSchlNm") or "").strip()
    resolved_id = str(item.get("schlId") or school_id).strip()
    if not school_name or not resolved_id:
        return None
    return {"name": school_name, "id": resolved_id}


def resolve_school_id(school_name: str, survey_year: str) -> tuple[str, str]:
    target = normalized_name(school_name)
    if not target:
        raise ValueError("학교명을 입력해 주세요.")

    cache = load_school_cache()
    cached_match = choose_school_match(school_name, list(cache.items()))
    if cached_match:
        return cached_match

    scanned_candidates: list[tuple[str, str]] = []
    school_ids = [f"{number:07d}" for number in range(1, SCHOOL_ID_SCAN_LIMIT + 1)]
    with ThreadPoolExecutor(max_workers=SCHOOL_ID_SCAN_WORKERS) as executor:
        futures = {
            executor.submit(lookup_school_by_id, school_id, survey_year): school_id
            for school_id in school_ids
        }
        for future in as_completed(futures):
            try:
                school = future.result()
            except (requests.RequestException, ET.ParseError):
                continue
            if not school:
                continue

            cache[school["name"]] = school["id"]
            scanned_candidates.append((school["name"], school["id"]))

    save_school_cache(cache)
    scanned_match = choose_school_match(school_name, scanned_candidates)
    if scanned_match:
        return scanned_match

    raise ValueError(f"'{school_name}' 학교명을 찾지 못했습니다. 학교명이 정확한지 확인해 주세요.")


def known_school_ids() -> list[str]:
    cached_ids = set(load_school_cache().values())
    if len(cached_ids) >= 50:
        return sorted(cached_ids)

    scanned_ids = {f"{number:07d}" for number in range(1, SCHOOL_ID_SCAN_LIMIT + 1)}
    return sorted(cached_ids | scanned_ids)


def nationwide_major_search(major_name: str, survey_year: str) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    cache = load_school_cache()

    with ThreadPoolExecutor(max_workers=SCHOOL_ID_SCAN_WORKERS) as executor:
        futures = {
            executor.submit(get_school_major_items, school_id, survey_year): school_id
            for school_id in known_school_ids()
        }
        for future in as_completed(futures):
            try:
                items = future.result()
            except (requests.RequestException, ET.ParseError):
                continue
            if not items:
                continue

            first = items[0]
            school_name = str(first.get("korSchlNm") or "").strip()
            school_id = str(first.get("schlId") or futures[future]).strip()
            if school_name and school_id:
                cache[school_name] = school_id

            matches.extend(item for item in items if major_matches(item, major_name))

    save_school_cache(cache)
    return matches


def build_major_response(
    items: list[dict[str, Any]],
    years: list[str],
    resolved_school_name: str = "",
    resolved_school_id: str = "",
) -> dict[str, Any]:
    return {
        "endpoint": "getUniversityMajorCode",
        "label": "학과 정보 조회",
        "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE."},
        "totalCount": str(len(items)),
        "pageNo": "1",
        "numOfRows": str(len(items)),
        "items": items,
        "surveyYears": years,
        "resolvedSchoolName": resolved_school_name,
        "resolvedSchoolId": resolved_school_id,
    }


def search_university_major(params: dict[str, str]) -> dict[str, Any]:
    years = parse_survey_years(params.get("svyYr", ""))
    school_name = params.get("schoolName", "").strip()
    major_name = params.get("majorName", "").strip()
    school_id = params.get("schlId", "").strip()

    if not school_name and not major_name and not school_id:
        raise ValueError("학교명 또는 학과명 중 하나 이상을 입력해 주세요.")

    all_items: list[dict[str, Any]] = []
    resolved_school_name = school_name
    resolved_school_id = school_id

    if school_name or school_id:
        if not school_id:
            resolved_school_id, resolved_school_name = resolve_school_id(school_name, years[0])
        for year in years:
            items = get_school_major_items(resolved_school_id, year)
            all_items.extend(item for item in items if major_matches(item, major_name))
    else:
        for year in years:
            all_items.extend(nationwide_major_search(major_name, year))

    return build_major_response(all_items, years, resolved_school_name, resolved_school_id)


@app.get("/")
def index() -> str:
    return render_template("index.html")


@app.get("/api/search")
def search() -> Any:
    endpoint = request.args.get("endpoint", "")
    if endpoint not in ENDPOINTS:
        return jsonify({"error": "지원하지 않는 API입니다."}), 400

    params = {
        key: value.strip()
        for key, value in request.args.items()
        if key != "endpoint" and value.strip()
    }

    try:
        data = search_university_major(params)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except requests.HTTPError as exc:
        return jsonify({"error": "공공데이터 API 호출에 실패했습니다.", "detail": str(exc)}), 502
    except ET.ParseError:
        return jsonify({"error": "API 응답 XML을 해석하지 못했습니다."}), 502
    except requests.RequestException as exc:
        return jsonify({"error": "네트워크 요청에 실패했습니다.", "detail": str(exc)}), 502

    return jsonify(data)


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
