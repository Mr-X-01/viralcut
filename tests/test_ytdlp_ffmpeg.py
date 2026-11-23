"""Частичное скачивание yt-dlp должно находить наш ffmpeg.

Регрессия из 1.5.7: бинарник imageio-ffmpeg называется
`ffmpeg-macos-aarch64-v9.0`, а yt-dlp для download_ranges проверяет команду
`ffmpeg` из PATH и отвечал «ffmpeg is not installed».
"""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from viralcut import config, downloader


class _TempData(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="vc-ffmpeg-"))
        self._old_data = config.DATA_DIR
        config.DATA_DIR = self.tmp
        config._ffmpeg_dir_cache = None
        config._ffmpeg_cache = None
        config._ffprobe_cache = None
        self._old_path = os.environ.get("PATH", "")

    def tearDown(self) -> None:
        config.DATA_DIR = self._old_data
        config._ffmpeg_dir_cache = None
        config._ffmpeg_cache = None
        config._ffprobe_cache = None
        os.environ["PATH"] = self._old_path


class BinDirTest(_TempData):
    def test_exposes_runnable_canonical_ffmpeg(self):
        bin_dir = config.ffmpeg_bin_dir()
        name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
        binary = bin_dir / name
        self.assertTrue(binary.exists(), "в data/bin должен появиться канонический ffmpeg")
        self.assertTrue(config._runs(binary), "канонический ffmpeg обязан запускаться")

    def test_heals_broken_symlink(self):
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
        broken = bin_dir / name
        broken.symlink_to(bin_dir / "нет-такого-файла")
        self.assertFalse(config._runs(broken))

        config.ffmpeg_bin_dir()

        self.assertTrue(config._runs(broken), "битая ссылка должна пересоздаться")

    def test_exposes_ffprobe_when_available(self):
        probe = config.ffprobe()
        if not probe:
            self.skipTest("в системе нет ffprobe")
        name = "ffprobe.exe" if os.name == "nt" else "ffprobe"
        self.assertTrue((config.ffmpeg_bin_dir() / name).exists())


class YtDlpSeesFfmpegTest(_TempData):
    def test_partial_download_gate_passes_with_clean_path(self):
        """PATH как в бандле .app (без ffmpeg), но data/bin даёт команду ffmpeg."""
        # эмулируем урезанный PATH: пустая папка — ffmpeg заведомо не находится
        empty = self.tmp / "empty-path"
        empty.mkdir(parents=True, exist_ok=True)
        os.environ["PATH"] = str(empty)
        config.ffmpeg_bin_dir()  # создаёт data/bin

        from yt_dlp.downloader.external import FFmpegFD

        self.assertFalse(FFmpegFD.available(), "до подготовки yt-dlp не видит ffmpeg")

        opts = downloader.ytdlp_ffmpeg({"quiet": True})

        self.assertTrue(downloader.ytdlp_ffmpeg_ready(),
                        "после подготовки проверка частичного скачивания должна проходить")
        self.assertEqual(opts["ffmpeg_location"], str(config.ffmpeg_bin_dir()))
        from yt_dlp.postprocessor.ffmpeg import FFmpegPostProcessor

        self.assertEqual(FFmpegPostProcessor._ffmpeg_location.get(),
                         str(config.ffmpeg_bin_dir()))

    def test_section_without_ffmpeg_raises_actionable_error(self):
        with mock.patch.object(downloader, "ytdlp_ffmpeg_ready", return_value=False):
            with self.assertRaises(downloader.DownloadError) as ctx:
                downloader.download_section(
                    "https://youtube.com/watch?v=test", self.tmp / "proj", 1.0, 5.0)
        message = str(ctx.exception)
        self.assertNotIn("is not installed", message)
        self.assertIn("VIRALCUT_FFMPEG", message)


class YouTubeQualityTest(unittest.TestCase):
    def test_pot_client_is_checked_after_sd_response(self):
        sd = {"formats": [{"format_id": "18", "vcodec": "avc1", "height": 360}]}
        hd = {"formats": [{"format_id": "137", "vcodec": "avc1", "height": 1080}]}
        with mock.patch("yt_dlp.YoutubeDL") as ydl, mock.patch.object(downloader, "ensure_path"), \
             mock.patch.dict(os.environ, {"VIRALCUT_NODE": "node.exe",
                                          "VIRALCUT_POT_URL": "http://127.0.0.1:4416"}):
            ydl.return_value.__enter__.return_value.extract_info.side_effect = [sd, sd, hd]
            info, args, label = downloader._youtube_info("https://youtube.com/watch?v=test", None, True)
        self.assertEqual(info, hd)
        self.assertEqual(label, "PO-token")
        self.assertEqual(args["youtube"]["fetch_pot"], ["always"])
        self.assertEqual(ydl.call_args.args[0]["js_runtimes"], {"node": {"path": "node.exe"}})

    def test_sd_requested_uses_the_first_suitable_response(self):
        sd = {"formats": [{"format_id": "18", "vcodec": "avc1", "height": 360}]}
        with mock.patch("yt_dlp.YoutubeDL") as ydl, mock.patch.object(downloader, "ensure_path"):
            ydl.return_value.__enter__.return_value.extract_info.return_value = sd
            info, _, _ = downloader._youtube_info("https://youtube.com/watch?v=test", None, True,
                                                  preferred_height=360)
        ydl.assert_called_once()
        self.assertEqual(info, sd)

    def test_hd_is_preferred_over_lower_avc_format(self):
        formats = [
            {"format_id": "18", "vcodec": "avc1", "acodec": "mp4a", "ext": "mp4", "height": 360},
            {"format_id": "248", "vcodec": "vp9", "ext": "webm", "height": 1080},
            {"format_id": "140", "acodec": "mp4a", "ext": "m4a"},
        ]
        self.assertEqual(downloader._pick_format({"formats": formats}, 1080), ("248+140", 1080))


if __name__ == "__main__":
    unittest.main(verbosity=2)
