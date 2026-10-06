import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="beets-originaldateextended",
    version="0.1",
    author="djhibee",
    packages=['beetsplug'],
    author_email="",
    description="enhance original_date option by backuping release year in flex attribute release_year_backup",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/djhibee/beets-originaldateextended",
    python_requires='>=3.6',
    install_requires=[
        "beets>=1.5.0",
        ]
)
