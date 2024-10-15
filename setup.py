import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="cvdupdate",
    version="1.1.2",
    author="The ClamAV Team",
    author_email="clamav-bugs@external.cisco.com",
    copyright="Copyright (C) 2022 Cisco Systems, Inc. and/or its affiliates. All rights reserved.",
    description="ClamAV Private Database Mirror Updater Tool",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Cisco-Talos/cvdupdate",
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
        "dnspython>=2.1.0",
        "rangehttpserver",
        "setuptools",
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ],
)
