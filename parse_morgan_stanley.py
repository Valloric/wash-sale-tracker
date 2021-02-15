#!/usr/bin/env python
#
# Parses table rows copy-pasted from Morgan Stanley 1099-B PDF into structured
# form.
# Use Google Chrome to copy from the 1099-B PDFs because it does the best job of
# correctly detecting line breaks.
# Each table row should become 3 separate lines in the text file.
# See --help for arguments to control sort order, output field separator etc.
#
# Usage example:
#  parse_morgan_stanley.py -i input.txt --symbol=GOOG
#
# Output is printed to stdout

import argparse
from collections import namedtuple
import fileinput
import csv
import sys
import arrow
from moneyed import Money, USD
from typing import List


HUMAN_FIELD_NAMES = [
    "Symbol",
    "Num Shares",
    "Description",
    "Buy Date",
    "Sell Date",
    "Basis",
    "Proceeds",
    "Buy Lot",
]

# Order matters!
WASH_FIELD_NAMES = [
    "Num Shares",
    "Symbol",
    "Description",
    "Buy Date",
    "Adjusted Buy Date",
    "Basis",
    "Adjusted Basis",
    "Sell Date",
    "Proceeds",
    "Adjustment Code",
    "Adjustment",
    "Form Position",
    "Buy Lot",
    "Replacement For",
    "Is Replacement",
    "Loss Processed",
]


def get_row_words(filename: str) -> List[List[str]]:
    rows: List[List[str]] = []
    line_num: int = 0
    buffer: List[str] = []
    for line in fileinput.input(files=[filename]):
        line_num += 1
        buffer.append(line)
        if line_num == 3:
            row = " ".join(buffer).split()
            rows.append(row)
            line_num = 0
            buffer = []
    return rows


def parse_dollars(input: str) -> Money:
    return Money(input.replace("$", "").replace(",", ""), USD)


Trade = namedtuple(
    "Trade", ["cost_basis", "num_shares", "proceeds", "sell_date", "buy_date"]
)


def parse_trades(rows: List[List[str]]) -> List[Trade]:
    trades = []
    for row in rows:
        trades.append(
            Trade(
                cost_basis=parse_dollars(row[-1]),
                proceeds=parse_dollars(row[-2]),
                sell_date=arrow.get(row[-3], "MM/DD/YY"),
                buy_date=arrow.get(row[-4], "MM/DD/YY"),
                num_shares=int(float(row[-5])),
            )
        )
    return trades


def sorted_trades(trades: List[Trade], parsed) -> List[Trade]:
    return (
        sorted(trades, key=lambda x: x.sell_date)
        if parsed.sort_by == "sale"
        else sorted(trades, key=lambda x: x.buy_date)
    )


def print_output(trades: List[Trade], parsed) -> None:
    def money_format(money):
        if parsed.format == "human":
            return "${}".format(money.amount)
        return money.get_amount_in_sub_unit()

    separator = "," if parsed.separator == "comma" else "\t"
    writer = csv.DictWriter(
        sys.stdout,
        delimiter=separator,
        quotechar="|",
        quoting=csv.QUOTE_MINIMAL,
        fieldnames=HUMAN_FIELD_NAMES
        if parsed.format == "human"
        else WASH_FIELD_NAMES,
    )
    writer.writeheader()
    for trade in trades:
        description = "{} shares of {}".format(trade.num_shares, parsed.symbol)
        writer.writerow(
            {
                "Symbol": parsed.symbol,
                "Num Shares": trade.num_shares,
                "Description": description,
                "Buy Date": trade.buy_date.format("MM/DD/YYYY"),
                "Sell Date": trade.sell_date.format("MM/DD/YYYY"),
                "Basis": money_format(trade.cost_basis),
                "Proceeds": money_format(trade.proceeds),
                "Buy Lot": "",
            }
        )


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input_file")
    parser.add_argument("-s", "--symbol")
    parser.add_argument(
        "--format",
        choices=["wash", "human"],
        default="wash",
        help="'wash' format is what wash.py expects. 'human' format is more "
        "human-readable and nicer for Google Sheets import",
    )
    parser.add_argument(
        "--separator", choices=["comma", "tab"], default="comma"
    )
    parser.add_argument("--sort-by", choices=["sale", "buy"], default="buy")
    return parser.parse_args()


def main():
    parsed = parse_args()
    rows = get_row_words(parsed.input_file)
    trades = parse_trades(rows)
    print_output(sorted_trades(trades, parsed), parsed)


if __name__ == "__main__":
    main()
