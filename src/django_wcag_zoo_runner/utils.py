""" Utilities for interacting with django """

import os
import sys
from pathlib import Path

import django


def get_django_package(search_root=".") -> str:
    """A simple hueristic to find the main package for this Django project.

    Based on:
    - https://github.com/mindvessel/django-project-template

    """
    root = Path(search_root)

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
    settings_module = str(package) + ".settings"
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", str(settings_module))
    django.setup()


def get_urlconf():
    """Load the project urlconf and return it"""
    try:
        urlconf = __import__(django.conf.settings.ROOT_URLCONF, {}, {}, [""])
    except Exception as e:
        raise ImportError(
            f"Couldn't import urlconf '{django.conf.settings.ROOT_URLCONF}': {e}"
        ) from e

    return urlconf


def flatten_urlpatterns(urlpatterns, base="", namespace=None):
    """Given a starting url pattern, return the flattened tree"""
    views = []
    for p in urlpatterns:
        if isinstance(p, django.urls.URLPattern):
            if namespace:
                name = f"{namespace}:{p.name}"
            else:
                name = p.name
            pattern = str(p.pattern)
            views.append((p.callback, base + pattern, name))
        elif isinstance(p, django.urls.URLResolver) or hasattr(p, "url_patterns"):
            patterns = p.url_patterns
            if namespace and p.namespace:
                _namespace = f"{namespace}:{p.namespace}"
            else:
                _namespace = p.namespace or namespace
            views.extend(
                flatten_urlpatterns(
                    patterns, base + str(p.pattern), namespace=_namespace
                )
            )
        elif hasattr(p, "_get_callback"):
            # pylint: disable=W0212
            views.append(
                (
                    p._get_callback(),
                    base + str(p.pattern),
                    p.name,
                )
            )
        else:
            raise TypeError(f"{p} does not appear to be a urlpattern object")
    return views


def project_urls():
    """Gather all URLs for the active project

    returns list of tuples (view, pattern, name)
    """
    urlpatterns = get_urlconf().urlpatterns
    return flatten_urlpatterns(urlpatterns)
