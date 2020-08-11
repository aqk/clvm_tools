from distutils import log
from setuptools.command.build_py import build_py as _build_py


class build_py(_build_py):

    def __init__(self, *args):
        _build_py.__init__(self, *args)

    def has_clvm_extensions(self):
        return (
            self.distribution.clvm_extensions
            and len(self.distribution.clvm_extensions) > 0
        )

    def run(self):
        """Run build_clvm sub command """
        if self.has_clvm_extensions():
            log.info("running build_clvm")
            build_clvm = self.get_finalized_command("build_clvm")
            build_clvm.run()

        _build_py.run(self)
