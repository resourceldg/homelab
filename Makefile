# Homelab operator interface. Run `make help` for the list.
.DEFAULT_GOAL := help
ANSIBLE_DIR   := ansible
PLAYBOOK      := $(ANSIBLE_DIR)/site.yml
RUN           := cd $(ANSIBLE_DIR) &&

# Target environment. Override on the CLI: `make apply ENV=staging`.
ENV       ?= production
INV       := inventories/$(ENV)
VAULT     := $(INV)/group_vars/all/vault.yml
PLAY      := ansible-playbook site.yml -i $(INV)

VENV := $(CURDIR)/.venv
export PATH := $(VENV)/bin:$(PATH)

.PHONY: help deps lint molecule vault-edit vault-create dry-run apply \
        harden firewall updates backups monitoring panol idempotence test verify \
        logs-on logs-off logs-estado \
        precommit secrets

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

$(VENV)/bin/pip:
	python3 -m venv $(VENV)

deps: $(VENV)/bin/pip ## Install Ansible core, Galaxy collections and Python dev/test deps
	# ansible-core from pip (Ubuntu 24.04 apt version lags; pip gives us
	# deb822_repository / docker_compose_v2).
	pip install -r tests/requirements.txt ansible-core ansible-lint yamllint \
	  molecule "molecule-plugins[docker]" docker pre-commit
	ansible-galaxy collection install -r requirements.yml

lint: ## Static analysis (yamllint + ansible-lint)
	yamllint .
	ansible-lint

precommit: ## Run every pre-commit hook against all files
	pre-commit run --all-files

secrets: ## Scan the repo for leaked secrets (gitleaks)
	pre-commit run gitleaks --all-files

molecule: ## Run Molecule for ddns + backups roles (set UBUNTU_IMAGE_TAG=2204|2404)
	cd $(ANSIBLE_DIR)/roles/ddns && molecule test
	cd $(ANSIBLE_DIR)/roles/backups && molecule test

vault-create: ## Create the encrypted vault for $(ENV) from the example
	cp $(ANSIBLE_DIR)/$(VAULT).example $(ANSIBLE_DIR)/$(VAULT)
	ansible-vault encrypt $(ANSIBLE_DIR)/$(VAULT)

vault-edit: ## Edit the encrypted vault for $(ENV)
	$(RUN) ansible-vault edit $(VAULT)

dry-run: ## Preview all changes without applying (--check --diff)
	$(RUN) $(PLAY) --check --diff

apply: ## Converge the whole server ($(ENV))
	$(RUN) $(PLAY)

harden: ## Apply only the security plane
	$(RUN) $(PLAY) --tags security

firewall: ## Apply only the firewall role
	$(RUN) $(PLAY) --tags firewall

monitoring: ## Redeploy the monitoring + proxy stacks
	$(RUN) $(PLAY) --tags "services,docker"

logs-on: ## Prender los logs en vivo (pregunta cada 5 min; se apagan solos)
	ssh -t ansible@homelab-01 logs-en-vivo

logs-off: ## Apagar los logs en vivo
	ssh ansible@homelab-01 logs-en-vivo --off

logs-estado: ## ¿Están prendidos los logs en vivo?
	ssh ansible@homelab-01 logs-en-vivo --estado

panol: ## Redeploy the Pañol IoT plane (broker MQTT + auditoría + Node-RED)
	$(RUN) $(PLAY) --tags panol

backups: ## Configure backups and run one now
	$(RUN) $(PLAY) --tags backups
	sudo borgmatic --verbosity 1

idempotence: ## Prove no changes on a second run (exit 1 if drift)
	$(RUN) $(PLAY) | tee /tmp/run1.log
	$(RUN) $(PLAY) | tee /tmp/run2.log
	@grep -qE 'changed=0 .*failed=0' /tmp/run2.log && \
	  echo "✅ idempotent" || (echo "❌ second run made changes" && exit 1)

verify: ## Run the in-Ansible posture checks
	$(RUN) ansible-playbook ../tests/verify.yml

test: ## Run the testinfra smoke tests locally
	py.test -v --hosts=local:// --sudo tests/test_homelab.py
