# -*- coding: utf-8 -*-
# Copyright (c) 2015, Vispy Development Team.
# Distributed under the (new) BSD License. See LICENSE.txt for more info.

""" This module provides a (functional) API to OpenGL ES 2.0.

There are multiple backend implementations of this API, available as
submodules of this module. One can use one of the backends directly,
or call `gl.use_gl()` to select one. The backend system allow running
visualizations using Angle, WebGL, or other forms of remote rendering.
This is in part possible by the widespread availability of OpenGL ES 2.0.

All functions that this API provides accept and return Python arguments
(no ctypes is required); strings are real strings and you can pass 
data as numpy arrays. In general the input arguments are not checked
(for performance reasons). Each function results in exactly one OpenGL
API call, except when using the pyopengl backend.

The functions do not have docstrings, but most IDE's should provide you
with the function signature. For more documentation see
http://www.khronos.org/opengles/sdk/docs/man/

"""

# NOTE: modules in this package that start with one underscore are
# autogenerated, and should not be edited.

from __future__ import division

import os

from ...util import config, logger

from ._constants import *  # noqa
from ._proxy import BaseGLProxy


# Variable that will hold the module corresponding to the current backend
# This variable is used in our proxy classes to call the right functions.
current_backend = None


class MainProxy(BaseGLProxy):
    """ Main proxy for the GL ES 2.0 API. 
    
    The functions in this namespace always call into the correct GL
    backend. Therefore these function objects can be safely stored for
    reuse. However, for efficienty it would probably be better to store the
    function name and then do ``func = getattr(gloo.gl, funcname)``.
    """
    
    def __call__(self, funcname, returns, *args):
        func = getattr(current_backend, funcname)
        return func(*args)


class DebugProxy(BaseGLProxy):
    """ Proxy for debug version of the GL ES 2.0 API. 
    
    This proxy calls the functions of the currently selected backend.
    In addition it logs debug information, and it runs check_error()
    on each API call. Intended for internal use.
    """
    
    def _arg_repr(self, arg):
        """ Get a useful (and not too large) represetation of an argument.
        """
        r = repr(arg)
        max = 40
        if len(r) > max:
            if hasattr(arg, 'shape'):
                r = 'array:' + 'x'.join([repr(s) for s in arg.shape])
            else:
                r = r[:max-3] + '...'
        return r
    
    def __call__(self, funcname, returns, *args):
        # Avoid recursion for glGetError
        if funcname == 'glGetError':
            func = getattr(current_backend, funcname)
            return func()
        # Log function call
        argstr = ', '.join(map(self._arg_repr, args))
        logger.debug("%s(%s)" % (funcname, argstr))
        # Call function
        func = getattr(current_backend, funcname)
        ret = func(*args)
        # Log return value
        if returns:
            logger.debug(" <= %s" % repr(ret))
        # Check for errors (raises if an error occured)
        check_error(funcname)
        # Return
        return ret


# Instantiate proxy objects
proxy = MainProxy()
_debug_proxy = DebugProxy()


def use_gl(target='gl2'):
    """ Let Vispy use the target OpenGL ES 2.0 implementation
    
    Also see ``vispy.use()``.
    
    Parameters
    ----------
    target : str
        The target GL backend to use.

    Available backends:
    * gl2 - Use ES 2.0 subset of desktop (i.e. normal) OpenGL
    * gl+ - Use the desktop ES 2.0 subset plus all non-deprecated GL
      functions on your system (requires PyOpenGL)
    * es2 - Use the ES2 library (Angle/DirectX on Windows)
    * pyopengl2 - Use ES 2.0 subset of pyopengl (for fallback and testing)
    * dummy - Prevent usage of gloo.gl (for when rendering occurs elsewhere)
    
    You can use vispy's config option "gl_debug" to check for errors
    on each API call. Or, one can specify it as the target, e.g. "gl2
    debug". (Debug does not apply to 'gl+', since PyOpenGL has its own
    debug mechanism)
    """
    target = target or 'gl2'
    target = target.replace('+', 'plus')
    
    # Get options
    target, _, options = target.partition(' ')
    debug = config['gl_debug'] or 'debug' in options
    
    # Select modules to import names from
    try:
        mod = __import__(target, globals(), level=1)
    except ImportError as err:
        msg = 'Could not import gl target "%s":\n%s' % (target, str(err))
        raise RuntimeError(msg)

    # Apply
    global current_backend
    current_backend = mod
    _clear_namespace()
    if 'plus' in target:
        # Copy PyOpenGL funcs, extra funcs, constants, no debug
        _copy_gl_functions(mod._pyopengl2, globals())
        _copy_gl_functions(mod, globals(), True)
    elif debug:
        _copy_gl_functions(_debug_proxy, globals())
    else:
        _copy_gl_functions(mod, globals())


def _clear_namespace():
    """ Clear names that are not part of the strict ES API
    """
    ok_names = set(default_backend.__dict__)
    ok_names.update(['gl2', 'glplus'])  # don't remove the module
    NS = globals()
    for name in list(NS.keys()):
        if name.lower().startswith('gl'):
            if name not in ok_names:
                del NS[name]


def _copy_gl_functions(source, dest, constants=False):
    """ Inject all objects that start with 'gl' from the source
    into the dest. source and dest can be dicts, modules or BaseGLProxy's.
    """
    # Get dicts
    if isinstance(source, BaseGLProxy):
        s = {}
        for key in dir(source):
            s[key] = getattr(source, key)
        source = s
    elif not isinstance(source, dict):
        source = source.__dict__
    if not isinstance(dest, dict):
        dest = dest.__dict__
    # Copy names
    funcnames = [name for name in source.keys() if name.startswith('gl')]
    for name in funcnames:
        dest[name] = source[name]
    # Copy constants
    if constants:
        constnames = [name for name in source.keys() if name.startswith('GL_')]
        for name in constnames:
            dest[name] = source[name]


def check_error(when='periodic check'):
    """ Check this from time to time to detect GL errors.

    Parameters
    ----------
    when : str
        Shown in the exception to help the developer determine when
        this check was done.
    """

    errors = []
    while True:
        err = glGetError()
        if err == GL_NO_ERROR or (errors and err == errors[-1]):
            break
        errors.append(err)
    if errors:
        msg = ', '.join([repr(ENUM_MAP.get(e, e)) for e in errors])
        err = RuntimeError('OpenGL got errors (%s): %s' % (when, msg))
        err.errors = errors
        err.err = errors[-1]  # pyopengl compat
        raise err


def _fix_osmesa_gl_lib_if_testing():
    """
    This functions checks if we a running test with the osmesa backends and
    fix the GL library if needed.

    Since we have to fix the VISPY_GL_LIB *before* any import from the gl
    module, we have to run this here.
    Test discovery utilities (like pytest) will try to import modules
    before running tests, so we have to modify the GL lib really early.
    The other solution would be to setup pre-run hooks for the test utility,
    but there doesn't seem to be a standard way to do that (e.g. conftest.py
    for py.test)
    """
    test_name = os.getenv('_VISPY_TESTING_APP', None)
    if test_name == 'osmesa':
        from ...util.osmesa_gl import fix_osmesa_gl_lib
        fix_osmesa_gl_lib()

_fix_osmesa_gl_lib_if_testing()

# Load default gl backend
from . import gl2 as default_backend  # noqa

# Call use to start using our default backend
use_gl()