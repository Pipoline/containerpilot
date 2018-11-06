import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="containerpilot",
    version="0.0.1",
    author="Peter Gonda",
    author_email="peter@pipoline.com",
    description="Autopilot pattern python implementation",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Pipoline/containerpilot",
    packages=setuptools.find_packages(),
    license="MIT",
    include_package_data=True,
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Topic :: Utilities",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    install_requires=(
        'python-consul',
        'netifaces'
    )
)
