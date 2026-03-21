.PHONY: lint test-role test-role-privileged test-role-qemu test-all-docker test-all-privileged test-all-qemu

lint:  ## Run yamllint and ansible-lint
	yamllint . && ansible-lint

test-role:  ## Test a single role (Docker). Usage: make test-role ROLE_PATH=monitoring/kuma-setup/roles/kuma
	@test -n "$(ROLE_PATH)" || (echo "Usage: make $@ ROLE_PATH=<path>"; exit 1)
	cd $(ROLE_PATH) && molecule test -s default

test-role-privileged:  ## Test a single role (privileged Docker). Usage: make test-role-privileged ROLE_PATH=security/secure-homelab-access/roles/firewall
	@test -n "$(ROLE_PATH)" || (echo "Usage: make $@ ROLE_PATH=<path>"; exit 1)
	cd $(ROLE_PATH) && molecule test -s privileged

test-role-qemu:  ## Test a single role (QEMU). Usage: make test-role-qemu ROLE_PATH=files/nas-setup/roles/mergerfs
	@test -n "$(ROLE_PATH)" || (echo "Usage: make $@ ROLE_PATH=<path>"; exit 1)
	cd $(ROLE_PATH) && molecule test -s qemu

test-all-docker:  ## Test all Docker-driver roles
	./scripts/test-all.sh docker

test-all-privileged:  ## Test all privileged Docker-driver roles
	./scripts/test-all.sh privileged

test-all-qemu:  ## Test all QEMU-driver roles
	./scripts/test-all.sh qemu
