# Catalogue des métriques

Généré depuis les `/metrics` réels (`tests/gen_metrics_catalog.py`, API metadata de Prometheus). Les noms changent d'une version à l'autre : toujours relire ce fichier avant d'écrire une requête.

| Métrique | Type | Signification | Levier d'optimisation |
|---|---|---|---|
| `DCGM_FI_DEV_CLOCK_THROTTLE_REASONS` | gauge | Raisons de throttling (bitmask). | bridage puissance/thermique |
| `DCGM_FI_DEV_ECC_DBE_VOL_TOTAL` | counter | Erreurs ECC doubles. |  |
| `DCGM_FI_DEV_ECC_SBE_VOL_TOTAL` | counter | Erreurs ECC simples. |  |
| `DCGM_FI_DEV_FB_FREE` | gauge | Mémoire GPU libre (MiB). |  |
| `DCGM_FI_DEV_FB_USED` | gauge | Mémoire GPU utilisée (MiB). | poids + cache KV |
| `DCGM_FI_DEV_GPU_TEMP` | gauge | Température (C). |  |
| `DCGM_FI_DEV_GPU_UTIL` | gauge | Utilisation GPU (%). | utilisation apparente (pas la saturation) |
| `DCGM_FI_DEV_MEM_CLOCK` | gauge | Fréquence mémoire (MHz). |  |
| `DCGM_FI_DEV_MEM_COPY_UTIL` | gauge | Utilisation du bus mémoire (%). |  |
| `DCGM_FI_DEV_PCIE_REPLAY_COUNTER` | counter | Rejeux PCIe. |  |
| `DCGM_FI_DEV_POWER_USAGE` | gauge | Puissance (W). | plafond de puissance du T4 (70 W) |
| `DCGM_FI_DEV_SM_CLOCK` | gauge | Fréquence SM (MHz). |  |
| `DCGM_FI_DEV_TOTAL_ENERGY_CONSUMPTION` | counter | Énergie cumulée (mJ). | tokens par joule |
| `DCGM_FI_PROF_DRAM_ACTIVE` | gauge | Activité de la mémoire (ratio). | limite de bande passante mémoire (decode) |
| `DCGM_FI_PROF_GR_ENGINE_ACTIVE` | gauge | Activité du moteur graphique (ratio). | activité réelle du moteur |
| `DCGM_FI_PROF_PCIE_RX_BYTES` | counter | Octets PCIe reçus. |  |
| `DCGM_FI_PROF_PCIE_TX_BYTES` | counter | Octets PCIe émis. |  |
| `argocd_app_info` | gauge | Information about application. |  |
| `inference_extension_info` | gauge | [ALPHA] General information of the current build of Inference Extension. |  |
| `inference_extension_plugin_duration_seconds` | histogram | [ALPHA] [Deprecated: Use llm_d_epp_plugin_duration_seconds] Plugin processing latency distribution in seconds for each extension point, plug |  |
| `inference_extension_scheduler_attempts_total` | counter | [ALPHA] [Deprecated: Use llm_d_epp_scheduler_attempts_total] Total number of scheduling attempts. |  |
| `inference_extension_scheduler_e2e_duration_seconds` | histogram | [ALPHA] [Deprecated: Use llm_d_epp_scheduler_e2e_duration_seconds] End-to-end scheduling latency distribution in seconds. |  |
| `inference_objective_input_tokens` | histogram | [ALPHA] [Deprecated: Use llm_d_epp_request_input_tokens] Inference objective input token count distribution for requests in each model. |  |
| `inference_objective_normalized_time_per_output_token_seconds` | histogram | [ALPHA] [Deprecated: Use llm_d_epp_request_ntpot_seconds] Inference objective latency divided by number of output tokens in seconds for each |  |
| `inference_objective_output_tokens` | histogram | [ALPHA] [Deprecated: Use llm_d_epp_request_output_tokens] Inference objective output token count distribution for requests in each model. |  |
| `inference_objective_request_duration_seconds` | histogram | [ALPHA] [Deprecated: Use llm_d_epp_request_duration_seconds] Inference objective response latency distribution in seconds for each model and |  |
| `inference_objective_request_sizes` | histogram | [ALPHA] [Deprecated: Use llm_d_epp_request_size_bytes] Inference objective requests size distribution in bytes for each model and target mod |  |
| `inference_objective_request_total` | counter | [ALPHA] [Deprecated: Use llm_d_epp_request_total] Counter of inference objective requests broken out for each model and target model. |  |
| `inference_objective_response_sizes` | histogram | [ALPHA] [Deprecated: Use llm_d_epp_response_size_bytes] Inference objective responses size distribution in bytes for each model and target m |  |
| `inference_objective_running_requests` | gauge | [ALPHA] [Deprecated: Use llm_d_epp_request_running] Inference objective number of running requests in each model. |  |
| `istio_request_duration_milliseconds` | histogram |  |  |
| `istio_requests_total` | counter |  |  |
| `keda_build_info` | gauge | Info metric, with static information about KEDA build like: version, git commit and Golang runtime info. |  |
| `keda_internal_metricsservice_grpc_client_handled_total` | counter | Total number of RPCs completed by the client, regardless of success or failure. |  |
| `keda_internal_metricsservice_grpc_client_handling_seconds` | histogram | Histogram of response latency (seconds) of the gRPC until it is finished by the application. |  |
| `keda_internal_metricsservice_grpc_client_msg_received_total` | counter | Total number of RPC stream messages received by the client. |  |
| `keda_internal_metricsservice_grpc_client_msg_sent_total` | counter | Total number of gRPC stream messages sent by the client. |  |
| `keda_internal_metricsservice_grpc_client_started_total` | counter | Total number of RPCs started on the client. |  |
| `keda_internal_metricsservice_grpc_server_handled_total` | counter | Total number of RPCs completed on the server, regardless of success or failure. |  |
| `keda_internal_metricsservice_grpc_server_handling_seconds` | histogram | Histogram of response latency (seconds) of gRPC that had been application-level handled by the server. |  |
| `keda_internal_metricsservice_grpc_server_msg_received_total` | counter | Total number of RPC stream messages received on the server. |  |
| `keda_internal_metricsservice_grpc_server_msg_sent_total` | counter | Total number of gRPC stream messages sent by the server. |  |
| `keda_internal_metricsservice_grpc_server_started_total` | counter | Total number of RPCs started on the server. |  |
| `keda_internal_scale_loop_latency_seconds` | gauge | Total deviation (in seconds) between the expected execution time and the actual execution time for the scaling loop. |  |
| `keda_resource_registered_total` | gauge | Total number of KEDA custom resources per namespace for each custom resource type (CRD) registered. |  |
| `keda_scaled_object_errors_total` | counter | The number of errors that have occurred for each ScaledObject. |  |
| `keda_scaled_object_paused` | gauge | Indicates whether a ScaledObject is paused (1), or not (0). |  |
| `keda_scaler_active` | gauge | Indicates whether a scaler is active (1), or not (0). |  |
| `keda_scaler_detail_errors_total` | counter | The total number of errors encountered for each scaler. |  |
| `keda_scaler_empty_upstream_responses_total` | counter | Number of times a query returns an empty result |  |
| `keda_scaler_http_request_duration_seconds` | histogram | Duration in seconds of outbound HTTP requests issued during scaler metric collection. |  |
| `keda_scaler_http_requests_total` | counter | Total number of outbound HTTP requests issued during scaler metric collection. |  |
| `keda_scaler_metrics_latency_seconds` | gauge | The latency of retrieving current metric from each scaler, in seconds. |  |
| `keda_scaler_metrics_value` | gauge | The current value for each scaler's metric that would be used by the HPA in computing the target average. | valeur du trigger d'autoscaling |
| `keda_trigger_registered_total` | gauge | Total number of triggers per trigger type registered. |  |
| `litellm_active_users` | gauge | Number of billable users in LiteLLM (excludes SCIM-deactivated users) |  |
| `litellm_cache_misses_metric` | counter | Total number of LiteLLM cache misses |  |
| `litellm_check_batch_cost_jobs_polled` | gauge | Number of unprocessed batches found by the last CheckBatchCost poll |  |
| `litellm_check_batch_cost_last_run_timestamp` | gauge | Unix timestamp of the last CheckBatchCost job run |  |
| `litellm_deployment_failure_responses` | counter | LLM Deployment Analytics - Total number of failed LLM API calls for a specific LLM deploymeny. exception_status is the status of the excepti |  |
| `litellm_deployment_latency_per_output_token` | histogram | LLM Deployment Analytics - Latency per output token |  |
| `litellm_deployment_state` | gauge | LLM Deployment Analytics - The state of the deployment: 0 = healthy, 1 = partial outage, 2 = complete outage |  |
| `litellm_deployment_success_responses` | counter | LLM Deployment Analytics - Total number of successful LLM API calls via litellm |  |
| `litellm_deployment_total_requests` | counter | LLM Deployment Analytics - Total number of LLM API calls via litellm - success + failure |  |
| `litellm_in_flight_requests` | gauge | Number of HTTP requests currently in-flight on this uvicorn worker |  |
| `litellm_input_tokens_metric` | counter | Total number of input tokens from LLM requests |  |
| `litellm_llm_api_failed_requests_metric` | counter | deprecated - use litellm_proxy_failed_requests_metric |  |
| `litellm_llm_api_latency_metric` | histogram | Total latency (seconds) for a models LLM API call |  |
| `litellm_llm_api_time_to_first_token_metric` | histogram | Time to first token for a models LLM API call |  |
| `litellm_output_tokens_metric` | counter | Total number of output tokens from LLM requests |  |
| `litellm_proxy_failed_requests_metric` | counter | Total number of failed responses from proxy - the client did not get a success response from litellm proxy |  |
| `litellm_proxy_total_requests_metric` | counter | Total number of requests made to the proxy server - track number of client side requests |  |
| `litellm_remaining_api_key_budget_metric` | gauge | Remaining budget for api key |  |
| `litellm_remaining_api_key_requests_for_model` | gauge | Remaining Requests API Key can make for model (model based rpm limit on key) |  |
| `litellm_remaining_api_key_tokens_for_model` | gauge | Remaining Tokens API Key can make for model (model based tpm limit on key) |  |
| `litellm_remaining_team_budget_metric` | gauge | Remaining budget for team |  |
| `litellm_request_queue_time_seconds` | histogram | Time (seconds) from request arrival at the proxy to the start of pre-call processing -- includes authentication and any ASGI-level queueing |  |
| `litellm_request_total_latency_metric` | histogram | End-to-end latency (seconds) for a request to LiteLLM Proxy Server, from the moment the request reached the proxy through the end of process |  |
| `litellm_requests_metric` | counter | deprecated - use litellm_proxy_total_requests_metric. Total number of LLM calls to litellm - track total per API Key, team, user |  |
| `litellm_spend_capture_rate` | gauge | Share of the provider's bill LiteLLM captured as spend over the scheduled check's window (captured spend / provider bill), by api_provider;  |  |
| `litellm_spend_metric` | counter | Total spend on LLM requests |  |
| `litellm_teams_count` | gauge | Total number of teams in LiteLLM |  |
| `litellm_total_tokens_metric` | counter | Total number of input + output tokens from LLM requests |  |
| `litellm_total_users` | gauge | Total number of users in LiteLLM |  |
| `llm_d_epp_average_kv_cache_utilization` | gauge | [ALPHA] The average kv cache utilization for an inference server pool. |  |
| `llm_d_epp_average_queue_size` | gauge | [ALPHA] The average number of requests pending in the model server queue. |  |
| `llm_d_epp_average_running_requests` | gauge | [ALPHA] The average number of running requests across model servers in the pool. |  |
| `llm_d_epp_inflight_requests` | gauge | [ALPHA] Current number of in-flight requests per endpoint, as tracked by the in-flight load producer. |  |
| `llm_d_epp_inflight_tokens` | gauge | [ALPHA] Current number of in-flight tokens per endpoint (uncached prompt tokens, optionally plus estimated output), as tracked by the in-fli |  |
| `llm_d_epp_info` | gauge | [ALPHA] General information of the current build of Inference Extension. |  |
| `llm_d_epp_per_endpoint_queue_size` | gauge | [ALPHA] The total number of requests pending in the model server queue for each underlying endpoint. |  |
| `llm_d_epp_plugin_duration_seconds` | histogram | [ALPHA] Plugin processing latency distribution in seconds for each extension point, plugin type and plugin name. |  |
| `llm_d_epp_ready_endpoints` | gauge | [ALPHA] The number of ready endpoints in the inference server pool. |  |
| `llm_d_epp_request_duration_seconds` | histogram | [ALPHA] End-to-end request latency distribution in seconds. |  |
| `llm_d_epp_request_input_tokens` | histogram | [ALPHA] Input token count distribution per request. |  |
| `llm_d_epp_request_ntpot_seconds` | histogram | [ALPHA] Normalized time per output token in seconds (end-to-end latency divided by output token count). |  |
| `llm_d_epp_request_output_tokens` | histogram | [ALPHA] Output token count distribution per request. |  |
| `llm_d_epp_request_processing_duration_seconds` | histogram | [ALPHA] EPP request processing latency distribution in seconds, from request receipt until the request body has been handled, including admi |  |
| `llm_d_epp_request_running` | gauge | [ALPHA] Current number of active running requests. |  |
| `llm_d_epp_request_size_bytes` | histogram | [ALPHA] Incoming request body size distribution in bytes. |  |
| `llm_d_epp_request_streaming_itl_seconds` | histogram | [ALPHA] Inter-token latency in seconds for streaming requests, measured as the time between consecutive response body chunks. |  |
| `llm_d_epp_request_streaming_tpot_seconds` | histogram | [ALPHA] Average time per output token in seconds for streaming requests, computed as (e2e - TTFT) / (output_tokens - 1). |  |
| `llm_d_epp_request_total` | counter | [ALPHA] Total number of processed requests. |  |
| `llm_d_epp_request_ttft_seconds` | histogram | [ALPHA] Time to first token in seconds, measured from request received to first response byte. For non-streaming requests, this equals total |  |
| `llm_d_epp_response_processing_duration_seconds` | histogram | [ALPHA] EPP response processing latency distribution in seconds: the sum of per-chunk handler time for a streamed response, or the interval  |  |
| `llm_d_epp_response_size_bytes` | histogram | [ALPHA] Outgoing response body size distribution in bytes. |  |
| `llm_d_epp_scheduler_attempts_total` | counter | [ALPHA] Total number of scheduling attempts. |  |
| `llm_d_epp_scheduler_e2e_duration_seconds` | histogram | [ALPHA] End-to-end scheduling latency distribution in seconds. |  |
| `llm_d_epp_std_dev_kv_cache_utilization` | gauge | [ALPHA] The standard deviation kv cache utilization for an inference server pool. |  |
| `llm_d_epp_std_dev_queue_size` | gauge | [ALPHA] The standard deviation number of requests pending in the model server queue. |  |
| `llm_d_epp_std_dev_running_requests` | gauge | [ALPHA] The standard deviation number of running requests across model servers in the pool. |  |
| `vllm:admission_rejections_created` | gauge | Number of admission attempts rejected by a queue limit, by reason. |  |
| `vllm:admission_rejections_total` | counter | Number of admission attempts rejected by a queue limit, by reason. |  |
| `vllm:cache_config_info` | gauge | Information of the LLMEngine CacheConfig |  |
| `vllm:e2e_request_latency_seconds` | histogram | Histogram of e2e request latency in seconds. | durée totale : longueur de génération, file, réplicas |
| `vllm:e2e_request_latency_seconds_created` | gauge | Histogram of e2e request latency in seconds. |  |
| `vllm:engine_sleep_state` | gauge | Engine sleep state; awake = 0 means engine is sleeping; awake = 1 means engine is awake; weights_offloaded = 1 means sleep level 1; discard_ |  |
| `vllm:estimated_flops_per_gpu_created` | gauge | Estimated number of floating point operations per GPU (for Model Flops Utilization calculations). |  |
| `vllm:estimated_flops_per_gpu_total` | counter | Estimated number of floating point operations per GPU (for Model Flops Utilization calculations). |  |
| `vllm:estimated_read_bytes_per_gpu_created` | gauge | Estimated number of bytes read from memory per GPU (for Model Flops Utilization calculations). |  |
| `vllm:estimated_read_bytes_per_gpu_total` | counter | Estimated number of bytes read from memory per GPU (for Model Flops Utilization calculations). |  |
| `vllm:estimated_write_bytes_per_gpu_created` | gauge | Estimated number of bytes written to memory per GPU (for Model Flops Utilization calculations). |  |
| `vllm:estimated_write_bytes_per_gpu_total` | counter | Estimated number of bytes written to memory per GPU (for Model Flops Utilization calculations). |  |
| `vllm:external_prefix_cache_hits_created` | gauge | External prefix cache hits from KV connector cross-instance cache sharing, in terms of number of cached tokens. |  |
| `vllm:external_prefix_cache_hits_total` | counter | External prefix cache hits from KV connector cross-instance cache sharing, in terms of number of cached tokens. |  |
| `vllm:external_prefix_cache_queries_created` | gauge | External prefix cache queries from KV connector cross-instance cache sharing, in terms of number of queried tokens. |  |
| `vllm:external_prefix_cache_queries_total` | counter | External prefix cache queries from KV connector cross-instance cache sharing, in terms of number of queried tokens. |  |
| `vllm:generation_tokens_created` | gauge | Number of generation tokens processed. |  |
| `vllm:generation_tokens_total` | counter | Number of generation tokens processed. | débit de decode |
| `vllm:inter_token_latency_seconds` | histogram | Histogram of inter-token latency in seconds. | decode : max-num-seqs, quantization, bande passante mémoire |
| `vllm:inter_token_latency_seconds_created` | gauge | Histogram of inter-token latency in seconds. |  |
| `vllm:iteration_tokens_total` | histogram | Histogram of number of tokens per engine_step. |  |
| `vllm:iteration_tokens_total_created` | gauge | Histogram of number of tokens per engine_step. |  |
| `vllm:kv_cache_usage_perc` | gauge | KV-cache usage. 1 means 100 percent usage. | max-model-len, gpu-memory-utilization, quantization |
| `vllm:mm_cache_hits_created` | gauge | Multi-modal cache hits, in terms of number of cached items. |  |
| `vllm:mm_cache_hits_total` | counter | Multi-modal cache hits, in terms of number of cached items. |  |
| `vllm:mm_cache_queries_created` | gauge | Multi-modal cache queries, in terms of number of queried items. |  |
| `vllm:mm_cache_queries_total` | counter | Multi-modal cache queries, in terms of number of queried items. |  |
| `vllm:num_preemptions_created` | gauge | Cumulative number of preemption from the engine. |  |
| `vllm:num_preemptions_total` | counter | Cumulative number of preemption from the engine. | mémoire KV insuffisante |
| `vllm:num_requests_running` | gauge | Number of requests in model execution batches. | taille du batch courant : max-num-seqs |
| `vllm:num_requests_waiting` | gauge | Number of requests waiting to be processed. | signal KEDA ; capacité |
| `vllm:num_requests_waiting_by_reason` | gauge | Number of waiting requests by reason. Reason labels: 'capacity' = waiting for scheduling capacity; 'deferred' = deferred by transient constr |  |
| `vllm:prefix_cache_hits_created` | gauge | Prefix cache hits, in terms of number of cached tokens. |  |
| `vllm:prefix_cache_hits_total` | counter | Prefix cache hits, in terms of number of cached tokens. | poids des scorers EPP, prompts à préfixe commun |
| `vllm:prefix_cache_queries_created` | gauge | Prefix cache queries, in terms of number of queried tokens. |  |
| `vllm:prefix_cache_queries_total` | counter | Prefix cache queries, in terms of number of queried tokens. | idem (dénominateur du taux de hit) |
| `vllm:prompt_tokens_by_source_created` | gauge | Number of prompt tokens by source. |  |
| `vllm:prompt_tokens_by_source_total` | counter | Number of prompt tokens by source. |  |
| `vllm:prompt_tokens_cached_by_source_created` | gauge | Prefix-cache hit tokens by the cache tier that supplied them: device (local HBM), host (offloaded to DRAM), disk, p2p (transferred from anot |  |
| `vllm:prompt_tokens_cached_by_source_total` | counter | Prefix-cache hit tokens by the cache tier that supplied them: device (local HBM), host (offloaded to DRAM), disk, p2p (transferred from anot |  |
| `vllm:prompt_tokens_cached_created` | gauge | Number of cached prompt tokens (local + external). |  |
| `vllm:prompt_tokens_cached_total` | counter | Number of cached prompt tokens (local + external). |  |
| `vllm:prompt_tokens_created` | gauge | Number of prefill tokens processed. |  |
| `vllm:prompt_tokens_total` | counter | Number of prefill tokens processed. | charge de prefill |
| `vllm:request_decode_time_seconds` | histogram | Histogram of time spent in DECODE phase for request. | decode : taille du batch, quantization |
| `vllm:request_decode_time_seconds_created` | gauge | Histogram of time spent in DECODE phase for request. |  |
| `vllm:request_generation_tokens` | histogram | Number of generation tokens processed. |  |
| `vllm:request_generation_tokens_created` | gauge | Number of generation tokens processed. |  |
| `vllm:request_inference_time_seconds` | histogram | Histogram of time spent in RUNNING phase for request. |  |
| `vllm:request_inference_time_seconds_created` | gauge | Histogram of time spent in RUNNING phase for request. |  |
| `vllm:request_max_num_generation_tokens` | histogram | Histogram of maximum number of requested generation tokens. |  |
| `vllm:request_max_num_generation_tokens_created` | gauge | Histogram of maximum number of requested generation tokens. |  |
| `vllm:request_num_preemptions` | histogram | Histogram of the number of times a request was preempted. |  |
| `vllm:request_num_preemptions_created` | gauge | Histogram of the number of times a request was preempted. |  |
| `vllm:request_params_max_tokens` | histogram | Histogram of the max_tokens request parameter. |  |
| `vllm:request_params_max_tokens_created` | gauge | Histogram of the max_tokens request parameter. |  |
| `vllm:request_params_n` | histogram | Histogram of the n request parameter. |  |
| `vllm:request_params_n_created` | gauge | Histogram of the n request parameter. |  |
| `vllm:request_prefill_kv_computed_tokens` | histogram | Histogram of new KV tokens computed during prefill (excluding cached tokens). |  |
| `vllm:request_prefill_kv_computed_tokens_created` | gauge | Histogram of new KV tokens computed during prefill (excluding cached tokens). |  |
| `vllm:request_prefill_time_seconds` | histogram | Histogram of time spent in PREFILL phase for request. | prompt long : prefill chunké, cache de préfixes |
| `vllm:request_prefill_time_seconds_created` | gauge | Histogram of time spent in PREFILL phase for request. |  |
| `vllm:request_prompt_tokens` | histogram | Number of prefill tokens processed. |  |
| `vllm:request_prompt_tokens_created` | gauge | Number of prefill tokens processed. |  |
| `vllm:request_queue_time_seconds` | histogram | Histogram of time spent in WAITING phase for request. | capacité : réplicas, KEDA, max-num-seqs |
| `vllm:request_queue_time_seconds_created` | gauge | Histogram of time spent in WAITING phase for request. |  |
| `vllm:request_success_created` | gauge | Count of successfully processed requests. |  |
| `vllm:request_success_total` | counter | Count of successfully processed requests. |  |
| `vllm:request_time_per_output_token_seconds` | histogram | Histogram of time_per_output_token_seconds per request. |  |
| `vllm:request_time_per_output_token_seconds_created` | gauge | Histogram of time_per_output_token_seconds per request. |  |
| `vllm:time_to_first_token_seconds` | histogram | Histogram of time to first token in seconds. | prefill : max-num-batched-tokens, cache de préfixes, backend d'attention |
| `vllm:time_to_first_token_seconds_created` | gauge | Histogram of time to first token in seconds. |  |
