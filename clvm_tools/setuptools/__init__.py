from .build_clvm import build_clvm  # noqa
from .patch_build_py import patch_build_py
from .patched_build_py import build_py


def monkey_patch():
    patch_build_py(build_py)
