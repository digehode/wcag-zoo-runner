""" Simple tool to run a django development server and test the urls with wcag-zoo """

# pylint: disable=R0914, W0718
import argparse
import configparser
import os
import re
import subprocess
import time

import requests
from wcag_zoo.validators.anteater import Anteater
from wcag_zoo.validators.ayeaye import Ayeaye
from wcag_zoo.validators.molerat import Molerat
from wcag_zoo.validators.tarsier import Tarsier

from . import dwr_logging
from .utils import activate_django_project, project_urls

LICENCE = """wcag-zoo-runner  Copyright (C) 2024  James Shuttleworth
This program comes with ABSOLUTELY NO WARRANTY;
This is free software, and you are welcome to redistribute it
under certain conditions, specified by the GPL V3;
for details: https://www.gnu.org/licenses/gpl-3.0.html
"""


def load_conf(configfile: str = "wcag_zoo_runner.ini"):
    """Load config file and return congifparser object"""
    config = configparser.ConfigParser(delimiters=("="), allow_no_value=True)
    config.read(configfile)
    return config


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


def sanitise_url(url: str):
    """Remove Django URL matching info from given URL"""
    replacements = [(r"\Z", ""), (r"\.", ".")]
    for r in replacements:
        url = url.replace(r[0], r[1])
    return f"{url}"


def url_test_excluded_path(url: str):
    """Test if a URL is probably NOT worth testing
    - that is, is it in one of the usually excluded paths?"""

    excluded_starts = ["admin", "media", "static", "__debug__"]
    for ex in excluded_starts:
        if url.startswith(ex):
            return True
    return False


def url_test_includes_values(url: str):
    """Test if a given URL string has places for values
    eg: /products/<int:prod_id>/detail
    """

    exp = ".*<.*>.*"
    if re.search(exp, url) is not None:
        return True
    return False


def generate_default_urls():
    """Generate a list of URLs that can probably be tested

    Used when a list isn't provided and won't deal with any URLs thay
    have parameters, admin, etc. and also to create a basic config file
    """

    allurls = project_urls()
    urls = {"include": [], "exclude": [], "complex": []}

    for url in allurls:
        i = url[1]
        if url_test_excluded_path(i):
            urls["exclude"].append(i)
        elif url_test_includes_values(i):
            urls["complex"].append(i)
        else:
            urls["include"].append(i)

    return urls


def gather_urls():
    """Display Django URLs on stdout"""
    urls = generate_default_urls()
    print("[include]")
    for url in urls["include"]:
        print(sanitise_url(url))
    print("[test]")
    for url in urls["complex"]:
        print(f"## {sanitise_url(url)}")
    print("[exclude]")
    for url in urls["exclude"]:
        print(sanitise_url(url))


def test_coverage(urls, logger):
    """Given a list of grouped URLs (include/exclude keys in dict), check the list
    covers the full range of URLs for the django project
    """

    django_urls = project_urls()
    proposed = list(urls["include"]) + list(urls["exclude"])
    logger.debug("Checking coverage")

    for i in django_urls:
        found = False
        url = f"/{i[1]}"
        logger.debug(f"Checking project URL: '{url}'")
        if url in proposed:
            found = True
            logger.debug("\tFound plain match")
        else:
            # Check if we have a regex that matches an included URL
            r = re.compile(url)
            for j in urls["include"]:
                if r.match(j):
                    logger.debug(f"\tFound included URL match to regex: '{j}'")
                    found = True
                    break
            if found:
                continue
            # Check if an excluded URL is a regex that covers this
            for j in urls["exclude"]:
                try:
                    r = re.compile(j)
                except re.error:
                    continue
                if r.match(url):
                    logger.debug(f"\tFound exclude regex that matches URL: '{j}'")
                    found = True
                    break
        if not found:
            logger.warning(f"Couldn't find a match for project URL '{url}'")


def main():
    """Run on execution"""

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

    parser.add_argument(
        "--gather-urls",
        action=argparse.BooleanOptionalAction,
        help="Output list of discovered URL patterns",
        default=False,
    )

    args = parser.parse_args()

    logger = dwr_logging.Logger(args.verbosity)
    logger.info(LICENCE)
    host = "0.0.0.0"
    port = args.port
    level = args.level
    activate_django_project()

    if args.gather_urls:
        gather_urls()
        return

    a = run_server(host, port)

    config = load_conf()
    if "include" in config.sections():
        urls = config
        test_coverage(urls, logger)
    else:
        logger.warning(
            "Using default URL gathering. This will "
            + "not guarantee coverage and will almost certainly"
            + " ignore key URLs. Create ini file and explicitly"
            + " list URLs to test in order to test complex URLs"
            + " and enable coverage testing.\n"
            + "Use the --gather-urls option to generate "
            + "starting content for an ini file"
        )
        urls = generate_default_urls()

    try:
        for url in urls["include"]:
            url = sanitise_url(url)
            logger.debug(f"Testing url: '{url}'")
            result = wcag_on_url(
                f"http://{host}:{port}{url}",
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
