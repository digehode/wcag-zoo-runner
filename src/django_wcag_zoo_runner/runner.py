""" Simple tool to run a django development server and test the urls with wcag-zoo """

# pylint: disable=R0914, W0718
import argparse
import os
import subprocess
import time

import django
import requests
from django.urls import get_resolver
from wcag_zoo.validators.anteater import Anteater
from wcag_zoo.validators.ayeaye import Ayeaye
from wcag_zoo.validators.molerat import Molerat
from wcag_zoo.validators.tarsier import Tarsier

from . import dwr_logging
from .utils import activate_django_project

LICENCE = """wcag-zoo-runner  Copyright (C) 2024  James Shuttleworth
This program comes with ABSOLUTELY NO WARRANTY;
This is free software, and you are welcome to redistribute it
under certain conditions, specified by the GPL V3;
for details: https://www.gnu.org/licenses/gpl-3.0.html
"""


def run_server(host="0.0.0.0", port: int = 8799, logfile="server-wcag-zoo-log.txt"):
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


def get_url(url: str, timeout: int, logger):
    """Load content from the given URL"""

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
            logger.debug("Server not responding")
            if retries > 0:
                logger.debug(f"Retry after a delay of {delay}")
            else:
                logger.error("No more retries - giving up")
                raise ConnectionError("Failed to reach server") from e
            retries -= 1
            time.sleep(delay)
            delay *= 2
    return content


def wcag_tool_on_content(tool, content: str, url: str, staticpath=".", level="AAA"):
    """Use the provided wcag-zoo tool to analyse the given content"""

    instance = tool(staticpath=staticpath, level=level)
    results = instance.validate_document(content.content)
    flat_results = {i: [] for i in ["success", "failures", "warnings", "skipped"]}
    for h in flat_results.keys():
        for i in results[h]:
            for j in results[h][i]:
                for k in results[h][i][j]:
                    k["url"] = url
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


def wcag_on_url(url: str, logger, timeout: int = 3, staticpath=".", level="AAA"):
    """Run all wcag-zoo tools on the given url"""
    results = {i: [] for i in ["success", "failures", "warnings", "skipped"]}

    tools = [Tarsier, Anteater, Ayeaye, Molerat]
    content = get_url(url, timeout, logger)
    content_type = content.headers["Content-Type"]
    if not content_type.startswith("text/html"):
        logger.info(f"Skipping {url} - not HTML - Content type={content_type}")
        return results
    for tool in tools:
        result = wcag_tool_on_content(
            tool, content, url, staticpath=staticpath, level=level
        )
        results = combine_results(results, result)
    return results


def process_results_hierarchy(h):
    """Diplay results in a given style"""
    output = ""
    mainkeys = ["url", "guideline", "technique", "xpath", "classes", "id"]
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
    return output


def display_results(results, logger):
    """display each category of results in an appropriate style"""

    if len(results["success"]) > 0:
        logger.full("✓ SUCCESSES")
        logger.full(process_results_hierarchy(results["success"]))
    if len(results["failures"]) > 0:
        logger.error("✗ FAILURES")
        logger.error(process_results_hierarchy(results["failures"]))
    if len(results["warnings"]) > 0:
        logger.warning("‼ WARNINGS")
        logger.warning(process_results_hierarchy(results["warnings"]))
    if len(results["skipped"]) > 0:
        logger.info("↷ SKIPPED")
        logger.info(process_results_hierarchy(results["skipped"]))


def gather_urls():
    """Returns a list of URLS for the django app"""

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
    print(LICENCE)
    # verbosity
    # ---------

    # 2 (default) : show all categories, even if empty
    # 1 : show failures, warnings and skipped checks
    # 0 : show only failures

    parser = argparse.ArgumentParser(
        prog="python -m django_wcag_zoo_runner",
        description="Run WCAG zoo tools on a django project",
        epilog="Provided under GPL v3",
    )
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        help="Port on which to run demo server",
        default=8799,
    )
    parser.add_argument(
        "--verbosity",
        "-v",
        type=int,
        help="Set verbosity (0 - errors only, 1 - include warnings, "
        + "2 - include skipped tests, 3 - include successful tests, "
        + "4 - include debug info)."
        + " Default: 1",
        metavar="N",
        choices=[0, 1, 2, 3, 4],
        default=1,
    )
    parser.add_argument(
        "--staticpath",
        "-s",
        type=str,
        help="Set path for static files. Default: ./static",
        metavar="STATIC",
        default="./static",
    )
    parser.add_argument(
        "--level",
        "-l",
        type=str,
        help="Set WCAG zoo level: AA or AAA. Default: AAA",
        metavar="LEVEL",
        choices=["AA", "AAA"],
        default="AAA",
    )
    args = parser.parse_args()

    logger = dwr_logging.Logger(args.verbosity)
    host = "0.0.0.0"
    port = args.port
    level = "AAA"
    activate_django_project()
    django.setup()
    urls = gather_urls()
    logger.debug(f"Gathered URLS: {urls}")
    a = run_server(host, port)
    try:
        for url in urls:
            logger.debug(f"Testing url: '{url}'")
            result = wcag_on_url(
                f"http://{host}:{port}/{url}",
                logger,
                staticpath=args.staticpath,
                level=level,
            )
            display_results(result, logger)
    except ConnectionError as e:
        logger.debug(f"Failed to load and test: {e}")
        a.terminate()
    finally:
        # FUTURE: have fail-on-error version and interactive shell version
        logger.debug("Terminating server process")
        a.terminate()


if __name__ == "__main__":
    main()
