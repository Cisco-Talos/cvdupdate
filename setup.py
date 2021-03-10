import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="cvdupdate",
    version="0.3.0",
    author="Micah Snyder",
    author_email="micasnyd@cisco.com",
    copyright="Copyright (C) 2021 Micah Snyder.",
    description="ClamAV Private Database Mirror Updater Tool",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/micahsnyder/cvdupdate",
    packages=setuptools.find_packages(),
    entry_points={
        "console_scripts": [
            "cvdupdate = cvdupdate.__main__:cli",
            "cvd = cvdupdate.__main__:cli",
        ]
    },
    install_requires=[
        "click>=7.0",
        "coloredlogs>=10.0",
        "colorama",
        "requests",
        "dnspython",
        "rangehttpserver",
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ],
)
