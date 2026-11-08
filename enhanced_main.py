"""Independent entry point. Never uses the original SnowMM AppData directory."""

if __name__ == "__main__":
    # A local diagnostic for frozen startup failures; no user files or paths are sent.
    import faulthandler
    import sys
    from pathlib import Path

    diagnostic = None
    if getattr(sys, "frozen", False) and "--self-test" in sys.argv:
        report = Path(sys.argv[sys.argv.index("--self-test") + 1])
        report.parent.mkdir(parents=True, exist_ok=True)
        diagnostic = report.with_suffix(".startup.log").open("w", encoding="utf-8")
        faulthandler.enable(diagnostic)
        faulthandler.dump_traceback_later(30, file=diagnostic)
        diagnostic.write("Loading application modules\n")
        diagnostic.flush()
    from snowmm.enhanced.app import main

    raise SystemExit(main())
