.PHONY: recreate

recreate:
	docker compose stop bot
	docker compose rm -f bot
	docker compose up -d --force-recreate bot

