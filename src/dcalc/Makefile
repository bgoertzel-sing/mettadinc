# Builds the dcalc CLI and the core library (no CeTTa needed).
CC ?= gcc
# make predefines AR=ar; fall back to gcc-ar when plain ar is not on PATH.
AR := $(if $(shell command -v ar),ar,gcc-ar)
CFLAGS ?= -std=c11 -Wall -Wextra -O2
BUILD ?= ../../build/dcalc
OBJS = rat.o graded.o ops_graded.o ops_refine.o ops_weakest.o ops_approx.o ops_kernels.o sexp.o sha256.o registry_gen.o registry.o admit.o binding.o api.o model.o ops_core.o obligations.o ops_req.o ops_induce.o ops_abs.o ops_dispatch.o records.o bdd.o ops_sym.o
all: $(BUILD)/dcalc $(BUILD)/libdcalc.a
$(BUILD)/%.o: %.c $(wildcard *.h)
	@mkdir -p $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@
$(BUILD)/libdcalc.a: $(addprefix $(BUILD)/,$(OBJS))
	$(AR) rcs $@ $^
$(BUILD)/dcalc: $(BUILD)/main.o $(BUILD)/libdcalc.a
	$(CC) $(CFLAGS) -o $@ $^
# M3 incrementality test (spec Lemma 4.17, Table 7); run by run_m3_gates.py neg 10-11.
$(BUILD)/m3_incremental: ../../tests/dcalc/m3_incremental.c $(BUILD)/libdcalc.a $(wildcard *.h) ops_sym.c
	$(CC) $(CFLAGS) -I. -o $@ $< $(BUILD)/libdcalc.a -lm
tests: $(BUILD)/m3_incremental
clean:
	rm -rf $(BUILD)
.PHONY: all clean tests
