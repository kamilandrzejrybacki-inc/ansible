PLAYBOOK = ansible-playbook playbook.yml

.PHONY: deploy update rollback verify caddy admin lint

## Full initial deploy: container + Caddy vhost + admin files
deploy:
	$(PLAYBOOK) --tags deploy,caddy

## Re-pull image and recreate container (no Caddy changes)
update:
	$(PLAYBOOK) --tags update --limit lw-main

## Roll back container to previous image digest
rollback:
	$(PLAYBOOK) --tags rollback --limit lw-main

## Verify container health and Caddy reachability (no changes)
verify:
	$(PLAYBOOK) --tags verify --limit lw-main

## Re-render Caddy vhost only
caddy:
	$(PLAYBOOK) --tags caddy --limit lw-main

## Re-render admin files into blog repo only
admin:
	$(PLAYBOOK) --tags decap-admin --limit localhost

## Lint all role files
lint:
	ansible-lint playbook.yml
