import setuptools  # type:ignore

import notiontree

with open("README.md") as readme_f:
    long_description_md = readme_f.read()

version = notiontree.__version__

with open("requirements.txt") as requirements_f:
    install_requires = [
        req.strip()
        for req in requirements_f.read().splitlines()
        if not req.strip().startswith("#") and "git+" not in req
    ]

setuptools.setup(
    name="notion-tree",
    version=version,
    author="Aurélien Delobelle",
    author_email="aurelien.delobelle@gmail.com",
    license="MIT",
    keywords="notion structure hierarchy export import sync",
    url="https://github.com/aureplop/notion-tree",
    project_urls={
        "Source": "https://github.com/aureplop/notion-tree",
        "Tracker": "https://github.com/aureplop/notion-tree/issues",
    },
    long_description=long_description_md,
    long_description_content_type="text/markdown",
    packages=setuptools.find_packages(exclude="test"),
    include_package_data=True,
    install_requires=install_requires,
    python_requires=">=3.6",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
