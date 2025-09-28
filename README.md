# isCat?

Design features:

- It is possible to interact with the application via either the web interface or directly with the api endpoints for each action.
- Both the api and worker components are independantly scalable, the worker could also scaled based on the SQS queue length and even scale to zero.
- Includes some of the foundations to enable easy introduction of support for scanning for other types, e.g. dog, bird etc.

This needs alot of work to be production-ready, non-exhaustive list below:

- Use a database instead of the S3 filesystem to track scan requests
- Refactor and share code as appropriate between api and worker
- Worker needs to respond to os signals, currently it does not
- Dead-letter queue
- Frontend design
- CICD - format, lint, testing, deployment etc.
- Further optimize worker image size

## Run

`docker compose up -d`

## Usage

### Web

<http://localhost:8080>

### API

submit: `curl -X POST http://localhost:8080/scan -F "file=@path/to/image.jpg"`

check: `curl http://localhost:8080/result/<image_id>`
