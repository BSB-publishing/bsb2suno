PY ?= python3
EXAMPLES = RUT:1 PSA:23 PSA:136 EXO:15 LUK:1

.PHONY: help setup test examples cast cuts clean-output clean-cache

help:
	@echo "make setup         install, download the pinned data and build the cast table (once)"
	@echo "make examples      rebuild examples/ ($(EXAMPLES))"
	@echo "make test          run the tests (they also check that examples/ is current)"
	@echo "make cast          rebuild the generated cast table (cache/cast/cast.csv, output/cast.csv)"
	@echo "make cuts          where chapters over 4000 characters can be cut (output/cut-points.txt)"
	@echo "$(PY) -m bsb2suno BOOK CHAPTER...   build any chapter(s) into output/; 'all' for a whole book"

setup:
	$(PY) -m pip install -e .
	$(PY) scripts/build_cast.py

examples:
	$(PY) -c "import shutil; shutil.rmtree('examples', ignore_errors=True)"
	@for bc in $(EXAMPLES); do $(PY) -m bsb2suno $${bc%%:*} $${bc##*:} --out examples --bare >/dev/null || exit 1; done
	@echo "examples/ rebuilt"

cast:
	$(PY) scripts/build_cast.py

cuts:
	@mkdir -p output
	$(PY) scripts/cut_points.py > output/cut-points.txt
	@head -5 output/cut-points.txt

test:
	$(PY) -m unittest discover -s tests -v

clean-output:
	$(PY) -c "import shutil; shutil.rmtree('output', ignore_errors=True)"

clean-cache:
	$(PY) -c "import shutil; shutil.rmtree('cache', ignore_errors=True)"
