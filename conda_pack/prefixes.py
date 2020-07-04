# Much of this file borrowed from conda/core/portability.py:
#
# https://github.com/conda/conda/blob/master/conda/core/portability.py
#
# The license of which has been provided below:
#
# -----------------------------------------------------------------------------
#
# BSD 3-Clause License
#
# Copyright (c) 2012, Continuum Analytics, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of the copyright holder nor the names of its
#       contributors may be used to endorse or promote products
#       derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

import re
import struct
import sys

on_win = sys.platform == 'win32'

# three capture groups: whole_shebang, executable, options
SHEBANG_REGEX = (
        # pretty much the whole match string
        br'^(#!'
        # allow spaces between #! and beginning of the executable path
        br'(?:[ ]*)'
        # the executable is the next text block without an escaped
        # space or non-space whitespace character
        br'(/(?:\\ |[^ \n\r\t])*)'
        # the rest of the line can contain option flags
        br'(.*)'
        # end whole_shebang group
        br')$')


def update_prefix(path, new_prefix, placeholder, mode='text'):
    if on_win and mode == 'text':
        # force all prefix replacements to forward slashes to simplify need to
        # escape backslashes replace with unix-style path separators
        new_prefix = new_prefix.replace('\\', '/')

    with open(path, 'rb+') as fh:
        original_data = fh.read()
        fh.seek(0)

        data = replace_prefix(original_data, mode, placeholder, new_prefix)

        # If the before and after content is the same, skip writing
        if data != original_data:
            fh.write(data)
            fh.truncate()


def replace_prefix(data, mode, placeholder, new_prefix):
    if mode == 'text':
        data2 = text_replace(data, placeholder, new_prefix)
    elif mode == 'binary':
        data2 = binary_replace(data,
                               placeholder.encode('utf-8'),
                               new_prefix.encode('utf-8'))
        if not on_win and len(data2) != len(data):
            message = ("Found mismatched data length in binary file:\n"
                       "original data length: {len_orig!d})\n"
                       "new data length: {len_new!d}\n"
                       ).format(len_orig=len(data),
                                len_new=len(data2))
            raise ValueError(message)
    else:
        raise ValueError("Invalid mode: %r" % mode)
    return data2


def text_replace(data, placeholder, new_prefix):
    return data.replace(placeholder.encode('utf-8'), new_prefix.encode('utf-8'))


if on_win:
    def binary_replace(data, placeholder, new_prefix):
        placeholder = placeholder.lower()
        new_prefix = new_prefix.lower()
        if placeholder not in data:
            return data
        return replace_pyzzer_entry_point_shebang(data, placeholder, new_prefix)

else:
    def binary_replace(data, placeholder, new_prefix):
        """Perform a binary replacement of `data`, where ``placeholder`` is
        replaced with ``new_prefix`` and the remaining string is padded with null
        characters.  All input arguments are expected to be bytes objects."""

        def replace(match):
            occurances = match.group().count(placeholder)
            padding = (len(placeholder) - len(new_prefix)) * occurances
            if padding < 0:
                raise ValueError("negative padding")
            return match.group().replace(placeholder, new_prefix) + b'\0' * padding

        pat = re.compile(re.escape(placeholder) + b'([^\0]*?)\0')
        return pat.sub(replace, data)


def replace_pyzzer_entry_point_shebang(all_data, placeholder, new_prefix):
    """Code adapted from pyzzer. This is meant to deal with entry point exe's
    created by distlib, which consist of a launcher, then a shebang, then a zip
    archive of the entry point code to run.  We need to change the shebang.
    """
    # Copyright (c) 2013 Vinay Sajip.
    #
    # Permission is hereby granted, free of charge, to any person obtaining a copy
    # of this software and associated documentation files (the "Software"), to deal
    # in the Software without restriction, including without limitation the rights
    # to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    # copies of the Software, and to permit persons to whom the Software is
    # furnished to do so, subject to the following conditions:
    #
    # The above copyright notice and this permission notice shall be included in
    # all copies or substantial portions of the Software.
    #
    # THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    # IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    # FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    # AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    # LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    # OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
    # THE SOFTWARE.
    launcher = shebang = None
    pos = all_data.rfind(b'PK\x05\x06')
    if pos >= 0:
        end_cdr = all_data[pos + 12:pos + 20]
        cdr_size, cdr_offset = struct.unpack('<LL', end_cdr)
        arc_pos = pos - cdr_size - cdr_offset
        data = all_data[arc_pos:]
        if arc_pos > 0:
            pos = all_data.rfind(b'#!', 0, arc_pos)
            if pos >= 0:
                shebang = all_data[pos:arc_pos]
                if pos > 0:
                    launcher = all_data[:pos]

        if data and shebang and launcher:
            if hasattr(placeholder, 'encode'):
                placeholder = placeholder.encode('utf-8')
            if hasattr(new_prefix, 'encode'):
                new_prefix = new_prefix.encode('utf-8')
            shebang = shebang.replace(placeholder, new_prefix)
            all_data = b"".join([launcher, shebang, data])
    return all_data
