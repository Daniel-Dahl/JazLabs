r"""Wrapper for digHolo.h

Generated with:
/Users/s4356803/opt/anaconda3/bin/ctypesgen digHolo.h --library=digHolo.dll -o digholoHeader.py

Do not modify this file.
"""

__docformat__ = "restructuredtext"

# Begin preamble for Python

import ctypes
import sys
from ctypes import *  # noqa: F401, F403

_int_types = (ctypes.c_int16, ctypes.c_int32)
if hasattr(ctypes, "c_int64"):
    # Some builds of ctypes apparently do not have ctypes.c_int64
    # defined; it's a pretty good bet that these builds do not
    # have 64-bit pointers.
    _int_types += (ctypes.c_int64,)
for t in _int_types:
    if ctypes.sizeof(t) == ctypes.sizeof(ctypes.c_size_t):
        c_ptrdiff_t = t
del t
del _int_types



class UserString:
    def __init__(self, seq):
        if isinstance(seq, bytes):
            self.data = seq
        elif isinstance(seq, UserString):
            self.data = seq.data[:]
        else:
            self.data = str(seq).encode()

    def __bytes__(self):
        return self.data

    def __str__(self):
        return self.data.decode()

    def __repr__(self):
        return repr(self.data)

    def __int__(self):
        return int(self.data.decode())

    def __long__(self):
        return int(self.data.decode())

    def __float__(self):
        return float(self.data.decode())

    def __complex__(self):
        return complex(self.data.decode())

    def __hash__(self):
        return hash(self.data)

    def __le__(self, string):
        if isinstance(string, UserString):
            return self.data <= string.data
        else:
            return self.data <= string

    def __lt__(self, string):
        if isinstance(string, UserString):
            return self.data < string.data
        else:
            return self.data < string

    def __ge__(self, string):
        if isinstance(string, UserString):
            return self.data >= string.data
        else:
            return self.data >= string

    def __gt__(self, string):
        if isinstance(string, UserString):
            return self.data > string.data
        else:
            return self.data > string

    def __eq__(self, string):
        if isinstance(string, UserString):
            return self.data == string.data
        else:
            return self.data == string

    def __ne__(self, string):
        if isinstance(string, UserString):
            return self.data != string.data
        else:
            return self.data != string

    def __contains__(self, char):
        return char in self.data

    def __len__(self):
        return len(self.data)

    def __getitem__(self, index):
        return self.__class__(self.data[index])

    def __getslice__(self, start, end):
        start = max(start, 0)
        end = max(end, 0)
        return self.__class__(self.data[start:end])

    def __add__(self, other):
        if isinstance(other, UserString):
            return self.__class__(self.data + other.data)
        elif isinstance(other, bytes):
            return self.__class__(self.data + other)
        else:
            return self.__class__(self.data + str(other).encode())

    def __radd__(self, other):
        if isinstance(other, bytes):
            return self.__class__(other + self.data)
        else:
            return self.__class__(str(other).encode() + self.data)

    def __mul__(self, n):
        return self.__class__(self.data * n)

    __rmul__ = __mul__

    def __mod__(self, args):
        return self.__class__(self.data % args)

    # the following methods are defined in alphabetical order:
    def capitalize(self):
        return self.__class__(self.data.capitalize())

    def center(self, width, *args):
        return self.__class__(self.data.center(width, *args))

    def count(self, sub, start=0, end=sys.maxsize):
        return self.data.count(sub, start, end)

    def decode(self, encoding=None, errors=None):  # XXX improve this?
        if encoding:
            if errors:
                return self.__class__(self.data.decode(encoding, errors))
            else:
                return self.__class__(self.data.decode(encoding))
        else:
            return self.__class__(self.data.decode())

    def encode(self, encoding=None, errors=None):  # XXX improve this?
        if encoding:
            if errors:
                return self.__class__(self.data.encode(encoding, errors))
            else:
                return self.__class__(self.data.encode(encoding))
        else:
            return self.__class__(self.data.encode())

    def endswith(self, suffix, start=0, end=sys.maxsize):
        return self.data.endswith(suffix, start, end)

    def expandtabs(self, tabsize=8):
        return self.__class__(self.data.expandtabs(tabsize))

    def find(self, sub, start=0, end=sys.maxsize):
        return self.data.find(sub, start, end)

    def index(self, sub, start=0, end=sys.maxsize):
        return self.data.index(sub, start, end)

    def isalpha(self):
        return self.data.isalpha()

    def isalnum(self):
        return self.data.isalnum()

    def isdecimal(self):
        return self.data.isdecimal()

    def isdigit(self):
        return self.data.isdigit()

    def islower(self):
        return self.data.islower()

    def isnumeric(self):
        return self.data.isnumeric()

    def isspace(self):
        return self.data.isspace()

    def istitle(self):
        return self.data.istitle()

    def isupper(self):
        return self.data.isupper()

    def join(self, seq):
        return self.data.join(seq)

    def ljust(self, width, *args):
        return self.__class__(self.data.ljust(width, *args))

    def lower(self):
        return self.__class__(self.data.lower())

    def lstrip(self, chars=None):
        return self.__class__(self.data.lstrip(chars))

    def partition(self, sep):
        return self.data.partition(sep)

    def replace(self, old, new, maxsplit=-1):
        return self.__class__(self.data.replace(old, new, maxsplit))

    def rfind(self, sub, start=0, end=sys.maxsize):
        return self.data.rfind(sub, start, end)

    def rindex(self, sub, start=0, end=sys.maxsize):
        return self.data.rindex(sub, start, end)

    def rjust(self, width, *args):
        return self.__class__(self.data.rjust(width, *args))

    def rpartition(self, sep):
        return self.data.rpartition(sep)

    def rstrip(self, chars=None):
        return self.__class__(self.data.rstrip(chars))

    def split(self, sep=None, maxsplit=-1):
        return self.data.split(sep, maxsplit)

    def rsplit(self, sep=None, maxsplit=-1):
        return self.data.rsplit(sep, maxsplit)

    def splitlines(self, keepends=0):
        return self.data.splitlines(keepends)

    def startswith(self, prefix, start=0, end=sys.maxsize):
        return self.data.startswith(prefix, start, end)

    def strip(self, chars=None):
        return self.__class__(self.data.strip(chars))

    def swapcase(self):
        return self.__class__(self.data.swapcase())

    def title(self):
        return self.__class__(self.data.title())

    def translate(self, *args):
        return self.__class__(self.data.translate(*args))

    def upper(self):
        return self.__class__(self.data.upper())

    def zfill(self, width):
        return self.__class__(self.data.zfill(width))


class MutableString(UserString):
    """mutable string objects

    Python strings are immutable objects.  This has the advantage, that
    strings may be used as dictionary keys.  If this property isn't needed
    and you insist on changing string values in place instead, you may cheat
    and use MutableString.

    But the purpose of this class is an educational one: to prevent
    people from inventing their own mutable string class derived
    from UserString and than forget thereby to remove (override) the
    __hash__ method inherited from UserString.  This would lead to
    errors that would be very hard to track down.

    A faster and better solution is to rewrite your program using lists."""

    def __init__(self, string=""):
        self.data = string

    def __hash__(self):
        raise TypeError("unhashable type (it is mutable)")

    def __setitem__(self, index, sub):
        if index < 0:
            index += len(self.data)
        if index < 0 or index >= len(self.data):
            raise IndexError
        self.data = self.data[:index] + sub + self.data[index + 1 :]

    def __delitem__(self, index):
        if index < 0:
            index += len(self.data)
        if index < 0 or index >= len(self.data):
            raise IndexError
        self.data = self.data[:index] + self.data[index + 1 :]

    def __setslice__(self, start, end, sub):
        start = max(start, 0)
        end = max(end, 0)
        if isinstance(sub, UserString):
            self.data = self.data[:start] + sub.data + self.data[end:]
        elif isinstance(sub, bytes):
            self.data = self.data[:start] + sub + self.data[end:]
        else:
            self.data = self.data[:start] + str(sub).encode() + self.data[end:]

    def __delslice__(self, start, end):
        start = max(start, 0)
        end = max(end, 0)
        self.data = self.data[:start] + self.data[end:]

    def immutable(self):
        return UserString(self.data)

    def __iadd__(self, other):
        if isinstance(other, UserString):
            self.data += other.data
        elif isinstance(other, bytes):
            self.data += other
        else:
            self.data += str(other).encode()
        return self

    def __imul__(self, n):
        self.data *= n
        return self


class String(MutableString, ctypes.Union):

    _fields_ = [("raw", ctypes.POINTER(ctypes.c_char)), ("data", ctypes.c_char_p)]

    def __init__(self, obj=b""):
        if isinstance(obj, (bytes, UserString)):
            self.data = bytes(obj)
        else:
            self.raw = obj

    def __len__(self):
        return self.data and len(self.data) or 0

    def from_param(cls, obj):
        # Convert None or 0
        if obj is None or obj == 0:
            return cls(ctypes.POINTER(ctypes.c_char)())

        # Convert from String
        elif isinstance(obj, String):
            return obj

        # Convert from bytes
        elif isinstance(obj, bytes):
            return cls(obj)

        # Convert from str
        elif isinstance(obj, str):
            return cls(obj.encode())

        # Convert from c_char_p
        elif isinstance(obj, ctypes.c_char_p):
            return obj

        # Convert from POINTER(ctypes.c_char)
        elif isinstance(obj, ctypes.POINTER(ctypes.c_char)):
            return obj

        # Convert from raw pointer
        elif isinstance(obj, int):
            return cls(ctypes.cast(obj, ctypes.POINTER(ctypes.c_char)))

        # Convert from ctypes.c_char array
        elif isinstance(obj, ctypes.c_char * len(obj)):
            return obj

        # Convert from object
        else:
            return String.from_param(obj._as_parameter_)

    from_param = classmethod(from_param)


def ReturnString(obj, func=None, arguments=None):
    return String.from_param(obj)


# As of ctypes 1.0, ctypes does not support custom error-checking
# functions on callbacks, nor does it support custom datatypes on
# callbacks, so we must ensure that all callbacks return
# primitive datatypes.
#
# Non-primitive return values wrapped with UNCHECKED won't be
# typechecked, and will be converted to ctypes.c_void_p.
def UNCHECKED(type):
    if hasattr(type, "_type_") and isinstance(type._type_, str) and type._type_ != "P":
        return type
    else:
        return ctypes.c_void_p


# ctypes doesn't have direct support for variadic functions, so we have to write
# our own wrapper class
class _variadic_function(object):
    def __init__(self, func, restype, argtypes, errcheck):
        self.func = func
        self.func.restype = restype
        self.argtypes = argtypes
        if errcheck:
            self.func.errcheck = errcheck

    def _as_parameter_(self):
        # So we can pass this variadic function as a function pointer
        return self.func

    def __call__(self, *args):
        fixed_args = []
        i = 0
        for argtype in self.argtypes:
            # Typecheck what we can
            fixed_args.append(argtype.from_param(args[i]))
            i += 1
        return self.func(*fixed_args + list(args[i:]))


def ord_if_char(value):
    """
    Simple helper used for casts to simple builtin types:  if the argument is a
    string type, it will be converted to it's ordinal value.

    This function will raise an exception if the argument is string with more
    than one characters.
    """
    return ord(value) if (isinstance(value, bytes) or isinstance(value, str)) else value

# End preamble

_libs = {}
_libdirs = []

# Begin loader

"""
Load libraries - appropriately for all our supported platforms
"""
# ----------------------------------------------------------------------------
# Copyright (c) 2008 David James
# Copyright (c) 2006-2008 Alex Holkner
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#  * Neither the name of pyglet nor the names of its
#    contributors may be used to endorse or promote products
#    derived from this software without specific prior written
#    permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
# ----------------------------------------------------------------------------

import ctypes
import ctypes.util
import glob
import os.path
import platform
import re
import sys


def _environ_path(name):
    """Split an environment variable into a path-like list elements"""
    if name in os.environ:
        return os.environ[name].split(":")
    return []


class LibraryLoader:
    """
    A base class For loading of libraries ;-)
    Subclasses load libraries for specific platforms.
    """

    # library names formatted specifically for platforms
    name_formats = ["%s"]

    class Lookup:
        """Looking up calling conventions for a platform"""

        mode = ctypes.DEFAULT_MODE

        def __init__(self, path):
            super(LibraryLoader.Lookup, self).__init__()
            self.access = dict(cdecl=ctypes.CDLL(path, self.mode))

        def get(self, name, calling_convention="cdecl"):
            """Return the given name according to the selected calling convention"""
            if calling_convention not in self.access:
                raise LookupError(
                    "Unknown calling convention '{}' for function '{}'".format(
                        calling_convention, name
                    )
                )
            return getattr(self.access[calling_convention], name)

        def has(self, name, calling_convention="cdecl"):
            """Return True if this given calling convention finds the given 'name'"""
            if calling_convention not in self.access:
                return False
            return hasattr(self.access[calling_convention], name)

        def __getattr__(self, name):
            return getattr(self.access["cdecl"], name)

    def __init__(self):
        self.other_dirs = []

    def __call__(self, libname):
        """Given the name of a library, load it."""
        paths = self.getpaths(libname)

        for path in paths:
            # noinspection PyBroadException
            try:
                return self.Lookup(path)
            except Exception:  # pylint: disable=broad-except
                pass

        raise ImportError("Could not load %s." % libname)

    def getpaths(self, libname):
        """Return a list of paths where the library might be found."""
        if os.path.isabs(libname):
            yield libname
        else:
            # search through a prioritized series of locations for the library

            # we first search any specific directories identified by user
            for dir_i in self.other_dirs:
                for fmt in self.name_formats:
                    # dir_i should be absolute already
                    yield os.path.join(dir_i, fmt % libname)

            # check if this code is even stored in a physical file
            try:
                this_file = __file__
            except NameError:
                this_file = None

            # then we search the directory where the generated python interface is stored
            if this_file is not None:
                for fmt in self.name_formats:
                    yield os.path.abspath(os.path.join(os.path.dirname(__file__), fmt % libname))

            # now, use the ctypes tools to try to find the library
            for fmt in self.name_formats:
                path = ctypes.util.find_library(fmt % libname)
                if path:
                    yield path

            # then we search all paths identified as platform-specific lib paths
            for path in self.getplatformpaths(libname):
                yield path

            # Finally, we'll try the users current working directory
            for fmt in self.name_formats:
                yield os.path.abspath(os.path.join(os.path.curdir, fmt % libname))

    def getplatformpaths(self, _libname):  # pylint: disable=no-self-use
        """Return all the library paths available in this platform"""
        return []


# Darwin (Mac OS X)


class DarwinLibraryLoader(LibraryLoader):
    """Library loader for MacOS"""

    name_formats = [
        "lib%s.dylib",
        "lib%s.so",
        "lib%s.bundle",
        "%s.dylib",
        "%s.so",
        "%s.bundle",
        "%s",
    ]

    class Lookup(LibraryLoader.Lookup):
        """
        Looking up library files for this platform (Darwin aka MacOS)
        """

        # Darwin requires dlopen to be called with mode RTLD_GLOBAL instead
        # of the default RTLD_LOCAL.  Without this, you end up with
        # libraries not being loadable, resulting in "Symbol not found"
        # errors
        mode = ctypes.RTLD_GLOBAL

    def getplatformpaths(self, libname):
        if os.path.pathsep in libname:
            names = [libname]
        else:
            names = [fmt % libname for fmt in self.name_formats]

        for directory in self.getdirs(libname):
            for name in names:
                yield os.path.join(directory, name)

    @staticmethod
    def getdirs(libname):
        """Implements the dylib search as specified in Apple documentation:

        http://developer.apple.com/documentation/DeveloperTools/Conceptual/
            DynamicLibraries/Articles/DynamicLibraryUsageGuidelines.html

        Before commencing the standard search, the method first checks
        the bundle's ``Frameworks`` directory if the application is running
        within a bundle (OS X .app).
        """

        dyld_fallback_library_path = _environ_path("DYLD_FALLBACK_LIBRARY_PATH")
        if not dyld_fallback_library_path:
            dyld_fallback_library_path = [
                os.path.expanduser("~/lib"),
                "/usr/local/lib",
                "/usr/lib",
            ]

        dirs = []

        if "/" in libname:
            dirs.extend(_environ_path("DYLD_LIBRARY_PATH"))
        else:
            dirs.extend(_environ_path("LD_LIBRARY_PATH"))
            dirs.extend(_environ_path("DYLD_LIBRARY_PATH"))
            dirs.extend(_environ_path("LD_RUN_PATH"))

        if hasattr(sys, "frozen") and getattr(sys, "frozen") == "macosx_app":
            dirs.append(os.path.join(os.environ["RESOURCEPATH"], "..", "Frameworks"))

        dirs.extend(dyld_fallback_library_path)

        return dirs


# Posix


class PosixLibraryLoader(LibraryLoader):
    """Library loader for POSIX-like systems (including Linux)"""

    _ld_so_cache = None

    _include = re.compile(r"^\s*include\s+(?P<pattern>.*)")

    name_formats = ["lib%s.so", "%s.so", "%s"]

    class _Directories(dict):
        """Deal with directories"""

        def __init__(self):
            dict.__init__(self)
            self.order = 0

        def add(self, directory):
            """Add a directory to our current set of directories"""
            if len(directory) > 1:
                directory = directory.rstrip(os.path.sep)
            # only adds and updates order if exists and not already in set
            if not os.path.exists(directory):
                return
            order = self.setdefault(directory, self.order)
            if order == self.order:
                self.order += 1

        def extend(self, directories):
            """Add a list of directories to our set"""
            for a_dir in directories:
                self.add(a_dir)

        def ordered(self):
            """Sort the list of directories"""
            return (i[0] for i in sorted(self.items(), key=lambda d: d[1]))

    def _get_ld_so_conf_dirs(self, conf, dirs):
        """
        Recursive function to help parse all ld.so.conf files, including proper
        handling of the `include` directive.
        """

        try:
            with open(conf) as fileobj:
                for dirname in fileobj:
                    dirname = dirname.strip()
                    if not dirname:
                        continue

                    match = self._include.match(dirname)
                    if not match:
                        dirs.add(dirname)
                    else:
                        for dir2 in glob.glob(match.group("pattern")):
                            self._get_ld_so_conf_dirs(dir2, dirs)
        except IOError:
            pass

    def _create_ld_so_cache(self):
        # Recreate search path followed by ld.so.  This is going to be
        # slow to build, and incorrect (ld.so uses ld.so.cache, which may
        # not be up-to-date).  Used only as fallback for distros without
        # /sbin/ldconfig.
        #
        # We assume the DT_RPATH and DT_RUNPATH binary sections are omitted.

        directories = self._Directories()
        for name in (
            "LD_LIBRARY_PATH",
            "SHLIB_PATH",  # HP-UX
            "LIBPATH",  # OS/2, AIX
            "LIBRARY_PATH",  # BE/OS
        ):
            if name in os.environ:
                directories.extend(os.environ[name].split(os.pathsep))

        self._get_ld_so_conf_dirs("/etc/ld.so.conf", directories)

        bitage = platform.architecture()[0]

        unix_lib_dirs_list = []
        if bitage.startswith("64"):
            # prefer 64 bit if that is our arch
            unix_lib_dirs_list += ["/lib64", "/usr/lib64"]

        # must include standard libs, since those paths are also used by 64 bit
        # installs
        unix_lib_dirs_list += ["/lib", "/usr/lib"]
        if sys.platform.startswith("linux"):
            # Try and support multiarch work in Ubuntu
            # https://wiki.ubuntu.com/MultiarchSpec
            if bitage.startswith("32"):
                # Assume Intel/AMD x86 compat
                unix_lib_dirs_list += ["/lib/i386-linux-gnu", "/usr/lib/i386-linux-gnu"]
            elif bitage.startswith("64"):
                # Assume Intel/AMD x86 compatible
                unix_lib_dirs_list += [
                    "/lib/x86_64-linux-gnu",
                    "/usr/lib/x86_64-linux-gnu",
                ]
            else:
                # guess...
                unix_lib_dirs_list += glob.glob("/lib/*linux-gnu")
        directories.extend(unix_lib_dirs_list)

        cache = {}
        lib_re = re.compile(r"lib(.*)\.s[ol]")
        # ext_re = re.compile(r"\.s[ol]$")
        for our_dir in directories.ordered():
            try:
                for path in glob.glob("%s/*.s[ol]*" % our_dir):
                    file = os.path.basename(path)

                    # Index by filename
                    cache_i = cache.setdefault(file, set())
                    cache_i.add(path)

                    # Index by library name
                    match = lib_re.match(file)
                    if match:
                        library = match.group(1)
                        cache_i = cache.setdefault(library, set())
                        cache_i.add(path)
            except OSError:
                pass

        self._ld_so_cache = cache

    def getplatformpaths(self, libname):
        if self._ld_so_cache is None:
            self._create_ld_so_cache()

        result = self._ld_so_cache.get(libname, set())
        for i in result:
            # we iterate through all found paths for library, since we may have
            # actually found multiple architectures or other library types that
            # may not load
            yield i


# Windows


class WindowsLibraryLoader(LibraryLoader):
    """Library loader for Microsoft Windows"""

    name_formats = ["%s.dll", "lib%s.dll", "%slib.dll", "%s"]

    class Lookup(LibraryLoader.Lookup):
        """Lookup class for Windows libraries..."""

        def __init__(self, path):
            super(WindowsLibraryLoader.Lookup, self).__init__(path)
            self.access["stdcall"] = ctypes.windll.LoadLibrary(path)


# Platform switching

# If your value of sys.platform does not appear in this dict, please contact
# the Ctypesgen maintainers.

loaderclass = {
    "darwin": DarwinLibraryLoader,
    "cygwin": WindowsLibraryLoader,
    "win32": WindowsLibraryLoader,
    "msys": WindowsLibraryLoader,
}

load_library = loaderclass.get(sys.platform, PosixLibraryLoader)()


def add_library_search_dirs(other_dirs):
    """
    Add libraries to search paths.
    If library paths are relative, convert them to absolute with respect to this
    file's directory
    """
    for path in other_dirs:
        if not os.path.isabs(path):
            path = os.path.abspath(path)
        load_library.other_dirs.append(path)


del loaderclass

# End loader

add_library_search_dirs([])

# Begin libraries
_libs["digHolo.dll"] = load_library("digHolo.dll")

# 1 libraries
# End libraries

# No modules

complex64 = c_float * int(2)# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 163

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 209
for _lib in _libs.values():
    if not _lib.has("digHoloCreate", "cdecl"):
        continue
    digHoloCreate = _lib.get("digHoloCreate", "cdecl")
    digHoloCreate.argtypes = []
    digHoloCreate.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 216
for _lib in _libs.values():
    if not _lib.has("digHoloDestroy", "cdecl"):
        continue
    digHoloDestroy = _lib.get("digHoloDestroy", "cdecl")
    digHoloDestroy.argtypes = [c_int]
    digHoloDestroy.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 245
for _lib in _libs.values():
    if not _lib.has("digHoloSetFrameBuffer", "cdecl"):
        continue
    digHoloSetFrameBuffer = _lib.get("digHoloSetFrameBuffer", "cdecl")
    digHoloSetFrameBuffer.argtypes = [c_int, POINTER(c_float)]
    digHoloSetFrameBuffer.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 255
for _lib in _libs.values():
    if not _lib.has("digHoloGetFrameBuffer", "cdecl"):
        continue
    digHoloGetFrameBuffer = _lib.get("digHoloGetFrameBuffer", "cdecl")
    digHoloGetFrameBuffer.argtypes = [c_int]
    digHoloGetFrameBuffer.restype = POINTER(c_float)
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 268
for _lib in _libs.values():
    if not _lib.has("digHoloSetFrameBufferUint16", "cdecl"):
        continue
    digHoloSetFrameBufferUint16 = _lib.get("digHoloSetFrameBufferUint16", "cdecl")
    digHoloSetFrameBufferUint16.argtypes = [c_int, POINTER(c_ushort), c_int]
    digHoloSetFrameBufferUint16.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 277
for _lib in _libs.values():
    if not _lib.has("digHoloGetFrameBufferUint16", "cdecl"):
        continue
    digHoloGetFrameBufferUint16 = _lib.get("digHoloGetFrameBufferUint16", "cdecl")
    digHoloGetFrameBufferUint16.argtypes = [c_int, POINTER(c_int)]
    digHoloGetFrameBufferUint16.restype = POINTER(c_ushort)
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 288
for _lib in _libs.values():
    if not _lib.has("digHoloSetFrameBufferFromFile", "cdecl"):
        continue
    digHoloSetFrameBufferFromFile = _lib.get("digHoloSetFrameBufferFromFile", "cdecl")
    digHoloSetFrameBufferFromFile.argtypes = [c_int, String]
    digHoloSetFrameBufferFromFile.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 298
for _lib in _libs.values():
    if not _lib.has("digHoloConfigSetFrameDimensions", "cdecl"):
        continue
    digHoloConfigSetFrameDimensions = _lib.get("digHoloConfigSetFrameDimensions", "cdecl")
    digHoloConfigSetFrameDimensions.argtypes = [c_int, c_int, c_int]
    digHoloConfigSetFrameDimensions.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 308
for _lib in _libs.values():
    if not _lib.has("digHoloConfigGetFrameDimensions", "cdecl"):
        continue
    digHoloConfigGetFrameDimensions = _lib.get("digHoloConfigGetFrameDimensions", "cdecl")
    digHoloConfigGetFrameDimensions.argtypes = [c_int, POINTER(c_int), POINTER(c_int)]
    digHoloConfigGetFrameDimensions.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 317
for _lib in _libs.values():
    if not _lib.has("digHoloConfigSetFramePixelSize", "cdecl"):
        continue
    digHoloConfigSetFramePixelSize = _lib.get("digHoloConfigSetFramePixelSize", "cdecl")
    digHoloConfigSetFramePixelSize.argtypes = [c_int, c_float]
    digHoloConfigSetFramePixelSize.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 325
for _lib in _libs.values():
    if not _lib.has("digHoloConfigGetFramePixelSize", "cdecl"):
        continue
    digHoloConfigGetFramePixelSize = _lib.get("digHoloConfigGetFramePixelSize", "cdecl")
    digHoloConfigGetFramePixelSize.argtypes = [c_int]
    digHoloConfigGetFramePixelSize.restype = c_float
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 334
for _lib in _libs.values():
    if not _lib.has("digHoloConfigSetPolCount", "cdecl"):
        continue
    digHoloConfigSetPolCount = _lib.get("digHoloConfigSetPolCount", "cdecl")
    digHoloConfigSetPolCount.argtypes = [c_int, c_int]
    digHoloConfigSetPolCount.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 344
for _lib in _libs.values():
    if not _lib.has("digHoloConfigGetPolCount", "cdecl"):
        continue
    digHoloConfigGetPolCount = _lib.get("digHoloConfigGetPolCount", "cdecl")
    digHoloConfigGetPolCount.argtypes = [c_int]
    digHoloConfigGetPolCount.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 369
for _lib in _libs.values():
    if not _lib.has("digHoloConfigSetRefCalibrationIntensity", "cdecl"):
        continue
    digHoloConfigSetRefCalibrationIntensity = _lib.get("digHoloConfigSetRefCalibrationIntensity", "cdecl")
    digHoloConfigSetRefCalibrationIntensity.argtypes = [c_int, POINTER(c_ushort), c_int, c_int, c_int]
    digHoloConfigSetRefCalibrationIntensity.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 384
for _lib in _libs.values():
    if not _lib.has("digHoloConfigSetRefCalibrationField", "cdecl"):
        continue
    digHoloConfigSetRefCalibrationField = _lib.get("digHoloConfigSetRefCalibrationField", "cdecl")
    digHoloConfigSetRefCalibrationField.argtypes = [c_int, POINTER(complex64), c_int, c_int, c_int]
    digHoloConfigSetRefCalibrationField.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 400
for _lib in _libs.values():
    if not _lib.has("digHoloConfigSetRefCalibrationFromFile", "cdecl"):
        continue
    digHoloConfigSetRefCalibrationFromFile = _lib.get("digHoloConfigSetRefCalibrationFromFile", "cdecl")
    digHoloConfigSetRefCalibrationFromFile.argtypes = [c_int, String, c_int, c_int, c_int]
    digHoloConfigSetRefCalibrationFromFile.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 409
for _lib in _libs.values():
    if not _lib.has("digHoloConfigSetRefCalibrationEnabled", "cdecl"):
        continue
    digHoloConfigSetRefCalibrationEnabled = _lib.get("digHoloConfigSetRefCalibrationEnabled", "cdecl")
    digHoloConfigSetRefCalibrationEnabled.argtypes = [c_int, c_int]
    digHoloConfigSetRefCalibrationEnabled.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 417
for _lib in _libs.values():
    if not _lib.has("digHoloConfigGetRefCalibrationEnabled", "cdecl"):
        continue
    digHoloConfigGetRefCalibrationEnabled = _lib.get("digHoloConfigGetRefCalibrationEnabled", "cdecl")
    digHoloConfigGetRefCalibrationEnabled.argtypes = [c_int]
    digHoloConfigGetRefCalibrationEnabled.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 437
for _lib in _libs.values():
    if not _lib.has("digHoloConfigGetRefCalibrationFields", "cdecl"):
        continue
    digHoloConfigGetRefCalibrationFields = _lib.get("digHoloConfigGetRefCalibrationFields", "cdecl")
    digHoloConfigGetRefCalibrationFields.argtypes = [c_int, POINTER(c_int), POINTER(c_int), POINTER(POINTER(c_float)), POINTER(POINTER(c_float)), POINTER(c_int), POINTER(c_int)]
    digHoloConfigGetRefCalibrationFields.restype = POINTER(complex64)
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 449
for _lib in _libs.values():
    if not _lib.has("digHoloConfigSetFillFactorCorrectionEnabled", "cdecl"):
        continue
    digHoloConfigSetFillFactorCorrectionEnabled = _lib.get("digHoloConfigSetFillFactorCorrectionEnabled", "cdecl")
    digHoloConfigSetFillFactorCorrectionEnabled.argtypes = [c_int, c_int]
    digHoloConfigSetFillFactorCorrectionEnabled.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 460
for _lib in _libs.values():
    if not _lib.has("digHoloConfigGetFillFactorCorrectionEnabled", "cdecl"):
        continue
    digHoloConfigGetFillFactorCorrectionEnabled = _lib.get("digHoloConfigGetFillFactorCorrectionEnabled", "cdecl")
    digHoloConfigGetFillFactorCorrectionEnabled.argtypes = [c_int]
    digHoloConfigGetFillFactorCorrectionEnabled.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 483
for _lib in _libs.values():
    if not _lib.has("digHoloSetBatch", "cdecl"):
        continue
    digHoloSetBatch = _lib.get("digHoloSetBatch", "cdecl")
    digHoloSetBatch.argtypes = [c_int, c_int, POINTER(c_float)]
    digHoloSetBatch.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 502
for _lib in _libs.values():
    if not _lib.has("digHoloSetBatchAvg", "cdecl"):
        continue
    digHoloSetBatchAvg = _lib.get("digHoloSetBatchAvg", "cdecl")
    digHoloSetBatchAvg.argtypes = [c_int, c_int, POINTER(c_float), c_int, c_int]
    digHoloSetBatchAvg.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 519
for _lib in _libs.values():
    if not _lib.has("digHoloSetBatchUint16", "cdecl"):
        continue
    digHoloSetBatchUint16 = _lib.get("digHoloSetBatchUint16", "cdecl")
    digHoloSetBatchUint16.argtypes = [c_int, c_int, POINTER(c_ushort), c_int]
    digHoloSetBatchUint16.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 540
for _lib in _libs.values():
    if not _lib.has("digHoloSetBatchAvgUint16", "cdecl"):
        continue
    digHoloSetBatchAvgUint16 = _lib.get("digHoloSetBatchAvgUint16", "cdecl")
    digHoloSetBatchAvgUint16.argtypes = [c_int, c_int, POINTER(c_ushort), c_int, c_int, c_int]
    digHoloSetBatchAvgUint16.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 551
for _lib in _libs.values():
    if not _lib.has("digHoloConfigSetBatchCount", "cdecl"):
        continue
    digHoloConfigSetBatchCount = _lib.get("digHoloConfigSetBatchCount", "cdecl")
    digHoloConfigSetBatchCount.argtypes = [c_int, c_int]
    digHoloConfigSetBatchCount.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 559
for _lib in _libs.values():
    if not _lib.has("digHoloConfigGetBatchCount", "cdecl"):
        continue
    digHoloConfigGetBatchCount = _lib.get("digHoloConfigGetBatchCount", "cdecl")
    digHoloConfigGetBatchCount.argtypes = [c_int]
    digHoloConfigGetBatchCount.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 570
for _lib in _libs.values():
    if not _lib.has("digHoloConfigSetBatchAvgCount", "cdecl"):
        continue
    digHoloConfigSetBatchAvgCount = _lib.get("digHoloConfigSetBatchAvgCount", "cdecl")
    digHoloConfigSetBatchAvgCount.argtypes = [c_int, c_int]
    digHoloConfigSetBatchAvgCount.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 580
for _lib in _libs.values():
    if not _lib.has("digHoloConfigGetBatchAvgCount", "cdecl"):
        continue
    digHoloConfigGetBatchAvgCount = _lib.get("digHoloConfigGetBatchAvgCount", "cdecl")
    digHoloConfigGetBatchAvgCount.argtypes = [c_int]
    digHoloConfigGetBatchAvgCount.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 599
for _lib in _libs.values():
    if not _lib.has("digHoloConfigSetBatchCalibration", "cdecl"):
        continue
    digHoloConfigSetBatchCalibration = _lib.get("digHoloConfigSetBatchCalibration", "cdecl")
    digHoloConfigSetBatchCalibration.argtypes = [c_int, POINTER(complex64), c_int, c_int]
    digHoloConfigSetBatchCalibration.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 611
for _lib in _libs.values():
    if not _lib.has("digHoloConfigGetBatchCalibration", "cdecl"):
        continue
    digHoloConfigGetBatchCalibration = _lib.get("digHoloConfigGetBatchCalibration", "cdecl")
    digHoloConfigGetBatchCalibration.argtypes = [c_int, POINTER(c_int), POINTER(c_int)]
    digHoloConfigGetBatchCalibration.restype = POINTER(complex64)
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 624
for _lib in _libs.values():
    if not _lib.has("digHoloConfigSetBatchCalibrationFromFile", "cdecl"):
        continue
    digHoloConfigSetBatchCalibrationFromFile = _lib.get("digHoloConfigSetBatchCalibrationFromFile", "cdecl")
    digHoloConfigSetBatchCalibrationFromFile.argtypes = [c_int, String, c_int, c_int]
    digHoloConfigSetBatchCalibrationFromFile.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 635
for _lib in _libs.values():
    if not _lib.has("digHoloConfigSetBatchCalibrationEnabled", "cdecl"):
        continue
    digHoloConfigSetBatchCalibrationEnabled = _lib.get("digHoloConfigSetBatchCalibrationEnabled", "cdecl")
    digHoloConfigSetBatchCalibrationEnabled.argtypes = [c_int, c_int]
    digHoloConfigSetBatchCalibrationEnabled.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 645
for _lib in _libs.values():
    if not _lib.has("digHoloConfigGetBatchCalibrationEnabled", "cdecl"):
        continue
    digHoloConfigGetBatchCalibrationEnabled = _lib.get("digHoloConfigGetBatchCalibrationEnabled", "cdecl")
    digHoloConfigGetBatchCalibrationEnabled.argtypes = [c_int]
    digHoloConfigGetBatchCalibrationEnabled.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 670
for _lib in _libs.values():
    if not _lib.has("digHoloConfigSetBatchAvgMode", "cdecl"):
        continue
    digHoloConfigSetBatchAvgMode = _lib.get("digHoloConfigSetBatchAvgMode", "cdecl")
    digHoloConfigSetBatchAvgMode.argtypes = [c_int, c_int]
    digHoloConfigSetBatchAvgMode.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 680
for _lib in _libs.values():
    if not _lib.has("digHoloConfigGetBatchAvgMode", "cdecl"):
        continue
    digHoloConfigGetBatchAvgMode = _lib.get("digHoloConfigGetBatchAvgMode", "cdecl")
    digHoloConfigGetBatchAvgMode.argtypes = [c_int]
    digHoloConfigGetBatchAvgMode.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 701
for _lib in _libs.values():
    if not _lib.has("digHoloConfigSetfftWindowSize", "cdecl"):
        continue
    digHoloConfigSetfftWindowSize = _lib.get("digHoloConfigSetfftWindowSize", "cdecl")
    digHoloConfigSetfftWindowSize.argtypes = [c_int, c_int, c_int]
    digHoloConfigSetfftWindowSize.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 712
for _lib in _libs.values():
    if not _lib.has("digHoloConfigGetfftWindowSize", "cdecl"):
        continue
    digHoloConfigGetfftWindowSize = _lib.get("digHoloConfigGetfftWindowSize", "cdecl")
    digHoloConfigGetfftWindowSize.argtypes = [c_int, POINTER(c_int), POINTER(c_int)]
    digHoloConfigGetfftWindowSize.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 722
for _lib in _libs.values():
    if not _lib.has("digHoloConfigSetfftWindowSizeX", "cdecl"):
        continue
    digHoloConfigSetfftWindowSizeX = _lib.get("digHoloConfigSetfftWindowSizeX", "cdecl")
    digHoloConfigSetfftWindowSizeX.argtypes = [c_int, c_int]
    digHoloConfigSetfftWindowSizeX.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 730
for _lib in _libs.values():
    if not _lib.has("digHoloConfigGetfftWindowSizeX", "cdecl"):
        continue
    digHoloConfigGetfftWindowSizeX = _lib.get("digHoloConfigGetfftWindowSizeX", "cdecl")
    digHoloConfigGetfftWindowSizeX.argtypes = [c_int]
    digHoloConfigGetfftWindowSizeX.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 739
for _lib in _libs.values():
    if not _lib.has("digHoloConfigGetfftWindowSizeY", "cdecl"):
        continue
    digHoloConfigGetfftWindowSizeY = _lib.get("digHoloConfigGetfftWindowSizeY", "cdecl")
    digHoloConfigGetfftWindowSizeY.argtypes = [c_int]
    digHoloConfigGetfftWindowSizeY.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 749
for _lib in _libs.values():
    if not _lib.has("digHoloConfigSetfftWindowSizeY", "cdecl"):
        continue
    digHoloConfigSetfftWindowSizeY = _lib.get("digHoloConfigSetfftWindowSizeY", "cdecl")
    digHoloConfigSetfftWindowSizeY.argtypes = [c_int, c_int]
    digHoloConfigSetfftWindowSizeY.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 766
for _lib in _libs.values():
    if not _lib.has("digHoloConfigSetFourierWindowRadius", "cdecl"):
        continue
    digHoloConfigSetFourierWindowRadius = _lib.get("digHoloConfigSetFourierWindowRadius", "cdecl")
    digHoloConfigSetFourierWindowRadius.argtypes = [c_int, c_float]
    digHoloConfigSetFourierWindowRadius.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 774
for _lib in _libs.values():
    if not _lib.has("digHoloConfigGetFourierWindowRadius", "cdecl"):
        continue
    digHoloConfigGetFourierWindowRadius = _lib.get("digHoloConfigGetFourierWindowRadius", "cdecl")
    digHoloConfigGetFourierWindowRadius.argtypes = [c_int]
    digHoloConfigGetFourierWindowRadius.restype = c_float
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 786
for _lib in _libs.values():
    if not _lib.has("digHoloConfigSetIFFTResolutionMode", "cdecl"):
        continue
    digHoloConfigSetIFFTResolutionMode = _lib.get("digHoloConfigSetIFFTResolutionMode", "cdecl")
    digHoloConfigSetIFFTResolutionMode.argtypes = [c_int, c_int]
    digHoloConfigSetIFFTResolutionMode.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 797
for _lib in _libs.values():
    if not _lib.has("digHoloConfigGetIFFTResolutionMode", "cdecl"):
        continue
    digHoloConfigGetIFFTResolutionMode = _lib.get("digHoloConfigGetIFFTResolutionMode", "cdecl")
    digHoloConfigGetIFFTResolutionMode.argtypes = [c_int]
    digHoloConfigGetIFFTResolutionMode.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 814
for _lib in _libs.values():
    if not _lib.has("digHoloConfigSetWavelengthCentre", "cdecl"):
        continue
    digHoloConfigSetWavelengthCentre = _lib.get("digHoloConfigSetWavelengthCentre", "cdecl")
    digHoloConfigSetWavelengthCentre.argtypes = [c_int, c_float]
    digHoloConfigSetWavelengthCentre.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 822
for _lib in _libs.values():
    if not _lib.has("digHoloConfigGetWavelengthCentre", "cdecl"):
        continue
    digHoloConfigGetWavelengthCentre = _lib.get("digHoloConfigGetWavelengthCentre", "cdecl")
    digHoloConfigGetWavelengthCentre.argtypes = [c_int]
    digHoloConfigGetWavelengthCentre.restype = c_float
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 832
for _lib in _libs.values():
    if not _lib.has("digHoloConfigSetWavelengths", "cdecl"):
        continue
    digHoloConfigSetWavelengths = _lib.get("digHoloConfigSetWavelengths", "cdecl")
    digHoloConfigSetWavelengths.argtypes = [c_int, POINTER(c_float), c_int]
    digHoloConfigSetWavelengths.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 843
for _lib in _libs.values():
    if not _lib.has("digHoloConfigSetWavelengthsLinearFrequency", "cdecl"):
        continue
    digHoloConfigSetWavelengthsLinearFrequency = _lib.get("digHoloConfigSetWavelengthsLinearFrequency", "cdecl")
    digHoloConfigSetWavelengthsLinearFrequency.argtypes = [c_int, c_float, c_float, c_int]
    digHoloConfigSetWavelengthsLinearFrequency.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 854
for _lib in _libs.values():
    if not _lib.has("digHoloConfigGetWavelengths", "cdecl"):
        continue
    digHoloConfigGetWavelengths = _lib.get("digHoloConfigGetWavelengths", "cdecl")
    digHoloConfigGetWavelengths.argtypes = [c_int, POINTER(c_int)]
    digHoloConfigGetWavelengths.restype = POINTER(c_float)
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 886
for _lib in _libs.values():
    if not _lib.has("digHoloConfigSetWavelengthOrdering", "cdecl"):
        continue
    digHoloConfigSetWavelengthOrdering = _lib.get("digHoloConfigSetWavelengthOrdering", "cdecl")
    digHoloConfigSetWavelengthOrdering.argtypes = [c_int, c_int, c_int]
    digHoloConfigSetWavelengthOrdering.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 895
for _lib in _libs.values():
    if not _lib.has("digHoloConfigGetWavelengthOrdering", "cdecl"):
        continue
    digHoloConfigGetWavelengthOrdering = _lib.get("digHoloConfigGetWavelengthOrdering", "cdecl")
    digHoloConfigGetWavelengthOrdering.argtypes = [c_int, c_int]
    digHoloConfigGetWavelengthOrdering.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 938
for _lib in _libs.values():
    if not _lib.has("digHoloConfigSetAutoAlignBeamCentre", "cdecl"):
        continue
    digHoloConfigSetAutoAlignBeamCentre = _lib.get("digHoloConfigSetAutoAlignBeamCentre", "cdecl")
    digHoloConfigSetAutoAlignBeamCentre.argtypes = [c_int, c_int]
    digHoloConfigSetAutoAlignBeamCentre.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 946
for _lib in _libs.values():
    if not _lib.has("digHoloConfigGetAutoAlignBeamCentre", "cdecl"):
        continue
    digHoloConfigGetAutoAlignBeamCentre = _lib.get("digHoloConfigGetAutoAlignBeamCentre", "cdecl")
    digHoloConfigGetAutoAlignBeamCentre.argtypes = [c_int]
    digHoloConfigGetAutoAlignBeamCentre.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 955
for _lib in _libs.values():
    if not _lib.has("digHoloConfigSetAutoAlignDefocus", "cdecl"):
        continue
    digHoloConfigSetAutoAlignDefocus = _lib.get("digHoloConfigSetAutoAlignDefocus", "cdecl")
    digHoloConfigSetAutoAlignDefocus.argtypes = [c_int, c_int]
    digHoloConfigSetAutoAlignDefocus.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 963
for _lib in _libs.values():
    if not _lib.has("digHoloConfigGetAutoAlignDefocus", "cdecl"):
        continue
    digHoloConfigGetAutoAlignDefocus = _lib.get("digHoloConfigGetAutoAlignDefocus", "cdecl")
    digHoloConfigGetAutoAlignDefocus.argtypes = [c_int]
    digHoloConfigGetAutoAlignDefocus.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 972
for _lib in _libs.values():
    if not _lib.has("digHoloConfigSetAutoAlignTilt", "cdecl"):
        continue
    digHoloConfigSetAutoAlignTilt = _lib.get("digHoloConfigSetAutoAlignTilt", "cdecl")
    digHoloConfigSetAutoAlignTilt.argtypes = [c_int, c_int]
    digHoloConfigSetAutoAlignTilt.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 980
for _lib in _libs.values():
    if not _lib.has("digHoloConfigGetAutoAlignTilt", "cdecl"):
        continue
    digHoloConfigGetAutoAlignTilt = _lib.get("digHoloConfigGetAutoAlignTilt", "cdecl")
    digHoloConfigGetAutoAlignTilt.argtypes = [c_int]
    digHoloConfigGetAutoAlignTilt.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 989
for _lib in _libs.values():
    if not _lib.has("digHoloConfigSetAutoAlignBasisWaist", "cdecl"):
        continue
    digHoloConfigSetAutoAlignBasisWaist = _lib.get("digHoloConfigSetAutoAlignBasisWaist", "cdecl")
    digHoloConfigSetAutoAlignBasisWaist.argtypes = [c_int, c_int]
    digHoloConfigSetAutoAlignBasisWaist.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 997
for _lib in _libs.values():
    if not _lib.has("digHoloConfigGetAutoAlignBasisWaist", "cdecl"):
        continue
    digHoloConfigGetAutoAlignBasisWaist = _lib.get("digHoloConfigGetAutoAlignBasisWaist", "cdecl")
    digHoloConfigGetAutoAlignBasisWaist.argtypes = [c_int]
    digHoloConfigGetAutoAlignBasisWaist.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1008
for _lib in _libs.values():
    if not _lib.has("digHoloConfigSetAutoAlignFourierWindowRadius", "cdecl"):
        continue
    digHoloConfigSetAutoAlignFourierWindowRadius = _lib.get("digHoloConfigSetAutoAlignFourierWindowRadius", "cdecl")
    digHoloConfigSetAutoAlignFourierWindowRadius.argtypes = [c_int, c_int]
    digHoloConfigSetAutoAlignFourierWindowRadius.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1016
for _lib in _libs.values():
    if not _lib.has("digHoloConfigGetAutoAlignFourierWindowRadius", "cdecl"):
        continue
    digHoloConfigGetAutoAlignFourierWindowRadius = _lib.get("digHoloConfigGetAutoAlignFourierWindowRadius", "cdecl")
    digHoloConfigGetAutoAlignFourierWindowRadius.argtypes = [c_int]
    digHoloConfigGetAutoAlignFourierWindowRadius.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1025
for _lib in _libs.values():
    if not _lib.has("digHoloConfigSetAutoAlignTol", "cdecl"):
        continue
    digHoloConfigSetAutoAlignTol = _lib.get("digHoloConfigSetAutoAlignTol", "cdecl")
    digHoloConfigSetAutoAlignTol.argtypes = [c_int, c_float]
    digHoloConfigSetAutoAlignTol.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1033
for _lib in _libs.values():
    if not _lib.has("digHoloConfigGetAutoAlignTol", "cdecl"):
        continue
    digHoloConfigGetAutoAlignTol = _lib.get("digHoloConfigGetAutoAlignTol", "cdecl")
    digHoloConfigGetAutoAlignTol.argtypes = [c_int]
    digHoloConfigGetAutoAlignTol.restype = c_float
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1046
for _lib in _libs.values():
    if not _lib.has("digHoloConfigSetAutoAlignPolIndependence", "cdecl"):
        continue
    digHoloConfigSetAutoAlignPolIndependence = _lib.get("digHoloConfigSetAutoAlignPolIndependence", "cdecl")
    digHoloConfigSetAutoAlignPolIndependence.argtypes = [c_int, c_int]
    digHoloConfigSetAutoAlignPolIndependence.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1058
for _lib in _libs.values():
    if not _lib.has("digHoloConfigGetAutoAlignPolIndependence", "cdecl"):
        continue
    digHoloConfigGetAutoAlignPolIndependence = _lib.get("digHoloConfigGetAutoAlignPolIndependence", "cdecl")
    digHoloConfigGetAutoAlignPolIndependence.argtypes = [c_int]
    digHoloConfigGetAutoAlignPolIndependence.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1071
for _lib in _libs.values():
    if not _lib.has("digHoloConfigSetAutoAlignBasisMulConjTrans", "cdecl"):
        continue
    digHoloConfigSetAutoAlignBasisMulConjTrans = _lib.get("digHoloConfigSetAutoAlignBasisMulConjTrans", "cdecl")
    digHoloConfigSetAutoAlignBasisMulConjTrans.argtypes = [c_int, c_int]
    digHoloConfigSetAutoAlignBasisMulConjTrans.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1083
for _lib in _libs.values():
    if not _lib.has("digHoloConfigGetAutoAlignBasisMulConjTrans", "cdecl"):
        continue
    digHoloConfigGetAutoAlignBasisMulConjTrans = _lib.get("digHoloConfigGetAutoAlignBasisMulConjTrans", "cdecl")
    digHoloConfigGetAutoAlignBasisMulConjTrans.argtypes = [c_int]
    digHoloConfigGetAutoAlignBasisMulConjTrans.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1101
for _lib in _libs.values():
    if not _lib.has("digHoloConfigSetAutoAlignMode", "cdecl"):
        continue
    digHoloConfigSetAutoAlignMode = _lib.get("digHoloConfigSetAutoAlignMode", "cdecl")
    digHoloConfigSetAutoAlignMode.argtypes = [c_int, c_int]
    digHoloConfigSetAutoAlignMode.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1109
for _lib in _libs.values():
    if not _lib.has("digHoloConfigGetAutoAlignMode", "cdecl"):
        continue
    digHoloConfigGetAutoAlignMode = _lib.get("digHoloConfigGetAutoAlignMode", "cdecl")
    digHoloConfigGetAutoAlignMode.argtypes = [c_int]
    digHoloConfigGetAutoAlignMode.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1128
for _lib in _libs.values():
    if not _lib.has("digHoloConfigSetAutoAlignGoalIdx", "cdecl"):
        continue
    digHoloConfigSetAutoAlignGoalIdx = _lib.get("digHoloConfigSetAutoAlignGoalIdx", "cdecl")
    digHoloConfigSetAutoAlignGoalIdx.argtypes = [c_int, c_int]
    digHoloConfigSetAutoAlignGoalIdx.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1136
for _lib in _libs.values():
    if not _lib.has("digHoloConfigGetAutoAlignGoalIdx", "cdecl"):
        continue
    digHoloConfigGetAutoAlignGoalIdx = _lib.get("digHoloConfigGetAutoAlignGoalIdx", "cdecl")
    digHoloConfigGetAutoAlignGoalIdx.argtypes = [c_int]
    digHoloConfigGetAutoAlignGoalIdx.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1152
for _lib in _libs.values():
    if not _lib.has("digHoloAutoAlign", "cdecl"):
        continue
    digHoloAutoAlign = _lib.get("digHoloAutoAlign", "cdecl")
    digHoloAutoAlign.argtypes = [c_int]
    digHoloAutoAlign.restype = c_float
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1163
for _lib in _libs.values():
    if not _lib.has("digHoloAutoAlignGetMetric", "cdecl"):
        continue
    digHoloAutoAlignGetMetric = _lib.get("digHoloAutoAlignGetMetric", "cdecl")
    digHoloAutoAlignGetMetric.argtypes = [c_int, c_int]
    digHoloAutoAlignGetMetric.restype = c_float
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1174
for _lib in _libs.values():
    if not _lib.has("digHoloAutoAlignGetMetrics", "cdecl"):
        continue
    digHoloAutoAlignGetMetrics = _lib.get("digHoloAutoAlignGetMetrics", "cdecl")
    digHoloAutoAlignGetMetrics.argtypes = [c_int, c_int]
    digHoloAutoAlignGetMetrics.restype = POINTER(c_float)
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1185
for _lib in _libs.values():
    if not _lib.has("digHoloAutoAlignCalcMetrics", "cdecl"):
        continue
    digHoloAutoAlignCalcMetrics = _lib.get("digHoloAutoAlignCalcMetrics", "cdecl")
    digHoloAutoAlignCalcMetrics.argtypes = [c_int]
    digHoloAutoAlignCalcMetrics.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1205
for _lib in _libs.values():
    if not _lib.has("digHoloConfigSetBeamCentre", "cdecl"):
        continue
    digHoloConfigSetBeamCentre = _lib.get("digHoloConfigSetBeamCentre", "cdecl")
    digHoloConfigSetBeamCentre.argtypes = [c_int, c_int, c_int, c_float]
    digHoloConfigSetBeamCentre.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1215
for _lib in _libs.values():
    if not _lib.has("digHoloConfigGetBeamCentre", "cdecl"):
        continue
    digHoloConfigGetBeamCentre = _lib.get("digHoloConfigGetBeamCentre", "cdecl")
    digHoloConfigGetBeamCentre.argtypes = [c_int, c_int, c_int]
    digHoloConfigGetBeamCentre.restype = c_float
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1226
for _lib in _libs.values():
    if not _lib.has("digHoloConfigSetTilt", "cdecl"):
        continue
    digHoloConfigSetTilt = _lib.get("digHoloConfigSetTilt", "cdecl")
    digHoloConfigSetTilt.argtypes = [c_int, c_int, c_int, c_float]
    digHoloConfigSetTilt.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1236
for _lib in _libs.values():
    if not _lib.has("digHoloConfigGetTilt", "cdecl"):
        continue
    digHoloConfigGetTilt = _lib.get("digHoloConfigGetTilt", "cdecl")
    digHoloConfigGetTilt.argtypes = [c_int, c_int, c_int]
    digHoloConfigGetTilt.restype = c_float
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1246
for _lib in _libs.values():
    if not _lib.has("digHoloConfigSetDefocus", "cdecl"):
        continue
    digHoloConfigSetDefocus = _lib.get("digHoloConfigSetDefocus", "cdecl")
    digHoloConfigSetDefocus.argtypes = [c_int, c_int, c_float]
    digHoloConfigSetDefocus.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1255
for _lib in _libs.values():
    if not _lib.has("digHoloConfigGetDefocus", "cdecl"):
        continue
    digHoloConfigGetDefocus = _lib.get("digHoloConfigGetDefocus", "cdecl")
    digHoloConfigGetDefocus.argtypes = [c_int, c_int]
    digHoloConfigGetDefocus.restype = c_float
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1270
for _lib in _libs.values():
    if not _lib.has("digHoloConfigSetPolLockTilt", "cdecl"):
        continue
    digHoloConfigSetPolLockTilt = _lib.get("digHoloConfigSetPolLockTilt", "cdecl")
    digHoloConfigSetPolLockTilt.argtypes = [c_int, c_int]
    digHoloConfigSetPolLockTilt.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1282
for _lib in _libs.values():
    if not _lib.has("digHoloConfigGetPolLockTilt", "cdecl"):
        continue
    digHoloConfigGetPolLockTilt = _lib.get("digHoloConfigGetPolLockTilt", "cdecl")
    digHoloConfigGetPolLockTilt.argtypes = [c_int]
    digHoloConfigGetPolLockTilt.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1297
for _lib in _libs.values():
    if not _lib.has("digHoloConfigSetPolLockDefocus", "cdecl"):
        continue
    digHoloConfigSetPolLockDefocus = _lib.get("digHoloConfigSetPolLockDefocus", "cdecl")
    digHoloConfigSetPolLockDefocus.argtypes = [c_int, c_int]
    digHoloConfigSetPolLockDefocus.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1309
for _lib in _libs.values():
    if not _lib.has("digHoloConfigGetPolLockDefocus", "cdecl"):
        continue
    digHoloConfigGetPolLockDefocus = _lib.get("digHoloConfigGetPolLockDefocus", "cdecl")
    digHoloConfigGetPolLockDefocus.argtypes = [c_int]
    digHoloConfigGetPolLockDefocus.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1318
for _lib in _libs.values():
    if not _lib.has("digHoloConfigSetPolLockBasisWaist", "cdecl"):
        continue
    digHoloConfigSetPolLockBasisWaist = _lib.get("digHoloConfigSetPolLockBasisWaist", "cdecl")
    digHoloConfigSetPolLockBasisWaist.argtypes = [c_int, c_int]
    digHoloConfigSetPolLockBasisWaist.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1326
for _lib in _libs.values():
    if not _lib.has("digHoloConfigGetPolLockBasisWaist", "cdecl"):
        continue
    digHoloConfigGetPolLockBasisWaist = _lib.get("digHoloConfigGetPolLockBasisWaist", "cdecl")
    digHoloConfigGetPolLockBasisWaist.argtypes = [c_int]
    digHoloConfigGetPolLockBasisWaist.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1384
for _lib in _libs.values():
    if not _lib.has("digHoloConfigSetBasisGroupCount", "cdecl"):
        continue
    digHoloConfigSetBasisGroupCount = _lib.get("digHoloConfigSetBasisGroupCount", "cdecl")
    digHoloConfigSetBasisGroupCount.argtypes = [c_int, c_int]
    digHoloConfigSetBasisGroupCount.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1393
for _lib in _libs.values():
    if not _lib.has("digHoloConfigGetBasisGroupCount", "cdecl"):
        continue
    digHoloConfigGetBasisGroupCount = _lib.get("digHoloConfigGetBasisGroupCount", "cdecl")
    digHoloConfigGetBasisGroupCount.argtypes = [c_int]
    digHoloConfigGetBasisGroupCount.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1404
for _lib in _libs.values():
    if not _lib.has("digHoloConfigSetBasisWaist", "cdecl"):
        continue
    digHoloConfigSetBasisWaist = _lib.get("digHoloConfigSetBasisWaist", "cdecl")
    digHoloConfigSetBasisWaist.argtypes = [c_int, c_int, c_float]
    digHoloConfigSetBasisWaist.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1416
for _lib in _libs.values():
    if not _lib.has("digHoloConfigGetBasisWaist", "cdecl"):
        continue
    digHoloConfigGetBasisWaist = _lib.get("digHoloConfigGetBasisWaist", "cdecl")
    digHoloConfigGetBasisWaist.argtypes = [c_int, c_int]
    digHoloConfigGetBasisWaist.restype = c_float
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1424
for _lib in _libs.values():
    if not _lib.has("digHoloConfigSetBasisTypeHG", "cdecl"):
        continue
    digHoloConfigSetBasisTypeHG = _lib.get("digHoloConfigSetBasisTypeHG", "cdecl")
    digHoloConfigSetBasisTypeHG.argtypes = [c_int]
    digHoloConfigSetBasisTypeHG.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1435
for _lib in _libs.values():
    if not _lib.has("digHoloConfigSetBasisTypeLG", "cdecl"):
        continue
    digHoloConfigSetBasisTypeLG = _lib.get("digHoloConfigSetBasisTypeLG", "cdecl")
    digHoloConfigSetBasisTypeLG.argtypes = [c_int]
    digHoloConfigSetBasisTypeLG.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1453
for _lib in _libs.values():
    if not _lib.has("digHoloConfigSetBasisTypeCustom", "cdecl"):
        continue
    digHoloConfigSetBasisTypeCustom = _lib.get("digHoloConfigSetBasisTypeCustom", "cdecl")
    digHoloConfigSetBasisTypeCustom.argtypes = [c_int, c_int, c_int, POINTER(complex64)]
    digHoloConfigSetBasisTypeCustom.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1464
for _lib in _libs.values():
    if not _lib.has("digHoloConfigSetBasisType", "cdecl"):
        continue
    digHoloConfigSetBasisType = _lib.get("digHoloConfigSetBasisType", "cdecl")
    digHoloConfigSetBasisType.argtypes = [c_int, c_int]
    digHoloConfigSetBasisType.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1472
for _lib in _libs.values():
    if not _lib.has("digHoloConfigGetBasisType", "cdecl"):
        continue
    digHoloConfigGetBasisType = _lib.get("digHoloConfigGetBasisType", "cdecl")
    digHoloConfigGetBasisType.argtypes = [c_int]
    digHoloConfigGetBasisType.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1494
for _lib in _libs.values():
    if not _lib.has("digHoloProcessBatch", "cdecl"):
        continue
    digHoloProcessBatch = _lib.get("digHoloProcessBatch", "cdecl")
    digHoloProcessBatch.argtypes = [c_int, POINTER(c_int), POINTER(c_int), POINTER(c_int)]
    digHoloProcessBatch.restype = POINTER(complex64)
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1510
for _lib in _libs.values():
    if not _lib.has("digHoloProcessBatchFrequencySweepLinear", "cdecl"):
        continue
    digHoloProcessBatchFrequencySweepLinear = _lib.get("digHoloProcessBatchFrequencySweepLinear", "cdecl")
    digHoloProcessBatchFrequencySweepLinear.argtypes = [c_int, POINTER(c_int), POINTER(c_int), POINTER(c_int), c_float, c_float, c_int]
    digHoloProcessBatchFrequencySweepLinear.restype = POINTER(complex64)
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1525
for _lib in _libs.values():
    if not _lib.has("digHoloProcessBatchWavelengthSweepArbitrary", "cdecl"):
        continue
    digHoloProcessBatchWavelengthSweepArbitrary = _lib.get("digHoloProcessBatchWavelengthSweepArbitrary", "cdecl")
    digHoloProcessBatchWavelengthSweepArbitrary.argtypes = [c_int, POINTER(c_int), POINTER(c_int), POINTER(c_int), POINTER(c_float), c_int]
    digHoloProcessBatchWavelengthSweepArbitrary.restype = POINTER(complex64)
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1549
for _lib in _libs.values():
    if not _lib.has("digHoloGetFields", "cdecl"):
        continue
    digHoloGetFields = _lib.get("digHoloGetFields", "cdecl")
    digHoloGetFields.argtypes = [c_int, POINTER(c_int), POINTER(c_int), POINTER(POINTER(c_float)), POINTER(POINTER(c_float)), POINTER(c_int), POINTER(c_int)]
    digHoloGetFields.restype = POINTER(complex64)
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1568
for _lib in _libs.values():
    if not _lib.has("digHoloGetFields16", "cdecl"):
        continue
    digHoloGetFields16 = _lib.get("digHoloGetFields16", "cdecl")
    digHoloGetFields16.argtypes = [c_int, POINTER(c_int), POINTER(c_int), POINTER(POINTER(c_short)), POINTER(POINTER(c_short)), POINTER(POINTER(c_float)), POINTER(POINTER(c_float)), POINTER(POINTER(c_float)), POINTER(c_int), POINTER(c_int)]
    digHoloGetFields16.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1587
for _lib in _libs.values():
    if not _lib.has("digHoloBasisGetFields", "cdecl"):
        continue
    digHoloBasisGetFields = _lib.get("digHoloBasisGetFields", "cdecl")
    digHoloBasisGetFields.argtypes = [c_int, POINTER(c_int), POINTER(c_int), POINTER(POINTER(c_float)), POINTER(POINTER(c_float)), POINTER(c_int), POINTER(c_int)]
    digHoloBasisGetFields.restype = POINTER(complex64)
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1603
for _lib in _libs.values():
    if not _lib.has("digHoloBasisGetCoefs", "cdecl"):
        continue
    digHoloBasisGetCoefs = _lib.get("digHoloBasisGetCoefs", "cdecl")
    digHoloBasisGetCoefs.argtypes = [c_int, POINTER(c_int), POINTER(c_int), POINTER(c_int)]
    digHoloBasisGetCoefs.restype = POINTER(complex64)
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1659
for _lib in _libs.values():
    if not _lib.has("digHoloBatchGetSummary", "cdecl"):
        continue
    digHoloBatchGetSummary = _lib.get("digHoloBatchGetSummary", "cdecl")
    digHoloBatchGetSummary.argtypes = [c_int, c_int, POINTER(c_int), POINTER(c_int), POINTER(c_int), POINTER(POINTER(c_float)), POINTER(c_int), POINTER(c_int), POINTER(POINTER(c_float)), POINTER(POINTER(c_float)), POINTER(POINTER(c_float))]
    digHoloBatchGetSummary.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1670
for _lib in _libs.values():
    if not _lib.has("digHoloProcessFFT", "cdecl"):
        continue
    digHoloProcessFFT = _lib.get("digHoloProcessFFT", "cdecl")
    digHoloProcessFFT.argtypes = [c_int]
    digHoloProcessFFT.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1682
for _lib in _libs.values():
    if not _lib.has("digHoloProcessIFFT", "cdecl"):
        continue
    digHoloProcessIFFT = _lib.get("digHoloProcessIFFT", "cdecl")
    digHoloProcessIFFT.argtypes = [c_int]
    digHoloProcessIFFT.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1694
for _lib in _libs.values():
    if not _lib.has("digHoloProcessRemoveTilt", "cdecl"):
        continue
    digHoloProcessRemoveTilt = _lib.get("digHoloProcessRemoveTilt", "cdecl")
    digHoloProcessRemoveTilt.argtypes = [c_int]
    digHoloProcessRemoveTilt.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1706
for _lib in _libs.values():
    if not _lib.has("digHoloProcessBasisExtractCoefs", "cdecl"):
        continue
    digHoloProcessBasisExtractCoefs = _lib.get("digHoloProcessBasisExtractCoefs", "cdecl")
    digHoloProcessBasisExtractCoefs.argtypes = [c_int]
    digHoloProcessBasisExtractCoefs.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1718
for _lib in _libs.values():
    if not _lib.has("digHoloGetFourierPlaneFull", "cdecl"):
        continue
    digHoloGetFourierPlaneFull = _lib.get("digHoloGetFourierPlaneFull", "cdecl")
    digHoloGetFourierPlaneFull.argtypes = [c_int, POINTER(c_int), POINTER(c_int), POINTER(c_int), POINTER(c_int)]
    digHoloGetFourierPlaneFull.restype = POINTER(complex64)
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1732
for _lib in _libs.values():
    if not _lib.has("digHoloGetFourierPlaneWindow", "cdecl"):
        continue
    digHoloGetFourierPlaneWindow = _lib.get("digHoloGetFourierPlaneWindow", "cdecl")
    digHoloGetFourierPlaneWindow.argtypes = [c_int, POINTER(c_int), POINTER(c_int), POINTER(c_int), POINTER(c_int)]
    digHoloGetFourierPlaneWindow.restype = POINTER(complex64)
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1749
for _lib in _libs.values():
    if not _lib.has("digHoloConfigSetThreadCount", "cdecl"):
        continue
    digHoloConfigSetThreadCount = _lib.get("digHoloConfigSetThreadCount", "cdecl")
    digHoloConfigSetThreadCount.argtypes = [c_int, c_int]
    digHoloConfigSetThreadCount.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1757
for _lib in _libs.values():
    if not _lib.has("digHoloConfigGetThreadCount", "cdecl"):
        continue
    digHoloConfigGetThreadCount = _lib.get("digHoloConfigGetThreadCount", "cdecl")
    digHoloConfigGetThreadCount.argtypes = [c_int]
    digHoloConfigGetThreadCount.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1766
for _lib in _libs.values():
    if not _lib.has("digHoloBenchmarkEstimateThreadCountOptimal", "cdecl"):
        continue
    digHoloBenchmarkEstimateThreadCountOptimal = _lib.get("digHoloBenchmarkEstimateThreadCountOptimal", "cdecl")
    digHoloBenchmarkEstimateThreadCountOptimal.argtypes = [c_int, c_float]
    digHoloBenchmarkEstimateThreadCountOptimal.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1776
for _lib in _libs.values():
    if not _lib.has("digHoloBenchmark", "cdecl"):
        continue
    digHoloBenchmark = _lib.get("digHoloBenchmark", "cdecl")
    digHoloBenchmark.argtypes = [c_int, c_float, POINTER(c_float)]
    digHoloBenchmark.restype = c_float
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1808
for _lib in _libs.values():
    if not _lib.has("digHoloConfigSetFFTWPlanMode", "cdecl"):
        continue
    digHoloConfigSetFFTWPlanMode = _lib.get("digHoloConfigSetFFTWPlanMode", "cdecl")
    digHoloConfigSetFFTWPlanMode.argtypes = [c_int, c_int]
    digHoloConfigSetFFTWPlanMode.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1818
for _lib in _libs.values():
    if not _lib.has("digHoloConfigGetFFTWPlanMode", "cdecl"):
        continue
    digHoloConfigGetFFTWPlanMode = _lib.get("digHoloConfigGetFFTWPlanMode", "cdecl")
    digHoloConfigGetFFTWPlanMode.argtypes = [c_int]
    digHoloConfigGetFFTWPlanMode.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1825
for _lib in _libs.values():
    if not _lib.has("digHoloFFTWWisdomForget", "cdecl"):
        continue
    digHoloFFTWWisdomForget = _lib.get("digHoloFFTWWisdomForget", "cdecl")
    digHoloFFTWWisdomForget.argtypes = []
    digHoloFFTWWisdomForget.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1835
for _lib in _libs.values():
    if not _lib.has("digHoloFFTWWisdomFilename", "cdecl"):
        continue
    digHoloFFTWWisdomFilename = _lib.get("digHoloFFTWWisdomFilename", "cdecl")
    digHoloFFTWWisdomFilename.argtypes = [String]
    digHoloFFTWWisdomFilename.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1883
for _lib in _libs.values():
    if not _lib.has("digHoloGetViewport", "cdecl"):
        continue
    digHoloGetViewport = _lib.get("digHoloGetViewport", "cdecl")
    digHoloGetViewport.argtypes = [c_int, c_int, c_int, POINTER(c_int), POINTER(c_int), POINTER(POINTER(c_char))]
    digHoloGetViewport.restype = POINTER(c_ubyte)
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1897
for _lib in _libs.values():
    if not _lib.has("digHoloGetViewportToFile", "cdecl"):
        continue
    digHoloGetViewportToFile = _lib.get("digHoloGetViewportToFile", "cdecl")
    digHoloGetViewportToFile.argtypes = [c_int, c_int, c_int, POINTER(c_int), POINTER(c_int), POINTER(POINTER(c_char)), String]
    digHoloGetViewportToFile.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1924
for _lib in _libs.values():
    if not _lib.has("digHoloConfigSetVerbosity", "cdecl"):
        continue
    digHoloConfigSetVerbosity = _lib.get("digHoloConfigSetVerbosity", "cdecl")
    digHoloConfigSetVerbosity.argtypes = [c_int, c_int]
    digHoloConfigSetVerbosity.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1937
for _lib in _libs.values():
    if not _lib.has("digHoloConfigGetVerbosity", "cdecl"):
        continue
    digHoloConfigGetVerbosity = _lib.get("digHoloConfigGetVerbosity", "cdecl")
    digHoloConfigGetVerbosity.argtypes = [c_int]
    digHoloConfigGetVerbosity.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1945
for _lib in _libs.values():
    if not _lib.has("digHoloConsoleRedirectToFile", "cdecl"):
        continue
    digHoloConsoleRedirectToFile = _lib.get("digHoloConsoleRedirectToFile", "cdecl")
    digHoloConsoleRedirectToFile.argtypes = [String]
    digHoloConsoleRedirectToFile.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1952
for _lib in _libs.values():
    if not _lib.has("digHoloConsoleRestore", "cdecl"):
        continue
    digHoloConsoleRestore = _lib.get("digHoloConsoleRestore", "cdecl")
    digHoloConsoleRestore.argtypes = []
    digHoloConsoleRestore.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1962
for _lib in _libs.values():
    if not _lib.has("digHoloRunBatchFromConfigFile", "cdecl"):
        continue
    digHoloRunBatchFromConfigFile = _lib.get("digHoloRunBatchFromConfigFile", "cdecl")
    digHoloRunBatchFromConfigFile.argtypes = [String]
    digHoloRunBatchFromConfigFile.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1973
for _lib in _libs.values():
    if not _lib.has("digHoloConfigBackupSave", "cdecl"):
        continue
    digHoloConfigBackupSave = _lib.get("digHoloConfigBackupSave", "cdecl")
    digHoloConfigBackupSave.argtypes = [c_int]
    digHoloConfigBackupSave.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1983
for _lib in _libs.values():
    if not _lib.has("digHoloConfigBackupLoad", "cdecl"):
        continue
    digHoloConfigBackupLoad = _lib.get("digHoloConfigBackupLoad", "cdecl")
    digHoloConfigBackupLoad.argtypes = [c_int]
    digHoloConfigBackupLoad.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1990
for _lib in _libs.values():
    if not _lib.has("digHoloDebugRoutine", "cdecl"):
        continue
    digHoloDebugRoutine = _lib.get("digHoloDebugRoutine", "cdecl")
    digHoloDebugRoutine.argtypes = [c_int]
    digHoloDebugRoutine.restype = None
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 2026
for _lib in _libs.values():
    if not _lib.has("digHoloFrameSimulatorCreate", "cdecl"):
        continue
    digHoloFrameSimulatorCreate = _lib.get("digHoloFrameSimulatorCreate", "cdecl")
    digHoloFrameSimulatorCreate.argtypes = [c_int, POINTER(c_int), POINTER(c_int), POINTER(c_float), POINTER(c_int), POINTER(POINTER(c_float)), POINTER(POINTER(c_float)), POINTER(POINTER(c_float)), POINTER(POINTER(c_float)), POINTER(POINTER(c_float)), POINTER(POINTER(c_float)), POINTER(POINTER(complex64)), POINTER(c_int), POINTER(POINTER(c_float)), POINTER(POINTER(complex64)), POINTER(POINTER(c_float)), POINTER(POINTER(c_float)), POINTER(c_int), c_int, POINTER(POINTER(c_float)), POINTER(c_int), c_int, c_int, POINTER(POINTER(c_ushort)), String]
    digHoloFrameSimulatorCreate.restype = POINTER(c_float)
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 2046
for _lib in _libs.values():
    if not _lib.has("digHoloFrameSimulatorCreateSimple", "cdecl"):
        continue
    digHoloFrameSimulatorCreateSimple = _lib.get("digHoloFrameSimulatorCreateSimple", "cdecl")
    digHoloFrameSimulatorCreateSimple.argtypes = [c_int, c_int, c_int, c_float, c_int, c_float, c_int]
    digHoloFrameSimulatorCreateSimple.restype = POINTER(c_float)
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 2056
for _lib in _libs.values():
    if not _lib.has("digHoloFrameSimulatorDestroy", "cdecl"):
        continue
    digHoloFrameSimulatorDestroy = _lib.get("digHoloFrameSimulatorDestroy", "cdecl")
    digHoloFrameSimulatorDestroy.argtypes = [POINTER(c_float)]
    digHoloFrameSimulatorDestroy.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 2075
for _lib in _libs.values():
    if not _lib.has("digHoloConfigGetZernCoefs", "cdecl"):
        continue
    digHoloConfigGetZernCoefs = _lib.get("digHoloConfigGetZernCoefs", "cdecl")
    digHoloConfigGetZernCoefs.argtypes = [c_int]
    digHoloConfigGetZernCoefs.restype = POINTER(POINTER(c_float))
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 2084
for _lib in _libs.values():
    if not _lib.has("digHoloConfigGetZernCount", "cdecl"):
        continue
    digHoloConfigGetZernCount = _lib.get("digHoloConfigGetZernCount", "cdecl")
    digHoloConfigGetZernCount.argtypes = [c_int]
    digHoloConfigGetZernCount.restype = c_int
    break

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 171
try:
    DIGHOLO_ERROR_SUCCESS = 0
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 172
try:
    DIGHOLO_ERROR_ERROR = 1
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 173
try:
    DIGHOLO_ERROR_INVALIDHANDLE = 2
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 174
try:
    DIGHOLO_ERROR_NULLPOINTER = 3
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 175
try:
    DIGHOLO_ERROR_SETFRAMEBUFFERDISABLED = 4
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 176
try:
    DIGHOLO_ERROR_INVALIDDIMENSION = 5
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 177
try:
    DIGHOLO_ERROR_INVALIDPOLARISATION = 6
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 178
try:
    DIGHOLO_ERROR_INVALIDAXIS = 7
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 179
try:
    DIGHOLO_ERROR_INVALIDARGUMENT = 8
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 180
try:
    DIGHOLO_ERROR_MEMORYALLOCATION = 9
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 181
try:
    DIGHOLO_ERROR_FILENOTCREATED = 10
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 182
try:
    DIGHOLO_ERROR_FILENOTFOUND = 11
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 190
try:
    DIGHOLO_UNIT_PIXEL = 1
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 191
try:
    DIGHOLO_UNIT_LAMBDA = 1
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 655
try:
    DIGHOLO_AVGMODE_SEQUENTIAL = 0
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 656
try:
    DIGHOLO_AVGMODE_INTERLACED = 1
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 657
try:
    DIGHOLO_AVGMODE_SEQUENTIALSWEEP = 2
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 658
try:
    DIGHOLO_AVGMODE_COUNT = 3
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 871
try:
    DIGHOLO_WAVELENGTHORDER_INPUT = 0
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 872
try:
    DIGHOLO_WAVELENGTHORDER_OUTPUT = 1
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 874
try:
    DIGHOLO_WAVELENGTHORDER_FAST = 0
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 875
try:
    DIGHOLO_WAVELENGTHORDER_SLOW = 1
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 925
try:
    DIGHOLO_AUTOALIGNMODE_FULL = 0
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 926
try:
    DIGHOLO_AUTOALIGNMODE_TWEAK = 1
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 927
try:
    DIGHOLO_AUTOALIGNMODE_ESTIMATE = 2
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 928
try:
    DIGHOLO_AUTOALIGNMODE_COUNT = 3
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1348
try:
    DIGHOLO_BASISTYPE_HG = 0
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1349
try:
    DIGHOLO_BASISTYPE_LG = 1
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1350
try:
    DIGHOLO_BASISTYPE_CUSTOM = 2
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1363
try:
    DIGHOLO_METRIC_IL = 0
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1364
try:
    DIGHOLO_METRIC_MDL = 1
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1365
try:
    DIGHOLO_METRIC_DIAG = 2
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1366
try:
    DIGHOLO_METRIC_SNRAVG = 3
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1367
try:
    DIGHOLO_METRIC_DIAGBEST = 4
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1368
try:
    DIGHOLO_METRIC_DIAGWORST = 5
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1369
try:
    DIGHOLO_METRIC_SNRBEST = 6
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1370
try:
    DIGHOLO_METRIC_SNRWORST = 7
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1371
try:
    DIGHOLO_METRIC_SNRMG = 8
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1372
try:
    DIGHOLO_METRIC_COUNT = 9
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1624
try:
    DIGHOLO_ANALYSIS_TOTALPOWER = 0
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1625
try:
    DIGHOLO_ANALYSIS_COMX = 1
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1626
try:
    DIGHOLO_ANALYSIS_COMY = 2
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1627
try:
    DIGHOLO_ANALYSIS_MAXABS = 3
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1628
try:
    DIGHOLO_ANALYSIS_MAXABSIDX = 4
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1629
try:
    DIGHOLO_ANALYSIS_AEFF = 5
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1630
try:
    DIGHOLO_ANALYSIS_COMYWRAP = 6
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1631
try:
    DIGHOLO_ANALYSIS_COUNT = 7
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1783
try:
    DIGHOLO_BENCHMARK_FFT = 0
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1784
try:
    DIGHOLO_BENCHMARK_IFFT = 1
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1785
try:
    DIGHOLO_BENCHMARK_APPLYTILT = 2
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1786
try:
    DIGHOLO_BENCHMARK_BASIS = 3
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1787
try:
    DIGHOLO_BENCHMARK_OVERLAP = 4
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1788
try:
    DIGHOLO_BENCHMARK_TOTAL = 5
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1857
try:
    DIGHOLO_VIEWPORT_NONE = 0
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1858
try:
    DIGHOLO_VIEWPORT_CAMERAPLANE = 1
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1859
try:
    DIGHOLO_VIEWPORT_FOURIERPLANE = 2
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1860
try:
    DIGHOLO_VIEWPORT_FOURIERPLANEDB = 3
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1861
try:
    DIGHOLO_VIEWPORT_FOURIERWINDOW = 4
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1862
try:
    DIGHOLO_VIEWPORT_FOURIERWINDOWABS = 5
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1863
try:
    DIGHOLO_VIEWPORT_FIELDPLANE = 6
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1864
try:
    DIGHOLO_VIEWPORT_FIELDPLANEABS = 7
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1865
try:
    DIGHOLO_VIEWPORT_FIELDPLANEMODE = 8
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1866
try:
    DIGHOLO_VIEWPORT_COUNT = 9
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1868
try:
    DIGHOLO_VIEWPORT_NAMELENGTH = 1024
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1906
try:
    DIGHOLO_VERBOSITY_OFF = 0
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1907
try:
    DIGHOLO_VERBOSITY_BASIC = 1
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1908
try:
    DIGHOLO_VERBOSITY_DEBUG = 2
except:
    pass

# /Users/s4356803/Documents/PhD/Codes/PythonCode/Experiments/Lab_Equipment/digHolo/digHolo_v1.0.0/src/digHolo.h: 1909
try:
    DIGHOLO_VERBOSITY_COOKED = 3
except:
    pass

# No inserted files

# No prefix-stripping

