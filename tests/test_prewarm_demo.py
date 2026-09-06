"""The demo pre-warm script: which entries it warms, and how it reports them.

The HTTP calls are mocked. What matters here is the combination list -- if it
does not match what the analyse page can produce, the demo hits a cold cache on
a chip the presenter unticks -- and that a verification failure reaches the exit
status rather than only the log.
"""

from __future__ import annotations

from unittest.mock import patch

from scripts.prewarm_demo import (
    PIPING_ENGINES,
    Verification,
    Warmed,
    build_parser,
    engine_combinations,
    main,
    prewarm,
    verify,
    warm_corrosion,
    warm_seismic,
)


class TestCombinations:
    """What the analyse page's five chips can produce."""

    def test_five_engines_give_thirty_one_selections(self):
        """2**5 - 1: every subset except the one the Run button refuses."""
        assert len(engine_combinations()) == 31

    def test_every_selection_is_unique(self):
        combinations = engine_combinations()
        assert len(set(combinations)) == len(combinations)

    def test_the_empty_selection_is_not_offered(self):
        """The page disables Run rather than sending an empty selection."""
        assert () not in engine_combinations()

    def test_the_full_selection_comes_first(self):
        """It is the view the page opens on and the slowest to compute."""
        assert engine_combinations()[0] == PIPING_ENGINES

    def test_selections_keep_the_page_chip_order(self):
        order = {code: i for i, code in enumerate(PIPING_ENGINES)}
        for selection in engine_combinations():
            positions = [order[code] for code in selection]
            assert positions == sorted(positions)

    def test_the_short_ids_are_what_the_page_sends(self):
        """AnalyzeView seeds selectedEngines with these, not the -001 labels."""
        assert PIPING_ENGINES == ("GC", "CC", "MC", "MM", "XM")

    def test_full_only_warms_one_selection(self):
        assert engine_combinations(full_only=True) == [PIPING_ENGINES]

    def test_a_smaller_engine_set_still_follows_the_formula(self):
        assert len(engine_combinations(("GC", "CC"))) == 3


class TestRequestShape:
    """What actually goes on the wire."""

    def test_corrosion_sends_every_engine_plus_include_low(self):
        with patch("scripts.prewarm_demo._post", return_value=({"cached": False, "audit_issues": []}, 1.5)) as post:
            warm_corrosion("http://x", 1541, ("GC", "CC"))
        _, path, fields = post.call_args.args
        assert path == "/api/analyze/corrosion"
        assert ("project_id", "1541") in fields
        assert [v for k, v in fields if k == "engines"] == ["GC", "CC"]
        assert ("include_low", "true") in fields
        assert ("use_cache", "true") in fields

    def test_seismic_sends_no_engine_selection(self):
        """One kernel, nothing to select between: sending a selection would
        create a cache entry the page can never ask for."""
        with patch("scripts.prewarm_demo._post", return_value=({"cached": False, "audit_issues": []}, 9.0)) as post:
            warm_seismic("http://x", 1542)
        _, path, fields = post.call_args.args
        assert path == "/api/analyze/seismic"
        assert [k for k, _ in fields] == ["project_id", "use_cache"]

    def test_verification_reads_the_results_endpoint_with_the_same_engines(self):
        with patch("scripts.prewarm_demo._get", return_value=({"cached": True, "issue_stats": {}}, 0.2)) as get:
            verify("http://x", 1541, "corrosion", ("GC", "MM"))
        _, path, params = get.call_args.args
        assert path == "/api/analyze/results/1541/corrosion"
        assert ("use_cache", "true") in params
        assert [v for k, v in params if k == "engines"] == ["GC", "MM"]


class TestReporting:
    """A warm-up nobody checked is worth nothing, so the check drives the exit."""

    def test_every_combination_is_warmed_and_verified(self):
        lines: list[str] = []
        with (
            patch("scripts.prewarm_demo._post", return_value=({"cached": False, "audit_issues": [1, 2]}, 3.0)),
            patch("scripts.prewarm_demo._get", return_value=({"cached": True, "issue_stats": {"medium": 2}}, 0.1)),
        ):
            report = prewarm("http://x", [1541], [1542], log=lines.append)

        assert len(report.warmed) == 32  # 31 corrosion selections + 1 seismic
        assert len(report.verified) == 32
        assert report.warnings == []

    def test_a_cold_second_read_is_a_warning(self):
        with (
            patch("scripts.prewarm_demo._post", return_value=({"cached": False, "audit_issues": []}, 3.0)),
            patch("scripts.prewarm_demo._get", return_value=({"cached": False, "issue_stats": {}}, 42.0)),
        ):
            report = prewarm("http://x", [1541], [], combinations="full-only", log=lambda _: None)

        assert len(report.warnings) == 1

    def test_warnings_are_printed_and_exit_non_zero(self, capsys):
        with (
            patch("scripts.prewarm_demo._post", return_value=({"cached": False, "audit_issues": []}, 3.0)),
            patch("scripts.prewarm_demo._get", return_value=({"cached": False, "issue_stats": {}}, 42.0)),
        ):
            status = main(["--piping", "1541", "--combinations", "full-only"])

        assert status == 1
        assert "WARN" in capsys.readouterr().out

    def test_all_hits_exit_zero(self):
        with (
            patch("scripts.prewarm_demo._post", return_value=({"cached": False, "audit_issues": []}, 3.0)),
            patch("scripts.prewarm_demo._get", return_value=({"cached": True, "issue_stats": {}}, 0.1)),
        ):
            assert main(["--seismic", "1542"]) == 0

    def test_no_project_ids_is_a_usage_error(self):
        assert main([]) == 2

    def test_a_failed_warm_exits_non_zero(self):
        import urllib.error

        with (
            patch("scripts.prewarm_demo._post", side_effect=urllib.error.URLError("refused")),
            patch("scripts.prewarm_demo._get", return_value=({"cached": True, "issue_stats": {}}, 0.1)),
        ):
            assert main(["--seismic", "1542", "--combinations", "full-only"]) == 1

    def test_verification_ok_requires_both_cached_and_no_error(self):
        assert Verification(1, "corrosion", ("GC",), True, 0, 0.1).ok
        assert not Verification(1, "corrosion", ("GC",), True, 0, 0.1, error="boom").ok
        assert not Verification(1, "corrosion", ("GC",), False, 0, 0.1).ok

    def test_a_warm_records_what_came_back(self):
        with patch("scripts.prewarm_demo._post", return_value=({"cached": True, "audit_issues": [1, 2, 3]}, 0.4)):
            warmed = warm_corrosion("http://x", 1541, PIPING_ENGINES)
        assert isinstance(warmed, Warmed)
        assert (warmed.cached, warmed.issues, warmed.slug) == (True, 3, "corrosion")


class TestCli:
    def test_defaults(self):
        args = build_parser().parse_args([])
        assert args.base_url == "http://127.0.0.1:8000"
        assert (args.piping, args.seismic, args.combinations) == ([], [], "all")

    def test_ids_and_flags_parse(self):
        args = build_parser().parse_args(
            ["--base-url", "http://127.0.0.1:8001", "--piping", "1540", "1541", "--seismic", "1542", "--combinations", "full-only"]
        )
        assert args.base_url == "http://127.0.0.1:8001"
        assert args.piping == [1540, 1541]
        assert args.seismic == [1542]
        assert args.combinations == "full-only"
