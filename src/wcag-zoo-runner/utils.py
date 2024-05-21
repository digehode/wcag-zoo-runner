""" Utilities for interacting with django """
import os
import sys
from pathlib import Path


def get_django_package(search_root=".") -> str:
    """A simple hueristic to find the main package for this Django project.

    Based on:
    - https://github.com/mindvessel/django-project-template

    """
    root = Path(search_root)
    print(f"Searching {root}")
    for item in root.iterdir():
        if not item.is_dir():
            continue
        if item.joinpath("settings.py").exists():
            return (Path(item.name), Path(item.name).parent.absolute())

    raise ModuleNotFoundError(
        """Unable to locate a likely module
        No subdirectory had a Django settings file """
        + f"""(searched {search_root}*/settings.py). """
    )


def activate_django_project(search_root="."):
    """Find and activate a django project
    in order to make use of django funcitons related to the project"""
    package, fullpath = get_django_package(search_root)
    sys.path.append(str(fullpath))
    print(f"{package} # {fullpath} # {sys.path}")
    settings_module = str(package) + ".settings"
    print(f"Using {settings_module}")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", str(settings_module))
