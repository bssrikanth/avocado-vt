"""
Package utility for manage package operation on host
"""
import logging
import aexpect

from avocado.core import exceptions
from avocado.utils import software_manager
from avocado.utils import path as utils_path
from six import string_types

from virttest import utils_misc
from virttest import vt_console

PACKAGE_MANAGERS = ['apt-get',
                    'yum',
                    'zypper',
                    'dnf']


class RemotePackageMgr(object):

    """
    The remote package manage class
    """

    def __init__(self, session, pkg):
        """
        :param session: session object
        :param pkg: package name or list
        """
        if not isinstance(session,
                          (aexpect.ShellSession,
                           aexpect.Expect,
                           vt_console.ConsoleSession)):
            raise exceptions.TestError("Parameters exception on session")
        if not isinstance(pkg, list):
            if not isinstance(pkg, string_types):
                raise exceptions.TestError("pkg %s must be list or str" % pkg)
            else:
                self.pkg_list = [pkg, ]
        else:
            self.pkg_list = pkg
        self.package_manager = None
        self.cmd = None
        self.query_cmd = None
        self.install_cmd = None
        self.remove_cmd = None
        self.clean_cmd = None
        self.session = session
        self.provides_cmd = None
        self.update_cache_cmd = None

        # Inspect and set package manager
        for pkg_mgr in PACKAGE_MANAGERS:
            cmd = 'which ' + pkg_mgr
            if not self.session.cmd_status(cmd):
                self.package_manager = pkg_mgr
                break

        if not self.package_manager:
            raise exceptions.TestError("Package manager not in %s" %
                                       PACKAGE_MANAGERS)
        elif self.package_manager == 'apt-get':
            self.query_cmd = "dpkg -s "
            self.remove_cmd = "apt-get --purge remove -y "
            self.install_cmd = "apt-get install -y "
            self.clean_cmd = "apt-get clean"
            self.provides_cmd = "apt-file search"
            self.update_cache_cmd = "apt-file update"
        else:
            self.query_cmd = "rpm -q "
            self.remove_cmd = self.package_manager + " remove -y "
            self.install_cmd = self.package_manager + " install -y "
            self.clean_cmd = self.package_manager + " clean all"
            self.provides_cmd = self.package_manager + " provides"

    def clean(self):
        """
        Run clean command to refresh repo db

        :return: True or False
        """
        return not self.session.cmd_status(self.clean_cmd)

    def is_installed(self, pkg_name):
        """
        Check the package installed status

        :param pkg_name: package name
        :return: True or False
        """
        cmd = self.query_cmd + pkg_name
        return not self.session.cmd_status(cmd)

    def provides(self):
        """
        Use package manager remove packages

        :param filename: binary/file which needs package to be found
        :return: if found return package name else False
        """
        error = False
        if self.update_cache_cmd:
            error = self.session.cmd_status(self.update_cache_cmd)
        if not error:
            package_list = {}
            try:
                for filename in self.pkg_list:
                    if self.package_manager in  ('yum', 'dnf'):
                        p_cmd = self.provides_cmd + " " + filename + "| grep 'noarch\|ppc' | tail -1 | awk -F ':' '{print $1}'"
                    else:
                        p_cmd = self.provides_cmd + " --regexp " + filename + "| awk -F ':' '{print $1}'"
                    package_list[filename] = self.session(p_cmd)
                    if not package_list[filename]:
                        logging.error("Filename %s has no providers ", filename)
                        error = True
                if error:
                    return None
                else:
                    return package_list
            except process.CmdError:
                    return None
        else:
            return False

    def operate(self, timeout, default_status, internal_timeout=2):
        """
        Run command and return status

        :param timeout: command timeout
        :param default_status: package default installed status
        :return: True of False
        """
        for pkg in self.pkg_list:
            need = False
            if '*' not in pkg:
                if self.is_installed(pkg) == default_status:
                    need = True
            else:
                need = True
            if need:
                cmd = self.cmd + pkg
                if self.session.cmd_status(cmd, timeout, internal_timeout):
                    # Try to clean the repo db and re-try installation
                    if not self.clean():
                        logging.error("Package %s was broken",
                                      self.package_manager)
                        return False
                    if self.session.cmd_status(cmd, timeout):
                        logging.error("Operate %s with %s failed", pkg, cmd)
                        return False
        return True

    def install(self, pkg=None,timeout=300):
        """
        Use package manager install packages

        :param timeout: install timeout
        :return: if install succeed return True, else False
        """
        self.cmd = self.install_cmd
        if pkg:
            self.pkg_list = pkg
        return self.operate(timeout, False)

    def remove(self, timeout=300):
        """
        Use package manager remove packages

        :param timeout: remove timeout
        :return: if remove succeed return True, else False
        """
        self.cmd = self.remove_cmd
        return self.operate(timeout, True)


class LocalPackageMgr(software_manager.SoftwareManager):

    """
    Local package manage class
    """

    def __init__(self, pkg):
        """
        :param pkg: package name or list
        """
        if not isinstance(pkg, list):
            if not isinstance(pkg, string_types):
                raise exceptions.TestError("pkg %s must be list or str" % pkg)
            else:
                self.pkg_list = [pkg, ]
        else:
            self.pkg_list = pkg
        super(LocalPackageMgr, self).__init__()
        self.func = None

    def operate(self, default_status=False, provides=False):
        """
        Use package manager to operate packages

        :param default_status: package default installed status
        """

        if not provides:
            for pkg in self.pkg_list:
                need = False
                if '*' not in pkg:
                    if self.check_installed(pkg) == default_status:
                        need = True
                else:
                    need = True
                if need:
                    if not self.func(pkg):
                        logging.error("Operate %s on host failed", pkg)
                        return False
        else:
            package_list = {}
            for filename in self.pkg_list:
                logging.info("operate: %s", filename)
                package_list[filename] = self.func(filename)
                if package_list[filename] == None:
                    logging.error("Unable to find providing package for %s", filename)
                    return False
            return package_list

        return True

    def install(self, pkg=None):
        """
        Use package manager install packages

        :return: if install succeed return True, else False
        """
        self.func = super(LocalPackageMgr, self).__getattr__('install')
        if pkg:
            self.pkg_list = pkg
        return self.operate(False)

    def remove(self):
        """
        Use package manager remove packages

        :return: if remove succeed return True, else False
        """
        self.func = super(LocalPackageMgr, self).__getattr__('remove')
        return self.operate(True)

    def provides(self):
        """
        Use package manager provides packages

        :return: if remove succeed return True, else False
        """
        self.func = super(LocalPackageMgr, self).__getattr__('provides')
        return self.operate(False,True)

def package_manager(session, pkg):
    """
    Package manager function

    :param session: session object
    :param pkg: pkg name or list
    :return: package manager class object
    """
    if session:
        mgr = RemotePackageMgr(session, pkg)
    else:
        mgr = LocalPackageMgr(pkg)
        logging.info("in LocalPackageMgr")
    return mgr


def package_install(pkg, session=None, timeout=300):
    """
    Try to install packages on system with package manager.

    :param pkg: package name or list of packages
    :param session: session Object
    :param timeout: timeout for install with session
    :return: True if all packages installed, False if any error
    """
    mgr = package_manager(session, pkg)
    return utils_misc.wait_for(mgr.install, timeout)


def package_remove(pkg, session=None, timeout=300):
    """
    Try to remove packages on system with package manager.

    :param pkg: package name or list of packages
    :param session: session Object
    :param timeout: timeout for remove with session
    :return: True if all packages removed, False if any error
    """
    mgr = package_manager(session, pkg)
    return utils_misc.wait_for(mgr.remove, timeout)

def package_provides(filenames, session=None, timeout=300):
    """
    Try to find packages providing binaries on system with package manager.

    :param pkg: binary or filenames
    :param session: session Object
    :param timeout: timeout for remove with session
    :return: package which provides given file/binary, False if error, None if not found
    """
    mgr = package_manager(session, "")
    logging.info("package_provides")
    if session:
        if not utils_misc.wait_for(mgr.install(mgr.provides_cmd.split(" ")[0]), timeout):
            return False
    mgr.pkg_list = filenames
    logging.info("mgr.pkg_list: %s", mgr.pkg_list)
    return utils_misc.wait_for(mgr.provides, timeout)
