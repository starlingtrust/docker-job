
.PHONY: init
init:
	@pip install -q pipenv
	@pipenv install --dev

.PHONY: freeze
freeze: dist/docker-job

.PHONY: install
install: freeze
	@cp dist/docker-job /usr/local/bin/

.PHONY: clean
clean:
	@rm -rf **/*.pyc **/__pycache__ build dist

dist/docker-job: docker-job.py
	@pyinstaller --onefile --specpath build/ docker-job.py
