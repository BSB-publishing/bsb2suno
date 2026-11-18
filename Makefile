PY ?= python3

.PHONY: help test examples cast clean-output clean-cache

help:
	@echo "make examples      build RUT 1, PSA 23, PSA 136, EXO 15, LUK 1 into output/"
	@echo "make test          run the tests (downloads into cache/ on first run)"
	@echo "make cast          rebuild config/cast.csv from the data (keeps manual rows)"
	@echo "$(PY) -m bsb2suno BOOK CHAPTER...   build any chapter(s); 'all' for a whole book"

examples:
	$(PY) -m bsb2suno RUT 1
	$(PY) -m bsb2suno PSA 23 136
	$(PY) -m bsb2suno EXO 15
	$(PY) -m bsb2suno LUK 1

cast:
	$(PY) scripts/build_cast.py

test:
	$(PY) -m unittest discover -s tests -v

clean-output:
	rm -rf output

clean-cache:
	rm -rf cache
