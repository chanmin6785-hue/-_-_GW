from flask import Flask, render_template, request
import requests
import xmltodict

app = Flask(__name__)

SERVICE_KEY = "여기에_본인_API_키"


@app.route('/', methods=['GET', 'POST'])
def home():

    majors = []
    university = ""

    if request.method == 'POST':

        university = request.form['university']

        url = "http://openapi.academyinfo.go.kr/openapi/service/rest/SchoolMajorInfoService/getSchoolMajorInfo"

        params = {
            'serviceKey': SERVICE_KEY,
            'pageNo': '1',
            'numOfRows': '20',
            'svyYr': '2023',
            'schlKrnNm': university
        }

        response = requests.get(url, params=params)

        data = xmltodict.parse(response.text)

        body = data['response']['body']

        if body['totalCount'] != '0':

            items = body['items']['item']

            if isinstance(items, list):
                majors = items
            else:
                majors = [items]

    return render_template(
        'index.html',
        majors=majors,
        university=university
    )


app.run(debug=True)