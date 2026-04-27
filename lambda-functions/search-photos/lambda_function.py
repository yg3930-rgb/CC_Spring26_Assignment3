import json
import urllib.parse
import urllib.request
import base64
import boto3
import uuid

OPENSEARCH_HOST = "search-photos-7ijoaxtycdp356y34xd4h5tlli.us-east-1.es.amazonaws.com"
INDEX = "photos"

USERNAME = "admin"
PASSWORD = "Gyy2003516@"

LEX_REGION = "us-east-1"
BOT_ID = "HPZA2DIIV7"
BOT_ALIAS_ID = "TSTALIASID"
LOCALE_ID = "en_US"

lex = boto3.client("lexv2-runtime", region_name=LEX_REGION)

def lambda_handler(event, context):
    print("EVENT:", json.dumps(event))

    query_params = event.get("queryStringParameters") or {}
    q = query_params.get("q", "")
    q = urllib.parse.unquote_plus(q).lower().strip()
    q = q.replace(",", " ")
    if not q:
        return response([])

    keywords = get_keywords_from_lex(q)

    if not keywords:
        keywords = extract_keywords_fallback(q)

    print("KEYWORDS:", keywords)

    if not keywords:
        return response([])

    search_body = {
        "query": {
            "bool": {
                "should": [
                    {"match": {"labels": keyword}}
                    for keyword in keywords
                ],
                "minimum_should_match": 1
            }
        }
    }

    url = f"https://{OPENSEARCH_HOST}/{INDEX}/_search"
    response_text = send_opensearch_request(url, search_body)
    response_json = json.loads(response_text)

    results = []

    for hit in response_json.get("hits", {}).get("hits", []):
        source = hit["_source"]
        bucket = source["bucket"]
        object_key = source["objectKey"]

        image_url = f"https://{bucket}.s3.amazonaws.com/{urllib.parse.quote(object_key)}"

        results.append({
            "url": image_url,
            "labels": source.get("labels", [])
        })

    return response(results)


def get_keywords_from_lex(text):
    try:
        lex_response = lex.recognize_text(
            botId=BOT_ID,
            botAliasId=BOT_ALIAS_ID,
            localeId=LOCALE_ID,
            sessionId=str(uuid.uuid4()),
            text=text
        )

        print("LEX RESPONSE:", json.dumps(lex_response))

        slots = lex_response.get("sessionState", {}).get("intent", {}).get("slots", {}) or {}

        keywords = []

        for slot_name in ["keyword", "keyword1", "keyword2"]:
            slot = slots.get(slot_name)
            if slot and slot.get("value"):
                value = slot["value"].get("interpretedValue")
                if value:
                    keywords.append(value.lower().strip())

        return keywords

    except Exception as e:
        print("LEX ERROR:", str(e))
        return []


def extract_keywords_fallback(q):
    stop_words = {
        "show", "me", "photos", "photo", "pictures", "picture",
        "with", "and", "in", "them", "of", "the", "a", "an",
        "find", "search", "for"
    }

    words = q.replace(",", " ").split()

    return [
        word.strip()
        for word in words
        if word.strip() and word.strip() not in stop_words
    ]


def send_opensearch_request(url, body):
    data = json.dumps(body).encode("utf-8")

    credentials = f"{USERNAME}:{PASSWORD}"
    encoded_credentials = base64.b64encode(credentials.encode("utf-8")).decode("utf-8")

    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Basic {encoded_credentials}"
        },
        method="POST"
    )

    with urllib.request.urlopen(request) as response:
        return response.read().decode("utf-8")


def response(results):
    return {
        "statusCode": 200,
        "headers": {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Allow-Methods": "GET,OPTIONS"
        },
        "body": json.dumps({"results": results})
    }