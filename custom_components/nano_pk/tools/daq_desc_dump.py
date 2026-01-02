#!/usr/bin/env python3
"""Fetch the DAQPRJ description from a Hargassner boiler via telnet."""

import argparse
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from daq_fetcher import DEFAULT_COMMAND, DaqFetchError, fetch_daq_template


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Dump the DAQPRJ XML template via telnet"
    )
    parser.add_argument("host", help="IP or hostname of the boiler")
    parser.add_argument(
        "--port", type=int, default=23, help="Telnet port (default: 23)"
    )
    parser.add_argument(
        "--timeout", type=float, default=8.0, help="Connection timeout in seconds"
    )
    parser.add_argument(
        "--read-timeout",
        type=float,
        default=5.0,
        help="Read timeout for waiting on the DAQ response",
    )
    parser.add_argument(
        "--command",
        default=DEFAULT_COMMAND,
        help="Command to send after connecting (default: '$DAQ DESC')",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Optional output file to store the DAQPRJ XML",
    )

    args = parser.parse_args(argv)

    try:
        xml = fetch_daq_template(
            host=args.host,
            port=args.port,
            command=args.command,
            connect_timeout=args.timeout,
            read_timeout=args.read_timeout,
        )
    except DaqFetchError as exc:
        print(f"Failed to fetch DAQ description: {exc}", file=sys.stderr)
        return 1

    if args.output:
        Path(args.output).write_text(xml, encoding="utf-8")
        print(f"Wrote {len(xml)} bytes to {args.output}")
    else:
        print(xml)

    return 0


if __name__ == "__main__":
    sys.exit(main())
