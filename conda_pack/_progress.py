from __future__ import division, absolute_import

import sys
import threading
import time
from timeit import default_timer


def format_time(t):
    """Format seconds into a human readable form.

    >>> format_time(10.4)
    '10.4s'
    >>> format_time(1000.4)
    '16min 40.4s'
    """
    m, s = divmod(t, 60)
    h, m = divmod(m, 60)
    if h:
        return '{0:2.0f}hr {1:2.0f}min {2:4.1f}s'.format(h, m, s)
    elif m:
        return '{0:2.0f}min {1:4.1f}s'.format(m, s)
    else:
        return '{0:4.1f}s'.format(s)


class progressbar(object):
    """A simple progressbar for iterables.

    Displays a progress bar showing progress through an iterable.

    Parameters
    ----------
    iterable : iterable
        The object to iterate over.
    width : int, optional
        Width of the bar in characters.
    enabled : bool, optional
        Whether to log progress. Useful for turning off progress reports
        without changing your code. Default is True.
    file : file, optional
        Where to log progress. Default is ``sys.stdout``.

    Example
    -------
    >>> with progressbar(iterable) as itbl:  # doctest: +SKIP
    ...     for i in itbl:
    ...         do_stuff(i)
    [########################################] | 100% Completed | 5.2 s
    """
    def __init__(self, iterable, width=40, enabled=True, file=None):
        self._iterable = iterable
        self._ndone = 0
        self._ntotal = len(iterable) + 1  # wait for exit to finish
        self._width = width
        self._enabled = enabled
        self._file = sys.stdout if file is None else file

    def __enter__(self):
        if self._enabled:
            self._start_time = default_timer()
            # Start background thread
            self._running = True
            self._timer = threading.Thread(target=self._timer_func)
            self._timer.daemon = True
            self._timer.start()
        return self

    def __exit__(self, type, value, traceback):
        if self._enabled:
            self._running = False
            self._timer.join()
            if type is None:  # Finished if no exception
                self._ndone += 1
            self._update_bar()
            self._file.write('\n')
            self._file.flush()

    def __iter__(self):
        for i in self._iterable:
            self._ndone += 1
            yield i

    def _timer_func(self):
        while self._running:
            self._update_bar()
            time.sleep(0.1)

    def _update_bar(self):
        elapsed = default_timer() - self._start_time
        frac = (self._ndone / self._ntotal) if self._ntotal else 1
        bar = '#' * int(self._width * frac)
        percent = int(100 * frac)
        elapsed = format_time(elapsed)
        msg = '\r[{0:<{1}}] | {2}% Completed | {3}'.format(bar, self._width,
                                                           percent, elapsed)
        try:
            self._file.write(msg)
            self._file.flush()
        except ValueError:
            pass
