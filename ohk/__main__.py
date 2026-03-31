"""Entry point for OHK — Onyx Hot Keys."""

import argparse

from .app import OHKApp


def main():
    parser = argparse.ArgumentParser(description="OHK — Onyx Hot Keys")
    parser.add_argument("--cps", type=int, default=20,
                        help="Default clicks per second (default: 20)")
    args = parser.parse_args()

    app = OHKApp(cps=max(1, args.cps))
    app.run()


if __name__ == "__main__":
    main()
