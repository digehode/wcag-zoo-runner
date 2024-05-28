# django-wcag-zoo-runner


# Config files

If a file called ~wcag_zoo_runner.ini~ exists in the current
directory, it will be used to decide which URLs to test.

## Format

    [include]
    /example/url
    /etc/
    /

    [exclude]
    /not/this
    /admin/.*


Regular expressions can be used in the exclude block.

The project URLs will sometimes have patterns defined as a regex or as
a URL with a component (e.g. ~/products/<int: id>/info~). You can
exclude these using a regex in the exclude block, or include an
example in the include block. The runner will look for a matching URL
in includes first, then for a regex in excludes.

## Generating a config gile

Use the ~--gather-urls~ option to generate an ini file. It will be displayed on stdout.

You will need to edit this!

Include examples that match the URL patterns, or exclude them.

Whole sets can be excluded, such as those that start ~__debug__~ or ~/admin~ like the below:

    [exclude]
    /__debug__/.*
    /admin/.*
