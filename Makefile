
dist: docker-job.py
	@pyinstaller --onefile --specpath build/ docker-job.py

.PHONY: install
install: dist
	@cp dist/docker-job /usr/local/bin/

.PHONY: clean
clean:
	@rm -rf **/*.pyc
	@rm -rf **/__pycache__
	@rm -rf build
	@rm -rf dist

.PHONY: setup
setup:
	@pip install -q pipenv
	@pipenv install --dev
