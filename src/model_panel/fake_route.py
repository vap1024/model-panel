"""Deterministic offline command used in examples and acceptance checks."""
import argparse
import sys

ANSWERS = {
    "alpha": "Parallel panel synthesis evidence supports careful review and shared decisions.",
    "beta": "Parallel panel synthesis evidence supports careful review and measured decisions.",
    "gamma": "Parallel panel synthesis evidence reveals orbital marmalade uncertainty and divergent signals.",
}


def main(argv: list[str] | None = None) -> int:
    """Print a fixed answer for the selected flavour."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--flavour", required=True, choices=("alpha", "beta", "gamma", "empty", "fail", "meta"))
    parser.add_argument("--prompt-file")
    args = parser.parse_args(argv)
    if args.flavour == "fail":
        print("synthetic route failure", file=sys.stderr)
        return 3
    if args.flavour == "meta":
        print("metadata answer")
        print('PANEL_META {"tokens_in": 12, "tokens_out": 34, "finish_reason": "stop"}')
    elif args.flavour != "empty":
        print(ANSWERS[args.flavour])
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
