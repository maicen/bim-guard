"""Tests for scripts/prewarm_demo.py."""

from __future__ import annotations

from unittest.mock import patch

from scripts.prewarm_demo import (
    build_parser,
    main,
    prewarm,
    verify_arch,
    warm_arch,
)


class TestRequestShape:
    """What actually goes on the wire."""

    def test_warm_arch_sends_project_id(self):
        with patch("scripts.prewarm_demo._post", return_value=({"cached": False, "audit_issues": []}, 1.5)) as post:
            warm_arch("http://x", 1541)
        _, path, fields = post.call_args.args
        assert path == "/api/analyze/arch"
        assert ("project_id", "1541") in fields

    def test_verify_arch_reads_endpoint(self):
        with patch("scripts.prewarm_demo._get", return_value=({"cached": True, "audit_issues": []}, 0.2)) as get:
            verify_arch("http://x", 1541)
        _, path = get.call_args.args[:2]
        assert path == "/api/analyze/arch/1541"


class TestReporting:
    def test_prewarm_records_runs(self):
        with (
            patch("scripts.prewarm_demo._post", return_value=({"cached": False, "audit_issues": [1, 2]}, 1.0)),
            patch("scripts.prewarm_demo._get", return_value=({"cached": True, "audit_issues": [1, 2]}, 0.1)),
        ):
            report = prewarm("http://x", [1541], log=lambda _: None)
        assert len(report.warmed) == 1
        assert len(report.verified) == 1
        assert report.warnings == []

    def test_main_cli_arguments(self):
        parser = build_parser()
        args = parser.parse_args(["--projects", "1540", "1541"])
        assert args.projects == [1540, 1541]

    def test_main_with_no_projects_returns_two(self):
        assert main([]) == 2

    def test_main_with_successful_run(self):
        with (
            patch("scripts.prewarm_demo._post", return_value=({"cached": False, "audit_issues": []}, 1.0)),
            patch("scripts.prewarm_demo._get", return_value=({"cached": True, "audit_issues": []}, 0.1)),
        ):
            assert main(["--projects", "1541"]) == 0
