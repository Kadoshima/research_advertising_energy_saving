#!/usr/bin/env python3
"""
Convert ESP32 session CSV to C header file for firmware embedding.

Usage:
    python scripts/convert_session_to_header.py --session 01 --output esp32_sweep/ccs_session_data.h

This generates a header file with the CCS time series as a const array.
"""

import argparse
import csv
from pathlib import Path


def convert_session_to_header(session_id: str, output_path: Path) -> None:
    """Convert session CSV to C header file."""

    input_path = Path(f"data/esp32_sessions/session_{session_id}.csv")

    if not input_path.exists():
        raise FileNotFoundError(f"Session file not found: {input_path}")

    # Read CSV
    intervals = []
    with open(input_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            intervals.append(int(row['interval_ms']))

    n_entries = len(intervals)
    duration_s = n_entries  # 1 entry per second

    # Generate header content
    header_content = f'''// === ccs_session_data.h ===
// Auto-generated from session_{session_id}.csv
// DO NOT EDIT MANUALLY
//
// Session: {session_id}
// Duration: {duration_s} seconds ({duration_s // 60} min {duration_s % 60} sec)
// Entries: {n_entries}

#ifndef CCS_SESSION_DATA_H
#define CCS_SESSION_DATA_H

#include <stdint.h>

// Session metadata
static const char* CCS_SESSION_ID = "{session_id}";
static const uint16_t CCS_N_ENTRIES = {n_entries};
static const uint32_t CCS_DURATION_S = {duration_s};

// Interval values at 1-second resolution
// Index = elapsed seconds from session start
// Value = advertising interval in ms (100, 500, or 2000)
static const uint16_t CCS_INTERVALS[{n_entries}] = {{
'''

    # Add interval values (16 per line for readability)
    for i in range(0, n_entries, 16):
        chunk = intervals[i:i+16]
        line = "    " + ", ".join(f"{v:4d}" for v in chunk)
        if i + 16 < n_entries:
            line += ","
        header_content += line + "\n"

    header_content += '''};

// Helper function to get interval for a given elapsed time
static inline uint16_t getIntervalForTime(uint32_t elapsed_s) {
    if (elapsed_s >= CCS_N_ENTRIES) {
        return CCS_INTERVALS[CCS_N_ENTRIES - 1];  // Hold last value
    }
    return CCS_INTERVALS[elapsed_s];
}

#endif // CCS_SESSION_DATA_H
'''

    # Write header file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        f.write(header_content)

    # Print summary
    interval_counts = {100: 0, 500: 0, 2000: 0}
    for v in intervals:
        if v in interval_counts:
            interval_counts[v] += 1

    print(f"Generated: {output_path}")
    print(f"  Session: {session_id}")
    print(f"  Duration: {duration_s}s")
    print(f"  Intervals: 100ms={interval_counts[100]}, 500ms={interval_counts[500]}, 2000ms={interval_counts[2000]}")


def main():
    parser = argparse.ArgumentParser(description="Convert session CSV to C header")
    parser.add_argument("--session", "-s", required=True, help="Session ID (e.g., 01)")
    parser.add_argument("--output", "-o", default="esp32_sweep/ccs_session_data.h",
                        help="Output header file path")
    args = parser.parse_args()

    convert_session_to_header(args.session, Path(args.output))


if __name__ == "__main__":
    main()
