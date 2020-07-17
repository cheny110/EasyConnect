#-----------------------------------------------------------------------------
# Copyright (c) 2005-2020, PyInstaller Development Team.
#
# Distributed under the terms of the GNU General Public License (version 2
# or later) with exception for distributing the bootloader.
#
# The full license is in the file COPYING.txt, distributed with this software.
#
# SPDX-License-Identifier: (GPL-2.0-or-later WITH Bootloader-exception)
#-----------------------------------------------------------------------------


"""
This module contains classes that are available for the .spec files.

Spec file is generated by PyInstaller. The generated code from .spec file
is a way how PyInstaller does the dependency analysis and creates executable.
"""
import os
import shutil
import tempfile
import pprint
from operator import itemgetter

from PyInstaller import HOMEPATH, PLATFORM
from PyInstaller.archive.writers import ZlibArchiveWriter, CArchiveWriter
from PyInstaller.building.utils import _check_guts_toc, add_suffix_to_extensions, \
    checkCache, strip_paths_in_code, get_code_object, \
    _make_clean_directory
from PyInstaller.compat import is_win, is_darwin, is_linux, is_cygwin, exec_command_all
from PyInstaller.depend import bindepend
from PyInstaller.depend.analysis import get_bootstrap_modules
from PyInstaller.depend.utils import is_path_to_egg
from PyInstaller.building.datastruct import TOC, Target, _check_guts_eq
from PyInstaller.utils import misc
from .. import log as logging

logger = logging.getLogger(__name__)

if is_win:
    from PyInstaller.utils.win32 import winmanifest, icon, versioninfo, winresource


class PYZ(Target):
    """
    Creates a ZlibArchive that contains all pure Python modules.
    """
    typ = 'PYZ'

    def __init__(self, *tocs, **kwargs):
        """
        tocs
                One or more TOCs (Tables of Contents), normally an
                Analysis.pure.

                If this TOC has an attribute `_code_cache`, this is
                expected to be a dict of module code objects from
                ModuleGraph.

        kwargs
            Possible keywork arguments:

            name
                A filename for the .pyz. Normally not needed, as the generated
                name will do fine.
            cipher
                The block cipher that will be used to encrypt Python bytecode.

        """

        from ..config import CONF
        Target.__init__(self)
        name = kwargs.get('name', None)
        cipher = kwargs.get('cipher', None)
        self.toc = TOC()
        # If available, use code objects directly from ModuleGraph to
        # speed up PyInstaller.
        self.code_dict = {}
        for t in tocs:
            self.toc.extend(t)
            self.code_dict.update(getattr(t, '_code_cache', {}))

        self.name = name
        if name is None:
            self.name = os.path.splitext(self.tocfilename)[0] + '.pyz'
        # PyInstaller bootstrapping modules.
        self.dependencies = get_bootstrap_modules()
        # Bundle the crypto key.
        self.cipher = cipher
        if cipher:
            key_file = ('pyimod00_crypto_key',
                         os.path.join(CONF['workpath'], 'pyimod00_crypto_key.pyc'),
                         'PYMODULE')
            # Insert the key as the first module in the list. The key module contains
            # just variables and does not depend on other modules.
            self.dependencies.insert(0, key_file)
        # Compile the top-level modules so that they end up in the CArchive and can be
        # imported by the bootstrap script.
        self.dependencies = misc.compile_py_files(self.dependencies, CONF['workpath'])
        self.__postinit__()

    _GUTS = (# input parameters
            ('name', _check_guts_eq),
            ('toc', _check_guts_toc),  # todo: pyc=1
            # no calculated/analysed values
            )

    def _check_guts(self, data, last_build):
        if Target._check_guts(self, data, last_build):
            return True
        return False

    def assemble(self):
        logger.info("Building PYZ (ZlibArchive) %s", self.name)
        # Do not bundle PyInstaller bootstrap modules into PYZ archive.
        toc = self.toc - self.dependencies
        for entry in toc[:]:
            if not entry[0] in self.code_dict and entry[2] == 'PYMODULE':
                # For some reason the code-object, modulegraph created
                # is not available. Recreate it
                try:
                    self.code_dict[entry[0]] = get_code_object(entry[0], entry[1])
                except SyntaxError:
                    # Exclude the module in case this is code meant for a newer Python version.
                    toc.remove(entry)
        # sort content alphabetically to support reproducible builds
        toc.sort()

        # Remove leading parts of paths in code objects
        self.code_dict = {
            key: strip_paths_in_code(code)
            for key, code in self.code_dict.items()
        }

        pyz = ZlibArchiveWriter(self.name, toc, code_dict=self.code_dict, cipher=self.cipher)
        logger.info("Building PYZ (ZlibArchive) %s completed successfully.",
                    self.name)


class PKG(Target):
    """
    Creates a CArchive. CArchive is the data structure that is embedded
    into the executable. This data structure allows to include various
    read-only data in a sigle-file deployment.
    """
    typ = 'PKG'
    xformdict = {'PYMODULE': 'm',
                 'PYSOURCE': 's',
                 'EXTENSION': 'b',
                 'PYZ': 'z',
                 'PKG': 'a',
                 'DATA': 'x',
                 'BINARY': 'b',
                 'ZIPFILE': 'Z',
                 'EXECUTABLE': 'b',
                 'DEPENDENCY': 'd'}

    def __init__(self, toc, name=None, cdict=None, exclude_binaries=0,
                 strip_binaries=False, upx_binaries=False, upx_exclude=None):
        """
        toc
                A TOC (Table of Contents)
        name
                An optional filename for the PKG.
        cdict
                Dictionary that specifies compression by typecode. For Example,
                PYZ is left uncompressed so that it can be accessed inside the
                PKG. The default uses sensible values. If zlib is not available,
                no compression is used.
        exclude_binaries
                If True, EXTENSIONs and BINARYs will be left out of the PKG,
                and forwarded to its container (usually a COLLECT).
        strip_binaries
                If True, use 'strip' command to reduce the size of binary files.
        upx_binaries
        """
        Target.__init__(self)
        self.toc = toc
        self.cdict = cdict
        self.name = name
        if name is None:
            self.name = os.path.splitext(self.tocfilename)[0] + '.pkg'
        self.exclude_binaries = exclude_binaries
        self.strip_binaries = strip_binaries
        self.upx_binaries = upx_binaries
        self.upx_exclude = upx_exclude or []
        # This dict tells PyInstaller what items embedded in the executable should
        # be compressed.
        if self.cdict is None:
            self.cdict = {'EXTENSION': COMPRESSED,
                          'DATA': COMPRESSED,
                          'BINARY': COMPRESSED,
                          'EXECUTABLE': COMPRESSED,
                          'PYSOURCE': COMPRESSED,
                          'PYMODULE': COMPRESSED,
                          # Do not compress PYZ as a whole. Single modules are
                          # compressed when creating PYZ archive.
                          'PYZ': UNCOMPRESSED}
        self.__postinit__()

    _GUTS = (# input parameters
            ('name', _check_guts_eq),
            ('cdict', _check_guts_eq),
            ('toc', _check_guts_toc),  # list unchanged and no newer files
            ('exclude_binaries', _check_guts_eq),
            ('strip_binaries', _check_guts_eq),
            ('upx_binaries', _check_guts_eq),
            ('upx_exclude', _check_guts_eq)
            # no calculated/analysed values
            )

    def _check_guts(self, data, last_build):
        if Target._check_guts(self, data, last_build):
            return True
        return False

    def assemble(self):
        logger.info("Building PKG (CArchive) %s", os.path.basename(self.name))
        trash = []
        mytoc = []
        srctoc = []
        seenInms = {}
        seenFnms = {}
        seenFnms_typ = {}
        toc = add_suffix_to_extensions(self.toc)
        # 'inm'  - relative filename inside a CArchive
        # 'fnm'  - absolute filename as it is on the file system.
        for inm, fnm, typ in toc:
            # Ensure filename 'fnm' is not None or empty string. Otherwise
            # it will fail in case of 'typ' being type OPTION.
            if fnm and not os.path.isfile(fnm) and is_path_to_egg(fnm):
                # file is contained within python egg, it is added with the egg
                continue
            if typ in ('BINARY', 'EXTENSION', 'DEPENDENCY'):
                if not self.exclude_binaries:
                    if typ == 'BINARY':
                        # Avoid importing the same binary extension twice. This might
                        # happen if they come from different sources (eg. once from
                        # binary dependence, and once from direct import).
                        if inm in seenInms:
                            logger.warning('Two binaries added with the same internal name.')
                            logger.warning(pprint.pformat((inm, fnm, typ)))
                            logger.warning('was placed previously at')
                            logger.warning(pprint.pformat((inm, seenInms[inm], seenFnms_typ[seenInms[inm]])))
                            logger.warning('Skipping %s.' % fnm)
                            continue

                        # Warn if the same binary extension was included
                        # with multiple internal names
                        if fnm in seenFnms:
                            logger.warning('One binary added with two internal names.')
                            logger.warning(pprint.pformat((inm, fnm, typ)))
                            logger.warning('was placed previously at')
                            logger.warning(pprint.pformat((seenFnms[fnm], fnm, seenFnms_typ[fnm])))
                    seenInms[inm] = fnm
                    seenFnms[fnm] = inm
                    seenFnms_typ[fnm] = typ

                    fnm = checkCache(fnm, strip=self.strip_binaries,
                                     upx=self.upx_binaries,
                                     upx_exclude=self.upx_exclude,
                                     dist_nm=inm)

                    mytoc.append((inm, fnm, self.cdict.get(typ, 0),
                                  self.xformdict.get(typ, 'b')))
            elif typ == 'OPTION':
                mytoc.append((inm, '', 0, 'o'))
            elif typ in ('PYSOURCE', 'PYMODULE'):
                # collect sourcefiles and module in a toc of it's own
                # which will not be sorted.
                srctoc.append((inm, fnm, self.cdict[typ], self.xformdict[typ]))
            else:
                mytoc.append((inm, fnm, self.cdict.get(typ, 0), self.xformdict.get(typ, 'b')))

        # Bootloader has to know the name of Python library. Pass python libname to CArchive.
        pylib_name = os.path.basename(bindepend.get_python_library_path())

        # Sort content alphabetically by type and name to support
        # reproducible builds.
        mytoc.sort(key=itemgetter(3, 0))
        # Do *not* sort modules and scripts, as their order is important.
        # TODO: Think about having all modules first and then all scripts.
        archive = CArchiveWriter(self.name, srctoc + mytoc,
                                 pylib_name=pylib_name)

        for item in trash:
            os.remove(item)
        logger.info("Building PKG (CArchive) %s completed successfully.",
                    os.path.basename(self.name))


class EXE(Target):
    """
    Creates the final executable of the frozen app.
    This bundles all necessary files together.
    """
    typ = 'EXECUTABLE'

    def __init__(self, *args, **kwargs):
        """
        args
                One or more arguments that are either TOCs Targets.
        kwargs
            Possible keywork arguments:

            bootloader_ignore_signals
                Non-Windows only. If True, the bootloader process will ignore
                all ignorable signals. If False (default), it will forward
                all signals to the child process. Useful in situations where
                e.g. a supervisor process signals both the bootloader and
                child (e.g. via a process group) to avoid signalling the
                child twice.
            console
                On Windows or OSX governs whether to use the console executable
                or the windowed executable. Always True on Linux/Unix (always
                console executable - it does not matter there).
            debug
                Setting to True gives you progress mesages from the executable
                (for console=False there will be annoying MessageBoxes on Windows).
            name
                The filename for the executable. On Windows suffix '.exe' is
                appended.
            exclude_binaries
                Forwarded to the PKG the EXE builds.
            icon
                Windows or OSX only. icon='myicon.ico' to use an icon file or
                icon='notepad.exe,0' to grab an icon resource.
            version
                Windows only. version='myversion.txt'. Use grab_version.py to get
                a version resource from an executable and then edit the output to
                create your own. (The syntax of version resources is so arcane
                that I wouldn't attempt to write one from scratch).
            uac_admin
                Windows only. Setting to True creates a Manifest with will request
                elevation upon application restart
            uac_uiaccess
                Windows only. Setting to True allows an elevated application to
                work with Remote Desktop
        """
        from ..config import CONF
        Target.__init__(self)

        # Available options for EXE in .spec files.
        self.exclude_binaries = kwargs.get('exclude_binaries', False)
        self.bootloader_ignore_signals = kwargs.get(
            'bootloader_ignore_signals', False)
        self.console = kwargs.get('console', True)
        self.debug = kwargs.get('debug', False)
        self.name = kwargs.get('name', None)
        self.icon = kwargs.get('icon', None)
        self.versrsrc = kwargs.get('version', None)
        self.manifest = kwargs.get('manifest', None)
        self.resources = kwargs.get('resources', [])
        self.strip = kwargs.get('strip', False)
        self.upx_exclude = kwargs.get("upx_exclude", [])
        self.runtime_tmpdir = kwargs.get('runtime_tmpdir', None)
        # If ``append_pkg`` is false, the archive will not be appended
        # to the exe, but copied beside it.
        self.append_pkg = kwargs.get('append_pkg', True)

        # On Windows allows the exe to request admin privileges.
        self.uac_admin = kwargs.get('uac_admin', False)
        self.uac_uiaccess = kwargs.get('uac_uiaccess', False)

        if CONF['hasUPX']:
            self.upx = kwargs.get('upx', False)
        else:
            self.upx = False

        # Old .spec format included in 'name' the path where to put created
        # app. New format includes only exename.
        #
        # Ignore fullpath in the 'name' and prepend DISTPATH or WORKPATH.
        # DISTPATH - onefile
        # WORKPATH - onedir
        if self.exclude_binaries:
            # onedir mode - create executable in WORKPATH.
            self.name = os.path.join(CONF['workpath'], os.path.basename(self.name))
        else:
            # onefile mode - create executable in DISTPATH.
            self.name = os.path.join(CONF['distpath'], os.path.basename(self.name))

        # Old .spec format included on Windows in 'name' .exe suffix.
        if is_win or is_cygwin:
            # Append .exe suffix if it is not already there.
            if not self.name.endswith('.exe'):
                self.name += '.exe'
            base_name = os.path.splitext(os.path.basename(self.name))[0]
        else:
            base_name = os.path.basename(self.name)
        self.pkgname = base_name + '.pkg'

        self.toc = TOC()

        for arg in args:
            if isinstance(arg, TOC):
                self.toc.extend(arg)
            elif isinstance(arg, Target):
                self.toc.append((os.path.basename(arg.name), arg.name, arg.typ))
                self.toc.extend(arg.dependencies)
            else:
                self.toc.extend(arg)

        if self.runtime_tmpdir is not None:
            self.toc.append(("pyi-runtime-tmpdir " + self.runtime_tmpdir, "", "OPTION"))

        if self.bootloader_ignore_signals:
            # no value; presence means "true"
            self.toc.append(("pyi-bootloader-ignore-signals", "", "OPTION"))

        if is_win:
            filename = os.path.join(CONF['workpath'], CONF['specnm'] + ".exe.manifest")
            self.manifest = winmanifest.create_manifest(filename, self.manifest,
                self.console, self.uac_admin, self.uac_uiaccess)

            manifest_filename = os.path.basename(self.name) + ".manifest"

            self.toc.append((manifest_filename, filename, 'BINARY'))
            if not self.exclude_binaries:
                # Onefile mode: manifest file is explicitly loaded.
                # Store name of manifest file as bootloader option. Allows
                # the exe to be renamed.
                self.toc.append(("pyi-windows-manifest-filename " + manifest_filename,
                                 "", "OPTION"))

            if self.versrsrc:
                if (not isinstance(self.versrsrc, versioninfo.VSVersionInfo)
                    and not os.path.isabs(self.versrsrc)):
                    # relative version-info path is relative to spec file
                    self.versrsrc = os.path.join(
                        CONF['specpath'], self.versrsrc)

        self.pkg = PKG(self.toc, cdict=kwargs.get('cdict', None),
                       exclude_binaries=self.exclude_binaries,
                       strip_binaries=self.strip, upx_binaries=self.upx,
                       upx_exclude=self.upx_exclude
                       )
        self.dependencies = self.pkg.dependencies

        # Get the path of the bootloader and store it in a TOC, so it
        # can be checked for being changed.
        exe = self._bootloader_file('run', '.exe' if is_win or is_cygwin else '')
        self.exefiles = TOC([(os.path.basename(exe), exe, 'EXECUTABLE')])

        self.__postinit__()

    _GUTS = (# input parameters
            ('name', _check_guts_eq),
            ('console', _check_guts_eq),
            ('debug', _check_guts_eq),
            ('exclude_binaries', _check_guts_eq),
            ('icon', _check_guts_eq),
            ('versrsrc', _check_guts_eq),
            ('uac_admin', _check_guts_eq),
            ('uac_uiaccess', _check_guts_eq),
            ('manifest', _check_guts_eq),
            ('append_pkg', _check_guts_eq),
            # for the case the directory ius shared between platforms:
            ('pkgname', _check_guts_eq),
            ('toc', _check_guts_eq),
            ('resources', _check_guts_eq),
            ('strip', _check_guts_eq),
            ('upx', _check_guts_eq),
            ('mtm', None,),  # checked below
            # no calculated/analysed values
            ('exefiles', _check_guts_toc),
            )

    def _check_guts(self, data, last_build):
        if not os.path.exists(self.name):
            logger.info("Rebuilding %s because %s missing",
                        self.tocbasename, os.path.basename(self.name))
            return 1
        if not self.append_pkg and not os.path.exists(self.pkgname):
            logger.info("Rebuilding because %s missing",
                        os.path.basename(self.pkgname))
            return 1

        if Target._check_guts(self, data, last_build):
            return True

        if (data['versrsrc'] or data['resources']) and not is_win:
            # todo: really ignore :-)
            logger.warning('ignoring version, manifest and resources, platform not capable')
        if data['icon'] and not (is_win or is_darwin):
            logger.warning('ignoring icon, platform not capable')

        mtm = data['mtm']
        if mtm != misc.mtime(self.name):
            logger.info("Rebuilding %s because mtimes don't match", self.tocbasename)
            return True
        if mtm < misc.mtime(self.pkg.tocfilename):
            logger.info("Rebuilding %s because pkg is more recent", self.tocbasename)
            return True
        return False

    def _bootloader_file(self, exe, extension=None):
        """
        Pick up the right bootloader file - debug, console, windowed.
        """
        # Having console/windowed bootolader makes sense only on Windows and
        # Mac OS X.
        if is_win or is_darwin:
            if not self.console:
                exe = exe + 'w'
        # There are two types of bootloaders:
        # run     - release, no verbose messages in console.
        # run_d   - contains verbose messages in console.
        if self.debug:
            exe = exe + '_d'
        if extension:
            exe = exe + extension
        bootloader_file = os.path.join(HOMEPATH, 'PyInstaller', 'bootloader', PLATFORM, exe)
        logger.info('Bootloader %s' % bootloader_file)
        return bootloader_file

    def assemble(self):
        from ..config import CONF
        logger.info("Building EXE from %s", self.tocbasename)
        trash = []
        if os.path.exists(self.name):
            os.remove(self.name)
        if not os.path.exists(os.path.dirname(self.name)):
            os.makedirs(os.path.dirname(self.name))
        exe = self.exefiles[0][1]  # pathname of bootloader
        if not os.path.exists(exe):
            raise SystemExit(_MISSING_BOOTLOADER_ERRORMSG)


        if is_win and (self.icon or self.versrsrc or self.resources):
            fd, tmpnm = tempfile.mkstemp(prefix=os.path.basename(exe) + ".",
                                         dir=CONF['workpath'])
            # need to close the file, otherwise copying resources will fail
            # with "the file [...] is being used by another process"
            os.close(fd)
            self._copyfile(exe, tmpnm)
            os.chmod(tmpnm, 0o755)
            if self.icon:
                icon.CopyIcons(tmpnm, self.icon)
            if self.versrsrc:
                versioninfo.SetVersion(tmpnm, self.versrsrc)
            for res in self.resources:
                res = res.split(",")
                for i in range(1, len(res)):
                    try:
                        res[i] = int(res[i])
                    except ValueError:
                        pass
                resfile = res[0]
                if not os.path.isabs(resfile):
                    resfile = os.path.join(CONF['specpath'], resfile)
                restype = resname = reslang = None
                if len(res) > 1:
                    restype = res[1]
                if len(res) > 2:
                    resname = res[2]
                if len(res) > 3:
                    reslang = res[3]
                try:
                    winresource.UpdateResourcesFromResFile(tmpnm, resfile,
                                                        [restype or "*"],
                                                        [resname or "*"],
                                                        [reslang or "*"])
                except winresource.pywintypes.error as exc:
                    if exc.args[0] != winresource.ERROR_BAD_EXE_FORMAT:
                        logger.error("Error while updating resources in %s"
                                     " from resource file %s", tmpnm, resfile, exc_info=1)
                        continue

                    # Handle the case where the file contains no resources, and is
                    # intended as a single resource to be added to the exe.
                    if not restype or not resname:
                        logger.error("resource type and/or name not specified")
                        continue
                    if "*" in (restype, resname):
                        logger.error("no wildcards allowed for resource type "
                                     "and name when source file does not "
                                     "contain resources")
                        continue
                    try:
                        winresource.UpdateResourcesFromDataFile(tmpnm,
                                                             resfile,
                                                             restype,
                                                             [resname],
                                                             [reslang or 0])
                    except winresource.pywintypes.error:
                        logger.error("Error while updating resource %s %s in %s"
                                     " from data file %s",
                                     restype, resname, tmpnm, resfile, exc_info=1)
            if is_win and self.manifest and not self.exclude_binaries:
                self.manifest.update_resources(tmpnm, [1])
            trash.append(tmpnm)
            exe = tmpnm

        # NOTE: Do not look up for bootloader file in the cache because it might
        #       get corrupted by UPX when UPX is available. See #1863 for details.

        if not self.append_pkg:
            logger.info("Copying bootloader exe to %s", self.name)
            self._copyfile(exe, self.name)
            logger.info("Copying archive to %s", self.pkgname)
            self._copyfile(self.pkg.name, self.pkgname)
        elif is_linux:
            self._copyfile(exe, self.name)
            logger.info("Appending archive to ELF section in EXE %s", self.name)
            retcode, stdout, stderr = exec_command_all(
                'objcopy', '--add-section', 'pydata=%s' % self.pkg.name,
                self.name)
            logger.debug("objcopy returned %i", retcode)
            if stdout:
                logger.debug(stdout)
            if stderr:
                logger.debug(stderr)
            if retcode != 0:
                raise SystemError("objcopy Failure: %s" % stderr)
        else:
            # Fall back to just append on end of file
            logger.info("Appending archive to EXE %s", self.name)
            with open(self.name, 'wb') as outf:
                # write the bootloader data
                with open(exe, 'rb') as infh:
                    shutil.copyfileobj(infh, outf, length=64*1024)
                # write the archive data
                with open(self.pkg.name, 'rb') as infh:
                    shutil.copyfileobj(infh, outf, length=64*1024)

        if is_darwin:
            # Fix Mach-O header for codesigning on OS X.
            logger.info("Fixing EXE for code signing %s", self.name)
            import PyInstaller.utils.osx as osxutils
            osxutils.fix_exe_for_code_signing(self.name)

        os.chmod(self.name, 0o755)
        # get mtime for storing into the guts
        self.mtm = misc.mtime(self.name)
        for item in trash:
            os.remove(item)
        logger.info("Building EXE from %s completed successfully.",
                    self.tocbasename)


    def _copyfile(self, infile, outfile):
        with open(infile, 'rb') as infh:
            with open(outfile, 'wb') as outfh:
                shutil.copyfileobj(infh, outfh, length=64*1024)


class COLLECT(Target):
    """
    In one-dir mode creates the output folder with all necessary files.
    """
    def __init__(self, *args, **kws):
        """
        args
                One or more arguments that are either TOCs Targets.
        kws
            Possible keywork arguments:

                name
                    The name of the directory to be built.
        """
        from ..config import CONF
        Target.__init__(self)
        self.strip_binaries = kws.get('strip', False)
        self.upx_exclude = kws.get("upx_exclude", [])
        self.console = True

        if CONF['hasUPX']:
            self.upx_binaries = kws.get('upx', False)
        else:
            self.upx_binaries = False

        self.name = kws.get('name')
        # Old .spec format included in 'name' the path where to collect files
        # for the created app.
        # app. New format includes only directory name.
        #
        # The 'name' directory is created in DISTPATH and necessary files are
        # then collected to this directory.
        self.name = os.path.join(CONF['distpath'], os.path.basename(self.name))

        self.toc = TOC()
        for arg in args:
            if isinstance(arg, TOC):
                self.toc.extend(arg)
            elif isinstance(arg, Target):
                self.toc.append((os.path.basename(arg.name), arg.name, arg.typ))
                if isinstance(arg, EXE):
                    self.console = arg.console
                    for tocnm, fnm, typ in arg.toc:
                        if tocnm == os.path.basename(arg.name) + ".manifest":
                            self.toc.append((tocnm, fnm, typ))
                    if not arg.append_pkg:
                        self.toc.append((os.path.basename(arg.pkgname), arg.pkgname, 'PKG'))
                self.toc.extend(arg.dependencies)
            else:
                self.toc.extend(arg)
        self.__postinit__()

    _GUTS = (
        # COLLECT always builds, just want the toc to be written out
        ('toc', None),
    )

    def _check_guts(self, data, last_build):
        # COLLECT always needs to be executed, since it will clean the output
        # directory anyway to make sure there is no existing cruft accumulating
        return 1

    def assemble(self):
        _make_clean_directory(self.name)
        logger.info("Building COLLECT %s", self.tocbasename)
        toc = add_suffix_to_extensions(self.toc)
        for inm, fnm, typ in toc:
            if not os.path.exists(fnm) or not os.path.isfile(fnm) and is_path_to_egg(fnm):
                # file is contained within python egg, it is added with the egg
                continue
            if os.pardir in os.path.normpath(inm).split(os.sep) \
               or os.path.isabs(inm):
                raise SystemExit('Security-Alert: try to store file outside '
                                 'of dist-directory. Aborting. %r' % inm)
            tofnm = os.path.join(self.name, inm)
            todir = os.path.dirname(tofnm)
            if not os.path.exists(todir):
                os.makedirs(todir)
            elif not os.path.isdir(todir):
                raise SystemExit(
                    "Pyinstaller needs to make a directory, but there "
                    "already is a file at that path. "
                    "The file at issue is {!r}".format(todir))
            if typ in ('EXTENSION', 'BINARY'):
                fnm = checkCache(fnm, strip=self.strip_binaries,
                                 upx=self.upx_binaries,
                                 upx_exclude=self.upx_exclude,
                                 dist_nm=inm)
            if typ != 'DEPENDENCY':
                if os.path.isdir(fnm):
                    # beacuse shutil.copy2() is the default copy function
                    # for shutil.copytree, this will also copy file metadata
                    shutil.copytree(fnm, tofnm)
                else:
                    shutil.copy(fnm, tofnm)
                try:
                    shutil.copystat(fnm, tofnm)
                except OSError:
                    logger.warning("failed to copy flags of %s", fnm)
            if typ in ('EXTENSION', 'BINARY'):
                os.chmod(tofnm, 0o755)
        logger.info("Building COLLECT %s completed successfully.",
                    self.tocbasename)


class MERGE(object):
    """
    Merge repeated dependencies from other executables into the first
    execuable. Data and binary files are then present only once and some
    disk space is thus reduced.
    """
    def __init__(self, *args):
        """
        Repeated dependencies are then present only once in the first
        executable in the 'args' list. Other executables depend on the
        first one. Other executables have to extract necessary files
        from the first executable.

        args  dependencies in a list of (Analysis, id, filename) tuples.
              Replace id with the correct filename.
        """
        # The first Analysis object with all dependencies.
        # Any item from the first executable cannot be removed.
        self._main = None

        self._dependencies = {}

        self._id_to_path = {}
        for _, i, p in args:
            self._id_to_path[os.path.normcase(i)] = p

        # Get the longest common path
        common_prefix = os.path.commonprefix([os.path.normcase(os.path.abspath(a.scripts[-1][1])) for a, _, _ in args])
        self._common_prefix = os.path.dirname(common_prefix)
        if self._common_prefix[-1] != os.sep:
            self._common_prefix += os.sep
        logger.info("Common prefix: %s", self._common_prefix)

        self._merge_dependencies(args)

    def _merge_dependencies(self, args):
        """
        Filter shared dependencies to be only in first executable.
        """
        for analysis, _, _ in args:
            path = os.path.abspath(analysis.scripts[-1][1]).replace(self._common_prefix, "", 1)
            path = os.path.splitext(path)[0]
            if os.path.normcase(path) in self._id_to_path:
                path = self._id_to_path[os.path.normcase(path)]
            self._set_dependencies(analysis, path)

    def _set_dependencies(self, analysis, path):
        """
        Synchronize the Analysis result with the needed dependencies.
        """
        for toc in (analysis.binaries, analysis.datas):
            for i, tpl in enumerate(toc):
                if not tpl[1] in self._dependencies:
                    logger.debug("Adding dependency %s located in %s" % (tpl[1], path))
                    self._dependencies[tpl[1]] = path
                else:
                    dep_path = self._get_relative_path(path, self._dependencies[tpl[1]])
                    logger.debug("Referencing %s to be a dependecy for %s, located in %s" % (tpl[1], path, dep_path))
                    analysis.dependencies.append((":".join((dep_path, tpl[0])), tpl[1], "DEPENDENCY"))
                    toc[i] = (None, None, None)
            # Clean the list
            toc[:] = [tpl for tpl in toc if tpl != (None, None, None)]

    # TODO move this function to PyInstaller.compat module (probably improve
    #      function compat.relpath()
    # TODO use os.path.relpath instead
    def _get_relative_path(self, startpath, topath):
        start = startpath.split(os.sep)[:-1]
        start = ['..'] * len(start)
        if start:
            start.append(topath)
            return os.sep.join(start)
        else:
            return topath


UNCOMPRESSED = 0
COMPRESSED = 1

_MISSING_BOOTLOADER_ERRORMSG = """
Fatal error: PyInstaller does not include a pre-compiled bootloader for your
platform. For more details and instructions how to build the bootloader see
<https://pyinstaller.readthedocs.io/en/stable/bootloader-building.html>
"""
