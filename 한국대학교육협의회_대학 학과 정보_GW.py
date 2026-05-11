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
