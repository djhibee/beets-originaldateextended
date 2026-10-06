beets-originaldateextended
=================

Plugin for beets that backup year field in flexible attribute in case original_date option is used and we need to get original release year later.

Motivation
----------

I'm using original_date option to set year field with original_year because my audio player does not read original_year tag.
However, I organize my album paths according to release year so I need this info, lost after original_date processing.
Thanks to new flexible attribute "original_year_backup", I will be able to access the info later.


Installation
------------

    $> pip install git+https://github.com/djhibee/beets-origindateextended

Next, add the following section to your beets config file to enable plugin:

    plugins:
        - originaldateextended

Configuration
-------------

---------
