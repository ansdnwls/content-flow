PYTHON ?= python
PIP ?= $(PYTHON) -m pip
NPM ?= npm
GO ?= go
DOCKER ?= docker
DOCKER_COMPOSE ?= docker compose
VERSION ?=

.PHONY: lint test build release docker-up docker-down sdk-python sdk-js sdk-go

lint:
	ruff check .

test:
	pytest -q
	cd sdk/python && $(PYTHON) -m pytest -q
	cd sdk/javascript && $(NPM) test
	cd sdk/go && $(GO) test ./...

build: sdk-python sdk-js sdk-go
	cd landing && $(NPM) run build
	$(DOCKER) build -t contentflow-api:local .

release: lint test build
	@test -n "$(VERSION)" || (echo "VERSION is required, e.g. make release VERSION=0.2.0" && exit 1)
	git tag "v$(VERSION)"
	git push origin "v$(VERSION)"

docker-up:
	$(DOCKER_COMPOSE) up --build -d

docker-down:
	$(DOCKER_COMPOSE) down

sdk-python:
	cd sdk/python && $(PYTHON) -m build

sdk-js:
	cd sdk/javascript && $(NPM) run build

sdk-go:
	cd sdk/go && $(GO) test ./...
