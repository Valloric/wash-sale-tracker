import csv
import datetime

_HAS_TERMINALTABLES = False
try:
    import terminaltables
    _HAS_TERMINALTABLES = True
except ImportError:
    pass


class BadHeadersError(Exception):
    """Raised if the headers that are parsed are not in the correct format."""


class Lot(object):
    """Models a single lot of stock."""

    # A list of the field names for a Lot.
    FIELD_NAMES = ['num_shares', 'symbol', 'description', 'buy_date', 'basis',
                   'sell_date', 'proceeds', 'adjustment_code', 'adjustment',
                   'form_position', 'buy_lot', 'is_replacement']

    def __init__(self, num_shares, symbol, description, buy_date, basis,
                 sell_date, proceeds, adjustment_code, adjustment,
                 form_position, buy_lot, is_replacement):
        """Initializes a lot.

        Args:
            num_shares: An integer.
            symbol: A string, the stock symbol.
            description: A string, an arbitrary description of this lot.
            buy_date: A datetime.date.
            basis: An integer, the number of cents that the lot was bought for.
                May be adjusted by a wash sale.
            sell_date: A datetime.date or None.
            proceeds: An integer, the number of cents that the lot was sold
                for, or 0 if the lot is not sold.
            adjustment_code: A string, basically 'W' in case this was a wash
                sale.
            adjustment: An integer, the number of cents of the disallowed loss,
                or 0 if the lot is not sold.
            form_position: A string, an arbitrary value that helps to determine
                which lots are related when a lot is split.
            buy_lot: A string, an arbitrary value that indicates that can be
                used to indicate that multiple entries are part of the same
                logical lot. An empty string indicates that this is a unique
                lot.
            is_replacement: A boolean, if true then this lot has been used as
                replacement shares. Useful because a lot can only be used as
                replacement shares once.
        """
        self.num_shares = num_shares
        self.symbol = symbol
        self.description = description
        self.buy_date = buy_date
        self.basis = basis
        self.sell_date = sell_date
        self.proceeds = proceeds
        self.adjustment_code = adjustment_code
        self.adjustment = adjustment
        self.form_position = form_position
        self.buy_lot = buy_lot
        self.is_replacement = is_replacement

        # This is used to determine whether the loss has been processed for a
        # potential wash sale.
        # TODO: Make this a field that is in the CSV, so that running the
        # script is idempotent.
        self.loss_processed = False

    def is_loss(self):
        """Determines whether this lot is a loss.

        Returns:
            True if this lot was sold for a loss. False if it was sold for a
            gain, or it has not been sold.
        """
        if self.sell_date and self.proceeds < self.basis:
            return True
        return False

    def __eq__(self, other):
        return (self.num_shares == other.num_shares and
                self.symbol == other.symbol and
                self.description == other.description and
                self.buy_date == other.buy_date and
                self.basis == other.basis and
                self.sell_date == other.sell_date and
                self.proceeds == other.proceeds and
                self.adjustment_code == other.adjustment_code and
                self.adjustment == other.adjustment and
                self.form_position == other.form_position and
                self.buy_lot == other.buy_lot and
                self.is_replacement == other.is_replacement)

    def __str__(self):
        return ' '.join(self.str_data())

    __repl__ = __str__

    def str_data(self):
        return ['{:d}'.format(self.num_shares),
                '{}'.format(self.symbol),
                '{}'.format(self.description),
                '{}'.format(self.buy_date),
                '${:.2f}'.format(float(self.basis) / 100),
                '{}'.format(self.sell_date),
                '${:.2f}'.format(float(self.proceeds) / 100),
                '{}'.format(self.adjustment_code),
                '${:.2f}'.format(float(self.adjustment) / 100),
                '{}'.format(self.form_position),
                '{}'.format(self.buy_lot),
                '{}'.format(self.is_replacement)]

    @staticmethod
    def cmp_by_buy_date(a, b):
        """Sorts two lots based on their buy dates."""
        if a.buy_date != b.buy_date:
            return (a.buy_date - b.buy_date).days
        if a.sell_date != b.sell_date:
            if a.sell_date is None:
                return 1
            if b.sell_date is None:
                return -1
            return (a.sell_date - b.sell_date).days
        if a.form_position != b.form_position:
            if a.form_position < b.form_position:
                return -1
            return 1
        return 0

    @staticmethod
    def cmp_by_sell_date(a, b):
        """Sorts two lots based on their sell dates."""
        if a.sell_date != b.sell_date:
            if a.sell_date is None:
                return 1
            if b.sell_date is None:
                return -1
            return (a.sell_date - b.sell_date).days
        if a.buy_date != b.buy_date:
            return (a.buy_date - b.buy_date).days
        if a.form_position != b.form_position:
            if a.form_position < b.form_position:
                return -1
            return 1
        return 0

    @staticmethod
    def cmp_by_num_shares(a, b):
        """Sorts two lots based solely on their number of shares."""
        return a.num_shares - b.num_shares


class Lots(object):
    """Contains a set of lots."""

    # A map of Lot field name to CSV header value.
    HEADERS = {
        'num_shares': 'Num Shares',
        'symbol': 'Symbol',
        'description': 'Description',
        'buy_date': 'Buy Date',
        'basis': 'Basis',
        'sell_date': 'Sell Date',
        'proceeds': 'Proceeds',
        'adjustment_code': 'Adjustment Code',
        'adjustment': 'Adjustment',
        'form_position': 'Form Position',
        'buy_lot': 'Buy Lot',
        'is_replacement': 'Is Replacement'
    }

    # A map of Lot field name to short strings naming the column.
    SHORT_HEADERS = {
        'num_shares': 'Num',
        'symbol': 'Symb',
        'description': 'Desc',
        'buy_date': 'Buy Date',
        'basis': 'Basis',
        'sell_date': 'Sell Date',
        'proceeds': 'Proceeds',
        'adjustment_code': 'AdjCode',
        'adjustment': 'Adj',
        'form_position': 'Pos',
        'buy_lot': 'BuyLot',
        'is_replacement': 'IsRepl'
    }

    # A map of Lot field name to CSV header value. These are legacy header
    # values, for compatibility with
    # https://github.com/adlr/wash-sale-calculator
    LEGACY_HEADERS = {
        'num_shares': 'Cnt',
        'symbol': 'Sym',
        'description': 'Desc',
        'buy_date': 'BuyDate',
        'basis': 'Basis',
        'sell_date': 'SellDate',
        'proceeds': 'Proceeds',
        'adjustment_code': 'AdjCode',
        'adjustment': 'Adj',
        'form_position': 'FormPosition',
        'buy_lot': 'BuyLot',
        'is_replacement': 'IsReplacement'
    }

    def __init__(self, lots):
        """Creates a new set of lots.

        Populates the buy_lot field in each lot if it is not set.

        Args:
            lots: A list of Lot objects.
        """
        i = 1
        for lot in lots:
            if not lot.buy_lot:
                lot.buy_lot = '_{}'.format(i)
                i += 1
        self._lots = lots

    def lots(self):
        """Returns the list of Lot objects."""
        return self._lots

    def add(self, lot):
        """Adds a lot to this object.

        Args:
            lot: The Lot to add.
        """
        self._lots.append(lot)

    def size(self):
        """Returns the number of lots."""
        return len(self._lots)

    def sort(self, **kwargs):
        self._lots.sort(**kwargs)

    def __eq__(self, other):
        retval = True
        for this, that in zip(self._lots, other._lots):
            retval = retval and this == that
        return retval

    def __str__(self):
        global _HAS_TERMINALTABLES
        if _HAS_TERMINALTABLES:
            return self._terminaltables_str()
        else:
            return self._simple_str()

    def __iter__(self):
        return iter(self._lots)

    def do_print(self, matched_lots=None):
        global _HAS_TERMINALTABLES
        if _HAS_TERMINALTABLES:
            print self._terminaltables_str(matched_lots)
        else:
            print self._simple_str(matched_lots)

    def _terminaltables_str(self, matched_lots=None):
        lots_data = [[self.SHORT_HEADERS[field] for field in Lot.FIELD_NAMES]]
        if matched_lots:
            lots_data[0].append('Matched')
        for lot in self._lots:
            str_data = lot.str_data()
            if matched_lots:
                if id(lot) in map(id, matched_lots):
                    str_data.append('*')
                else:
                    str_data.append('')
            lots_data.append(str_data)
        return terminaltables.AsciiTable(lots_data).table

    def _simple_str(self, matched_lots=None):
        lot_strings = []
        lot_strings.append(' '.join([self.SHORT_HEADERS[field]
                                     for field in Lot.FIELD_NAMES]))
        if matched_lots:
            lot_strings.append('Matched')
        for lot in self._lots:
            str_data = str(lot)
            if matched_lots and id(lot) in map(id, matched_lots):
                str_data = '* ' + str_data
            lot_strings.append(str_data)
        return '\n'.join(lot_strings)

    __repl__ = __str__

    @staticmethod
    def create_from_csv_data(data):
        """Creates a Lots object based on a multi-line string of csv data.

        The content of the csv file must look like:
        Num Shares,Symbol,Description,Buy Date,Basis,Sell Date,Proceeds,Adjustment Code,Adjustment,Form Position,Buy Lot,Is Replacement
        10,ABC,A,9/15/2014,2000,10/5/2014,1800,,,lot1

        Args:
            data: A list of strings, where each line is a CSV row that matches
                    the format above
        Returns:
            A Lots object
        """

        def convert_to_int(value):
            if value:
                return int(value)
            return 0

        def convert_to_date(value):
            if value:
                return datetime.datetime.strptime(value, '%m/%d/%Y').date()
            return None

        def convert_to_bool(value):
            if value:
                return value.lower() == 'true'
            return False

        reader = csv.DictReader(data, fieldnames=Lot.FIELD_NAMES)
        header_row = reader.next()
        if header_row != Lots.HEADERS and header_row != Lots.LEGACY_HEADERS:
            raise BadHeadersError()
        lots = []
        for row in reader:
            row['num_shares'] = convert_to_int(row['num_shares'])
            row['buy_date'] = convert_to_date(row['buy_date'])
            row['basis'] = convert_to_int(row['basis'])
            row['sell_date'] = convert_to_date(row['sell_date'])
            row['proceeds'] = convert_to_int(row['proceeds'])
            row['adjustment'] = convert_to_int(row['adjustment'])
            row['is_replacement'] = convert_to_bool(row['is_replacement'])
            lots.append(Lot(**row))
        return Lots(lots)

    def write_csv_data(self, output_file):
        """Writes this lots data as CSV data to an output file.

        Args:
            output_file: A file-like object to write to.
        """

        def convert_from_int(value):
            if value:
                return str(value)
            return ''

        def convert_from_date(value):
            if value:
                return value.strftime('%m/%d/%Y')
            return ''

        def convert_from_bool(value):
            if value:
                return 'True'
            return 'False'

        writer = csv.DictWriter(output_file, fieldnames=Lot.FIELD_NAMES)
        writer.writerow(self.HEADERS)
        for lot in self._lots:
            row = {}
            row['num_shares'] = convert_from_int(lot.num_shares)
            row['symbol'] = lot.symbol
            row['description'] = lot.description
            row['buy_date'] = convert_from_date(lot.buy_date)
            row['basis'] = convert_from_int(lot.basis)
            row['sell_date'] = convert_from_date(lot.sell_date)
            row['proceeds'] = convert_from_int(lot.proceeds)
            row['adjustment_code'] = lot.adjustment_code
            row['adjustment'] = convert_from_int(lot.adjustment)
            row['form_position'] = lot.form_position
            row['buy_lot'] = lot.buy_lot
            row['is_replacement'] = convert_from_bool(lot.is_replacement)
            writer.writerow(row)