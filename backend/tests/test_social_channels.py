import json
import unittest

from agency_runtime.social_channels import (
    SocialChannelConfigurationError,
    SocialChannelRegistry,
)


class SocialChannelRegistryTests(unittest.TestCase):
    def test_missing_configuration_is_secret_free_and_disabled(self):
        registry = SocialChannelRegistry.from_environment({})
        channels = registry.public_list()

        self.assertEqual([item["channel_id"] for item in channels], ["x", "instagram"])
        self.assertTrue(all(item["configuration_state"] == "missing_credentials" for item in channels))
        self.assertTrue(all(item["connection_state"] == "not_connected" for item in channels))
        self.assertTrue(all(item["oauth_start_available"] is False for item in channels))
        self.assertTrue(all(item["publishing_available"] is False for item in channels))
        self.assertTrue(all(item["external_effects_enabled"] is False for item in channels))
        serialized = json.dumps(channels)
        self.assertNotIn("x-consumer-secret-value", serialized)
        self.assertNotIn("instagram-app-secret", serialized)

    def test_x_consumer_credentials_and_loopback_callback_are_ready_for_authentication(self):
        registry = SocialChannelRegistry.from_environment(
            {
                "AGENCY_X_CONSUMER_KEY": "x-consumer-key-value",
                "AGENCY_X_CONSUMER_SECRET": "x-consumer-secret-value",
                "AGENCY_X_REDIRECT_URI": "http://127.0.0.1:4175/api/v1/social-channels/x/oauth/callback",
            }
        )
        channel = registry.get("x")
        public = channel.public_dict()

        self.assertTrue(channel.configured)
        self.assertEqual(channel.configuration_state, "ready_for_authentication")
        self.assertEqual(channel.oauth_flow, "oauth_1_0a_user_context")
        self.assertFalse(channel.requires_media)
        self.assertEqual(public["publish_protocol"], "POST /2/tweets")
        self.assertNotIn("x-consumer-key-value", repr(registry.private_config("x")))
        self.assertNotIn("x-consumer-secret-value", json.dumps(public))

    def test_x_oauth2_aliases_are_supported_when_values_agree(self):
        registry = SocialChannelRegistry.from_environment(
            {
                "AGENCY_X_CLIENT_ID": "x-client-id",
                "AGENCY_X_CLIENT_SECRET": "x-client-secret",
                "AGENCY_X_REDIRECT_URI": "https://app.example.test/oauth/x/callback",
            }
        )
        self.assertTrue(registry.get("x").configured)

    def test_instagram_requires_professional_account_media_and_publish_scopes(self):
        registry = SocialChannelRegistry.from_environment(
            {
                "AGENCY_INSTAGRAM_APP_ID": "instagram-app-id",
                "AGENCY_INSTAGRAM_APP_SECRET": "instagram-app-secret",
                "AGENCY_INSTAGRAM_REDIRECT_URI": "https://app.example.test/oauth/instagram/callback",
            }
        )
        instagram = registry.get("instagram")
        public = instagram.public_dict()

        self.assertTrue(instagram.configured)
        self.assertTrue(instagram.requires_media)
        self.assertIn("Professional", instagram.account_requirement)
        self.assertEqual(
            public["scopes"],
            ["instagram_business_basic", "instagram_business_content_publish"],
        )
        self.assertEqual(
            public["publish_protocol"],
            "POST /media then POST /media_publish",
        )
        self.assertNotIn("instagram-app-secret", json.dumps(public))
        self.assertNotIn("instagram-app-secret", repr(registry.private_config("instagram")))

    def test_credentials_without_callback_report_the_exact_missing_state(self):
        registry = SocialChannelRegistry.from_environment(
            {
                "AGENCY_X_CONSUMER_KEY": "x-key",
                "AGENCY_X_CONSUMER_SECRET": "x-secret",
            }
        )
        x_channel = registry.get("x")
        self.assertTrue(x_channel.credentials_configured)
        self.assertFalse(x_channel.callback_configured)
        self.assertEqual(x_channel.configuration_state, "missing_redirect_uri")

    def test_conflicting_aliases_fail_closed(self):
        with self.assertRaisesRegex(
            SocialChannelConfigurationError, "aliases disagree"
        ):
            SocialChannelRegistry.from_environment(
                {
                    "AGENCY_X_CONSUMER_KEY": "consumer-key",
                    "AGENCY_X_CLIENT_ID": "different-client-id",
                }
            )

    def test_redirect_uri_rejects_insecure_or_ambiguous_values(self):
        invalid = (
            "http://example.com/oauth/callback",
            "https://user:password@example.com/oauth/callback",
            "https://example.com/oauth/callback?tenant=alpha",
            "https://example.com/oauth/callback#fragment",
        )
        for redirect_uri in invalid:
            with self.subTest(redirect_uri=redirect_uri):
                with self.assertRaises(SocialChannelConfigurationError):
                    SocialChannelRegistry.from_environment(
                        {
                            "AGENCY_X_CONSUMER_KEY": "x-key",
                            "AGENCY_X_CONSUMER_SECRET": "x-secret",
                            "AGENCY_X_REDIRECT_URI": redirect_uri,
                        }
                    )


if __name__ == "__main__":
    unittest.main()
