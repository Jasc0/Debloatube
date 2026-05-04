SHELL := /bin/bash
DIR := $(shell pwd)
USER_SYSTEMD_DIR := $(HOME)/.config/systemd/user
SERVICE_NAME := debloatube.service

.PHONY: install uninstall venv

install: venv
	mkdir -p $(USER_SYSTEMD_DIR)
	sed 's|{DIR}|$(DIR)|g' $(SERVICE_NAME) > $(USER_SYSTEMD_DIR)/$(SERVICE_NAME)
	systemctl --user daemon-reload
	systemctl --user enable $(SERVICE_NAME)
	systemctl --user start $(SERVICE_NAME)

venv:
	python3 -m venv debloatube
	./debloatube/bin/pip install -r requirements.txt

uninstall:
	systemctl --user stop $(SERVICE_NAME) || true
	systemctl --user disable $(SERVICE_NAME) || true
	rm -f $(USER_SYSTEMD_DIR)/$(SERVICE_NAME)
	systemctl --user daemon-reload
