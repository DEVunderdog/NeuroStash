run:
	docker compose -f docker/docker-compose.yaml up --detach

build:
	docker compose -f docker/docker-compose.yaml build

stop:
	docker compose -f docker/docker-compose.yaml down

logs:
	docker compose -f docker/docker-compose.yaml logs -f $(SERVICE)
