import unittest

from check_video import VideoQAError, evaluate_metadata


def example(width=1080, height=1920, fps="30/1", codec="h264", pix="yuv420p", duration="6.0", audio="aac"):
    return {"format": {"duration": duration}, "streams": [
        {"codec_type": "video", "codec_name": codec, "width": width, "height": height,
         "avg_frame_rate": fps, "pix_fmt": pix, "nb_frames": "180"},
        {"codec_type": "audio", "codec_name": audio}
    ]}


class DeliveryQATest(unittest.TestCase):
    def test_valid_vertical(self):
        value = evaluate_metadata(example())
        self.assertEqual(value["status"], "pass")
        self.assertEqual(value["video"]["frames"], 180)

    def test_valid_horizontal(self):
        self.assertEqual(evaluate_metadata(example(1920, 1080), orientation="horizontal")["status"], "pass")

    def test_missing_audio_fails(self):
        item = example()
        item["streams"].pop()
        self.assertIn("AAC", str(evaluate_metadata(item)["errors"]))

    def test_bad_codec_fails(self):
        self.assertEqual(evaluate_metadata(example(codec="hevc"))["status"], "fail")

    def test_low_resolution_fails(self):
        self.assertEqual(evaluate_metadata(example(360, 640))["status"], "fail")

    def test_bad_frame_rate_fails(self):
        self.assertEqual(evaluate_metadata(example(fps="12/1"))["status"], "fail")

    def test_final_tier_requires_1080_short_edge(self):
        self.assertEqual(evaluate_metadata(example(), tier="final")["status"], "pass")
        self.assertEqual(evaluate_metadata(example(720,1280), tier="final")["status"], "fail")

    def test_wrong_orientation_fails(self):
        self.assertEqual(evaluate_metadata(example(), orientation="horizontal")["status"], "fail")

    def test_missing_video_stream_raises(self):
        with self.assertRaises(VideoQAError):
            evaluate_metadata({"format": {"duration": "6"}, "streams": []})


if __name__ == "__main__":
    unittest.main()
