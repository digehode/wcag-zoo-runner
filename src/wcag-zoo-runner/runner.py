""" Simple tool to run a django development server and test the urls with wcag-zoo """
# pylint: disable=R0914, W0718
import os
import subprocess
import time

import django
import requests
from django.urls import get_resolver
from termcolor import colored
from utils import activate_django_project
from wcag_zoo.validators.anteater import Anteater
from wcag_zoo.validators.ayeaye import Ayeaye
from wcag_zoo.validators.molerat import Molerat
from wcag_zoo.validators.tarsier import Tarsier

LICENCE = """wcag-zoo-runner  Copyright (C) 2024  James Shuttleworth
This program comes with ABSOLUTELY NO WARRANTY;
This is free software, and you are welcome to redistribute it
under certain conditions, specified by the GPL V3;
for details: https://www.gnu.org/licenses/gpl-3.0.html
"""


def run_server(host="0.0.0.0", port="8799", logfile="server-wcag-zoo-log.txt"):
    """Run the django development server"""

    with open(logfile, "w", encoding="utf-8") as log:
        # Use environment variable to turn off the debug toolbar
        # Not appropriate to flag problems with that since it's only used in debugging
        # But we need DEBUG to be on so that static files are served

        environment = os.environ.copy()
        environment["DEBUG_TOOLBAR"] = "False"

        return subprocess.Popen(
            ["python", "manage.py", "runserver", f"{host}:{port}"],
            stdout=log,
            stderr=log,
            env=environment,
        )


def wcag_tool_on_url(tool, url: str, timeout: int, staticpath=".", level="AAA"):
    """Use the provided wcag-zoo tool to analyse the given URL"""

    # Retry multiple times, devrementing retries var to 0
    # Sleep doubles after each retry

    retries = 3
    delay = 1
    success = False
    while not success:
        success = True
        try:
            content = requests.get(url, timeout=timeout)
        except (
            requests.HTTPError,
            ConnectionError,
            TimeoutError,
            ConnectionRefusedError,
            Exception,
        ) as e:
            success = False
            print("Server not responding")
            if retries > 0:
                print(f"Retry after a delay of {delay}")
            else:
                print("No more retries")
                raise ConnectionError("Failed to reach server") from e
            retries -= 1
            time.sleep(delay)
            delay *= 2

    instance = tool(staticpath=staticpath, level=level)
    results = instance.validate_document(content.content)

    flat_results = {i: [] for i in ["success", "failures", "warnings", "skipped"]}
    for h in flat_results.keys():
        for i in results[h]:
            for j in results[h][i]:
                for k in results[h][i][j]:
                    flat_results[h].append(k)

    return flat_results


def combine_results(res1, res2):
    """Takes two sets of wcag-zoo results and combines them"""
    result = {}
    if res1.keys() != res2.keys():
        raise KeyError("Keys don't match")
    for i in res1:
        result[i] = res1[i] + res2[i]
    return result


def wcag_on_url(url: str, timeout: int = 3, staticpath=".", level="AAA"):
    """Run all wcag-zoo tools on the given url"""
    results = {i: [] for i in ["success", "failures", "warnings", "skipped"]}

    tools = [Tarsier, Anteater, Ayeaye, Molerat]
    for tool in tools:
        result = wcag_tool_on_url(
            tool, url, timeout, staticpath=staticpath, level=level
        )
        results = combine_results(results, result)
    return results


def display_results_hierarchy(h, style="white"):
    """Diplay results in a given style"""
    output = ""
    mainkeys = ["guideline", "technique", "xpath", "classes", "id"]
    for i in h:
        block = ""
        for k in mainkeys:
            block += f"\t{k}: {i[k]}\n"
        for k in i.keys():
            if k in mainkeys:
                continue
            block += f"\t{k}: {i[k]}\n"
        block = block.rstrip()
        output += block + "\n\t----\n"
    print(colored(output, style))


def display_results(results, verbosity: int = 2):
    """display each category of results in an appropriate style

    verbosity
    ---------

    2 (default) : show all categories, even if empty
    1 : show failures, warnings and skipped checks
    0 : show only failures
    """

    if verbosity > 1:
        print(colored("✓ SUCCESSES", "green"))
        display_results_hierarchy(results["success"], "green")
    print(colored("✗ FAILURES", "red"))
    display_results_hierarchy(results["failures"], "red")
    if verbosity > 0:
        print(colored("‼ WARNINGS", "yellow"))
        display_results_hierarchy(results["warnings"], "yellow")
        print(colored("↷ SKIPPED", "blue"))
        display_results_hierarchy(results["skipped"], "blue")


def gather_urls():
    """Returns a list of URLS for the django app"""
    # urls=get_resolver().reverse_dict.keys()
    allurls = {v[1] for k, v in get_resolver(None).reverse_dict.items()}
    urls = []

    for i in allurls:
        if i.startswith("admin"):
            continue
        if i.startswith("media"):
            continue
        urls.append(i.replace(r"\Z", "").replace(r"\.", "."))
    return urls


def main():
    """Run on execution"""
    host = "0.0.0.0"
    port = 8799
    staticpath = "./var"
    level = "AAA"
    activate_django_project()
    django.setup()
    urls = gather_urls()
    for i in urls:
        print(i)

    a = run_server(host, port)
    try:
        for url in urls:
            print(f"Testing url: '{url}'")
            result = wcag_on_url(
                f"http://{host}:{port}/{url}", staticpath=staticpath, level=level
            )
            display_results(result, verbosity=1)
    except ConnectionError as e:
        print(f"Failed to load and test: {e}")
        a.terminate()
    finally:
        # FUTURE: have fail-on-error version and interactive shell version
        print("Terminating server process")
        a.terminate()


if __name__ == "__main__":
    print(LICENCE)
    main()


# os.environ.setdefault("DJANGO_SETTINGS_MODULE", "server.settings")

# from django.core.management import call_command
# from django.core.wsgi import get_wsgi_application
# application = get_wsgi_application()
# call_command('runserver',  '127.0.0.1:8000')
