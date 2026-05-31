PYTHON ?= python
DBT ?= dbt
DBT_FLAGS := --project-dir dbt --profiles-dir dbt

.PHONY: help install gen deps build test report docs up clean

help:
	@echo "Strata"
	@echo "  make install   install the package + deps (dbt-duckdb, polars, ...)"
	@echo "  make gen       generate the synthetic raw parquet layer"
	@echo "  make deps      install dbt packages (dbt_utils)"
	@echo "  make build     run + test the whole bronze->silver->gold pipeline"
	@echo "  make test      run tests only"
	@echo "  make report    print the reconciliation + data-quality reports"
	@echo "  make docs      generate the dbt docs / lineage site"
	@echo "  make up        gen + deps + build + report (one command, from clean)"
	@echo "  make clean     remove generated data + dbt artifacts"

install:
	$(PYTHON) -m pip install -e .

gen:
	$(PYTHON) -m generate

deps:
	$(DBT) deps $(DBT_FLAGS)

build:
	$(DBT) build $(DBT_FLAGS)

test:
	$(DBT) test $(DBT_FLAGS)

report:
	$(PYTHON) scripts/show_reports.py

docs:
	$(DBT) docs generate $(DBT_FLAGS)

up: gen deps build report

clean:
	rm -rf data/raw data/strata.duckdb data/strata.duckdb.wal dbt/target dbt/dbt_packages dbt/logs logs
