"""FinTree CLI — command-line interface."""

import sys


def main():
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help", "help"):
        print("Usage: fintree <command>")
        print()
        print("Commands:")
        print("  serve [--port PORT]   Start the FinTree explorer (default port 8000)")
        print("  version               Show version")
        return

    if args[0] == "version":
        from fintree import __version__
        print(f"fintree {__version__}")
        return

    if args[0] == "serve":
        port = 8000
        if "--port" in args:
            idx = args.index("--port")
            if idx + 1 < len(args):
                port = int(args[idx + 1])

        try:
            import uvicorn
        except ImportError:
            print("Error: uvicorn not installed. Run: pip install fintree[api]")
            sys.exit(1)

        # Add the api package to the path
        from pathlib import Path
        api_dir = Path(__file__).resolve().parent.parent.parent / "api"
        if api_dir.exists():
            sys.path.insert(0, str(api_dir))

        import webbrowser
        print(f"Starting FinTree explorer at http://localhost:{port}")
        webbrowser.open(f"http://localhost:{port}")
        uvicorn.run("fintree_api.main:app", host="127.0.0.1", port=port, log_level="info")
        return

    print(f"Unknown command: {args[0]}")
    print("Run 'fintree --help' for usage.")
    sys.exit(1)


if __name__ == "__main__":
    main()
