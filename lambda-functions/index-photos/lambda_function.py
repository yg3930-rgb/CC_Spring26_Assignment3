import json
import boto3
import urllib.parse
import urllib.request
import base64

rekognition = boto3.client("rekognition")
s3 = boto3.client("s3")

OPENSEARCH_HOST = "search-photos-7ijoaxtycdp356y34xd4h5tlli.us-east-1.es.amazonaws.com"
INDEX = "photos"

USERNAME = "admin"
PASSWORD = "Gyy2003516@"

def lambda_handler(event, context):
    print("EVENT:", json.dumps(event))

    bucket = event["Records"][0]["s3"]["bucket"]["name"]
    key = urllib.parse.unquote_plus(event["Records"][0]["s3"]["object"]["key"])

    # 1. Rekognition 自动识别图片标签
    rek_response = rekognition.detect_labels(
        Image={
            "S3Object": {
                "Bucket": bucket,
                "Name": key
            }
        },
        MaxLabels=10
    )

    labels = [label["Name"].lower() for label in rek_response["Labels"]]

    # 2. 读取用户上传时的自定义标签
    head_response = s3.head_object(Bucket=bucket, Key=key)
    metadata = head_response.get("Metadata", {})

    custom_labels = []
    if "customlabels" in metadata:
        custom_labels = [
            label.strip().lower()
            for label in metadata["customlabels"].split(",")
            if label.strip()
        ]

    all_labels = list(set(labels + custom_labels))

    # 3. 构造写入 OpenSearch 的文档
    document = {
        "objectKey": key,
        "bucket": bucket,
        "createdTimestamp": head_response["LastModified"].isoformat(),
        "labels": all_labels
    }

    print("DOCUMENT:", json.dumps(document))

    # 4. 写入 OpenSearch（用 objectKey 作为文档 ID，防止重复）
    url = f"https://{OPENSEARCH_HOST}/{INDEX}/_doc/{urllib.parse.quote(key, safe='')}"
    data = json.dumps(document).encode("utf-8")
    credentials = f"{USERNAME}:{PASSWORD}"
    encoded_credentials = base64.b64encode(credentials.encode("utf-8")).decode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Basic {encoded_credentials}"
        },
        method="PUT"  # 改成 PUT，POST 不支持指定 ID
    )
    with urllib.request.urlopen(request) as response:
        result = response.read().decode("utf-8")
        print("OPENSEARCH RESPONSE:", result)

    return {
        "statusCode": 200,
        "body": json.dumps("Indexed successfully")
    }