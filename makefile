.PHONY: recreate

recreate:
	docker compose stop bot
	docker compose rm -f bot
	docker compose up -d --force-recreate bot

.PHONY: list-imports

list-imports:
	docker compose run --rm bot python -m tgtwin.ingestion list data/imports/result.json --names --limit 40
