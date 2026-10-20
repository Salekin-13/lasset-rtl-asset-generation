# data/

The RTL and the reference lists of the 41 NEORV32 modules that LAsset's manual asset sheet covers, in LAsset's own copy
of NEORV32. The split and every module's file, entry count and sha are in `LASSET_41_MODULES.csv`.

| folder | holds |
|---|---|
| `RTL_data/` | the 15 tuning modules, plus three files with no reference entry that served as negative controls (`neorv32_boot_rom`, `neorv32_fifo`) and the package (`neorv32_package`) |
| `RTL_heldout/` | the 26 held-out modules |
| `ground_truth/` | LAsset's manual asset list (`manual_gt_neorv32.json`) and its initial and refined lists in scorer form |
| `LAsset_initial_results/` | LAsset's published initial asset lists (spec+RTL and RTL-only) |
| `parsed_tuning18/`, `parsed_heldout26/`, `parsed_heldout_raw/` | the closed sets: every port and signal of each module, extracted by regex |

Tuning (15): bus, cache, cpu, cpu_cp_cfu, cpu_cp_muldiv, cpu_pmp, debug_dtm, hwspinlock, imem, spi, sys, trng, twi,
uart, wdt. Held-out (26): cpu_alu, cpu_control, cpu_counters, cpu_cp_bitmanip, cpu_cp_cond, cpu_cp_crypto, cpu_cp_fpu,
cpu_cp_shifter, cpu_decompressor, cpu_frontend, cpu_icc, cpu_lsu, cpu_regfile, debug_auth, debug_dm, dmem, gpio, gptmr,
neoled, onewire, pwm, sdi, slink, sysinfo, twd, xbus. All names carry the `neorv32_` prefix.

The two RTL folders are kept apart because the pre-registrations of September and October pin files under these
names (`assetgen_meta/HELDOUT_PREREG.md`, `assetgen_meta/lasset_layer/PREREG.md`). The NEORV32 license is in
`third_party/`.
