import json
import logging
import os
import sys
import uuid
from flask import Flask, request, render_template, jsonify
import boto3
from botocore.exceptions import ClientError
from mypy_boto3_s3 import S3ServiceResource
from mypy_boto3_s3.service_resource import Bucket
from mypy_boto3_sqs import SQSServiceResource
from mypy_boto3_sqs.service_resource import Queue

app = Flask(__name__)
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY")
if not FLASK_SECRET_KEY:
    app.logger.critical('"FLASK_SECRET_KEY" must be set')  #
    sys.exit(1)
app.config["SECRET_KEY"] = FLASK_SECRET_KEY

BUCKET_NAME = os.getenv("BUCKET_NAME")
if not BUCKET_NAME:
    app.logger.critical('"BUCKET_NAME" must be set')
    sys.exit(1)
QUEUE_NAME = os.getenv("QUEUE_NAME")
if not QUEUE_NAME:
    app.logger.critical('"QUEUE_NAME" must be set')
    sys.exit(1)

ALLOWED_EXTENSIONS = {"jpeg", "jpg", "png"}

s3: S3ServiceResource = boto3.resource("s3")
bucket: Bucket = s3.Bucket(BUCKET_NAME)
sqs: SQSServiceResource = boto3.resource("sqs")
queue: Queue = sqs.get_queue_by_name(QueueName=QUEUE_NAME)


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def is_valid_uuidv4(id: str) -> bool:
    try:
        uuid.UUID(str(id), version=4)
        return True
    except ValueError:
        return False


@app.route("/", methods=["GET"])
def index():
    if request.method == "GET":
        return render_template("index.html")


@app.route("/scan", methods=["POST"])
def upload():
    if request.method == "POST":
        if len(request.files) != 1 or "file" not in request.files:
            return jsonify({"error": "exactly one file must be uploaded."}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "exactly one file must be uploaded."}), 400

        if not allowed_file(file.filename):
            return (
                jsonify({"error": "file type not allowed, upload PNG, JPEG or JPG."}),
                400,
            )

        image_id = str(uuid.uuid4())
        try:
            bucket.put_object(Key=image_id, Body=file)
            app.logger.info(f"stored {image_id} in bucket")
            queue.send_message(
                MessageBody=image_id,
                MessageAttributes={
                    "detectionType": {
                        "StringValue": "cat",
                        "DataType": "String",
                    },
                },
            )
            app.logger.info(f"added {image_id} to queue")
        except ClientError as e:
            app.logger.error(e)
            return jsonify({"error": "something went wrong"}), 500

        return jsonify({"image_id": image_id, "status": "queued"}), 201


@app.route("/result/<image_id>", methods=["GET"])
def result(image_id: str):
    if not is_valid_uuidv4(image_id):
        return jsonify({"error": "invalid image_id"}), 400

    try:
        obj = bucket.Object(f"{image_id}.json")
        obj_body = obj.get()["Body"].read()
        result = json.loads(obj_body)
        return (
            jsonify(
                {
                    "image_id": image_id,
                    "detection_type": result.get("detection_type"),
                    "detected": result.get("detected", False),
                    "status": "scanned",
                }
            ),
            200,
        )
    except ClientError as e:
        app.logger.info(e)
        if e.response["Error"]["Code"] == "NoSuchKey":
            try:
                img_obj = bucket.Object(image_id)
                img_obj.load()
                return (
                    jsonify(
                        {
                            "image_id": image_id,
                            "status": "queued",
                        }
                    ),
                    202,
                )
            except ClientError as e:
                app.logger.error(e)
                if e.response["Error"]["Code"] == "404":
                    return jsonify({"error": "unknown image_id"}), 202
                return jsonify({"error": "something went wrong"}), 500
        else:
            return jsonify({"error": "something went wrong"}), 500


if __name__ != "__main__":
    gunicorn_logger = logging.getLogger("gunicorn.error")
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(gunicorn_logger.level)
