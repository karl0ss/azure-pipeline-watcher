"""Setup script for azure-pipeline-watcher."""

from setuptools import setup, find_packages

with open("README.md", "r") as f:
    long_description = f.read()

with open("requirements.txt", "r") as f:
    requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]

setup(
    name="azure-pipeline-watcher",
    version="1.0.0",
    author="Karl Hudgell",
    author_email="karl@k-world.me.uk",
    description="Monitor Azure DevOps pipelines for the currently logged-in user",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/karl0ss/azure-pipeline-watcher",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "azure_pipeline_watcher": ["config.json.sample"],
    },
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "azure-pipeline-watcher=azure_pipeline_watcher.cli:main",
        ],
    },
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
