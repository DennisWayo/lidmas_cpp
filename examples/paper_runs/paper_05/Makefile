SHELL := /bin/bash
.EXPORT_ALL_VARIABLES:

.PHONY: \
	repetition-local repetition-submit repetition-status repetition-finalize \
	css-local css-submit css-status css-finalize \
	surface-local surface-submit surface-status surface-finalize \
	gkp supplemental

repetition-local:
	./01_build_syndrome_circuits.sh
	./02_run_local_simulation.sh

repetition-submit:
	./03_submit_ibm_runtime.sh

repetition-status:
	LIDMAS_P5_IBM_STATUS_ONLY=1 ./03_fetch_ibm_runtime_results.sh

repetition-finalize:
	./03_fetch_ibm_runtime_results.sh
	./04_ingest_results.sh
	./05_decode_live_syndromes.sh
	./06_analyze_and_plot.sh

css-local:
	./11_build_qldpc_syndrome_circuits.sh
	./12_run_qldpc_local_simulation.sh

css-submit:
	./13_submit_qldpc_ibm_runtime.sh

css-status:
	LIDMAS_P5_QLDPC_IBM_STATUS_ONLY=1 ./13_fetch_qldpc_ibm_runtime_results.sh

css-finalize:
	./13_fetch_qldpc_ibm_runtime_results.sh
	./14_ingest_qldpc_results.sh
	./15_decode_qldpc_syndromes.sh
	./16_analyze_qldpc.sh

surface-local:
	./21_build_surface_syndrome_circuits.sh
	./22_run_surface_local_simulation.sh

surface-submit:
	./23_submit_surface_ibm_runtime.sh

surface-status:
	LIDMAS_P5_SURFACE_IBM_STATUS_ONLY=1 ./23_fetch_surface_ibm_runtime_results.sh

surface-finalize:
	./23_fetch_surface_ibm_runtime_results.sh
	./24_ingest_surface_results.sh
	./25_decode_surface_syndromes.sh
	./26_analyze_surface.sh

gkp:
	./31_build_gkp_digitized_model.sh
	./32_run_gkp_digitized_sampler.sh
	./33_ingest_gkp_results.sh
	./34_decode_gkp_syndromes.sh
	./35_analyze_gkp.sh
	./36_render_gkp_figures.sh

supplemental:
	./37_render_supplemental_figures.sh
