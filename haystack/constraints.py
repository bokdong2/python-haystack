#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2011 Loic Jaquemet loic.jaquemet+python@gmail.com
#

"""
This module holds some basic constraint class for the Haystack model.
"""

__author__ = "Loic Jaquemet loic.jaquemet+python@gmail.com"

import ConfigParser
import logging
import sys

import os
import re

log = logging.getLogger('constraints')

from haystack.abc import interfaces


class ConstraintsConfigHandler(interfaces.IConstraintsConfigHandler):
    """
    Read constraints config files, applies constraints to modules.

      a list(), a [], a dict(), a set() (possibly containing RangeValue, PerfectMatch and NotNull)
      IgnoreMember
      RangeValue(low, high)
      NotNull
      PerfectMatch('bytestr')

    """
    valid_names = ['IgnoreMember', 'NotNull', 'RangeValue', 'PerfectMatch']
    _rv = re.compile(r'''(?P<fn>RangeValue\((?P<args>[^)]+)\))''')
    _pm = re.compile(r'''(?P<fn>PerfectMatch\((?P<args>'[^']+')\))''')
    _nn = re.compile(r'''(?P<fn>NotNull)[,]*,?''')

    def read(self, filename):
        """
        Read the constraints list from a file

        :param filename:
        :return:
        """
        if not os.access(filename, os.F_OK):
            raise IOError("File not found")
        # read the constraint file
        parser = ConfigParser.RawConfigParser()
        parser.read(filename)
        # prepare the return object
        _constraints = dict()
        # each section anem is the name of the target structure
        for struct_name in parser.sections():
            log.debug('handling structure %s', struct_name)
            if struct_name not in _constraints:
                _constraints[struct_name] = []
            # each config entry is a field and its IConstraint
            for field, value in parser.items(struct_name):
                log.debug('%s: field %s ::= %s', struct_name, field, value)
                value = self._parse(value)
                # each field can only have one IConstraint (which can be a list of)
                _constraints[struct_name].append((field, value))
        return _constraints

    def _parse(self, value):
        if IgnoreMember.__name__ == value:
            return IgnoreMember
        elif IgnoreMember.__name__ in value:
            raise ValueError("IgnoreMember should be alone as a constraint")

        # TODO use re and .start(groups)
        if '[' == value[0]:
            remnant = value[1:-1]
            log.debug('list is %s', remnant)
            _args = []
            # check for functions in the list
            for fn in [self._rv, self._pm, self._nn]:
                res = []
                # find all fn
                for x in fn.finditer(remnant):
                    log.debug("Found fn %s", x.group('fn'))
                    res.append(x.group('fn'))
                # now parse each fn
                for match in res:
                    _args.append(self._parse_c(match))
                    # remove them from the parsing lefts
                    remnant = remnant.replace(match, "")
                    log.debug("remnant is %s", remnant)
            # now handle other element in list, like integers and floats
            _class_type = list
            args = remnant.split(',')
            for x in args:
                if '' == x.strip():
                    continue
                else:
                    try:
                        # try an int
                        _args.append(int(x))
                    except ValueError, e:
                        # try a float
                        try:
                            _args.append(float(x))
                        except ValueError, e:
                            # fallback to string
                            _args.append(str(x))
            return _class_type(_args)
        else:
            return self._parse_c(value)

    def _parse_c(self, value):
        """
        Parse the function and args for a known function.

        :param value:
        :return:
        """
        if 'NotNull' in value:
            return NotNull
        # get the function name
        _t = value.split('(')
        _class_name = _t[0]
        args = _t[1][:-1]
        # else its a RangeValue or a PerfectMatch
        log.debug('we have a IConstraint %s', _class_name)
        if _class_name not in ['RangeValue', 'PerfectMatch']:
            raise ValueError('invalid constraints near %s', _class_name)
        # we know the constraint
        _class_type = getattr(sys.modules[__name__], _class_name)
        log.debug('args: %s', args)
        # look at the args
        _args = None
        if _class_name == 'RangeValue':
            _args = self._rv.search(value).group('args').split(',')
            assert len(_args) == 2
            _args = [int(x) for x in _args]
            return _class_type(*_args)
        elif _class_name == 'PerfectMatch':
            _args = args[1:-1]
            return _class_type(_args)
        else:
            raise RuntimeError('no such constraint %s',_class_name)

    def apply_to_module(self, constraints,module):
        """
        Apply the list of constraints to a module

        :param constraints: list of IConstraint
        :param module:
        :return:
        """
        pass

class IgnoreMember(interfaces.IConstraint):

    """
    Constraint class for the Haystack model.
    If this constraints is applied on a Structure member,
    the member will be ignored by the validation engine.
    """

    def __contains__(self, obj):
        return True


class RangeValue(interfaces.IConstraint):

    """
    Constraint class for the Haystack model.
    If this constraints is applied on a Structure member,
    the member has to be between 'low' and 'high' values to be
    considered as Valid.
    """

    def __init__(self, low, high):
        self.low = low
        self.high = high

    def __contains__(self, obj):
        return self.low <= obj <= self.high

    def __eq__(self, obj):
        if isinstance(obj, RangeValue):
            return self.low == obj.low and self.high == obj.high
        return self.low <= obj <= self.high


class NotNullComparable(interfaces.IConstraint):

    """
    Constraint class for the Haystack model.
    If this constraints is applied on a Structure member,
    the member should not be null to be considered valid by the validation engine.
    """

    def __contains__(self, obj):
        return bool(obj)

    def __eq__(self, obj):
        return bool(obj)

"""
Constraint class for the Haystack model.
If this constraints is applied on a Structure member,
the member should not be null to be considered valid by the validation engine.
"""
NotNull = NotNullComparable()


class BytesComparable(interfaces.IConstraint):

    """
    Constraint class for the Haystack model.
    If this constraints is applied on a Structure member,
    the member should have the same bytes value and length.
    """

    def __init__(self, seq):
        self.seq = seq

    def __contains__(self, obj):
        if cmp(self, obj) == 0:
            return True
        return False

    def __cmp__(self, obj):
        import ctypes
        if isinstance(obj, type(ctypes.c_void_p)):
            if ctypes.sizeof(obj) != len(self.seq):
                return -1
            bytes = ctypes.string_at(ctypes.addressof(obj), ctypes.sizeof(obj))
            if bytes == self.seq:
                return 0
            else:
                return -1
        # check if its a ctypes
        try:
            ctypes.sizeof(obj)
            return cmp(self.seq, ctypes.string_at(
                ctypes.addressof(obj), ctypes.sizeof(obj)))
        except TypeError:
            return cmp(self.seq, obj)

PerfectMatch = BytesComparable
