$(info machine: $(shell uname -m))

PROJECT_NAME := $(shell basename `pwd`)
MICROBIT_BIN = ./build/bbc-microbit-classic-gcc/src/firmware/bluescan-advsniff-combined.hex
MICROBIT_PATH = /media/${USER}/MICROBIT
NETHUNTER_ROOT = /data/local/nhsystem/kali-arm64

TWINE_PROXY := HTTPS_PROXY=http://localhost:7890


.PHONY: build
build:
	@python3.10 -m pip install -U xpycommon pyclui bthci btsmp btatt btgatt
	@python3.10 -m build --no-isolation


.PHONY: flash
flash:
	@yotta build bluescan-advsniff

	@if [ -d $(MICROBIT_PATH) ]; then \
		cp $(MICROBIT_BIN) $(MICROBIT_PATH); \
	fi
	
	@if [ -d $(MICROBIT_PATH)1 ]; then \
		cp $(MICROBIT_BIN) $(MICROBIT_PATH)1; \
	fi
	
	@if [ -d $(MICROBIT_PATH)2 ]; then \
		cp $(MICROBIT_BIN) $(MICROBIT_PATH)2; \
	fi


.PHONY: clean
clean:
	-@rm -r dist/* src/$(PROJECT_NAME)/__pycache__ src/*.egg-info
	-@yotta clean


.PHONY: microbit-purge
microbit-purge:
	-@yotta clean
	-@rm -r yotta_modules
	-@rm -r yotta_targets


.PHONY: release
release:
	$(TWINE_PROXY) twine upload dist/*.whl dist/*.tar.gz


.PHONY: push
push:
	@adb push dist/*.whl /sdcard/Download/
	@adb shell su -c mv /sdcard/Download/*.whl $(NETHUNTER_ROOT)/root/Desktop/temp
	@scp dist/*.whl Raspberry-Pi-4-via-Local-Ethernet:~/Desktop/temp
