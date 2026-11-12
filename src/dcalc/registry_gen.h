/* The adopted registry, compiled in (see tools/gen_registry.py). */
#ifndef DCALC_REGISTRY_GEN_H
#define DCALC_REGISTRY_GEN_H
/* sha256 of registry/mettadinc_registry.json, lowercase hex. */
extern const char dc_registry_digest[];
/* The registry as s-expression text, in NULL-terminated pieces. */
extern const char *const dc_registry_parts[];
/* The beyond-release registry (release registry plus local patches), selected by --beyond-release. */
extern const char dc_registry_beyond_digest[];
extern const char *const dc_registry_beyond_parts[];
#endif
