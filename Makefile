LIBDIR := $(shell uv run python -c "import sysconfig; print(sysconfig.get_config_var('LIBDIR'))")

.PHONY: test
test:
	DYLD_LIBRARY_PATH=$(LIBDIR) LD_LIBRARY_PATH=$(LIBDIR) cargo test $(ARGS)
