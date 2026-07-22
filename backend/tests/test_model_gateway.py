import json
import unittest

import httpx

from agency_runtime.model_gateway import (
    ModelGateway,
    ModelGatewayConfigurationError,
    ModelGatewayDisabledError,
    ModelGatewayProviderError,
    ModelRequest,
)


class ModelGatewayTests(unittest.TestCase):
    def test_execution_is_disabled_by_default_without_touching_transport(self):
        calls = []

        def handler(request):
            calls.append(request)
            raise AssertionError("transport must not be called")

        gateway = ModelGateway.from_environment(
            {
                "OPENAI_API_KEY": "openai-secret-value-that-must-not-leak",
                "AGENCY_OPENAI_MODEL": "gpt-5.2",
            },
            transport=httpx.MockTransport(handler),
        )
        with self.assertRaises(ModelGatewayDisabledError):
            gateway.complete(ModelRequest(request_id="request-disabled-001", user="hello"))
        self.assertEqual(calls, [])
        self.assertFalse(gateway.public_status()["execution_enabled"])
        gateway.close()

    def test_openai_responses_contract_and_receipt_are_secret_free(self):
        secret = "openai-secret-value-that-must-not-leak"
        observed = []

        def handler(request):
            observed.append(request)
            self.assertEqual(request.method, "POST")
            self.assertEqual(str(request.url), "https://api.openai.com/v1/responses")
            self.assertEqual(request.headers["authorization"], "Bearer {}".format(secret))
            body = json.loads(request.content)
            self.assertEqual(body["model"], "gpt-5.2")
            self.assertEqual(body["instructions"], "Return a concise campaign insight.")
            self.assertEqual(body["input"], "Explain the audience tension.")
            self.assertEqual(body["max_output_tokens"], 128)
            return httpx.Response(
                200,
                headers={"x-request-id": "req_openai_001"},
                json={
                    "id": "resp_001",
                    "model": "gpt-5.2",
                    "output": [
                        {
                            "type": "message",
                            "content": [
                                {"type": "output_text", "text": "Lead with verifiable evidence."}
                            ],
                        }
                    ],
                    "usage": {"input_tokens": 14, "output_tokens": 6, "total_tokens": 20},
                },
            )

        gateway = ModelGateway.from_environment(
            {
                "AGENCY_MODEL_EXECUTION_ENABLED": "true",
                "AGENCY_MODEL_PROVIDER": "openai",
                "OPENAI_API_KEY": secret,
                "AGENCY_OPENAI_MODEL": "gpt-5.2",
                "AGENCY_MODEL_EGRESS_ALLOWED_HOSTS": "api.openai.com",
                "AGENCY_MODEL_MAX_OUTPUT_TOKENS": "128",
            },
            transport=httpx.MockTransport(handler),
        )
        result = gateway.complete(
            ModelRequest(
                request_id="request-openai-001",
                system="Return a concise campaign insight.",
                user="Explain the audience tension.",
            )
        )

        self.assertEqual(result.text, "Lead with verifiable evidence.")
        self.assertEqual(result.receipt.provider_id, "openai")
        self.assertEqual(result.receipt.provider_request_id, "req_openai_001")
        self.assertEqual(result.receipt.input_tokens, 14)
        self.assertEqual(result.receipt.output_tokens, 6)
        self.assertEqual(result.receipt.total_tokens, 20)
        serialized = json.dumps(result.receipt.public_dict(), sort_keys=True)
        self.assertNotIn(secret, serialized)
        self.assertNotIn(result.text, serialized)
        self.assertNotIn("Explain the audience tension", serialized)
        self.assertEqual(len(observed), 1)
        gateway.close()

    def test_anthropic_messages_contract(self):
        secret = "anthropic-secret-value-that-must-not-leak"

        def handler(request):
            self.assertEqual(str(request.url), "https://api.anthropic.com/v1/messages")
            self.assertEqual(request.headers["x-api-key"], secret)
            self.assertEqual(request.headers["anthropic-version"], "2023-06-01")
            self.assertNotIn("authorization", request.headers)
            body = json.loads(request.content)
            self.assertEqual(body["model"], "claude-sonnet-4")
            self.assertEqual(body["system"], "Be precise.")
            self.assertEqual(body["messages"], [{"role": "user", "content": "Summarize this."}])
            self.assertEqual(body["max_tokens"], 96)
            return httpx.Response(
                200,
                headers={"request-id": "req_anthropic_001"},
                json={
                    "id": "msg_001",
                    "model": "claude-sonnet-4",
                    "content": [{"type": "text", "text": "A precise summary."}],
                    "usage": {"input_tokens": 10, "output_tokens": 4},
                },
            )

        gateway = ModelGateway.from_environment(
            {
                "AGENCY_MODEL_EXECUTION_ENABLED": "true",
                "AGENCY_MODEL_PROVIDER": "anthropic",
                "ANTHROPIC_API_KEY": secret,
                "AGENCY_ANTHROPIC_MODEL": "claude-sonnet-4",
                "AGENCY_MODEL_EGRESS_ALLOWED_HOSTS": "api.anthropic.com",
                "AGENCY_MODEL_MAX_OUTPUT_TOKENS": "96",
            },
            transport=httpx.MockTransport(handler),
        )
        result = gateway.complete(
            ModelRequest(
                request_id="request-anthropic-001",
                system="Be precise.",
                user="Summarize this.",
            )
        )
        self.assertEqual(result.text, "A precise summary.")
        self.assertEqual(result.receipt.total_tokens, 14)
        gateway.close()

    def test_openai_compatible_contracts_for_deepseek_kimi_and_llama(self):
        cases = (
            (
                "deepseek",
                {
                    "DEEPSEEK_API_KEY": "deepseek-secret-value-that-must-not-leak",
                    "AGENCY_DEEPSEEK_MODEL": "deepseek-v4-flash",
                    "AGENCY_MODEL_EGRESS_ALLOWED_HOSTS": "api.deepseek.com",
                },
                "https://api.deepseek.com/chat/completions",
                "deepseek-v4-flash",
            ),
            (
                "moonshot",
                {
                    "MOONSHOT_API_KEY": "moonshot-secret-value-that-must-not-leak",
                    "AGENCY_MOONSHOT_MODEL": "kimi-k3",
                    "AGENCY_MODEL_EGRESS_ALLOWED_HOSTS": "api.moonshot.ai",
                },
                "https://api.moonshot.ai/v1/chat/completions",
                "kimi-k3",
            ),
            (
                "llama",
                {
                    "LLAMA_API_KEY": "llama-secret-value-that-must-not-leak",
                    "AGENCY_LLAMA_MODEL": "llama-4-maverick",
                    "AGENCY_LLAMA_BASE_URL": "https://llama.example.test/v1",
                    "AGENCY_MODEL_EGRESS_ALLOWED_HOSTS": "llama.example.test",
                },
                "https://llama.example.test/v1/chat/completions",
                "llama-4-maverick",
            ),
        )
        for provider_id, extra, expected_url, expected_model in cases:
            with self.subTest(provider_id=provider_id):
                observed = []

                def handler(request):
                    observed.append(request)
                    self.assertEqual(str(request.url), expected_url)
                    self.assertTrue(request.headers["authorization"].startswith("Bearer "))
                    body = json.loads(request.content)
                    self.assertEqual(body["model"], expected_model)
                    self.assertEqual(
                        body["messages"],
                        [
                            {"role": "system", "content": "Use evidence."},
                            {"role": "user", "content": "Write one insight."},
                        ],
                    )
                    self.assertEqual(body["max_tokens"], 64)
                    self.assertFalse(body["stream"])
                    return httpx.Response(
                        200,
                        headers={"x-request-id": "req_{}_001".format(provider_id)},
                        json={
                            "id": "chat_{}_001".format(provider_id),
                            "model": expected_model,
                            "choices": [
                                {
                                    "index": 0,
                                    "message": {"role": "assistant", "content": "Evidence first."},
                                    "finish_reason": "stop",
                                }
                            ],
                            "usage": {
                                "prompt_tokens": 8,
                                "completion_tokens": 3,
                                "total_tokens": 11,
                            },
                        },
                    )

                gateway = ModelGateway.from_environment(
                    {
                        "AGENCY_MODEL_EXECUTION_ENABLED": "true",
                        "AGENCY_MODEL_PROVIDER": provider_id,
                        "AGENCY_MODEL_MAX_OUTPUT_TOKENS": "64",
                        **extra,
                    },
                    transport=httpx.MockTransport(handler),
                )
                result = gateway.complete(
                    ModelRequest(
                        request_id="request-{}-001".format(provider_id),
                        system="Use evidence.",
                        user="Write one insight.",
                    )
                )
                self.assertEqual(result.text, "Evidence first.")
                self.assertEqual(result.receipt.model, expected_model)
                self.assertEqual(len(observed), 1)
                gateway.close()

    def test_provider_errors_are_sanitized_and_never_retried(self):
        secret = "provider-secret-that-must-not-leak"
        raw_body = "upstream leaked secret={} and private prompt".format(secret)
        calls = []

        def handler(request):
            calls.append(request)
            return httpx.Response(429, text=raw_body, headers={"x-request-id": "req_rate_001"})

        gateway = ModelGateway.from_environment(
            {
                "AGENCY_MODEL_EXECUTION_ENABLED": "true",
                "AGENCY_MODEL_PROVIDER": "openai",
                "OPENAI_API_KEY": secret,
                "AGENCY_OPENAI_MODEL": "gpt-5.2",
                "AGENCY_MODEL_EGRESS_ALLOWED_HOSTS": "api.openai.com",
            },
            transport=httpx.MockTransport(handler),
        )
        with self.assertRaises(ModelGatewayProviderError) as captured:
            gateway.complete(ModelRequest(request_id="request-rate-001", user="private prompt"))
        message = str(captured.exception)
        self.assertEqual(message, "model provider request failed (status=429)")
        self.assertNotIn(secret, message)
        self.assertNotIn(raw_body, message)
        self.assertNotIn("private prompt", message)
        self.assertEqual(len(calls), 1)
        gateway.close()

    def test_limits_invalid_response_and_host_policy_fail_closed(self):
        base = {
            "AGENCY_MODEL_EXECUTION_ENABLED": "true",
            "AGENCY_MODEL_PROVIDER": "openai",
            "OPENAI_API_KEY": "openai-secret-value-that-must-not-leak",
            "AGENCY_OPENAI_MODEL": "gpt-5.2",
            "AGENCY_MODEL_EGRESS_ALLOWED_HOSTS": "api.openai.com",
        }
        with self.assertRaises(ModelGatewayConfigurationError):
            ModelGateway.from_environment({**base, "AGENCY_MODEL_EGRESS_ALLOWED_HOSTS": "example.com"})
        with self.assertRaises(ModelGatewayConfigurationError):
            ModelGateway.from_environment({**base, "AGENCY_OPENAI_BASE_URL": "https://127.0.0.1/v1", "AGENCY_MODEL_EGRESS_ALLOWED_HOSTS": "127.0.0.1"})
        with self.assertRaises(ModelGatewayConfigurationError):
            ModelGateway.from_environment({**base, "AGENCY_MODEL_MAX_OUTPUT_TOKENS": "0"})

        gateway = ModelGateway.from_environment(
            {**base, "AGENCY_MODEL_MAX_INPUT_CHARS": "16"},
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json={})),
        )
        with self.assertRaises(ModelGatewayConfigurationError):
            gateway.complete(ModelRequest(request_id="request-input-limit", user="x" * 17))
        gateway.close()

        gateway = ModelGateway.from_environment(
            {**base, "AGENCY_MODEL_MAX_RESPONSE_BYTES": "64"},
            transport=httpx.MockTransport(
                lambda _: httpx.Response(200, content=b"{" + b"x" * 128 + b"}")
            ),
        )
        with self.assertRaises(ModelGatewayProviderError) as captured:
            gateway.complete(ModelRequest(request_id="request-response-limit", user="hello"))
        self.assertEqual(str(captured.exception), "model provider response exceeded the configured size limit")
        gateway.close()

        gateway = ModelGateway.from_environment(
            base,
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"output": []})),
        )
        with self.assertRaises(ModelGatewayProviderError) as captured:
            gateway.complete(ModelRequest(request_id="request-invalid-shape", user="hello"))
        self.assertEqual(str(captured.exception), "model provider returned an invalid response")
        gateway.close()

    def test_selected_provider_must_be_exact_ready_and_enabled(self):
        with self.assertRaises(ModelGatewayConfigurationError):
            ModelGateway.from_environment(
                {
                    "AGENCY_MODEL_EXECUTION_ENABLED": "yes",
                    "AGENCY_MODEL_PROVIDER": "openai",
                }
            )
        with self.assertRaises(ModelGatewayConfigurationError):
            ModelGateway.from_environment(
                {
                    "AGENCY_MODEL_EXECUTION_ENABLED": "true",
                    "AGENCY_MODEL_PROVIDER": "unknown",
                }
            )
        with self.assertRaises(ModelGatewayConfigurationError):
            ModelGateway.from_environment(
                {
                    "AGENCY_MODEL_EXECUTION_ENABLED": "true",
                    "AGENCY_MODEL_PROVIDER": "openai",
                    "AGENCY_OPENAI_MODEL": "gpt-5.2",
                    "AGENCY_MODEL_EGRESS_ALLOWED_HOSTS": "api.openai.com",
                }
            )


if __name__ == "__main__":
    unittest.main()
