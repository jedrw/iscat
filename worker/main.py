import logging
import io
import json
import os
import sys
import cv2
import boto3
from mypy_boto3_s3 import S3ServiceResource
from mypy_boto3_s3.service_resource import Bucket
from mypy_boto3_sqs import SQSServiceResource
from mypy_boto3_sqs.service_resource import Queue
import numpy as np
from ultralytics import YOLO

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# https://github.com/ultralytics/ultralytics/blob/main/ultralytics/cfg/datasets/coco.yaml
DETECTION_TYPES = {
    "cat": 15,
}

BUCKET_NAME = os.getenv("BUCKET_NAME")
if not BUCKET_NAME:
    logging.critical('"BUCKET_NAME" must be set')
    sys.exit(1)
QUEUE_NAME = os.getenv("QUEUE_NAME")
if not QUEUE_NAME:
    logging.critical('"QUEUE_NAME" must be set')
    sys.exit(1)

s3: S3ServiceResource = boto3.resource("s3")
bucket: Bucket = s3.Bucket(BUCKET_NAME)
sqs: SQSServiceResource = boto3.resource("sqs")
queue: Queue = sqs.get_queue_by_name(QueueName=QUEUE_NAME)


def main():
    model = YOLO("yolov8n.pt")
    while True:
        try:
            messages = queue.receive_messages(
                MessageAttributeNames=["All"],
                MaxNumberOfMessages=1,
                WaitTimeSeconds=1,
            )

            if not messages:
                continue

            msg = messages[0]
            image_id = msg.body
            detection_type_attr = (
                msg.message_attributes.get("detectionType")
                if msg.message_attributes
                else None
            )
            detection_type_str = (
                detection_type_attr.get("StringValue") if detection_type_attr else None
            )
            if not detection_type_str:
                logging.error('Msg had no "detect_type" attribute')
                continue

            detect_type = DETECTION_TYPES[detection_type_str]
            if not detect_type:
                logging.error(
                    f'Unsupported detect_type attribute: "{detection_type_str}"'
                )
                continue

            obj = bucket.Object(image_id)
            obj_body = obj.get()["Body"].read()
            image_bytes: bytes = obj_body
            nparray = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparray, cv2.IMREAD_COLOR)

            logging.info(f"detecting {detection_type_str} in {image_id}")
            scan_results = model(img, verbose=False)
            detected = False
            for result in scan_results:
                boxes = result.boxes
                class_ids = boxes.cls.cpu().numpy().astype(int)
                if detect_type in class_ids:
                    detected = True

                logging.info(
                    f"detected {detection_type_str} in {image_id}"
                    if detected
                    else f"did not detect {detection_type_str} in {image_id}"
                )
                result_data = {
                    "detected": detected,
                    "detection_type": detection_type_str,
                }

                json_bytes = io.BytesIO(json.dumps(result_data).encode("utf-8"))
                bucket.put_object(Key=f"{image_id}.json", Body=json_bytes)

        except Exception as e:
            logging.error(f"Unexpected Error: {e}")
            continue

        msg.delete()


if __name__ == "__main__":
    main()
