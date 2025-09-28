#!/bin/bash

export AWS_ACCESS_KEY_ID=000000000000 AWS_SECRET_ACCESS_KEY=000000000000

awslocal s3 mb s3://${BUCKET_NAME}
awslocal sqs create-queue --queue-name ${QUEUE_NAME}