# adapted from https://github.com/PyO3/setuptools-rust

from distutils.command.install import install
from distutils.dist import Distribution as DistDistribution
from setuptools.dist import Distribution

try:
    from wheel.bdist_wheel import bdist_wheel

    wheel = True
except ImportError:
    wheel = False


def patch_build_py(build_py):
    # allow to use 'clvm_extensions' parameter for setup() call
    Distribution.clvm_extensions = ()

    # replace setuptools build_py
    Distribution.orig_get_command_class = Distribution.get_command_class

    def get_command_class(self, command):
        if command == "build_py":
            if command not in self.cmdclass:
                self.cmdclass[command] = build_py

        return self.orig_get_command_class(command)

    Distribution.get_command_class = get_command_class

    # this is required because, install directly access distribution's
    # ext_modules attr to check if dist has ext modules
    install.orig_finalize_options = install.finalize_options

    def finalize_options(self):
        # all ext modules
        clvm_files = []
        if self.distribution.clvm_extensions:
            clvm_files.extend(self.distribution.clvm_extensions)

        self.orig_finalize_options()

    install.finalize_options = finalize_options
