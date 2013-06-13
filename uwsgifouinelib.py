import collections
from importlib import import_module
import itertools
import logging
import numpy
import re
import datetime


logger = logging.getLogger('uwsgiFouine')


def add_parse_options(parser):
    parser.add_option('--num_results', action='store',
                      dest='num_results', default=30, type='int')
    parser.add_option('--date_from', action='store',
                      dest='date_from', default=None,
                      help='Parse from date. Format: %Y-%m-%d')
    parser.add_option('--time_from', action='store',
                      dest='time_from', default=None,
                      help='Parse from time. Date from NEEDED. Format: %H:%M:%S')
    parser.add_option('--date_to', action='store',
                      dest='date_to', default=None,
                      help='Parse to date. Format: %Y-%m-%d')
    parser.add_option('--time_to', action='store',
                      dest='time_to', default=None,
                      help='Parse to time. Date to NEEDED. Format: %H:%M:%S')
    parser.add_option('--path_map_function', action='store',
                      dest='path_map_function', default=False,
                      help='A python function to rename paths')


class LineParser(object):
    def __init__(self, path_map_function=None, date_from=None, time_from=None, date_to=None, time_to=None):
        if path_map_function:
            self.path_map_function = string_to_symbol(path_map_function)
        else:
            self.path_map_function = None

        if date_from:
            self.date_from = date_from
        else:
            self.date_from = None

        if time_from:
            self.time_from = time_from
        else:
            self.time_from = None

        if date_to:
            self.date_to = date_to
        else:
            self.date_to = None

        if time_to:
            self.time_to = time_to
        else:
            self.time_to = None

    def parse_line(self, line):
        res = re.match(r'.* (\S+ \S+ \S+ \S+ \S+) (GET|POST) (\S+) .* in (\d+) msecs .*', line)
        if not res:
            if logger.isEnabledFor(logger.warn):
                logger.warn("Can't parse line: {0}".format(line.strip()))
            return None

        if self.date_from:
            start_date = datetime.datetime.strptime(self.date_from, '%Y-%m-%d')
            if self.time_from:
                start_date = datetime.datetime.strptime(
                    "{date} {time}".format(date=self.date_from, time=self.time_from), '%Y-%m-%d %H:%M:%S')

            log_date = datetime.datetime.strptime(res.group(1).replace(']', '').replace('[', ''), '%a %b %d %H:%M:%S %Y')
            if log_date < start_date:
                return None

        if self.date_to:
            end_date = datetime.datetime.strptime(self.date_to, '%Y-%m-%d')
            if self.time_to:
                end_date = datetime.datetime.strptime(
                    "{date} {time}".format(date=self.date_to, time=self.time_to), '%Y-%m-%d %H:%M:%S')

            log_date = datetime.datetime.strptime(res.group(1).replace(']', '').replace('[', ''), '%a %b %d %H:%M:%S %Y')
            if log_date > end_date:
                return None

        path = res.group(3).split('?')[0]
        if path.endswith('/'):
            path = path[:-1]
        if self.path_map_function:
            path = self.path_map_function(path)
        return path, int(res.group(4))


def condense_parsed_data(data):
    res = collections.defaultdict(list)
    for row in data:
        if row:
            res[row[0]].append(row[1])
    return res


def condensed_data_to_summary(data, aggregator):
    return dict(itertools.imap(lambda (a, b): (a, aggregator(b)), data.iteritems()))


def string_to_symbol(str):
    parts = str.split('.')
    module = import_module('.'.join(parts[:-1]))
    return getattr(module, parts[-1])


def print_data(data, num_results):
    import locale

    # locale.setlocale(locale.LC_ALL, 'en_US')
    row_count = iter(xrange(1, 999999))

    def print_row(row):
        details = data[row[0]]
        args = {'path': row[0],
                'row_count': row_count.next(),
                'total_msecs':
                    locale.format('%d', sum(details), grouping=True),
                'avg_msecs':
                    locale.format('%d', numpy.average(details), grouping=True),
                'max_msecs':
                    locale.format('%d', max(details), grouping=True),
                'num_calls':
                    locale.format('%d', len(details), grouping=True), }
        print "{row_count}. {path} | {total_msecs} total ms | {avg_msecs} avg ms | " \
              "{max_msecs} max ms | {num_calls} calls".format(**args)

    print "Where was the most time spent?"
    print "=============================="
    for row in collections.Counter(
            condensed_data_to_summary(data, sum)).most_common(num_results):
        print_row(row)
    for i in xrange(3):
        print ""
    row_count = iter(xrange(1, 999999))
    print "What were the slowest pages (max page load time)?"
    print "=============================="
    for row in collections.Counter(
            condensed_data_to_summary(data, max)).most_common(num_results):
        print_row(row)
    for i in xrange(3):
        print ""
    row_count = iter(xrange(1, 999999))
    print "What were the slowest pages (avg page load time)?"
    print "=============================="
    for row in collections.Counter(
            condensed_data_to_summary(data, numpy.average)).most_common(num_results):
        print_row(row)


def parse_log(logfile, options):
    f = open(logfile, 'r')
    logger.info("opened " + logfile)
    parser = LineParser(
        options.path_map_function,
        options.date_from,
        options.time_from,
        options.date_to,
        options.time_to
    )
    data = condense_parsed_data(itertools.imap(parser.parse_line, f))
    print_data(data, options.num_results)
