import os
import re
import sys
import fnmatch
import os.path

# for command line options and supported environment variables, please
# see the end of 'setupinfo.py'

if sys.version_info[:2] < (3, 8):
    print("This lxml version requires Python 3.8 or later.")
    sys.exit(1)

from setuptools import setup

# make sure Cython finds include files in the project directory and not outside
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import versioninfo
import setupinfo

# override these and pass --static for a static build. See
# doc/build.txt for more information. If you do not pass --static
# changing this will have no effect.
def static_env_list(name, separator=None):
    return [x.strip() for x in os.environ.get(name, "").split(separator) if x.strip()]

STATIC_INCLUDE_DIRS = static_env_list("LXML_STATIC_INCLUDE_DIRS", separator=os.pathsep)
STATIC_LIBRARY_DIRS = static_env_list("LXML_STATIC_LIBRARY_DIRS", separator=os.pathsep)
STATIC_CFLAGS = static_env_list("LXML_STATIC_CFLAGS")
STATIC_BINARIES = static_env_list("LXML_STATIC_BINARIES", separator=os.pathsep)

# create lxml-version.h file
versioninfo.create_version_h()
lxml_version = versioninfo.version()
print("Building lxml version %s." % lxml_version)

OPTION_RUN_TESTS = setupinfo.has_option('run-tests')

branch_link = """
After an official release of a new stable series, bug fixes may become available at
https://github.com/lxml/lxml/tree/lxml-{branch_version} .
Running ``pip install https://github.com/lxml/lxml/archive/refs/heads/lxml-{branch_version}.tar.gz``
will install the unreleased branch state as soon as a maintenance branch has been established.
Note that this requires Cython to be installed at an appropriate version for the build.

"""

if versioninfo.is_pre_release():
    branch_link = ""

with open("requirements.txt", "r") as f:
    deps = [line.strip() for line in f if ':' in line]

extra_options = {
    'python_requires': '>=3.8',  # NOTE: keep in sync with Trove classifier list below.

    'extras_require': {
        'source': deps,
        'cssselect': 'cssselect>=0.7',
        'html5': 'html5lib',
        'htmlsoup': 'BeautifulSoup4',
        'html_clean': 'lxml_html_clean',
    },

    'zip_safe': False,

    'package_data': {
        'lxml': [
            'etree.h',
            'etree_api.h',
            'lxml.etree.h',
            'lxml.etree_api.h',
            # Include Cython source files for better traceback output.
            '*.pyx',
            '*.pxi',
        ],
        'lxml.includes': [
            '*.pxd',
            '*.h',
        ],
        'lxml.isoschematron': [
            'resources/rng/iso-schematron.rng',
            'resources/xsl/*.xsl',
            'resources/xsl/iso-schematron-xslt1/*.xsl',
            'resources/xsl/iso-schematron-xslt1/readme.txt',
        ],
    },

    'package_dir': {
        '': 'src'
    },

    'packages': [
        'lxml', 'lxml.includes', 'lxml.html', 'lxml.isoschematron'
    ],

    **setupinfo.extra_setup_args(),
}


def setup_extra_options():
    is_interesting_package = re.compile('^(libxml|libxslt|libexslt)$').match
    is_interesting_header = re.compile(r'^(zconf|zlib|.*charset)\.h$').match

    def extract_files(directories, pattern='*'):
        def get_files(root, dir_path, files):
            return [ (root, dir_path, filename)
                     for filename in fnmatch.filter(files, pattern) ]

        file_list = []
        for dir_path in directories:
            dir_path = os.path.realpath(dir_path)
            for root, dirs, files in os.walk(dir_path):
                rel_dir = root[len(dir_path)+1:]
                if is_interesting_package(rel_dir):
                    file_list.extend(get_files(root, rel_dir, files))
                elif not rel_dir:
                    # include also top-level header files (zlib/iconv)
                    file_list.extend(
                        item for item in get_files(root, rel_dir, files)
                        if is_interesting_header(item[-1])
                    )
        return file_list

    def build_packages(files):
        packages = {}
        seen = set()
        for root_path, rel_path, filename in files:
            if filename in seen:
                # libxml2/libxslt header filenames are unique
                continue
            seen.add(filename)
            package_path = '.'.join(rel_path.split(os.sep))
            if package_path in packages:
                root, package_files = packages[package_path]
                if root != root_path:
                    print("WARNING: conflicting directories found for include package '%s': %s and %s"
                          % (package_path, root_path, root))
                    continue
            else:
                package_files = []
                packages[package_path] = (root_path, package_files)
            package_files.append(filename)

        return packages

    # Copy Global Extra Options
    extra_opts = dict(extra_options)

    # Build ext modules
    ext_modules = setupinfo.ext_modules(
                    STATIC_INCLUDE_DIRS, STATIC_LIBRARY_DIRS,
                    STATIC_CFLAGS, STATIC_BINARIES)
    extra_opts['ext_modules'] = ext_modules

    packages = extra_opts.get('packages', list())
    package_dir = extra_opts.get('package_dir', dict())
    package_data = extra_opts.get('package_data', dict())

    # Add lxml.include with (lxml, libxslt headers...)
    #   python setup.py build --static --static-deps install
    #   python setup.py bdist_wininst --static
    if setupinfo.OPTION_STATIC:
        include_dirs = [] # keep them in order
        for extension in ext_modules:
            for inc_dir in extension.include_dirs:
                if inc_dir not in include_dirs:
                    include_dirs.append(inc_dir)

        header_packages = build_packages(extract_files(include_dirs))

        package_filename = "__init__.py"
        for package_path, (root_path, filenames) in header_packages.items():
            if not package_path:
                # lxml.includes -> lxml.includes.extlibs
                package_path = "extlibs"
            package = 'lxml.includes.' + package_path
            packages.append(package)

            # create '__init__.py' to make sure it's considered a package
            if package_filename not in filenames:
                with open(os.path.join(root_path, package_filename), 'wb') as f:
                    pass
                filenames.append(package_filename)

            assert package not in package_data
            package_data[package] = filenames
            assert package not in package_dir
            package_dir[package] = root_path

    return extra_opts

setup(
    name = "lxml",
    version = lxml_version,
    author="lxml dev team",
    author_email="lxml@lxml.de",
    maintainer="lxml dev team",
    maintainer_email="lxml@lxml.de",
    license="BSD-3-Clause",
    url="https://lxml.de/",
    project_urls={
        "Source": "https://github.com/lxml/lxml",
        "Bug Tracker": "https://bugs.launchpad.net/lxml",
    },
    description=(
        "Powerful and Pythonic XML processing library"
        " combining libxml2/libxslt with the ElementTree API."
    ),
    long_description=(("""\
lxml is a Pythonic, mature binding for the libxml2 and libxslt libraries.
It provides safe and convenient access to these libraries using the
ElementTree API.

It extends the ElementTree API significantly to offer support for XPath,
RelaxNG, XML Schema, XSLT, C14N and much more.

To contact the project, go to the `project home page <https://lxml.de/>`_
or see our bug tracker at https://launchpad.net/lxml

In case you want to use the current in-development version of lxml,
you can get it from the github repository at
https://github.com/lxml/lxml .  Note that this requires Cython to
build the sources, see the build instructions on the project home page.

""" + branch_link).format(branch_version=versioninfo.branch_version())
    + versioninfo.changes()),
    classifiers=[
        versioninfo.dev_status(),
        'Intended Audience :: Developers',
        'Intended Audience :: Information Technology',
        'Programming Language :: Cython',
        # NOTE: keep in sync with 'python_requires' list above.
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Programming Language :: Python :: 3.13',
        'Programming Language :: C',
        'Operating System :: OS Independent',
        'Topic :: Text Processing :: Markup :: HTML',
        'Topic :: Text Processing :: Markup :: XML',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ],

    **setup_extra_options()
)

if OPTION_RUN_TESTS:
    print("Running tests.")
    import test
    try:
        sys.exit( test.main(sys.argv[:1]) )
    except ImportError:
        pass  # we assume that the binaries were not built with this setup.py run
