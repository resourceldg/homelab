# Homelab operator interface. Run `make help` for the list.
.DEFAULT_GOAL := help
ANSIBLE_DIR   := ansible
PLAYBOOK      := $(ANSIBLE_DIR)/site.yml
RUN           := cd $(ANSIBLE_DIR) &&

.PHONY: help deps lint molecule vault-edit vault-create dry-run apply \
        harden firewall updates backups monitoring idempotence test verify

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

deps: ## Install Galaxy collections and Python dev/test deps
	ansible-galaxy collection install -r requirements.yml
	pip install -r tests/requirements.txt ansible-lint yamllint \
	  molecule "molecule-plugins[docker]" docker

lint: ## Static analysis (yamllint + ansible-lint)
	yamllint .
	ansible-lint

molecule: ## Run the Molecule scenario for the ddns role (Docker driver)
	cd $(ANSIBLE_DIR)/roles/ddns && molecule test

vault-create: ## Create the encrypted vault from the example
	cp $(ANSIBLE_DIR)/group_vars/all/vault.yml.example $(ANSIBLE_DIR)/group_vars/all/vault.yml
	ansible-vault encrypt $(ANSIBLE_DIR)/group_vars/all/vault.yml

vault-edit: ## Edit the encrypted vault
	$(RUN) ansible-vault edit group_vars/all/vault.yml

dry-run: ## Preview all changes without applying (--check --diff)
	$(RUN) ansible-playbook site.yml --check --diff

apply: ## Converge the whole server
	$(RUN) ansible-playbook site.yml

harden: ## Apply only the security plane
	$(RUN) ansible-playbook site.yml --tags security

firewall: ## Apply only the firewall role
	$(RUN) ansible-playbook site.yml --tags firewall

monitoring: ## Redeploy the monitoring + proxy stacks
	$(RUN) ansible-playbook site.yml --tags "services,docker"

backups: ## Configure backups and run one now
	$(RUN) ansible-playbook site.yml --tags backups
	sudo borgmatic --verbosity 1

idempotence: ## Prove no changes on a second run (exit 1 if drift)
	$(RUN) ansible-playbook site.yml | tee /tmp/run1.log
	$(RUN) ansible-playbook site.yml | tee /tmp/run2.log
	@grep -qE 'changed=0 .*failed=0' /tmp/run2.log && \
	  echo "✅ idempotent" || (echo "❌ second run made changes" && exit 1)

verify: ## Run the in-Ansible posture checks
	$(RUN) ansible-playbook ../tests/verify.yml

test: ## Run the testinfra smoke tests locally
	py.test -v --hosts=local:// tests/test_homelab.py
