import unittest

from agency_runtime.providers import ProviderConfigurationError, ProviderRegistry


class ProviderRegistryTests(unittest.TestCase):
    def test_default_registry_exposes_five_safe_provider_contracts(self):
        registry = ProviderRegistry.from_environment({})

        providers = registry.public_list()

        self.assertEqual(
            [item["provider_id"] for item in providers],
            ["openai", "anthropic", "deepseek", "moonshot", "llama"],
        )
        self.assertEqual(len(providers), 5)
        self.assertTrue(all(item["configured"] is False for item in providers))
        self.assertNotIn("api_key", repr(providers).lower())
        self.assertNotIn("secret", repr(providers).lower())

    def test_configuration_state_is_derived_without_exposing_credentials(self):
        raw_key = "openai-provider-key-that-must-never-leave-the-server"
        registry = ProviderRegistry.from_environment(
            {
                "OPENAI_API_KEY": raw_key,
                "AGENCY_OPENAI_MODEL": "gpt-5.2",
                "DEEPSEEK_API_KEY": "deepseek-provider-key-value-2026",
                "AGENCY_DEEPSEEK_MODEL": "deepseek-v4-flash",
                "AGENCY_LLAMA_BASE_URL": "https://llama.example.test/v1",
                "AGENCY_LLAMA_MODEL": "llama-4-maverick",
            }
        )

        openai = registry.get("openai").public_dict()
        deepseek = registry.get("deepseek").public_dict()
        llama = registry.get("llama").public_dict()

        self.assertTrue(openai["configured"])
        self.assertEqual(openai["configuration_state"], "ready")
        self.assertEqual(openai["model"], "gpt-5.2")
        self.assertTrue(deepseek["configured"])
        self.assertEqual(deepseek["model"], "deepseek-v4-flash")
        self.assertFalse(llama["configured"])
        self.assertEqual(llama["configuration_state"], "missing_credential")
        self.assertNotIn(raw_key, repr(registry.public_list()))

    def test_partial_configuration_reports_one_actionable_missing_field(self):
        registry = ProviderRegistry.from_environment(
            {
                "ANTHROPIC_API_KEY": "anthropic-provider-key-value-2026",
                "MOONSHOT_API_KEY": "moonshot-provider-key-value-2026",
                "AGENCY_MOONSHOT_MODEL": "kimi-k3",
            }
        )

        anthropic = registry.get("anthropic").public_dict()
        moonshot = registry.get("moonshot").public_dict()

        self.assertEqual(anthropic["configuration_state"], "missing_model")
        self.assertEqual(moonshot["configuration_state"], "ready")
        self.assertEqual(moonshot["model"], "kimi-k3")

    def test_private_execution_config_redacts_credentials_and_aliases_must_agree(self):
        secret = "moonshot-secret-value-that-must-not-leak"
        registry = ProviderRegistry.from_environment(
            {
                "MOONSHOT_API_KEY": secret,
                "KIMI_API_KEY": secret,
                "AGENCY_MOONSHOT_MODEL": "kimi-k3",
            }
        )
        execution = registry.execution_config("moonshot")
        self.assertEqual(execution.credential, secret)
        self.assertNotIn(secret, repr(execution))
        self.assertNotIn(secret, repr(registry.public_list()))

        with self.assertRaises(ProviderConfigurationError):
            ProviderRegistry.from_environment(
                {
                    "MOONSHOT_API_KEY": "moonshot-secret-one-that-must-not-leak",
                    "KIMI_API_KEY": "moonshot-secret-two-that-must-not-leak",
                    "AGENCY_MOONSHOT_MODEL": "kimi-k3",
                }
            )

    def test_custom_endpoint_must_be_https_and_must_not_contain_credentials(self):
        with self.assertRaises(ProviderConfigurationError):
            ProviderRegistry.from_environment(
                {
                    "AGENCY_LLAMA_BASE_URL": "http://llama.example.test/v1",
                    "LLAMA_API_KEY": "llama-provider-key-value-2026",
                    "AGENCY_LLAMA_MODEL": "llama-4-scout",
                }
            )

        with self.assertRaises(ProviderConfigurationError):
            ProviderRegistry.from_environment(
                {
                    "AGENCY_LLAMA_BASE_URL": "https://user:password@llama.example.test/v1",
                    "LLAMA_API_KEY": "llama-provider-key-value-2026",
                    "AGENCY_LLAMA_MODEL": "llama-4-scout",
                }
            )

    def test_unknown_provider_is_not_enumerated(self):
        registry = ProviderRegistry.from_environment({})
        with self.assertRaises(KeyError):
            registry.get("unknown")


if __name__ == "__main__":
    unittest.main()
